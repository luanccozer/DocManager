"""Planilhas de comissionamento (nível 3): os status próprios do fluxo delas.

Pedido do usuário (2026-09-30): nas planilhas de comissionamento,
'Aguardando Editável' equivale a 'Para Assinatura' (consolidado APROVADO) e
'Reviewed with No Comments' equivale a 'Não Aprovado' (consolidado NÃO
APROVADO). Só nelas - documento comum com esses rótulos segue como antes.

O teste mais forte aqui é o de EQUIVALÊNCIA: o mesmo histórico, escrito uma vez
com os rótulos novos e outra com os status equivalentes, tem de dar exatamente
o mesmo resultado em todos os motores. É isso que "equivale a" quer dizer.
"""
from datetime import date

import pandas as pd
import pytest
from builders import HistoricoBuilder, base

from docmanager.core.comissionamento import (
    e_planilha_comissionamento,
    equivalente,
    traduzir_historico,
)
from docmanager.core.consolidation import (
    calcula_status_consolidado,
    calcula_status_consolidado_estrito,
)
from docmanager.core.kpis import analisar_kpis_documento, calcular_atrasos_acumulados
from docmanager.core.mapping import processar_documento
from docmanager.core.reports.avanco import gerar_relatorio_avanco
from docmanager.core.status_engine import calcular_status_real
from docmanager.core.wide import build_wide_table, gerar_dataset_dashboard

HOJE = date(2025, 12, 31)
PLANILHA = "SISTEMA X - PLANILHA DE COMISSIONAMENTO"
COMUM = "MEMORIAL DESCRITIVO DO SISTEMA X"

AE = "Aguardando Editável"
RNC = "Reviewed with No Comments"
# Cada rótulo novo → o status que ele equivale.
EQUIVALENTE = {AE: "Para Assinatura", RNC: "Não Aprovado"}


def _historico(eventos, titulo=PLANILHA, tracking="T1", doc="IT-PL-1") -> pd.DataFrame:
    """`eventos`: (rev, versão, status, data[, current])."""
    b = HistoricoBuilder(tracking, doc, "CMI-" + doc, titulo)
    for rev, versao, status, data, *resto in eventos:
        b.evento(rev, versao, status, data, current=bool(resto and resto[0]))
    return b.build()


def _canonico(eventos):
    """O mesmo histórico, com os status equivalentes no lugar dos rótulos novos."""
    return [(rev, v, EQUIVALENTE.get(st, st), data, *resto) for rev, v, st, data, *resto in eventos]


# --------------------------------------------------------------------------
# Reconhecimento e tradução
# --------------------------------------------------------------------------
@pytest.mark.parametrize("titulo,esperado", [
    ("PLANILHA DE COMISSIONAMENTO", True),
    ("Planilha de Comissionamento - Unidade 9", True),     # caixa não importa
    ("PLANILHA DE TESTES DE COMISSIONAMENTO", True),
    ("PLANO DE COMISSIONAMENTO", False),                   # o plano (nível 2) não é planilha
    ("PLANILHA DE CÁLCULO", False),
])
def test_reconhece_a_planilha_pelo_titulo(titulo, esperado):
    assert e_planilha_comissionamento(titulo) is esperado


@pytest.mark.parametrize("bruto,esperado", [
    ("Aguardando Editável", "Para Assinatura"),
    ("AGUARDANDO EDITAVEL", "Para Assinatura"),            # sem acento, maiúsculas
    ("  aguardando   editável ", "Para Assinatura"),       # espaço sobrando
    ("Reviewed with No Comments", "Não Aprovado"),
    ("REVIEWED WITH NO COMMENTS", "Não Aprovado"),
    ("Aprovado", "Aprovado"),                              # o resto volta intacto
    ("Em Processo", "Em Processo"),
])
def test_equivalente_tolera_acento_caixa_e_espaco(bruto, esperado):
    assert equivalente(bruto) == esperado


def test_traduz_so_as_linhas_de_planilha():
    df = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", PLANILHA).evento("0A", 1, AE, "10/03/2025"),
        HistoricoBuilder("T2", "IT-2", "CMI-2", COMUM).evento("0A", 1, AE, "10/03/2025"),
    )
    status = dict(zip(traduzir_historico(df)["Tracking ID"], traduzir_historico(df)["Status"]))
    assert status == {"T1": "Para Assinatura", "T2": AE}
    assert list(df["Status"]) == [AE, AE]          # a entrada não é alterada


def test_sem_nada_para_traduzir_nao_copia():
    """Quase todo documento cai aqui - não pode custar uma cópia do histórico."""
    df = _historico([("0A", 1, "Aprovado", "10/03/2025", True)])
    assert traduzir_historico(df) is df


