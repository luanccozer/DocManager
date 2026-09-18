"""Histórico Consolidado DIRIGIDO PELO CONTROLE (§24.11) + leitura do Controle.

O Controle (obrigatório) define os documentos; o extrato Aconex dá o histórico.
"""
from datetime import date

import pandas as pd
import pytest
from builders import HistoricoBuilder, base, escrever_controle_xlsx

from docmanager.core.delays import COL_ATRASO_CMI, COL_DATA_PREVISTA_CTRL, COL_DIAS_CMI, DelayPolicy
from docmanager.services.controle_docs import ControleDocs, ControleRow, ler_controle
from docmanager.services.excel_io import exportar_historico, preparar_para_exportar
from docmanager.services.historico_consolidado import gerar_historico


def _ctrl(*docs) -> ControleDocs:
    """ControleDocs a partir de dicts: itaipu, cmi, [titulo], [fase], [prevista],
    [reprog], [emitido], [especialidade], [subespecialidade], [tipo_documento],
    [subtipo]. Fase default só para não ficar vazia nos testes."""
    rows = [ControleRow(
        cod_itaipu=d.get("itaipu", ""), cod_cmi=d.get("cmi", ""),
        titulo=d.get("titulo", ""),
        data_prevista=d.get("prevista"), data_reprogramada=d.get("reprog"),
        fase=d.get("fase", "PROJETO FABRICAÇÃO"), emitido=d.get("emitido", ""),
        especialidade=d.get("especialidade", ""), subespecialidade=d.get("subespecialidade", ""),
        tipo_documento=d.get("tipo_documento", ""), subtipo=d.get("subtipo", ""),
    ) for d in docs]
    return ControleDocs(rows)


# ==========================================================================
# Leitura do Controle de Documentos
# ==========================================================================
def test_controle_reprogramacao_vence_prevista(tmp_path):
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/03/2024", "reprog": "15/04/2024"},
        {"itaipu": "IT-2", "cmi": "CMI-2", "prevista": "10/05/2024", "reprog": ""},
    ])
    ctrl = ler_controle(p)
    assert ctrl.linha_por_codigo("IT-1").data_ref == date(2024, 4, 15)
    assert ctrl.linha_por_codigo("IT-2").data_ref == date(2024, 5, 10)


def test_controle_le_fase_e_emitido(tmp_path):
    """Novo (§24.11): lê FASE DE PROJETO e EMITIDO / NÃO EMITIDO."""
    from openpyxl import Workbook
    p = tmp_path / "ctrl_fase.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["ITAIPU - CONTROLE"])
    ws.append([])
    ws.append([])
    ws.append(["ITEM", "FASE DE PROJETO", "NÚMERO INTERNO", "CODIFICAÇÃO ITAIPÚ (ACONEX)",
               "DESCRIÇÃO", "DATA PREVISTA DE EMISSÃO ACONEX", "REPROGRAMAÇÃO", "EMITIDO / NÃO EMITIDO"])
    ws.append([1, "PROJETO FABRICAÇÃO", "CMI-A", "#IT-A", "DOC A", "30-11-2025", "", "EMITIDO"])
    ws.append([2, "EXECUÇÃO", "CMI-B", "#IT-B", "DOC B", "17-07-2025", "", "NÃO EMITIDO"])
    wb.save(p)
    ctrl = ler_controle(p)
    a = ctrl.linha_por_codigo("#IT-A")
    b = ctrl.linha_por_codigo("#IT-B")
    assert a.fase == "PROJETO FABRICAÇÃO" and a.esta_emitido is True
    assert b.fase == "EXECUÇÃO" and b.esta_emitido is False


def test_controle_le_metadados_para_nao_emitido(tmp_path):
    """Lê EQUIPAMENTO / SISTEMA, REFERÊNCIA DA ESPECIFICAÇÃO TÉCNICA, TIPO DE
    DOCUMENTO e SUBTIPO (metadados que preenchem a linha NÃO EMITIDO)."""
    from openpyxl import Workbook
    p = tmp_path / "ctrl_meta.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["ITAIPU - CONTROLE"])
    ws.append([])
    ws.append([])
    ws.append(["ITEM", "NÚMERO INTERNO", "CODIFICAÇÃO ITAIPÚ (ACONEX)", "DESCRIÇÃO",
               "EQUIPAMENTO / SISTEMA", "REFERÊNCIA DA ESPECIFICAÇÃO TÉCNICA",
               "TIPO DE DOCUMENTO", "SUBTIPO", "DATA PREVISTA DE EMISSÃO ACONEX"])
    ws.append([1, "CMI-A", "#IT-A", "DOC A", "TURBINA", "ET-900", "DESENHO", "MONTAGEM", "30-11-2025"])
    wb.save(p)
    r = ler_controle(p).linha_por_codigo("#IT-A")
    assert r.especialidade == "TURBINA"
    assert r.subespecialidade == "ET-900"
    assert r.tipo_documento == "DESENHO"
    assert r.subtipo == "MONTAGEM"


