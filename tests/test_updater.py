"""Atualização automática: comparação de versões, leitura do release e política.

Nada aqui toca a rede. O que é testado é justamente a parte que decide se o
usuário vai ou não ser avisado - e que, errada, produz os dois piores defeitos
possíveis: nunca avisar, ou reoferecer a mesma versão para sempre.
"""
import json

import pytest

from docmanager._ofuscacao import desofuscar, ofuscar
from docmanager.services import updater
from docmanager.services.config import ConfigManager


# --------------------------------------------------------------------------
# Comparação de versões
# --------------------------------------------------------------------------
@pytest.mark.parametrize("remota,atual,esperado", [
    ("3.1.0", "3.0.0", True),
    ("3.0.1", "3.0.0", True),
    ("3.10.0", "3.9.0", True),      # 10 > 9: comparação numérica, não de texto
    ("v3.1.0", "3.0.0", True),      # o 'v' da tag não atrapalha
    ("3.0.0", "3.0.0", False),      # em dia
    ("3.0.0", "3.1.0", False),      # nunca "atualizar" para trás
    ("3.1.0-beta.1", "3.1.0", False),   # pré-versão vem ANTES da final
    ("3.1.0", "3.1.0-beta.1", True),    # da pré-versão para a final, sim
    ("3.1", "3.0.9", True),         # tag encurtada ainda compara certo
])
def test_comparacao_de_versoes(remota, atual, esperado):
    assert updater.e_mais_nova(remota, atual) is esperado


def test_versao_estranha_nao_derruba_o_app():
    """Uma tag digitada errada no GitHub não pode virar exceção na abertura."""
    assert updater.e_mais_nova("versao-de-teste", "3.0.0") is False
    assert updater.e_mais_nova("", "3.0.0") is False
    assert updater.e_mais_nova(None, "3.0.0") is False


# --------------------------------------------------------------------------
# Leitura do release
# --------------------------------------------------------------------------
def _release(assets, tag="v3.2.0", body="- novidade"):
    return {"tag_name": tag, "body": body, "assets": assets,
            "html_url": "https://github.com/x/y/releases/tag/" + tag,
            "published_at": "2026-09-18T10:00:00Z"}


def test_interpretar_release_escolhe_o_instalador():
    r = _release([
        {"name": "latest.json", "url": "https://api/assets/1", "size": 300},
        {"name": "DocManager_Itaipu_Setup_3.2.0.exe", "url": "https://api/assets/2",
         "size": 40_000_000, "digest": "sha256:ABC123"},
    ])
    info = updater.interpretar_release(r)
    assert info.versao == "3.2.0"
    assert info.nome_arquivo.endswith(".exe")
    # A URL guardada é a da API, não a browser_download_url: em repositório
    # privado só a de API entrega o binário (a outra devolve uma página HTML).
    assert info.url_asset == "https://api/assets/2"
    assert info.sha256 == "abc123"          # normalizado para minúsculas
    assert info.tamanho_mb == 38.1


def test_manifesto_vence_o_digest_da_api():
    r = _release([{"name": "s.exe", "url": "u", "size": 1, "digest": "sha256:doapi"}])
    info = updater.interpretar_release(r, {"sha256": "DOMANIFESTO", "notas": "- do manifesto"})
    assert info.sha256 == "domanifesto"
    assert info.notas == "- do manifesto"


def test_sem_manifesto_usa_o_body_do_release():
    r = _release([{"name": "s.exe", "url": "u", "size": 1}], body="- veio do body")
    info = updater.interpretar_release(r)
    assert info.notas == "- veio do body"
    assert info.sha256 == ""        # sem hash: baixar() avisa que não conferiu


def test_release_sem_instalador_devolve_none():
    """Publicar só o latest.json (build que falhou no meio) não pode virar um
    aviso de atualização que não instala nada."""
    assert updater.interpretar_release(_release([{"name": "latest.json", "url": "u"}])) is None


# --------------------------------------------------------------------------
# Token embutido
# --------------------------------------------------------------------------
def test_ofuscacao_ida_e_volta():
    token = "github_pat_11ABCDEF_umTokenQualquerComSímbolos-_=."
    assert desofuscar(ofuscar(token)) == token
    assert token not in ofuscar(token)   # não aparece num `strings` do .exe


