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


def test_controle_leitura_dinamica_formatos_mistos(tmp_path):
    """Cabeçalho localizado dinamicamente + datas em formatos MISTOS por coluna:
    DATA PREVISTA em DD-MM-AAAA e REPROGRAMAÇÃO em M/D/AAAA (US)."""
    from openpyxl import Workbook

    from docmanager.services.controle_docs import ler_controle

    p = tmp_path / "ctrl_real.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["ITAIPU - CONTROLE DE DOCUMENTOS", "", "", "", "Planejamento"])
    ws.append(["PLANO GERAL DE ENVIO DE DOCUMENTOS"])
    ws.append(["", "", "", ";", "."])
    ws.append(["ITEM", "NÚMERO INTERNO", "CODIFICAÇÃO ITAIPÚ (ACONEX)", "DESCRIÇÃO",
               "DATA PREVISTA DE EMISSÃO ACONEX", "REPROGRAMAÇÃO"])
    ws.append([1, "CMI-A", "#IT-A", "DOC A", "30-11-2025", ""])           # só prevista
    ws.append([2, "CMI-B", "#IT-B", "DOC B", "17-07-2025", "10/20/2025"])  # reprog US vence
    wb.save(p)

    ctrl = ler_controle(p)
    assert ctrl.linha_por_codigo("#IT-A").data_ref == date(2025, 11, 30)
    assert ctrl.linha_por_codigo("#IT-B").data_ref == date(2025, 10, 20)   # 20/out (M/D)
    # casa também pelo NÚMERO INTERNO (código CMI)
    assert ctrl.linha_por_codigo("CMI-B").data_ref == date(2025, 10, 20)


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


def test_colunas_prevista_reprogramacao_so_na_0a(tmp_path):
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC A")
             .evento("0A", 1, "Não Aprovado", "20/09/2024")
             .evento("0B", 1, "Em Processo", "01/10/2024", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/08/2024", "reprog": "20/08/2024"},
    ])
    wide = gerar_historico(b, ler_controle(p), DelayPolicy(hoje=date(2024, 12, 31)))
    out = tmp_path / "h.xlsx"
    exportar_historico(wide, out)
    lido = pd.read_excel(out, sheet_name="Histórico").fillna("")
    assert "Data Prevista" in lido.columns and "Reprogramação" in lido.columns
    por_rev = {r["Revisão"]: r for _, r in lido.iterrows()}
    assert str(por_rev["0A"]["Data Prevista"]) != "" and str(por_rev["0A"]["Reprogramação"]) != ""
    assert str(por_rev["0B"]["Data Prevista"]) == "" and str(por_rev["0B"]["Reprogramação"]) == ""


def test_base_atraso_cmi_0a_alterna_reprogramacao_vs_prevista(tmp_path):
    from docmanager.core.delays import COL_ATRASO_CMI
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC A")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/08/2024", "reprog": "20/08/2024"},
    ])
    ctrl = ler_controle(p)
    HJ = date(2024, 12, 31)
    reprog = gerar_historico(b, ctrl, DelayPolicy(hoje=HJ, base_cmi_0a="reprogramacao"))
    prev = gerar_historico(b, ctrl, DelayPolicy(hoje=HJ, base_cmi_0a="prevista"))
    a_reprog = int(reprog[reprog["Revisão"] == "0A"].iloc[0][COL_ATRASO_CMI])
    a_prev = int(prev[prev["Revisão"] == "0A"].iloc[0][COL_ATRASO_CMI])
    assert a_reprog == 12    # 20/08 → 01/09
    assert a_prev == 31      # 01/08 → 01/09


def test_ordem_revisao_por_familia_e_cadeia_cmi():
    """Ciclo de vida (KB §3.1): 0A→0B→0 (aprovação fecha a família) → 1A…
    A aprovação seca '0' vem ANTES da família seguinte '1A', e o atraso CMI de
    uma reemissão mede contra o RETORNO da revisão imediatamente anterior."""
    from docmanager.core.delays import COL_DIAS_CMI
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC FAMILIA")
        .evento("0A", 1, "Em Processo", "01/09/2024")
        .evento("0A", 2, "Não Aprovado", "10/09/2024")
        .evento("0B", 1, "Em Processo", "15/09/2024")
        .evento("0B", 2, "Aprovado com Comentários", "25/09/2024")
        .evento("0", 1, "Em Processo", "01/10/2024")
        .evento("0", 2, "Aprovado", "10/10/2024")
        .evento("1A", 1, "Em Processo", "20/10/2024")
        .evento("1A", 2, "Aprovado", "30/10/2024", current=True)
    )
    wide = gerar_historico(b, None, DelayPolicy(hoje=date(2024, 12, 31)))
    # A '0' (aprovação) fica ANTES de '1A' (bug antigo jogava para o fim).
    assert list(wide["Revisão"]) == ["0A", "0B", "0", "1A"], list(wide["Revisão"])
    por_rev = {r["Revisão"]: r for _, r in wide.iterrows()}
    # 1A mede contra o retorno da '0' (10/10 → 20/10 = 10 dias), não da '0B'.
    assert int(por_rev["1A"][COL_DIAS_CMI]) == 10


