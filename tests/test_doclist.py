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
    classificar_situacao_say_do,
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
from docmanager.services.sobrescricao import ABA_RECUSAS, DecisaoSobrescricao

HOJE = date(2026, 7, 27)


# ---------------------------------------------------------------------------
# Status consolidado - IGUAL ao do Mapa (§27.4)
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


def _resolver(prevista_atual=None, reprogramada_atual=None, aceitas=frozenset(), **kw_row):
    return resolver_datas_doclist(
        prevista_atual=prevista_atual, reprogramada_atual=reprogramada_atual,
        codigos=[], cod_itaipu_atual="IT", cod_cmi_atual="",
        controle=_ControleFake(_row_controle(**kw_row)), aceitas=aceitas)


def _incidencias(d):
    return [(i.coluna, i.valor_planilha, i.data_controle) for i in d.incidencias]


def test_prevista_preenchida_nao_e_trocada_e_vira_incidencia():
    """ADR 0001: a DATA PREVISTA é a baseline. O Controle replanejou para frente,
    mas a troca só acontece com aceite - até lá, é uma incidência."""
    d = _resolver(prevista_atual=date(2026, 3, 1), prevista=date(2026, 9, 1))
    assert d.prevista is None                     # nada a escrever
    assert d.data_alvo == date(2026, 3, 1)
    assert _incidencias(d) == [("prevista", date(2026, 3, 1), date(2026, 9, 1))]


def test_prevista_da_planilha_mais_recente_tambem_vira_incidencia():
    d = _resolver(prevista_atual=date(2026, 9, 1), prevista=date(2026, 1, 1))
    assert d.prevista is None
    assert d.data_alvo == date(2026, 9, 1)
    assert _incidencias(d) == [("prevista", date(2026, 9, 1), date(2026, 1, 1))]


def test_reprogramada_manual_nunca_e_sobrescrita():
    d = _resolver(prevista_atual=None, reprogramada_atual=date(2026, 8, 8),
                  prevista=date(2026, 1, 1), reprog=date(2026, 5, 5))
    assert d.reprogramada is None                 # input manual manda
    assert d.prevista == date(2026, 1, 1)         # a vazia é preenchida
    assert d.data_alvo == date(2026, 8, 8)        # e é a manual que vale
    assert _incidencias(d) == [("reprogramada", date(2026, 8, 8), date(2026, 5, 5))]


def test_incidencia_aceita_troca_a_prevista():
    d = _resolver(prevista_atual=date(2026, 3, 1), prevista=date(2026, 9, 1),
                  aceitas=frozenset({"prevista"}))
    assert d.prevista == date(2026, 9, 1)
    assert d.data_alvo == date(2026, 9, 1)


def test_data_alvo_prefere_reprogramada():
    d = _resolver(prevista=date(2026, 1, 1), reprog=date(2026, 5, 5))
    assert d.reprogramada == date(2026, 5, 5)
    assert d.data_alvo == date(2026, 5, 5)


def test_fase_do_controle_e_ignorada():
    """§27.3: FASE DE PROJETO virou input manual - o Controle não a fornece mais."""
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
    # planilha não - e continua não tendo.
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
# Situação de emissão - aderência ao planejamento (§27.5)
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
    documento que nasceu adiantado - 0A→0F é ciclo normal de aprovação.
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


# Corte de 19/08/2024 (KB §7): antes dele a submissão à Itaipu era 'Para Análise' e
# 'Em Processo' era trâmite interno da CMI. Documento emitido no regime antigo não
# pode ganhar a data de uma reemissão posterior (achado do painel da UG, 2026-11-11).
def test_antes_do_corte_o_envio_era_para_analise():
    df = _hist(("0A", 1, "Para Análise", "06/10/2023"),
               ("0A", 2, "Não Aprovado", "20/11/2023"),
               ("0B", 1, "Para Análise", "10/01/2024"),
               ("0B", 2, "Aprovado com Comentários", "05/02/2024"),
               ("0C", 1, "Em Processo", "21/03/2025"))
    assert data_primeira_emissao(df) == date(2023, 10, 6)


def test_em_processo_antes_do_corte_e_tramite_interno():
    df = _hist(("0A", 1, "Em Processo", "01/10/2023"),
               ("0A", 2, "Para Análise", "06/10/2023"))
    assert data_primeira_emissao(df) == date(2023, 10, 6)


