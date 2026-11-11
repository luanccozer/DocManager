"""Backend do módulo **Doc List Mapping**.

Porta única para a UI. Três frentes:
  - atualização da planilha (status, hierarquia de dois níveis, planejamento);
  - **Análise por Período** - o que está previsto para emitir (olha para FRENTE,
    pelas datas de planejamento);
  - **Delta por Período** - o que aconteceu entre duas datas (olha para TRÁS,
    pelo histórico do Aconex). Reaproveita o motor do Mapa dos Planos: as
    colunas que ele precisa (GRUPO, SISTEMA, NÍVEL, DESCRIÇÃO, PREDECESSOR,
    N° ITAIPU) têm os mesmos nomes nos dois layouts;
  - **Painel HTML** da Unidade Geradora - o lugar do Power BI: um arquivo só,
    com o retrato de hoje, as emissões, o progresso, o esforço da engenharia e o
    histórico de revisões (`core/painel_ug.py`, `.scratch/painel-ug-html/`).

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
from .services.doclist_io import DocListSheet, exportar_analise_periodo, ler_linhas_doclist

# Delta ("Máquina do Tempo"): o mesmo motor do Mapa, sobre a planilha do Doc List.
from .core.snapshots import calcular_mudancas_periodo
from .services.excel_io import exportar_delta_arvore

# Orquestração da atualização.
from .services.doclist_update import ResultadoDocList, atualizar_doclist

# Painel HTML (no lugar do Power BI): lê a planilha e a base, não escreve nada nelas.
from .services.painel_ug import ResultadoPainelUG, gerar_painel_ug

__all__ = [
    "atualizar_doclist", "ResultadoDocList",
    "COLUNAS_DOCLIST", "ANCORA_DOCLIST", "NIVEL_GRUPO", "NIVEL_DOCUMENTO",
    "LinhaDocList", "DatasDocList",
    "calcular_predecessores", "calcular_resumo_quantidades", "resolver_datas_doclist",
    "DocListSheet", "ler_linhas_doclist", "exportar_analise_periodo",
    "analisar_periodo", "listar_sem_data", "janelas_padrao", "Janela", "ItemPeriodo",
    "agrupar_por", "agrupar_por_mes", "resumo",
    "calcular_mudancas_periodo", "exportar_delta_arvore",
    "gerar_painel_ug", "ResultadoPainelUG",
]
