from __future__ import annotations

from datetime import datetime
from tkinter import filedialog, messagebox

from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView


class HistoricoView(BaseView):
    titulo_view = "Histórico Consolidado"
    subtitulo_view = "1 linha por revisão, com datas/status de envio e retorno e colunas de atraso"

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Arquivos")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.sel_aconex = card.add(FileSelector(card, "Base Aconex", cfg, "aconex"))
        self.sel_ctrl = card.add(FileSelector(card, "Controle de Documentos (opcional)", cfg, "controle"))

        self.log = LogConsole(body, height=280)
        self.run = RunBar(body, "Gerar Histórico", self._tarefa, self.log)
        self.run.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self.log.grid(row=2, column=0, sticky="nsew", pady=(4, 0))

    def _tarefa(self, run: RunBar):
        if not self.sel_aconex.path:
            self.log.log("Selecione a base Aconex.")
            return
        nome = f"Historico_Consolidado_{datetime.now().strftime('%d.%m.%y_%Hh%Mm')}.xlsx"
        saida = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome,
                                             filetypes=[("Excel", "*.xlsx")])
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        from ...services.controle_docs import ler_controle
        from ...services.excel_io import carregar_base_aconex, exportar_historico
        from ...services.historico_consolidado import gerar_historico
        self.log.log("Lendo base Aconex...")
        run.set_progress(0.2)
        base = carregar_base_aconex(self.sel_aconex.path)
        controle = ler_controle(self.sel_ctrl.path, log_cb=self.log.log) if self.sel_ctrl.path else None
        self.log.log(f"{len(base)} linhas. Consolidando...")
        run.set_progress(0.6)
        wide = gerar_historico(base, controle)
        ok, msg = exportar_historico(wide, saida)
        run.set_progress(1.0)
        self.log.log(msg)
        if ok:
            self.after(0, lambda: messagebox.showinfo("Histórico", f"{len(wide)} revisões geradas."))