def test_emitido_so_no_regime_antigo_tem_primeira_emissao():
    """Sem nenhum 'Em Processo' depois do corte o documento aparecia como pendente."""
    df = _hist(("0A", 1, "Para Análise", "06/10/2023"),
               ("0A", 2, "Para Assinatura", "30/10/2023"),
               ("0", 1, "Aprovado", "15/12/2023"))
    assert data_primeira_emissao(df) == date(2023, 10, 6)


def test_no_dia_do_corte_vale_o_regime_novo():
    """19/08/2024 já é regime novo: 'Para Análise' é espelho; 'Em Processo' é envio."""
    df = _hist(("0A", 1, "Para Análise", "19/08/2024"),
               ("0A", 2, "Em Processo", "20/08/2024"))
    assert data_primeira_emissao(df) == date(2024, 8, 20)
    df = _hist(("0A", 1, "Em Processo", "19/08/2024"))
    assert data_primeira_emissao(df) == date(2024, 8, 19)


@pytest.mark.parametrize("emissao,alvo,consolidado,esperado", [
    (date(2026, 3, 5), ALVO, "APROVADO", SIT_EMITIDO_NO_PRAZO),
    (ALVO, ALVO, "APROVADO", SIT_EMITIDO_NO_PRAZO),          # no dia = no prazo
    (date(2026, 3, 11), ALVO, "APROVADO", SIT_EMITIDO_COM_ATRASO),
    (None, date(2026, 12, 1), "NÃO EMITIDO", SIT_PENDENTE_NO_PRAZO),
    (None, HOJE, "NÃO EMITIDO", SIT_PENDENTE_NO_PRAZO),      # vence hoje, ainda dá
    (None, ALVO, "NÃO EMITIDO", SIT_PENDENTE_VENCIDO),
    (None, None, "NÃO EMITIDO", SIT_SEM_PLANEJAMENTO),
    (date(2026, 3, 5), None, "APROVADO", SIT_SEM_PLANEJAMENTO),
    # CANCELADO é terminal e vence tudo - sai do gráfico por filtro do visual.
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

    # DIAS DESVIO é NÚMERO, não texto - negativo = adiantado.
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


# ---------------------------------------------------------------------------
# Datas como DATA do Excel - o que o Power BI precisa (pedido de 2026-09-30)
# ---------------------------------------------------------------------------
# numFmtId 14 do Excel ("Data abreviada"): categoria "Data" no Formatar Células,
# exibida no padrão do Windows. O "DD/MM/YYYY" antigo aparecia como
# "Personalizado".
FORMATO_DATA_EXCEL = "mm-dd-yy"
COLUNAS_DE_DATA = ("DATA PREVISTA EMISSÃO", "DATA REPROGRAMADA", "DATA-ALVO EMISSÃO",
                   "DATA ÚLTIMA EMISSÃO", "DATA 1ª EMISSÃO")


def _rodar_doclist(tmp_path, linhas, *, preparar=None, controle=None):
    """Base mínima + Doc List → (planilha relida, logs). `preparar(ws, col)`
    mexe nas células antes da atualização (texto, formato antigo...)."""
    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC APROVADO")
             .evento("0A", 1, "Em Processo", "01/03/2026")
             .evento("0A", 2, "Aprovado", "20/03/2026", current=True))
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", linhas)
    if preparar is not None:
        wb = openpyxl.load_workbook(path_dl)
        ws = wb.active
        preparar(ws, {str(c.value): c.column for c in ws[1]})
        wb.save(path_dl)
    logs: list[str] = []
    r = atualizar_doclist(path_base, path_dl, controle=controle, hoje=HOJE, log_cb=logs.append)
    assert r.ok, r.mensagem
    ws = openpyxl.load_workbook(path_dl).active
    return ws, {str(c.value): c.column for c in ws[1]}, logs


def test_datas_gravadas_no_formato_de_data_do_excel(tmp_path):
    path_ctrl = escrever_controle_xlsx(
        tmp_path / "ctrl.xlsx",
        [{"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "01-02-2026", "reprog": "9/15/2026"}])
    ws, col, _ = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC APROVADO", "2", None, None)],
        controle=ler_controle(path_ctrl, 0, log_cb=lambda _m: None))
    for titulo in COLUNAS_DE_DATA:
        cell = ws.cell(2, col[titulo])
        assert cell.number_format == FORMATO_DATA_EXCEL, titulo
        assert cell.is_date, titulo
        assert cell.value.time() == pd.Timestamp(0).time(), titulo   # sem hora
    assert ws.cell(2, col["DATA-ALVO EMISSÃO"]).value.date() == date(2026, 9, 15)


def test_planilha_antiga_com_formato_personalizado_e_corrigida(tmp_path):
    """Quem já rodou a v3.1.0 tem as células no formato personalizado - uma
    atualização basta para trocá-las, inclusive as digitadas à mão."""
    def preparar(ws, col):
        for titulo in ("DATA PREVISTA EMISSÃO", "DATA REPROGRAMADA"):
            ws.cell(2, col[titulo]).number_format = "DD/MM/YYYY"

    ws, col, _ = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2",
                    date(2026, 5, 4), date(2026, 6, 7))], preparar=preparar)
    for titulo in ("DATA PREVISTA EMISSÃO", "DATA REPROGRAMADA", "DATA-ALVO EMISSÃO"):
        assert ws.cell(2, col[titulo]).number_format == FORMATO_DATA_EXCEL, titulo
    assert ws.cell(2, col["DATA-ALVO EMISSÃO"]).value.date() == date(2026, 6, 7)


