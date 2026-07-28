"""Leitura do Controle de Documentos e a busca das datas previstas (KB §24.12).

Regressões da rodada em que o usuário reportou "vários documentos com data no
Controle não foram para o mapeamento, sendo que um Ctrl+F acha na hora". Cada
teste aqui trava uma das causas encontradas.
"""
from datetime import date

import openpyxl
import pandas as pd
from builders import HistoricoBuilder, base, escrever_controle_xlsx

from docmanager.services.controle_docs import (
    ControleDocs,
    ControleRow,
    _col,
    _infer_dayfirst,
    _norm,
    _parse_col_datas,
    chave_frouxa,
    ler_controle,
)
from docmanager.services.mapping_update import atualizar_mapeamento

HOJE = date(2026, 7, 27)


def _row(itaipu="", cmi="", prevista=None, reprog=None, fase=""):
    return ControleRow(cod_itaipu=itaipu, cod_cmi=cmi, titulo="t",
                       data_prevista=prevista, data_reprogramada=reprog, fase=fase)


# ---------------------------------------------------------------------------
# Causa 1 — cabeçalho com QUEBRA DE LINHA dentro da célula
# ---------------------------------------------------------------------------
def test_norm_colapsa_quebra_de_linha_do_cabecalho():
    assert _norm("DATA PREVISTA DE\nEMISSÃO  ACONEX") == "DATA PREVISTA DE EMISSAO ACONEX"
    assert _norm("  REPROGRAMAÇÃO\t") == "REPROGRAMACAO"


def test_col_acha_cabecalho_quebrado_em_duas_linhas():
    df = pd.DataFrame(columns=["ITEM", "DATA PREVISTA DE\nEMISSÃO ACONEX", "REPROGRAMAÇÃO"])
    assert _col(df, "DATA PREVISTA DE EMISSÃO ACONEX") == "DATA PREVISTA DE\nEMISSÃO ACONEX"
    assert _col(df, "REPROGRAMA") == "REPROGRAMAÇÃO"


def test_col_acha_cabecalho_com_palavra_a_mais():
    """Terceiro nível do casamento: todas as palavras do alvo presentes."""
    df = pd.DataFrame(columns=["DATA PREVISTA DE EMISSÃO NO ACONEX"])
    assert _col(df, "DATA PREVISTA DE EMISSÃO ACONEX") == "DATA PREVISTA DE EMISSÃO NO ACONEX"


