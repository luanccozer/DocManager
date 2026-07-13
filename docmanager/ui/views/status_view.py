from __future__ import annotations

from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView


class StatusDocsView(BaseView):
    titulo_view = "Status Documentos"
    subtitulo_view = "Status real de uma lista de códigos (ou de toda a base)"

    def montar(self, body):
        card = Card(body, "Entrada")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.sel = card.add(FileSelector(card, "Base Aconex", self.ctx.config, "aconex"))

        opc = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(opc, text="Tipo do código:", font=t.corpo(12), text_color=t.TEXTO).pack(side="left", padx=(0, 8))
        self.tipo = ctk.CTkOptionMenu(opc, values=["Itaipu", "CMI"], width=120, font=t.corpo(12),
                                      fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.tipo.pack(side="left")
        self.usar_base = ctk.CTkCheckBox(opc, text="Analisar toda a base (Current)", font=t.corpo(12),
                                         command=self._toggle_base)
        self.usar_base.pack(side="left", padx=20)
        card.add(opc)

        ctk.CTkLabel(card, text="Cole os códigos (um por linha):", font=t.corpo(11),
                     text_color=t.TEXTO_FRACO, anchor="w").grid(row=card._linha, column=0, sticky="w", padx=16)
        card._linha += 1
        self.txt = ctk.CTkTextbox(card, height=120, font=t.mono(11), fg_color="#0B1119")
        card.add(self.txt, pady=(2, 12))

        self.log = LogConsole(body, height=200)
        RunBar(body, "Analisar Status", self._tarefa, self.log).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.log.grid(row=2, column=0, sticky="nsew", pady=(4, 0))

    def _toggle_base(self):
        estado = "disabled" if self.usar_base.get() else "normal"
        self.txt.configure(state=estado)

    def _tarefa(self, run: RunBar):
        if not self.sel.path:
            self.log.log("Selecione a base Aconex.")
            return
        from ...core.reports.status_docs import analisar_status_documentos
        from ...services.excel_io import carregar_base_aconex, exportar_dataframe
        self.log.log("Lendo base...")
        run.set_progress(0.3)
        base = carregar_base_aconex(self.sel.path, self.sel.sheet)
        tipo = "itaipu" if self.tipo.get() == "Itaipu" else "cmi"
        col = "No. do Documento" if tipo == "itaipu" else "Controle do Emissor"
        if self.usar_base.get():
            cur = base[base["Current"].astype(str).str.lower() == "true"]
            codigos = sorted(c for c in cur[col].astype(str).str.strip().unique() if c)
        else:
            codigos = [c.strip() for c in self.txt.get("1.0", "end").splitlines() if c.strip()]
        if not codigos:
            self.log.log("Nenhum código informado.")
            return
        self.log.log(f"Analisando {len(codigos)} códigos...")
        run.set_progress(0.6)
        df = analisar_status_documentos(base, codigos, tipo_codigo=tipo)
        resumo = df["Status Real"].value_counts()
        for st, n in resumo.items():
            self.log.log(f"  {st}: {n}")
        nome = f"Status_Docs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        saida = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome,
                                             filetypes=[("Excel", "*.xlsx")])
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok, msg = exportar_dataframe(df, saida, sheet_name="Status")
        run.set_progress(1.0)
        self.log.log(msg)
        if ok:
            self.after(0, lambda: messagebox.showinfo("Status Documentos", f"{len(df)} documentos analisados."))
