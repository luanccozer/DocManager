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


def estrategias(proxy: str | None = None, url: str = "",
                log_cb: Log = _nada) -> list[tuple[str, dict | None, bool]]:
    """Rotas a tentar, na ordem. Cada item: (nome, proxies|None, trust_env).

    `proxies=None` → deixa o `requests` decidir pelo ambiente;
    `proxies={}`   → força SEM proxy (conexão direta).
    Um `proxy` explícito curto-circuita tudo: é escolha do usuário.
    """
    if proxy:
        return [("proxy informado", {"http": proxy, "https": proxy}, False)]
    rotas: list[tuple[str, dict | None, bool]] = []
    # Primeiro o proxy do PAC, resolvido pelo Windows — ver a seção no fim
    # deste módulo. Sem PAC devolve [] e a ordem antiga fica intacta.
    vistos: set[str] = set()
    for endereco in (proxies_do_windows_para(url, log_cb) if url else []):
        if endereco in vistos:
            continue
        vistos.add(endereco)
        alvo = endereco if "://" in endereco else f"http://{endereco}"
        rotas.append((f"proxy do Windows ({endereco})", {"http": alvo, "https": alvo}, False))
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
    rotas = estrategias(proxy, url, log_cb)
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

# ─────────────────── proxy resolvido PELO WINDOWS (arquivo PAC) ──────────────
#
# Caso real que motivou este bloco (máquina da CMI, 18/09/2026):
#
#     ProxyEnable   = 0
#     AutoConfigURL = http://127.0.0.1:9999/4049_gpproxy.pac
#
# Não há proxy estático — só um arquivo PAC, servido pelo próprio agente do
# GlobalProtect. E o `urllib.request.getproxies()` lê SOMENTE `ProxyEnable` e
# `ProxyServer`: com ProxyEnable=0 ele responde "sem proxy", o app vai direto, e
# a VPN descarta os pacotes em silêncio — 21 segundos de timeout, sem pista.
#
# Um PAC é um programa JavaScript (`FindProxyForURL(url, host)`) e a resposta
# MUDA POR DESTINO — e, num PAC de VPN, muda também conforme o túnel esteja de
# pé (proxy local no 127.0.0.1) ou não (gateway do Zscaler). Interpretar isso em
# Python exigiria embutir um motor de JavaScript. A saída limpa é perguntar ao
# WINDOWS, que já faz isso o dia inteiro para o navegador: `WinHttpGetProxyForUrl`
# baixa o PAC, executa a função e responde qual proxy usar para AQUELA url.

_WINHTTP_ACCESS_TYPE_NO_PROXY = 1
_AUTOPROXY_AUTO_DETECT = 0x00000001
_AUTOPROXY_CONFIG_URL = 0x00000002
_AUTO_DETECT_DHCP = 0x00000001
_AUTO_DETECT_DNS_A = 0x00000002

# Códigos do WinHTTP que distinguem "esta rede não usa proxy" de "a consulta
# falhou" — sem isso, as duas situações viram o mesmo silêncio.
_ERROS_WINHTTP = {
    12002: "a consulta ao PAC expirou",
    12015: "o proxy exige autenticação",
    12166: "o arquivo PAC deu erro ao executar",
    12167: "não foi possível baixar o arquivo PAC",
    12180: "a rede não publica WPAD",
}

# (proxies, momento) por URL. O WPAD sozinho custa segundos quando não há PAC
# nenhum, e a extração faz várias chamadas; mas o cache é CURTO de propósito:
# ligar ou desligar a VPN muda a resposta do PAC, e um valor descoberto na
# abertura do app valeria a sessão inteira — errado.
_VALIDADE_CACHE_S = 60.0
_cache_proxy: dict[str, tuple[list[str], float]] = {}


def esquecer_proxy_descoberto() -> None:
    """Descarta o cache — use ao trocar de rede ou ligar/desligar a VPN."""
    _cache_proxy.clear()


