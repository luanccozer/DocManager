"""Fluxos de Trabalho: parse da Workflows API + relatório 'onde está e com quem'."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from docmanager.core.reports.fluxos import (
    analisar_fluxos_em_andamento,
    resumir_por_responsavel,
)
from docmanager.workflows_backend import (
    montar_dataframe_workflows,
    parse_pagina_workflows,
)

# XML fiel ao que a API devolve (inclusive o espaço à direita em 'Concluído ',
# que o Aconex realmente manda e quebraria toda comparação exata).
XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<WorkflowSearch TotalResultsOnPage="2" TotalResults="2" TotalPages="1" PageSize="25" CurrentPage="1">
 <SearchResults>
  <Workflow WorkflowId="111">
   <Assignees>
    <Assignee><OrganizationId>1</OrganizationId><OrganizationName>ITAIPU BINACIONAL</OrganizationName>
     <Name>Edson Mancini</Name><UserId>10</UserId></Assignee>
    <Assignee><OrganizationId>2</OrganizationId>
     <OrganizationName>CONSORCIO MODERNIZACAO ITAIPU</OrganizationName>
     <Name>Gustavo Takehara</Name><UserId>11</UserId></Assignee>
   </Assignees>
   <Comments>Documento ja comentado</Comments>
   <DateCompleted></DateCompleted>
   <DateDue>2026-09-11T00:00:00.000Z</DateDue>
   <DateIn>2026-09-04T00:00:00.000Z</DateIn>
   <DaysLate>0</DaysLate>
   <DocumentNumber>#ST60=M20MKD10-UH901&amp;EAB010</DocumentNumber>
   <DocumentRevision>0B</DocumentRevision>
   <DocumentTitle>LISTA DE DOCUMENTOS</DocumentTitle>
   <DocumentTrackingId>999888777</DocumentTrackingId>
   <DocumentVersion>8</DocumentVersion>
   <Duration>7.0</Duration>
   <Initiator><OrganizationId>2</OrganizationId>
    <OrganizationName>CONSORCIO MODERNIZACAO ITAIPU</OrganizationName>
    <Name>BIANCA SANTOS</Name><UserId>20</UserId></Initiator>
   <ReasonForIssue>Issued for Review</ReasonForIssue>
   <StepName>Analisis Compartido</StepName>
   <StepOutcome>Em Processo</StepOutcome>
   <StepStatus>Atual</StepStatus>
   <WorkflowName>03 - UNI GER - AUX ASO UG</WorkflowName>
   <WorkflowNumber>WF-010474</WorkflowNumber>
   <WorkflowStatus>Em Andamento</WorkflowStatus>
   <WorkflowTemplate>03 - UNI GER</WorkflowTemplate>
  </Workflow>
  <Workflow WorkflowId="222">
   <Assignees>
    <Assignee><OrganizationId>1</OrganizationId><OrganizationName>ITAIPU BINACIONAL</OrganizationName>
     <Name>Jefferson Mello</Name><UserId>12</UserId></Assignee>
   </Assignees>
   <DateDue>2026-08-20T00:00:00.000Z</DateDue>
   <DateIn>2026-08-01T00:00:00.000Z</DateIn>
   <DocumentNumber>#ST60=X00XGF10&amp;MLD020</DocumentNumber>
   <DocumentRevision>0A</DocumentRevision>
   <DocumentTitle>DIAGRAMA</DocumentTitle>
   <DocumentTrackingId>555</DocumentTrackingId>
   <StepName>ENCA-E</StepName>
   <StepStatus>Em Atraso</StepStatus>
   <WorkflowNumber>WF-010119</WorkflowNumber>
   <WorkflowStatus>Em Andamento</WorkflowStatus>
  </Workflow>
 </SearchResults>
</WorkflowSearch>"""


def _base_fluxos():
    return montar_dataframe_workflows(parse_pagina_workflows(XML))


