"""Auditoria de Fluxo de Integração — quem deveria ter passado pela 0AA (KB §18.4).

Porta fiel de `DataManager.auditar_fluxo_integracao` (L2036-2133). Universo:
Current=True cujo No. do Documento contém um dos 27 DCCs monitorados; marca
Integração = SIM/NÃO pela existência de envio 0AA no histórico do Tracking.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DCCS_MONITORADOS = [
    "LB010", "LB020", "LC030", "LC040", "LC060", "LC061", "LC070",
    "LD010", "LD020", "LD040", "LD050", "LD051", "LH011", "LU010",
    "DC070", "DC075", "CC051", "EC020", "BD010", "BD011", "BD012",
    "BD013", "BD014", "BD015", "BD016", "BS020", "BS110",
]


def auditar_fluxo_integracao(df_aconex: pd.DataFrame) -> pd.DataFrame:
    if df_aconex is None or df_aconex.empty or "Current" not in df_aconex.columns:
        return pd.DataFrame()
    df = df_aconex.copy()

    df_current = df[df["Current"].astype(str).str.strip().str.lower() == "true"].copy()
    regex = "|".join(DCCS_MONITORADOS)
    df_alvo = df_current[df_current["No. do Documento"].astype(str).str.contains(regex, case=False, na=False)].copy()
    if df_alvo.empty:
        return pd.DataFrame()

    df["Revisão_Limpa"] = df["Revisão"].astype(str).str.strip().str.upper()
    df["Versão_Int"] = pd.to_numeric(df["Versão"], errors="coerce").fillna(0)
    df = df.sort_values(by=["Tracking ID", "Versão_Int"], ascending=[True, True])

    def _agg(rev, sufixo):
        d = df[df["Revisão_Limpa"] == rev]
        return d.groupby("Tracking ID").agg(**{
            f"Data_Primeiro_Envio_{sufixo}": ("Data de Alteração", "first"),
            f"Status_Primeiro_Envio_{sufixo}": ("Status", "first"),
            f"Data_Ultimo_Retorno_{sufixo}": ("Data de Alteração", "last"),
            f"Status_Ultimo_Retorno_{sufixo}": ("Status", "last"),
        }).reset_index()

    df_final = df_alvo.merge(_agg("0AA", "0AA"), on="Tracking ID", how="left")
    df_final = df_final.merge(_agg("0A", "0A"), on="Tracking ID", how="left")
    df_final["INTEGRAÇÃO"] = np.where(df_final["Data_Primeiro_Envio_0AA"].notna(), "SIM", "NÃO")

    cols = ["No. do Documento", "Controle do Emissor", "Título", "INTEGRAÇÃO",
            "Data_Primeiro_Envio_0AA", "Status_Primeiro_Envio_0AA", "Data_Ultimo_Retorno_0AA",
            "Status_Ultimo_Retorno_0AA", "Data_Primeiro_Envio_0A", "Status_Primeiro_Envio_0A",
            "Data_Ultimo_Retorno_0A", "Status_Ultimo_Retorno_0A"]
    df_final = df_final[[c for c in cols if c in df_final.columns]].fillna("")
    return df_final.rename(columns={
        "INTEGRAÇÃO": "Integração",
        "Data_Primeiro_Envio_0AA": "Data Envio 0AA", "Status_Primeiro_Envio_0AA": "Status Envio 0AA",
        "Data_Ultimo_Retorno_0AA": "Data Retorno 0AA", "Status_Ultimo_Retorno_0AA": "Status Retorno 0AA",
        "Data_Primeiro_Envio_0A": "Data Envio 0A", "Status_Primeiro_Envio_0A": "Status Envio 0A",
        "Data_Ultimo_Retorno_0A": "Data Retorno 0A", "Status_Ultimo_Retorno_0A": "Status Retorno 0A",
    })
