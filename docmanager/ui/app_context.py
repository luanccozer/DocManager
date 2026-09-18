"""Estado compartilhado entre as views (config, versão, navegação, atualização)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..services.config import ConfigManager


@dataclass
class AppContext:
    config: ConfigManager
    versao: str
    # Navega para outra view pela sua `key` (ex.: a Home usa para abrir módulos).
    # Preenchido pela MainApp após criar o contexto.
    navegar: Callable[[str], None] | None = None

    # --- atualização ---------------------------------------------------------
    # A checagem roda em segundo plano e termina DEPOIS de a interface já estar
    # montada, então quem quiser mostrar o aviso (Home, rodapé da sidebar,
    # Configurações) se inscreve aqui e é avisado quando a resposta chegar.
    # `atualizacao` guarda o resultado para quem se inscrever depois - a Home é
    # criada na abertura, mas as Configurações só quando a pessoa clica nelas.
    atualizacao: object | None = None
    abrir_atualizacao: Callable[[], None] | None = None
    verificar_atualizacao: Callable[[bool], None] | None = None
    _ouvintes: list[Callable[[object], None]] = field(default_factory=list, repr=False)

    def ao_achar_atualizacao(self, callback: Callable[[object], None]) -> None:
        """Inscreve `callback(info)`. Se a novidade já chegou, avisa na hora."""
        self._ouvintes.append(callback)
        if self.atualizacao is not None:
            callback(self.atualizacao)

    def anunciar_atualizacao(self, info) -> None:
        """Guarda a novidade e avisa os inscritos. Chamado pela MainApp, sempre
        na thread da interface."""
        self.atualizacao = info
        for cb in list(self._ouvintes):
            try:
                cb(info)
            except Exception:  # noqa: BLE001 - um ouvinte quebrado não derruba os outros
                pass