# ---------------------------------------------------------------------------
# Parse / montagem
# ---------------------------------------------------------------------------
def test_parse_achata_assignees_e_pessoas():
    linhas = parse_pagina_workflows(XML)
    assert len(linhas) == 2
    a = linhas[0]
    assert a["Workflow ID"] == "111"
    assert a["Atribuído a"] == "Edson Mancini; Gustavo Takehara"
    assert a["Organização Atribuída"] == "ITAIPU BINACIONAL; CONSORCIO MODERNIZACAO ITAIPU"
    # Pareada 1-a-1 com os nomes: é o que evita fragmentar a pessoa no resumo.
    assert a["Organizações (por atribuído)"] == "ITAIPU BINACIONAL; CONSORCIO MODERNIZACAO ITAIPU"
    assert a["Qtd. Atribuídos"] == 2
    assert a["Iniciador"] == "BIANCA SANTOS"
    assert a["Organização Iniciador"] == "CONSORCIO MODERNIZACAO ITAIPU"


def test_parse_faz_strip_do_espaco_a_direita():
    """O Aconex manda 'Concluído ' com espaço — sem strip, todo filtro falha."""
    xml = XML.replace(b"<StepStatus>Atual</StepStatus>",
                      b"<StepStatus>Concluido </StepStatus>")
    assert parse_pagina_workflows(xml)[0]["StepStatus"] == "Concluido"


def test_montar_dataframe_renomeia_ordena_e_formata_datas():
    df = _base_fluxos()
    # Nomes IDÊNTICOS aos da base de documentos → junção direta.
    assert {"No. do Documento", "Tracking ID", "Revisão", "Título"} <= set(df.columns)
    assert list(df.columns)[:3] == ["Nº do Fluxo", "Nome do Fluxo", "Status do Fluxo"]
    assert df.loc[0, "Data de Vencimento"] == "11/09/2026"
    assert df.loc[0, "Tracking ID"] == "999888777"


def test_montar_dataframe_vazio():
    assert montar_dataframe_workflows([]).empty


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------
def test_fluxos_em_andamento_calcula_prazo_e_atraso():
    d = analisar_fluxos_em_andamento(_base_fluxos(), hoje=date(2026, 9, 4))
    assert len(d) == 2
    # Mais atrasado primeiro.
    atrasado = d.iloc[0]
    assert atrasado["Nº do Fluxo"] == "WF-010119"
    assert atrasado["Dias de Atraso"] == 15        # 20/08 → 04/09
    assert atrasado["Dias em Aberto"] == 34        # 01/08 → 04/09
    assert atrasado["Situação"] == "Atrasado"
    no_prazo = d.iloc[1]
    assert no_prazo["Dias de Atraso"] == 0
    assert no_prazo["Situação"] == "No prazo"
    assert no_prazo["Atribuído a"] == "Edson Mancini; Gustavo Takehara"


def test_fluxos_vence_hoje():
    d = analisar_fluxos_em_andamento(_base_fluxos(), hoje=date(2026, 9, 11))
    assert d.set_index("Nº do Fluxo").loc["WF-010474", "Situação"] == "Vence hoje"


def test_fluxos_ignora_etapas_fechadas_e_previsao():
    """Só 'Atual'/'Em Atraso' respondem 'com quem está' — concluída é passado,
    previsão ainda não começou."""
    df = _base_fluxos()
    df.loc[0, "Status da Etapa"] = "Concluído"
    df.loc[1, "Status da Etapa"] = "Previsão"
    assert analisar_fluxos_em_andamento(df, hoje=date(2026, 9, 4)).empty


def test_fluxos_ignora_fluxo_concluido():
    df = _base_fluxos()
    df["Status do Fluxo"] = "Concluído"
    assert analisar_fluxos_em_andamento(df, hoje=date(2026, 9, 4)).empty


def test_fluxos_base_errada_da_erro_acionavel():
    """Apontar a base de DOCUMENTOS aqui é o engano óbvio — a mensagem tem que dizer."""
    with pytest.raises(KeyError, match="Fluxos"):
        analisar_fluxos_em_andamento(pd.DataFrame({"No. do Documento": ["X"]}))


