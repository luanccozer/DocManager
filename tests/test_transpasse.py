"""Transpasse de Fase: a Planilha1 (quadro de cores por dia) desenhada sozinha
a partir das datas das planilhas de acompanhamento.

Os casos de pintura vêm da própria Planilha1, pintada à mão pela equipe: é ela
a fonte do comportamento esperado (cada cor vai da sua data até a véspera do
próximo marco, sem pintar sábado e domingo; verde e preto ocupam um dia só).
"""
import json
import re
from datetime import date, datetime

import openpyxl
import pytest
from openpyxl.utils import column_index_from_string, get_column_letter

from docmanager.core.transpasse import GrupoLido, montar_quadro, pintar
from docmanager.services.transpasse_io import ler_planilha_complementar, ler_planilha_principal
from docmanager.transpasse_backend import gerar_painel_transpasse

HOJE = date(2026, 10, 27)
SALA_50 = "SALA SEGURA 50 Hz"
SALA_60 = "SALA SEGURA 60 Hz"


def d(dia, mes=9):
    return date(2026, mes, dia)


def lido(ident="GEQ-001-002", sala=SALA_50, nome="DISTRIBUIÇÃO CA 460VAC", **datas):
    return GrupoLido(ident, sala, nome, datas)


def unico(principal, complementar=None):
    """O único grupo do quadro montado com uma linha de cada planilha."""
    quadro = montar_quadro([principal], [complementar] if complementar else None, HOJE)
    (grupo,) = quadro.grupos
    return grupo


def test_pinta_um_grupo_completo_como_a_planilha1():
    """GEQ-001-002: convocação e inspeção em 01/09, CCMLC 10/09, transpasse
    17/09 e início 23/09 - na Planilha1, OOOO..OOOBB..BBBG.....K."""
    datas = {"conv": d(1), "insp": d(1), "ccmlc": d(10), "transp": d(17), "inicio": d(23)}

    assert pintar(datas, HOJE) == {
        d(1): "O", d(2): "O", d(3): "O", d(4): "O", d(7): "O", d(8): "O", d(9): "O",
        d(10): "B", d(11): "B", d(14): "B", d(15): "B", d(16): "B",
        d(17): "G", d(23): "K",
    }


def test_etapa_em_andamento_vai_ate_hoje():
    """Convocado em 14/10 e ainda sem inspeção: o vermelho segue até hoje (27/10)."""
    vermelhos = pintar({"conv": d(14, 10)}, HOJE)

    assert sorted(vermelhos) == [d(x, 10) for x in (14, 15, 16, 19, 20, 21, 22, 23, 26, 27)]
    assert set(vermelhos.values()) == {"R"}


def test_depois_do_transpasse_fica_em_branco_ate_o_inicio():
    """Entre o verde e o preto a Planilha1 deixa os dias em branco - também
    quando o comissionamento ainda não começou."""
    assert pintar({"conv": d(28), "insp": d(28), "ccmlc": d(28), "transp": d(28)}, HOJE) == {d(28): "G"}


# ─────────────────────────── junção das duas planilhas ───────────────────────

def test_complementar_traz_o_inicio_e_os_dias_contam_os_dois_extremos():
    """A principal não tem o início do comissionamento; a complementar tem.
    'Dias' conta da convocação ao início incluindo os dois dias, como a coluna
    da Planilha1 (01/09 → 23/09 = 23)."""
    grupo = unico(lido(conv=d(1), insp=d(1), ccmlc=d(10), transp=d(17)),
                  lido(conv=d(1), inicio=d(23)))

    assert grupo.datas["inicio"] == d(23)
    assert grupo.celulas[d(23)] == "K"
    assert grupo.dias == 23
    assert grupo.avisos == []


def test_sem_inicio_nao_ha_dias():
    assert unico(lido(conv=d(1), insp=d(1), ccmlc=d(10), transp=d(17))).dias is None


def test_datas_diferentes_vale_a_principal_e_o_card_mostra_a_outra():
    """GEQ-001-010: CCMLC em 08/10 numa planilha e 14/10 na outra."""
    grupo = unico(lido(conv=d(6, 10), insp=d(8, 10), ccmlc=d(8, 10), transp=d(14, 10)),
                  lido(conv=d(6, 10), insp=d(8, 10), ccmlc=d(14, 10), transp=d(14, 10)))

    assert grupo.datas["ccmlc"] == d(8, 10)
    assert grupo.avisos == ["Na planilha complementar: Emissão CCMLC = 14/10/2026"]


