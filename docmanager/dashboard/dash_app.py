"""App Dash executiva do histórico. Fábrica `create_app(df_wide)` - sem variável
global e sem `app.layout` injetado de fora (dívidas do legado resolvidas)."""
from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import dcc, html

from ..core.reports import dashboard_series as ds

# Paleta executiva (alinhada ao app)
FUNDO = "#0F1620"
CARD = "#18222E"
TEXTO = "#E8EDF2"
TEXTO_FRACO = "#8CA0B3"
TEAL = "#1F6F5C"
AZUL = "#2E86C1"
LARANJA = "#E67E22"
VERM = "#B23A48"
VERDE = "#2ECC71"

_LAYOUT_FIG = dict(paper_bgcolor=CARD, plot_bgcolor=CARD, font=dict(color=TEXTO, family="Segoe UI"),
                   margin=dict(l=40, r=20, t=40, b=40), colorway=[TEAL, AZUL, LARANJA, VERM])


def _card_kpi(titulo, valor, sub=""):
    return html.Div(style={"background": CARD, "borderRadius": "12px", "padding": "18px 22px",
                           "flex": "1", "minWidth": "160px"},
                    children=[
                        html.Div(titulo, style={"color": TEXTO_FRACO, "fontSize": "13px"}),
                        html.Div(str(valor), style={"color": TEXTO, "fontSize": "30px", "fontWeight": "700"}),
                        html.Div(sub, style={"color": TEXTO_FRACO, "fontSize": "12px"}),
                    ])


def _fig_status(df):
    fig = go.Figure(go.Bar(x=df["Quantidade"], y=df["Status"], orientation="h", marker_color=TEAL))
    fig.update_layout(title="Status vigente dos documentos", **_LAYOUT_FIG)
    fig.update_yaxes(autorange="reversed")
    return fig


def _fig_fluxo(df):
    fig = go.Figure()
    fig.add_bar(x=df["Mês"], y=df["Envios"], name="Envios", marker_color=AZUL)
    fig.add_bar(x=df["Mês"], y=df["Retornos"], name="Retornos", marker_color=TEAL)
    fig.update_layout(title="Envios vs Retornos por mês", barmode="group", **_LAYOUT_FIG)
    return fig


def _fig_especialidade(df):
    fig = go.Figure(go.Bar(x=df["Atraso Médio"], y=df["Especialidade"], orientation="h", marker_color=LARANJA))
    fig.update_layout(title="Atraso médio da Itaipu por especialidade (dias)", **_LAYOUT_FIG)
    fig.update_yaxes(autorange="reversed")
    return fig


def _fig_evolucao(df):
    fig = go.Figure()
    fig.add_scatter(x=df["Mês"], y=df["Atraso Itaipu"], name="Itaipu (análise)",
                    mode="lines+markers", line=dict(color=AZUL, width=2))
    fig.add_scatter(x=df["Mês"], y=df["Atraso CMI"], name="CMI (reemissão)",
                    mode="lines+markers", line=dict(color=TEAL, width=2))
    fig.update_layout(title="Evolução do atraso médio ao longo do tempo (dias)", **_LAYOUT_FIG)
    return fig


def create_app(df_wide) -> dash.Dash:
    app = dash.Dash(__name__, title="DocManager · Dashboard")
    k = ds.kpis_gerais(df_wide)
    cards = html.Div(style={"display": "flex", "gap": "14px", "flexWrap": "wrap", "marginBottom": "18px"}, children=[
        _card_kpi("Documentos", k.get("documentos", 0), f"{k.get('revisoes', 0)} revisões"),
        _card_kpi("First Time Right", f"{k.get('first_time_right', 0)}%", "0A aprovadas de primeira"),
        _card_kpi("Ciclo até aprovar", k.get("ciclo_aprovacao", 0), "revisões (média)"),
        _card_kpi("Atraso médio Itaipu", f"{k.get('atraso_itaipu_medio', 0)} d", "quando atrasa"),
        _card_kpi("Atraso médio CMI", f"{k.get('atraso_cmi_medio', 0)} d", "reemissão"),
    ])
    def graf(f):
        return dcc.Graph(figure=f, style={"background": CARD, "borderRadius": "12px"})

    app.layout = html.Div(style={"background": FUNDO, "minHeight": "100vh", "padding": "28px",
                                 "fontFamily": "Segoe UI"}, children=[
        html.H2("Dashboard do Histórico Consolidado", style={"color": TEXTO, "marginBottom": "4px"}),
        html.Div("Visão executiva - CMI ↔ Itaipu", style={"color": TEXTO_FRACO, "marginBottom": "20px"}),
        cards,
        # Evolução do atraso ocupa a largura toda (gráfico principal).
        html.Div(graf(_fig_evolucao(ds.evolucao_atraso(df_wide))), style={"marginBottom": "16px"}),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}, children=[
            graf(_fig_status(ds.status_vigente(df_wide))),
            graf(_fig_fluxo(ds.serie_envios_retornos(df_wide))),
            graf(_fig_especialidade(ds.atraso_por_especialidade(df_wide))),
        ]),
    ])
    return app
