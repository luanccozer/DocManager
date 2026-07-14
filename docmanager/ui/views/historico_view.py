from __future__ import annotations

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, RunBar
from .base import BaseView


class HistoricoView(BaseView):
    titulo_view = "Histórico Consolidado"
    subtitulo_view = "Gera a planilha detalhada ou o dashboard executivo, a partir da mesma base"

    def __init__(self, master, ctx):
        self._server = None
        super().__init__(master, ctx)

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Arquivos")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.sel_aconex = card.add(FileSelector(card, "Base Aconex", cfg, "aconex", aba_padrao="Documentos"))
        self.sel_ctrl = card.add(FileSelector(card, "Controle de Documentos (opcional)", cfg, "controle"))

        self.tabs = ctk.CTkTabview(body, fg_color=t.CARD, segmented_button_selected_color=t.ACENTO,
                                   segmented_button_selected_hover_color=t.ACENTO_HOVER)
        self.tabs.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        aba_plan = self.tabs.add("📄 Planilha")
        aba_dash = self.tabs.add("📈 Dashboard")
        aba_plan.grid_columnconfigure(0, weight=1)
        aba_dash.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(aba_plan, text="Excel com 1 linha por revisão + colunas de atraso (Itaipu e CMI).",
                     font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=700).grid(
            row=0, column=0, sticky="w", pady=8, padx=6)
        RunBar(aba_plan, "Gerar Planilha", self._gerar_planilha, self.log).grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))

        ctk.CTkLabel(aba_dash, text="Dashboard web: First Time Right, ciclo de aprovação, status vigente, "
                     "fluxo de envios/retornos, evolução do atraso no tempo e gargalos por especialidade.\n"
                     "Em desenvolvimento — será liberado em breve.",
                     font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=700).grid(
            row=0, column=0, sticky="w", pady=8, padx=6)
        run_dash = RunBar(aba_dash, "Gerar e Abrir Dashboard", self._abrir_dashboard, self.log)
        run_dash.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))
        run_dash.desabilitar("Dashboard (em desenvolvimento)")

    def _base(self, run):
        from ...common import carregar_base_aconex
        from ...controle_backend import ler_controle
        if not self.sel_aconex.path:
            self.log.log("Selecione a base Aconex.")
            return None, None
        self.log.log("Lendo base Aconex...")
        run.set_progress(0.3)
        base = carregar_base_aconex(self.sel_aconex.path, self.sel_aconex.sheet)
        controle = (ler_controle(self.sel_ctrl.path, self.sel_ctrl.sheet, log_cb=self.log.log)
                    if self.sel_ctrl.path else None)
        return base, controle

    def _policy(self):
        from ...historico_backend import DelayPolicy
        return DelayPolicy(base_cmi_0a=self.ctx.config.settings.base_atraso_cmi_0a)

    def _gerar_planilha(self, run: RunBar):
        base, controle = self._base(run)
        if base is None:
            return
        from ...historico_backend import exportar_historico, gerar_historico
        wide = gerar_historico(base, controle, self._policy(), log_cb=self.log.log)
        nome = f"Historico_Consolidado_{datetime.now().strftime('%d.%m.%y_%Hh%Mm')}.xlsx"
        saida = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome, filetypes=[("Excel", "*.xlsx")])
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok, msg = exportar_historico(wide, saida)
        run.set_progress(1.0)
        self.log.log(msg)
        if ok:
            self.after(0, lambda: messagebox.showinfo("Histórico", f"{len(wide)} revisões geradas."))

    def _abrir_dashboard(self, run: RunBar):
        base, controle = self._base(run)
        if base is None:
            return
        from ...historico_backend import DashboardServer, gerar_historico
        self.log.log("Consolidando...")
        run.set_progress(0.7)
        wide = gerar_historico(base, controle, self._policy(), log_cb=self.log.log)
        if self._server is None:
            self._server = DashboardServer(porta=self.ctx.config.settings.dash_port)
        url = self._server.iniciar(wide)
        run.set_progress(1.0)
        self.log.log(f"Dashboard disponível em {url}")
