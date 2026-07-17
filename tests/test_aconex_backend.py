"""Extração Aconex: tipo de tramitação (Fonte) + montagem do DataFrame.

Testa a montagem do DataFrame SEM rede (função pura `montar_dataframe`) e o
parse de XML sintético — nada aqui toca a API nem depende de segredo (KB §24.5).
(As colunas de anotações/markups foram removidas — §24.9: numberOfMarkups conta
elementos, não as Anotações do site, e não há endpoint confiável.)
"""
import os

from docmanager.aconex_backend import (
    AconexConfig,
    _parse_pagina,
    classificar_fonte,
    montar_dataframe,
    usuarios_disponiveis,
)


def _env_limpo(monkeypatch):
    """Remove todo SECRET_/CLIENTID_/USERID_ do ambiente (o .env real vaza no import)."""
    for k in list(os.environ):
        if k.startswith(("SECRET_", "CLIENTID_", "USERID_")):
            monkeypatch.delenv(k, raising=False)


# --------------------------------------------------------------------------
# Usuários da extração descobertos pelo .env (item 2)
# --------------------------------------------------------------------------
def test_sem_secret_nenhum_lista_vazia(monkeypatch):
    _env_limpo(monkeypatch)
    assert usuarios_disponiveis() == []


def test_lista_apenas_conhecidos_com_secret(monkeypatch):
    _env_limpo(monkeypatch)
    monkeypatch.setenv("SECRET_LUAN", "x")
    assert usuarios_disponiveis() == ["Luan Cozer"]      # Rafhael some (sem secret)
    monkeypatch.setenv("SECRET_RAFHAEL", "y")
    assert set(usuarios_disponiveis()) == {"Luan Cozer", "Rafhael Martins"}


def test_usuario_novo_do_env_aparece_sozinho(monkeypatch):
    """A lista cresce conforme os secrets: um SECRET_<NOME> novo entra sozinho,
    desde que traga CLIENTID_/USERID_ (o Aconex exige os três)."""
    _env_limpo(monkeypatch)
    monkeypatch.setenv("SECRET_JOAO", "s3cr3t")
    assert "Joao" not in usuarios_disponiveis()          # só o secret não basta
    monkeypatch.setenv("CLIENTID_JOAO", "SCP_JOAO_APPID")
    monkeypatch.setenv("USERID_JOAO", "999")
    assert "Joao" in usuarios_disponiveis()
    cfg = AconexConfig.para_usuario("Joao")
    assert cfg.client_id == "SCP_JOAO_APPID"
    assert cfg.user_id == "999"
    assert cfg.client_secret == "s3cr3t"


def test_usuario_conhecido_sem_secret_erra_por_secret_vazio(monkeypatch):
    _env_limpo(monkeypatch)
    try:
        AconexConfig.para_usuario("Luan Cozer")
    except ValueError as e:
        assert "SECRET_LUAN" in str(e)                   # erro acionável
    else:
        raise AssertionError("deveria acusar secret vazio")


# --------------------------------------------------------------------------
# Fluxos: classificação da Fonte (ReviewSource) no mecanismo de tramitação
# --------------------------------------------------------------------------
def test_classificar_fonte_workflow():
    assert classificar_fonte("WF-001234") == "Fluxo"
    assert classificar_fonte("wf-999") == "Fluxo"


def test_classificar_fonte_transmittal_numerico():
    assert classificar_fonte("1234567") == "Transmissão"
    assert classificar_fonte("1208-560") == "Transmissão"


def test_classificar_fonte_supplier_docs():
    assert classificar_fonte("SD-42") == "Docs. Fornecedor"


def test_classificar_fonte_fora_de_ciclo():
    # 'Nenhum' e vazio → sem tramitação (linha fora de qualquer ciclo, KB §24.1)
    assert classificar_fonte("Nenhum") == ""
    assert classificar_fonte("") == ""
    assert classificar_fonte(None) == ""


# --------------------------------------------------------------------------
# Parse de XML sintético (tags CamelCase como o Aconex devolve)
# --------------------------------------------------------------------------
def _xml(*docs: str) -> bytes:
    corpo = "".join(docs)
    return (f"<RegisterSearch><Documents>{corpo}</Documents></RegisterSearch>").encode()


def _doc(**tags: str) -> str:
    dentro = "".join(f"<{k}>{v}</{k}>" for k, v in tags.items())
    return f"<Document>{dentro}</Document>"


def test_parse_pagina_le_campos_e_fonte():
    xml = _xml(_doc(DocumentNumber="DOC-1", Revision="0A", ReviewSource="WF-77"))
    docs = _parse_pagina(xml)
    assert docs == [{"DocumentNumber": "DOC-1", "Revision": "0A", "ReviewSource": "WF-77"}]


# --------------------------------------------------------------------------
# Montagem do DataFrame canônico (fim a fim, sem rede)
# --------------------------------------------------------------------------
def test_montar_dataframe_renomeia_deriva_e_formata():
    registros = [
        {"DocumentNumber": "DOC-1", "Revision": "0A", "ReviewSource": "WF-77",
         "DateModified": "2024-03-15T10:00:00"},
        {"DocumentNumber": "DOC-2", "Revision": "0B", "ReviewSource": "1234567",
         "DateModified": ""},
    ]
    df = montar_dataframe(registros)

    # rename (§5)
    assert list(df["No. do Documento"]) == ["DOC-1", "DOC-2"]
    # data formatada dd/mm/yyyy (e vazio permanece vazio)
    assert list(df["Data de Alteração"]) == ["15/03/2024", ""]
    # coluna derivada de tramitação
    assert list(df["Tipo de Tramitação"]) == ["Fluxo", "Transmissão"]
    # Fonte crua preservada
    assert list(df["Fonte"]) == ["WF-77", "1234567"]


def test_montar_dataframe_ordem_tramitacao_ao_lado_da_fonte():
    df = montar_dataframe([{"DocumentNumber": "X", "ReviewSource": "WF-1"}])
    cols = list(df.columns)
    assert cols.index("Tipo de Tramitação") == cols.index("Fonte") + 1


def test_montar_dataframe_preserva_colunas_desconhecidas_no_fim():
    # Um campo novo do Aconex que não está no ORDEM_COLUNAS não pode sumir.
    df = montar_dataframe([{"DocumentNumber": "X", "CampoNovoInesperado": "v"}])
    assert "CampoNovoInesperado" in df.columns
    assert list(df.columns)[-1] == "CampoNovoInesperado"


def test_montar_dataframe_vazio():
    assert montar_dataframe([]).empty


def test_montar_dataframe_sem_fonte_nao_cria_tramitacao():
    # Sem a coluna Fonte, não há o que classificar (não deve quebrar).
    df = montar_dataframe([{"DocumentNumber": "X", "Revision": "0A"}])
    assert "Tipo de Tramitação" not in df.columns
