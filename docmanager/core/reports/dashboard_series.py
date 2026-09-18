"""Séries e KPIs para o dashboard, calculados sobre o wide (KB §18.5).

Porta de `DataManager.calcular_kpis_revisoes` (L1213) + agregações executivas.
Funções puras (recebem/retornam DataFrames), consumidas pela app Dash.
"""
from __future__ import annotations

import pandas as pd

from ...core.compat import month_end_freq

_APROV_TECNICA = ("APROVADO", "APROVADO COM COMENTÁRIOS", "PARA ASSINATURA", "APPROVED", "APPROVED WITH COMMENTS")
_APROV_FINAL = ("APROVADO", "APPROVED")


def calcular_kpis_revisoes(df_wide: pd.DataFrame) -> dict:
    """Média de revisões até a 1ª aprovação técnica e até o Aprovado final."""
    if df_wide.empty:
        return {"ciclo_aprovacao": 0, "ciclo_completo": 0}
    kpi_ap, kpi_fin = [], []
    for _, grupo in df_wide.groupby("Tracking ID"):
        revisoes = grupo.sort_values("Data Envio").to_dict("records")
        achou_ap = achou_fin = False
        for i, rev in enumerate(revisoes):
            st = str(rev.get("Status Retorno", "")).upper()
            if not achou_ap and st in _APROV_TECNICA:
                kpi_ap.append(i + 1)
                achou_ap = True
            if not achou_fin and st in _APROV_FINAL:
                kpi_fin.append(i + 1)
                achou_fin = True
    def media(xs):
        return round(sum(xs) / len(xs), 1) if xs else 0

    return {"ciclo_aprovacao": media(kpi_ap), "ciclo_completo": media(kpi_fin)}


def kpis_gerais(df_wide: pd.DataFrame) -> dict:
    """Cartões executivos: docs, First Time Right, ciclos, atraso médio."""
    if df_wide.empty:
        return {}
    docs = df_wide["Tracking ID"].nunique()
    # First Time Right: % de 0A cujo retorno foi sucesso.
    r0a = df_wide[df_wide["Revisão"].astype(str).str.upper() == "0A"]
    r0a_ret = r0a[r0a["Status Retorno"].notna()]
    ftr = 0
    if len(r0a_ret):
        ok = r0a_ret["Status Retorno"].str.upper().isin(_APROV_TECNICA).sum()
        ftr = round(100 * ok / len(r0a_ret), 1)
    ciclos = calcular_kpis_revisoes(df_wide)
    at_it = pd.to_numeric(df_wide.get("Atraso Itaipu"), errors="coerce")
    at_cmi = pd.to_numeric(df_wide.get("Atraso CMI"), errors="coerce")
    return {
        "documentos": int(docs),
        "revisoes": int(len(df_wide)),
        "first_time_right": ftr,
        "ciclo_aprovacao": ciclos["ciclo_aprovacao"],
        "atraso_itaipu_medio": round(at_it[at_it > 0].mean(), 1) if (at_it > 0).any() else 0,
        "atraso_cmi_medio": round(at_cmi[at_cmi > 0].mean(), 1) if (at_cmi > 0).any() else 0,
    }


def status_vigente(df_wide: pd.DataFrame) -> pd.DataFrame:
    """Contagem por status de retorno vigente (última revisão de cada doc)."""
    if df_wide.empty:
        return pd.DataFrame(columns=["Status", "Quantidade"])
    ultimas = df_wide.sort_values("Data Envio").groupby("Tracking ID").tail(1)
    col = ultimas["Status Retorno"].fillna("Em Análise (com Itaipu)").replace("", "Em Análise (com Itaipu)")
    vc = col.value_counts().reset_index()
    vc.columns = ["Status", "Quantidade"]
    return vc


def serie_envios_retornos(df_wide: pd.DataFrame) -> pd.DataFrame:
    """Envios e retornos por mês."""
    if df_wide.empty:
        return pd.DataFrame(columns=["Mês", "Envios", "Retornos"])
    freq = month_end_freq()
    env = df_wide.dropna(subset=["Data Envio"]).groupby(pd.Grouper(key="Data Envio", freq=freq)).size()
    ret = df_wide.dropna(subset=["Data Retorno"]).groupby(pd.Grouper(key="Data Retorno", freq=freq)).size()
    idx = env.index.union(ret.index)
    out = pd.DataFrame({"Mês": idx, "Envios": env.reindex(idx, fill_value=0).values,
                        "Retornos": ret.reindex(idx, fill_value=0).values})
    return out


def evolucao_atraso(df_wide: pd.DataFrame) -> pd.DataFrame:
    """Atraso médio ao longo do tempo (por mês): Itaipu pelo mês do retorno,
    CMI pelo mês do envio. Mostra se o projeto está melhorando ou piorando."""
    if df_wide.empty:
        return pd.DataFrame(columns=["Mês", "Atraso Itaipu", "Atraso CMI"])
    freq = month_end_freq()
    d = df_wide.copy()
    d["_it"] = pd.to_numeric(d.get("Atraso Itaipu"), errors="coerce")
    d["_cmi"] = pd.to_numeric(d.get("Atraso CMI"), errors="coerce")
    it = d.dropna(subset=["Data Retorno"]).groupby(pd.Grouper(key="Data Retorno", freq=freq))["_it"].mean()
    cmi = d.dropna(subset=["Data Envio"]).groupby(pd.Grouper(key="Data Envio", freq=freq))["_cmi"].mean()
    idx = it.index.union(cmi.index)
    return pd.DataFrame({
        "Mês": idx,
        "Atraso Itaipu": it.reindex(idx).round(1).values,
        "Atraso CMI": cmi.reindex(idx).round(1).values,
    })


def atraso_por_especialidade(df_wide: pd.DataFrame, top=10) -> pd.DataFrame:
    """Atraso médio da Itaipu por especialidade (maiores gargalos)."""
    if df_wide.empty or "Especialidade" not in df_wide.columns:
        return pd.DataFrame(columns=["Especialidade", "Atraso Médio", "Revisões"])
    d = df_wide.copy()
    d["_at"] = pd.to_numeric(d["Atraso Itaipu"], errors="coerce")
    d = d[d["_at"].notna()]
    g = d.groupby("Especialidade").agg(Atraso_Medio=("_at", "mean"), Revisoes=("_at", "size")).reset_index()
    g = g[g["Revisoes"] >= 30].sort_values("Atraso_Medio", ascending=False).head(top)
    g.columns = ["Especialidade", "Atraso Médio", "Revisões"]
    g["Atraso Médio"] = g["Atraso Médio"].round(1)
    return g