def test_data_fora_de_ordem_na_principal_cede_lugar_a_da_complementar():
    """GEQ-001-016: na principal o CCMLC (10/09) é anterior à inspeção (15/09)."""
    grupo = unico(lido(conv=d(14), insp=d(15), ccmlc=d(10), transp=d(15)),
                  lido(conv=d(14), insp=d(15), ccmlc=d(15), transp=d(15)))

    assert grupo.datas["ccmlc"] == d(15)
    assert grupo.avisos == [
        "Na planilha principal: Emissão CCMLC = 10/09/2026 (fora de ordem: antes de Inspeção IB, 15/09/2026)"]


def test_data_no_futuro_nao_entra_e_a_etapa_segue_em_andamento():
    """Todos os marcos são de coisas que JÁ aconteceram: data depois de hoje é erro."""
    grupo = unico(lido(conv=d(14, 10), insp=d(30, 10)))

    assert grupo.datas["insp"] is None
    assert grupo.avisos == ["Na planilha principal: Inspeção IB = 30/10/2026 (data no futuro)"]
    assert grupo.celulas[d(27, 10)] == "R"


def test_ano_digitado_errado_no_inicio_nao_entra():
    """GEQ-001-027: início do comissionamento digitado como 19/10/2020."""
    grupo = unico(lido(conv=d(28), insp=d(2, 10), ccmlc=d(5, 10), transp=d(9, 10)),
                  lido(inicio=date(2020, 10, 19)))

    assert grupo.datas["inicio"] is None and grupo.dias is None
    assert grupo.avisos == ["Na planilha complementar: Início do comissionamento = 19/10/2020 "
                            "(data improvável: mais de um ano antes das demais)"]


def test_convocacao_com_ano_errado_nao_estica_o_quadro():
    """Uma convocação de 2020 no meio de um quadro de 2026 é erro de digitação:
    ficaria fora de ordem só se houvesse marco anterior, e não há."""
    quadro = montar_quadro([lido("GEQ-001-001", conv=date(2020, 9, 14)),
                            lido("GEQ-001-002", conv=d(1), insp=d(1)),
                            lido("GEQ-001-003", conv=d(21), insp=d(22))], None, HOJE)
    errado = quadro.grupos[0]

    assert errado.datas["conv"] is None
    assert errado.avisos == ["Na planilha principal: Convocação = 14/09/2020 "
                             "(data improvável: mais de um ano antes das demais)"]
    assert quadro.inicio == d(1)


def test_grupo_que_so_existe_na_complementar_entra_na_mesma_sala_da_principal():
    """A complementar chama a sala de '60HZ'; o grupo novo vai para o bloco
    'SALA SEGURA 60 Hz' da principal, depois dos grupos dela."""
    principal = [lido("GEQ-001-041", SALA_60, "DCIM", conv=d(1)), lido("GEQ-001-001", SALA_50, conv=d(1))]
    complementar = [lido("GEQ-001-044", "60HZ", "Piso Elevado")]

    quadro = montar_quadro(principal, complementar, HOJE)

    assert [(g.id, g.sala) for g in quadro.grupos] == [
        ("GEQ-001-041", SALA_60), ("GEQ-001-044", SALA_60), ("GEQ-001-001", SALA_50)]


def test_mesmo_numero_com_outro_grupo_na_complementar_avisa_no_card():
    grupo = unico(lido("GEQ-001-040", SALA_60, "SISTEMA DE CONTROLE DE ACESSO (CA), CFTV"),
                  lido("GEQ-001-040", "60HZ", "Sistema de Exaustão da Sala de baterias", conv=d(19, 10)))

    assert grupo.avisos == ["Na planilha complementar, este número é “Sistema de Exaustão da Sala de baterias” "
                            "- confira se as datas são deste grupo"]


def test_numero_com_outro_grupo_sem_datas_so_aponta_a_diferenca():
    """Sem data vinda da complementar, não há o que conferir - só a lista diverge."""
    grupo = unico(lido("GEQ-001-023", SALA_60, "DISTRIBUIÇÃO CA 460VAC", conv=d(1)),
                  lido("GEQ-001-023", "60HZ", "Infraestrutura seca"))

    assert grupo.avisos == ["Na planilha complementar, este número é “Infraestrutura seca”"]


