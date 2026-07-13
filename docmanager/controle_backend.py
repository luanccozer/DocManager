"""Backend do Controle de Documentos (planilha de planejamento manual).

Estrutura e regras: `docs/controle_de_documentos.md`. Só aproveitamos as datas
de input manual (DATA PREVISTA / REPROGRAMAÇÃO); `data_ref` = REPROGRAMAÇÃO >
PREVISTA. Usado por [mapa_backend] e [historico_backend].
"""
from __future__ import annotations

from .services.controle_docs import ControleDocs, ControleRow, ler_controle

__all__ = ["ler_controle", "ControleDocs", "ControleRow"]
