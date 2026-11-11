"""PROTÓTIPO DESCARTÁVEL - painel HTML da Unidade Geradora (spec: ../spec.md).

Lê o Doc List Mapping (aba Unidade Geradora) e o Aconex Histórico, calcula com o motor
do DocManager as séries do protótipo e grava um HTML único. Não é código de produção:
sem testes, sem tratamento de erro. O HTML gerado tem dados do cliente e NUNCA entra
no Git (este repositório é público). Uso, da raiz do repositório:

    python .scratch/painel-ug-html/prototipo/gerar_prototipo.py "Doc List Mapping.xlsx" \
        Aconex_Historico.xlsx painel_ug.html [--hoje AAAA-MM-DD] [--chartjs chart.umd.js]

Sem --chartjs, o HTML carrega o Chart.js 4.4.4 do jsdelivr (precisa de internet).
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[2]))
from docmanager.core.consolidation import (  # noqa: E402
    calcula_status_consolidado,
    calcular_emitido_nao_emitido,
)
from docmanager.core.identity import AconexIndex  # noqa: E402
from docmanager.core.snapshots import obter_snapshot_status  # noqa: E402
from docmanager.core.wide import build_wide_table, gerar_dataset_dashboard  # noqa: E402
from docmanager.services.excel_io import carregar_base_aconex  # noqa: E402

APROVACAO = {"Aprovado", "Aprovado com Comentários", "Para Assinatura", "Informativo",
             "Para Informação", "For Partial Handover"}
ESTADOS = ["Aprovado", "Em processo (com a Itaipu)", "Não aprovado (com a CMI)", "Não emitido"]
MAPA_ESTADO = {"APROVADO": "Aprovado", "APROVAÇÃO INTERMEDIÁRIA": "Aprovado",
               "EM PROCESSO": "Em processo (com a Itaipu)", "ERRO": "Em processo (com a Itaipu)",
               "NÃO APROVADO": "Não aprovado (com a CMI)", "NÃO EMITIDO": "Não emitido"}
SITUACOES = ["EMITIDO NO PRAZO", "EMITIDO COM ATRASO", "PENDENTE NO PRAZO", "PENDENTE VENCIDO"]


def ler_doclist(caminho: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    linhas = list(wb["Unidade Geradora"].iter_rows(values_only=True))
    vistos = collections.Counter()
    cab = []
    for h in linhas[1]:
        h = h if h is not None else "None"
        vistos[h] += 1
        cab.append(h if vistos[h] == 1 else f"{h}__{vistos[h]}")
    df = pd.DataFrame(linhas[3:], columns=cab)
    df["linha"] = range(4, 4 + len(df))
    df = df[df.notna().any(axis=1)]
    return df[df["NÍVEL__2"] == 2].copy()


def mes(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s).dt.to_period("M")


def calcular(path_dl: str, path_acx: str, hoje: date) -> dict:
    docs = ler_doclist(path_dl)
    base = carregar_base_aconex(path_acx, 0)
    idx = AconexIndex(base)
    docs["tracking"] = [
        (lambda d: d["Tracking ID"].iloc[0] if not d.empty else None)(
            idx.localizar(str(r["N° ITAIPU"] or "").strip(), str(r["Nº CMI"] or "").strip()))
        for _, r in docs.iterrows()
    ]
    # Universo: cada código conta uma vez (como o DISTINCTCOUNT do Power BI); cancelado fica fora.
    u = docs.drop_duplicates("N° ITAIPU").copy()
    u = u[u["STATUS CONSOLIDADO"] != "CANCELADO"].copy()
    trks = set(u["tracking"].dropna())
    sub = base[base["Tracking ID"].isin(trks)].copy()

    # Ciclos por revisão: envio à Itaipu e retorno (veredito) - core/wide.py.
    wide = build_wide_table(gerar_dataset_dashboard(sub))
    wide = wide.sort_values(["Tracking ID", "Data Envio"])
    wide["ordem"] = wide.groupby("Tracking ID").cumcount() + 1
    rev = wide["Revisão"].astype(str).str.strip()
    wide["tipo"] = np.select(
        [wide["ordem"] == 1, rev.str.fullmatch(r"\d+")],
        ["1ª emissão", "Emissão final (rev. numérica)"], default="Reemissão (comentários/reprovação)")
    primeira = wide.dropna(subset=["Data Envio"]).groupby("Tracking ID")["Data Envio"].min()

    # Máquina do tempo: estado consolidado de cada documento a cada dia com evento.
    sub["Data_Obj"] = pd.to_datetime(sub["Data de Alteração"], dayfirst=True, errors="coerce")
    sub = sub.dropna(subset=["Data_Obj"])
    snaps = []
    for tid, g in sub.groupby("Tracking ID"):
        for dia in sorted(g["Data_Obj"].dt.normalize().unique()):
            corte = pd.Timestamp(dia) + pd.Timedelta(hours=23, minutes=59)
            bruto, real, _rev, _d = obter_snapshot_status(g, corte)
            cons = calcula_status_consolidado(real, bruto, calcular_emitido_nao_emitido(real))
            snaps.append((tid, pd.Timestamp(dia), MAPA_ESTADO.get(cons, "Em processo (com a Itaipu)")))
    sn = pd.DataFrame(snaps, columns=["tracking", "dia", "estado"])

    meses = pd.period_range("2024-01", "2027-12", freq="M")
    rotulos = [p.strftime("%Y-%m") for p in meses]
    mes_hoje = pd.Period(hoje, "M")

    # Estado de cada documento no fim de cada mês (não encontrado no Aconex = não emitido).
    comp = {e: [] for e in ESTADOS}
    sn = sn.sort_values("dia")
    for p in meses:
        if p > mes_hoje:
            for e in ESTADOS:
                comp[e].append(None)
            continue
        fim = min(p.end_time.normalize(), pd.Timestamp(hoje))
        ult = sn[sn["dia"] <= fim].groupby("tracking")["estado"].last()
        estados = u["tracking"].map(ult).fillna("Não emitido")
        cont = estados.value_counts()
        for e in ESTADOS:
            comp[e].append(int(cont.get(e, 0)))

    def acum(datas: pd.Series) -> list:
        m = mes(datas.dropna())
        antes = int((m < meses[0]).sum())
        return (m.value_counts().reindex(meses, fill_value=0).cumsum() + antes).astype(int).tolist()

    u["d_emit"] = u["tracking"].map(primeira)
    curva = {
        "alvo": acum(u["DATA-ALVO EMISSÃO"]),
        "baseline": acum(u["DATA PREVISTA EMISSÃO"]),
        "emitido": [v if p <= mes_hoje else None for v, p in zip(acum(u["d_emit"]), meses)],
        "aprovado": comp["Aprovado"],
    }

    # Ritmo das últimas 13 semanas e projeção.
    ini = pd.Timestamp(hoje) - pd.Timedelta(weeks=13)
    emit_ok = u["d_emit"].dropna()
    ritmo_emit = float(((emit_ok > ini) & (emit_ok <= pd.Timestamp(hoje))).sum() / 13)
    aprov_hoje = comp["Aprovado"][meses.get_loc(mes_hoje)]
    aprov_ini = sn[sn["dia"] <= ini].groupby("tracking")["estado"].last()
    aprov_ini = int((u["tracking"].map(aprov_ini) == "Aprovado").sum())
    ritmo_aprov = (aprov_hoje - aprov_ini) / 13
    total = len(u)
    emit_hoje = int((emit_ok <= pd.Timestamp(hoje)).sum())

    def projetar(atual: int, ritmo: float) -> list:
        out = []
        for p in meses:
            if p < mes_hoje:
                out.append(None)
                continue
            semanas = max((min(p.end_time, pd.Timestamp("2099-01-01")) - pd.Timestamp(hoje)).days, 0) / 7
            out.append(min(total, round(atual + ritmo * semanas)))
        return out
    curva["proj_emitido"] = projetar(emit_hoje, ritmo_emit)
    curva["proj_aprovado"] = projetar(aprov_hoje, ritmo_aprov)

    # Esforço da engenharia: envios à Itaipu por mês e tipo; retornos por veredito.
    w = wide.copy()
    w["m_env"] = mes(w["Data Envio"])
    w["m_ret"] = mes(w["Data Retorno"])
    envios = {t: w[w["tipo"] == t]["m_env"].value_counts().reindex(meses, fill_value=0).astype(int).tolist()
              for t in ["1ª emissão", "Reemissão (comentários/reprovação)", "Emissão final (rev. numérica)"]}
    ret = w.dropna(subset=["Data Retorno"])
    retornos = {
        "Aprovado": ret[ret["Status Retorno"].isin(APROVACAO)]["m_ret"].value_counts().reindex(meses, fill_value=0).astype(int).tolist(),
        "Não aprovado": ret[ret["Status Retorno"] == "Não Aprovado"]["m_ret"].value_counts().reindex(meses, fill_value=0).astype(int).tolist(),
    }
    ret = ret.dropna(subset=["Data Envio"]).copy()
    ret["dias"] = (ret["Data Retorno"] - ret["Data Envio"]).dt.days
    ret["no_sla"] = ret["dias"] <= ret["SLA_Itaipu"]
    g = ret.groupby("m_ret").agg(n=("dias", "size"), pct=("no_sla", "mean"), med=("dias", "median"))
    g = g.reindex(meses)
    sla = {"pct": [None if pd.isna(v) or n < 5 else round(100 * v, 1) for v, n in zip(g["pct"], g["n"].fillna(0))],
           "mediana": [None if pd.isna(v) else float(v) for v in g["med"]]}

    # Documentos para emissão por mês, nas três réguas (ATUAL, OTD, SAY-DO).
    def por_situacao(col_data: str, col_sit: str) -> dict:
        d = u.dropna(subset=[col_data])
        d = d[d[col_sit].isin(SITUACOES)]
        mm = mes(d[col_data])
        return {s: mm[d[col_sit] == s].value_counts().reindex(meses, fill_value=0).astype(int).tolist() for s in SITUACOES}
    emissao = {"ATUAL": por_situacao("DATA-ALVO EMISSÃO", "SITUAÇÃO EMISSÃO"),
               "OTD": por_situacao("DATA PREVISTA EMISSÃO", "SITUAÇÃO OTD"),
               "SAY-DO": por_situacao("DATA REPROGRAMADA", "SITUAÇÃO SAY-DO")}

    # Retrato de hoje por fase e por grupo (estado consolidado da planilha).
    u["estado"] = u["STATUS CONSOLIDADO"].map(MAPA_ESTADO).fillna("Em processo (com a Itaipu)")
    def quebra(col: str) -> dict:
        t = u.pivot_table(index=col, columns="estado", values="linha", aggfunc="count", fill_value=0)
        t = t.reindex(columns=ESTADOS, fill_value=0)
        t = t.loc[t.sum(axis=1).sort_values(ascending=False).index]
        return {"rotulos": t.index.tolist(), "series": {e: t[e].astype(int).tolist() for e in ESTADOS}}

    otd = u[u["SITUAÇÃO OTD"].isin(SITUACOES)]
    otd_atr = otd["SITUAÇÃO OTD"].isin(["EMITIDO COM ATRASO", "PENDENTE VENCIDO"]).sum()
    sd = u[u["SITUAÇÃO SAY-DO"].isin(SITUACOES)]
    sd_atr = sd["SITUAÇÃO SAY-DO"].isin(["EMITIDO COM ATRASO", "PENDENTE VENCIDO"]).sum()
    kpi = {
        "total": total, "emitidos": emit_hoje, "aprovados": int(aprov_hoje),
        "itaipu": comp["Em processo (com a Itaipu)"][meses.get_loc(mes_hoje)],
        "reprovados": comp["Não aprovado (com a CMI)"][meses.get_loc(mes_hoje)],
        "nao_emitidos": comp["Não emitido"][meses.get_loc(mes_hoje)],
        "vencidos_alvo": int((u["SITUAÇÃO EMISSÃO"] == "PENDENTE VENCIDO").sum()),
        "vencidos_baseline": int((u["SITUAÇÃO OTD"] == "PENDENTE VENCIDO").sum()),
        "otd": round(100 * (len(otd) - otd_atr) / len(otd), 1), "otd_n": int(len(otd) - otd_atr), "otd_de": int(len(otd)),
        "saydo": round(100 * (len(sd) - sd_atr) / len(sd), 1) if len(sd) else None, "saydo_n": int(len(sd) - sd_atr), "saydo_de": int(len(sd)),
        "ritmo_emit": round(ritmo_emit, 1), "ritmo_aprov": round(ritmo_aprov, 1),
        "alvo_ate_fev27": int((pd.to_datetime(u["DATA-ALVO EMISSÃO"]) <= "2027-02-28").sum()),
        "data_base": hoje.isoformat(),
    }
    payload = {"meses": rotulos, "hoje": mes_hoje.strftime("%Y-%m"), "kpi": kpi, "curva": curva,
               "composicao": comp, "envios": envios, "retornos": retornos, "sla": sla, "emissao": emissao,
               "fase": quebra("FASE DE PROJETO"), "grupo": quebra("GRUPO")}
    return payload


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("doclist")
    ap.add_argument("aconex")
    ap.add_argument("saida")
    ap.add_argument("--hoje", type=date.fromisoformat, default=date.today())
    ap.add_argument("--chartjs", help="chart.umd.js local, para o HTML abrir sem internet")
    a = ap.parse_args()
    payload = calcular(a.doclist, a.aconex, a.hoje)
    if a.chartjs:
        lib = "<script>" + Path(a.chartjs).read_text(encoding="utf-8").replace("</script", "<\\/script") + "</script>"
    else:
        lib = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>'
    html = (AQUI / "template.html").read_text(encoding="utf-8")
    html = html.replace("<script>/*CHARTJS*/</script>", lib).replace("/*DADOS*/", json.dumps(payload, ensure_ascii=False))
    Path(a.saida).write_text(html, encoding="utf-8")
    print(json.dumps(payload["kpi"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
