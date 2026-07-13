"""Backend do módulo Status Documentos.

Status real de uma lista/arquivo/base de documentos e o Delta FLEXÍVEL por
metadado (agrupa direto na base, sem depender do mapeamento). A carga da base
Aconex vem de [common]; a exportação com gráfico, de excel_io.
"""
from __future__ import annotations

# Status real por par (Itaipu, CMI) e por lista de códigos.
from .core.reports.status_docs import analisar_status_documentos, analisar_status_pares

# Delta flexível por metadado (Especialidade, DCC, ...) + metadados disponíveis.
from .core.snapshots import METADADOS_AGRUPAVEIS, calcular_mudancas_base

# Excel legado com gráfico de barras.
from .services.excel_io import exportar_status_documentos

__all__ = [
    "analisar_status_pares", "analisar_status_documentos",
    "calcular_mudancas_base", "METADADOS_AGRUPAVEIS",
    "exportar_status_documentos",
]
