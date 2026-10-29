"""Incidências de sobrescrição: as datas preenchidas que o Controle trocaria (ADR 0001).

A regra pura mora em `core/planejamento.py`; aqui fica o que as duas planilhas
(Doc List e Mapa dos Planos) compartilham em volta dela: a incidência com o
documento e a coluna em que ela aparece, o texto do log e a memória das recusas.
"""
from __future__ import annotations

import getpass
from dataclasses import dataclass
from datetime import date

from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from ..core.normalize import celula_para_date, remover_acentos
from .controle_docs import chave_codigo
from .excel_io import gravar_data

# Aba da própria pasta de trabalho onde o app anota as trocas recusadas. O
# Power BI lê só a aba dele, então ela não muda nada no painel; e, como viaja
# com o arquivo, a recusa vale para quem rodar o app em outra máquina.
ABA_RECUSAS = "Sobrescrições recusadas"
CABECALHO_RECUSAS = ("N° ITAIPU", "Nº CMI", "COLUNA", "DATA NA PLANILHA", "DATA DO CONTROLE",
                     "RECUSADA EM", "POR")
_LARGURAS_RECUSAS = (30, 28, 32, 16, 16, 14, 18)


@dataclass(frozen=True)
class IncidenciaDoc:
    """Uma incidência localizada na planilha: qual documento, qual coluna."""
    row: int
    cod_itaipu: str
    cod_cmi: str
    descricao: str
    coluna: str               # core.planejamento.COLUNA_PREVISTA | COLUNA_REPROGRAMADA
    titulo_coluna: str        # cabeçalho da planilha, para a pessoa reconhecer a coluna
    valor_planilha: object    # date, ou o texto que está na célula
    data_controle: date

    @property
    def codigo(self) -> str:
        return self.cod_itaipu or self.cod_cmi


@dataclass(frozen=True)
class DecisaoSobrescricao:
    """O que a pessoa decidiu sobre as incidências pendentes (índices na lista
    que ela recebeu). O que não está em nenhum dos dois fica para depois."""
    aceitas: frozenset[int] = frozenset()
    recusadas: frozenset[int] = frozenset()

    @classmethod
    def aceitar_todas(cls, n: int) -> DecisaoSobrescricao:
        return cls(aceitas=frozenset(range(n)))

    @classmethod
    def recusar_todas(cls, n: int) -> DecisaoSobrescricao:
        return cls(recusadas=frozenset(range(n)))


def formatar_valor(valor) -> str:
    """Data como dd/mm/aaaa; texto entre aspas, para não parecer data."""
    d = celula_para_date(valor) if not isinstance(valor, str) else None
    if d is not None:
        return d.strftime("%d/%m/%Y")
    return f"'{valor}'"


def descrever(inc: IncidenciaDoc) -> str:
    return (f"{inc.codigo} · {inc.titulo_coluna} {formatar_valor(inc.valor_planilha)} "
            f"→ {formatar_valor(inc.data_controle)}")


def linhas_log_nao_trocadas(incidencias: list[IncidenciaDoc], limite: int = 15) -> list[str]:
    """Log das incidências que ficaram como estão (sem decisão, ou recusadas)."""
    n = len(incidencias)
    if not n:
        return []
    cab = ("1 data preenchida que o Controle trocaria ficou como está" if n == 1 else
           f"{n} datas preenchidas que o Controle trocaria ficaram como estão")
    amostra = "; ".join(descrever(i) for i in incidencias[:limite])
    resto = "" if n <= limite else f" (+{n - limite} outras)"
    return [f"{cab}: {amostra}{resto}."]


