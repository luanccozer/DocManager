from __future__ import annotations

import customtkinter as ctk

from .. import theme as t


class BaseView(ctk.CTkFrame):
    """Cabeçalho (título + subtítulo) + corpo rolável. Subclasses montam o corpo."""

    titulo_view = "View"
    subtitulo_view = ""

    def __init__(self, master, ctx):
        super().__init__(master, fg_color=t.FUNDO)
        self.ctx = ctx
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        cab = ctk.CTkFrame(self, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 8))
        ctk.CTkLabel(cab, text=self.titulo_view, font=t.titulo(24), text_color=t.TEXTO).pack(anchor="w")
        if self.subtitulo_view:
            ctk.CTkLabel(cab, text=self.subtitulo_view, font=t.corpo(13),
                         text_color=t.TEXTO_FRACO).pack(anchor="w", pady=(2, 0))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=28, pady=(4, 24))
        self.body.grid_columnconfigure(0, weight=1)
        self.montar(self.body)

    def montar(self, body):  # override
        raise NotImplementedError
