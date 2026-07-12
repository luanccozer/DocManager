"""Estado compartilhado entre as views (config, versão)."""
from __future__ import annotations

from dataclasses import dataclass

from ..services.config import ConfigManager


@dataclass
class AppContext:
    config: ConfigManager
    versao: str
