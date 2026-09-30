"""Planilhas de comissionamento (nível 3): as regras que só valem para elas.

As planilhas de comissionamento são analisadas por OUTRO time do cliente, com
fluxo e rótulos de status próprios no Aconex (KB §4, §8.2). O que é específico
delas mora aqui, para o motor de status, os KPIs, o histórico e os relatórios
reconhecerem a planilha e traduzirem os rótulos do mesmo jeito.

Como a planilha é reconhecida
-----------------------------
Pelo TÍTULO: contém `PLANILHA` e `COMISSIONAMENTO`. O motor de status não
conhece o nível da linha no mapeamento (o Status Documentos, o Histórico e o
Delta nem têm mapeamento), e as planilhas de nível 3 são exatamente os
documentos com esse título. É a mesma porta da exceção do 'Para Aprovação'
(§8.2).

Status próprios do fluxo de comissionamento (pedido do usuário, 2026-09-30)
--------------------------------------------------------------------------
| Rótulo no Aconex            | Equivale a       | Consolidado  |
|-----------------------------|------------------|--------------|
| Aguardando Editável         | Para Assinatura  | APROVADO     |
| Reviewed with No Comments   | Não Aprovado     | NÃO APROVADO |

A tradução acontece ANTES de qualquer motor olhar o histórico: status real,
consolidado, KPIs, atrasos, histórico consolidado e dashboard passam a tratar
os dois exatamente como os status a que equivalem - com todas as regras que já
valem para eles (salvamento na própria revisão, batalha de versões, reprovação
em revisão numérica, regra estrita VIP). A coluna STATUS do mapeamento continua
mostrando o rótulo cru do Aconex; o STATUS REAL mostra o equivalente.

Fora das planilhas de comissionamento os dois rótulos NÃO são traduzidos: o
pedido é só para o nível 3, e um status desconhecido num documento comum
continua caindo onde sempre caiu (e o consolidado ERRO denuncia).
"""
from __future__ import annotations

import pandas as pd

from .constants import COL_STATUS, COL_TITULO, STATUS_NAO_APROVADO, STATUS_PARA_ASSINATURA
from .normalize import remover_acentos


def e_planilha_comissionamento(titulo) -> bool:
    """True se o título é de uma planilha de comissionamento."""
    t = str(titulo).strip().upper()
    return "PLANILHA" in t and "COMISSIONAMENTO" in t


def historico_e_planilha(df_tracking: pd.DataFrame) -> bool:
    """O documento (histórico de UM Tracking ID) é planilha de comissionamento?

    Olha o título da primeira linha - o critério que o motor de status sempre
    usou para a exceção §8.2. Os motores que recebem o histórico de um documento
    (status real, KPIs, atrasos) usam esta função, para decidirem igual.
    """
    if df_tracking.empty or COL_TITULO not in df_tracking.columns:
        return False
    return e_planilha_comissionamento(df_tracking[COL_TITULO].iloc[0])


def _chave(status) -> str:
    """Status comparável: sem acento, MAIÚSCULAS, espaços simples. O Aconex às
    vezes grava 'Editavel' sem acento ou com espaço sobrando."""
    return " ".join(remover_acentos(status).upper().split())


# Rótulo do Aconex (em `_chave`) → status que ele equivale.
STATUS_EQUIVALENTES: dict[str, str] = {
    "AGUARDANDO EDITAVEL": STATUS_PARA_ASSINATURA,
    "REVIEWED WITH NO COMMENTS": STATUS_NAO_APROVADO,
}


def equivalente(status):
    """O status a que um rótulo do fluxo de comissionamento equivale; qualquer
    outro status volta intacto (inclusive o tipo: NaN continua NaN)."""
    return STATUS_EQUIVALENTES.get(_chave(status), status)


def traduzir_historico(df: pd.DataFrame, *, planilha: bool | None = None) -> pd.DataFrame:
    """Cópia do histórico com os rótulos do comissionamento já traduzidos.

    `planilha=None` decide LINHA A LINHA pelo título de cada evento - é o modo
    das bases com vários documentos (histórico consolidado, relatórios).
    `planilha=True/False` vale para o histórico inteiro de UM documento, já
    classificado por `historico_e_planilha`.

    Devolve o próprio `df` (sem copiar) quando não há nada a traduzir, que é o
    caso de quase todo documento.
    """
    if df.empty or COL_STATUS not in df.columns or planilha is False:
        return df
    alvo = df[COL_STATUS].map(_chave).isin(STATUS_EQUIVALENTES)
    if planilha is None:
        if COL_TITULO not in df.columns:
            return df
        alvo &= df[COL_TITULO].map(e_planilha_comissionamento)
    if not alvo.any():
        return df
    df = df.copy()
    df.loc[alvo, COL_STATUS] = df.loc[alvo, COL_STATUS].map(equivalente)
    return df