def test_token_da_variavel_de_ambiente_vence(monkeypatch):
    monkeypatch.setenv("DOCMANAGER_UPDATE_TOKEN", "tok_do_ambiente")
    assert updater.token() == "tok_do_ambiente"


def test_token_do_arquivo_em_documentos(monkeypatch, tmp_path):
    """Trocar o token sem refazer o build (rotação de emergência)."""
    monkeypatch.delenv("DOCMANAGER_UPDATE_TOKEN", raising=False)
    arquivo = updater.caminho_token_externo()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("  tok_do_arquivo\n", encoding="utf-8")
    assert updater.token() == "tok_do_arquivo"


def test_sem_token_a_checagem_explica_em_vez_de_quebrar(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "")
    with pytest.raises(updater.SemToken):
        updater.checar("3.0.0")


# --------------------------------------------------------------------------
# Política: quando avisar
# --------------------------------------------------------------------------
def test_nao_verifica_sem_token(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "")
    assert updater.deve_verificar(ConfigManager()) is False


def test_verifica_na_primeira_vez_e_respeita_o_intervalo(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "tok")
    cfg = ConfigManager()
    assert updater.deve_verificar(cfg) is True      # nunca verificou
    updater.registrar_verificacao(cfg)
    assert updater.deve_verificar(cfg) is False     # acabou de verificar
    assert updater.deve_verificar(cfg, intervalo_horas=0) is True


def test_desligar_o_aviso_automatico_para_a_verificacao(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "tok")
    cfg = ConfigManager()
    cfg.set_setting("verificar_atualizacoes", False)
    assert updater.deve_verificar(cfg) is False


def test_data_invalida_na_config_nao_trava_a_verificacao(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "tok")
    cfg = ConfigManager()
    cfg.set_setting("ultima_verificacao", "ontem de manhã")
    assert updater.deve_verificar(cfg) is True


def test_pular_versao_silencia_so_aquela_versao():
    cfg = ConfigManager()
    updater.ignorar_versao(cfg, "3.2.0")
    assert updater.esta_ignorada(cfg, "3.2.0") is True
    assert updater.esta_ignorada(cfg, "3.3.0") is False   # a próxima volta a avisar


def test_manifesto_com_bom_ainda_e_lido():
    """O PowerShell pode gravar o latest.json com BOM; `utf-8-sig` cobre os dois."""
    bruto = b"\xef\xbb\xbf" + json.dumps({"sha256": "abc"}).encode("utf-8")
    assert json.loads(bruto.decode("utf-8-sig"))["sha256"] == "abc"


def test_release_publicado_de_verdade_e_entendido():
    """O JSON (resumido) que a API devolveu para o Release v3.1.0 publicado pelo
    workflow: é o formato que os apps instalados vão ler na próxima versão."""
    release = {
        "tag_name": "v3.1.0", "prerelease": False, "draft": False,
        "html_url": "https://github.com/luanccozer/DocManager/releases/tag/v3.1.0",
        "published_at": "2026-09-18T17:35:25Z", "body": "## O que mudou na v3.1.0 ...",
        "assets": [
            {"name": "DocManager_Itaipu_Setup_3.1.0.exe", "size": 54226345,
             "url": "https://api.github.com/repos/luanccozer/DocManager/releases/assets/573114368",
             "digest": "sha256:b675b74dc1dace0d54762173eaf0c1d250d31d3824d7a63c89e983c4e9eb3491"},
            {"name": "latest.json", "size": 1670,
             "url": "https://api.github.com/repos/luanccozer/DocManager/releases/assets/573114371"},
        ],
    }
    info = updater.interpretar_release(release)
    assert info.versao == "3.1.0"
    assert info.nome_arquivo == "DocManager_Itaipu_Setup_3.1.0.exe"
    assert info.url_asset.endswith("/releases/assets/573114368")   # a URL de API
    assert info.sha256 == "b675b74dc1dace0d54762173eaf0c1d250d31d3824d7a63c89e983c4e9eb3491"
    assert info.tamanho_mb == 51.7
    assert updater.e_mais_nova("3.1.1", "3.1.0")