def test_data_digitada_como_texto_vira_data(tmp_path):
    ws, col, logs = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", "15/10/2026", " 20/11/2026 ")])
    for titulo, esperado in (("DATA PREVISTA EMISSÃO", date(2026, 10, 15)),
                             ("DATA REPROGRAMADA", date(2026, 11, 20)),
                             ("DATA-ALVO EMISSÃO", date(2026, 11, 20))):
        cell = ws.cell(2, col[titulo])
        assert cell.is_date and cell.value.date() == esperado, titulo
        assert cell.number_format == FORMATO_DATA_EXCEL, titulo
    assert not any("texto nas colunas de data" in m for m in logs)


def test_texto_que_nao_e_data_fica_e_e_avisado(tmp_path):
    """'A DEFINIR' é input de alguém: não some, mas o log diz onde está - é
    ele que impede o Power BI de ler a coluna como data."""
    ws, col, logs = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", "A DEFINIR", None)])
    assert ws.cell(2, col["DATA PREVISTA EMISSÃO"]).value == "A DEFINIR"
    assert ws.cell(2, col["DATA-ALVO EMISSÃO"]).value is None
    aviso = [m for m in logs if "texto nas colunas de data" in m]
    assert aviso and "DATA PREVISTA EMISSÃO linha 2: 'A DEFINIR'" in aviso[0]


def test_formula_na_coluna_de_data_nao_e_mexida(tmp_path):
    def preparar(ws, col):
        ws.cell(2, col["DATA REPROGRAMADA"]).value = "=DATE(2026,12,1)"

    ws, col, logs = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", None, None)], preparar=preparar)
    assert ws.cell(2, col["DATA REPROGRAMADA"]).value == "=DATE(2026,12,1)"
    assert not any("texto nas colunas de data" in m for m in logs)


def test_grupo_fica_sem_data_alvo(tmp_path):
    """A célula do grupo nunca era reescrita e podia guardar texto (ex.: sobra
    da antiga coluna TROCAR) no meio da coluna de data."""
    def preparar(ws, col):
        ws.cell(2, col["DATA-ALVO EMISSÃO"]).value = "VER ABA 2"

    ws, col, _ = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "", "GRUPO-1", "AGRUPAMENTO", "1", None, None),
                   ("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", date(2026, 8, 1), None)],
        preparar=preparar)
    assert ws.cell(2, col["DATA-ALVO EMISSÃO"]).value is None
    assert ws.cell(3, col["DATA-ALVO EMISSÃO"]).value.date() == date(2026, 8, 1)