def _contar(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def linhas_log_decisao(*, aceitas: list[IncidenciaDoc], recusadas: list[IncidenciaDoc],
                       adiadas: list[IncidenciaDoc], ja_recusadas: list[IncidenciaDoc],
                       limite: int = 15) -> list[str]:
    """Resumo do que aconteceu com as incidências da rodada."""
    msgs: list[str] = []
    total = len(aceitas) + len(recusadas) + len(adiadas) + len(ja_recusadas)
    if total and (aceitas or recusadas):
        msgs.append(f"{_contar(total, 'data preenchida', 'datas preenchidas')} que o Controle "
                    f"trocaria: {_contar(len(aceitas), 'trocada', 'trocadas')}, "
                    f"{_contar(len(recusadas), 'recusada', 'recusadas')}, "
                    f"{len(adiadas)} para depois, {len(ja_recusadas)} já recusadas antes.")
    if ja_recusadas:
        n = len(ja_recusadas)
        msgs.append(f"{n} troca{'s' if n > 1 else ''} já recusada{'s' if n > 1 else ''} antes "
                    f"não {'foram perguntadas' if n > 1 else 'foi perguntada'} de novo "
                    f"(aba '{ABA_RECUSAS}').")
    if aceitas:
        amostra = "; ".join(descrever(i) for i in aceitas[:limite])
        resto = "" if len(aceitas) <= limite else f" (+{len(aceitas) - limite} outras)"
        msgs.append(f"Sobrescrição aceita: {len(aceitas)} data(s) trocada(s) pela do Controle: "
                    f"{amostra}{resto}.")
    if recusadas:
        msgs.append(f"Sobrescrição recusada: {len(recusadas)} data(s) mantida(s) e anotada(s) na "
                    f"aba '{ABA_RECUSAS}'.")
    return msgs + linhas_log_nao_trocadas(adiadas, limite)


# ---------------------------------------------------------------------------
# Memória das recusas
# ---------------------------------------------------------------------------
def _chaves(cod_itaipu, cod_cmi, titulo_coluna, data_controle) -> set[tuple]:
    """Uma chave por código do documento: o N° ITAIPU muda quando o Aconex traz um
    código novo, e a recusa tem de continuar valendo pelo Nº CMI (e vice-versa)."""
    coluna = remover_acentos(str(titulo_coluna)).strip().upper()
    data = celula_para_date(data_controle)
    return {(chave_codigo(c), coluna, data) for c in (cod_itaipu, cod_cmi) if chave_codigo(c)}


def ler_recusas(wb) -> set[tuple]:
    """Chaves (código, coluna, data do Controle) já recusadas na pasta de trabalho."""
    if ABA_RECUSAS not in wb.sheetnames:
        return set()
    chaves: set[tuple] = set()
    for linha in wb[ABA_RECUSAS].iter_rows(min_row=2, values_only=True):
        if not linha or len(linha) < 5:
            continue
        if linha[2] and celula_para_date(linha[4]) is not None:
            chaves |= _chaves(linha[0], linha[1], linha[2], linha[4])
    return chaves


def separar_ja_recusadas(incidencias: list[IncidenciaDoc], recusas: set[tuple]):
    """(pendentes, já recusadas). Uma recusa vale enquanto o Controle mantiver a
    mesma data: se ele mudar de novo, é informação nova e volta a ser perguntada."""
    pendentes, ja = [], []
    for inc in incidencias:
        chaves = _chaves(inc.cod_itaipu, inc.cod_cmi, inc.titulo_coluna, inc.data_controle)
        (ja if chaves & recusas else pendentes).append(inc)
    return pendentes, ja


def _usuario() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - sem usuário do sistema, a recusa vale assim mesmo
        return ""


def anotar_recusas(wb, recusadas: list[IncidenciaDoc], *, quando: date, quem: str | None = None) -> None:
    """Acrescenta as recusas na aba (criada na primeira vez, no fim da pasta)."""
    if not recusadas:
        return
    if ABA_RECUSAS in wb.sheetnames:
        ws = wb[ABA_RECUSAS]
    else:
        ws = wb.create_sheet(ABA_RECUSAS)
        ws.append(list(CABECALHO_RECUSAS))
        for c, largura in enumerate(_LARGURAS_RECUSAS, start=1):
            ws.cell(1, c).font = Font(bold=True)
            ws.column_dimensions[get_column_letter(c)].width = largura
        ws.freeze_panes = "A2"
    quem = _usuario() if quem is None else quem
    for inc in recusadas:
        ws.append([inc.cod_itaipu, inc.cod_cmi, inc.titulo_coluna, None, None, None, quem])
        row = ws.max_row
        # O valor da planilha é uma data ou o texto que estava na célula ('A DEFINIR',
        # '=DATE(...)'). Fórmula vira TEXTO aqui: é o registro do que havia lá.
        if isinstance(inc.valor_planilha, str):
            ws.cell(row, 4).value = inc.valor_planilha
            ws.cell(row, 4).data_type = "s"
        else:
            gravar_data(ws.cell(row, 4), inc.valor_planilha)
        gravar_data(ws.cell(row, 5), inc.data_controle)
        gravar_data(ws.cell(row, 6), quando)


def decidir(incidencias: list[IncidenciaDoc], wb, decidir_cb, *, hoje: date):
    """Aplica a memória de recusas e a decisão da pessoa às incidências da rodada.

    Devolve `(aceitas_por_linha, linhas_de_log)`: as colunas aceitas de cada
    linha da planilha e o resumo para o log. As recusas novas já ficam anotadas
    na aba. Sem `decidir_cb` (linha de comando, testes) nada é trocado nem
    anotado; `decidir_cb` devolvendo None (a tela fechada) também não.
    """
    pendentes, ja_recusadas = separar_ja_recusadas(incidencias, ler_recusas(wb))
    decisao = decidir_cb(pendentes) if (decidir_cb is not None and pendentes) else None
    aceitas, recusadas, adiadas = [], [], []
    for i, inc in enumerate(pendentes):
        if decisao is not None and i in decisao.aceitas:
            aceitas.append(inc)
        elif decisao is not None and i in decisao.recusadas:
            recusadas.append(inc)
        else:
            adiadas.append(inc)
    anotar_recusas(wb, recusadas, quando=hoje)

    aceitas_por_linha: dict[int, frozenset[str]] = {}
    for inc in aceitas:
        aceitas_por_linha[inc.row] = aceitas_por_linha.get(inc.row, frozenset()) | {inc.coluna}
    log = linhas_log_decisao(aceitas=aceitas, recusadas=recusadas, adiadas=adiadas,
                             ja_recusadas=ja_recusadas)
    if adiadas and decidir_cb is None:
        log.append("Para escolher quais trocar, rode a atualização pela tela do DocManager.")
    return aceitas_por_linha, log
