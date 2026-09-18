"""Cofre de credenciais do Aconex - o que substituiu o `.env`.

O ponto sensível é a MIGRAÇÃO: quem atualiza da v3.0.0 tem as credenciais num
`.env` e não pode abrir o app novo e encontrar a lista de usuários vazia.
"""
import pytest

from docmanager import aconex_backend as ab
from docmanager.services import credenciais as cred
from docmanager.services.credenciais import Cofre, sufixo_env


@pytest.fixture
def cofre(tmp_path):
    return Cofre(tmp_path / "credenciais.json")


def _env_limpo(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith(("SECRET_", "CLIENTID_", "USERID_")):
            monkeypatch.delenv(k, raising=False)


# --------------------------------------------------------------------------
# Cadastro
# --------------------------------------------------------------------------
def test_salvar_e_ler_de_volta(cofre):
    assert cofre.vazio()
    cofre.salvar("Luan Cozer", "SCP_LUAN_APPID", "1208560183", "s3cr3t")
    assert cofre.listar() == ["Luan Cozer"]
    c = cofre.obter("Luan Cozer")
    assert (c.client_id, c.user_id, c.secret) == ("SCP_LUAN_APPID", "1208560183", "s3cr3t")
    assert c.completa()


def test_o_segredo_nao_fica_em_texto_puro_no_arquivo(cofre):
    cofre.salvar("Fulano", "SCP_X", "1", "MinhaSenhaSecreta")
    assert "MinhaSenhaSecreta" not in cofre.caminho.read_text(encoding="utf-8")


def test_sobrevive_ao_fechar_e_abrir_o_app(cofre):
    cofre.salvar("Fulano", "SCP_X", "1", "abc")
    assert Cofre(cofre.caminho).obter("Fulano").secret == "abc"


def test_campos_obrigatorios(cofre):
    """O Aconex exige os TRÊS dados - recusar cedo evita um erro de OAuth
    incompreensível 30 segundos depois."""
    for args in [("", "SCP", "1", "s"), ("N", "", "1", "s"), ("N", "SCP", "1", ""),
                 ("N", "SCP", "", "s")]:
        with pytest.raises(ValueError):
            cofre.salvar(*args)


def test_user_id_precisa_ser_numerico(cofre):
    """Confundir User ID com login é o engano mais comum do cadastro."""
    with pytest.raises(ValueError, match="numérico"):
        cofre.salvar("Fulano", "SCP_X", "luan.cozer", "s")


def test_remover(cofre):
    cofre.salvar("Fulano", "SCP_X", "1", "s")
    assert cofre.remover("Fulano") is True
    assert cofre.vazio()
    assert cofre.remover("Fulano") is False


def test_arquivo_corrompido_nao_impede_de_abrir(tmp_path):
    caminho = tmp_path / "credenciais.json"
    caminho.write_text("{isto não é json", encoding="utf-8")
    c = Cofre(caminho)
    assert c.vazio()
    c.salvar("Fulano", "SCP_X", "1", "s")     # e volta a funcionar
    assert c.listar() == ["Fulano"]


# --------------------------------------------------------------------------
# Migração do .env (quem vem da v3.0.0)
# --------------------------------------------------------------------------
def test_importa_usuario_conhecido_pela_chave_do_env(cofre):
    """O .env em uso hoje traz `SECRET_LUAN`, mas o usuário se chama
    'Luan Cozer' - o casamento usa a chave declarada em USUARIOS."""
    importados = cofre.importar_do_env(ab.USUARIOS, {"SECRET_LUAN": "abc"})
    assert importados == ["Luan Cozer"]
    c = cofre.obter("Luan Cozer")
    assert c.secret == "abc"
    assert c.client_id == ab.USUARIOS["Luan Cozer"]["client_id"]


def test_importa_usuario_novo_com_os_tres_dados(cofre):
    importados = cofre.importar_do_env(ab.USUARIOS, {
        "SECRET_FULANO": "s", "CLIENTID_FULANO": "SCP_F", "USERID_FULANO": "1200000000"})
    assert importados == ["Fulano"]
    assert cofre.obter("Fulano").user_id == "1200000000"


def test_secret_sozinho_nao_importa(cofre):
    """Sem Client ID / User ID o secret não autentica - importar criaria um
    usuário na lista que falharia na hora da extração."""
    assert cofre.importar_do_env(ab.USUARIOS, {"SECRET_DESCONHECIDO": "s"}) == []
    assert cofre.vazio()


def test_cadastro_no_app_vence_o_env_antigo(cofre):
    cofre.salvar("Luan Cozer", "SCP_NOVO", "999", "secret_novo")
    assert cofre.importar_do_env(ab.USUARIOS, {"SECRET_LUAN": "secret_velho"}) == []
    assert cofre.obter("Luan Cozer").secret == "secret_novo"


def test_migracao_e_idempotente(cofre):
    env = {"SECRET_LUAN": "abc"}
    assert cofre.importar_do_env(ab.USUARIOS, env) == ["Luan Cozer"]
    assert cofre.importar_do_env(ab.USUARIOS, env) == []   # rodar de novo não duplica


def test_sufixo_env():
    assert sufixo_env("Luan Cozer") == "LUAN_COZER"
    assert sufixo_env("josé da silva-júnior") == "JOS_DA_SILVA_J_NIOR"


# --------------------------------------------------------------------------
# Integração com a lista da tela de Extração
# --------------------------------------------------------------------------
def test_usuario_cadastrado_aparece_na_extracao(monkeypatch):
    _env_limpo(monkeypatch)
    assert ab.usuarios_disponiveis() == []
    cred.cofre().salvar("Ciclano", "SCP_C", "42", "s")
    assert ab.usuarios_disponiveis() == ["Ciclano"]
    cfg = ab.AconexConfig.para_usuario("Ciclano")
    assert (cfg.client_id, cfg.user_id, cfg.client_secret) == ("SCP_C", "42", "s")


def test_cofre_e_env_convivem(monkeypatch):
    _env_limpo(monkeypatch)
    monkeypatch.setenv("SECRET_LUAN", "do_env")
    cred.cofre().salvar("Ciclano", "SCP_C", "42", "s")
    assert set(ab.usuarios_disponiveis()) == {"Luan Cozer", "Ciclano"}
    assert ab.AconexConfig.para_usuario("Luan Cozer").client_secret == "do_env"


def test_erro_de_secret_vazio_diz_o_que_fazer(monkeypatch):
    _env_limpo(monkeypatch)
    with pytest.raises(ValueError, match="Cadastre o Client Secret|SECRET_LUAN"):
        ab.AconexConfig.para_usuario("Luan Cozer")