def test_exportacao_da_analise_por_periodo_usa_o_formato_de_data(tmp_path):
    from docmanager.services.doclist_io import exportar_analise_periodo

    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", [
        ("UNIT", "SDSC", "CMI-1", "IT-1", "PROXIMO", "2", date(2026, 8, 10), None)])
    itens = analisar_periodo(ler_linhas_doclist(path_dl), inicio=None, fim=None, hoje=HOJE)
    saida = tmp_path / "periodo.xlsx"
    ok, _ = exportar_analise_periodo(itens, resumo(itens), saida, titulo_janela="Tudo", hoje=HOJE)
    assert ok
    ws = openpyxl.load_workbook(saida).active
    celulas = [c for linha in ws.iter_rows() for c in linha if c.is_date]
    assert celulas and all(c.number_format == FORMATO_DATA_EXCEL for c in celulas)


# ---------------------------------------------------------------------------
# Data prevista congelada e incidências (ADR 0001, pedido de 2026-10-28)
# ---------------------------------------------------------------------------
def _controle_xlsx(tmp_path, prevista="", reprog=""):
    p = escrever_controle_xlsx(tmp_path / "ctrl.xlsx",
                               [{"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": prevista, "reprog": reprog}])
    return ler_controle(p, 0, log_cb=lambda _m: None)


def _valor_data(ws, col, titulo):
    v = ws.cell(2, col[titulo]).value
    return v.date() if hasattr(v, "date") else v


def test_data_prevista_preenchida_nao_e_trocada_pelo_controle_e_vai_para_o_log(tmp_path):
    def preparar(ws, col):
        ws.cell(2, col["DATA PREVISTA EMISSÃO"]).value = date(2026, 3, 1)

    ws, col, logs = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", None, None)],
        preparar=preparar, controle=_controle_xlsx(tmp_path, prevista="01-09-2026"))
    assert _valor_data(ws, col, "DATA PREVISTA EMISSÃO") == date(2026, 3, 1)
    assert _valor_data(ws, col, "DATA-ALVO EMISSÃO") == date(2026, 3, 1)
    texto = "\n".join(logs)
    assert "1 data preenchida que o Controle trocaria ficou como está" in texto
    assert "#IT-1" in texto and "01/03/2026 → 01/09/2026" in texto


def test_texto_na_reprogramada_nao_e_apagado_pelo_controle(tmp_path):
    """Até a v3.6 o Controle escrevia por cima de 'A DEFINIR' sem avisar."""
    def preparar(ws, col):
        ws.cell(2, col["DATA REPROGRAMADA"]).value = "A DEFINIR"

    ws, col, logs = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", date(2026, 2, 1), None)],
        preparar=preparar, controle=_controle_xlsx(tmp_path, prevista="01-02-2026", reprog="15/12/2026"))
    assert ws.cell(2, col["DATA REPROGRAMADA"]).value == "A DEFINIR"
    assert _valor_data(ws, col, "DATA-ALVO EMISSÃO") == date(2026, 2, 1)
    assert any("'A DEFINIR' → 15/12/2026" in m for m in logs)


def test_celula_de_data_vazia_continua_recebendo_a_data_do_controle(tmp_path):
    ws, col, logs = _rodar_doclist(
        tmp_path, [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", None, None)],
        controle=_controle_xlsx(tmp_path, prevista="01-02-2026", reprog="15/12/2026"))
    assert _valor_data(ws, col, "DATA PREVISTA EMISSÃO") == date(2026, 2, 1)
    assert _valor_data(ws, col, "DATA REPROGRAMADA") == date(2026, 12, 15)
    assert not any("o Controle trocaria" in m for m in logs)


# ---------------------------------------------------------------------------
# Decisão das incidências e aba de recusas (ADR 0001)
# ---------------------------------------------------------------------------
class _Decisor:
    """Faz o papel da tela: anota o que recebeu e devolve a decisão pedida."""

    def __init__(self, decidir):
        self.decidir = decidir
        self.chamadas: list[list] = []

    def __call__(self, pendentes):
        self.chamadas.append(list(pendentes))
        return self.decidir(pendentes)


def _preparar_planilha(tmp_path, *, prevista=date(2026, 3, 1), reprog=None):
    """Base + Doc List com um documento já planejado; devolve os caminhos."""
    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC")
             .evento("0A", 1, "Em Processo", "01/03/2026")
             .evento("0A", 2, "Aprovado", "20/03/2026", current=True))
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx",
                                [("UNIT", "SDSC", "CMI-1", "#IT-1", "DOC", "2", prevista, reprog)])
    return path_base, path_dl


