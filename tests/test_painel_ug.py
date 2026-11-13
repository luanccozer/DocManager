"""Painel HTML da Unidade Geradora: os dados que o DocManager calcula para ele
(`core/painel_ug.py`). Spec: `.scratch/painel-ug-html/spec.md`."""
from datetime import date

import pytest
from builders import HistoricoBuilder, base

from docmanager.core.doclist import (
    SIT_EMITIDO_COM_ATRASO,
    SIT_EMITIDO_NO_PRAZO,
    SIT_PENDENTE_NO_PRAZO,
    SIT_PENDENTE_VENCIDO,
    LinhaDocList,
)
from docmanager.core.painel_ug import (
    ESCOPO_18A,
    ESCOPO_UG,
    TIPO_EMISSAO_FINAL,
    TIPO_PRIMEIRA_EMISSAO,
    TIPO_REEMISSAO,
    escopo_da_linha,
    linha_do_tempo,
    montar_dados_painel,
    tipo_de_envio,
)

HOJE = date(2026, 6, 1)


@pytest.mark.parametrize("sistema,grupo,esperado", [
    ("SDSC - UG", "SDSC UG FABRIC", ESCOPO_UG),
    ("SDSC - UG 18A", "SDSC UG18A FABR", ESCOPO_18A),
    ("eBOP - PRESS UG", "eBOP - PRESS UG FABR", ESCOPO_UG),
    ("MIGRATION", "MIG PLAN - 18A", ESCOPO_18A),      # PEM: o 18A está só no grupo
    ("INST - 18A", "INST - 18A EXE", ESCOPO_18A),
])
def test_escopo_ug_ou_18a(sistema, grupo, esperado):
    assert escopo_da_linha(sistema, grupo) == esperado


@pytest.mark.parametrize("revisao,primeiro,esperado", [
    ("0A", True, TIPO_PRIMEIRA_EMISSAO),
    ("0B", False, TIPO_REEMISSAO),
    ("0", False, TIPO_EMISSAO_FINAL),
    ("1A", False, TIPO_REEMISSAO),
    ("1", False, TIPO_EMISSAO_FINAL),
    ("0C", True, TIPO_PRIMEIRA_EMISSAO),             # documento SAT entra em revisão alta
])
def test_tipo_do_envio(revisao, primeiro, esperado):
    assert tipo_de_envio(revisao, primeiro=primeiro) == esperado


def _doc_reprovado_e_reemitido(tracking="T1", doc="#IT-1", cmi="CMI-1"):
    # A Versão do Aconex é um contador do documento, não da revisão: só cresce.
    return (HistoricoBuilder(tracking, doc, cmi, "DOC 1")
            .evento("0A", 1, "Em Processo", "05/03/2026")
            .evento("0A", 2, "Não Aprovado", "01/04/2026")
            .evento("0B", 3, "Em Processo", "10/04/2026")
            .evento("0B", 4, "Aprovado com Comentários", "30/04/2026")
            .evento("0", 5, "Em Processo", "05/05/2026")
            .evento("0", 6, "Aprovado", "12/05/2026", current=True))


def test_linha_do_tempo_guarda_so_as_mudancas_de_status():
    tempo = linha_do_tempo(_doc_reprovado_e_reemitido().build())
    assert tempo == [
        (date(2026, 3, 5), "Em Processo"),
        (date(2026, 4, 1), "Não Aprovado"),
        (date(2026, 4, 10), "Em Processo"),          # a reemissão já está com a Itaipu
        (date(2026, 4, 30), "Aprovado com Comentários"),
        (date(2026, 5, 12), "Aprovado"),             # o envio da rev. 0 não rebaixa o aprovado
    ]


def test_linha_do_tempo_de_documento_sem_historico_e_vazia():
    assert linha_do_tempo(base()) == []


def _linhas():
    def ln(row, nivel, grupo, sistema, cod, cmi, prev=None, reprog=None, fase="FABRICAÇÃO", resp="COE"):
        return LinhaDocList(row=row, cod_itaipu=cod, cod_cmi=cmi, nivel=nivel, grupo=grupo,
                            sistema=sistema, fase_projeto=fase, descricao=f"DESC {cod}",
                            responsavel=resp, data_prevista=prev, data_reprogramada=reprog)
    return [
        ln(4, "1", "SDSC", "SDSC - UG", "SDSC UG FABRIC", ""),
        ln(5, "2", "SDSC", "SDSC - UG", "#IT-1", "CMI-1", prev=date(2026, 3, 10)),
        ln(6, "2", "SDSC", "SDSC - UG", "#IT-2", "CMI-2", prev=date(2026, 4, 1), reprog=date(2026, 7, 1)),
        ln(7, "1", "SDSC", "SDSC - UG 18A", "SDSC UG18A FABR", ""),
        ln(8, "2", "SDSC", "SDSC - UG 18A", "#IT-1", "CMI-1", prev=date(2026, 3, 10)),   # mesmo documento
        ln(9, "2", "SDSC", "SDSC - UG 18A", "#IT-3", "CMI-3", prev=date(2026, 2, 1), resp="JVM"),
    ]