def test_controle_normaliza_codigo_float(tmp_path):
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": 12345, "cmi": 999, "prevista": "01/03/2024"},
    ])
    ctrl = ler_controle(p)
    assert ctrl.linha_por_codigo("12345") is not None
    assert ctrl.data_ref_por_codigos(["999"]) == date(2024, 3, 1)


def test_controle_le_apenas_a_aba_selecionada(tmp_path):
    from openpyxl import Workbook

    from docmanager.core.constants import CTRL_COL_CMI, CTRL_COL_DATA_PREVISTA, CTRL_COL_ITAIPU
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "Principal"
    ws1.append(["ITAIPU - CONTROLE DE DOCUMENTOS"])
    ws1.append([])
    ws1.append([])
    ws1.append(["ITEM", CTRL_COL_CMI, CTRL_COL_ITAIPU, "DESCRIÇÃO", CTRL_COL_DATA_PREVISTA, "REPROGRAMAÇÃO"])
    ws1.append([1, "CMI-A", "IT-A", "DOC A", "01/03/2025", ""])
    ws2 = wb.create_sheet("Dados Planilhas Comissionamento")
    ws2.append(["PLANO GERAL"])
    ws2.append(["ITEM", CTRL_COL_CMI, CTRL_COL_ITAIPU, "DESCRIÇÃO", CTRL_COL_DATA_PREVISTA, "REPROGRAMAÇÃO"])
    ws2.append([1, "CMI-B", "IT-B", "PLANILHA B", "16/10/2025", ""])
    p = tmp_path / "controle_multiabas.xlsx"
    wb.save(p)
    ctrl1 = ler_controle(p, "Principal")
    assert ctrl1.linha_por_codigo("IT-A").data_ref == date(2025, 3, 1)
    assert ctrl1.linha_por_codigo("IT-B") is None
    ctrl2 = ler_controle(p, "Dados Planilhas Comissionamento")
    assert ctrl2.linha_por_codigo("IT-B").data_ref == date(2025, 10, 16)
    assert ctrl2.linha_por_codigo("IT-A") is None


def test_controle_celula_com_varios_codigos():
    ctrl = ControleDocs([ControleRow(
        cod_itaipu="IT-A\nIT-B", cod_cmi="", titulo="DOC MULTI",
        data_prevista=date(2025, 3, 1), data_reprogramada=None)])
    assert ctrl.linha_por_codigo("IT-A").data_ref == date(2025, 3, 1)
    assert ctrl.linha_por_codigo("IT-B").data_ref == date(2025, 3, 1)


def test_datas_por_codigos_nao_para_em_linha_sem_data():
    sem_data = ControleRow("IT-1", "", "LINHA VELHA", None, None)
    com_data = ControleRow("", "CMI-1", "LINHA ATUAL", date(2025, 10, 16), None)
    ctrl = ControleDocs([sem_data, com_data])
    prev, _ = ctrl.datas_por_codigos(["IT-1", "CMI-1"])
    assert prev == date(2025, 10, 16)


def test_controle_codigo_duplicado_prefere_linha_datada(tmp_path):
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-DUP", "cmi": "CMI-DUP", "prevista": ""},
        {"itaipu": "IT-DUP", "cmi": "CMI-DUP", "prevista": "16/10/2025"},
    ])
    ctrl = ler_controle(p)
    assert ctrl.linha_por_codigo("IT-DUP").data_ref == date(2025, 10, 16)


# ==========================================================================
# Histórico dirigido pelo Controle (§24.11) - estrutura nova
# ==========================================================================
def test_controle_obrigatorio():
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1").evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    with pytest.raises(ValueError):
        gerar_historico(b, None, DelayPolicy(hoje=date(2024, 12, 31)))


def test_so_documentos_do_controle_aparecem():
    # Aconex tem 2 docs; Controle só 1 → só 1 aparece (o Controle manda).
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC NO CONTROLE")
        .evento("0A", 1, "Em Processo", "01/09/2024", current=True),
        HistoricoBuilder("T2", "IT-2", "CMI-2", "DOC FORA DO CONTROLE")
        .evento("0A", 1, "Em Processo", "01/09/2024", current=True),
    )
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"}),
                           DelayPolicy(hoje=date(2024, 12, 31)))
    assert set(wide["No. do Documento"]) == {"IT-1"}


