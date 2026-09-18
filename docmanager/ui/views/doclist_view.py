"""Módulo **Doc List Mapping** - follow-up semanal de uma lista de documentos.

Mesmo fluxo do Mapa dos Planos (base Aconex + planilha + Controle opcional),
com as regras próprias do módulo. Traz as duas análises por período, que se
complementam: **Analisar Período** olha para FRENTE (o que está previsto para
emitir, pelas datas de planejamento) e **Delta** olha para TRÁS (o que mudou de
status entre duas datas, pelo histórico do Aconex).
"""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, RunBar
from .base import BaseView


class DocListView(BaseView):
    titulo_view = "Doc List Mapping"
    subtitulo_view = ("Follow-up da lista de documentos: status, agrupamento por escopo, "
                      "planejamento de emissão e análises por período")

    # Colunas que o Delta lê da planilha - mesmos nomes do Mapa dos Planos.
    _COLS_CFG = {"doc": "N° ITAIPU", "grupo": "GRUPO", "sistema": "SISTEMA",
                 "nivel": "NÍVEL", "titulo": "DESCRIÇÃO DO DOCUMENTO",
                 "predecessor": "PREDECESSOR"}

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Arquivos")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.sel_aconex = card.add(FileSelector(card, "Base Aconex", cfg, "aconex",
                                                aba_padrao="Documentos"))
        self.sel_doclist = card.add(FileSelector(card, "Doc List Mapping", cfg, "doclist"))
        self.sel_ctrl = card.add(FileSelector(card, "Controle de Documentos (opcional)",
                                              cfg, "controle"))

        ctk.CTkLabel(card, text=("Do Controle vêm DATA PREVISTA EMISSÃO (vence a data mais "
                                 "recente), DATA REPROGRAMADA (nunca sobrescreve o que já "
                                 "está preenchido) e a descrição dos documentos que o Aconex "
                                 "ainda não conhece. FASE DE PROJETO é preenchida à mão."),
                     font=t.corpo(11), text_color=t.TEXTO_FRACO, justify="left",
                     wraplength=820, anchor="w").grid(row=card._linha, column=0, sticky="w",
                                                      padx=16, pady=(0, 12))

        linha = ctk.CTkFrame(body, fg_color="transparent")
        linha.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(linha, text="🗓️ Analisar Período (previstos para emitir)", width=300,
                      font=t.corpo(12), fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._abrir_periodo).pack(side="left")
        ctk.CTkButton(linha, text="⏳ Analisar Mudanças por Período (Delta)", width=290,
                      font=t.corpo(12), fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._abrir_delta).pack(side="right")

        self.run = RunBar(body, "Iniciar Atualização", self._tarefa, self.log)
        self.run.grid(row=2, column=0, sticky="ew", pady=(4, 8))

    # ------------------------------------------------------------------
    def _abrir_periodo(self):
        """O que está previsto para emitir (olha para FRENTE, pelo planejamento)."""
        if not self.sel_doclist.path:
            messagebox.showwarning("Aviso", "Selecione a planilha do Doc List Mapping primeiro.")
            return
        from .periodo_dialog import PeriodoDialog
        PeriodoDialog(self, path_doclist=self.sel_doclist.path, sheet=self.sel_doclist.sheet)

    def _abrir_delta(self):
        """O que ACONTECEU entre duas datas (olha para trás, pelo Aconex).

        Mesmo motor do Mapa dos Planos: as colunas de que ele precisa têm os
        mesmos nomes neste layout. `estrito=False` fixo - a regra das planilhas
        VIP é de níveis 3/4, que não existem aqui."""
        if not self.sel_doclist.path:
            messagebox.showwarning("Aviso", "Selecione a planilha do Doc List Mapping primeiro.")
            return
        if not self.sel_aconex.path:
            messagebox.showwarning("Aviso", "Selecione a Base Aconex para prosseguir.")
            return
        from .delta_dialog import DeltaDialog
        cfg = dict(self._COLS_CFG)
        try:
            import openpyxl

            from ...doclist_backend import DocListSheet
            wb = openpyxl.load_workbook(self.sel_doclist.path, read_only=True)
            ws = (wb[self.sel_doclist.sheet]
                  if self.sel_doclist.sheet and not isinstance(self.sel_doclist.sheet, int)
                  else wb.active)
            cfg["header_row"] = DocListSheet(ws).row_header
            wb.close()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Erro", f"Não foi possível ler o cabeçalho do Doc List:\n{e}")
            return
        DeltaDialog(self, path_map=self.sel_doclist.path, sheet_map=self.sel_doclist.sheet,
                    path_hist=self.sel_aconex.path, sheet_hist=self.sel_aconex.sheet,
                    cols_config=cfg, estrito=False,
                    titulo="Doc List Mapping - Mudanças por Período (Delta)")

    def _tarefa(self, run: RunBar):
        if not self.sel_aconex.path or not self.sel_doclist.path:
            self.log.log("Selecione a base Aconex e a planilha do Doc List Mapping.")
            return
        from ...controle_backend import ler_controle
        from ...doclist_backend import atualizar_doclist
        controle = (ler_controle(self.sel_ctrl.path, self.sel_ctrl.sheet, log_cb=self.log.log)
                    if self.sel_ctrl.path else None)
        if controle is None:
            self.log.log("Sem Controle de Documentos: fase e datas de planejamento não serão "
                         "atualizadas (o restante roda normalmente).")
        r = atualizar_doclist(
            self.sel_aconex.path, self.sel_doclist.path,
            sheet_aconex=self.sel_aconex.sheet, sheet_doclist=self.sel_doclist.sheet,
            controle=controle, log_cb=self.log.log, progress_cb=run.set_progress,
            retry_cb=lambda m: messagebox.askretrycancel("Salvar", m))
        self.log.log(r.mensagem)
        if r.ok:
            self.after(0, lambda: messagebox.showinfo("Doc List Mapping", r.mensagem))
