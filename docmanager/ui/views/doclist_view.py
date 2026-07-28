"""Módulo **Doc List Mapping** — follow-up semanal de uma lista de documentos.

Mesmo fluxo do Mapa dos Planos (base Aconex + planilha + Controle opcional),
com as regras próprias do módulo. Traz também a **Análise por Período**, que
responde "o que está previsto para emitir nos próximos tempos", e um gerador de
planilha modelo com o cabeçalho oficial.
"""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, RunBar, pedir_salvar
from .base import BaseView


class DocListView(BaseView):
    titulo_view = "Doc List Mapping"
    subtitulo_view = ("Follow-up da lista de documentos: status, agrupamento por escopo, "
                      "planejamento de emissão e análise por período")

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Arquivos")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.sel_aconex = card.add(FileSelector(card, "Base Aconex", cfg, "aconex",
                                                aba_padrao="Documentos"))
        self.sel_doclist = card.add(FileSelector(card, "Doc List Mapping", cfg, "doclist"))
        self.sel_ctrl = card.add(FileSelector(card, "Controle de Documentos (opcional)",
                                              cfg, "controle"))

        ctk.CTkLabel(card, text=("Do Controle vêm FASE DE PROJETO, DATA PREVISTA EMISSÃO "
                                 "(vence a data mais recente) e DATA REPROGRAMADA (nunca "
                                 "sobrescreve o que já está preenchido)."),
                     font=t.corpo(11), text_color=t.TEXTO_FRACO, justify="left",
                     wraplength=820, anchor="w").grid(row=card._linha, column=0, sticky="w",
                                                      padx=16, pady=(0, 12))

        linha = ctk.CTkFrame(body, fg_color="transparent")
        linha.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(linha, text="🗓️ Analisar Período (previstos para emitir)", width=310,
                      font=t.corpo(12), fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._abrir_periodo).pack(side="left")
        ctk.CTkButton(linha, text="📄 Criar planilha modelo", width=190, font=t.corpo(12),
                      fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._criar_modelo).pack(side="right")

        self.run = RunBar(body, "Iniciar Atualização", self._tarefa, self.log)
        self.run.grid(row=2, column=0, sticky="ew", pady=(4, 8))

    # ------------------------------------------------------------------
    def _criar_modelo(self):
        from ...doclist_backend import criar_modelo
        caminho = pedir_salvar(self.ctx.config, "doclist", "Doc_List_Mapping.xlsx",
                               titulo="Criar planilha modelo")
        if not caminho:
            return
        ok, msg = criar_modelo(caminho)
        self.log.log(msg)
        (messagebox.showinfo if ok else messagebox.showerror)("Doc List Mapping", msg)

    def _abrir_periodo(self):
        if not self.sel_doclist.path:
            messagebox.showwarning("Aviso", "Selecione a planilha do Doc List Mapping primeiro.")
            return
        from .periodo_dialog import PeriodoDialog
        PeriodoDialog(self, path_doclist=self.sel_doclist.path, sheet=self.sel_doclist.sheet)

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