def _atualizar(path_base, path_dl, controle, decisor, logs=None):
    r = atualizar_doclist(path_base, path_dl, controle=controle, hoje=HOJE,
                          log_cb=(logs.append if logs is not None else lambda _m: None),
                          decidir_cb=decisor)
    assert r.ok, r.mensagem
    wb = openpyxl.load_workbook(path_dl)
    ws = wb.active
    return wb, ws, {str(c.value): c.column for c in ws[1]}


def _data(ws, col, titulo, row=2):
    v = ws.cell(row, col[titulo]).value
    return v.date() if hasattr(v, "date") else v


def test_aceitar_troca_a_data_e_a_data_alvo_acompanha(tmp_path):
    path_base, path_dl = _preparar_planilha(tmp_path)
    decisor = _Decisor(lambda p: DecisaoSobrescricao.aceitar_todas(len(p)))
    wb, ws, col = _atualizar(path_base, path_dl, _controle_xlsx(tmp_path, prevista="01-09-2026"), decisor)

    assert [(i.codigo, i.coluna, i.data_controle) for i in decisor.chamadas[0]] == \
        [("#IT-1", "prevista", date(2026, 9, 1))]
    assert _data(ws, col, "DATA PREVISTA EMISSÃO") == date(2026, 9, 1)
    assert _data(ws, col, "DATA-ALVO EMISSÃO") == date(2026, 9, 1)
    assert ABA_RECUSAS not in wb.sheetnames


def test_recusa_fica_anotada_na_aba_e_nao_e_perguntada_de_novo(tmp_path):
    path_base, path_dl = _preparar_planilha(tmp_path)
    controle = _controle_xlsx(tmp_path, prevista="01-09-2026")
    recusa = _Decisor(lambda p: DecisaoSobrescricao.recusar_todas(len(p)))
    wb, ws, col = _atualizar(path_base, path_dl, controle, recusa)

    assert _data(ws, col, "DATA PREVISTA EMISSÃO") == date(2026, 3, 1)
    aba = wb[ABA_RECUSAS]
    assert [c.value for c in aba[1]][:5] == ["N° ITAIPU", "Nº CMI", "COLUNA", "DATA NA PLANILHA",
                                             "DATA DO CONTROLE"]
    linha = [c.value for c in aba[2]]
    assert linha[:3] == ["#IT-1", "CMI-1", "DATA PREVISTA EMISSÃO"]
    assert (linha[3].date(), linha[4].date(), linha[5].date()) == \
        (date(2026, 3, 1), date(2026, 9, 1), HOJE)

    # Segunda rodada, mesmo Controle: a tela nem é aberta.
    de_novo = _Decisor(lambda p: DecisaoSobrescricao.aceitar_todas(len(p)))
    logs = []
    _wb, ws, col = _atualizar(path_base, path_dl, controle, de_novo, logs)
    assert de_novo.chamadas == []
    assert _data(ws, col, "DATA PREVISTA EMISSÃO") == date(2026, 3, 1)
    assert any("já recusada antes" in m for m in logs)


def test_controle_com_outra_data_volta_a_perguntar(tmp_path):
    path_base, path_dl = _preparar_planilha(tmp_path)
    _atualizar(path_base, path_dl, _controle_xlsx(tmp_path, prevista="01-09-2026"),
               _Decisor(lambda p: DecisaoSobrescricao.recusar_todas(len(p))))

    decisor = _Decisor(lambda p: None)
    _atualizar(path_base, path_dl, _controle_xlsx(tmp_path, prevista="15-09-2026"), decisor)
    assert [i.data_controle for i in decisor.chamadas[0]] == [date(2026, 9, 15)]


def test_linha_apagada_da_aba_faz_perguntar_de_novo(tmp_path):
    path_base, path_dl = _preparar_planilha(tmp_path)
    controle = _controle_xlsx(tmp_path, prevista="01-09-2026")
    wb, _ws, _col = _atualizar(path_base, path_dl, controle,
                               _Decisor(lambda p: DecisaoSobrescricao.recusar_todas(len(p))))
    wb[ABA_RECUSAS].delete_rows(2)
    wb.save(path_dl)

    decisor = _Decisor(lambda p: None)
    _atualizar(path_base, path_dl, controle, decisor)
    assert len(decisor.chamadas) == 1