def test_nome_mais_completo_numa_das_planilhas_nao_e_divergencia():
    grupo = unico(lido("GEQ-001-031", SALA_60, "ALIMENTAÇÃO REDUNDANTE SALA ELÉTRICA / SALA SEGURA / INVERSORES",
                       conv=d(8, 10)),
                  lido("GEQ-001-031", "60HZ", "limentação redundante Sala Elétrica / Sala Segura"))

    assert grupo.avisos == []


def test_sala_diferente_na_complementar_tambem_avisa():
    grupo = unico(lido("GEQ-001-022", SALA_60, "INFRAESTRUTURA SECA", conv=d(1)),
                  lido("GEQ-001-022", "50HZ", "Sala Segura e Sala Elétrica"))

    assert grupo.avisos == ["Na planilha complementar, este número é “Sala Segura e Sala Elétrica” e está na "
                            "sala 50HZ"]


# ─────────────────────────── o card (passar o mouse) ─────────────────────────

def test_card_mostra_os_dias_entre_os_marcos_e_o_total():
    """Os intervalos somam 22; o total soma 23 porque conta os dois extremos."""
    grupo = unico(lido(conv=d(1), insp=d(1), ccmlc=d(10), transp=d(17)), lido(inicio=d(23)))

    assert grupo.intervalos == {"conv": None, "insp": 0, "ccmlc": 9, "transp": 7, "inicio": 6}
    assert grupo.rodape == "Dias (convocação → início): 23"


def test_card_de_grupo_parado_diz_o_que_espera_e_ha_quanto_tempo():
    assert unico(lido(conv=d(6, 10), insp=d(8, 10), ccmlc=d(8, 10), transp=d(14, 10))).rodape == \
        "Aguardando o início do comissionamento há 13 dias"
    assert unico(lido(conv=d(26, 10))).rodape == "Aguardando a inspeção há 1 dia"


def test_grupo_sem_convocacao_fica_pendente():
    """Na Planilha1, o código do grupo ainda não convocado fica em amarelo."""
    quadro = montar_quadro([lido("GEQ-001-001"), lido("GEQ-001-002", conv=d(1)),
                            lido("GEQ-001-003", insp=d(2))], None, HOJE)
    sem, com, sem_conv = quadro.grupos

    assert sem.pendente and sem.rodape == "Ainda não convocado"
    assert not com.pendente
    assert sem_conv.pendente and sem_conv.rodape == "Sem data de convocação"


def test_sala_sem_nenhuma_convocacao_fica_fora_do_quadro():
    """A sala de testes ainda não teve grupo convocado: entra quando tiver."""
    quadro = montar_quadro([lido("GEQ-001-002", conv=d(1)), lido("GEQ-012-001", "SALA TESTES (QAS)")], None, HOJE)

    assert [g.id for g in quadro.grupos] == ["GEQ-001-002"]


# ─────────────────────────── leitura das planilhas ───────────────────────────

def dt(dia, mes=9):
    return datetime(2026, mes, dia)


# Cabeçalho da planilha principal como ela é hoje (linha 4), coluna → título.
CABECALHO_PRINCIPAL = {
    "G": "CAPÍTULO", "I": "ID GRUPO EQUIPAMENTOS", "J": "GRUPO EQUIPAMENTOS",
    "K": "DESCRIÇÃO GRUPO EQUIPAMENTOS", "V": "DATA PRÉ-INSPEÇÃO CMI",
    "Z": "CONVOCAÇÃO CONJUNTA REALIZADA EM", "AA": "DATA PREVISTA  INSPEÇÃO CMI/ITAIPU ",
    "AB": "DATA INSPEÇÃO REALIZADA CMI/ITAIPU", "AF": "EMISSÃO CCMLC", "AH": "Nº CCMLC",
    "AI": "DATA EMISSÃO CCMLC", "AJ": "CCMLC DISPONÍVEL NO UNIFIER", "AM": "DATA TRANSPASSE FASE",
}


