"""Backend do módulo Mapa dos Planos.

Porta única para a UI do Mapa: atualização da planilha de mapeamento
(status/hierarquia/KPIs/atrasos), resolução das datas do Controle e a Análise
Delta baseada no mapeamento ("Máquina do Tempo"). A lógica compartilhada está em
[common]; aqui fica o que é específico do Mapa.
"""
from __future__ import annotations

# Orquestração da atualização do mapeamento (I/O da planilha + callbacks).
from .services.mapping_update import ResultadoMapa, atualizar_mapeamento

# Pipeline puro por documento e resolução das datas do Controle.
from .core.mapping import (
    DatasControle,
    ResultadoDocumento,
    filtrar_historico_por_titulo,
    processar_documento,
    resolver_data_prevista,
    resolver_datas_controle,
)

# I/O da planilha de mapeamento.
from .services.excel_io import COLUNAS_MAPA, MappingSheet, exportar_delta_arvore

# Análise Delta pelo mapeamento (comparação de status entre duas datas).
from .core.snapshots import calcular_mudancas_periodo

__all__ = [
    "atualizar_mapeamento", "ResultadoMapa",
    "processar_documento", "ResultadoDocumento", "filtrar_historico_por_titulo",
    "resolver_datas_controle", "resolver_data_prevista", "DatasControle",
    "MappingSheet", "COLUNAS_MAPA",
    "calcular_mudancas_periodo", "exportar_delta_arvore",
]
