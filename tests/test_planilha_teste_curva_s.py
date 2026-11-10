"""Planilha de teste do painel (tools/planilha_teste_curva_s.py): as regras da página
Projeção do Power BI (passo 12 do roteiro) e o que a aba Esperado promete.

As funções são o gabarito das medidas DAX do roteiro: se uma regra mudar aqui, o roteiro
muda junto.
"""
from datetime import date

import openpyxl

from tools import planilha_teste_curva_s as p

HOJE = date(2026, 11, 10)


def test_realizado_entra_na_1a_emissao_ou_na_prevista_se_ja_teve_revisao():
    prevista = date(2026, 10, 20)
    assert p.entrada_realizado(prevista, date(2026, 9, 1), None) == date(2026, 9, 1)
    assert p.entrada_realizado(prevista, date(2026, 9, 1), date(2026, 9, 1)) == date(2026, 9, 1)
    # revisão depois da 1ª emissão: a data do Doc List é de revisão posterior
    assert p.entrada_realizado(prevista, date(2025, 3, 10), date(2026, 8, 5)) == prevista
    # ... mas quem saiu atrasado entra no dia em que saiu
    assert p.entrada_realizado(prevista, date(2026, 11, 2), date(2026, 11, 9)) == date(2026, 11, 2)
    assert p.entrada_realizado(prevista, None, None) is None
    assert p.entrada_realizado(None, date(2026, 9, 1), None) is None


def test_projecao_poe_o_pendente_na_data_alvo_se_ela_nao_venceu():
    prevista = date(2026, 9, 5)
    assert p.entrada_projecao(prevista, date(2027, 3, 31), None, None, HOJE) == date(2027, 3, 31)
    assert p.entrada_projecao(prevista, HOJE, None, None, HOJE) == HOJE
    assert p.entrada_projecao(prevista, prevista, None, None, HOJE) is None  # vencido, sem data nova
    assert p.entrada_projecao(prevista, None, None, None, HOJE) is None
    assert p.entrada_projecao(prevista, prevista, date(2026, 9, 1), None, HOJE) == date(2026, 9, 1)


def test_a_recuperar_e_o_pendente_vencido_contra_a_prevista():
    assert p.grupo_recuperar(HOJE, HOJE, None, HOJE) is None  # vence hoje: ainda no prazo
    assert p.grupo_recuperar(date(2026, 11, 9), date(2026, 11, 9), None, HOJE) == p.SEM_DATA_NOVA
    assert p.grupo_recuperar(date(2026, 11, 9), None, None, HOJE) == p.SEM_DATA_NOVA
    assert p.grupo_recuperar(date(2026, 11, 9), HOJE, None, HOJE) == p.COM_DATA_NOVA
    assert p.grupo_recuperar(date(2026, 11, 9), date(2027, 1, 5), date(2026, 11, 9), HOJE) is None


def test_pagina_projecao_com_os_documentos_de_exemplo():
    linhas = list(p._linhas(HOJE))
    atrasados = [(g, x["cod"]) for g, x in p.a_recuperar(linhas, HOJE)]
    assert atrasados == [(p.SEM_DATA_NOVA, "TESTE-05"), (p.COM_DATA_NOVA, "TESTE-10"),
                         (p.COM_DATA_NOVA, "TESTE-09")]
    # hoje: 3 atrasados menos 1 adiantado de verdade (TESTE-06) = 2 abaixo da baseline
    assert p.curva_do_projeto(linhas, HOJE, HOJE) == (9, 7, 7)
    assert p.curva_do_projeto(linhas, HOJE, date(2026, 10, 31)) == (9, 7, None)
    assert p.curva_do_projeto(linhas, HOJE, date(2026, 12, 31)) == (12, None, 9)
    assert p.curva_do_projeto(linhas, HOJE, date(2027, 2, 28)) == (12, None, 10)
    # no fim, o vão é o sem data nova (TESTE-05)
    assert p.curva_do_projeto(linhas, HOJE, p.FIM_DO_EIXO) == (12, None, 11)


def test_documentos_da_projecao_nao_mudam_o_que_outubro_mostra():
    linhas = list(p._linhas(HOJE))
    assert p._contar(linhas, "alvo", date(2026, 10, 28)) == (6, 6)
    assert p._contar(linhas, "prev", date(2026, 10, 28)) == (7, 6)
    assert p._cartao(linhas, "alvo", "sit") == ("66,7%", "5/6")
    assert p._cartao(linhas, "prev", "otd") == ("42,9%", "5/7")
    assert p._cartao(linhas, "reprog", "say") == ("100,0%", "1/1")


def test_aba_esperado_traz_a_pagina_projecao(tmp_path):
    caminho = tmp_path / "teste.xlsx"
    p.gerar(caminho, HOJE)
    ws = openpyxl.load_workbook(caminho)["Esperado"]
    linhas = [[c.value for c in r] for r in ws.iter_rows()]
    i = next(k for k, r in enumerate(linhas) if r[0] == "Cartão A recuperar")
    assert linhas[i + 1][2:4] == [3, "2 COM DATA NOVA · 1 SEM DATA NOVA"]
    assert any(str(r[0]).startswith("No fim do eixo, a diferença entre a baseline e a projeção é 1:")
               for r in linhas)
    dados = openpyxl.load_workbook(caminho)["Unidade Geradora"]
    assert [dados.cell(r, 6).value for r in range(4, dados.max_row + 1)][-3:] == [
        "TESTE-10", "TESTE-11", "TESTE-12"]