def _base():
    return base(
        _doc_reprovado_e_reemitido(),
        HistoricoBuilder("T3", "#IT-3", "CMI-3", "DOC 3")
        .evento("0A", 1, "Em Processo", "20/02/2026", current=True),
    )


def test_um_codigo_conta_uma_vez_e_as_linhas_viram_associacoes():
    dados = montar_dados_painel(_linhas(), _base(), hoje=HOJE)
    assert [d["codigo"] for d in dados["documentos"]] == ["#IT-1", "#IT-2", "#IT-3"]
    assoc = [(a["doc"], a["sistema"], a["escopo"]) for a in dados["associacoes"]]
    assert assoc == [(0, "SDSC - UG", ESCOPO_UG), (1, "SDSC - UG", ESCOPO_UG),
                     (0, "SDSC - UG 18A", ESCOPO_18A), (2, "SDSC - UG 18A", ESCOPO_18A)]
    assert [g["codigo"] for g in dados["grupos"]] == ["SDSC UG FABRIC", "SDSC UG18A FABR"]
    assert dados["associacoes"][3]["responsavel"] == "JVM"
    assert dados["ultimo_evento_aconex"] == "2026-05-12"


def test_retrato_de_hoje_como_a_atualizacao_da_planilha_calcula():
    docs = montar_dados_painel(_linhas(), _base(), hoje=HOJE)["documentos"]
    d1, d2, d3 = docs
    assert d1["status_real"] == "Aprovado" and d1["consolidado"] == "APROVADO"
    assert d1["primeira_emissao"] == "2026-03-05"
    assert d1["situacao_emissao"] == SIT_EMITIDO_NO_PRAZO and d1["desvio"] == -5
    # Não está no Aconex: não emitido, com o backlog medido contra a reprogramada.
    assert not d2["no_aconex"] and d2["status_real"] == "NÃO EMITIDO"
    assert d2["situacao_emissao"] == SIT_PENDENTE_NO_PRAZO      # data-alvo = 01/07
    assert d2["situacao_otd"] == SIT_PENDENTE_VENCIDO           # contra a prevista (01/04)
    assert d2["backlog"] and d2["situacao_say_do"] == SIT_PENDENTE_NO_PRAZO
    assert d2["alvo"] == "2026-07-01" and d2["revisoes"] == [] and d2["linha_do_tempo"] == []
    assert d3["com"] == "ITAIPU" and d3["situacao_emissao"] == SIT_EMITIDO_COM_ATRASO


def test_historico_de_revisoes_com_dias_e_tipo_do_envio():
    d1 = montar_dados_painel(_linhas(), _base(), hoje=HOJE)["documentos"][0]
    revs = [(r["revisao"], r["tipo"], r["envio"], r["retorno"], r["status_retorno"],
             r["dias_itaipu"], r["atraso_itaipu"], r["dias_cmi"], r["atraso_cmi"]) for r in d1["revisoes"]]
    assert revs == [
        ("0A", TIPO_PRIMEIRA_EMISSAO, "2026-03-05", "2026-04-01", "Não Aprovado", 27, 0, None, None),
        ("0B", TIPO_REEMISSAO, "2026-04-10", "2026-04-30", "Aprovado com Comentários", 20, 5, 9, 0),
        ("0", TIPO_EMISSAO_FINAL, "2026-05-05", "2026-05-12", "Aprovado", 7, 0, 5, 0),
    ]


def test_dias_cmi_da_1a_emissao_contam_contra_a_data_alvo():
    d1 = montar_dados_painel(_linhas(), _base(), hoje=HOJE)["documentos"][0]
    d3 = montar_dados_painel(_linhas(), _base(), hoje=HOJE)["documentos"][2]
    assert d1["revisoes"][0]["dias_cmi"] is None          # saiu antes da data-alvo
    assert d3["revisoes"][0]["dias_cmi"] == 19 and d3["revisoes"][0]["atraso_cmi"] == 19
    # Ainda com a Itaipu: sem retorno, e o relógio dela corre até hoje.
    assert d3["revisoes"][0]["retorno"] is None and d3["revisoes"][0]["status_retorno"] is None
    assert d3["revisoes"][0]["dias_itaipu"] == (HOJE - date(2026, 2, 20)).days


