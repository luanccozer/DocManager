"""Diagnóstico de rede corporativa (Zscaler/GlobalProtect).

Estes testes existem por causa de um log real que não respondia a pergunta:

    [proxy do sistema] sem conexão (HTTPSConnectionPool(host='...', port=443): Max retr).
    [conexão direta]   sem conexão (HTTPSConnectionPool(host='...', port=443): Max retr).

As duas rotas falharam com a MESMA frase - que é a mesma para timeout, DNS,
conexão recusada e proxy recusando. Sem saber qual foi, não dá para agir.
"""
import socket

import pytest
import requests
import urllib3

from docmanager.services import rede


def _erro_do_requests(causa: Exception) -> requests.exceptions.ConnectionError:
    """Monta o embrulho real: requests(ConnectionError) → urllib3(MaxRetryError)."""
    mre = urllib3.exceptions.MaxRetryError(None, "https://x/auth/token", reason=causa)
    return requests.exceptions.ConnectionError(mre)


# --------------------------------------------------------------------------
# resumo_erro: achar a causa raiz
# --------------------------------------------------------------------------
def test_distingue_timeout_de_conexao_recusada():
    """O sintoma que importa: pacote descartado (firewall) x porta fechada."""
    timeout = rede.resumo_erro(_erro_do_requests(
        urllib3.exceptions.ConnectTimeoutError(None, "timed out")))
    recusada = rede.resumo_erro(_erro_do_requests(
        urllib3.exceptions.NewConnectionError(None, "[Errno 111] Connection refused")))
    assert "ConnectTimeoutError" in timeout
    assert "NewConnectionError" in recusada and "refused" in recusada
    assert timeout != recusada


def test_nao_devolve_so_o_embrulho_generico():
    """'Max retries exceeded' é ruído: aparece igual em todas as causas."""
    resumo = rede.resumo_erro(_erro_do_requests(
        urllib3.exceptions.ConnectTimeoutError(None, "timed out")))
    assert "Max retries exceeded" not in resumo


def test_respeita_o_limite_de_tamanho():
    resumo = rede.resumo_erro(_erro_do_requests(RuntimeError("x" * 500)), limite=80)
    assert len(resumo) <= 80


def test_erro_simples_sem_cadeia():
    assert "recusado" in rede.resumo_erro(OSError("acesso recusado"))


def test_cadeia_circular_nao_trava():
    """Exceções com __context__ mútuo existem; o laço não pode ser infinito."""
    a, b = RuntimeError("a"), RuntimeError("b")
    a.__context__ = b
    b.__context__ = a
    assert rede.resumo_erro(a)      # só precisa terminar


# --------------------------------------------------------------------------
# diagnostico: nunca pode explodir, e tem que dizer algo útil
# --------------------------------------------------------------------------
def test_diagnostico_relata_o_que_o_python_enxerga():
    linhas = "\n".join(rede.diagnostico("example.com"))
    assert "Variáveis de proxy do ambiente" in linhas
    assert "getproxies" in linhas
    assert "Como o Windows está configurado" in linhas


def test_dns_que_falha_vira_conclusao_e_nao_excecao(monkeypatch):
    def _sem_dns(*a, **k):
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", _sem_dns)
    linhas = rede.diagnostico("host.inexistente.invalido")
    texto = "\n".join(linhas)
    assert "FALHOU" in texto
    assert "bloqueio de DNS" in texto


def test_timeout_de_tcp_explica_firewall(monkeypatch):
    """Porta que não abre com o nome resolvendo = pacote descartado."""
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("10.0.0.1", 443))])

    def _timeout(*a, **k):
        raise socket.timeout("timed out")

    monkeypatch.setattr(socket, "create_connection", _timeout)
    texto = "\n".join(rede.diagnostico("aconex.exemplo"))
    assert "TIMEOUT" in texto
    assert "DESCARTADOS" in texto and "firewall" in texto


def test_diagnostico_nunca_levanta(monkeypatch):
    """Ele roda JUSTAMENTE quando tudo já deu errado - não pode ser a gota."""
    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert rede.diagnostico("x")      # devolve linhas em vez de explodir