def normalizar_proxies(bruto: str) -> list[str]:
    """Resposta do WinHTTP/PAC → lista de 'host:porta'. Pura, testada.

    O WinHTTP costuma devolver a lista já sem o verbo, mas o formato do PAC
    permite `PROXY host:porta; DIRECT` e `SOCKS host:porta`. Aceitar as duas
    formas custa nada e evita o erro bobo de tratar a palavra "PROXY" como se
    fosse um endereço — e de tentar conectar num proxy chamado "DIRECT".
    """
    saida: list[str] = []
    for pedaco in str(bruto or "").replace(",", ";").split(";"):
        limpo = pedaco.strip()
        if not limpo or limpo.upper().startswith("DIRECT"):
            continue
        partes = limpo.split()
        if len(partes) > 1 and partes[0].upper() in ("PROXY", "SOCKS", "HTTP", "HTTPS"):
            limpo = partes[1]
        if limpo and limpo not in saida:
            saida.append(limpo)
    return saida


def _ler_e_liberar(ponteiro) -> str:
    """Lê uma string devolvida pelo WinHTTP e libera a memória (GlobalFree).

    Os campos saem como `c_void_p`, e não `LPWSTR`, justamente para isto: com
    LPWSTR o ctypes converteria para `str` e o endereço original se perderia —
    um vazamento a cada consulta.
    """
    import ctypes

    if not ponteiro:
        return ""
    try:
        return ctypes.wstring_at(ponteiro)
    finally:
        ctypes.windll.kernel32.GlobalFree(ctypes.c_void_p(ponteiro))


