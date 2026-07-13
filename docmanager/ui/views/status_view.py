from __future__ import annotations

from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView
from .delta_view import _flatten


class StatusDocsView(BaseView):
    titulo_view = "Status Documentos"
    subtitulo_view = "Status real de códigos e Delta flexível por metadado (sem depender do mapa)"

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Base Aconex")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.sel = card.add(FileSelector(card, "Base Aconex", cfg, "aconex"))

        self.tabs = ctk.CTkTabview(body, fg_color=t.CARD, segmented_button_selected_color=t.ACENTO,
                                   segmented_button_selected_hover_color=t.ACENTO_HOVER)
        self.tabs.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._montar_status(self.tabs.add("🔎 Status atual"))
        self._montar_delta(self.tabs.add("⏳ Delta por período"))

        self.log = LogConsole(body, height=200)
        self.log.grid(row=2, column=0, sticky="nsew", pady=(6, 0))
        self._ultimo = None

    # ---- Aba: status atual ----
    def _montar_status(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        opc = ctk.CTkFrame(aba, fg_color="transparent")
        opc.grid(row=0, column=0, sticky="w", pady=6, padx=6)
        ctk.CTkLabel(opc, text="Tipo do código:", font=t.corpo(12), text_color=t.TEXTO).pack(side="left", padx=(0, 8))
        self.tipo = ctk.CTkOptionMenu(opc, values=["Itaipu", "CMI"], width=110, font=t.corpo(12),
                                      fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.tipo.pack(side="left")
        self.usar_base = ctk.CTkCheckBox(opc, text="Toda a base (Current)", font=t.corpo(12), command=self._toggle_base)
        self.usar_base.pack(side="left", padx=18)
        self.txt = ctk.CTkTextbox(aba, height=110, font=t.mono(11), fg_color="#0B1119")
        self.txt.grid(row=1, column=0, sticky="ew", padx=6, pady=(2, 6))
        RunBar(aba, "Analisar Status", self._tarefa_status, None).grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 8))

    def _toggle_base(self):
        self.txt.configure(state="disabled" if self.usar_base.get() else "normal")

    # ---- Aba: delta flexível ----
    def _montar_delta(self, aba):
        from ...core.snapshots import METADADOS_AGRUPAVEIS
        aba.grid_columnconfigure(0, weight=1)
        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.grid(row=0, column=0, sticky="w", pady=6, padx=6)
        hoje = datetime.now()
        ctk.CTkLabel(linha, text="De:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=0, padx=(0, 4))
        self.dt_ini = ctk.CTkEntry(linha, width=100, font=t.corpo(12))
        self.dt_ini.insert(0, (hoje - timedelta(days=30)).strftime("%d/%m/%Y"))
        self.dt_ini.grid(row=0, column=1)
        ctk.CTkLabel(linha, text="Até:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=2, padx=(12, 4))
        self.dt_fim = ctk.CTkEntry(linha, width=100, font=t.corpo(12))
        self.dt_fim.insert(0, hoje.strftime("%d/%m/%Y"))
        self.dt_fim.grid(row=0, column=3)
        ctk.CTkLabel(linha, text="Agrupar por:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=4, padx=(16, 4))
        self.agrup = ctk.CTkOptionMenu(linha, values=METADADOS_AGRUPAVEIS, width=190, font=t.corpo(12),
                                       fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.agrup.grid(row=0, column=5)
        ctk.CTkLabel(linha, text="Visão:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=6, padx=(16, 4))
        self.visao = ctk.CTkOptionMenu(linha, values=["Efetiva", "Bruta"], width=100, font=t.corpo(12),
                                       fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.visao.grid(row=0, column=7)
        ctk.CTkLabel(aba, text="Analisa TODA a base agrupada pelo metadado escolhido (roda em segundo plano).",
                     font=t.corpo(11), text_color=t.TEXTO_FRACO).grid(row=1, column=0, sticky="w", padx=6, pady=(2, 4))
        RunBar(aba, "Analisar Mudanças", self._tarefa_delta, None).grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 8))

    def _carregar(self, run):
        from ...services.excel_io import carregar_base_aconex
        if not self.sel.path:
            self.log.log("Selecione a base Aconex.")
            return None
        self.log.log("Lendo base...")
        run.set_progress(0.3)
        return carregar_base_aconex(self.sel.path, self.sel.sheet)

    def _tarefa_status(self, run: RunBar):
        base = self._carregar(run)
        if base is None:
            return
        from ...core.reports.status_docs import analisar_status_documentos
        from ...services.excel_io import exportar_dataframe
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
        for st, n in df["Status Real"].value_counts().items():
            self.log.log(f"  {st}: {n}")
        nome = f"Status_Docs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        saida = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome, filetypes=[("Excel", "*.xlsx")])
        if saida:
            ok, msg = exportar_dataframe(df, saida, sheet_name="Status")
            self.log.log(msg)

    def _tarefa_delta(self, run: RunBar):
        base = self._carregar(run)
        if base is None:
            return
        from ...core.snapshots import calcular_mudancas_base
        self.log.log(f"Delta {self.dt_ini.get()} → {self.dt_fim.get()} por {self.agrup.get()} ({self.visao.get()})...")
        run.set_progress(0.6)
        ok, arvore, total = calcular_mudancas_base(
            base, self.dt_ini.get(), self.dt_fim.get(),
            coluna_agrupar=self.agrup.get(), tipo_visao=self.visao.get())
        run.set_progress(0.95)
        if not ok:
            self.log.log(f"ERRO: {arvore}")
            return
        self.log.log(f"\n{total} mudanças:")
        for grupo, niveis in sorted(arvore.items()):
            qt = sum(len(v) for v in niveis.values())
            self.log.log(f"  ▸ {grupo}: {qt}")
        self._ultimo = _flatten(arvore)
        if self._ultimo and messagebox.askyesno("Delta", f"{total} mudanças. Exportar?"):
            import pandas as pd
            from ...services.excel_io import exportar_dataframe
            saida = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                 initialfile=f"Delta_{self.agrup.get()}.xlsx", filetypes=[("Excel", "*.xlsx")])
            if saida:
                _, msg = exportar_dataframe(pd.DataFrame(self._ultimo), saida, sheet_name="Delta")
                self.log.log(msg)