def _dois_docs():
    """Base + Controle com dois documentos (IT-1/CMI-1 e IT-2/CMI-2)."""
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "FICA")
        .evento("0A", 1, "Em Processo", "01/09/2024", current=True),
        HistoricoBuilder("T2", "IT-2", "CMI-2", "SAI")
        .evento("0A", 1, "Em Processo", "01/09/2024", current=True),
    )
    ctrl = _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"}, {"itaipu": "IT-2", "cmi": "CMI-2"})
    return b, ctrl


def test_remocao_manual_retira_doc_por_itaipu():
    """Lista manual de remoção (colada na interface) retira o doc do histórico."""
    b, ctrl = _dois_docs()
    wide = gerar_historico(b, ctrl, DelayPolicy(hoje=date(2024, 12, 31)),
                           excluir_codigos=["IT-2"])
    assert set(wide["No. do Documento"]) == {"IT-1"}


def test_remocao_manual_por_cmi_e_tolerante_a_sujeira():
    """Casa por CMI e tolera caixa/espaços/linhas em branco (como colado do Excel)."""
    b, ctrl = _dois_docs()
    wide = gerar_historico(b, ctrl, DelayPolicy(hoje=date(2024, 12, 31)),
                           excluir_codigos=["  cmi-2 ", ""])
    assert set(wide["No. do Documento"]) == {"IT-1"}


def test_remocao_manual_de_todos_gera_historico_vazio():
    """Remover todos os documentos não deve quebrar - histórico vazio."""
    b, ctrl = _dois_docs()
    wide = gerar_historico(b, ctrl, DelayPolicy(hoje=date(2024, 12, 31)),
                           excluir_codigos=["IT-1", "IT-2"])
    assert wide.empty


def test_fase_de_projeto_e_tracking_no_historico():
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1", "fase": "EXECUÇÃO"}),
                           DelayPolicy(hoje=date(2024, 12, 31)))
    r = wide.iloc[0]
    assert r["Fase de Projeto"] == "EXECUÇÃO"
    assert r["Tracking ID"] == "T1"          # tracking do doc buscado


def test_nao_emitido_tracking_em_branco_e_atraso_corrente():
    # Doc do Controle sem tracking no Aconex → NÃO EMITIDO, Tracking em BRANCO.
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1").evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    wide = gerar_historico(
        b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"},
                 {"itaipu": "IT-99", "cmi": "CMI-99", "titulo": "FANTASMA", "prevista": date(2024, 6, 1)}),
        DelayPolicy(hoje=date(2024, 12, 31)))
    ne = wide[wide["Status Envio"] == "NÃO EMITIDO"]
    assert len(ne) == 1
    s = ne.iloc[0]
    assert s["No. do Documento"] == "IT-99"
    assert str(s["Tracking ID"]) == ""                                  # em branco
    assert pd.Timestamp(s[COL_DATA_PREVISTA_CTRL]) == pd.Timestamp("2024-06-01")
    assert s[COL_ATRASO_CMI] == 213                                     # 01/06 → 31/12


def test_nao_emitido_recebe_metadados_do_controle():
    """A linha NÃO EMITIDO herda Especialidade/Subespecialidade/Tipo DCC/Subtipo DCC
    do Controle (o doc não está no Aconex para trazê-los) - pedido do usuário."""
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1").evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    wide = gerar_historico(
        b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"},
                 {"itaipu": "IT-99", "cmi": "CMI-99", "titulo": "FANTASMA",
                  "prevista": date(2024, 6, 1), "especialidade": "MECÂNICA",
                  "subespecialidade": "ET-123", "tipo_documento": "DESENHO",
                  "subtipo": "MONTAGEM"}),
        DelayPolicy(hoje=date(2024, 12, 31)))
    ne = wide[wide["No. do Documento"] == "IT-99"].iloc[0]
    assert ne["Especialidade"] == "MECÂNICA"
    assert ne["Subespecialidade"] == "ET-123"
    assert ne["Tipo do Documento DCC"] == "DESENHO"
    assert ne["Subtipo DCC"] == "MONTAGEM"


def test_emitido_no_controle_sem_tracking_vai_para_o_log():
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1").evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    logs = []
    gerar_historico(
        b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"},
                 {"itaipu": "IT-SUMIU", "cmi": "CMI-SUMIU", "emitido": "EMITIDO"}),
        DelayPolicy(hoje=date(2024, 12, 31)), log_cb=logs.append)
    txt = "\n".join(logs)
    assert "EMITIDO" in txt and "IT-SUMIU" in txt


