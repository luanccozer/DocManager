"""Backend do módulo Relatórios.

Relatório de Avanço (prazos de devolução da Itaipu), Auditoria de Integração
(documentos presos em 0AA) e Fluxos em Andamento (onde cada documento está e com
quem). Os dois primeiros operam sobre a base Aconex carregada por [common]; o
terceiro sobre a base de FLUXOS (`workflows_backend`), que é outro arquivo.
"""
from __future__ import annotations

from .core.reports.avanco import gerar_relatorio_avanco
from .core.reports.fluxos import analisar_fluxos_em_andamento, resumir_por_responsavel
from .core.reports.integracao import auditar_fluxo_integracao

__all__ = ["gerar_relatorio_avanco", "auditar_fluxo_integracao",
           "analisar_fluxos_em_andamento", "resumir_por_responsavel"]
