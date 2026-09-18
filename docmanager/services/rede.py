"""Acesso HTTP que sobrevive à rede da empresa (Zscaler + GlobalProtect).

O problema, e por que este módulo existe
----------------------------------------
Na CMI o tráfego HTTPS passa pela inspeção do Zscaler: ele termina o TLS e
reemite o certificado do site assinado por uma CA própria. Essa CA está
instalada no **Windows**, mas o Python não olha o Windows — ele usa o bundle do
`certifi`, que não a conhece. Resultado: todo `requests.get` morre com
`SSLError: certificate verify failed`. Com a VPN (GlobalProtect) ligada entra
ainda o proxy corporativo, que o `requests` só enxerga se `trust_env` estiver
ligado — e às vezes só a conexão DIRETA funciona.

É exatamente aí que um verificador de atualização ingênuo (um `requests.get` na
API do GitHub) falha silenciosamente e o app nunca avisa que há versão nova.

A solução, em três camadas, na ordem em que são tentadas:
  1. `truststore` injeta os certificados do **Windows** (inclusive o do Zscaler)
     na verificação SSL do Python — resolve o caso normal da máquina gerenciada;
  2. cascata de rotas — proxy do sistema, variáveis de ambiente, conexão direta —
     porque qual delas funciona muda com a VPN ligada ou desligada;
  3. só se TODAS falharem **por certificado**, uma última tentativa sem verificar
     o TLS, com aviso no log. Nunca antes: quem já funciona não é rebaixado.

O `aconex_backend` faz a mesma cascata, porém amarrada ao POST de token OAuth.
Aqui está a versão genérica (GET), usada pelo verificador de atualização.
"""
from __future__ import annotations

import os
import urllib.request
from typing import Callable, Iterable

Log = Callable[[str], None]


def _nada(_msg: str) -> None:
    """Log padrão: silencioso."""


def injetar_certificados_windows(log_cb: Log = _nada) -> bool:
    """Passa a validar TLS pela loja de certificados do Windows (Zscaler inclusive).

    Idempotente: chamar várias vezes não faz mal. Devolve False (com aviso no log)
    se o `truststore` não estiver disponível — aí a cascata ainda pode salvar.
    """
    try:
        import truststore

        truststore.inject_into_ssl()
        return True
    except Exception as e:  # noqa: BLE001 — sem truststore ainda dá para tentar
        log_cb(f"(truststore indisponível: {e} — se o Zscaler inspecionar o SSL, "
               f"a verificação pode falhar)")
        return False


def estrategias(proxy: str | None = None) -> list[tuple[str, dict | None, bool]]:
    """Rotas a tentar, na ordem. Cada item: (nome, proxies|None, trust_env).

    `proxies=None` → deixa o `requests` decidir pelo ambiente;
    `proxies={}`   → força SEM proxy (conexão direta).
    Um `proxy` explícito curto-circuita tudo: é escolha do usuário.
    """
    if proxy:
        return [("proxy informado", {"http": proxy, "https": proxy}, False)]
    rotas: list[tuple[str, dict | None, bool]] = []
    try:
        sistema = urllib.request.getproxies()
    except Exception:  # noqa: BLE001
        sistema = {}
    if sistema:
        rotas.append(("proxy do sistema", sistema, False))
    if any(os.getenv(v) for v in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")):
        rotas.append(("variáveis de ambiente", None, True))
    rotas.append(("conexão direta", {}, False))
    return rotas


class FalhaDeRede(RuntimeError):
    """Nenhuma rota chegou ao destino. A mensagem traz o diagnóstico de cada uma."""


def abrir(url: str, *, headers: dict | None = None, timeout: int = 30,
          stream: bool = False, proxy: str | None = None, log_cb: Log = _nada,
          status_ok: Iterable[int] = (200,)):
    """GET tentando cada rota até uma responder. Devolve `(session, response)`.

    A `session` volta junto de propósito: quem baixa o instalador reaproveita a
    MESMA rota que já funcionou para o manifesto, em vez de redescobri-la (e
    talvez cair numa rota diferente no meio do download).

    Levanta `FalhaDeRede` se nenhuma rota entregar um status de `status_ok`.
    Um status fora da lista (404, 401...) NÃO é erro de rota: interrompe a
    cascata na hora, porque trocar de proxy não muda a resposta do servidor.
    """
    import requests

    injetar_certificados_windows(log_cb)
    rotas = estrategias(proxy)
    problemas: list[str] = []
    houve_ssl = False

    for verificar_ssl in (True, False):
        if not verificar_ssl:
            if not houve_ssl:
                break   # nenhuma falha foi de certificado → não relaxa o TLS
            log_cb("⚠️ Último recurso: tentando SEM verificação de certificado "
                   "(o certificado do Zscaler/GlobalProtect não está no Windows).")
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:  # noqa: BLE001
                pass

        for nome, proxies, trust_env in rotas:
            sessao = requests.Session()
            sessao.trust_env = trust_env
            if proxies is not None:
                sessao.proxies = dict(proxies)
            sessao.verify = verificar_ssl
            try:
                resp = sessao.get(url, headers=headers or {}, timeout=timeout, stream=stream)
            except requests.exceptions.SSLError as e:
                houve_ssl = True
                problemas.append(f"{nome}: certificado não confiável ({str(e)[:80]})")
                log_cb(f"  [{nome}] certificado SSL não confiável.")
                sessao.close()
                continue
            except requests.exceptions.RequestException as e:
                problemas.append(f"{nome}: sem conexão ({str(e)[:80]})")
                log_cb(f"  [{nome}] sem conexão ({str(e)[:80]}).")
                sessao.close()
                continue

            if resp.status_code in status_ok:
                via = nome + ("" if verificar_ssl else " · SSL NÃO verificado")
                log_cb(f"Conectado via {via}.")
                return sessao, resp

            # Chegou ao servidor: o problema é a requisição, não a rota.
            corpo = ""
            if not stream:
                corpo = f" — {resp.text[:160]}"
            resp.close()
            sessao.close()
            raise FalhaDeRede(f"HTTP {resp.status_code} em {url}{corpo}")

    raise FalhaDeRede("Nenhuma rota de rede funcionou. Tentativas:\n  · "
                      + "\n  · ".join(problemas or ["(nenhuma rota disponível)"]))