def test_fluxos_sem_vencimento_fica_sem_prazo():
    df = _base_fluxos()
    df["Data de Vencimento"] = ""
    d = analisar_fluxos_em_andamento(df, hoje=date(2026, 9, 4))
    assert set(d["Situação"]) == {"Sem prazo"}
    assert set(d["Dias de Atraso"]) == {0}


# ---------------------------------------------------------------------------
# Resumo por responsável
# ---------------------------------------------------------------------------
def test_resumo_por_pessoa_explode_a_lista():
    d = analisar_fluxos_em_andamento(_base_fluxos(), hoje=date(2026, 9, 4))
    r = resumir_por_responsavel(d, por="pessoa")
    # 3 pessoas em 2 etapas: a etapa com 2 revisores conta para cada um.
    assert set(r["Responsável"]) == {"Edson Mancini", "Gustavo Takehara", "Jefferson Mello"}
    jm = r.set_index("Responsável").loc["Jefferson Mello"]
    assert jm["Fluxos"] == 1 and jm["Atrasados"] == 1
    assert jm["Atraso Máx. (dias)"] == 15 and jm["% Atrasados"] == 100.0
    em = r.set_index("Responsável").loc["Edson Mancini"]
    assert em["Atrasados"] == 0 and em["Atraso Médio (dias)"] == 0


def test_resumo_por_pessoa_usa_a_organizacao_DA_PESSOA():
    """Etapa mista (Itaipu + CMI): cada um entra com a SUA organização.

    Antes o agrupamento usava a lista de organizações da ETAPA, e quem
    participava de etapas mistas aparecia duas vezes no resumo (visto na base
    real: Bianca/David/Luciana duplicados)."""
    d = analisar_fluxos_em_andamento(_base_fluxos(), hoje=date(2026, 9, 4))
    r = resumir_por_responsavel(d, por="pessoa")
    por_nome = r.set_index("Responsável")["Organização"].to_dict()
    assert por_nome["Edson Mancini"] == "ITAIPU BINACIONAL"
    assert por_nome["Gustavo Takehara"] == "CONSORCIO MODERNIZACAO ITAIPU"
    assert len(r) == r["Responsável"].nunique()      # ninguém fragmentado


def test_resumo_por_organizacao_nao_explode_pessoas():
    d = analisar_fluxos_em_andamento(_base_fluxos(), hoje=date(2026, 9, 4))
    r = resumir_por_responsavel(d, por="organizacao")
    ib = r.set_index("Responsável").loc["ITAIPU BINACIONAL"]
    assert ib["Fluxos"] == 2 and ib["Atrasados"] == 1   # 2 etapas, não 3 pessoas


def test_resumo_vazio():
    assert resumir_por_responsavel(pd.DataFrame()).empty


# ---------------------------------------------------------------------------
# Exportação
# ---------------------------------------------------------------------------
def test_export_tres_abas_e_semaforo(tmp_path):
    import openpyxl

    from docmanager.services.excel_io import exportar_fluxos_andamento
    d = analisar_fluxos_em_andamento(_base_fluxos(), hoje=date(2026, 9, 4))
    saida = tmp_path / "fluxos.xlsx"
    ok, _ = exportar_fluxos_andamento(d, resumir_por_responsavel(d, por="pessoa"),
                                      resumir_por_responsavel(d, por="organizacao"), str(saida))
    assert ok
    wb = openpyxl.load_workbook(saida)
    assert wb.sheetnames == ["Fluxos em Andamento", "Por Responsável", "Por Organização"]
    ws = wb["Fluxos em Andamento"]
    col_sit = [c.value for c in ws[1]].index("Situação") + 1
    assert ws.cell(2, col_sit).value == "Atrasado"
    assert str(ws.cell(2, col_sit).font.color.rgb).endswith("9C0006")   # vermelho
    assert str(ws.cell(2, col_sit).fill.fgColor.rgb).endswith("FFC7CE")


def test_export_vazio_avisa(tmp_path):
    from docmanager.services.excel_io import exportar_fluxos_andamento
    ok, msg = exportar_fluxos_andamento(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                                        str(tmp_path / "x.xlsx"))
    assert not ok and "Nenhum fluxo" in msg
