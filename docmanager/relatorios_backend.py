"""Backend do módulo Relatórios.

Relatório de Avanço (prazos de devolução da Itaipu) e Auditoria de Integração
(documentos presos em 0AA). Ambos operam sobre a base Aconex carregada por
[common].
"""
from __future__ import annotations

from .core.reports.avanco import gerar_relatorio_avanco
from .core.reports.integracao import auditar_fluxo_integracao

__all__ = ["gerar_relatorio_avanco", "auditar_fluxo_integracao"]