def test_linha_do_tempo_termina_no_status_de_hoje():
    docs = montar_dados_painel(_linhas(), _base(), hoje=HOJE)["documentos"]
    assert docs[0]["linha_do_tempo"][-1] == ("2026-05-12", "Aprovado")
    assert docs[2]["linha_do_tempo"] == [("2026-02-20", "Em Processo")]


def test_progresso_vai_de_0_a_1():
    passos = []
    montar_dados_painel(_linhas(), _base(), hoje=HOJE, progresso=passos.append)
    assert passos[0] > 0 and passos[-1] == 1.0 and passos == sorted(passos)


# ---------------------------------------------------------------------------
# A página: um arquivo só, sem nada da internet
# ---------------------------------------------------------------------------
def _html(dados):
    from docmanager.dashboard.painel_ug_html import renderizar
    return renderizar(dados, base="base.xlsx", doc_list="dl.xlsx", aba="Unidade Geradora",
                      gerado_em="10/06/2026 09:00", versao="9.9.9")


def test_pagina_e_um_arquivo_so_que_abre_sem_internet():
    html = _html(montar_dados_painel(_linhas(), _base(), hoje=HOJE))
    assert "Chart.js v4.4.4" in html and "chartjs-plugin-datalabels v2.2.0" in html   # licenças preservadas
    assert "/*__" not in html                                     # nenhum marcador sobrando
    assert "<script src=" not in html and "<link" not in html     # nada buscado fora do arquivo
    assert '"versao":"9.9.9"' in html and '"#IT-3"' in html


def test_texto_da_planilha_nao_fecha_o_script():
    linhas = _linhas()
    linhas[1].descricao = "PAINEL </script><b>X</b>"
    html = _html(montar_dados_painel(linhas, base(), hoje=HOJE))
    assert "</script><b>X" not in html


def test_ordem_dos_campos_e_o_contrato_com_o_javascript():
    """`painel_ug.html` lê `D.docs[i][k]` por posição: mudar a ordem quebra a página."""
    from docmanager.dashboard.painel_ug_html import compactar
    dados = montar_dados_painel(_linhas(), _base(), hoje=HOJE)
    c = compactar(dados, {"base": "b"})
    d1 = c["docs"][0]
    assert d1[0] == "#IT-1" and d1[6] == "2026-03-10" and d1[7] == "2026-03-05" and d1[10] == "Aprovado"
    assert d1[14] == SIT_EMITIDO_NO_PRAZO and d1[19] == 1
    assert d1[20][0] == ["2026-03-05", "Em Processo"]
    assert d1[21][1][:5] == ["0B", TIPO_REEMISSAO, "2026-04-10", "2026-04-30", "Aprovado com Comentários"]
    # Tracking ID, como foi achado, ambíguo, código vigente, Aconex sem Nº CMI, datas
    # diferentes nas linhas do mesmo código
    assert d1[22:] == ["T1", "par", 0, 1, 0, 0]
    assert c["docs"][1][22:] == ["", "", 0, 1, 0, 0]       # não achado no Aconex
    assert c["assoc"][2][:3] == [0, "SDSC", "SDSC - UG 18A"] and c["assoc"][2][5] == ESCOPO_18A
    assert c["meta"]["hoje"] == "2026-06-01" and c["meta"]["base"] == "b"


def test_gerar_painel_de_ponta_a_ponta(tmp_path):
    from test_doclist import _escrever_doclist

    from docmanager.doclist_backend import gerar_painel_ug

    path_base = tmp_path / "base.xlsx"
    _base().to_excel(path_base, index=False)
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", [
        ("SDSC", "SDSC - UG", "", "SDSC UG FABRIC", "GRUPO", "1", None, None),
        ("SDSC", "SDSC - UG", "CMI-1", "#IT-1", "DOC 1", "2", date(2026, 3, 10), None),
        ("SDSC", "SDSC - UG", "CMI-2", "#IT-2", "DOC 2", "2", date(2026, 4, 1), date(2026, 7, 1)),
    ])
    logs = []
    saida = tmp_path / "painel.html"
    r = gerar_painel_ug(path_base, path_dl, saida, hoje=HOJE, log_cb=logs.append)
    assert r.ok and r.documentos == 2
    html = saida.read_text(encoding="utf-8")
    assert '"#IT-1"' in html and '"#IT-2"' in html
    assert any("1 ainda não estão no Aconex" in m for m in logs)


