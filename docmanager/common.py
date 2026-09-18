"""Funções compartilhadas entre os módulos (o "cérebro" comum).

Ponto único de import para o que é usado por MAIS DE UM módulo: carga da base
Aconex, exportação genérica de Excel, índice de identidade, linha da verdade e
os motores de status. A implementação detalhada (e testada) continua em
`core/` e `services/`; aqui está a superfície pública que os backends e a UI
consomem - equivale ao antigo `data_manager.py`, porém sem I/O de tela.

Arquitetura (v3):
    ui/  →  *_backend.py  →  common.py  →  core/ + services/  (implementação)
Cada módulo tem o seu backend (mapa_backend, status_backend, historico_backend,
relatorios_backend, controle_backend, aconex_backend); o que é comum mora aqui.
"""
from __future__ import annotations

# --- Constantes de domínio (fonte única) ---
from .core import constants
from .core.constants import (
    COL_CURRENT,
    COL_DATA,
    COL_DOC_CMI,
    COL_DOC_ITAIPU,
    COL_REVISAO,
    COL_STATUS,
    COL_TITULO,
    COL_TRACKING,
    NAO_EMITIDO,
)

# --- Normalização (revisão, código, acentos) ---
from .core.normalize import (
    normalizar_codigo,
    normalizar_revisao,
    remover_acentos,
)

# --- Identidade Aconex (Tracking ID como identidade real) ---
from .core.identity import (
    AconexIndex,
    construir_indice_reverso,
    obter_codigos_historicos,
)

# --- Linha da verdade + motores de status ---
from .core.truth_line import resolver_linha_da_verdade, limpar_terminated_por_limiar
from .core.status_engine import calcular_status_real
from .core.status_model_bim import calcular_status_real_modelo
from .core.consolidation import (
    calcula_status_consolidado,
    calcular_emitido_nao_emitido,
)

# --- KPIs ---
from .core.kpis import analisar_kpis_documento, calcular_atrasos_acumulados

# --- I/O de Excel compartilhado ---
from .services.excel_io import carregar_base_aconex, exportar_dataframe

__all__ = [
    "constants",
    "COL_CURRENT", "COL_DATA", "COL_DOC_CMI", "COL_DOC_ITAIPU", "COL_REVISAO",
    "COL_STATUS", "COL_TITULO", "COL_TRACKING", "NAO_EMITIDO",
    "normalizar_codigo", "normalizar_revisao", "remover_acentos",
    "AconexIndex", "construir_indice_reverso", "obter_codigos_historicos",
    "resolver_linha_da_verdade", "limpar_terminated_por_limiar",
    "calcular_status_real", "calcular_status_real_modelo",
    "calcula_status_consolidado", "calcular_emitido_nao_emitido",
    "analisar_kpis_documento", "calcular_atrasos_acumulados",
    "carregar_base_aconex", "exportar_dataframe",
]
