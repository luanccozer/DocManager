"""Pipeline do Mapa: processar_documento (puro) + atualizar_mapeamento (I/O headless)."""
from datetime import date

import openpyxl
from builders import HistoricoBuilder, base

from docmanager.core.hierarchy import (
    LinhaPlano,
    aplicar_regra_estrita,
    calcular_hierarquia,
    calcular_resumo_quantidades,
    identificar_planos_comissionamento,
)
from docmanager.core.mapping import processar_documento
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


_COLS_MAPA_REPROG = [
    "GRUPO", "Nº CMI", "N° ITAIPU", "DESCRIÇÃO DO DOCUMENTO", "NÍVEL",
    "DATA PREVISTA EMISSÃO ETAPA 1", "DATA REPROGRAMADA", "EMITIDO / NÃO EMITIDO",
    "DATA ÚLTIMA EMISSÃO", "ÚLTIMA REV. EMITIDA", "STATUS REAL", "STATUS",
    "STATUS CONSOLIDADO", "COM ITAIPU", "PLANO DE EXECUÇÃO", "PREDECESSOR",
    "TAG ETAPA", "RESUMO QUANTIDADES",
]


def test_mapa_preenche_prevista_e_reprogramada(tmp_path):
    """Controle: DATA PREVISTA vai na célula (vazia); REPROGRAMAÇÃO na coluna
    DATA REPROGRAMADA (posicional). Atraso do KPI usa a reprogramação."""
    from openpyxl import Workbook

    from docmanager.services.controle_docs import ler_controle

    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC A")
             .evento("0A", 1, "Em Processo", "01/09/2024", current=True))
    base_path = tmp_path / "base.xlsx"
    b.to_excel(base_path, index=False)

    # Mapa com a coluna DATA REPROGRAMADA logo após a DATA PREVISTA ETAPA 1.
    mapa_path = tmp_path / "mapa.xlsx"
    wb = Workbook()
    ws = wb.active
    for c, nome in enumerate(_COLS_MAPA_REPROG, 1):
        ws.cell(1, c, nome)
    ws.cell(3, 1, "SALAS")
    ws.cell(3, 2, "CMI-1")
    ws.cell(3, 3, "#IT-1")
    ws.cell(3, 4, "DOC A")
    ws.cell(3, 5, "4")
    wb.save(mapa_path)

    # Controle: cabeçalho na linha 4, PREVISTA (DD-MM) + REPROGRAMAÇÃO (US M/D).
    ctrl_path = tmp_path / "ctrl.xlsx"
    wc = Workbook()
    wsc = wc.active
    wsc.append(["ITAIPU - CONTROLE DE DOCUMENTOS"])
    wsc.append([])
    wsc.append([])
    wsc.append(["CODIFICAÇÃO ITAIPÚ (ACONEX)", "NÚMERO INTERNO", "DESCRIÇÃO",
                "DATA PREVISTA DE EMISSÃO ACONEX", "REPROGRAMAÇÃO"])
    wsc.append(["#IT-1", "CMI-1", "DOC A", "01-09-2024", "10/20/2024"])
    wc.save(ctrl_path)

    controle = ler_controle(ctrl_path)
    r = atualizar_mapeamento(str(base_path), str(mapa_path), controle=controle,
                             hoje=HOJE, log_cb=lambda m: None)
    assert r.ok

    wb2 = openpyxl.load_workbook(mapa_path)
    ws2 = wb2.active
    prevista = ws2.cell(3, 6).value   # DATA PREVISTA EMISSÃO ETAPA 1
    reprog = ws2.cell(3, 7).value     # DATA REPROGRAMADA
    assert str(prevista).startswith("2024-09-01"), prevista
    assert str(reprog).startswith("2024-10-20"), reprog   # US M/D → 20/out


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


# --------------------------------------------------------------------------
# Regra estrita nos PLANOS de (des)comissionamento (nível 2 → planilhas nível 3)
# --------------------------------------------------------------------------
def _linhas_comiss():
    """Plano de comissionamento (nível 2) com 2 planilhas nível 3: uma com
    aprovação parcial, outra aprovada seca."""
    return [
        LinhaPlano(row=1, cod_itaipu="#PLANO1", nivel="1", descricao="PLANO DE EXECUÇÃO"),
        LinhaPlano(row=2, cod_itaipu="#PLANO-COM", nivel="2", descricao="PLANO DE COMISSIONAMENTO Z",
                   status_real="Aprovado", status_consolidado="APROVADO"),
        LinhaPlano(row=3, cod_itaipu="#PLAN-1", nivel="3", descricao="PLANILHA DE COMISSIONAMENTO A",
                   status_real="Aprovado com Comentários", status_consolidado="APROVADO"),
        LinhaPlano(row=4, cod_itaipu="#PLAN-2", nivel="3", descricao="PLANILHA DE COMISSIONAMENTO B",
                   status_real="Aprovado", status_consolidado="APROVADO"),
    ]


def test_identifica_plano_comissionamento_so_nivel_2():
    linhas = _linhas_comiss() + [
        LinhaPlano(row=5, cod_itaipu="#PLANO-DESCOM", nivel="2", descricao="PLANO DE DESCOMISSIONAMENTO W"),
        LinhaPlano(row=6, cod_itaipu="#OUTRO2", nivel="2", descricao="PLANO DE MONTAGEM"),  # não é (des)comiss
    ]
    planos = identificar_planos_comissionamento(linhas)
    assert planos == {"#PLANO-COM", "#PLANO-DESCOM"}   # nível 2 (des)comiss; #OUTRO2 fora


def test_regra_estrita_rebaixa_planilha_nivel_3_sob_plano_comissionamento():
    linhas = _linhas_comiss()
    hier = calcular_hierarquia(linhas)
    planos = identificar_planos_comissionamento(linhas)
    novos = aplicar_regra_estrita(linhas, hier, vips=set(), planos_comiss=planos)
    assert novos[3] == "APROVAÇÃO INTERMEDIÁRIA"   # aprovação parcial rebaixada
    assert novos[4] == "APROVADO"                  # aprovado seco continua APROVADO


def test_resumo_do_plano_comissionamento_conta_intermediaria():
    linhas = _linhas_comiss()
    hier = calcular_hierarquia(linhas)
    planos = identificar_planos_comissionamento(linhas)
    # Aplica o rebaixamento (como o orquestrador faz) antes do resumo.
    for row_r, cons in aplicar_regra_estrita(linhas, hier, set(), planos).items():
        linhas[row_r - 1].status_consolidado = cons
    resumo = calcular_resumo_quantidades(linhas, hier, estrito=True, planos_comiss=planos)
    texto = resumo[2]   # o plano de comissionamento (nível 2)
    assert "Aprovação Intermediária: 1" in texto
    assert "Aprovados: 1" in texto
    assert "Total: 2" in texto


def test_resumo_plano_comissionamento_sem_toggle_mantem_plano_aprovado():
    """Com o toggle DESLIGADO, o plano nível 2 APROVADO volta ao atalho 'Plano
    Aprovado' — nenhuma mudança de comportamento."""
    linhas = _linhas_comiss()
    hier = calcular_hierarquia(linhas)
    planos = identificar_planos_comissionamento(linhas)
    resumo = calcular_resumo_quantidades(linhas, hier, estrito=False, planos_comiss=planos)
    assert resumo[2] == "Plano Aprovado"
