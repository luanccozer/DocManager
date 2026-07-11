"""Histórico consolidado: dataset (long) + tabela wide ÚNICA (KB §18.5).

Funde os dois caminhos divergentes do legado (`gerar_dataset_dashboard` L938,
`gerar_excel_historico_formatado` L1032 e `preparar_tabela_wide` L1152) num só:

- `gerar_dataset_dashboard(df_bruto)` → df_limpo (long, 1 linha por evento),
  com a borda 19/08 PADRONIZADA (regime novo ⇔ data >= 19/08, §21.3):
  o legado usava `<=` para o passado, tratando 19/08 como regime antigo,
  divergindo do motor de status. Aqui `is_regime_novo` manda em todo lugar.
- `build_wide_table(df_limpo)` → df_wide (1 linha por Tracking+Revisão) com
  colunas internas `Data Envio`/`Data Retorno`, `Status Envio`/`Status Retorno`
  e `SLA_Itaipu`. Ordenação pela sort key canônica de 3 níveis. A exportação
  Excel renomeia para `Data de Envio`/`Data de Retorno` (layout legado).

Divergências sancionadas: #2 (borda), #4 (sort key do Excel unificada na de 3
níveis; base de metadados por data+keep-last como no wide).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import (
    COL_DATA,
    COL_REVISAO,
    COL_STATUS,
    COL_TIPO_DOC,
    COL_TITULO,
    COL_TRACKING,
    COL_VERSAO,
    DATA_CORTE_FLUXO,
    HIST_STATUS_VALIDOS,
    HIST_TIPOS_VALIDOS,
    SLA_ITAIPU_DEMAIS,
    SLA_ITAIPU_REV_0A,
)
from .normalize import sort_key_revisao

# Colunas internas do wide (sem "de"); a exportação Excel renomeia.
COL_DATA_ENVIO = "Data Envio"
COL_STATUS_ENVIO = "Status Envio"
COL_DATA_RETORNO = "Data Retorno"
COL_STATUS_RETORNO = "Status Retorno"
COL_SLA = "SLA_Itaipu"

_COLS_META = ("Especialidade", "Subespecialidade", "Tipo do Documento DCC", "Subtipo DCC")
_COLS_ESTATICAS = (
    "No. do Documento", "Controle do Emissor", COL_TRACKING, COL_TITULO,
    COL_TIPO_DOC, "Especialidade", "Subespecialidade",
    "Tipo do Documento DCC", "Subtipo DCC", COL_VERSAO, "Current", COL_REVISAO,
)


def _ultimo_nao_vazio(s: pd.Series) -> str:
    """Último valor não-vazio da série (na ordem do grupo); '' se todos vazios."""
    nao_vazios = s[s != ""]
    return nao_vazios.iloc[-1] if len(nao_vazios) else ""


def gerar_dataset_dashboard(df_bruto: pd.DataFrame) -> pd.DataFrame:
    """Dataset long limpo (envios vs retornos), base do histórico e do dashboard."""
    if df_bruto.empty:
        return pd.DataFrame()

    df = df_bruto.copy()

    # 1. Filtros grossos: Terminated, status válidos, tipos válidos.
    if "Status da Revisão" in df.columns:
        df = df[df["Status da Revisão"].astype(str).str.strip() != "Terminated"]
    df = df[df[COL_STATUS].isin(HIST_STATUS_VALIDOS)]
    if COL_TIPO_DOC in df.columns:
        df = df[df[COL_TIPO_DOC].isin(HIST_TIPOS_VALIDOS)]

    # 2. Limpeza técnica de revisão e datas.
    df[COL_REVISAO] = df[COL_REVISAO].astype(str).str.upper().str.replace("R", "", regex=False).str.strip()
    df = df[df[COL_REVISAO].str.len() <= 2]
    df[COL_DATA] = pd.to_datetime(df[COL_DATA], errors="coerce", dayfirst=True)
    df = df.dropna(subset=[COL_DATA])
    df["Versão_Int"] = pd.to_numeric(df[COL_VERSAO], errors="coerce").fillna(0)

    # 3. Borda 19/08 PADRONIZADA: regime novo ⇔ data >= corte (§21.3).
    antigo = df[COL_DATA] < DATA_CORTE_FLUXO
    df.loc[antigo & (df[COL_STATUS] == "Em Processo"), COL_STATUS] = "Em Processo (CMI)"
    df.loc[antigo & (df[COL_STATUS] == "Para Análise"), COL_STATUS] = "Em Processo"
    df = df[~((~antigo) & (df[COL_STATUS] == "Para Análise"))]

    # Regras cirúrgicas do "Para Aprovação":
    mask_para_aprov = df[COL_STATUS] == "Para Aprovação"
    mask_comiss = df[COL_TITULO].str.contains(r"PLANILHA[S]? DE COMISSIONAMENTO", case=False, na=False)
    df.loc[mask_para_aprov & mask_comiss, COL_STATUS] = "Para Assinatura"
    df = df[df[COL_STATUS] != "Para Aprovação"]  # o resto é exterminado

    # 4. Ordenação para deduplicação.
    df = df.sort_values(
        by=[COL_TRACKING, COL_REVISAO, COL_DATA, "Versão_Int"],
        ascending=[True, True, False, False],
    )

    # 4.5. Backfill de metadados por Tracking (último valor não-vazio sobrescreve).
    # Evita `.replace(regex)` (deprecação de downcasting no pandas 2.3); opera
    # sobre a versão já "stripada" e pega o último não-vazio na ordem do grupo.
    cols_meta = [c for c in _COLS_META if c in df.columns]
    for col in cols_meta:
        stripped = df[col].astype(str).str.strip()
        df[col] = stripped.groupby(df[COL_TRACKING]).transform(_ultimo_nao_vazio)

    # 5. Separação ENVIOS (Em Processo) vs RETORNOS (não contém "Em Processo").
    df_envios = df[df[COL_STATUS] == "Em Processo"].drop_duplicates(
        subset=[COL_TRACKING, COL_REVISAO], keep="first"
    )
    df_retornos = df[~df[COL_STATUS].str.contains("Em Processo", case=False, na=False)].drop_duplicates(
        subset=[COL_TRACKING, COL_REVISAO], keep="first"
    )
    df_final = pd.concat([df_envios, df_retornos])
    df_final = df_final.sort_values(by=[COL_TRACKING, COL_REVISAO, COL_DATA])
    return df_final


def build_wide_table(df_limpo: pd.DataFrame) -> pd.DataFrame:
    """1 linha por (Tracking, Revisão) com Envio/Retorno + SLA_Itaipu.

    Builder ÚNICO consumido pelo Excel e pelo dashboard.
    """
    if df_limpo.empty:
        return pd.DataFrame()

    cols_existentes = [c for c in _COLS_ESTATICAS if c in df_limpo.columns]
    df_base = df_limpo.sort_values(by=[COL_DATA]).drop_duplicates(
        subset=[COL_TRACKING, COL_REVISAO], keep="last"
    )[cols_existentes].copy()

    df_envio = df_limpo[df_limpo[COL_STATUS] == "Em Processo"][
        [COL_TRACKING, COL_REVISAO, COL_DATA, COL_STATUS]
    ].rename(columns={COL_DATA: COL_DATA_ENVIO, COL_STATUS: COL_STATUS_ENVIO})

    df_retorno = df_limpo[df_limpo[COL_STATUS] != "Em Processo"][
        [COL_TRACKING, COL_REVISAO, COL_DATA, COL_STATUS]
    ].rename(columns={COL_DATA: COL_DATA_RETORNO, COL_STATUS: COL_STATUS_RETORNO})

    df_wide = pd.merge(df_base, df_envio, on=[COL_TRACKING, COL_REVISAO], how="left")
    df_wide = pd.merge(df_wide, df_retorno, on=[COL_TRACKING, COL_REVISAO], how="left")

    df_wide["_sort"] = df_wide[COL_REVISAO].apply(sort_key_revisao)
    df_wide = df_wide.sort_values(by=[COL_TRACKING, "_sort"]).drop(columns="_sort")

    df_wide[COL_SLA] = np.where(
        df_wide[COL_REVISAO].astype(str).str.strip().str.upper() == "0A",
        SLA_ITAIPU_REV_0A,
        SLA_ITAIPU_DEMAIS,
    )
    return df_wide.reset_index(drop=True)