def proxies_do_windows_para(url: str, log_cb: Log = _nada) -> list[str]:
    """Os proxies que o NAVEGADOR usaria para `url`. [] = direto ou indisponível.

    Nunca levanta exceção: se o WinHTTP não colaborar, quem chama simplesmente
    segue com as rotas de sempre. Esta via só ACRESCENTA uma tentativa — não
    substitui nem rebaixa nenhuma das que já funcionavam.
    """
    if os.name != "nt":
        return []

    agora = __import__("time").monotonic()
    if (achado := _cache_proxy.get(url)) and agora - achado[1] < _VALIDADE_CACHE_S:
        return list(achado[0])

    import ctypes
    from ctypes import wintypes

    class _ConfigIE(ctypes.Structure):
        _fields_ = [("fAutoDetect", wintypes.BOOL),
                    ("lpszAutoConfigUrl", ctypes.c_void_p),
                    ("lpszProxy", ctypes.c_void_p),
                    ("lpszProxyBypass", ctypes.c_void_p)]

    class _Opcoes(ctypes.Structure):
        _fields_ = [("dwFlags", wintypes.DWORD),
                    ("dwAutoDetectFlags", wintypes.DWORD),
                    ("lpszAutoConfigUrl", wintypes.LPCWSTR),
                    ("lpvReserved", ctypes.c_void_p),
                    ("dwReserved", wintypes.DWORD),
                    ("fAutoLogonIfChallenged", wintypes.BOOL)]

    class _InfoProxy(ctypes.Structure):
        _fields_ = [("dwAccessType", wintypes.DWORD),
                    ("lpszProxy", ctypes.c_void_p),
                    ("lpszProxyBypass", ctypes.c_void_p)]

    try:
        # use_last_error: sem isto o `get_last_error()` não vale nada — qualquer
        # chamada entre a falha e a leitura já sobrescreveu o código.
        winhttp = ctypes.WinDLL("winhttp", use_last_error=True)
    except Exception as e:  # noqa: BLE001
        log_cb(f"  (WinHTTP indisponível: {e})")
        return []

    # argtypes/restype em TUDO. HINTERNET é ponteiro: sem `restype`, o ctypes
    # assume `c_int` e TRUNCA o handle para 32 bits num Python de 64. O handle
    # sai diferente de zero — parece válido — e toda chamada seguinte falha em
    # silêncio. É o bug que faz um app relatar "só conexão direta" numa rede que
    # publica PAC.
    winhttp.WinHttpOpen.restype = ctypes.c_void_p
    winhttp.WinHttpOpen.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPCWSTR,
                                    wintypes.LPCWSTR, wintypes.DWORD]
    winhttp.WinHttpCloseHandle.restype = wintypes.BOOL
    winhttp.WinHttpCloseHandle.argtypes = [ctypes.c_void_p]
    winhttp.WinHttpGetIEProxyConfigForCurrentUser.restype = wintypes.BOOL
    winhttp.WinHttpGetIEProxyConfigForCurrentUser.argtypes = [ctypes.POINTER(_ConfigIE)]
    winhttp.WinHttpGetProxyForUrl.restype = wintypes.BOOL
    winhttp.WinHttpGetProxyForUrl.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                              ctypes.POINTER(_Opcoes),
                                              ctypes.POINTER(_InfoProxy)]

    def _guardar(lista: list[str]) -> list[str]:
        _cache_proxy[url] = (list(lista), agora)
        return lista

    sessao = winhttp.WinHttpOpen("DocManagerItaipu", _WINHTTP_ACCESS_TYPE_NO_PROXY,
                                 None, None, 0)
    if not sessao:
        log_cb("  (WinHttpOpen falhou — seguindo sem o proxy do Windows)")
        return _guardar([])

    try:
        opcoes = _Opcoes()
        opcoes.fAutoLogonIfChallenged = True   # proxy corporativo pede credencial
        config = _ConfigIE()
        pac_url = ""

        # A configuração do USUÁRIO (a mesma do navegador) — não a do serviço,
        # que é o que o `netsh winhttp show proxy` mostra e costuma estar vazia.
        if winhttp.WinHttpGetIEProxyConfigForCurrentUser(ctypes.byref(config)):
            pac_url = _ler_e_liberar(config.lpszAutoConfigUrl)
            estatico = _ler_e_liberar(config.lpszProxy)
            _ler_e_liberar(config.lpszProxyBypass)
            if pac_url:
                opcoes.dwFlags = _AUTOPROXY_CONFIG_URL
                opcoes.lpszAutoConfigUrl = pac_url
                origem = f"PAC ({pac_url})"
            elif config.fAutoDetect:
                opcoes.dwFlags = _AUTOPROXY_AUTO_DETECT
                opcoes.dwAutoDetectFlags = _AUTO_DETECT_DHCP | _AUTO_DETECT_DNS_A
                origem = "autodetecção (WPAD)"
            elif estatico:
                lista = normalizar_proxies(estatico)
                log_cb(f"  Windows: proxy estático {', '.join(lista)}")
                return _guardar(lista)
            else:
                log_cb("  Windows: nenhum proxy configurado para o usuário.")
                return _guardar([])
        else:
            opcoes.dwFlags = _AUTOPROXY_AUTO_DETECT
            opcoes.dwAutoDetectFlags = _AUTO_DETECT_DHCP | _AUTO_DETECT_DNS_A
            origem = "autodetecção (WPAD)"

        info = _InfoProxy()
        if not winhttp.WinHttpGetProxyForUrl(sessao, url, ctypes.byref(opcoes),
                                             ctypes.byref(info)):
            codigo = ctypes.get_last_error()
            motivo = _ERROS_WINHTTP.get(codigo, f"erro {codigo}")
            log_cb(f"  Windows não resolveu o proxy por {origem}: {motivo}.")
            return _guardar([])

        lista = normalizar_proxies(_ler_e_liberar(info.lpszProxy))
        _ler_e_liberar(info.lpszProxyBypass)
        if lista:
            log_cb(f"  Windows resolveu, via {origem}: {', '.join(lista)}")
        else:
            log_cb(f"  Windows respondeu CONEXÃO DIRETA via {origem}.")
        return _guardar(lista)
    except Exception as e:  # noqa: BLE001 — nunca impedir as rotas antigas
        log_cb(f"  (falha ao consultar o proxy do Windows: {e})")
        return []
    finally:
        try:
            winhttp.WinHttpCloseHandle(sessao)
        except Exception:  # noqa: BLE001
            pass