def test_adiar_nao_troca_nem_anota(tmp_path):
    path_base, path_dl = _preparar_planilha(tmp_path)
    logs = []
    wb, ws, col = _atualizar(path_base, path_dl, _controle_xlsx(tmp_path, prevista="01-09-2026"),
                             _Decisor(lambda p: None), logs)
    assert _data(ws, col, "DATA PREVISTA EMISSÃO") == date(2026, 3, 1)
    assert ABA_RECUSAS not in wb.sheetnames
    assert any("ficou como está" in m for m in logs)


def test_caso_a_caso_troca_so_as_escolhidas(tmp_path):
    path_base, path_dl = _preparar_planilha(tmp_path, prevista=date(2026, 3, 1),
                                            reprog=date(2026, 11, 10))
    controle = _controle_xlsx(tmp_path, prevista="01-09-2026", reprog="15/12/2026")

    def escolher(pendentes):
        reprog = next(i for i, inc in enumerate(pendentes) if inc.coluna == "reprogramada")
        prev = next(i for i, inc in enumerate(pendentes) if inc.coluna == "prevista")
        return DecisaoSobrescricao(aceitas=frozenset({reprog}), recusadas=frozenset({prev}))

    wb, ws, col = _atualizar(path_base, path_dl, controle, _Decisor(escolher))
    assert _data(ws, col, "DATA PREVISTA EMISSÃO") == date(2026, 3, 1)       # recusada
    assert _data(ws, col, "DATA REPROGRAMADA") == date(2026, 12, 15)         # aceita
    assert _data(ws, col, "DATA-ALVO EMISSÃO") == date(2026, 12, 15)
    assert [c.value for c in wb[ABA_RECUSAS][2]][2] == "DATA PREVISTA EMISSÃO"


# ---------------------------------------------------------------------------
# SITUAÇÃO OTD e SITUAÇÃO SAY-DO (Baseline OTD e Say-do, pedido de 2026-10-28)
# ---------------------------------------------------------------------------
HOJE_OUT = date(2026, 10, 28)


@pytest.mark.parametrize("caso,prevista,reprogramada,emissao,esperado", [
    # A: perdeu a data prevista e assumiu nova data → backlog, no prazo do novo compromisso.
    ("A", date(2026, 10, 15), date(2027, 2, 28), None, SIT_PENDENTE_NO_PRAZO),
    # B: reprogramado antes de vencer → entra no backlog assim que é reprogramado.
    ("B", date(2026, 12, 22), date(2027, 2, 28), None, SIT_PENDENTE_NO_PRAZO),
    # C: saiu antes da prevista; a reprogramada é de outra revisão → fora do backlog.
    ("C", date(2026, 9, 30), date(2026, 10, 9), date(2026, 9, 24), None),
    # D: a data não mudou → fora do backlog.
    ("D", date(2027, 2, 28), date(2027, 2, 28), None, None),
    # E: vencido sem data nova → fora do backlog (é o atrasado sem compromisso).
    ("E", date(2026, 9, 1), None, None, None),
    # Saiu depois da prevista, mas antes da reprogramada → cumpriu o novo compromisso.
    ("F", date(2026, 5, 1), date(2026, 8, 1), date(2026, 7, 20), SIT_EMITIDO_NO_PRAZO),
    # Perdeu também a reprogramada.
    ("G", date(2026, 5, 1), date(2026, 8, 1), date(2026, 9, 2), SIT_EMITIDO_COM_ATRASO),
    ("H", date(2026, 5, 1), date(2026, 8, 1), None, SIT_PENDENTE_VENCIDO),
])
def test_situacao_say_do_so_existe_no_backlog(caso, prevista, reprogramada, emissao, esperado):
    assert classificar_situacao_say_do(
        data_prevista=prevista, data_reprogramada=reprogramada, data_primeira_emissao=emissao,
        status_consolidado="NÃO EMITIDO" if emissao is None else "APROVADO",
        hoje=HOJE_OUT) == esperado, caso


