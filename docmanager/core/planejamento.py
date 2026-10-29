"""Reconciliação das datas de planejamento: planilha × Controle (KB §24.14, ADR 0001).

Uma planilha de acompanhamento (Mapa dos Planos, Doc List Mapping) tem DUAS
fontes para a mesma data: o que está na célula e o que está no Controle de
Documentos. Este módulo é a regra ÚNICA de quem vence - os dois módulos a usam.

Regra (decisão do usuário, 2026-10-28 - "o melhor é nunca sobrescrever a data
digitada à mão"):

- **Célula vazia** recebe a data do Controle: não há nada a perder.
- **Célula preenchida** - data, texto ('A DEFINIR') ou fórmula - nunca é trocada
  sem aceite. Se o Controle tem outra data, nasce uma **incidência**, e quem roda
  a atualização decide. O app não sabe se a data foi digitada à mão ou escrita
  por uma rodada anterior: para a planilha, as duas são só o valor da célula.
  Vale para a DATA PREVISTA (que é a baseline do Baseline OTD) e para a DATA
  REPROGRAMADA (o compromisso do Say-do).
- **`data_ref`** - `REPROGRAMADA > PREVISTA` sobre os valores **finais** (os que
  ficam nas células). É a data que alimenta o cálculo de atraso.

Substitui a regra de 2026-07-28 (KB §24.13), em que a DATA PREVISTA ficava com a
mais recente das duas: era assim que a data inicial se perdia a cada
replanejamento do Controle.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .normalize import celula_para_date

COLUNA_PREVISTA = "prevista"
COLUNA_REPROGRAMADA = "reprogramada"


@dataclass(frozen=True)
class Incidencia:
    """Uma data preenchida que o Controle trocaria.

    `valor_planilha` é o que está na célula: uma `date` ou, quando a célula não
    tem data, o texto dela ('A DEFINIR', '=DATE(...)').
    """
    coluna: str
    valor_planilha: object
    data_controle: date


@dataclass(frozen=True)
class DatasPlanejadas:
    """O que gravar e qual data vale.

    `None` em `prevista`/`reprogramada` significa **não mexer na célula** - não
    "apagar". `data_ref` é o resultado efetivo, sempre recalculado.
    `incidencias` lista todas as trocas possíveis, aceitas ou não.
    """
    prevista: date | None = None
    reprogramada: date | None = None
    data_ref: date | None = None
    incidencias: tuple[Incidencia, ...] = ()


def celula_vazia(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _valor_exibido(valor):
    """Data quando a célula tem data; senão o texto dela, para a pessoa ver o que perderia."""
    d = celula_para_date(valor)
    return d if d is not None else str(valor).strip()


def _resolver_coluna(coluna: str, valor_planilha, data_controle: date | None, aceita: bool):
    """(data a escrever ou None, data final da célula, incidência ou None)."""
    atual = celula_para_date(valor_planilha)
    if data_controle is None:
        return None, atual, None
    if celula_vazia(valor_planilha):
        return data_controle, data_controle, None
    if atual == data_controle:
        return None, atual, None
    incidencia = Incidencia(coluna, _valor_exibido(valor_planilha), data_controle)
    if aceita:
        return data_controle, data_controle, incidencia
    return None, atual, incidencia


def reconciliar_datas(*, prevista_planilha, reprogramada_planilha,
                      prevista_controle: date | None, reprogramada_controle: date | None,
                      aceitas: frozenset[str] = frozenset()) -> DatasPlanejadas:
    """Aplica a regra acima. Função pura - sem I/O, sem planilha, sem Controle.

    `prevista_planilha`/`reprogramada_planilha` são os valores CRUS das células
    (data, texto, fórmula ou None). `aceitas` traz as colunas (`COLUNA_PREVISTA`,
    `COLUNA_REPROGRAMADA`) cuja incidência a pessoa aceitou trocar.
    """
    prevista, prevista_final, inc_prev = _resolver_coluna(
        COLUNA_PREVISTA, prevista_planilha, prevista_controle, COLUNA_PREVISTA in aceitas)
    reprogramada, reprogramada_final, inc_reprog = _resolver_coluna(
        COLUNA_REPROGRAMADA, reprogramada_planilha, reprogramada_controle,
        COLUNA_REPROGRAMADA in aceitas)
    data_ref = reprogramada_final if reprogramada_final is not None else prevista_final
    return DatasPlanejadas(prevista=prevista, reprogramada=reprogramada, data_ref=data_ref,
                           incidencias=tuple(i for i in (inc_prev, inc_reprog) if i is not None))
