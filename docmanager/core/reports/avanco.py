"""Relatório de Avanço — foto vigente com prazos de devolução (KB §18.3).

Porta fiel de `DataManager.gerar_relatorio_avanco` (L774-918). Usa a
nomenclatura antiga de propósito (pós-corte, 'Em Processo' vira 'Para Análise'
e Empresa=IB). Retorna (ok, df_final | mensagem).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ...core.normalize import remover_acentos

_COLS_OBRIGATORIAS = ["No. do Documento", "Revisão", "Status", "Tipo do Documento", "Current",
                      "Data de Alteração", "Título", "Status da Revisão", "Tracking ID", "Versão"]
_STATUS_VALIDOS = ["Anulado", "Aprovado", "Aprovado com Comentários", "Cancelado", "Em Processo",
                   "Informativo", "Não Aprovado", "Para Análise", "Para Assinatura", "Para Informação"]
_DOCS_LIXO = ["ESCRITÓRIO CMI", "FORNECEDOR ZEI-GE ITP", "NEE-CF-U1_U18A-A_D-EL06125-M3-TEL"]
_TIPOS_EXCLUIR = ["MODELO", "DOCUMENTO DE REFERENCIA", "CONTRACTOR DOCUMENTS", "INSPECAO", "DISPOSICAO DE CAMPO"]


def _norm(t):
    return remover_acentos(t).upper().strip()


def gerar_relatorio_avanco(df: pd.DataFrame) -> tuple[bool, object]:
    if not all(c in df.columns for c in _COLS_OBRIGATORIAS):
        return False, "Colunas obrigatórias faltando ('Tracking ID' e 'Versão' incluídas)."
    df = df.copy()

    # Fase 0: mata revisões Current+Terminated inteiras (chave Tracking_Revisão).
    mask_current = df["Current"].astype(str).str.strip().str.lower() == "true"
    mask_term = df["Status da Revisão"].astype(str).str.strip().str.lower().str.contains("terminated", na=False)
    to_kill = df.loc[mask_current & mask_term, ["Tracking ID", "Revisão"]].drop_duplicates()
    if not to_kill.empty:
        key = df["Tracking ID"].astype(str) + "_" + df["Revisão"].astype(str)
        kill = to_kill["Tracking ID"].astype(str) + "_" + to_kill["Revisão"].astype(str)
        df = df[~key.isin(set(kill))]

    # Fase 1: linha da verdade = maior Versão, depois data mais recente, por Tracking.
    df["Versão_Int"] = pd.to_numeric(df["Versão"], errors="coerce").fillna(0)
    df["Data_Temp"] = pd.to_datetime(df["Data de Alteração"], dayfirst=True, errors="coerce")
    df = df.sort_values(by=["Tracking ID", "Versão_Int", "Data_Temp"], ascending=[True, False, False])
    df = df.drop_duplicates(subset=["Tracking ID"], keep="first")

    # Fase 2: filtros.
    def revisao_valida(rev):
        rev = str(rev).strip().upper()
        return not (re.search(r"[A-Z]{2}", rev) or re.search(r"[^A-Z0-9]", rev))
    df = df[df["Revisão"].apply(revisao_valida)]
    df = df[df["Status"].str.strip().isin(_STATUS_VALIDOS)]
    df = df[~df["No. do Documento"].str.strip().str.upper().str.startswith("RDI")]
    df = df[~df["No. do Documento"].str.strip().str.upper().isin(_DOCS_LIXO)]
    df = df[~df["Tipo do Documento"].apply(_norm).isin(_TIPOS_EXCLUIR)]

    # Fase 3: enriquecimento.
    df = df.dropna(subset=["Data_Temp"])
    data_corte = pd.to_datetime("2024-08-18")
    df.loc[(df["Data_Temp"] > data_corte) & (df["Status"] == "Em Processo"), "Status"] = "Para Análise"
    df["Empresa"] = np.where(df["Status"] == "Para Análise", "IB", "CMI")
    mask_0a = df["Revisão"].astype(str).str.strip().str.upper() == "0A"
    dias = np.where(mask_0a, 30, 15)
    df["Data Devolução"] = (df["Data_Temp"] + pd.to_timedelta(dias, unit="D")).dt.strftime("%d/%m/%Y")
    df["Data de Alteração"] = df["Data_Temp"].dt.strftime("%d/%m/%Y")

    titulo = df["Título"].apply(_norm)
    tipo = df["Tipo do Documento"].apply(_norm)
    dcc = df.get("Subtipo DCC", "").astype(str).apply(_norm)
    tipo_dcc = df.get("Tipo do Documento DCC", "").astype(str).apply(_norm)
    df.loc[tipo == "DOCUMENTO TECNICO", "Tipo do Documento"] = "Técnico"
    df.loc[tipo == "MANAGEMENT DOCUMENT", "Tipo do Documento"] = "Gerenciamento"
    termos = ["PLANO DE EXECUCAO", "PLANO DE MIGRACAO", "PLANO DE COMISSIONAMENTO",
              "PLANO DE DESCOMISSIONAMENTO", "PLANO DE DESMONTAGEM"]
    regex = "|".join(re.escape(t) for t in termos)
    df.loc[titulo.str.contains(regex, regex=True) | (tipo_dcc == "DOCUMENTACAO TECNICA E DE GESTAO"),
           "Tipo do Documento"] = "Gerenciamento"
    df.loc[titulo.str.contains("WORKSTATEMENT", na=False) | dcc.str.contains("WORKSTATEMENT", na=False),
           "Tipo do Documento"] = "WORKSTATEMENT"
    df.loc[titulo.str.contains("CRITERIO", regex=True) | dcc.str.contains("CRITERIO", regex=True),
           "Tipo do Documento"] = "Critério"

    df = df.rename(columns={"Fonte": "Fonte da revisão"})
    cols = ["No. do Documento", "Controle do Emissor", "Título", "Tipo do Documento", "Revisão",
            "Status", "Data de Alteração", "Status da Revisão", "Fonte da revisão", "Empresa", "Data Devolução"]
    return True, df[[c for c in cols if c in df.columns]].copy()
