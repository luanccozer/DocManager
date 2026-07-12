"""Controle de Documentos + injeção de sintéticas + histórico ponta a ponta."""
from datetime import date

import pandas as pd
from builders import HistoricoBuilder, base, escrever_controle_xlsx

from docmanager.core.delays import COL_ATRASO_CMI, COL_DATA_PREVISTA_CTRL, DelayPolicy
from docmanager.services.controle_docs import ler_controle
from docmanager.services.excel_io import exportar_historico, preparar_para_exportar
from docmanager.services.historico_consolidado import gerar_historico


# --------------------------------------------------------------------------
# Controle de Documentos
# --------------------------------------------------------------------------
def test_controle_reprogramacao_vence_prevista(tmp_path):
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/03/2024", "reprog": "15/04/2024"},
        {"itaipu": "IT-2", "cmi": "CMI-2", "prevista": "10/05/2024", "reprog": ""},
    ])
    ctrl = ler_controle(p)
    assert ctrl.linha_por_codigo("IT-1").data_ref == date(2024, 4, 15)   # reprogramada
    assert ctrl.linha_por_codigo("IT-2").data_ref == date(2024, 5, 10)   # prevista


def test_controle_normaliza_codigo_float(tmp_path):
    # Código numérico vira '12345.0' na leitura str; deve casar por '12345'.
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": 12345, "cmi": 999, "prevista": "01/03/2024"},
    ])
    ctrl = ler_controle(p)
    assert ctrl.linha_por_codigo("12345") is not None
    assert ctrl.data_ref_por_codigos(["999"]) == date(2024, 3, 1)


# --------------------------------------------------------------------------
# Histórico ponta a ponta com sintéticas
# --------------------------------------------------------------------------
def test_injecao_de_linha_sintetica_para_doc_nao_postado(tmp_path):
    # Base com 1 doc postado (envio real pós-corte); Controle com esse + um NÃO postado.
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC POSTADO")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/02/2024"},
        {"itaipu": "IT-99", "cmi": "CMI-99", "titulo": "DOC NAO POSTADO", "prevista": "01/06/2024"},
    ])
    ctrl = ler_controle(p)
    wide = gerar_historico(b, ctrl, DelayPolicy(hoje=date(2024, 12, 31)))

    # A linha sintética existe e está marcada NÃO EMITIDO
    sinteticas = wide[wide["Status Envio"] == "NÃO EMITIDO"]
    assert len(sinteticas) == 1
    s = sinteticas.iloc[0]
    assert s["No. do Documento"] == "IT-99"
    assert pd.Timestamp(s[COL_DATA_PREVISTA_CTRL]) == pd.Timestamp("2024-06-01")
    # Atraso CMI correndo até hoje: 01/06 → 31/12 = 213 dias
    assert s[COL_ATRASO_CMI] == 213


def test_doc_postado_nao_gera_sintetica(tmp_path):
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/02/2024"},
    ])
    wide = gerar_historico(b, ler_controle(p), DelayPolicy(hoje=date(2024, 12, 31)))
    assert (wide["Status Envio"] == "NÃO EMITIDO").sum() == 0


def test_exportacao_excel_layout(tmp_path):
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC 1")
             .evento("0A", 1, "Em Processo", "01/03/2024")
             .evento("0A", 2, "Aprovado", "20/03/2024", current=True))
    wide = gerar_historico(b, None, DelayPolicy(hoje=date(2024, 12, 31)))
    out = tmp_path / "hist.xlsx"
    ok, msg = exportar_historico(wide, out)
    assert ok, msg
    lido = pd.read_excel(out, sheet_name="Histórico")
    # Nomes legados COM "de" + colunas novas ao fim
    assert "Data de Envio" in lido.columns and "Data de Retorno" in lido.columns
    for c in ["Dias Itaipu", "Atraso Itaipu", "Dias CMI", "Atraso CMI"]:
        assert c in lido.columns
    # Data Prevista (Controle) é interna — NÃO deve aparecer no Excel
    assert "Data Prevista (Controle)" not in lido.columns


def test_preparar_para_exportar_renomeia_datas():
    import numpy as np
    df = pd.DataFrame({
        "Tracking ID": ["T"], "Revisão": ["0A"],
        "Data Envio": [pd.Timestamp("2024-03-01")],
        "Status Envio": ["Em Processo"],
        "Data Retorno": [pd.NaT], "Status Retorno": [np.nan],
        "SLA_Itaipu": [30],
    })
    out = preparar_para_exportar(df)
    assert "Data de Envio" in out.columns
    assert out.iloc[0]["Data de Envio"] == "01/03/2024"
