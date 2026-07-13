from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView


class MapaView(BaseView):
    titulo_view = "Mapa dos Planos"
    subtitulo_view = "Atualiza status, hierarquia, KPIs e resumos da planilha de mapeamento"

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Arquivos")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.sel_aconex = card.add(FileSelector(card, "Base Aconex", cfg, "aconex"))
        self.sel_mapa = card.add(FileSelector(card, "Mapeamento de Planos", cfg, "mapa"))
        self.sel_ctrl = card.add(FileSelector(card, "Controle de Documentos (opcional)", cfg, "controle"))

        self.lbl_vip = ctk.CTkLabel(body, text="", font=t.corpo(12), text_color=t.TEXTO_FRACO)
        self.lbl_vip.grid(row=1, column=0, sticky="w", pady=(0, 8))
        self._atualizar_vip()

        self.log = LogConsole(body, height=260)
        self.run = RunBar(body, "Iniciar Atualização", self._tarefa, self.log)
        self.run.grid(row=2, column=0, sticky="ew", pady=(4, 8))
        self.log.grid(row=3, column=0, sticky="nsew", pady=(4, 0))

    def _atualizar_vip(self):
        estado = "Ligada" if self.ctx.config.settings.regra_estrita_vip else "Desligada"
        self.lbl_vip.configure(text=f"Regra da Aprovação Intermediária: {estado}  (altere em Configurações)")

    def _tarefa(self, run: RunBar):
        self._atualizar_vip()
        if not self.sel_aconex.path or not self.sel_mapa.path:
            self.log.log("Selecione a base Aconex e o mapeamento.")
            return
        from ...services.controle_docs import ler_controle
        from ...services.mapping_update import atualizar_mapeamento
        controle = ler_controle(self.sel_ctrl.path, log_cb=self.log.log) if self.sel_ctrl.path else None
        r = atualizar_mapeamento(
            self.sel_aconex.path, self.sel_mapa.path, controle=controle,
            regra_estrita_vip=self.ctx.config.settings.regra_estrita_vip,
            log_cb=self.log.log, progress_cb=run.set_progress,
            retry_cb=lambda m: messagebox.askretrycancel("Salvar", m))
        self.log.log(r.mensagem)
        if r.ok:
            self.after(0, lambda: messagebox.showinfo("Mapa dos Planos", r.mensagem))
