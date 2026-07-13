from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView


class MapaView(BaseView):
    titulo_view = "Mapa dos Planos"
    subtitulo_view = "Atualiza status, hierarquia, KPIs e resumos da planilha de mapeamento"

    _COLS_CFG = {"doc": "N° ITAIPU", "grupo": "GRUPO", "sistema": "SISTEMA",
                 "nivel": "NÍVEL", "titulo": "DESCRIÇÃO DO DOCUMENTO", "predecessor": "PREDECESSOR"}

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Arquivos")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.sel_aconex = card.add(FileSelector(card, "Base Aconex", cfg, "aconex", aba_padrao="Documentos"))
        self.sel_mapa = card.add(FileSelector(card, "Mapeamento de Planos", cfg, "mapa"))
        self.sel_ctrl = card.add(FileSelector(card, "Controle de Documentos (opcional)", cfg, "controle"))

        linha = ctk.CTkFrame(body, fg_color="transparent")
        linha.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.lbl_vip = ctk.CTkLabel(linha, text="", font=t.corpo(12), text_color=t.TEXTO_FRACO)
        self.lbl_vip.pack(side="left")
        ctk.CTkButton(linha, text="⏳ Analisar Mudanças por Período (Delta)", width=280,
                      font=t.corpo(12), fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._abrir_delta).pack(side="right")
        self._atualizar_vip()

        self.log = LogConsole(body, height=260)
        self.run = RunBar(body, "Iniciar Atualização", self._tarefa, self.log)
        self.run.grid(row=2, column=0, sticky="ew", pady=(4, 8))
        self.log.grid(row=3, column=0, sticky="nsew", pady=(4, 0))

    def _abrir_delta(self):
        if not self.sel_mapa.path:
            messagebox.showwarning("Aviso", "Selecione a Planilha de Mapeamento primeiro.")
            return
        if not self.sel_aconex.path:
            messagebox.showwarning("Aviso", "Selecione a Base Aconex para prosseguir.")
            return
        from ..views.delta_dialog import DeltaDialog
        cfg = dict(self._COLS_CFG)
        try:
            import openpyxl
            from ...services.excel_io import MappingSheet
            wb = openpyxl.load_workbook(self.sel_mapa.path, read_only=True)
            ws = wb[self.sel_mapa.sheet] if self.sel_mapa.sheet and not isinstance(self.sel_mapa.sheet, int) else wb.active
            cfg["header_row"] = MappingSheet(ws).row_header
            wb.close()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Erro", f"Não foi possível ler o cabeçalho do mapeamento:\n{e}")
            return
        DeltaDialog(self, path_map=self.sel_mapa.path, sheet_map=self.sel_mapa.sheet,
                    path_hist=self.sel_aconex.path, sheet_hist=self.sel_aconex.sheet,
                    cols_config=cfg, estrito=self.ctx.config.settings.regra_estrita_vip)

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
        controle = (ler_controle(self.sel_ctrl.path, self.sel_ctrl.sheet, log_cb=self.log.log)
                    if self.sel_ctrl.path else None)
        r = atualizar_mapeamento(
            self.sel_aconex.path, self.sel_mapa.path,
            sheet_aconex=self.sel_aconex.sheet, sheet_mapping=self.sel_mapa.sheet,
            controle=controle, regra_estrita_vip=self.ctx.config.settings.regra_estrita_vip,
            log_cb=self.log.log, progress_cb=run.set_progress,
            retry_cb=lambda m: messagebox.askretrycancel("Salvar", m))
        self.log.log(r.mensagem)
        if r.ok:
            self.after(0, lambda: messagebox.showinfo("Mapa dos Planos", r.mensagem))
