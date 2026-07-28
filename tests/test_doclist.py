"""Módulo Doc List Mapping: consolidado de 3 sabores, hierarquia de 2 níveis,
planejamento vindo do Controle e a Análise por Período."""
from datetime import date

import openpyxl
import pytest
from builders import HistoricoBuilder, base, escrever_controle_xlsx

from docmanager.core.doclist import (
    COLUNAS_DOCLIST,
    LinhaDocList,
    calcula_status_consolidado_doclist,
    calcular_predecessores,
    calcular_resumo_quantidades,
    resolver_datas_doclist,
)
from docmanager.core.doclist_periodo import (
    analisar_periodo,
    janelas_padrao,
    listar_sem_data,
    resumo,
)
from docmanager.services.controle_docs import ler_controle
from docmanager.services.doclist_io import DocListSheet, criar_modelo, ler_linhas_doclist
from docmanager.services.doclist_update import atualizar_doclist

HOJE = date(2026, 7, 27)


# ---------------------------------------------------------------------------
# Status consolidado — três sabores de aprovação
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status_real,status_emissao,esperado", [
    ("Aprovado", "Aprovado", "APROVADO"),
    ("Aprovado com Comentários", "Aprovado com Comentários", "APROVADO COM COMENTÁRIOS"),
    ("Para Assinatura", "Para Assinatura", "PARA ASSINATURA"),
    ("Informativo", "Informativo", "APROVADO"),
    ("Não Aprovado", "Não Aprovado", "NÃO APROVADO"),
    ("Em Processo", "Em Processo", "EM PROCESSO"),
    ("NÃO EMITIDO", "", "NÃO EMITIDO"),
])
def test_consolidado_doclist_separa_aprovacoes(status_real, status_emissao, esperado):
    assert calcula_status_consolidado_doclist(status_real, status_emissao, "EMITIDO") == esperado


def test_consolidado_doclist_diverge_do_mapa_so_nas_aprovacoes():
    """O Mapa funde tudo em APROVADO; o Doc List separa. O resto é idêntico."""
    from docmanager.core.consolidation import calcula_status_consolidado

    assert calcula_status_consolidado("Aprovado com Comentários", "x", "EMITIDO") == "APROVADO"
    assert calcula_status_consolidado_doclist("Aprovado com Comentários", "x", "EMITIDO") \
        == "APROVADO COM COMENTÁRIOS"
    for sr, se in (("Não Aprovado", "Não Aprovado"), ("Em Processo", "Em Processo")):
        assert calcula_status_consolidado_doclist(sr, se, "EMITIDO") \
            == calcula_status_consolidado(sr, se, "EMITIDO")


