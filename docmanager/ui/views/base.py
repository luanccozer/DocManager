from __future__ import annotations

import customtkinter as ctk

from .. import theme as t
from ..components import LogConsole


class BaseView(ctk.CTkFrame):
    """Cabeçalho (título + subtítulo) + corpo rolável + console de log padronizado.

    TODA view herda o mesmo painel de log ancorado no rodapé, com altura
    dinâmica (acompanha o tamanho da janela). Como não vemos o terminal, é aqui
    que aparece o que está acontecendo e os erros. Subclasses usam `self.log`.
    """

    titulo_view = "View"
    subtitulo_view = ""

    def __init__(self, master, ctx):
        super().__init__(master, fg_color=t.FUNDO)
        self.ctx = ctx
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)   # corpo cresce; o log fica ancorado embaixo

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 8))
        ctk.CTkLabel(cab, text=self.titulo_view, font=t.titulo(24), text_color=t.TEXTO).pack(anchor="w")
        if self.subtitulo_view:
            ctk.CTkLabel(cab, text=self.subtitulo_view, font=t.corpo(13),
                         text_color=t.TEXTO_FRACO).pack(anchor="w", pady=(2, 0))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(4, 8))
        self.body.grid_columnconfigure(0, weight=1)

        self._montar_console()   # cria self.log (rodapé, altura dinâmica)
        self.montar(self.body)

    # Console de log padronizado - presente em todas as views.
    def _montar_console(self):
        self._console = ctk.CTkFrame(self, fg_color=t.CARD, corner_radius=10,
                                     border_width=1, border_color=t.CARD_BORDA, height=200)
        self._console.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 20))
        self._console.grid_propagate(False)   # altura controlada por nós (dinâmica)
        self._console.grid_columnconfigure(0, weight=1)
        self._console.grid_rowconfigure(1, weight=1)

        barra = ctk.CTkFrame(self._console, fg_color="transparent")
        barra.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        barra.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(barra, text="📋 Registro de execução", font=t.corpo(12, "bold"),
                     text_color=t.TEXTO_FRACO).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(barra, text="Limpar", width=72, height=24, font=t.corpo(11),
                      fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=lambda: self.log.clear()).grid(row=0, column=1, sticky="e")

        self.log = LogConsole(self._console)
        self.log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.log.log("Pronto. Os passos e eventuais erros aparecem aqui.")

        self.bind("<Configure>", self._ajustar_console)

    def _ajustar_console(self, _evt=None):
        """Altura do console = ~24% da janela, entre 140 e 300 px (padronizado)."""
        try:
            alvo = max(140, min(int(self.winfo_height() * 0.24), 300))
        except Exception:  # noqa: BLE001
            return
        if abs(self._console.winfo_height() - alvo) > 8:
            self._console.configure(height=alvo)

    def montar(self, body):  # override
        raise NotImplementedError
