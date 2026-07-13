from __future__ import annotations

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView


class ReportsView(BaseView):
    titulo_view = "Relatórios"
    subtitulo_view = "Relatório de Avanço (prazos de devolução) e Auditoria de Integração (0AA)"

    def montar(self, body):
        card = Card(body, "Base Aconex")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.sel = card.add(FileSelector(card, "Base Aconex", self.ctx.config, "aconex"))

        self.log = LogConsole(body, height=260)
        botoes = ctk.CTkFrame(body, fg_color="transparent")
        botoes.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        RunBar(botoes, "Relatório de Avanço", self._avanco, self.log).pack(fill="x", pady=4)
        RunBar(botoes, "Auditoria de Integração", self._integracao, self.log).pack(fill="x", pady=4)
        self.log.grid(row=2, column=0, sticky="nsew", pady=(4, 0))

    def _carregar(self):
        from ...services.excel_io import carregar_base_aconex
        if not self.sel.path:
            self.log.log("Selecione a base Aconex.")
            return None
        self.log.log("Lendo base Aconex...")
        return carregar_base_aconex(self.sel.path, self.sel.sheet)

    def _exportar(self, ok, obj, nome, sheet, run):
        from ...services.excel_io import exportar_dataframe
        if not ok:
            self.log.log(f"ERRO: {obj}")
            return
        if obj is None or obj.empty:
            self.log.log("Nenhuma linha no relatório.")
            return
        saida = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome,
                                             filetypes=[("Excel", "*.xlsx")])
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok2, msg = exportar_dataframe(obj, saida, sheet_name=sheet)
        run.set_progress(1.0)
        self.log.log(msg)
        if ok2:
            self.after(0, lambda: messagebox.showinfo("Relatórios", f"{len(obj)} linhas geradas."))

    def _avanco(self, run: RunBar):
        base = self._carregar()
        if base is None:
            return
        from ...core.reports.avanco import gerar_relatorio_avanco
        run.set_progress(0.6)
        ok, obj = gerar_relatorio_avanco(base)
        nome = f"Relatorio_Avanco_{datetime.now().strftime('%d%m%y')}.xlsx"
        self._exportar(ok, obj, nome, "Avanço", run)

    def _integracao(self, run: RunBar):
        base = self._carregar()
        if base is None:
            return
        from ...core.reports.integracao import auditar_fluxo_integracao
        run.set_progress(0.6)
        df = auditar_fluxo_integracao(base)
        nome = f"Auditoria_Integracao_{datetime.now().strftime('%d%m%y')}.xlsx"
        self._exportar(True, df, nome, "Integração", run)
