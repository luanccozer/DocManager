"""Backend do módulo Histórico Consolidado + Dashboard.

Gera o wide (1 linha por revisão + 4 colunas de atraso, casando com o Controle e
injetando linhas sintéticas), exporta o Excel profissional e serve o dashboard
executivo. As séries do dashboard e a política de atraso ficam expostas aqui.
"""
from __future__ import annotations

# Pipeline do histórico (bruto → wide com atrasos e sintéticas).
from .services.historico_consolidado import gerar_historico

# Exportação do Excel do histórico (layout legado + colunas novas).
from .services.excel_io import exportar_historico

# Política e colunas de atraso (SLA injetável).
from .core.delays import (
    COL_ATRASO_CMI,
    COL_ATRASO_ITAIPU,
    COL_DATA_PREVISTA,
    COL_DATA_PREVISTA_CTRL,
    COL_DIAS_CMI,
    COL_DIAS_ITAIPU,
    COL_REPROGRAMACAO,
    DelayPolicy,
    calcular_atrasos,
)

# Séries do dashboard (KPIs, evolução do atraso, fluxo, gargalos).
from .core.reports import dashboard_series

# App/serviço do dashboard web.
from .dashboard.dash_app import create_app
from .dashboard.server import DashboardServer

__all__ = [
    "gerar_historico", "exportar_historico",
    "DelayPolicy", "calcular_atrasos",
    "COL_DIAS_ITAIPU", "COL_ATRASO_ITAIPU", "COL_DIAS_CMI", "COL_ATRASO_CMI",
    "COL_DATA_PREVISTA", "COL_REPROGRAMACAO", "COL_DATA_PREVISTA_CTRL",
    "dashboard_series", "create_app", "DashboardServer",
]
