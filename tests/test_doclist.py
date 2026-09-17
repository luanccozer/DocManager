"""Módulo Doc List Mapping: consolidado de 3 sabores, hierarquia de 2 níveis,
planejamento vindo do Controle e a Análise por Período."""
from datetime import date

import openpyxl
import pandas as pd
import pytest
from builders import HistoricoBuilder, base, escrever_controle_xlsx

from docmanager.core.consolidation import calcula_status_consolidado
from docmanager.core.doclist import (
    COLUNAS_DOCLIST,
    SIT_CANCELADO,
    SIT_EMITIDO_COM_ATRASO,
    SIT_EMITIDO_NO_PRAZO,
    SIT_PENDENTE_NO_PRAZO,
    SIT_PENDENTE_VENCIDO,
    SIT_SEM_PLANEJAMENTO,
    LinhaDocList,
    calcular_dias_desvio_emissao,
    calcular_predecessores,
    calcular_resumo_quantidades,
    classificar_situacao_emissao,
    resolver_datas_doclist,
)
from docmanager.core.doclist_periodo import (
    analisar_periodo,
    janelas_padrao,
    listar_sem_data,
    resumo,
)
from docmanager.core.kpis import data_primeira_emissao
from docmanager.services.controle_docs import ler_controle
from docmanager.services.doclist_io import DocListSheet, ler_linhas_doclist
from docmanager.services.doclist_update import atualizar_doclist

HOJE = date(2026, 7, 27)


# ---------------------------------------------------------------------------
# Status consolidado — IGUAL ao do Mapa (§27.4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status_real,status_emissao,esperado", [
    ("Aprovado", "Aprovado", "APROVADO"),
    # Os três status de aprovação caem no MESMO balde: discretizar aqui só
    # replicaria a coluna STATUS REAL (decisão do usuário, 2026-07-28).
    ("Aprovado com Comentários", "Aprovado com Comentários", "APROVADO"),
    ("Para Assinatura", "Para Assinatura", "APROVADO"),
    ("Informativo", "Informativo", "APROVADO"),
    ("Não Aprovado", "Não Aprovado", "NÃO APROVADO"),
    ("Em Processo", "Em Processo", "EM PROCESSO"),
    ("Cancelado", "VOID", "CANCELADO"),
    ("NÃO EMITIDO", "", "NÃO EMITIDO"),
])
def test_consolidado_do_doclist(status_real, status_emissao, esperado):
    assert calcula_status_consolidado(status_real, status_emissao, "EMITIDO") == esperado


# ---------------------------------------------------------------------------
# Hierarquia de dois níveis (uma coluna PREDECESSOR)
# ---------------------------------------------------------------------------
def _linhas_hierarquia():
    return [
        LinhaDocList(row=2, cod_itaipu="SDSC UG FABRIC", nivel="1"),
        LinhaDocList(row=3, cod_itaipu="DOC-A", nivel="2", status_consolidado="APROVADO"),
        # 'Aprovado com Comentários' consolida como APROVADO (§27.4).
        LinhaDocList(row=4, cod_itaipu="DOC-B", nivel="2", status_consolidado="APROVADO"),
        LinhaDocList(row=5, cod_itaipu="SDSC UG MONTAG", nivel="1"),
        LinhaDocList(row=6, cod_itaipu="DOC-C", nivel="2", status_consolidado="NÃO EMITIDO"),
    ]


def test_predecessor_nivel1_aponta_para_si_e_nivel2_para_o_grupo():
    pred = calcular_predecessores(_linhas_hierarquia())
    assert pred[2] == "SDSC UG FABRIC"     # grupo aponta para si (decisão do usuário)
    assert pred[3] == "SDSC UG FABRIC"
    assert pred[4] == "SDSC UG FABRIC"
    assert pred[5] == "SDSC UG MONTAG"
    assert pred[6] == "SDSC UG MONTAG"     # troca de grupo


