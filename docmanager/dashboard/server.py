"""Servidor do dashboard em thread daemon (debug=False, sem reloader)."""
from __future__ import annotations

import socket
import threading
import webbrowser

from .dash_app import create_app


def _porta_livre(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


class DashboardServer:
    """Sobe o dashboard uma vez; nas próximas só reabre o navegador."""

    def __init__(self, porta: int = 8050):
        self.porta = porta
        self._rodando = False

    def iniciar(self, df_wide):
        url = f"http://127.0.0.1:{self.porta}/"
        if self._rodando:
            webbrowser.open(url)
            return url
        if not _porta_livre(self.porta):
            # Porta ocupada (talvez uma execução anterior) - só abre o navegador.
            webbrowser.open(url)
            self._rodando = True
            return url
        app = create_app(df_wide)

        def _run():
            app.run(debug=False, port=self.porta, use_reloader=False)

        threading.Thread(target=_run, daemon=True).start()
        self._rodando = True
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        return url
