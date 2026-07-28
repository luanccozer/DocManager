"""Backend do módulo **Doc List Mapping**.

Porta única para a UI: atualização da planilha (status, hierarquia de dois
níveis, planejamento vindo do Controle) e a Análise por Período — "quais
documentos estão previstos para emitir nos próximos tempos".

Regras e motivação em `docmanager/core/doclist.py` e na KB §27. O que é comum
ao Mapa dos Planos continua em [common]/[mapa_backend]; aqui fica só o que é
específico deste módulo.
"""
from __future__ import annotations

# Núcleo puro: colunas, consolidado, hierarquia, resumo e datas de planejamento.
from .core.doclist import (
    ANCORA_DOCLIST,
    COLUNAS_DOCLIST,
    NIVEL_DOCUMENTO,
    NIVEL_GRUPO,
    DatasDocList,
    LinhaDocList,
    calcula_status_consolidado_doclist,
    calcular_predecessores,
    calcular_resumo_quantidades,
    resolver_datas_doclist,
)

# Análise por período (planejamento de emissão).
from .core.doclist_periodo import (
    ItemPeriodo,
    Janela,
    agrupar_por,
    agrupar_por_mes,
    analisar_periodo,
    janelas_padrao,
    listar_sem_data,
    resumo,
)

# I/O da planilha + exportações.
from .services.doclist_io import (
    DocListSheet,
    criar_modelo,
    exportar_analise_periodo,
    ler_linhas_doclist,
)

# Orquestração da atualização.
from .services.doclist_update import ResultadoDocList, atualizar_doclist

__all__ = [
    "atualizar_doclist", "ResultadoDocList",
    "COLUNAS_DOCLIST", "ANCORA_DOCLIST", "NIVEL_GRUPO", "NIVEL_DOCUMENTO",
    "LinhaDocList", "DatasDocList", "calcula_status_consolidado_doclist",
    "calcular_predecessores", "calcular_resumo_quantidades", "resolver_datas_doclist",
    "DocListSheet", "ler_linhas_doclist", "criar_modelo", "exportar_analise_periodo",
    "analisar_periodo", "listar_sem_data", "janelas_padrao", "Janela", "ItemPeriodo",
    "agrupar_por", "agrupar_por_mes", "resumo",
]