# --------------------------------------------------------------------------
# Instalação: o app só fecha quando o instalador está PRONTO (2026-09-30)
# --------------------------------------------------------------------------
# Até a v3.1.0 o app disparava o instalador e fechava 400 ms depois. Em modo
# silencioso o Inno aborta se o app ainda estiver aberto na checagem do
# AppMutex - a atualização falhava em meio segundo (reproduzido no Wine).
# Agora o instalador cria o arquivo de /SINAL quando está pronto (e esperando
# o app sair), e `instalar` só volta nesse momento.
def _instalador_falso(tmp_path, corpo: str):
    """Script executável no lugar do Setup.exe; recebe os mesmos argumentos."""
    import stat
    import sys

    script = tmp_path / "Setup_falso.py"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys, time, pathlib\n"
        "args = sys.argv[1:]\n"
        "sinal = next((a.split('=', 1)[1] for a in args if a.startswith('/SINAL=')), '')\n"
        f"pathlib.Path({str(tmp_path / 'args.txt')!r}).write_text('\\n'.join(args))\n"
        + corpo, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture
def pasta_update(tmp_path, monkeypatch):
    pasta = tmp_path / "update"
    pasta.mkdir()
    monkeypatch.setattr(updater, "pasta_download", lambda: pasta)
    # O instalador falso continua rodando depois que `instalar` volta (como o de
    # verdade): encerra no fim do teste, senão sobra processo órfão da suíte.
    abertos = []
    popen = updater.subprocess.Popen

    def popen_registrando(*args, **kwargs):
        processo = popen(*args, **kwargs)
        abertos.append(processo)
        return processo

    monkeypatch.setattr(updater.subprocess, "Popen", popen_registrando)
    yield pasta
    for processo in abertos:
        processo.kill()
        processo.wait()


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_instalar_espera_o_instalador_ficar_pronto(tmp_path, pasta_update):
    inst = _instalador_falso(tmp_path, (
        "time.sleep(0.5)\n"
        "pathlib.Path(sinal).write_text('pronto')\n"
        "time.sleep(2)\n"))
    inicio = __import__("time").monotonic()
    updater.instalar(inst)
    assert __import__("time").monotonic() - inicio >= 0.5    # esperou o sinal
    args = (tmp_path / "args.txt").read_text().splitlines()
    for esperado in ("/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS",
                     "/RESTARTAPPLICATIONS", "/REABRIR"):
        assert esperado in args
    assert f"/SINAL={pasta_update / 'instalador_pronto.txt'}" in args
    assert f"/LOG={pasta_update / 'instalacao.log'}" in args


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_instalador_que_termina_sem_ficar_pronto_nao_fecha_o_app(tmp_path, pasta_update):
    """UAC recusado, antivírus...: o instalador sai sem criar o sinal. O app
    tem de continuar aberto e avisar - fechar seria perder a pessoa de vista."""
    inst = _instalador_falso(tmp_path, "sys.exit(2)\n")
    with pytest.raises(updater.InstaladorNaoIniciou, match="código 2"):
        updater.instalar(inst)


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_sinal_velho_nao_e_confundido_com_pronto(tmp_path, pasta_update):
    """Um sinal que sobrou de uma tentativa anterior não pode fechar o app."""
    (pasta_update / "instalador_pronto.txt").write_text("pronto")
    inst = _instalador_falso(tmp_path, "sys.exit(1)\n")
    with pytest.raises(updater.InstaladorNaoIniciou):
        updater.instalar(inst)


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_instalador_que_nao_responde_desiste_sem_fechar_o_app(tmp_path, pasta_update):
    inst = _instalador_falso(tmp_path, "time.sleep(5)\n")
    with pytest.raises(updater.InstaladorNaoIniciou, match="não respondeu"):
        updater.instalar(inst, espera_s=0.5)


def test_instalador_que_nao_abre_vira_aviso(tmp_path, pasta_update):
    with pytest.raises(updater.InstaladorNaoIniciou, match="não deixou abrir"):
        updater.instalar(tmp_path / "nao_existe.exe")