def test_controle_le_datas_com_cabecalho_quebrado(tmp_path):
    caminho = escrever_controle_xlsx(
        tmp_path / "ctrl.xlsx",
        [{"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "01-09-2026"}],
        cabecalhos={"prevista": "DATA PREVISTA DE\nEMISSÃO ACONEX"})
    ctrl = ler_controle(caminho, 0, log_cb=lambda _m: None)
    assert ctrl.linha_por_codigo("#IT-1").data_prevista == date(2026, 9, 1)


# ---------------------------------------------------------------------------
# Causa 2 — coluna com FORMATOS MISTOS zerava tudo após a primeira linha
# ---------------------------------------------------------------------------
def test_data_real_do_excel_no_topo_nao_zera_o_resto_da_coluna():
    serie = pd.Series(["2026-10-13 00:00:00", "10/20/2026", "5/30/2035"])
    assert _parse_col_datas(serie) == [date(2026, 10, 13), date(2026, 10, 20), date(2035, 5, 30)]


def test_dayfirst_por_votacao_ignora_datas_iso():
    # ISO não é ambígua e não vota; as duas M/D decidem a coluna.
    assert _infer_dayfirst(pd.Series(["2026-10-13 00:00:00", "10/20/2026", "5/30/2035"])) is False
    assert _infer_dayfirst(pd.Series(["30-11-2026", "17-07-2026"])) is True


def test_serial_do_excel_e_convertido():
    assert _parse_col_datas(pd.Series(["45678"])) == [date(2025, 1, 21)]
    assert _parse_col_datas(pd.Series(["1234"])) == [None]     # fora da janela: não é data


# ---------------------------------------------------------------------------
# Causa 3 — linha SEM data escondendo a linha COM data
# ---------------------------------------------------------------------------
def test_linha_sem_data_nao_sombreia_a_com_data_pelo_codigo_preferido():
    """O código Itaipu do mapeamento casa com uma linha vazia; o código CMI casa
    com a linha preenchida. Antes, o preferido vencia mesmo vazio."""
    ctrl = ControleDocs([_row(itaipu="#IT-1"),
                         _row(cmi="CMI-1", prevista=date(2026, 5, 5))])
    m = ctrl.resolver([], "#IT-1", "CMI-1")
    assert m.linha.data_prevista == date(2026, 5, 5)


def test_sem_nenhuma_linha_com_data_devolve_a_primeira():
    ctrl = ControleDocs([_row(itaipu="#IT-1", fase="FABRICAÇÃO")])
    m = ctrl.resolver([], "#IT-1", "")
    assert m.linha.fase == "FABRICAÇÃO" and m.via == "exato"


# ---------------------------------------------------------------------------
# Causa 4 — cascata de busca (o "Ctrl+F na mão")
# ---------------------------------------------------------------------------
def test_chave_frouxa_ignora_pontuacao():
    assert chave_frouxa("#ST00=M00MYA10&EAB010") == "ST00M00MYA10EAB010"
    assert chave_frouxa("#ST00-M00MYA10 EAB010") == chave_frouxa("#ST00=M00MYA10&EAB010")


def test_busca_frouxa_acha_codigo_com_pontuacao_diferente():
    ctrl = ControleDocs([_row(itaipu="#ST00-M00MYA10 EAB010", prevista=date(2026, 3, 3))])
    m = ctrl.resolver([], "#ST00=M00MYA10&EAB010", "")
    assert m.via == "frouxo" and m.linha.data_prevista == date(2026, 3, 3)


def test_busca_por_conteudo_acha_codigo_com_texto_em_volta():
    ctrl = ControleDocs([_row(itaipu="ver doc 08934100CJA10-FS00AB-01 (rev)",
                              prevista=date(2026, 4, 4))])
    m = ctrl.resolver([], "08934100CJA10-FS00AB-01", "")
    assert m.via == "contido" and m.linha.data_prevista == date(2026, 4, 4)


def test_codigo_curto_nao_dispara_fallback():
    """Fallback com código curto casaria com qualquer coisa — fica desligado."""
    ctrl = ControleDocs([_row(itaipu="ABC-123456789", prevista=date(2026, 1, 1))])
    assert ctrl.resolver([], "ABC", "").linha is None


# ---------------------------------------------------------------------------
# Causa 5 — documento fora do Aconex nunca recebia data no mapeamento
# ---------------------------------------------------------------------------
_COLS_MAPA = [
    "GRUPO", "Nº CMI", "N° ITAIPU", "DESCRIÇÃO DO DOCUMENTO", "NÍVEL",
    "DATA PREVISTA EMISSÃO ETAPA 1", "DATA REPROGRAMADA", "EMITIDO / NÃO EMITIDO",
    "DATA ÚLTIMA EMISSÃO", "ÚLTIMA REV. EMITIDA", "STATUS REAL", "STATUS",
    "STATUS CONSOLIDADO", "COM ITAIPU", "PLANO DE EXECUÇÃO", "PREDECESSOR",
    "TAG ETAPA", "RESUMO QUANTIDADES", "SITUAÇÃO DO PRAZO",
]


def test_documento_nao_emitido_recebe_data_prevista_do_controle(tmp_path):
    """Regressão do portão `not df_tracking.empty`: o documento que ainda NÃO
    está no Aconex é justamente o que mais precisa da data planejada."""
    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC EMITIDO")
             .evento("0A", 1, "Em Processo", "01/09/2025", current=True))
    base_path = tmp_path / "base.xlsx"
    b.to_excel(base_path, index=False)

    mapa_path = tmp_path / "mapa.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    for c, nome in enumerate(_COLS_MAPA, 1):
        ws.cell(1, c, nome)
    for i, (cmi, itaipu, desc) in enumerate(
            [("CMI-1", "#IT-1", "DOC EMITIDO"), ("CMI-2", "#IT-2", "DOC NUNCA EMITIDO")], start=3):
        ws.cell(i, 1, "SALAS")
        ws.cell(i, 2, cmi)
        ws.cell(i, 3, itaipu)
        ws.cell(i, 4, desc)
        ws.cell(i, 5, "4")
    wb.save(mapa_path)

    ctrl_path = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "01-09-2025"},
        {"itaipu": "#IT-2", "cmi": "CMI-2", "prevista": "05-08-2026"},
    ])
    controle = ler_controle(ctrl_path, 0, log_cb=lambda _m: None)

    r = atualizar_mapeamento(str(base_path), str(mapa_path), controle=controle,
                             hoje=HOJE, log_cb=lambda _m: None)
    assert r.ok

    ws2 = openpyxl.load_workbook(mapa_path).active
    col_prev = _COLS_MAPA.index("DATA PREVISTA EMISSÃO ETAPA 1") + 1
    assert str(ws2.cell(3, col_prev).value).startswith("2025-09-01")
    # A linha 4 (fora do Aconex) também recebe — era o que sumia.
    assert str(ws2.cell(4, col_prev).value).startswith("2026-08-05")


