"""Lista de Sobressalentes com Preço: o status 'For Partial Handover'.

Pedido do usuário (2026-10-26): na lista de sobressalentes com preço,
'For Partial Handover' é aprovação PARCIAL - consolidado APROVAÇÃO
INTERMEDIÁRIA, sucesso nos KPIs. A lista é reconhecida pelo título
(SOBRESSALENTE + PREÇO) ou pelo código terminado em PB021. Só nela - documento
comum com esse rótulo segue como antes.
"""
from datetime import date

import pandas as pd
import pytest
from builders import HistoricoBuilder, base

from docmanager.core.consolidation import (
    calcula_status_consolidado,
    calcula_status_consolidado_estrito,
)
from docmanager.core.doclist import LinhaDocList, calcular_predecessores
from docmanager.core.doclist import calcular_resumo_quantidades as resumo_doclist
from docmanager.core.hierarchy import LinhaPlano, calcular_hierarquia
from docmanager.core.hierarchy import calcular_resumo_quantidades as resumo_mapa
from docmanager.core.kpis import analisar_kpis_documento
from docmanager.core.mapping import processar_documento
from docmanager.core.reports.avanco import gerar_relatorio_avanco
from docmanager.core.reports.dashboard_series import calcular_kpis_revisoes
from docmanager.core.sobressalentes import e_lista_sobressalentes, normalizar_historico
from docmanager.core.status_engine import calcular_status_real
from docmanager.core.wide import build_wide_table, gerar_dataset_dashboard

HOJE = date(2025, 12, 31)
LISTA = "LISTA DE SOBRESSALENTES COM PREÇO - UNIDADE 9"
COMUM = "MEMORIAL DESCRITIVO DO SISTEMA X"
FPH = "For Partial Handover"


def _historico(eventos, titulo=LISTA, tracking="T1", doc="IT-SB-1", cmi=None) -> pd.DataFrame:
    """`eventos`: (rev, versão, status, data[, current])."""
    b = HistoricoBuilder(tracking, doc, cmi or "CMI-" + doc, titulo)
    for rev, versao, status, data, *resto in eventos:
        b.evento(rev, versao, status, data, current=bool(resto and resto[0]))
    return b.build()