def test_backlog_cancelado_fica_cancelado_no_say_do():
    assert classificar_situacao_say_do(
        data_prevista=date(2026, 5, 1), data_reprogramada=date(2026, 8, 1),
        data_primeira_emissao=None, status_consolidado="CANCELADO", hoje=HOJE_OUT) == SIT_CANCELADO


def _doclist_casos_a_e(tmp_path, *, sem_colunas_novas=False):
    """Um grupo e os casos A-E (só o C está no Aconex, emitido em 24/09/2026)."""
    b = base(HistoricoBuilder("TC", "#IT-C", "CMI-C", "DOC C")
             .evento("0A", 1, "Em Processo", "24/09/2026", current=True))
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)
    linhas = [
        ("UNIT", "SDSC", "", "GRUPO-1", "AGRUPAMENTO", "1", None, None),
        ("UNIT", "SDSC", "CMI-A", "#IT-A", "DOC A", "2", date(2026, 10, 15), date(2027, 2, 28)),
        ("UNIT", "SDSC", "CMI-B", "#IT-B", "DOC B", "2", date(2026, 12, 22), date(2027, 2, 28)),
        ("UNIT", "SDSC", "CMI-C", "#IT-C", "DOC C", "2", date(2026, 9, 30), date(2026, 10, 9)),
        ("UNIT", "SDSC", "CMI-D", "#IT-D", "DOC D", "2", date(2027, 2, 28), date(2027, 2, 28)),
        ("UNIT", "SDSC", "CMI-E", "#IT-E", "DOC E", "2", date(2026, 9, 1), None),
    ]
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", linhas)
    if sem_colunas_novas:
        wb = openpyxl.load_workbook(path_dl)
        ws = wb.active
        for titulo in ("SITUAÇÃO SAY-DO", "SITUAÇÃO OTD"):
            ws.delete_cols([c.column for c in ws[1] if c.value == titulo][0])
        ws.auto_filter.ref = f"A1:{ws.cell(1, ws.max_column).column_letter}{ws.max_row}"
        wb.save(path_dl)
    return path_base, path_dl


def test_ciclo_completo_grava_situacao_otd_e_say_do(tmp_path):
    path_base, path_dl = _doclist_casos_a_e(tmp_path)
    r = atualizar_doclist(path_base, path_dl, hoje=HOJE_OUT, log_cb=lambda _m: None)
    assert r.ok, r.mensagem
    ws = openpyxl.load_workbook(path_dl).active
    col = {str(c.value): c.column for c in ws[1]}
    situacao = {ws.cell(row, col["N° ITAIPU"]).value: (ws.cell(row, col["SITUAÇÃO OTD"]).value,
                                                       ws.cell(row, col["SITUAÇÃO SAY-DO"]).value,
                                                       ws.cell(row, col["SITUAÇÃO EMISSÃO"]).value)
                for row in range(2, 8)}
    assert situacao == {
        "GRUPO-1": (None, None, None),                                   # grupo não é documento
        "#IT-A": (SIT_PENDENTE_VENCIDO, SIT_PENDENTE_NO_PRAZO, SIT_PENDENTE_NO_PRAZO),
        "#IT-B": (SIT_PENDENTE_NO_PRAZO, SIT_PENDENTE_NO_PRAZO, SIT_PENDENTE_NO_PRAZO),
        "#IT-C": (SIT_EMITIDO_NO_PRAZO, None, SIT_EMITIDO_NO_PRAZO),
        "#IT-D": (SIT_PENDENTE_NO_PRAZO, None, SIT_PENDENTE_NO_PRAZO),
        "#IT-E": (SIT_PENDENTE_VENCIDO, None, SIT_PENDENTE_VENCIDO),
    }


def test_colunas_otd_e_say_do_sao_criadas_quando_faltam(tmp_path):
    path_base, path_dl = _doclist_casos_a_e(tmp_path, sem_colunas_novas=True)
    logs = []
    assert atualizar_doclist(path_base, path_dl, hoje=HOJE_OUT, log_cb=logs.append).ok
    ws = openpyxl.load_workbook(path_dl).active
    cab = [c.value for c in ws[1]]
    assert cab[-2:] == ["SITUAÇÃO OTD", "SITUAÇÃO SAY-DO"]                # no fim da aba
    assert ws.cell(3, len(cab)).value == SIT_PENDENTE_NO_PRAZO           # say-do do caso A
    assert ws.auto_filter.ref.endswith(f"{ws.cell(1, len(cab)).column_letter}7")
    assert any("Coluna criada: SITUAÇÃO OTD" in m for m in logs)
    assert not any("não encontradas" in m for m in logs)


