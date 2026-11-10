"""Planilha de teste do painel: 12 documentos fictícios, um para cada regra.

Monta um Excel com a aba 'Unidade Geradora' no mesmo layout da planilha real (linha 1
vazia, cabeçalho na linha 2, linha 3 vazia, dados da linha 4) e uma aba 'Esperado' com o
que o Power BI tem de mostrar:

- em outubro/2026, a curva S da página Curva (a antiga Página 1; ATUAL e OTD) e o cartão
  da página Unidade Geradora: só TESTE-01 a TESTE-09 entram nessas contas;
- no dia dado, a página Projeção: a curva do projeto, o cartão A recuperar e a lista dos
  atrasados. TESTE-10 a TESTE-12 existem para ela.

As situações são calculadas pelo DocManager, com o "hoje" dado. A página Projeção conta pelo
dia em que o Power BI é aberto: gere a planilha no mesmo dia em que for conferir. Roteiro:
docs/power_bi_otd_say_do.md (passos 10 e 12, teste com documentos de exemplo). Uso:

    python tools/planilha_teste_curva_s.py saida.xlsx [AAAA-MM-DD]
"""
from __future__ import annotations

import calendar
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
    ("TESTE-10", "previsto 05/09, reprogramado para 31/03/27, não saiu: atrasado com data nova",
     D(2026, 9, 5), D(2027, 3, 31), None, None, ""),
    ("TESTE-11", "previsto 15/12, não saiu: ainda no prazo, entra na projeção em 15/12",
     D(2026, 12, 15), None, None, None, ""),
    ("TESTE-12", "previsto 10/12, reprogramado para 26/02/27, não saiu: vai atrasar contra a baseline",
     D(2026, 12, 10), D(2027, 2, 26), None, None, ""),
]
INICIO, FIM = D(2026, 10, 1), D(2026, 10, 31)

# Página Projeção (passo 12): o projeto inteiro, contra a data prevista (a baseline).
FIM_DO_EIXO = D(2027, 10, 31)
SEM_DATA_NOVA, COM_DATA_NOVA = "SEM DATA NOVA", "COM DATA NOVA"


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


def entrada_realizado(prevista, emissao, ultima):
    """O dia em que o documento emitido entra no Realizado da página Projeção (passo 12).

    Na 1ª emissão. Se já teve revisão depois dela, na data prevista, porque a data do Doc
    List é de uma revisão posterior (a regra da curva mensal), ou na 1ª emissão, se ela
    veio depois. Sem data prevista, o documento não está na baseline e não entra. O
    cancelado fica de fora antes, em quem chama.
    """
    if prevista is None or emissao is None:
        return None
    if ultima is None or ultima <= emissao:
        return emissao
    return max(emissao, prevista)


def entrada_projecao(prevista, alvo, emissao, ultima, hoje):
    """O dia em que o documento entra na Projeção: o emitido, como no Realizado; o pendente,
    na data-alvo, se ela ainda não venceu. Pendente com a data-alvo vencida não entra: é o
    vão que sobra no fim da curva (decisão do usuário, Q21 = A)."""
    if prevista is None:
        return None
    if emissao is not None:
        return entrada_realizado(prevista, emissao, ultima)
    return alvo if alvo is not None and alvo >= hoje else None


def grupo_recuperar(prevista, alvo, emissao, hoje):
    """O grupo do documento no cartão A recuperar, ou None se ele não é atrasado.

    A recuperar é o documento que não saiu e cuja data prevista já passou (a mesma conta do
    PENDENTE VENCIDO da SITUAÇÃO OTD). Tem data nova se a data-alvo ainda não venceu.
    """
    if prevista is None or emissao is not None or prevista >= hoje:
        return None
    return COM_DATA_NOVA if alvo is not None and alvo >= hoje else SEM_DATA_NOVA


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


def curva_do_projeto(linhas, hoje, dia):
    """Baseline, Realizado e Projeção num dia da página Projeção. O Realizado só existe até
    hoje e a Projeção só de hoje em diante (None no resto), como as linhas do gráfico."""
    baseline = sum(1 for x in linhas if x["prev"] and x["prev"] <= dia)
    realizado = sum(1 for x in linhas
                    if (e := entrada_realizado(x["prev"], x["em1"], x["ult"])) and e <= dia)
    projecao = sum(1 for x in linhas
                   if (e := entrada_projecao(x["prev"], x["alvo"], x["em1"], x["ult"], hoje)) and e <= dia)
    return baseline, realizado if dia <= hoje else None, projecao if dia >= hoje else None


