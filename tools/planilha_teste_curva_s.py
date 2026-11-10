"""Planilha de teste do painel: 9 documentos fictícios, um para cada regra da curva S.

Monta um Excel com a aba 'Unidade Geradora' no mesmo layout da planilha real (linha 1
vazia, cabeçalho na linha 2, linha 3 vazia, dados da linha 4) e uma aba 'Esperado' com o
que o Power BI tem de mostrar em outubro/2026: a curva S da Página 1 (ATUAL e OTD) e o
cartão da página Unidade Geradora. As situações são calculadas pelo DocManager, com o
"hoje" dado. Roteiro: docs/power_bi_otd_say_do.md (passo 10, teste com documentos de
exemplo). Uso:

    python tools/planilha_teste_curva_s.py saida.xlsx [AAAA-MM-DD]
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from docmanager.core.doclist import (  # noqa: E402
    classificar_situacao_emissao,
    classificar_situacao_say_do,
)

CABECALHO = ["NÍVEL", "GRUPO", "SISTEMA", "FASE DE PROJETO", "Nº CMI", "N° ITAIPU",
             "DESCRIÇÃO DO DOCUMENTO", "DATA PREVISTA EMISSÃO", "DATA REPROGRAMADA",
             "DATA-ALVO EMISSÃO", "DATA 1ª EMISSÃO", "SITUAÇÃO EMISSÃO", "DIAS DESVIO EMISSÃO",
             "EMITIDO / NÃO EMITIDO", "DATA ÚLTIMA EMISSÃO", "ÚLTIMA REV. EMITIDA", "STATUS REAL",
             "STATUS", "RESPONSIBLE (COE/VENDOR)", "NÍVEL", "STATUS CONSOLIDADO", "COM ITAIPU",
             "PREDECESSOR", "OBSERVAÇÕES", "RESUMO QUANTIDADES", "Column30",
             "SITUAÇÃO OTD", "SITUAÇÃO SAY-DO"]

D = date
# código, caso, prevista, reprogramada, 1ª emissão, última emissão, última revisão
DOCUMENTOS = [
    ("TESTE-01", "previsto 10/10, saiu 08/10: adiantado dentro do mês",
     D(2026, 10, 10), None, D(2026, 10, 8), D(2026, 10, 8), "0A"),
    ("TESTE-02", "previsto 15/10, saiu 25/09 e segue na 1ª revisão: adiantado de verdade",
     D(2026, 10, 15), None, D(2026, 9, 25), D(2026, 9, 25), "0A"),
    ("TESTE-03", "previsto 20/10, saiu em 2025 e já teve revisão: data de revisão posterior",
     D(2026, 10, 20), None, D(2025, 3, 10), D(2026, 8, 5), "0B"),
    ("TESTE-04", "previsto 12/10, saiu 22/10: atrasado dentro do mês",
     D(2026, 10, 12), None, D(2026, 10, 22), D(2026, 10, 22), "0A"),
    ("TESTE-05", "previsto 25/10, não saiu: pendente",
     D(2026, 10, 25), None, None, None, ""),
    ("TESTE-06", "previsto 18/11, saiu 14/10: adiantado de novembro",
     D(2026, 11, 18), None, D(2026, 10, 14), D(2026, 10, 14), "0A"),
    ("TESTE-07", "previsto 20/09, saiu 06/10: atrasado de setembro",
     D(2026, 9, 20), None, D(2026, 10, 6), D(2026, 10, 6), "0A"),
    ("TESTE-08", "previsto 05/10, reprogramado para 28/10, saiu 27/10",
     D(2026, 10, 5), D(2026, 10, 28), D(2026, 10, 27), D(2026, 10, 27), "0A"),
    ("TESTE-09", "previsto 08/10, reprogramado para 16/11, não saiu",
     D(2026, 10, 8), D(2026, 11, 16), None, None, ""),
]
INICIO, FIM = D(2026, 10, 1), D(2026, 10, 31)


def entrada(alvo, emissao, ultima, inicio=INICIO, fim=FIM):
    """O dia em que o documento entra na linha clara: a regra do passo 10 (Emitidos Acum)."""
    if emissao is None or alvo is None:
        return None
    so_primeira = ultima is None or ultima <= emissao
    if inicio <= alvo <= fim:
        return max(emissao, inicio) if so_primeira else max(emissao, alvo)
    if alvo > fim and so_primeira and emissao >= inicio:
        return emissao
    return None


def _linhas(hoje):
    for cod, caso, prev, reprog, em1, ult, rev in DOCUMENTOS:
        alvo = reprog or prev
        cons = "APROVADO" if em1 else "NÃO EMITIDO"
        yield {
            "cod": cod, "caso": caso, "prev": prev, "reprog": reprog, "alvo": alvo, "em1": em1,
            "ult": ult, "rev": rev, "cons": cons,
            "sit": classificar_situacao_emissao(data_primeira_emissao=em1, data_alvo=alvo,
                                                status_consolidado=cons, hoje=hoje),
            "otd": classificar_situacao_emissao(data_primeira_emissao=em1, data_alvo=prev,
                                                status_consolidado=cons, hoje=hoje),
            "say": classificar_situacao_say_do(data_prevista=prev, data_reprogramada=reprog,
                                               data_primeira_emissao=em1, status_consolidado=cons,
                                               hoje=hoje),
        }


def _aba_dados(ws, linhas):
    for c, titulo in enumerate(CABECALHO, 1):
        ws.cell(2, c, titulo).font = Font(bold=True)
    for r, x in enumerate(linhas, 4):
        valores = [2, "TESTE", "TESTE", "EXECUTIVO", f"CMI-{x['cod']}", x["cod"], x["caso"],
                   x["prev"], x["reprog"], x["alvo"], x["em1"], x["sit"], None,
                   "EMITIDO" if x["em1"] else "NÃO EMITIDO", x["ult"], x["rev"],
                   "Aprovado" if x["em1"] else "NÃO EMITIDO", "Aprovado" if x["em1"] else "",
                   "TESTE", 2, x["cons"], "", "", "", "", None, x["otd"], x["say"]]
        for c, v in enumerate(valores, 1):
            cel = ws.cell(r, c, v)
            if isinstance(v, date):
                cel.number_format = "dd/mm/yyyy"


def _contar(linhas, data_do_plano, ate):
    previstos = sum(1 for x in linhas if x[data_do_plano] and INICIO <= x[data_do_plano] <= ate)
    emitidos = sum(1 for x in linhas
                   if (e := entrada(x[data_do_plano], x["em1"], x["ult"])) and e <= ate)
    return previstos, emitidos


def _cartao(linhas, data_do_plano, situacao):
    base = [x for x in linhas if x[data_do_plano] and INICIO <= x[data_do_plano] <= FIM
            and x[situacao] in ("EMITIDO NO PRAZO", "EMITIDO COM ATRASO",
                                "PENDENTE NO PRAZO", "PENDENTE VENCIDO")]
    if not base:
        return "—", "0/0"
    atrasados = sum(1 for x in base if x[situacao] in ("EMITIDO COM ATRASO", "PENDENTE VENCIDO"))
    emitidos = sum(1 for x in base if x[situacao] in ("EMITIDO NO PRAZO", "EMITIDO COM ATRASO"))
    indice = f"{100 * (len(base) - atrasados) / len(base):.1f}%".replace(".", ",")
    return indice, f"{emitidos}/{len(base)}"


def _aba_esperado(ws, linhas, hoje):
    negrito = Font(bold=True)
    ws.append([f"O que o Power BI tem de mostrar com esta planilha, filtro 2026 → outubro "
               f"(situações calculadas em {hoje:%d/%m/%Y})."])
    ws["A1"].font = negrito
    ws.append([])
    ws.append(["Documento", "Caso", "Entra na escura (ATUAL)", "Entra na clara (ATUAL)",
               "Entra na escura (OTD)", "Entra na clara (OTD)"])
    for c in ws[3]:
        c.font = negrito
    for x in linhas:
        def no_mes(d):
            return d if d and INICIO <= d <= FIM else "não entra"
        ws.append([x["cod"], x["caso"], no_mes(x["alvo"]),
                   entrada(x["alvo"], x["em1"], x["ult"]) or "não entra",
                   no_mes(x["prev"]), entrada(x["prev"], x["em1"], x["ult"]) or "não entra"])
    ws.append([])
    ws.append(["Curva S, Página 1 (dia a dia)", "", "ATUAL previstos", "ATUAL emitidos",
               "OTD previstos", "OTD emitidos"])
    for c in ws[ws.max_row]:
        c.font = negrito
    dias = sorted({d for x in linhas for d in (x["alvo"], x["prev"], entrada(x["alvo"], x["em1"], x["ult"]),
                                                 entrada(x["prev"], x["em1"], x["ult"]))
                   if d and INICIO <= d <= FIM} | {INICIO, FIM})
    for dia in dias:
        pa, ea = _contar(linhas, "alvo", dia)
        po, eo = _contar(linhas, "prev", dia)
        ws.append([dia, "", pa, ea, po, eo])
    ws.append([])
    ws.append(["Cartão, página Unidade Geradora", "", "Número", "Título"])
    for c in ws[ws.max_row]:
        c.font = negrito
    for botao, data_do_plano, situacao in (("ATUAL", "alvo", "sit"), ("OTD", "prev", "otd"),
                                          ("SAY-DO", "reprog", "say")):
        indice, fracao = _cartao(linhas, data_do_plano, situacao)
        ws.append([botao, "", indice, fracao])
    for linha in ws.iter_rows():
        for c in linha:
            if isinstance(c.value, date):
                c.number_format = "dd/mm/yyyy"
    for col, largura in zip("ABCDEF", (14, 70, 22, 22, 22, 22)):
        ws.column_dimensions[col].width = largura


def gerar(caminho, hoje: date) -> None:
    linhas = list(_linhas(hoje))
    wb = openpyxl.Workbook()
    _aba_dados(wb.active, linhas)
    wb.active.title = "Unidade Geradora"
    _aba_esperado(wb.create_sheet("Esperado"), linhas, hoje)
    wb.save(caminho)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    hoje = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    gerar(sys.argv[1], hoje)
    print(f"Planilha de teste gravada em {sys.argv[1]}")