def test_injecao_nao_emitido_para_doc_nao_postado(tmp_path):
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC POSTADO")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/02/2024"},
        {"itaipu": "IT-99", "cmi": "CMI-99", "titulo": "DOC NAO POSTADO", "prevista": "01/06/2024"},
    ])
    wide = gerar_historico(b, ler_controle(p), DelayPolicy(hoje=date(2024, 12, 31)))
    ne = wide[wide["Status Envio"] == "NÃO EMITIDO"]
    assert len(ne) == 1 and ne.iloc[0]["No. do Documento"] == "IT-99"
    assert ne.iloc[0][COL_ATRASO_CMI] == 213


def test_doc_postado_nao_gera_nao_emitido(tmp_path):
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/02/2024"},
    ])
    wide = gerar_historico(b, ler_controle(p), DelayPolicy(hoje=date(2024, 12, 31)))
    assert (wide["Status Envio"] == "NÃO EMITIDO").sum() == 0


def test_busca_tolerante_a_sujeira_de_excel(tmp_path):
    """Código do Controle com espaços internos/à volta casa pelo fallback
    tolerante (chave_codigo) mesmo com a cascata exata falhando (§24.8b)."""
    b = base(HistoricoBuilder("T1", "#ST00=U01BFA10UC012-UC009&EDC080", "0893410CYU20-209FDC-16", "DOC X")
             .evento("0A", 1, "Em Processo", "01/09/2025", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "  #ST00=U01BFA10 UC012 - UC009&EDC080 ", "cmi": "0893410CYU20 -209FDC-16",
         "prevista": "16/10/2025"},
    ])
    wide = gerar_historico(b, ler_controle(p), DelayPolicy(hoje=date(2025, 12, 31)))
    assert len(wide) == 1
    assert wide.iloc[0]["Data Prevista"] == pd.Timestamp("2025-10-16")
    assert wide.iloc[0]["Tracking ID"] == "T1"


# ==========================================================================
# Regras do wide preservadas (exercitadas via o Controle)
# ==========================================================================
def test_ordem_revisao_por_familia_e_cadeia_cmi():
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
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"}), DelayPolicy(hoje=date(2024, 12, 31)))
    assert list(wide["Revisão"]) == ["0A", "0B", "0", "1A"], list(wide["Revisão"])
    por_rev = {r["Revisão"]: r for _, r in wide.iterrows()}
    assert int(por_rev["1A"][COL_DIAS_CMI]) == 10


def test_ciclo_consistente_subida_errada_ignorada():
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0C", 1, "Em Processo", "05/06/2025")
        .evento("0C", 2, "Aprovado com Comentários", "19/06/2025")
        .evento("0C", 3, "Em Processo", "24/07/2025")
        .evento("0D", 4, "Em Processo", "24/07/2025")
        .evento("0D", 5, "Para Assinatura", "14/08/2025", current=True)
    )
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"}), DelayPolicy(hoje=date(2025, 12, 31)))
    c = wide[wide["Revisão"] == "0C"].iloc[0]
    assert c["Data Envio"] == pd.Timestamp("2025-06-05")
    assert c["Data Retorno"] == pd.Timestamp("2025-06-19")
    assert int(c["Dias Itaipu"]) == 14
    d = wide[wide["Revisão"] == "0D"].iloc[0]
    assert d["Data Envio"] == pd.Timestamp("2025-07-24")


def test_ciclo_consistente_relancamento_vira_pendente():
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, "Não Aprovado", "20/03/2025")
        .evento("0A", 3, "Em Processo", "01/06/2025", current=True)
    )
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"}), DelayPolicy(hoje=date(2025, 12, 31)))
    a = wide.iloc[0]
    assert a["Data Envio"] == pd.Timestamp("2025-06-01")
    assert pd.isna(a["Data Retorno"])
    assert int(a["Dias Itaipu"]) == 213
    assert int(a["Atraso Itaipu"]) == 183


def test_comissionamento_sem_envio_vira_nao_emitido():
    b = base(
        HistoricoBuilder("T1", "IT-PL-1", "CMI-PL-1", "SISTEMA X - PLANILHA DE COMISSIONAMENTO")
        .evento("0A", 1, "Para Aprovação", "10/04/2025")
        .evento("0A", 2, "Para Aprovação", "10/04/2025", current=True)
    )
    # Sem envio válido, o doc não tem linhas no wide (retorno fantasma removido)…
    from docmanager.core.wide import build_wide_table, gerar_dataset_dashboard
    assert build_wide_table(gerar_dataset_dashboard(b)).empty
    # …e no histórico aparece como NÃO EMITIDO (tem tracking, mas sem revisão válida).
    wide = gerar_historico(
        b, _ctrl({"itaipu": "IT-PL-1", "cmi": "CMI-PL-1", "titulo": "PLANILHA", "prevista": date(2025, 3, 1)}),
        DelayPolicy(hoje=date(2025, 12, 31)))
    assert len(wide) == 1 and wide.iloc[0]["Status Envio"] == "NÃO EMITIDO"


