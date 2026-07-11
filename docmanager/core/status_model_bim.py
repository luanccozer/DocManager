"""Motor de status de Modelos BIM (KB §16).

Porta fiel de `DataManager.calcular_status_real_modelo` (legado L1704-1771):
varredura de fantasmas + Milestone Lock (Fase Preliminar → LOD 300 → LOD 350).
Usado hoje no módulo Status Documentos; o Mapa dos Planos NÃO roteia para
este motor (decisão preservada — KB §22.6).
"""
from __future__ import annotations

import pandas as pd

from .constants import (
    COL_STATUS,
    COL_VERSAO,
    MOD_ANALISE_300,
    MOD_ANALISE_350,
    MOD_ANALISE_PRE,
    MOD_APROV_300,
    MOD_APROV_350,
    MOD_APROV_PRE,
    MOD_INFO,
    MOD_INICIAL_300,
    MOD_INICIAL_350,
    MOD_INICIAL_PRE,
    MOD_REPROV_300,
    MOD_REPROV_350,
    MOD_REPROV_PRE,
    NAO_EMITIDO,
)


def _up(*grupos) -> list[str]:
    return [s.upper() for g in grupos for s in g]


_VALIDOS_UPPER = _up(
    MOD_APROV_PRE, MOD_APROV_300, MOD_APROV_350,
    MOD_REPROV_PRE, MOD_REPROV_300, MOD_REPROV_350,
    MOD_ANALISE_PRE, MOD_ANALISE_300, MOD_ANALISE_350,
    MOD_INICIAL_PRE, MOD_INICIAL_300, MOD_INICIAL_350,
    MOD_INFO,
)

_APROV_350 = _up(MOD_APROV_350)
_APROV_300 = _up(MOD_APROV_300)
_APROV_PRE = _up(MOD_APROV_PRE)
_FASE_350 = _APROV_350 + _up(MOD_REPROV_350, MOD_ANALISE_350, MOD_INICIAL_350)
_FASE_300 = _APROV_300 + _up(MOD_REPROV_300, MOD_ANALISE_300, MOD_INICIAL_300)
_FASE_PRE = _APROV_PRE + _up(MOD_REPROV_PRE, MOD_ANALISE_PRE, MOD_INICIAL_PRE)


def calcular_status_real_modelo(df_tracking: pd.DataFrame, revisao_current) -> str:
    if df_tracking.empty or not revisao_current:
        return NAO_EMITIDO

    try:
        df_hist = df_tracking.copy()
        df_hist["Versão_Int"] = pd.to_numeric(df_hist[COL_VERSAO], errors="coerce").fillna(0)
        df_hist = df_hist.sort_values(by=["Versão_Int", COL_VERSAO], ascending=[False, False])
    except Exception:
        df_hist = df_tracking

    historico_valido = [
        str(row.get(COL_STATUS, "")).strip().upper()
        for _, row in df_hist.iterrows()
        if str(row.get(COL_STATUS, "")).strip().upper() in _VALIDOS_UPPER
    ]
    if not historico_valido:
        return NAO_EMITIDO

    status_final = historico_valido[0]

    # Milestone Lock: aprovação da fase congela e vence regressões dentro da fase.
    if status_final in _FASE_350:
        if any(st in _APROV_350 for st in historico_valido):
            return "Aprovado - LOD 350"
    elif status_final in _FASE_300:
        if any(st in _APROV_300 for st in historico_valido):
            return "Aprovado - LOD 300"
    elif status_final in _FASE_PRE:
        if any(st in _APROV_PRE for st in historico_valido):
            return "Aprovado - Fase Preliminar"

    tabela = [
        (_APROV_350, "Aprovado - LOD 350"),
        (_APROV_300, "Aprovado - LOD 300"),
        (_APROV_PRE, "Aprovado - Fase Preliminar"),
        (_up(MOD_REPROV_350), "Não Aprovado - LOD 350"),
        (_up(MOD_REPROV_300), "Não Aprovado - LOD 300"),
        (_up(MOD_REPROV_PRE), "Não Aprovado - Fase Preliminar"),
        (_up(MOD_ANALISE_350), "Em Análise - LOD 350"),
        (_up(MOD_ANALISE_300), "Em Análise - LOD 300"),
        (_up(MOD_ANALISE_PRE), "Em Análise - Fase Preliminar"),
        (_up(MOD_INICIAL_350), "Emissão Inicial - LOD 350"),
        (_up(MOD_INICIAL_300), "Emissão Inicial - LOD 300"),
        (_up(MOD_INICIAL_PRE), "Emissão Inicial - Fase Preliminar"),
        (_up(MOD_INFO), "Informativo"),
    ]
    for grupo, rotulo in tabela:
        if status_final in grupo:
            return rotulo
    return NAO_EMITIDO