# --------------------------------------------------------------------------
# Status real
# --------------------------------------------------------------------------
def test_aguardando_editavel_vira_para_assinatura():
    df = _historico([("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, AE, "10/03/2025", True)])
    assert calcular_status_real(df, "0A") == "Para Assinatura"


def test_reviewed_with_no_comments_vira_nao_aprovado():
    df = _historico([("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, RNC, "10/03/2025", True)])
    assert calcular_status_real(df, "0A") == "Não Aprovado"


@pytest.mark.parametrize("rotulo", [AE, RNC])
def test_documento_comum_nao_traduz(rotulo):
    """O pedido é só para o nível 3: fora da planilha o rótulo segue
    desconhecido e o documento cai onde sempre caiu."""
    df = _historico([("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, rotulo, "10/03/2025", True)],
                    titulo=COMUM)
    assert calcular_status_real(df, "0A") == "NÃO EMITIDO"


# Históricos em que os rótulos novos aparecem nas posições que o motor trata
# de jeito diferente: veredito atual, fantasma depois do veredito (salvamento
# na própria revisão), reemissão depois da reprovação, revisão numérica e
# reprovação depois da aprovação.
CENARIOS = {
    "aguardando_atual": [("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, AE, "10/03/2025", True)],
    "reviewed_atual": [("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, RNC, "10/03/2025", True)],
    "fantasma_salva_aguardando": [("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, AE, "10/03/2025"),
                                  ("0A", 3, "Em Integração", "12/03/2025", True)],
    "fantasma_salva_reviewed": [("0A", 1, "Em Processo", "10/02/2025"), ("0A", 2, RNC, "10/03/2025"),
                                ("0A", 3, "Validado", "12/03/2025", True)],
    "reemissao_apos_reviewed": [("0A", 1, "Em Processo", "01/03/2025"), ("0A", 2, RNC, "20/03/2025"),
                                ("0B", 1, "Em Processo", "30/04/2025", True)],
    "aguardando_na_reemissao": [("0A", 1, "Em Processo", "01/03/2025"), ("0A", 2, RNC, "20/03/2025"),
                                ("0B", 1, "Em Processo", "30/04/2025"), ("0B", 2, AE, "10/05/2025", True)],
    "reviewed_em_revisao_numerica": [("0A", 1, "Em Processo", "01/03/2025"), ("0A", 2, AE, "20/03/2025"),
                                     ("0", 1, "Em Processo", "30/04/2025"), ("0", 2, RNC, "10/05/2025", True)],
    "reviewed_depois_de_aguardando": [("0A", 1, "Em Processo", "01/03/2025"), ("0A", 2, AE, "20/03/2025"),
                                      ("0A", 3, RNC, "25/03/2025", True)],
}


@pytest.mark.parametrize("nome", CENARIOS)
def test_status_real_equivalente(nome):
    eventos = CENARIOS[nome]
    rev = next(e[0] for e in eventos if len(e) > 4 and e[4])
    assert (calcular_status_real(_historico(eventos), rev)
            == calcular_status_real(_historico(_canonico(eventos)), rev))


@pytest.mark.parametrize("nome", CENARIOS)
def test_mapa_e_doclist_equivalentes(nome):
    """processar_documento é o motor do Mapa E do Doc List: status real,
    consolidado, com quem está, KPIs e atrasos iguais aos do equivalente."""
    eventos = CENARIOS[nome]
    novo = processar_documento(_historico(eventos), nivel="3", data_prevista="01/02/2025", hoje=HOJE)
    ref = processar_documento(_historico(_canonico(eventos)), nivel="3", data_prevista="01/02/2025",
                              hoje=HOJE)
    for campo in ("status_real", "status_consolidado", "emitido_nao_emitido", "com_itaipu",
                  "kpis", "atrasos", "data_primeira_emissao"):
        assert getattr(novo, campo) == getattr(ref, campo), campo


# --------------------------------------------------------------------------
# Consolidado (o que o usuário pediu, com todas as letras)
# --------------------------------------------------------------------------
def test_aguardando_editavel_consolida_aprovado_e_mantem_o_status_do_aconex():
    r = processar_documento(_historico(CENARIOS["aguardando_atual"]), nivel="3", hoje=HOJE)
    assert r.status_real == "Para Assinatura"
    assert r.status_consolidado == "APROVADO"
    assert r.status_emissao == AE          # coluna STATUS: o rótulo cru do Aconex
    assert r.com_itaipu == "CMI"


def test_reviewed_consolida_nao_aprovado_e_mantem_o_status_do_aconex():
    r = processar_documento(_historico(CENARIOS["reviewed_atual"]), nivel="3", hoje=HOJE)
    assert r.status_real == "Não Aprovado"
    assert r.status_consolidado == "NÃO APROVADO"
    assert r.status_emissao == RNC


def test_consolidado_nao_cai_em_erro_com_o_bruto_novo():
    """Sem traduzir o bruto, o par (Não Aprovado, Reviewed...) virava ERRO."""
    assert calcula_status_consolidado("Não Aprovado", RNC, "EMITIDO") == "NÃO APROVADO"
    assert calcula_status_consolidado("Para Assinatura", AE, "EMITIDO") == "APROVADO"


def test_regra_estrita_trata_aguardando_como_para_assinatura():
    """Com o toggle VIP ligado, 'Para Assinatura' vira APROVAÇÃO INTERMEDIÁRIA -
    e 'Aguardando Editável' também, por ser o mesmo status."""
    r = processar_documento(_historico(CENARIOS["aguardando_atual"]), nivel="3", hoje=HOJE)
    assert calcula_status_consolidado_estrito(r.status_real, r.status_consolidado) == \
        "APROVAÇÃO INTERMEDIÁRIA"


# --------------------------------------------------------------------------
# KPIs e atrasos (dependem de reconhecer o retorno no histórico bruto)
# --------------------------------------------------------------------------
def test_kpi_aguardando_editavel_e_doc_aprovado():
    df = _historico(CENARIOS["aguardando_atual"])
    r = analisar_kpis_documento(df, "Para Assinatura", "0A", None, hoje=HOJE)
    assert r["situacao_prazo"] == "Doc Aprovado"
    assert r["ciclos_aprovar"] == 1


def test_kpi_reviewed_poe_a_bola_com_a_cmi():
    """O relógio da CMI conta a partir do 'Reviewed with No Comments' - sem a
    tradução ele não seria reconhecido como retorno e o prazo ficaria vazio."""
    df = _historico([("0A", 1, "Em Processo", "01/12/2025"), ("0A", 2, RNC, "11/12/2025", True)])
    r = analisar_kpis_documento(df, "Não Aprovado", "0A", None, hoje=HOJE)
    assert r["dias_status"] == 20          # 11/12 → 31/12
    assert r["dias_atraso"] == 5           # SLA de reemissão da CMI: 15 dias
    assert r["situacao_prazo"] == "Atrasado"


def test_kpi_downgrade_de_aguardando_para_reviewed():
    df = _historico(CENARIOS["reviewed_depois_de_aguardando"])
    assert analisar_kpis_documento(df, "Não Aprovado", "0A", None, hoje=HOJE)["downgrade"] == "SIM"


def test_atraso_de_retrabalho_da_cmi_conta_depois_do_reviewed():
    df = _historico(CENARIOS["reemissao_apos_reviewed"])
    r = calcular_atrasos_acumulados(df, "Em Processo", None, hoje=HOJE)
    assert r["atraso_acumulado_cmi"] == 26     # 20/03 → 30/04 = 41 dias − 15 de SLA


# --------------------------------------------------------------------------
# Histórico consolidado / dashboard e Relatório de Avanço
# --------------------------------------------------------------------------
def _base_historico():
    return base(
        HistoricoBuilder("T1", "IT-PL-1", "CMI-PL-1", PLANILHA)
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, AE, "20/03/2025", current=True),
        HistoricoBuilder("T2", "IT-PL-2", "CMI-PL-2", PLANILHA)
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, RNC, "25/03/2025", current=True),
        HistoricoBuilder("T3", "IT-3", "CMI-3", COMUM)
        .evento("0A", 1, "Em Processo", "01/03/2025")
        .evento("0A", 2, AE, "20/03/2025", current=True),
    )


def test_historico_registra_o_retorno_equivalente():
    wide = build_wide_table(gerar_dataset_dashboard(_base_historico())).set_index("Tracking ID")
    assert wide.loc["T1", "Status Retorno"] == "Para Assinatura"
    assert wide.loc["T1", "Data Retorno"] == pd.Timestamp("2025-03-20")
    assert wide.loc["T2", "Status Retorno"] == "Não Aprovado"
    # Documento comum: o rótulo continua fora dos status válidos, como antes.
    assert pd.isna(wide.loc["T3", "Status Retorno"])


def test_relatorio_de_avanco_mantem_a_planilha_com_o_status_equivalente():
    ok, df = gerar_relatorio_avanco(_base_historico())
    assert ok
    status = dict(zip(df["No. do Documento"], df["Status"]))
    assert status["IT-PL-1"] == "Para Assinatura"
    assert status["IT-PL-2"] == "Não Aprovado"
    assert "IT-3" not in status            # documento comum: filtrado, como sempre
    assert set(df.loc[df["No. do Documento"].str.startswith("IT-PL"), "Empresa"]) == {"CMI"}