@pytest.mark.skipif(__import__("os").name == "nt", reason="caminho do Windows")
def test_fora_do_windows_avisa_em_vez_de_quebrar():
    assert "só no Windows" in "\n".join(rede._proxies_do_windows())


# --------------------------------------------------------------------------
# Proxy do PAC resolvido pelo Windows
#
# A API é do Windows, então aqui se testa tudo o que NÃO depende dela: o
# parsing da resposta, a ordem da cascata e o comportamento fora do Windows.
# Que a via realmente conecta o Aconex com a VPN ligada só a máquina do
# usuário prova - este módulo garante que ela é tentada, e primeiro.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bruto,esperado", [
    ("PROXY 127.0.0.1:10017; DIRECT", ["127.0.0.1:10017"]),   # PAC de VPN
    ("PROXY zscaler:80", ["zscaler:80"]),
    ("p1:8080;p2:8080", ["p1:8080", "p2:8080"]),              # já sem o verbo
    ("SOCKS s:1080", ["s:1080"]),
    ("a:80, a:80", ["a:80"]),                                 # sem repetir
    ("DIRECT", []),
    ("", []),
    (None, []),
])
def test_normaliza_a_resposta_do_pac(bruto, esperado):
    assert rede.normalizar_proxies(bruto) == esperado


def test_a_palavra_PROXY_nao_vira_endereco():
    """Sem tirar o verbo, o app tentaria conectar num host chamado 'PROXY'."""
    assert "PROXY" not in rede.normalizar_proxies("PROXY host:8080")
    assert "DIRECT" not in rede.normalizar_proxies("PROXY host:8080; DIRECT")


def test_fora_do_windows_nao_ha_via_de_pac():
    assert rede.proxies_do_windows_para("https://x.com") == []


def test_via_do_pac_vem_antes_da_direta(monkeypatch):
    """A ordem é o que faz a diferença: a direta é justamente a que a VPN
    descarta, então a via do PAC tem que ser tentada antes."""
    monkeypatch.setattr(rede, "proxies_do_windows_para",
                        lambda url, log_cb=None: ["127.0.0.1:10017"])
    nomes = [n for n, _, _ in rede.estrategias(url="https://aconex.exemplo")]
    assert nomes[0].startswith("proxy do Windows")
    assert nomes[-1] == "conexão direta"


def test_via_do_pac_monta_a_url_do_proxy(monkeypatch):
    monkeypatch.setattr(rede, "proxies_do_windows_para",
                        lambda url, log_cb=None: ["127.0.0.1:10017"])
    _, proxies, trust_env = rede.estrategias(url="https://x")[0]
    assert proxies == {"http": "http://127.0.0.1:10017",
                       "https": "http://127.0.0.1:10017"}
    assert trust_env is False


def test_proxy_informado_pelo_usuario_ganha_de_tudo(monkeypatch):
    monkeypatch.setattr(rede, "proxies_do_windows_para",
                        lambda url, log_cb=None: ["do-pac:80"])
    rotas = rede.estrategias("http://meu:3128", url="https://x")
    assert [n for n, _, _ in rotas] == ["proxy informado"]


def test_cascata_do_aconex_tambem_usa_o_pac(monkeypatch):
    from docmanager import aconex_backend as ab

    monkeypatch.setattr(ab.rede, "proxies_do_windows_para",
                        lambda url, log_cb=None: ["127.0.0.1:10017", "127.0.0.1:10017"])
    cfg = ab.AconexConfig(client_id="x", client_secret="y", user_id="1")
    nomes = [n for n, _, _ in ab._estrategias_conexao(cfg)]
    assert nomes[0].startswith("proxy do Windows")
    assert sum(n.startswith("proxy do Windows") for n in nomes) == 1   # sem repetir
    assert nomes[-1] == "conexão direta"


def test_cache_do_proxy_pode_ser_esquecido():
    """Ligar/desligar a VPN muda a resposta do PAC - o cache não pode
    sobreviver a isso."""
    rede._cache_proxy["https://x"] = (["velho:80"], 9e9)
    rede.esquecer_proxy_descoberto()
    assert rede._cache_proxy == {}