def a_recuperar(linhas, hoje):
    """Os atrasados contra a data prevista, com o grupo, do mais atrasado para o menos."""
    atrasados = [(g, x) for x in linhas if (g := grupo_recuperar(x["prev"], x["alvo"], x["em1"], hoje))]
    return sorted(atrasados, key=lambda gx: (gx[0] != SEM_DATA_NOVA, gx[1]["prev"]))


def _dias_da_curva(hoje):
    fins = [D(a, m, calendar.monthrange(a, m)[1]) for a, m in
            ((2026, 9), (2026, 10), (2026, 11), (2026, 12), (2027, 1), (2027, 2), (2027, 3))]
    return sorted(set(fins) | {hoje, FIM_DO_EIXO})


def _titulo(ws, texto):
    ws.append([texto])
    ws.cell(ws.max_row, 1).font = Font(bold=True)


def _cabecalho(ws, valores):
    ws.append(valores)
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)


def _aba_esperado(ws, linhas, hoje):
    def no_mes(d):
        return d if d and INICIO <= d <= FIM else "não entra"

    _titulo(ws, f"O que o Power BI tem de mostrar com esta planilha, filtro 2026 → outubro "
                f"(situações calculadas em {hoje:%d/%m/%Y}).")
    ws.append([])
    _cabecalho(ws, ["Documento", "Caso", "Entra na escura (ATUAL)", "Entra na clara (ATUAL)",
                    "Entra na escura (OTD)", "Entra na clara (OTD)"])
    for x in linhas[:9]:  # TESTE-10 a TESTE-12 são da página Projeção: em outubro, não entram
        ws.append([x["cod"], x["caso"], no_mes(x["alvo"]),
                   entrada(x["alvo"], x["em1"], x["ult"]) or "não entra",
                   no_mes(x["prev"]), entrada(x["prev"], x["em1"], x["ult"]) or "não entra"])
    ws.append([])
    _cabecalho(ws, ["Curva S, página Curva (dia a dia)", "", "ATUAL previstos", "ATUAL emitidos",
                    "OTD previstos", "OTD emitidos"])
    dias = sorted({d for x in linhas for d in (x["alvo"], x["prev"], entrada(x["alvo"], x["em1"], x["ult"]),
                                                 entrada(x["prev"], x["em1"], x["ult"]))
                   if d and INICIO <= d <= FIM} | {INICIO, FIM})
    for dia in dias:
        pa, ea = _contar(linhas, "alvo", dia)
        po, eo = _contar(linhas, "prev", dia)
        ws.append([dia, "", pa, ea, po, eo])
    ws.append([])
    _cabecalho(ws, ["Cartão, página Unidade Geradora", "", "Número", "Título"])
    for botao, data_do_plano, situacao in (("ATUAL", "alvo", "sit"), ("OTD", "prev", "otd"),
                                          ("SAY-DO", "reprog", "say")):
        indice, fracao = _cartao(linhas, data_do_plano, situacao)
        ws.append([botao, "", indice, fracao])

    ws.append([])
    ws.append([])
    _titulo(ws, f"Página Projeção (passo 12), com o Power BI aberto em {hoje:%d/%m/%Y}. "
                "Em outro dia, gere a planilha de novo.")
    atrasados = a_recuperar(linhas, hoje)
    com = sum(1 for g, _ in atrasados if g == COM_DATA_NOVA)
    ws.append([])
    _cabecalho(ws, ["Cartão A recuperar", "", "Número", "Título"])
    ws.append(["", "", len(atrasados), f"{com} COM DATA NOVA · {len(atrasados) - com} SEM DATA NOVA"])
    ws.append([])
    _cabecalho(ws, ["Lista (matriz)", "Grupo", "Prevista", "Data nova", "Dias de atraso"])
    for grupo, x in atrasados:
        ws.append([x["cod"], grupo, x["prev"], x["alvo"] if grupo == COM_DATA_NOVA else "",
                   (hoje - x["prev"]).days])
    ws.append([])
    _cabecalho(ws, ["Curva do projeto", "", "Baseline", "Realizado", "Projeção"])
    for dia in _dias_da_curva(hoje):
        base, real, proj = curva_do_projeto(linhas, hoje, dia)
        ws.append([dia, "hoje" if dia == hoje else "", base, "—" if real is None else real,
                   "—" if proj is None else proj])
    base, _, proj = curva_do_projeto(linhas, hoje, FIM_DO_EIXO)
    ws.append([f"No fim do eixo sobram {base - proj} entre a baseline e a projeção: os sem data nova."])

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
