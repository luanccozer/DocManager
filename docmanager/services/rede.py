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
import urllib.parse
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
                problemas.append(f"{nome}: certificado não confiável ({resumo_erro(e, 120)})")
                log_cb(f"  [{nome}] certificado SSL não confiável — {resumo_erro(e)}")
                sessao.close()
                continue
            except requests.exceptions.RequestException as e:
                problemas.append(f"{nome}: sem conexão ({resumo_erro(e, 120)})")
                log_cb(f"  [{nome}] sem conexão — {resumo_erro(e)}")
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

    for linha in diagnostico(urllib.parse.urlparse(url).hostname or ""):
        log_cb(linha)
    raise FalhaDeRede("Nenhuma rota de rede funcionou. Tentativas:\n  · "
                      + "\n  · ".join(problemas or ["(nenhuma rota disponível)"]))


# ─────────────────────────── diagnóstico de rede ────────────────────────────
#
# Quando NENHUMA rota funciona, a pergunta seguinte é sempre a mesma: o Windows
# tem proxy configurado? qual? o nome resolve? a porta 443 abre? Sem isso o log
# só diz "sem conexão", que não distingue firewall de proxy errado, e a pessoa
# fica trocando de VPN no escuro. Estas funções respondem tudo de uma vez.

def resumo_erro(e: BaseException, limite: int = 240) -> str:
    """A mensagem MAIS ESPECÍFICA de uma exceção de rede.

    O `requests` embrulha o `urllib3`, que embrulha o erro de socket. O texto de
    fora ("HTTPSConnectionPool(host=..., port=443): Max retries exceeded") é o
    mesmo para causas completamente diferentes — timeout, DNS, conexão recusada,
    proxy recusando. Quem responde "o que aconteceu de fato" é a causa lá no
    fundo, que é o que esta função vai buscar.
    """
    especifico = e
    # requests.ConnectionError → MaxRetryError → .reason é o erro real.
    alvo = e.args[0] if getattr(e, "args", None) else None
    if (motivo := getattr(alvo, "reason", None)) is not None:
        especifico = motivo
    for _ in range(6):          # limite: cadeias circulares existem
        proxima = especifico.__cause__ or especifico.__context__
        if proxima is None:
            break
        especifico = proxima
    texto = f"{type(especifico).__name__}: {especifico}"
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


def _proxies_do_windows() -> list[str]:
    """Como o WINDOWS está configurado — que não é o que o Python enxerga.

    O `urllib.request.getproxies()` lê só `ProxyEnable`/`ProxyServer` do
    registro. Ele IGNORA o `AutoConfigURL` (arquivo PAC), que é justamente como
    o Zscaler costuma ser distribuído, e ignora a configuração do WinHTTP. Numa
    máquina só com PAC, o Python conclui "sem proxy" e tenta conexão direta —
    que a VPN bloqueia. Por isso o diagnóstico mostra as três coisas.
    """
    if os.name != "nt":
        return ["  (diagnóstico de proxy do Windows: só no Windows)"]
    linhas: list[str] = []
    try:
        import winreg

        chave = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
            for nome in ("ProxyEnable", "ProxyServer", "AutoConfigURL", "ProxyOverride"):
                try:
                    valor, _ = winreg.QueryValueEx(k, nome)
                    linhas.append(f"  {nome} = {valor}")
                except FileNotFoundError:
                    linhas.append(f"  {nome} = (não definido)")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"  (não foi possível ler o registro: {e})")

    try:
        import subprocess

        r = subprocess.run(["netsh", "winhttp", "show", "proxy"], capture_output=True,
                           text=True, timeout=15,
                           creationflags=0x08000000)   # CREATE_NO_WINDOW
        for linha in r.stdout.splitlines():
            if linha.strip():
                linhas.append(f"  [winhttp] {linha.strip()}")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"  (netsh winhttp indisponível: {e})")
    return linhas


def diagnostico(host: str, porta: int = 443) -> list[str]:
    """Relatório do estado da rede para `host`. Nunca levanta exceção."""
    import socket

    linhas = ["─── Diagnóstico de rede ───"]

    vistos = {v: os.getenv(v) for v in ("HTTPS_PROXY", "https_proxy",
                                        "HTTP_PROXY", "http_proxy", "NO_PROXY")}
    definidos = {k: v for k, v in vistos.items() if v}
    linhas.append(f"Variáveis de proxy do ambiente: {definidos or '(nenhuma)'}")

    try:
        linhas.append(f"O que o Python enxerga (getproxies): {urllib.request.getproxies() or '(nada)'}")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"O que o Python enxerga (getproxies): erro — {e}")

    linhas.append("Como o Windows está configurado:")
    linhas.extend(_proxies_do_windows())

    # DNS e TCP separados: dizem coisas diferentes. Nome que não resolve é
    # bloqueio de DNS; porta que não abre com o nome resolvendo é firewall.
    try:
        enderecos = sorted({info[4][0] for info in socket.getaddrinfo(host, porta)})
        linhas.append(f"DNS de {host}: {', '.join(enderecos)}")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"DNS de {host}: FALHOU — {e}")
        return linhas + ["→ O nome nem resolve: é bloqueio de DNS da rede/VPN, "
                         "não problema do aplicativo."]

    try:
        with socket.create_connection((host, porta), timeout=8):
            linhas.append(f"Conexão TCP direta a {host}:{porta}: ABRIU")
            linhas.append("→ A porta abre direto. Se mesmo assim a extração falha, "
                          "o bloqueio está no TLS ou o destino exige ir por proxy.")
    except socket.timeout:
        linhas.append(f"Conexão TCP direta a {host}:{porta}: TIMEOUT")
        linhas.append("→ Os pacotes estão sendo DESCARTADOS em silêncio (típico de "
                      "firewall corporativo). Ou o acesso a este destino não está "
                      "liberado na VPN, ou o tráfego precisa ir por um proxy que o "
                      "Python não descobriu — compare com o 'Como o Windows está "
                      "configurado' acima.")
    except Exception as e:  # noqa: BLE001
        linhas.append(f"Conexão TCP direta a {host}:{porta}: {type(e).__name__} — {e}")
    return linhas