def test_planilha_sem_documentos_avisa_e_nao_grava(tmp_path):
    from test_doclist import _escrever_doclist

    from docmanager.doclist_backend import gerar_painel_ug

    path_base = tmp_path / "base.xlsx"
    _base().to_excel(path_base, index=False)
    path_dl = _escrever_doclist(tmp_path / "dl.xlsx", [("SDSC", "SDSC - UG", "", "G", "GRUPO", "1", None, None)])
    r = gerar_painel_ug(path_base, path_dl, tmp_path / "painel.html", hoje=HOJE)
    assert not r.ok and "Nenhum documento" in r.mensagem
    assert not (tmp_path / "painel.html").exists()


def test_rastreamento_diz_por_qual_codigo_o_documento_foi_achado():
    """Mesma cascata da atualização da planilha: o par Itaipu+CMI vence; com o CMI da
    planilha errado, o documento ainda é achado pelo Itaipu, e o painel registra isso."""
    linhas = _linhas()
    linhas[5].cod_cmi = "CMI-ERRADO"
    docs = montar_dados_painel(linhas, _base(), hoje=HOJE)["documentos"]
    assert (docs[0]["tracking"], docs[0]["achado_por"]) == ("T1", "par")
    assert (docs[2]["tracking"], docs[2]["achado_por"]) == ("T3", "itaipu")
    assert (docs[1]["tracking"], docs[1]["achado_por"]) == ("", "")
    assert not any(d["ambiguo"] for d in docs) and all(d["codigo_vigente"] for d in docs)


def test_achado_so_pelo_itaipu_separa_aconex_sem_n_cmi_de_n_cmi_diferente():
    """Dois motivos para achar só pelo Nº ITAIPU: o Aconex não tem Nº CMI (a atualização
    da planilha mantém o dela, e o caso não some sozinho) ou o Nº CMI da planilha é
    outro (a próxima atualização grava o do Aconex)."""
    linhas = _linhas()                                      # #IT-3 está na planilha com CMI-3
    sem_cmi = base(_doc_reprovado_e_reemitido(),
                   HistoricoBuilder("T3", "#IT-3", "", "DOC 3")
                   .evento("0A", 1, "Em Processo", "20/02/2026", current=True))
    d = montar_dados_painel(linhas, sem_cmi, hoje=HOJE)["documentos"][2]
    assert d["achado_por"] == "itaipu" and d["aconex_sem_cmi"]
    assert d["cmi"] == "CMI-3"                              # fica o Nº CMI da planilha

    linhas[5].cod_cmi = "CMI-ERRADO"
    docs = montar_dados_painel(linhas, _base(), hoje=HOJE)["documentos"]
    assert docs[2]["achado_por"] == "itaipu" and not docs[2]["aconex_sem_cmi"]
    assert not docs[0]["aconex_sem_cmi"] and not docs[1]["aconex_sem_cmi"]   # pelo par; não achado


def test_documento_compartilhado_com_datas_diferentes_nas_linhas_fica_marcado():
    """O mesmo código em duas linhas com datas diferentes: o painel usa as da 1ª linha e
    marca o documento, para a qualidade dos dados apontar onde alinhar a planilha."""
    linhas = _linhas()                                      # #IT-1 nas linhas 5 e 8, mesma data
    docs = montar_dados_painel(linhas, _base(), hoje=HOJE)["documentos"]
    assert not any(d["datas_divergentes"] for d in docs)

    linhas[4].data_prevista = date(2026, 5, 20)
    docs = montar_dados_painel(linhas, _base(), hoje=HOJE)["documentos"]
    assert [d["datas_divergentes"] for d in docs] == [True, False, False]
    assert docs[0]["prevista"] == "2026-03-10"              # vale a 1ª linha

    linhas[4].data_prevista = date(2026, 3, 10)
    linhas[4].data_reprogramada = date(2026, 8, 1)          # só a reprogramada difere
    assert montar_dados_painel(linhas, _base(), hoje=HOJE)["documentos"][0]["datas_divergentes"]


def test_codigo_com_dois_tracking_ids_fica_marcado_como_ambiguo():
    b = base(_doc_reprovado_e_reemitido(),
             HistoricoBuilder("T9", "#IT-1", "CMI-9", "OUTRO DOC").evento("0A", 1, "Em Processo", "01/06/2026"))
    linhas = [ln for ln in _linhas() if ln.cod_itaipu in ("#IT-1",)][:1]
    linhas[0].cod_cmi = ""                                  # sem CMI: só o Itaipu, que dois documentos usam
    d = montar_dados_painel(linhas, b, hoje=HOJE)["documentos"][0]
    assert d["ambiguo"] and d["tracking"] == "T9"          # desempate: alteração mais recente