# ---------------------------------------------------------------------------
# Hierarquia de dois níveis (uma coluna PREDECESSOR)
# ---------------------------------------------------------------------------
def _linhas_hierarquia():
    return [
        LinhaDocList(row=2, cod_itaipu="SDSC UG FABRIC", nivel="1"),
        LinhaDocList(row=3, cod_itaipu="DOC-A", nivel="2", status_consolidado="APROVADO"),
        LinhaDocList(row=4, cod_itaipu="DOC-B", nivel="2",
                     status_consolidado="APROVADO COM COMENTÁRIOS"),
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


def test_resumo_quantidades_separa_aprovados_com_comentarios():
    linhas = _linhas_hierarquia()
    resumo_txt = calcular_resumo_quantidades(linhas, calcular_predecessores(linhas))
    assert resumo_txt[2] == ("Total: 2\nAprovados: 1\nAprovados c/ Comentários: 1\n"
                             "Para Assinatura: 0\nEm Processo: 0\nNão Aprovados: 0\n"
                             "Não Emitidos: 0")
    assert "Não Emitidos: 1" in resumo_txt[5]


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


def _row_controle(prevista=None, reprog=None, fase=""):
    from docmanager.services.controle_docs import ControleRow
    return ControleRow(cod_itaipu="IT", cod_cmi="CMI", titulo="t",
                       data_prevista=prevista, data_reprogramada=reprog, fase=fase)


def test_prevista_vence_a_mais_recente():
    """Divergência entre planilha e Controle → a data MAIS RECENTE ganha."""
    ctrl = _ControleFake(_row_controle(prevista=date(2026, 9, 1)))
    d = resolver_datas_doclist(prevista_atual=date(2026, 3, 1), reprogramada_atual=None,
                               fase_atual="", codigos=[], cod_itaipu_atual="IT",
                               cod_cmi_atual="", controle=ctrl)
    assert d.prevista == date(2026, 9, 1) and d.prevista_atualizada
    assert d.data_alvo == date(2026, 9, 1)


def test_prevista_da_planilha_mais_recente_e_preservada():
    ctrl = _ControleFake(_row_controle(prevista=date(2026, 1, 1)))
    d = resolver_datas_doclist(prevista_atual=date(2026, 9, 1), reprogramada_atual=None,
                               fase_atual="", codigos=[], cod_itaipu_atual="IT",
                               cod_cmi_atual="", controle=ctrl)
    assert d.prevista is None            # nada a escrever
    assert d.data_alvo == date(2026, 9, 1)


def test_reprogramada_manual_nunca_e_sobrescrita():
    ctrl = _ControleFake(_row_controle(prevista=date(2026, 1, 1), reprog=date(2026, 5, 5)))
    d = resolver_datas_doclist(prevista_atual=None, reprogramada_atual=date(2026, 8, 8),
                               fase_atual="", codigos=[], cod_itaipu_atual="IT",
                               cod_cmi_atual="", controle=ctrl)
    assert d.reprogramada is None                 # input manual manda
    assert d.data_alvo == date(2026, 8, 8)        # e é ela que vale


def test_data_alvo_prefere_reprogramada():
    ctrl = _ControleFake(_row_controle(prevista=date(2026, 1, 1), reprog=date(2026, 5, 5)))
    d = resolver_datas_doclist(prevista_atual=None, reprogramada_atual=None, fase_atual="",
                               codigos=[], cod_itaipu_atual="IT", cod_cmi_atual="", controle=ctrl)
    assert d.reprogramada == date(2026, 5, 5)
    assert d.data_alvo == date(2026, 5, 5)


def test_fase_vem_do_controle_e_preserva_quando_controle_vazio():
    d = resolver_datas_doclist(prevista_atual=None, reprogramada_atual=None, fase_atual="",
                               codigos=[], cod_itaipu_atual="IT", cod_cmi_atual="",
                               controle=_ControleFake(_row_controle(fase="FABRICAÇÃO")))
    assert d.fase == "FABRICAÇÃO"
    d2 = resolver_datas_doclist(prevista_atual=None, reprogramada_atual=None,
                                fase_atual="MONTAGEM", codigos=[], cod_itaipu_atual="IT",
                                cod_cmi_atual="", controle=_ControleFake(_row_controle(fase="")))
    assert d2.fase is None


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


def test_criar_modelo_gera_cabecalho_oficial(tmp_path):
    destino = tmp_path / "modelo.xlsx"
    ok, msg = criar_modelo(destino)
    assert ok, msg
    ws = openpyxl.load_workbook(destino).active
    assert [c.value for c in ws[1]] == list(COLUNAS_DOCLIST.values())


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
    assert "Aprovados: 1" in val(2, "RESUMO QUANTIDADES")
    assert "Aprovados c/ Comentários: 1" in val(2, "RESUMO QUANTIDADES")
    assert "Não Emitidos: 1" in val(2, "RESUMO QUANTIDADES")

    # Documentos: consolidado de 3 sabores + predecessor do grupo.
    assert val(3, "STATUS CONSOLIDADO") == "APROVADO"
    assert val(4, "STATUS CONSOLIDADO") == "APROVADO COM COMENTÁRIOS"
    assert val(5, "STATUS CONSOLIDADO") == "NÃO EMITIDO"
    assert val(5, "PREDECESSOR") == "SDSC UG FABRIC"

    # Data de emissão vem do Aconex como data NATIVA (o dashboard precisa).
    assert val(3, "DATA ÚLTIMA EMISSÃO").date() == date(2026, 3, 20)
    assert val(3, "ÚLTIMA REV. EMITIDA") == "0A"

    # Planejamento: fase, datas nativas e a data-alvo (reprogramada > prevista).
    assert val(3, "FASE DE PROJETO") == "FABRICAÇÃO"
    assert val(3, "DATA PREVISTA EMISSÃO").date() == date(2026, 2, 1)
    assert val(3, "DATA-ALVO EMISSÃO").date() == date(2026, 2, 1)
    assert val(4, "DATA REPROGRAMADA").date() == date(2026, 9, 15)
    assert val(4, "DATA-ALVO EMISSÃO").date() == date(2026, 9, 15)
    # Documento fora do Aconex TAMBÉM recebe a data do Controle (§27/§24.12).
    assert val(5, "DATA PREVISTA EMISSÃO").date() == date(2026, 8, 5)
    assert val(5, "DATA-ALVO EMISSÃO").date() == date(2026, 8, 5)


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