def test_log_de_diagnostico_nomeia_quem_nao_casou(tmp_path):
    """A falha era silenciosa: sem data, o resultado era igual ao de rodar sem
    Controle. Agora o log conta o placar e nomeia os ausentes."""
    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC")
             .evento("0A", 1, "Em Processo", "01/09/2025", current=True))
    base_path = tmp_path / "base.xlsx"
    b.to_excel(base_path, index=False)

    mapa_path = tmp_path / "mapa.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    for c, nome in enumerate(_COLS_MAPA, 1):
        ws.cell(1, c, nome)
    ws.cell(3, 1, "SALAS"), ws.cell(3, 2, "CMI-9"), ws.cell(3, 3, "#IT-9")
    ws.cell(3, 4, "DOC FORA DO CONTROLE"), ws.cell(3, 5, "4")
    wb.save(mapa_path)

    ctrl_path = escrever_controle_xlsx(
        tmp_path / "ctrl.xlsx", [{"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "01-09-2025"}])
    controle = ler_controle(ctrl_path, 0, log_cb=lambda _m: None)

    linhas = []
    atualizar_mapeamento(str(base_path), str(mapa_path), controle=controle,
                         hoje=HOJE, log_cb=linhas.append)
    texto = "\n".join(linhas)
    assert "SEM correspondência no Controle" in texto
    assert "#IT-9" in texto


# ---------------------------------------------------------------------------
# §24.13 — Mapa adotou as regras de data do Doc List
# ---------------------------------------------------------------------------
def _resolver(prevista_celula, reprogramada_celula, prevista_ctrl, reprogramada_ctrl):
    from docmanager.core.mapping import resolver_datas_controle
    ctrl = ControleDocs([_row(itaipu="#IT-1", prevista=prevista_ctrl, reprog=reprogramada_ctrl)])
    return resolver_datas_controle(prevista_celula, [], "#IT-1", "", ctrl,
                                   valor_celula_reprogramada=reprogramada_celula)


def test_prevista_do_controle_mais_recente_atualiza_a_celula():
    """Antes o Mapa só escrevia na célula vazia — uma data nova no Controle
    nunca chegava ao mapeamento."""
    d = _resolver(date(2026, 3, 1), None, date(2026, 9, 1), None)
    assert d.prevista_para_celula == date(2026, 9, 1)
    assert d.prevista_atualizada
    assert d.data_ref == date(2026, 9, 1)      # o atraso passa a usar a nova


def test_prevista_da_planilha_mais_recente_e_preservada_no_mapa():
    d = _resolver(date(2026, 9, 1), None, date(2026, 3, 1), None)
    assert d.prevista_para_celula is None
    assert d.data_ref == date(2026, 9, 1)      # atraso usa a da planilha, não a do Controle


def test_celula_vazia_recebe_a_prevista_sem_marcar_atualizacao():
    d = _resolver(None, None, date(2026, 3, 1), None)
    assert d.prevista_para_celula == date(2026, 3, 1) and not d.prevista_atualizada


def test_reprogramada_digitada_na_planilha_nao_e_mais_sobrescrita():
    """Regressão: o Mapa reescrevia essa coluna a cada rodada, apagando o input
    manual da equipe."""
    d = _resolver(date(2026, 1, 1), date(2026, 8, 8), date(2026, 1, 1), date(2026, 5, 5))
    assert d.reprogramada is None
    assert d.data_ref == date(2026, 8, 8)      # e é a manual que vale


def test_reprogramada_vazia_e_preenchida_pelo_controle():
    d = _resolver(date(2026, 1, 1), None, date(2026, 1, 1), date(2026, 5, 5))
    assert d.reprogramada == date(2026, 5, 5) and d.data_ref == date(2026, 5, 5)


def test_sem_match_no_controle_data_ref_vem_da_planilha():
    from docmanager.core.mapping import resolver_datas_controle
    ctrl = ControleDocs([_row(itaipu="#OUTRO", prevista=date(2026, 1, 1))])
    d = resolver_datas_controle(date(2026, 6, 6), [], "#IT-1", "", ctrl,
                                valor_celula_reprogramada=None)
    assert d.via == "" and d.prevista_para_celula is None
    assert d.data_ref == date(2026, 6, 6)


def test_mapa_e_doclist_concordam_nas_datas():
    """As duas implementações têm de dar o MESMO resultado para o mesmo caso."""
    from docmanager.core.doclist import resolver_datas_doclist
    from docmanager.core.mapping import resolver_datas_controle

    casos = [
        (date(2026, 3, 1), None, date(2026, 9, 1), None),
        (date(2026, 9, 1), None, date(2026, 3, 1), None),
        (None, None, date(2026, 3, 1), date(2026, 5, 5)),
        (date(2026, 1, 1), date(2026, 8, 8), date(2026, 1, 1), date(2026, 5, 5)),
        (None, None, None, None),
    ]
    for prev_cel, reprog_cel, prev_ctrl, reprog_ctrl in casos:
        ctrl = ControleDocs([_row(itaipu="#IT-1", prevista=prev_ctrl, reprog=reprog_ctrl)])
        m = resolver_datas_controle(prev_cel, [], "#IT-1", "", ctrl,
                                    valor_celula_reprogramada=reprog_cel)
        d = resolver_datas_doclist(prevista_atual=prev_cel, reprogramada_atual=reprog_cel,
                                   fase_atual="", codigos=[], cod_itaipu_atual="#IT-1",
                                   cod_cmi_atual="", controle=ctrl)
        assert (m.prevista_para_celula, m.reprogramada, m.data_ref) == \
               (d.prevista, d.reprogramada, d.data_alvo), (prev_cel, reprog_cel, prev_ctrl, reprog_ctrl)


def test_mapa_end_to_end_respeita_input_manual(tmp_path):
    """Planilha com prevista antiga e reprogramada digitada; Controle com
    prevista nova e outra reprogramação."""
    b = base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC")
             .evento("0A", 1, "Em Processo", "01/09/2025", current=True))
    base_path = tmp_path / "base.xlsx"
    b.to_excel(base_path, index=False)

    mapa_path = tmp_path / "mapa.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    for c, nome in enumerate(_COLS_MAPA, 1):
        ws.cell(1, c, nome)
    ws.cell(3, 1, "SALAS"), ws.cell(3, 2, "CMI-1"), ws.cell(3, 3, "#IT-1")
    ws.cell(3, 4, "DOC"), ws.cell(3, 5, "4")
    ws.cell(3, _COLS_MAPA.index("DATA PREVISTA EMISSÃO ETAPA 1") + 1, date(2026, 1, 1))
    ws.cell(3, _COLS_MAPA.index("DATA REPROGRAMADA") + 1, date(2026, 12, 25))
    wb.save(mapa_path)

    ctrl_path = escrever_controle_xlsx(tmp_path / "ctrl.xlsx", [
        {"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "30-06-2026", "reprog": "5/5/2026"}])
    controle = ler_controle(ctrl_path, 0, log_cb=lambda _m: None)
    assert atualizar_mapeamento(str(base_path), str(mapa_path), controle=controle,
                                hoje=HOJE, log_cb=lambda _m: None).ok

    ws2 = openpyxl.load_workbook(mapa_path).active
    prevista = ws2.cell(3, _COLS_MAPA.index("DATA PREVISTA EMISSÃO ETAPA 1") + 1).value
    reprog = ws2.cell(3, _COLS_MAPA.index("DATA REPROGRAMADA") + 1).value
    assert str(prevista).startswith("2026-06-30")   # Controle é mais recente → atualiza
    assert str(reprog).startswith("2026-12-25")     # input manual preservado


def test_controle_sem_nenhuma_data_avisa(tmp_path):
    caminho = escrever_controle_xlsx(tmp_path / "ctrl.xlsx",
                                     [{"itaipu": "#IT-1", "cmi": "CMI-1"}])
    linhas = []
    ler_controle(caminho, 0, log_cb=linhas.append)
    assert any("nenhuma linha do Controle tem data" in m for m in linhas)