def test_recusa_continua_valendo_quando_o_aconex_troca_o_codigo_itaipu(tmp_path):
    """O app atualiza o N° ITAIPU pelo Aconex; a recusa anotada com o código
    antigo continua valendo pelo Nº CMI."""
    b = base(HistoricoBuilder("T1", "#IT-NOVO", "CMI-1", "DOC")
             .evento("0A", 1, "Em Processo", "01/03/2026", current=True))
    path_base = tmp_path / "base.xlsx"
    b.to_excel(path_base, index=False)
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx",
                                [("UNIT", "SDSC", "CMI-1", "#IT-VELHO", "DOC", "2", date(2026, 3, 1), None)])
    controle = ler_controle(escrever_controle_xlsx(
        tmp_path / "ctrl.xlsx", [{"itaipu": "#IT-NOVO", "cmi": "CMI-1", "prevista": "01-09-2026"}]),
        0, log_cb=lambda _m: None)
    _atualizar(path_base, path_dl, controle, _Decisor(lambda p: DecisaoSobrescricao.recusar_todas(len(p))))

    de_novo = _Decisor(lambda p: None)
    _wb, ws, col = _atualizar(path_base, path_dl, controle, de_novo)
    assert ws.cell(2, col["N° ITAIPU"]).value == "#IT-NOVO"
    assert de_novo.chamadas == []


def test_formula_recusada_fica_como_texto_na_aba(tmp_path):
    def preparar_formula(path_dl):
        wb = openpyxl.load_workbook(path_dl)
        ws = wb.active
        col = {str(c.value): c.column for c in ws[1]}
        ws.cell(2, col["DATA REPROGRAMADA"]).value = "=DATE(2026,12,1)"
        wb.save(path_dl)

    path_base, path_dl = _preparar_planilha(tmp_path)
    preparar_formula(path_dl)
    logs = []
    wb, ws, col = _atualizar(path_base, path_dl,
                             _controle_xlsx(tmp_path, prevista="01-03-2026", reprog="15/12/2026"),
                             _Decisor(lambda p: DecisaoSobrescricao.recusar_todas(len(p))), logs)
    assert ws.cell(2, col["DATA REPROGRAMADA"]).value == "=DATE(2026,12,1)"   # a fórmula ficou
    celula = wb[ABA_RECUSAS].cell(2, 4)
    assert (celula.value, celula.data_type) == ("=DATE(2026,12,1)", "s")
    assert any("1 data preenchida que o Controle trocaria: 0 trocadas, 1 recusada" in m for m in logs)


def _windows_recusa_salvar(monkeypatch, programas):
    """Toda gravação de planilha é recusada; o Windows aponta `programas`."""
    from docmanager.services import gravacao

    def recusa(self, caminho):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(openpyxl.Workbook, "save", recusa)
    monkeypatch.setattr(gravacao, "_somente_leitura", lambda c: False)
    monkeypatch.setattr(gravacao, "_programas_com_o_arquivo", lambda c: programas)
    monkeypatch.setattr(gravacao.time, "sleep", lambda s: None)


def test_salvar_recusado_diz_qual_programa_esta_com_a_planilha(tmp_path, monkeypatch):
    """3.6.1-rc.1: o app dizia "arquivo aberto?" sem o arquivo estar aberto. O motivo
    agora vem do Windows, na pergunta "Tentar de novo" e no resultado."""
    path_base, path_dl = _preparar_planilha(tmp_path)
    _windows_recusa_salvar(monkeypatch, ["Microsoft Excel"])
    perguntas = []
    r = atualizar_doclist(path_base, path_dl, hoje=HOJE, log_cb=lambda _m: None,
                          retry_cb=lambda m: perguntas.append(m) or False)
    assert not r.ok
    assert "Microsoft Excel" in r.mensagem
    assert "arquivo aberto?" not in r.mensagem
    assert len(perguntas) == 1 and "Microsoft Excel" in perguntas[0]
