"""Atualização automática: comparação de versões, leitura do release e política.

Nada aqui toca a rede. O que é testado é justamente a parte que decide se o
usuário vai ou não ser avisado — e que, errada, produz os dois piores defeitos
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