def test_comissionamento_com_envio_mantem_para_assinatura():
    b = base(
        HistoricoBuilder("T1", "IT-PL-2", "CMI-PL-2", "SISTEMA Y - PLANILHA DE COMISSIONAMENTO")
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, "Para Aprovação", "20/03/2025", current=True)
    )
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-PL-2", "cmi": "CMI-PL-2"}),
                           DelayPolicy(hoje=date(2025, 12, 31)))
    r = wide.iloc[0]
    assert r["Data Envio"] == pd.Timestamp("2025-03-01")
    assert r["Status Retorno"] == "Para Assinatura"
    assert int(r["Dias Itaipu"]) == 19


def test_para_aprovacao_vira_envio_fallback():
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0", 85, "Para Aprovação", "17/10/2023")
        .evento("0", 87, "Aprovado", "23/10/2023", current=True)
    )
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"}), DelayPolicy(hoje=date(2023, 12, 31)))
    r = wide.iloc[0]
    assert r["Data Envio"] == pd.Timestamp("2023-10-17")
    assert r["Data Retorno"] == pd.Timestamp("2023-10-23")
    assert int(r["Dias Itaipu"]) == 6


def test_para_aprovacao_nao_substitui_envio_real():
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0B", 1, "Em Processo", "01/03/2025")
        .evento("0B", 2, "Não Aprovado", "20/03/2025")
        .evento("0B", 3, "Para Aprovação", "25/03/2025", current=True)
    )
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1"}), DelayPolicy(hoje=date(2025, 12, 31)))
    r = wide.iloc[0]
    assert r["Data Envio"] == pd.Timestamp("2025-03-01")
    assert r["Data Retorno"] == pd.Timestamp("2025-03-20")
    assert int(r["Dias Itaipu"]) == 19


# ==========================================================================
# Exportação
# ==========================================================================
def test_base_atraso_cmi_0a_alterna_reprogramacao_vs_prevista(tmp_path):
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC A")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "IT-1", "cmi": "CMI-1", "prevista": "01/08/2024", "reprog": "20/08/2024"},
    ])
    ctrl = ler_controle(p)
    HJ = date(2024, 12, 31)
    reprog = gerar_historico(b, ctrl, DelayPolicy(hoje=HJ, base_cmi_0a="reprogramacao"))
    prev = gerar_historico(b, ctrl, DelayPolicy(hoje=HJ, base_cmi_0a="prevista"))
    assert int(reprog[reprog["Revisão"] == "0A"].iloc[0][COL_ATRASO_CMI]) == 12
    assert int(prev[prev["Revisão"] == "0A"].iloc[0][COL_ATRASO_CMI]) == 31


def test_exportacao_layout_fase_e_ordem_cmi_antes_itaipu(tmp_path):
    b = base(HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC 1")
             .evento("0A", 1, "Em Processo", "01/03/2024")
             .evento("0A", 2, "Aprovado", "20/03/2024", current=True))
    wide = gerar_historico(b, _ctrl({"itaipu": "IT-1", "cmi": "CMI-1", "fase": "PROJETO FABRICAÇÃO"}),
                           DelayPolicy(hoje=date(2024, 12, 31)))
    out = tmp_path / "hist.xlsx"
    ok, msg = exportar_historico(wide, out)
    assert ok, msg
    lido = pd.read_excel(out, sheet_name="Histórico")
    cols = list(lido.columns)
    assert "Fase de Projeto" in cols and cols[0] == "Fase de Projeto"
    assert "Data de Envio" in cols and "Data de Retorno" in cols
    # CMI antes de Itaipu (pedido do usuário)
    assert cols.index("Dias CMI") < cols.index("Dias Itaipu")
    assert cols.index("Atraso CMI") < cols.index("Atraso Itaipu")
    assert "Data Prevista (Controle)" not in cols


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
    por_rev = {r["Revisão"]: r for _, r in lido.iterrows()}
    assert str(por_rev["0A"]["Data Prevista"]) != "" and str(por_rev["0A"]["Reprogramação"]) != ""
    assert str(por_rev["0B"]["Data Prevista"]) == "" and str(por_rev["0B"]["Reprogramação"]) == ""


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