def test_ciclo_consistente_subida_errada_ignorada():
    """Caso 0C/0D real (KB §24.6): envio etiquetado com a revisão errada e
    corrigido em seguida NÃO pode virar o envio da revisão anterior."""
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0C", 1, "Em Processo", "05/06/2025")
        .evento("0C", 2, "Aprovado com Comentários", "19/06/2025")
        .evento("0C", 3, "Em Processo", "24/07/2025")          # subida errada
        .evento("0D", 4, "Em Processo", "24/07/2025")           # corrigida p/ 0D
        .evento("0D", 5, "Para Assinatura", "14/08/2025", current=True)
    )
    wide = gerar_historico(b, None, DelayPolicy(hoje=date(2025, 12, 31)))
    c = wide[wide["Revisão"] == "0C"].iloc[0]
    assert c["Data Envio"] == pd.Timestamp("2025-06-05")        # não o 24/07
    assert c["Data Retorno"] == pd.Timestamp("2025-06-19")
    assert int(c["Dias Itaipu"]) == 14                          # antes: em branco
    d = wide[wide["Revisão"] == "0D"].iloc[0]
    assert d["Data Envio"] == pd.Timestamp("2025-07-24")


def test_ciclo_consistente_relancamento_vira_pendente():
    """Relançamento (doc volta à mesma revisão como último evento): conta a
    segunda vida — envio novo, sem retorno, relógio em aberto correndo."""
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, "Não Aprovado", "20/03/2025")
        .evento("0A", 3, "Em Processo", "01/06/2025", current=True)  # relançada
    )
    wide = gerar_historico(b, None, DelayPolicy(hoje=date(2025, 12, 31)))
    a = wide.iloc[0]
    assert a["Data Envio"] == pd.Timestamp("2025-06-01")
    assert pd.isna(a["Data Retorno"])                           # vida anterior descartada
    assert int(a["Dias Itaipu"]) == 213                         # 01/06 → 31/12 em aberto
    assert int(a["Atraso Itaipu"]) == 183                       # 213 − SLA 30


def test_para_aprovacao_vira_envio_fallback():
    """Caso da revisão '0' no início do projeto (KB §24.7): o envio subia como
    'Para Aprovação'. Quando a revisão NÃO tem 'Em Processo', o último PA
    anterior ao retorno vira o envio (rev 0 real: 17/10→23/10 = 6 dias)."""
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0", 85, "Para Aprovação", "17/10/2023")
        .evento("0", 87, "Aprovado", "23/10/2023", current=True)
    )
    wide = gerar_historico(b, None, DelayPolicy(hoje=date(2023, 12, 31)))
    r = wide.iloc[0]
    assert r["Data Envio"] == pd.Timestamp("2023-10-17")     # antes: vazio
    assert r["Data Retorno"] == pd.Timestamp("2023-10-23")
    assert int(r["Dias Itaipu"]) == 6
    assert int(r["Atraso Itaipu"]) == 0                      # SLA 15


def test_para_aprovacao_nao_substitui_envio_real():
    """'Para Aprovação' é SÓ fallback: revisão com 'Em Processo' fica intacta
    (e o PA continua sem virar retorno)."""
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0B", 1, "Em Processo", "01/03/2025")
        .evento("0B", 2, "Não Aprovado", "20/03/2025")
        .evento("0B", 3, "Para Aprovação", "25/03/2025", current=True)
    )
    wide = gerar_historico(b, None, DelayPolicy(hoje=date(2025, 12, 31)))
    r = wide.iloc[0]
    assert r["Data Envio"] == pd.Timestamp("2025-03-01")     # envio real preservado
    assert r["Data Retorno"] == pd.Timestamp("2025-03-20")   # PA não é retorno
    assert int(r["Dias Itaipu"]) == 19


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
