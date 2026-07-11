"""Orquestração do Histórico Consolidado turbinado (KB §18.5 + feature nova).

Pipeline:
  base Aconex bruta
    → gerar_dataset_dashboard (long, borda 19/08 corrigida)
    → build_wide_table (1 linha por Tracking+Revisão + SLA)
    → anexar_data_prevista (data_ref do Controle por Tracking)
    → injetar_linhas_sinteticas (docs previstos e não postados)
    → calcular_atrasos (4 colunas de atraso)
    → exportar Excel (renomeia Data Envio→Data de Envio, layout legado + novas)

Este módulo é a ponte core↔serviços: o core (wide/delays) permanece puro;
aqui ele se casa com o Controle de Documentos.
"""
from __future__ import annotations

import pandas as pd

from ..core.delays import COL_DATA_PREVISTA_CTRL, DelayPolicy, calcular_atrasos
from ..core.identity import construir_indice_reverso, obter_codigos_historicos
from ..core.normalize import normalizar_codigo
from ..core.wide import (
    COL_STATUS_ENVIO,
    build_wide_table,
    gerar_dataset_dashboard,
)
from ..core.constants import COL_DOC_CMI, COL_DOC_ITAIPU, COL_TITULO, COL_TRACKING
from .controle_docs import ControleDocs

_SINTETICA_STATUS = "NÃO EMITIDO"


def anexar_data_prevista(df_wide: pd.DataFrame, controle: ControleDocs | None,
                         df_base: pd.DataFrame) -> pd.DataFrame:
    """Preenche 'Data Prevista (Controle)' por Tracking (data_ref via códigos
    históricos do doc, REPROGRAMAÇÃO > DATA PREVISTA)."""
    df = df_wide.copy()
    if controle is None or df.empty:
        df[COL_DATA_PREVISTA_CTRL] = pd.NaT
        return df
    ref_por_tracking: dict[str, object] = {}
    for tid, grp in df_base.groupby(COL_TRACKING, sort=False):
        codigos = obter_codigos_historicos(grp)
        ref_por_tracking[str(tid)] = controle.data_ref_por_codigos(codigos)
    df[COL_DATA_PREVISTA_CTRL] = df[COL_TRACKING].astype(str).map(ref_por_tracking)
    df[COL_DATA_PREVISTA_CTRL] = pd.to_datetime(df[COL_DATA_PREVISTA_CTRL], errors="coerce")
    return df


def injetar_linhas_sinteticas(df_wide: pd.DataFrame, controle: ControleDocs | None,
                              indice_reverso: dict) -> pd.DataFrame:
    """Adiciona linhas NÃO EMITIDO para docs do Controle sem representação no
    wide (não resolvem no índice reverso, ou resolvem para um Tracking que foi
    filtrado — ex.: preso em integração/0AA)."""
    if controle is None:
        return df_wide
    trackings_no_wide = set(df_wide[COL_TRACKING].astype(str)) if not df_wide.empty else set()
    novas: list[dict] = []
    ja_incluido: set[str] = set()
    for r in controle.rows:
        codigos = [normalizar_codigo(r.cod_itaipu), normalizar_codigo(r.cod_cmi)]
        codigos = [c for c in codigos if c]
        if not codigos:
            continue
        tid = next((indice_reverso[c] for c in codigos if c in indice_reverso), None)
        if tid is not None and str(tid) in trackings_no_wide:
            continue  # já está no wide
        chave = codigos[0]
        if chave in ja_incluido:
            continue
        ja_incluido.add(chave)
        novas.append({
            COL_DOC_ITAIPU: r.cod_itaipu,
            COL_DOC_CMI: r.cod_cmi,
            COL_TRACKING: f"SINT::{chave}",
            COL_TITULO: r.titulo,
            "Revisão": "",
            COL_STATUS_ENVIO: _SINTETICA_STATUS,
            COL_DATA_PREVISTA_CTRL: pd.Timestamp(r.data_ref) if r.data_ref else pd.NaT,
        })
    if not novas:
        return df_wide
    df_novas = pd.DataFrame(novas).reindex(columns=df_wide.columns if not df_wide.empty else None)
    return pd.concat([df_wide, df_novas], ignore_index=True)


def gerar_historico(df_bruto: pd.DataFrame, controle: ControleDocs | None = None,
                    policy: DelayPolicy | None = None) -> pd.DataFrame:
    """Do bruto ao wide final com atrasos e sintéticas (tudo em memória)."""
    df_limpo = gerar_dataset_dashboard(df_bruto)
    df_wide = build_wide_table(df_limpo)
    df_wide = anexar_data_prevista(df_wide, controle, df_limpo)
    indice_reverso = construir_indice_reverso(df_bruto) if controle is not None else {}
    df_wide = injetar_linhas_sinteticas(df_wide, controle, indice_reverso)
    df_wide = calcular_atrasos(df_wide, policy)
    return df_wide
