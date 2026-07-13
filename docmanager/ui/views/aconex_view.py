from __future__ import annotations

from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, RunBar
from .base import BaseView


class AconexView(BaseView):
    titulo_view = "Extração Aconex (API)"
    subtitulo_view = "Baixa o histórico completo do projeto direto da API do Aconex"

    def montar(self, body):
        from ...aconex_backend import USUARIOS
        card = Card(body, "Credenciais")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        linha = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(linha, text="Usuário", width=170, anchor="w", font=t.corpo(12),
                     text_color=t.TEXTO).grid(row=0, column=0, sticky="w")
        self.opt_user = ctk.CTkOptionMenu(linha, values=list(USUARIOS.keys()),
                                          fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO,
                                          font=t.corpo(12))
        self.opt_user.grid(row=0, column=1, sticky="w")
        linha.grid_columnconfigure(1, weight=1)
        card.add(linha)

        self.entry_proxy = ctk.CTkEntry(card, placeholder_text="Proxy (opcional) — vazio detecta automático",
                                        font=t.corpo(12))
        card.add(self.entry_proxy)
        ctk.CTkLabel(card, text="O Client Secret é lido do arquivo .env (SECRET_<USUÁRIO>).",
                     font=t.corpo(11), text_color=t.TEXTO_FRACO, anchor="w").grid(
            row=card._linha, column=0, sticky="w", padx=16, pady=(0, 12))

        self.run = RunBar(body, "Iniciar Extração", self._tarefa, self.log)
        self.run.grid(row=1, column=0, sticky="ew", pady=(4, 8))

    def _tarefa(self, run: RunBar):
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import AconexConfig, extrair_base, nome_arquivo_padrao, salvar_excel
        try:
            proxy = self.entry_proxy.get().strip()
            config = AconexConfig.para_usuario(self.opt_user.get(), proxy=proxy if proxy else None)
        except (KeyError, ValueError) as e:
            self.log.log(f"ERRO: {e}")
            return
        run.set_progress(0.1)
        self.log.log("Extração iniciada (pode levar vários minutos)...")
        df = extrair_base(config, log_cb=self.log.log)
        if df.empty:
            self.log.log("Nenhum dado retornado.")
            return
        saida = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                             initialfile=nome_arquivo_padrao(),
                                             filetypes=[("Excel", "*.xlsx")])
        if not saida:
            self.log.log("Salvamento cancelado (dados perdidos da memória).")
            return
        salvar_excel(df, saida)
        run.set_progress(1.0)
        self.log.log(f"Concluído: {len(df)} linhas salvas.")
        self.after(0, lambda: messagebox.showinfo("Extração Aconex", f"{len(df)} linhas extraídas."))
