"""Backend do Controle de Documentos (planilha de planejamento manual).

Estrutura e regras: `docs/controle_de_documentos.md`. Só aproveitamos as datas
de input manual (DATA PREVISTA / REPROGRAMAÇÃO); `data_ref` = REPROGRAMAÇÃO >
PREVISTA. Usado por [mapa_backend] e [historico_backend], e pela tela de
sobrescrição: as datas preenchidas que o Controle trocaria (ADR 0001).
"""
from __future__ import annotations

from .core.planejamento import COLUNA_PREVISTA, COLUNA_REPROGRAMADA
from .services.controle_docs import ControleDocs, ControleRow, ler_controle
from .services.sobrescricao import ABA_RECUSAS, DecisaoSobrescricao, IncidenciaDoc, formatar_valor

__all__ = ["ler_controle", "ControleDocs", "ControleRow",
           "COLUNA_PREVISTA", "COLUNA_REPROGRAMADA", "ABA_RECUSAS",
           "DecisaoSobrescricao", "IncidenciaDoc", "formatar_valor"]
