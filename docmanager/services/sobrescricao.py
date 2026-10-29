"""Incidências de sobrescrição: as datas preenchidas que o Controle trocaria (ADR 0001).

A regra pura mora em `core/planejamento.py`; aqui fica o que as duas planilhas
(Doc List e Mapa dos Planos) compartilham em volta dela: a incidência com o
documento e a coluna em que ela aparece, o texto do log e a memória das recusas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..core.normalize import celula_para_date


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
