"""Shims de compatibilidade pandas 2.x ↔ 3.x.

O código-alvo roda nesta máquina (pandas 3.x) e no notebook corporativo
(provavelmente 2.x). Concentre aqui qualquer diferença de API.
"""
from __future__ import annotations

import pandas as pd

_PD_MAJOR, _PD_MINOR = (int(x) for x in pd.__version__.split(".")[:2])


def month_end_freq() -> str:
    """Alias de frequência mensal (fim de mês) válido na versão corrente.

    'ME' só existe em pandas >= 2.2; 'M' foi removido no pandas 3.
    (O legado usa freq='ME' fixo — quebrava em pandas < 2.2.)
    """
    if (_PD_MAJOR, _PD_MINOR) >= (2, 2):
        return "ME"
    return "M"