def planilha_principal(caminho, linhas, cabecalho=CABECALHO_PRINCIPAL):
    """Uma aba qualquer antes; na aba de dados, título na linha 2, cabeçalho na
    4, SIM/NÃO na 5 e os grupos a partir da 7. `linhas`: dicts título → valor."""
    wb = openpyxl.Workbook()
    wb.active.title = "Resumo"
    wb.active["B2"] = "outra aba"
    ws = wb.create_sheet("CONCLUSÃO MONTAGEM - CCMLC")
    ws["B2"] = "PAT_OBJ1 - ACOMPANHAMENTO DE TRANSPASSE DE FASES"
    for col, titulo in cabecalho.items():
        ws[f"{col}4"] = titulo
    ws["AF5"], ws["AG5"] = "SIM", "NÃO"
    coluna = {titulo: col for col, titulo in cabecalho.items()}
    for i, valores in enumerate(linhas):
        for titulo, valor in valores.items():
            ws[f"{coluna[titulo]}{7 + i}"] = valor
    wb.save(caminho)
    return caminho


def test_le_a_planilha_principal_pelos_titulos_das_colunas(tmp_path):
    caminho = planilha_principal(tmp_path / "acompanhamento.xlsx", [
        {"ID GRUPO EQUIPAMENTOS": "GEQ-001-002", "CAPÍTULO": "SALA SEGURA 50 Hz",
         "GRUPO EQUIPAMENTOS": "DISTRIBUIÇÃO CA 460VAC", "CONVOCAÇÃO CONJUNTA REALIZADA EM": dt(1),
         "DATA PREVISTA  INSPEÇÃO CMI/ITAIPU ": "=Z7+3", "DATA INSPEÇÃO REALIZADA CMI/ITAIPU": dt(1),
         "DATA EMISSÃO CCMLC": dt(10), "CCMLC DISPONÍVEL NO UNIFIER": dt(17), "DATA TRANSPASSE FASE": dt(17)},
        {"ID GRUPO EQUIPAMENTOS": "GEQ-001-003", "CAPÍTULO": "SALA SEGURA 50 Hz",
         "GRUPO EQUIPAMENTOS": "ALIMENTAÇÃO ELÉTRICA DO SISTEMA DE AR_x000D_\nCONDICIONADO"},
    ])

    assert ler_planilha_principal(caminho) == [
        GrupoLido("GEQ-001-002", "SALA SEGURA 50 Hz", "DISTRIBUIÇÃO CA 460VAC",
                  {"conv": d(1), "insp": d(1), "ccmlc": d(10), "transp": d(17)}),
        GrupoLido("GEQ-001-003", "SALA SEGURA 50 Hz", "ALIMENTAÇÃO ELÉTRICA DO SISTEMA DE AR CONDICIONADO", {}),
    ]


def test_coluna_inserida_no_meio_nao_desalinha_as_datas(tmp_path):
    """Cada título uma coluna à direita do lugar de hoje."""
    deslocado = {get_column_letter(column_index_from_string(c) + 1): t for c, t in CABECALHO_PRINCIPAL.items()}
    caminho = planilha_principal(tmp_path / "a.xlsx", [
        {"ID GRUPO EQUIPAMENTOS": "GEQ-001-016", "CAPÍTULO": "SALA SEGURA 50 Hz",
         "CONVOCAÇÃO CONJUNTA REALIZADA EM": dt(14), "DATA TRANSPASSE FASE": dt(15)}], deslocado)

    (grupo,) = ler_planilha_principal(caminho)
    assert grupo.datas == {"conv": d(14), "transp": d(15)}


def test_texto_que_nao_e_data_vai_para_o_card(tmp_path):
    """'14/1O/2026' (letra O no lugar do zero) sumiria do quadro sem ninguém
    saber por quê. Vazio, '[Data Início]', '-' e fórmula não são avisados."""
    caminho = planilha_principal(tmp_path / "a.xlsx", [
        {"ID GRUPO EQUIPAMENTOS": "GEQ-001-004", "CAPÍTULO": "SALA SEGURA 50 Hz",
         "CONVOCAÇÃO CONJUNTA REALIZADA EM": "14/1O/2026", "DATA INSPEÇÃO REALIZADA CMI/ITAIPU": "-",
         "DATA EMISSÃO CCMLC": "[Data Início]", "DATA TRANSPASSE FASE": "=AI7+1"}])

    (lido_,) = ler_planilha_principal(caminho)
    assert lido_.datas == {}
    assert lido_.avisos == ["Na planilha principal: Convocação “14/1O/2026” não é uma data"]
    assert montar_quadro([lido_, lido("GEQ-001-002", conv=d(1))], None, HOJE).grupos[0].avisos == lido_.avisos


