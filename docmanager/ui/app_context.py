"""Estado compartilhado entre as views (config, versão, navegação)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..services.config import ConfigManager


@dataclass
class AppContext:
    config: ConfigManager
    versao: str
    # Navega para outra view pela sua `key` (ex.: a Home usa para abrir módulos).
    # Preenchido pela MainApp após criar o contexto.
    navegar: Callable[[str], None] | None = None
