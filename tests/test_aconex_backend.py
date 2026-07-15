"""Extração Aconex: comentários por revisão (markups) + tipo de tramitação.

Testa a montagem do DataFrame SEM rede (função pura `montar_dataframe`) e o
parse de XML sintético — nada aqui toca a API nem depende de segredo (KB §24.5).
"""
from docmanager.aconex_backend import (
    CAMPOS_STRING,
    MAPA_COLUNAS,
    ORDEM_COLUNAS,
    _parse_pagina,
    classificar_fonte,
    montar_dataframe,
)


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
# Campos pedidos à API: os markups precisam estar no return_fields
# --------------------------------------------------------------------------
def test_campos_pedem_markups():
    assert "numberOfMarkups" in CAMPOS_STRING
    assert "markupLastModifiedDate" in CAMPOS_STRING


def test_mapa_renomeia_markups_para_comentarios():
    assert MAPA_COLUNAS["NumberOfMarkups"] == "Qtd. de Comentários"
    assert MAPA_COLUNAS["MarkupLastModifiedDate"] == "Data do Último Comentário"
    for nome in ("Qtd. de Comentários", "Data do Último Comentário", "Tipo de Tramitação"):
        assert nome in ORDEM_COLUNAS


# --------------------------------------------------------------------------
# Parse de XML sintético (tags CamelCase como o Aconex devolve)
# --------------------------------------------------------------------------
def _xml(*docs: str) -> bytes:
    corpo = "".join(docs)
    return (f"<RegisterSearch><Documents>{corpo}</Documents></RegisterSearch>").encode()


def _doc(**tags: str) -> str:
    dentro = "".join(f"<{k}>{v}</{k}>" for k, v in tags.items())
    return f"<Document>{dentro}</Document>"


def test_parse_pagina_le_markups_e_fonte():
    xml = _xml(_doc(
        DocumentNumber="DOC-1", Revision="0A", ReviewSource="WF-77",
        NumberOfMarkups="7", MarkupLastModifiedDate="2024-03-15T10:00:00",
    ))
    docs = _parse_pagina(xml)
    assert docs == [{
        "DocumentNumber": "DOC-1", "Revision": "0A", "ReviewSource": "WF-77",
        "NumberOfMarkups": "7", "MarkupLastModifiedDate": "2024-03-15T10:00:00",
    }]


# --------------------------------------------------------------------------
# Montagem do DataFrame canônico (fim a fim, sem rede)
# --------------------------------------------------------------------------
def test_montar_dataframe_renomeia_deriva_e_formata():
    registros = [
        {"DocumentNumber": "DOC-1", "Revision": "0A", "ReviewSource": "WF-77",
         "NumberOfMarkups": "7", "MarkupLastModifiedDate": "2024-03-15T10:00:00"},
        {"DocumentNumber": "DOC-2", "Revision": "0B", "ReviewSource": "1234567",
         "NumberOfMarkups": "0", "MarkupLastModifiedDate": ""},
    ]
    df = montar_dataframe(registros)

    # rename (§5)
    assert list(df["No. do Documento"]) == ["DOC-1", "DOC-2"]
    assert list(df["Qtd. de Comentários"]) == ["7", "0"]
    # data formatada dd/mm/yyyy (e vazio permanece vazio)
    assert list(df["Data do Último Comentário"]) == ["15/03/2024", ""]
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
