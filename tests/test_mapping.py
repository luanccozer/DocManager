"""Pipeline do Mapa: processar_documento (puro) + atualizar_mapeamento (I/O headless)."""
from datetime import date

import openpyxl
from builders import HistoricoBuilder, base

from docmanager.core.mapping import filtrar_historico_por_titulo, processar_documento
from docmanager.services.excel_io import MappingSheet
from docmanager.services.mapping_update import atualizar_mapeamento

HOJE = date(2024, 12, 31)

_COLS_MAPA = [
    "GRUPO", "Nº CMI", "N° ITAIPU", "DESCRIÇÃO DO DOCUMENTO", "NÍVEL",
    "DATA PREVISTA EMISSÃO ETAPA 1", "EMITIDO / NÃO EMITIDO", "DATA ÚLTIMA EMISSÃO",
    "ÚLTIMA REV. EMITIDA", "STATUS REAL", "STATUS", "STATUS CONSOLIDADO",
    "COM ITAIPU", "PLANO DE EXECUÇÃO", "PREDECESSOR", "TAG ETAPA", "RESUMO QUANTIDADES",
]


def _escrever_mapa(path, linhas):
    """linhas: list de (cmi, itaipu, descricao, nivel). Cabeçalho na linha 1, dados na 3."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for c, nome in enumerate(_COLS_MAPA, 1):
        ws.cell(1, c, nome)
    for i, (cmi, itaipu, desc, nivel) in enumerate(linhas, start=3):
        ws.cell(i, 1, "SALAS")
        ws.cell(i, 2, cmi)
        ws.cell(i, 3, itaipu)
        ws.cell(i, 4, desc)
        ws.cell(i, 5, nivel)
    wb.save(path)


def test_processar_documento_aprovado():
    df = (HistoricoBuilder("T", "IT-1", "CMI-1")
          .evento("0A", 1, "Em Processo", "01/03/2024")
          .evento("0A", 2, "Aprovado", "20/03/2024", current=True)).build()
    r = processar_documento(df, nivel="4", tag_etapa="", data_prevista=None, hoje=HOJE)
    assert r.status_real == "Aprovado"
    assert r.status_consolidado == "APROVADO"
    assert r.emitido_nao_emitido == "EMITIDO"


def test_processar_documento_nao_encontrado():
    import pandas as pd
    r = processar_documento(pd.DataFrame(), nivel="4", tag_etapa="", data_prevista="01/06/2024", hoje=HOJE)
    assert r.status_real == "NÃO EMITIDO"
    assert r.kpis["situacao_prazo"] == "Atrasado"  # cobra a data prevista vencida


def test_filtro_tag_etapa_esvazia_vira_nao_emitido():
    df = HistoricoBuilder("T", "IT", "CMI", titulo="PLANO ETAPA 3").evento("0A", 1, "Aprovado", "01/03/2024", current=True).build()
    r = processar_documento(df, nivel="1", tag_etapa="ETAPA 9", data_prevista=None, hoje=HOJE)
    assert r.status_real == "NÃO EMITIDO"  # nenhum título contém 'ETAPA 9'


def test_atualizar_mapeamento_headless(tmp_path):
    # Base: 1 plano nível 1 (aprovado) + 1 planilha nível 3 (em processo).
    b = base(
        HistoricoBuilder("T1", "#PLANO1", "CMI-1", "PLANO DE EXECUÇÃO X")
        .evento("0A", 1, "Aprovado", "01/03/2024", current=True),
        HistoricoBuilder("T2", "#PLAN-COM", "CMI-2", "PLANILHA DE COMISSIONAMENTO Y")
        .evento("0A", 1, "Em Processo", "01/09/2024", current=True),
    )
    base_path = tmp_path / "base.xlsx"
    b.to_excel(base_path, index=False)
    mapa_path = tmp_path / "mapa.xlsx"
    _escrever_mapa(mapa_path, [
        ("CMI-1", "#PLANO1", "PLANO DE EXECUÇÃO X", "1"),
        ("CMI-2", "#PLAN-COM", "PLANILHA DE COMISSIONAMENTO Y", "3"),
    ])

    r = atualizar_mapeamento(str(base_path), str(mapa_path), hoje=HOJE, log_cb=lambda m: None)
    assert r.ok and r.linhas_processadas == 2

    ms = MappingSheet(openpyxl.load_workbook(mapa_path).active)
    linhas = {ln.cod_itaipu: ln for ln in ms.ler_linhas()}
    assert ms.get_val("status_real", linhas["#PLANO1"].row) == "Aprovado"
    assert ms.get_val("status_consolidado", linhas["#PLANO1"].row) == "APROVADO"
    # hierarquia: nível 1 é predecessor/plano de si mesmo
    assert ms.get_val("predecessor", linhas["#PLANO1"].row) == "#PLANO1"
    # a planilha nível 3 está em processo
    assert ms.get_val("com_itaipu", linhas["#PLAN-COM"].row) == "ITAIPU"