def test_arquivo_que_nao_e_o_acompanhamento_explica_o_erro(tmp_path):
    caminho = tmp_path / "outra.xlsx"
    openpyxl.Workbook().save(caminho)

    with pytest.raises(ValueError, match="ID GRUPO EQUIPAMENTOS"):
        ler_planilha_principal(caminho)


def test_coluna_de_data_faltando_explica_qual(tmp_path):
    sem_transpasse = {c: t for c, t in CABECALHO_PRINCIPAL.items() if t != "DATA TRANSPASSE FASE"}
    caminho = planilha_principal(tmp_path / "a.xlsx", [], sem_transpasse)

    with pytest.raises(ValueError, match="(?i)data transpasse fase"):
        ler_planilha_principal(caminho)


def cabecalho_complementar(inicio="InicIo do Comissionamento"):
    """Como na planilha: o prazo da etapa vem no próprio título, e o título do
    início do comissionamento muda de grafia de uma aba para a outra."""
    return ["Sala", "Grupo", "Descrição", "Equipamentos", "Execução", "Convocação Inspeção IB \n3 dias",
            "Inspeção IB \n1 dia", "Emissão CCMLC \n1 dia", "Transpasse de fase\n 1 dia",
            "Planilhas Editáveis \n0 dias", "Notificação SMIS-DT \n0 dias", "Emissão SSA+AT\n3 dias",
            inicio, "Término Comissionamento A frio"]


def aba_complementar(wb, nome, sala, pares, inicio="InicIo do Comissionamento"):
    """Cada grupo em duas linhas (Prevista, Realizada), com Sala, Grupo e
    Descrição mescladas nas duas. `pares`: (grupo, descrição, prevista, realizada,
    rótulo da 2ª linha); prevista/realizada são listas F..N."""
    ws = wb.create_sheet(nome)
    ws.append(cabecalho_complementar(inicio))
    for grupo, descricao, prevista, realizada, rotulo in pares:
        ws.append([sala, grupo, descricao, "", "Prevista", *prevista])
        ws.append([None, None, None, None, rotulo, *realizada])
        for col in "ABCD":
            ws.merge_cells(f"{col}{ws.max_row - 1}:{col}{ws.max_row}")


