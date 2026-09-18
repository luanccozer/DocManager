"""Reconciliação das datas de planejamento: planilha × Controle (KB §24.13).

Uma planilha de acompanhamento (Mapa dos Planos, Doc List Mapping) tem DUAS
fontes para a mesma data: o que a equipe digitou na célula e o que está no
Controle de Documentos. Este módulo é a regra ÚNICA de quem vence - antes cada
módulo tinha a sua, e elas divergiam.

Regra (decisão do usuário, 2026-07-28 - "a lógica do Doc List é melhor"):

- **DATA PREVISTA** - vence a **mais recente** entre as duas. O Controle é
  replanejado com frequência; a regra antiga do Mapa ("só escreve se a célula
  estiver vazia") fazia uma data nova nunca chegar ao mapeamento.
- **DATA REPROGRAMADA** - só preenche o **vazio**. A coluna aceita input manual,
  e a regra antiga do Mapa (sobrescrever sempre) apagava o que a equipe digitava
  a cada rodada.
- **`data_ref`** - `REPROGRAMADA > PREVISTA` sobre os valores **finais** (os que
  ficam nas células), não sobre os do Controle. É a data que alimenta o cálculo
  de atraso, e ela precisa refletir o que o leitor vê na planilha.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DatasPlanejadas:
    """O que gravar e qual data vale.

    `None` em `prevista`/`reprogramada` significa **não mexer na célula** - não
    "apagar". `data_ref` é o resultado efetivo, sempre recalculado.
    """
    prevista: date | None = None
    reprogramada: date | None = None
    data_ref: date | None = None
    prevista_atualizada: bool = False   # a célula tinha data e o Controle trouxe mais recente


def reconciliar_datas(*, prevista_planilha: date | None, reprogramada_planilha: date | None,
                      prevista_controle: date | None,
                      reprogramada_controle: date | None) -> DatasPlanejadas:
    """Aplica a regra acima. Função pura - sem I/O, sem planilha, sem Controle."""
    prevista_final = prevista_planilha
    reprogramada_final = reprogramada_planilha
    prevista_escrever = reprogramada_escrever = None
    atualizada = False

    if prevista_controle is not None and (prevista_planilha is None
                                          or prevista_controle > prevista_planilha):
        prevista_escrever = prevista_final = prevista_controle
        atualizada = prevista_planilha is not None

    if reprogramada_planilha is None and reprogramada_controle is not None:
        reprogramada_escrever = reprogramada_final = reprogramada_controle

    data_ref = reprogramada_final if reprogramada_final is not None else prevista_final
    return DatasPlanejadas(prevista=prevista_escrever, reprogramada=reprogramada_escrever,
                           data_ref=data_ref, prevista_atualizada=atualizada)
