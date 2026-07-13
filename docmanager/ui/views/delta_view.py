from __future__ import annotations

from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView

_COLS_CFG_BASE = {"doc": "N° ITAIPU", "grupo": "GRUPO", "sistema": "SISTEMA",
                  "nivel": "NÍVEL", "titulo": "DESCRIÇÃO DO DOCUMENTO", "predecessor": "PREDECESSOR"}


def _flatten(arvore) -> list[dict]:
    linhas = []
    for grupo, niveis in arvore.items():
        for nivel, itens in niveis.items():
            for it in itens:
                linhas.append({
                    "Grupo": grupo, "Nível": nivel, "Documento": it["doc"], "Título": it["titulo"],
                    "Status Antes": it["real_antes"], "Status Depois": it["real_depois"],
                    "Rev Antes": it["rev_antes"], "Data Antes": it["data_antes"],
                    "Rev Depois": it["rev_depois"], "Data Depois": it["data_depois"],
                })
    return linhas


class DeltaView(BaseView):
    titulo_view = "Análise Delta (Máquina do Tempo)"
    subtitulo_view = "Compara o estado de cada documento entre duas datas"

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Arquivos")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.sel_mapa = card.add(FileSelector(card, "Mapeamento de Planos", cfg, "mapa"))
        self.sel_aconex = card.add(FileSelector(card, "Base Aconex", cfg, "aconex"))

        params = Card(body, "Período e visão")
        params.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        linha = ctk.CTkFrame(params, fg_color="transparent")
        hoje = datetime.now()
        self.dt_ini = self._campo_data(linha, "De:", (hoje - timedelta(days=30)).strftime("%d/%m/%Y"), 0)
        self.dt_fim = self._campo_data(linha, "Até:", hoje.strftime("%d/%m/%Y"), 2)
        ctk.CTkLabel(linha, text="Agrupar por:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=4, padx=(20, 6))
        self.agrup = ctk.CTkOptionMenu(linha, values=["Grupo", "Sistema"], width=110, font=t.corpo(12),
                                       fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.agrup.grid(row=0, column=5)
        ctk.CTkLabel(linha, text="Visão:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=6, padx=(20, 6))
        self.visao = ctk.CTkOptionMenu(linha, values=["Efetiva", "Bruta"], width=110, font=t.corpo(12),
                                       fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.visao.grid(row=0, column=7)
        params.add(linha)

        self.log = LogConsole(body, height=280)
        RunBar(body, "Analisar Mudanças", self._tarefa, self.log).grid(row=2, column=0, sticky="ew", pady=(0, 8))
        self.log.grid(row=3, column=0, sticky="nsew", pady=(4, 0))
        self._ultimo = None

    def _campo_data(self, master, label, valor, col):
        ctk.CTkLabel(master, text=label, font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=col, padx=(0, 6))
        e = ctk.CTkEntry(master, width=110, font=t.corpo(12))
        e.insert(0, valor)
        e.grid(row=0, column=col + 1)
        return e

    def _header_row(self, caminho, sheet):
        import openpyxl
        from ...services.excel_io import MappingSheet
        wb = openpyxl.load_workbook(caminho, read_only=True)
        ws = wb[sheet] if sheet and not isinstance(sheet, int) else wb.active
        return MappingSheet(ws).row_header

    def _tarefa(self, run: RunBar):
        if not self.sel_mapa.path or not self.sel_aconex.path:
            self.log.log("Selecione o mapeamento e a base Aconex.")
            return
        from ...core.snapshots import calcular_mudancas_periodo
        cfg = dict(_COLS_CFG_BASE)
        try:
            cfg["header_row"] = self._header_row(self.sel_mapa.path, self.sel_mapa.sheet)
        except Exception as e:
            self.log.log(f"Aviso: cabeçalho não localizado ({e}). Usando linha 1.")
            cfg["header_row"] = 1
        run.set_progress(0.3)
        self.log.log(f"Comparando {self.dt_ini.get()} → {self.dt_fim.get()} ({self.visao.get()})...")
        ok, arvore, total = calcular_mudancas_periodo(
            self.sel_mapa.path, self.sel_mapa.sheet, self.sel_aconex.path, self.sel_aconex.sheet,
            self.dt_ini.get(), self.dt_fim.get(), cfg,
            agrupador_escolhido=self.agrup.get(), tipo_visao=self.visao.get(),
            estrito=self.ctx.config.settings.regra_estrita_vip)
        run.set_progress(0.9)
        if not ok:
            self.log.log(f"ERRO: {arvore}")
            return
        self.log.log(f"\n{total} mudanças no período:")
        for grupo, niveis in arvore.items():
            self.log.log(f"\n▸ {grupo}")
            for nivel, itens in niveis.items():
                for it in itens:
                    self.log.log(f"    [N{nivel}] {it['doc']}: {it['real_antes']} → {it['real_depois']}")
        self._ultimo = _flatten(arvore)
        if self._ultimo:
            self.after(0, self._perguntar_export)

    def _perguntar_export(self):
        if messagebox.askyesno("Delta", f"{len(self._ultimo)} mudanças. Exportar para Excel?"):
            import pandas as pd
            from ...services.excel_io import exportar_dataframe
            nome = f"Delta_{self.dt_ini.get().replace('/', '')}_ate_{self.dt_fim.get().replace('/', '')}.xlsx"
            saida = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome,
                                                 filetypes=[("Excel", "*.xlsx")])
            if saida:
                ok, msg = exportar_dataframe(pd.DataFrame(self._ultimo), saida, sheet_name="Delta")
                self.log.log(msg)