def test_resumo_quantidades_conta_por_grupo():
    """Os três status de aprovação entram num balde só, 'Aprovados' (§27.4)."""
    linhas = _linhas_hierarquia()
    resumo_txt = calcular_resumo_quantidades(linhas, calcular_predecessores(linhas))
    assert resumo_txt[2] == ("Total: 2\nAprovados: 2\nEm Processo: 0\n"
                             "Não Aprovados: 0\nNão Emitidos: 0")
    assert "Não Emitidos: 1" in resumo_txt[5]


def test_resumo_quantidades_mostra_cancelados_so_quando_existem():
    linhas = [LinhaDocList(row=2, cod_itaipu="G", nivel="1"),
              LinhaDocList(row=3, cod_itaipu="D1", nivel="2", status_consolidado="APROVADO")]
    assert "Cancelados" not in calcular_resumo_quantidades(
        linhas, calcular_predecessores(linhas))[2]
    linhas.append(LinhaDocList(row=4, cod_itaipu="D2", nivel="2",
                               status_consolidado="CANCELADO"))
    texto = calcular_resumo_quantidades(linhas, calcular_predecessores(linhas))[2]
    assert texto.startswith("Total: 2") and "Cancelados: 1" in texto


def test_resumo_quantidades_fecha_o_total_com_bucket_desconhecido():
    """Um consolidado inesperado não pode sumir: cai em 'Outros'."""
    linhas = [LinhaDocList(row=2, cod_itaipu="G", nivel="1"),
              LinhaDocList(row=3, cod_itaipu="D1", nivel="2", status_consolidado="ERRO")]
    texto = calcular_resumo_quantidades(linhas, calcular_predecessores(linhas))[2]
    assert texto.startswith("Total: 1")
    assert "Outros: 1" in texto


# ---------------------------------------------------------------------------
# Datas de planejamento
# ---------------------------------------------------------------------------
class _ControleFake:
    def __init__(self, linha, via="exato"):
        self._linha, self._via = linha, via

    def resolver(self, codigos, cod_itaipu_atual="", cod_cmi_atual="", **_kw):
        from docmanager.services.controle_docs import MatchControle
        return MatchControle(self._linha, self._via)


def _row_controle(prevista=None, reprog=None, fase="", titulo="t"):
    from docmanager.services.controle_docs import ControleRow
    return ControleRow(cod_itaipu="IT", cod_cmi="CMI", titulo=titulo,
                       data_prevista=prevista, data_reprogramada=reprog, fase=fase)


def _resolver(prevista_atual=None, reprogramada_atual=None, **kw_row):
    return resolver_datas_doclist(
        prevista_atual=prevista_atual, reprogramada_atual=reprogramada_atual,
        codigos=[], cod_itaipu_atual="IT", cod_cmi_atual="",
        controle=_ControleFake(_row_controle(**kw_row)))


def test_prevista_vence_a_mais_recente():
    """Divergência entre planilha e Controle → a data MAIS RECENTE ganha."""
    d = _resolver(prevista_atual=date(2026, 3, 1), prevista=date(2026, 9, 1))
    assert d.prevista == date(2026, 9, 1) and d.prevista_atualizada
    assert d.data_alvo == date(2026, 9, 1)


def test_prevista_da_planilha_mais_recente_e_preservada():
    d = _resolver(prevista_atual=date(2026, 9, 1), prevista=date(2026, 1, 1))
    assert d.prevista is None            # nada a escrever
    assert d.data_alvo == date(2026, 9, 1)


def test_reprogramada_manual_nunca_e_sobrescrita():
    d = _resolver(prevista_atual=None, reprogramada_atual=date(2026, 8, 8),
                  prevista=date(2026, 1, 1), reprog=date(2026, 5, 5))
    assert d.reprogramada is None                 # input manual manda
    assert d.data_alvo == date(2026, 8, 8)        # e é ela que vale