ATUAL = [("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, FPH, "10/03/2025", True)]


# --------------------------------------------------------------------------
# Reconhecimento
# --------------------------------------------------------------------------
@pytest.mark.parametrize("titulo,codigos,esperado", [
    ("LISTA DE SOBRESSALENTES COM PREÇO", (), True),
    ("Lista de Sobressalentes com Precos", (), True),            # sem acento, plural
    ("LISTA DE SOBRESALENTES COM PREÇO", (), True),              # grafia com um S
    ("LISTA DE SOBRESSALENTES", (), False),                      # sem preço não é ela
    ("TABELA DE PREÇOS", (), False),
    ("DOCUMENTO QUALQUER", ("RDSPP-ABC-PB021",), True),          # pelo código Itaipu
    ("DOCUMENTO QUALQUER", ("IT-1", " rdspp-x-pb021 "), True),   # pelo CMI, caixa/espaço
    ("DOCUMENTO QUALQUER", ("RDSPP-PB021-01",), False),          # PB021 tem de ser o final
])
def test_reconhece_a_lista(titulo, codigos, esperado):
    assert e_lista_sobressalentes(titulo, *codigos) is esperado


def test_normaliza_so_as_linhas_da_lista():
    df = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", LISTA).evento("0A", 1, "for partial  HANDOVER", "10/03/2025"),
        HistoricoBuilder("T2", "IT-2", "CMI-2", COMUM).evento("0A", 1, "for partial  HANDOVER", "10/03/2025"),
    )
    out = normalizar_historico(df)
    assert list(out["Status"]) == [FPH, "for partial  HANDOVER"]
    assert list(df["Status"]) == ["for partial  HANDOVER"] * 2    # a entrada não é alterada


def test_sem_nada_para_normalizar_nao_copia():
    df = _historico([("0A", 1, "Aprovado", "10/03/2025", True)])
    assert normalizar_historico(df) is df


# --------------------------------------------------------------------------
# Status real e consolidado
# --------------------------------------------------------------------------
def test_status_real_e_for_partial_handover():
    assert calcular_status_real(_historico(ATUAL), "0A") == FPH


def test_reconhece_pelo_codigo_pb021():
    df = _historico(ATUAL, titulo="RDSPP UNIDADE 9", doc="IT-RDSPP-PB021")
    assert calcular_status_real(df, "0A") == FPH


def test_documento_comum_nao_reconhece():
    """Fora da lista o rótulo segue desconhecido e o documento cai onde sempre caiu."""
    assert calcular_status_real(_historico(ATUAL, titulo=COMUM), "0A") == "NÃO EMITIDO"


def test_fantasma_depois_do_handover_salva_o_veredito():
    df = _historico([("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, FPH, "10/03/2025"),
                     ("0A", 3, "Em Integração", "12/03/2025", True)])
    assert calcular_status_real(df, "0A") == FPH


def test_handover_vence_a_batalha_como_aprovacao():
    """Revisão nova em integração: vale o último veredito oficial da família."""
    df = _historico([("0A", 1, "Em Processo", "01/03/2025"), ("0A", 2, FPH, "20/03/2025"),
                     ("0B", 1, "Em Integração", "30/04/2025", True)])
    assert calcular_status_real(df, "0B") == FPH


def test_aprovado_depois_do_handover_vira_aprovado():
    df = _historico([("0A", 1, "Em Processo", "01/03/2025"), ("0A", 2, FPH, "20/03/2025"),
                     ("0B", 1, "Em Processo", "30/04/2025"), ("0B", 2, "Aprovado", "10/05/2025", True)])
    r = processar_documento(df, nivel="3", hoje=HOJE)
    assert r.status_real == "Aprovado"
    assert r.status_consolidado == "APROVADO"


def test_consolida_aprovacao_intermediaria_e_mantem_o_status_do_aconex():
    r = processar_documento(_historico(ATUAL), nivel="3", hoje=HOJE)
    assert r.status_real == FPH
    assert r.status_consolidado == "APROVAÇÃO INTERMEDIÁRIA"
    assert r.status_emissao == FPH
    assert r.emitido_nao_emitido == "EMITIDO"
    assert r.com_itaipu == "CMI"


def test_consolidado_e_regra_estrita():
    assert calcula_status_consolidado(FPH, FPH, "EMITIDO") == "APROVAÇÃO INTERMEDIÁRIA"
    assert calcula_status_consolidado_estrito(FPH, "APROVAÇÃO INTERMEDIÁRIA") == "APROVAÇÃO INTERMEDIÁRIA"


# --------------------------------------------------------------------------
# KPIs
# --------------------------------------------------------------------------
def test_kpi_handover_conta_como_sucesso():
    r = analisar_kpis_documento(_historico(ATUAL), FPH, "0A", None, hoje=HOJE)
    assert r["situacao_prazo"] == "Doc Aprovado"
    assert r["ciclos_aprovar"] == 1


def test_kpi_documento_comum_nao_conta_o_rotulo():
    df = _historico(ATUAL, titulo=COMUM)
    r = analisar_kpis_documento(df, "NÃO EMITIDO", "0A", None, hoje=HOJE)
    assert r["situacao_prazo"] != "Doc Aprovado"


# --------------------------------------------------------------------------
# Resumo de quantidades (Mapa e Doc List)
# --------------------------------------------------------------------------
def test_resumo_do_mapa_mostra_a_aprovacao_intermediaria():
    linhas = [
        LinhaPlano(1, "PL-1", nivel="2", status_consolidado="EM PROCESSO"),
        LinhaPlano(2, "SB-1", nivel="3", status_consolidado="APROVAÇÃO INTERMEDIÁRIA"),
        LinhaPlano(3, "SB-2", nivel="3", status_consolidado="APROVADO"),
    ]
    texto = resumo_mapa(linhas, calcular_hierarquia(linhas))[1]
    assert "Aprovação Intermediária: 1" in texto
    assert "Aprovados: 1" in texto


def test_resumo_do_mapa_sem_intermediaria_fica_como_antes():
    linhas = [
        LinhaPlano(1, "PL-1", nivel="2", status_consolidado="EM PROCESSO"),
        LinhaPlano(2, "SB-2", nivel="3", status_consolidado="APROVADO"),
    ]
    assert "Intermediária" not in resumo_mapa(linhas, calcular_hierarquia(linhas))[1]


def test_resumo_do_doclist_conta_a_aprovacao_intermediaria():
    linhas = [
        LinhaDocList(1, "G-1", nivel="1"),
        LinhaDocList(2, "SB-1", nivel="2", status_consolidado="APROVAÇÃO INTERMEDIÁRIA"),
    ]
    texto = resumo_doclist(linhas, calcular_predecessores(linhas))[1]
    assert "Aprovação Intermediária: 1" in texto
    assert "Outros" not in texto


# --------------------------------------------------------------------------
# Histórico consolidado / dashboard e Relatório de Avanço
# --------------------------------------------------------------------------
def _base_historico():
    return base(
        HistoricoBuilder("T1", "IT-SB-1", "CMI-SB-1", LISTA)
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, FPH, "20/03/2025", current=True),
        HistoricoBuilder("T3", "IT-3", "CMI-3", COMUM)
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, FPH, "20/03/2025", current=True),
    )


def test_historico_registra_o_retorno():
    wide = build_wide_table(gerar_dataset_dashboard(_base_historico())).set_index("Tracking ID")
    assert wide.loc["T1", "Status Retorno"] == FPH
    assert wide.loc["T1", "Data Retorno"] == pd.Timestamp("2025-03-20")
    # Documento comum: o rótulo continua fora dos status válidos, como antes.
    assert pd.isna(wide.loc["T3", "Status Retorno"])


def test_dashboard_conta_o_handover_como_aprovacao_tecnica():
    wide = build_wide_table(gerar_dataset_dashboard(_base_historico()))
    assert calcular_kpis_revisoes(wide[wide["Tracking ID"] == "T1"])["ciclo_aprovacao"] == 1


def test_relatorio_de_avanco_mantem_a_lista():
    ok, df = gerar_relatorio_avanco(_base_historico())
    assert ok
    status = dict(zip(df["No. do Documento"], df["Status"]))
    assert status["IT-SB-1"] == FPH
    assert "IT-3" not in status            # documento comum: filtrado, como sempre