def test_le_a_planilha_complementar_so_pela_linha_realizada(tmp_path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    aba_complementar(wb, "50Hz", "50HZ", [
        (2, "Distribuição CA 460Vac ", ["[Data Início]", "=F2+4", dt(30), "=H2+1"],
         [dt(1), dt(1), dt(10), dt(17), dt(17), dt(17), "=K3+3", dt(23), "=M3+1"], "Realizada"),
        (22, "Sala Segura e Sala Elétrica ", ["[Data Início]"], ["[Data Início]"], "Prevista"),
    ])
    aba_complementar(wb, "60HZ", "60HZ", [
        (24, "Distribuição CA 460Vac ", ["[Data Início]"], [dt(25), dt(1, 10), dt(3, 10), dt(9, 10)], "Realizada"),
    ], inicio="Inico do Comissionamento")
    caminho = tmp_path / "controle.xlsx"
    wb.save(caminho)

    assert ler_planilha_complementar(caminho) == [
        GrupoLido("GEQ-001-002", "50HZ", "Distribuição CA 460Vac",
                  {"conv": d(1), "insp": d(1), "ccmlc": d(10), "transp": d(17), "inicio": d(23)}),
        GrupoLido("GEQ-001-022", "50HZ", "Sala Segura e Sala Elétrica", {}),
        GrupoLido("GEQ-001-024", "60HZ", "Distribuição CA 460Vac",
                  {"conv": d(25), "insp": d(1, 10), "ccmlc": d(3, 10), "transp": d(9, 10)}),
    ]


def test_arquivo_que_nao_e_a_complementar_explica_o_erro(tmp_path):
    caminho = planilha_principal(tmp_path / "acompanhamento.xlsx", [])

    with pytest.raises(ValueError, match="complementar"):
        ler_planilha_complementar(caminho)


# ─────────────────────────── o painel (arquivo HTML) ─────────────────────────

GRUPO_002 = {"ID GRUPO EQUIPAMENTOS": "GEQ-001-002", "CAPÍTULO": "SALA SEGURA 50 Hz",
             "GRUPO EQUIPAMENTOS": "DISTRIBUIÇÃO CA 460VAC", "CONVOCAÇÃO CONJUNTA REALIZADA EM": dt(1),
             "DATA INSPEÇÃO REALIZADA CMI/ITAIPU": dt(1), "DATA EMISSÃO CCMLC": dt(10), "DATA TRANSPASSE FASE": dt(17)}


def complementar_com_inicio(caminho, grupo=2, inicio=dt(23)):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    aba_complementar(wb, "50Hz", "50HZ", [(grupo, "Distribuição CA 460Vac", [], [None] * 7 + [inicio], "Realizada")])
    wb.save(caminho)
    return caminho


def dados_do_painel(caminho) -> dict:
    """O contrato entre o Python e a página: o JSON embutido no HTML."""
    html = caminho.read_text(encoding="utf-8")
    return json.loads(re.search(r'<script id="dados" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_gera_o_painel_com_o_quadro_das_duas_planilhas(tmp_path):
    saida = tmp_path / "painel.html"

    r = gerar_painel_transpasse(planilha_principal(tmp_path / "a.xlsx", [GRUPO_002]), saida,
                                complementar_com_inicio(tmp_path / "c.xlsx"), hoje=HOJE)

    assert r.ok and r.grupos == 1
    dados = dados_do_painel(saida)
    assert (dados["inicio"], dados["fim"], dados["hoje"]) == ("2026-09-01", "2026-10-31", "2026-10-27")
    (grupo,) = dados["grupos"]
    assert grupo["id"] == "GEQ-001-002" and grupo["sala"] == "SALA SEGURA 50 Hz"
    assert (grupo["dias"], grupo["rodape"]) == (23, "Dias (convocação → início): 23")
    assert grupo["celulas"]["2026-09-01"] == "O" and grupo["celulas"]["2026-09-17"] == "G"
    assert grupo["celulas"]["2026-09-23"] == "K" and "2026-09-05" not in grupo["celulas"]
    assert grupo["datas"]["ccmlc"] == "2026-09-10" and grupo["intervalos"]["ccmlc"] == 9


def test_sem_a_complementar_o_painel_sai_sem_o_inicio(tmp_path):
    saida = tmp_path / "painel.html"

    r = gerar_painel_transpasse(planilha_principal(tmp_path / "a.xlsx", [GRUPO_002]), saida, hoje=HOJE)

    assert r.ok
    (grupo,) = dados_do_painel(saida)["grupos"]
    assert "K" not in grupo["celulas"].values() and grupo["dias"] is None


def test_painel_usa_a_legenda_e_as_cores_da_planilha1(tmp_path):
    saida = tmp_path / "painel.html"
    gerar_painel_transpasse(planilha_principal(tmp_path / "a.xlsx", [GRUPO_002]), saida, hoje=HOJE)
    html = saida.read_text(encoding="utf-8")

    for linha in ("Vermelho: data de convocação IB p/ inspeção conjunta",
                  "Laranja: data da inspeção efetivamente realizada por IB", "Azul: data emissão CCMLC",
                  "Verde: data do transpasse de fase (CCMLC emitido via UNIFIER)",
                  "Preto: data do início efetivo da execução do comissionamento, quando time manutenção "
                  "chega no local para execução"):
        assert linha in html
    for cor in ("#FF0000", "#FFC000", "#00B0F0", "#92D050", "#000000", "#FFF2CC", "#FFFF00"):
        assert cor in html


def test_planilha_errada_vira_mensagem_e_nao_gera_arquivo(tmp_path):
    vazia = tmp_path / "vazia.xlsx"
    openpyxl.Workbook().save(vazia)
    saida = tmp_path / "painel.html"

    r = gerar_painel_transpasse(vazia, saida, hoje=HOJE)

    assert not r.ok and "ID GRUPO EQUIPAMENTOS" in r.mensagem
    assert not saida.exists()