def test_data_alvo_prefere_reprogramada():
    d = _resolver(prevista=date(2026, 1, 1), reprog=date(2026, 5, 5))
    assert d.reprogramada == date(2026, 5, 5)
    assert d.data_alvo == date(2026, 5, 5)


def test_fase_do_controle_e_ignorada():
    """§27.3: FASE DE PROJETO virou input manual — o Controle não a fornece mais."""
    d = _resolver(fase="FABRICAÇÃO")
    assert not hasattr(d, "fase")


def test_titulo_do_controle_vem_junto_para_fallback():
    d = _resolver(titulo="LISTA DE DOCUMENTOS")
    assert d.titulo_controle == "LISTA DE DOCUMENTOS"


# ---------------------------------------------------------------------------
# Planilha: modelo, cabeçalho legado e ciclo completo
# ---------------------------------------------------------------------------
def _escrever_doclist(path, linhas, *, titulo_alvo="DATA-ALVO EMISSÃO"):
    """linhas: (grupo, sistema, cmi, itaipu, desc, nivel, prevista, reprog)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    titulos = [t if t != "DATA-ALVO EMISSÃO" else titulo_alvo for t in COLUNAS_DOCLIST.values()]
    ws.append(titulos)
    col = {t: i + 1 for i, t in enumerate(COLUNAS_DOCLIST.values())}
    for i, (grupo, sistema, cmi, itaipu, desc, nivel, prev, reprog) in enumerate(linhas, start=2):
        ws.cell(i, col["GRUPO"], grupo)
        ws.cell(i, col["SISTEMA"], sistema)
        ws.cell(i, col["Nº CMI"], cmi)
        ws.cell(i, col["N° ITAIPU"], itaipu)
        ws.cell(i, col["DESCRIÇÃO DO DOCUMENTO"], desc)
        ws.cell(i, col["NÍVEL"], nivel)
        if prev:
            ws.cell(i, col["DATA PREVISTA EMISSÃO"], prev)
        if reprog:
            ws.cell(i, col["DATA REPROGRAMADA"], reprog)
    wb.save(path)
    return path


def test_cabecalho_legado_trocar_e_reconhecido_e_renomeado(tmp_path):
    caminho = _escrever_doclist(tmp_path / "dl.xlsx",
                                [("UNIT", "SDSC", "CMI-1", "IT-1", "DOC", "2", None, None)],
                                titulo_alvo="TROCAR")
    wb = openpyxl.load_workbook(caminho)
    ds = DocListSheet(wb.active)
    assert ds.set_data("data_alvo", 2, date(2026, 1, 1))     # achou pela chave legada
    trocas = ds.renomear_cabecalhos_legados()
    assert ("TROCAR", "DATA-ALVO EMISSÃO") in trocas


def test_ciclo_completo_doclist(tmp_path):
    """Base + Controle + planilha → status, hierarquia, planejamento e resumo."""
    b = base(
        HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC APROVADO")
        .evento("0A", 1, "Em Processo", "01/03/2026")
        .evento("0A", 2, "Aprovado", "20/03/2026", current=True),
        HistoricoBuilder("T2", "#IT-2", "CMI-2", "DOC COM COMENTARIOS")
        .evento("0A", 1, "Aprovado com Comentários", "10/04/2026", current=True),
    )
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)

    path_ctrl = escrever_controle_xlsx(
        tmp_path / "ctrl.xlsx",
        [{"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "01-02-2026", "fase": "FABRICAÇÃO"},
         {"itaipu": "#IT-2", "cmi": "CMI-2", "prevista": "01-03-2026",
          "reprog": "9/15/2026", "fase": "MONTAGEM"},
         {"itaipu": "#IT-3", "cmi": "CMI-3", "prevista": "05-08-2026", "fase": "FABRICAÇÃO"}],
        incluir_fase=True)

    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", [
        ("UNIT", "SDSC - UG", "", "SDSC UG FABRIC", "DCS PENDING DOCUMENTS", "1", None, None),
        ("UNIT", "SDSC - UG", "CMI-1", "#IT-1", "DOC APROVADO", "2", None, None),
        ("UNIT", "SDSC - UG", "CMI-2", "#IT-2", "DOC COM COMENTARIOS", "2", None, None),
        ("UNIT", "SDSC - UG", "CMI-3", "#IT-3", "DOC NAO EMITIDO", "2", None, None),
    ])

    controle = ler_controle(path_ctrl, 0, log_cb=lambda _m: None)
    r = atualizar_doclist(path_base, path_dl, controle=controle, hoje=HOJE,
                          log_cb=lambda _m: None)
    assert r.ok, r.mensagem
    assert r.grupos == 1

    ws = openpyxl.load_workbook(path_dl).active
    col = {str(c.value): c.column for c in ws[1]}

    def val(row, titulo):
        return ws.cell(row, col[titulo]).value

    # Grupo (nível 1): não é documento, mas recebe o resumo.
    assert val(2, "STATUS CONSOLIDADO") == "NÃO EMITIDO"
    assert val(2, "PREDECESSOR") == "SDSC UG FABRIC"
    assert val(2, "RESUMO QUANTIDADES").startswith("Total: 3")
    assert "Aprovados: 2" in val(2, "RESUMO QUANTIDADES")   # Aprovado + c/ Comentários
    assert "Não Emitidos: 1" in val(2, "RESUMO QUANTIDADES")

    # Consolidado: um balde só para aprovação; o detalhe fica em STATUS REAL.
    assert val(3, "STATUS REAL") == "Aprovado"
    assert val(3, "STATUS CONSOLIDADO") == "APROVADO"
    assert val(4, "STATUS REAL") == "Aprovado com Comentários"
    assert val(4, "STATUS CONSOLIDADO") == "APROVADO"
    assert val(5, "STATUS CONSOLIDADO") == "NÃO EMITIDO"
    assert val(5, "PREDECESSOR") == "SDSC UG FABRIC"

    # Data de emissão vem do Aconex como data NATIVA (o dashboard precisa).
    assert val(3, "DATA ÚLTIMA EMISSÃO").date() == date(2026, 3, 20)
    assert val(3, "ÚLTIMA REV. EMITIDA") == "0A"

    # FASE DE PROJETO é input manual (§27.3): o Controle tem 'FABRICAÇÃO', a
    # planilha não — e continua não tendo.
    assert val(3, "FASE DE PROJETO") is None

    # Planejamento: datas nativas e a data-alvo (reprogramada > prevista).
    assert val(3, "DATA PREVISTA EMISSÃO").date() == date(2026, 2, 1)
    assert val(3, "DATA-ALVO EMISSÃO").date() == date(2026, 2, 1)
    assert val(4, "DATA REPROGRAMADA").date() == date(2026, 9, 15)
    assert val(4, "DATA-ALVO EMISSÃO").date() == date(2026, 9, 15)
    # Documento fora do Aconex TAMBÉM recebe a data do Controle (§27/§24.12).
    assert val(5, "DATA PREVISTA EMISSÃO").date() == date(2026, 8, 5)
    assert val(5, "DATA-ALVO EMISSÃO").date() == date(2026, 8, 5)


def test_descricao_segue_prioridade_aconex_controle_planilha(tmp_path):
    """§27.3: prioridade Aconex > Controle > planilha. O título do Controle
    SOBRESCREVE a descrição digitada à mão (que costuma ser genérica); só quem
    está no Aconex mantém a descrição de lá."""
    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "TITULO DO ACONEX")
             .evento("0A", 1, "Em Processo", "01/03/2026", current=True))
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)

    path_ctrl = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "#IT-1", "cmi": "CMI-1", "titulo": "TITULO DO CONTROLE", "prevista": "01-02-2026"},
        {"itaipu": "#IT-2", "cmi": "CMI-2", "titulo": "DOC PREVISTO SEM EMISSAO", "prevista": "05-08-2026"},
        {"itaipu": "#IT-3", "cmi": "CMI-3", "titulo": "TITULO DO CONTROLE", "prevista": "05-08-2026"},
    ])
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", [
        ("UNIT", "SDSC", "", "GRUPO-1", "AGRUPAMENTO", "1", None, None),
        ("UNIT", "SDSC", "CMI-1", "#IT-1", "", "2", None, None),   # no Aconex, sem descrição
        ("UNIT", "SDSC", "CMI-2", "#IT-2", "", "2", None, None),   # fora do Aconex, sem descrição
        ("UNIT", "SDSC", "CMI-3", "#IT-3", "DESCRICAO JA ESCRITA", "2", None, None),
    ])
    controle = ler_controle(path_ctrl, 0, log_cb=lambda _m: None)
    logs = []
    assert atualizar_doclist(path_base, path_dl, controle=controle, hoje=HOJE,
                             log_cb=logs.append).ok

    ws = openpyxl.load_workbook(path_dl).active
    col = {str(c.value): c.column for c in ws[1]}
    desc = lambda row: ws.cell(row, col["DESCRIÇÃO DO DOCUMENTO"]).value  # noqa: E731
    assert desc(3) == "TITULO DO ACONEX"          # está no Aconex → Aconex manda
    assert desc(4) == "DOC PREVISTO SEM EMISSAO"  # fora do Aconex, vazia → Controle
    assert desc(5) == "TITULO DO CONTROLE"        # fora do Aconex → Controle SOBRESCREVE
    assert any("2 descrições vindas do título do Controle" in m for m in logs)


def test_analise_por_periodo(tmp_path):
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", [
        ("UNIT", "SDSC", "", "GRUPO-1", "AGRUPAMENTO", "1", None, None),
        ("UNIT", "SDSC", "CMI-1", "IT-1", "VENCIDO", "2", date(2026, 1, 10), None),
        ("UNIT", "SDSC", "CMI-2", "IT-2", "PROXIMO", "2", date(2026, 8, 10), None),
        ("UNIT", "SDSC", "CMI-3", "IT-3", "REPROGRAMADO", "2", date(2026, 2, 1), date(2026, 8, 20)),
        ("UNIT", "SDSC", "CMI-4", "IT-4", "LONGE", "2", date(2027, 5, 1), None),
        ("UNIT", "SDSC", "CMI-5", "IT-5", "SEM DATA", "2", None, None),
    ])
    linhas = ler_linhas_doclist(path_dl)

    proximos = analisar_periodo(linhas, inicio=HOJE, fim=date(2026, 8, 31), hoje=HOJE)
    assert [i.cod_itaipu for i in proximos] == ["IT-2", "IT-3"]
    assert proximos[1].origem == "Reprogramada"     # a data-alvo veio da reprogramação
    assert proximos[0].dias == 14

    vencidos = analisar_periodo(linhas, inicio=None, fim=date(2026, 7, 26), hoje=HOJE)
    assert [i.cod_itaipu for i in vencidos] == ["IT-1"]
    assert vencidos[0].situacao == "Vencido"

    # O agrupamento (nível 1) nunca entra; o sem-data sai numa lista própria.
    assert all(i.cod_itaipu != "GRUPO-1" for i in analisar_periodo(
        linhas, inicio=None, fim=None, hoje=HOJE))
    assert [ln.cod_itaipu for ln in listar_sem_data(linhas)] == ["IT-5"]

    dados = resumo(analisar_periodo(linhas, inicio=None, fim=None, hoje=HOJE))
    assert dados["total"] == 4 and dados["vencidos"] == 1 and dados["reprogramados"] == 1


def test_janelas_padrao_cobrem_hoje():
    janelas = {j.rotulo: j for j in janelas_padrao(HOJE)}
    assert janelas["Próximos 30 dias"].contem(HOJE)
    assert not janelas["Vencidos (não emitidos)"].contem(HOJE)
    assert janelas["Mês que vem"].inicio == date(2026, 8, 1)
    assert janelas["Mês que vem"].fim == date(2026, 8, 31)


# ---------------------------------------------------------------------------
# Situação de emissão — aderência ao planejamento (§27.5)
# ---------------------------------------------------------------------------
ALVO = date(2026, 3, 10)


def _hist(*eventos, terminated_em=()):
    """Histórico de UM documento. eventos: (rev, versao, status, 'dd/mm/aaaa')."""
    b = HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC")
    for i, (rev, versao, status, data) in enumerate(eventos):
        b.evento(rev, versao, status, data,
                 current=(i == len(eventos) - 1),
                 terminated=(i in terminated_em))
    return b.build()


def test_primeira_emissao_e_o_em_processo_da_0a():
    df = _hist(("0A", 1, "Em Processo", "05/03/2026"),
               ("0A", 2, "Aprovado", "20/03/2026"))
    assert data_primeira_emissao(df) == date(2026, 3, 5)


def test_regua_e_a_primeira_emissao_nao_a_ultima():
    """O teste que justifica a coluna: 0A no prazo, 0F meses depois.

    Usar DATA ÚLTIMA EMISSÃO como régua acusaria 9 meses de atraso num
    documento que nasceu adiantado — 0A→0F é ciclo normal de aprovação.
    """
    df = _hist(("0A", 1, "Em Processo", "05/03/2026"),
               ("0A", 2, "Não Aprovado", "01/04/2026"),
               ("0F", 1, "Em Processo", "10/12/2026"),
               ("0F", 2, "Aprovado", "20/12/2026"))
    assert data_primeira_emissao(df) == date(2026, 3, 5)
    assert classificar_situacao_emissao(
        data_primeira_emissao=data_primeira_emissao(df), data_alvo=ALVO,
        status_consolidado="APROVADO", hoje=HOJE) == SIT_EMITIDO_NO_PRAZO


def test_reenvio_da_mesma_revisao_manda_a_data_mais_recente():
    """Decisão do usuário (2026-09-16): o reenvio corrigiu a entrega anterior."""
    df = _hist(("0A", 1, "Em Processo", "05/03/2026"),
               ("0A", 2, "Em Processo", "12/03/2026"))
    assert data_primeira_emissao(df) == date(2026, 3, 12)


def test_sem_0a_vale_a_emissao_mais_antiga_documento_sat():
    """Documento SAT/legado: continua um doc antigo da Itaipu e já entra alto."""
    df = _hist(("0C", 1, "Em Processo", "05/03/2026"),
               ("0D", 1, "Em Processo", "20/05/2026"))
    assert data_primeira_emissao(df) == date(2026, 3, 5)


def test_0a_vence_mesmo_fora_de_ordem_cronologica():
    df = _hist(("0B", 1, "Em Processo", "01/03/2026"),
               ("0A", 1, "Em Processo", "05/03/2026"))
    assert data_primeira_emissao(df) == date(2026, 3, 5)


def test_ciclo_interno_0aa_nao_conta_como_emissao():
    """Revisões de len > 2 são ciclo interno da CMI, não entrega à Itaipu."""
    df = _hist(("0AA", 1, "Em Processo", "01/02/2026"),
               ("0A", 1, "Em Processo", "05/03/2026"))
    assert data_primeira_emissao(df) == date(2026, 3, 5)


def test_revisao_sem_em_processo_e_ruido():
    df = _hist(("0A", 1, "Aprovado", "05/03/2026"))
    assert data_primeira_emissao(df) is None


def test_0a_terminada_sem_renascimento_nao_conta():
    df = _hist(("0A", 1, "Em Processo", "05/03/2026"), terminated_em=(0,))
    assert data_primeira_emissao(df) is None


def test_0a_terminada_que_renasceu_conta_a_versao_sobrevivente():
    df = _hist(("0A", 1, "Em Processo", "05/03/2026"),
               ("0A", 2, "Em Processo", "18/03/2026"), terminated_em=(0,))
    assert data_primeira_emissao(df) == date(2026, 3, 18)


def test_documento_sem_historico_nao_tem_primeira_emissao():
    assert data_primeira_emissao(pd.DataFrame()) is None


@pytest.mark.parametrize("emissao,alvo,consolidado,esperado", [
    (date(2026, 3, 5), ALVO, "APROVADO", SIT_EMITIDO_NO_PRAZO),
    (ALVO, ALVO, "APROVADO", SIT_EMITIDO_NO_PRAZO),          # no dia = no prazo
    (date(2026, 3, 11), ALVO, "APROVADO", SIT_EMITIDO_COM_ATRASO),
    (None, date(2026, 12, 1), "NÃO EMITIDO", SIT_PENDENTE_NO_PRAZO),
    (None, HOJE, "NÃO EMITIDO", SIT_PENDENTE_NO_PRAZO),      # vence hoje, ainda dá
    (None, ALVO, "NÃO EMITIDO", SIT_PENDENTE_VENCIDO),
    (None, None, "NÃO EMITIDO", SIT_SEM_PLANEJAMENTO),
    (date(2026, 3, 5), None, "APROVADO", SIT_SEM_PLANEJAMENTO),
    # CANCELADO é terminal e vence tudo — sai do gráfico por filtro do visual.
    (date(2026, 3, 5), ALVO, "CANCELADO", SIT_CANCELADO),
    (None, None, "CANCELADO", SIT_CANCELADO),
])
def test_classificar_situacao_emissao(emissao, alvo, consolidado, esperado):
    assert classificar_situacao_emissao(
        data_primeira_emissao=emissao, data_alvo=alvo,
        status_consolidado=consolidado, hoje=HOJE) == esperado


@pytest.mark.parametrize("emissao,alvo,esperado", [
    (date(2026, 3, 5), ALVO, -5),     # adiantado
    (ALVO, ALVO, 0),
    (date(2026, 3, 20), ALVO, 10),    # atrasado
    (None, ALVO, None),
    (date(2026, 3, 5), None, None),
])
def test_dias_desvio_emissao(emissao, alvo, esperado):
    assert calcular_dias_desvio_emissao(emissao, alvo) == esperado


def test_ciclo_completo_grava_situacao_emissao(tmp_path):
    """Planilha real: as três colunas saem preenchidas e com o TIPO certo."""
    b = base(
        # Nasceu 01/03 para um alvo de 01/02 → atrasado, apesar de aprovado.
        HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC ATRASADO")
        .evento("0A", 1, "Em Processo", "01/03/2026")
        .evento("0A", 2, "Aprovado", "20/03/2026", current=True),
        # Nasceu 10/01 para um alvo de 01/02 → no prazo, mesmo com 0B depois.
        HistoricoBuilder("T2", "#IT-2", "CMI-2", "DOC NO PRAZO")
        .evento("0A", 1, "Em Processo", "10/01/2026")
        .evento("0A", 2, "Não Aprovado", "15/02/2026")
        .evento("0B", 1, "Em Processo", "01/06/2026", current=True),
    )
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)

    path_ctrl = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "01-02-2026"},
        {"itaipu": "#IT-2", "cmi": "CMI-2", "prevista": "01-02-2026"},
        {"itaipu": "#IT-3", "cmi": "CMI-3", "prevista": "05-08-2026"},   # futuro
        {"itaipu": "#IT-4", "cmi": "CMI-4", "prevista": "05-01-2026"},   # vencido
    ])
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", [
        ("UNIT", "SDSC - UG", "", "GRUPO-1", "AGRUPAMENTO", "1", None, None),
        ("UNIT", "SDSC - UG", "CMI-1", "#IT-1", "DOC ATRASADO", "2", None, None),
        ("UNIT", "SDSC - UG", "CMI-2", "#IT-2", "DOC NO PRAZO", "2", None, None),
        ("UNIT", "SDSC - UG", "CMI-3", "#IT-3", "DOC PENDENTE", "2", None, None),
        ("UNIT", "SDSC - UG", "CMI-4", "#IT-4", "DOC VENCIDO", "2", None, None),
    ])

    controle = ler_controle(path_ctrl, 0, log_cb=lambda _m: None)
    r = atualizar_doclist(path_base, path_dl, controle=controle, hoje=HOJE,
                          log_cb=lambda _m: None)
    assert r.ok, r.mensagem

    ws = openpyxl.load_workbook(path_dl).active
    col = {str(c.value): c.column for c in ws[1]}

    def val(row, titulo):
        return ws.cell(row, col[titulo]).value

    assert val(3, "SITUAÇÃO EMISSÃO") == SIT_EMITIDO_COM_ATRASO
    assert val(4, "SITUAÇÃO EMISSÃO") == SIT_EMITIDO_NO_PRAZO
    assert val(5, "SITUAÇÃO EMISSÃO") == SIT_PENDENTE_NO_PRAZO
    assert val(6, "SITUAÇÃO EMISSÃO") == SIT_PENDENTE_VENCIDO

    # DATA 1ª EMISSÃO é data NATIVA (o dashboard precisa agrupar por período).
    assert val(3, "DATA 1ª EMISSÃO").date() == date(2026, 3, 1)
    assert val(4, "DATA 1ª EMISSÃO").date() == date(2026, 1, 10)
    assert val(5, "DATA 1ª EMISSÃO") is None

    # DIAS DESVIO é NÚMERO, não texto — negativo = adiantado.
    assert val(3, "DIAS DESVIO EMISSÃO") == 28      # 01/03 vs 01/02
    assert val(4, "DIAS DESVIO EMISSÃO") == -22     # 10/01 vs 01/02
    assert val(5, "DIAS DESVIO EMISSÃO") is None

    # Agrupamento (nível 1) não é documento: bloco vazio, não polui a legenda.
    assert val(2, "SITUAÇÃO EMISSÃO") is None
    assert val(2, "DATA 1ª EMISSÃO") is None


def test_planilha_sem_as_colunas_novas_continua_rodando(tmp_path):
    """Retrocompatibilidade: quem não criou as colunas só recebe um aviso."""
    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC")
             .evento("0A", 1, "Em Processo", "01/03/2026")
             .evento("0A", 2, "Aprovado", "20/03/2026", current=True))
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)

    # Cabeçalho SEM as três colunas novas.
    novas = {"DATA 1ª EMISSÃO", "SITUAÇÃO EMISSÃO", "DIAS DESVIO EMISSÃO"}
    titulos = [t for t in COLUNAS_DOCLIST.values() if t not in novas]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(titulos)
    col = {t: i + 1 for i, t in enumerate(titulos)}
    ws.cell(2, col["N° ITAIPU"], "#IT-1")
    ws.cell(2, col["Nº CMI"], "CMI-1")
    ws.cell(2, col["NÍVEL"], "2")
    path_dl = tmp_path / "dl_antiga.xlsx"
    wb.save(path_dl)

    logs = []
    r = atualizar_doclist(path_base, path_dl, hoje=HOJE, log_cb=logs.append)
    assert r.ok, r.mensagem
    assert any("SITUAÇÃO EMISSÃO" in m for m in logs if "não encontradas" in m)

    ws = openpyxl.load_workbook(path_dl).active
    col = {str(c.value): c.column for c in ws[1]}
    assert ws.cell(2, col["STATUS CONSOLIDADO"]).value == "APROVADO"
