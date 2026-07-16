"""Janela de Análise de Mudanças por Período do Status Documentos.

Mesma ideia da tree do Delta legado do Mapa (CTkToplevel + ttk.Treeview,
Efetiva/Bruta, ocultar aprovados, export Excel), porém SEM a estruturação de
níveis: a árvore é apenas **Classificação (metadado) → Documento**. Opera sobre
os documentos da aba ativa do Status (via `codigos`) ou sobre toda a base
vigente (`is_todos`). Fonte: `status_backend.calcular_mudancas_base`.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

import customtkinter as ctk

from .. import theme as t
from ..components import pedir_salvar

_APROVADOS = {"Aprovado", "Aprovado com Comentários", "Para Assinatura"}


class StatusDeltaDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, path_aconex, sheet_aconex, codigos, is_todos, metadados):
        super().__init__(parent)
        self.title("Análise de Mudanças por Período — Status Documentos")
        self.geometry("1120x600")
        self.configure(fg_color=t.FUNDO)
        self.path_aconex, self.sheet_aconex = path_aconex, sheet_aconex
        self.codigos = codigos
        self.is_todos = is_todos
        self._base = None          # base Aconex carregada (lazy, cacheada)
        self.arvore = None

        self._montar(metadados)
        self._estilo_tree()
        self.lift()
        self.after(80, self.focus_force)

    # ---------------------------------------------------------------- UI
    def _montar(self, metadados):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color=t.CARD)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        hoje = datetime.now()
        ctk.CTkLabel(top, text="Período:", font=t.corpo(12, "bold"), text_color=t.TEXTO).pack(side="left", padx=(12, 6))
        self.entry_ini = ctk.CTkEntry(top, width=105)
        self.entry_ini.insert(0, (hoje - timedelta(days=30)).strftime("%d/%m/%Y"))
        self.entry_ini.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="até", text_color=t.TEXTO_FRACO).pack(side="left", padx=4)
        self.entry_fim = ctk.CTkEntry(top, width=105)
        self.entry_fim.insert(0, hoje.strftime("%d/%m/%Y"))
        self.entry_fim.pack(side="left", padx=4)

        ctk.CTkLabel(top, text="Classificar por:", font=t.corpo(12, "bold"), text_color=t.TEXTO).pack(side="left", padx=(16, 6))
        self.var_agrup = ctk.StringVar(value=metadados[0])
        ctk.CTkOptionMenu(top, variable=self.var_agrup, values=metadados, width=175,
                          fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO).pack(side="left", padx=4)

        ctk.CTkLabel(top, text="Visão:", font=t.corpo(12, "bold"), text_color=t.TEXTO).pack(side="left", padx=(16, 6))
        self.var_visao = ctk.StringVar(value="Efetiva")
        ctk.CTkSegmentedButton(top, variable=self.var_visao, values=["Efetiva", "Bruta"],
                               selected_color=t.ACENTO, selected_hover_color=t.ACENTO_HOVER,
                               command=lambda _: self._repovoar()).pack(side="left", padx=4)

        self.btn_filtrar = ctk.CTkButton(top, text="Verificar Mudanças", command=self._executar,
                                         fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER, width=155)
        self.btn_filtrar.pack(side="left", padx=16)
        self.var_ocultar = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Ocultar se já estava Aprovado", variable=self.var_ocultar,
                        command=self._repovoar).pack(side="left", padx=8)

        alvo = "toda a base vigente" if self.is_todos else f"{len(self.codigos or [])} documento(s) da aba"
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        cols = ("info_antes", "raw_antes", "real_antes", "seta", "info_depois", "raw_depois", "real_depois")
        self.tree = ttk.Treeview(tree_frame, columns=cols, selectmode="browse")
        self.tree.heading("#0", text="Classificação / Documento", anchor="w")
        for c, txt, w in [("info_antes", "Rev/Data (Antes)", 120), ("raw_antes", "Aconex (Antes)", 135),
                          ("real_antes", "Efetivo (Antes)", 135), ("seta", " ", 30),
                          ("info_depois", "Rev/Data (Depois)", 120), ("raw_depois", "Aconex (Depois)", 135),
                          ("real_depois", "Efetivo (Depois)", 135)]:
            self.tree.heading(c, text=txt, anchor="w")
            self.tree.column(c, width=w, minwidth=w, anchor="center" if c == "seta" else "w")
        self.tree.column("#0", width=300, minwidth=200)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._duplo_clique)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.lbl_status = ctk.CTkLabel(footer, text=f"Analisando {alvo}. Informe o período e clique em Verificar Mudanças.",
                                       text_color=t.TEXTO_FRACO, font=t.corpo(12))
        self.lbl_status.pack(side="left")
        self.btn_exportar = ctk.CTkButton(footer, text="📊 Exportar Excel", command=self._exportar,
                                          fg_color=t.SIDEBAR_ATIVO, state="disabled")
        self.btn_exportar.pack(side="right")

    def _estilo_tree(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=t.CARD, foreground=t.TEXTO, fieldbackground=t.CARD,
                        rowheight=30, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading", background=t.SIDEBAR, foreground=t.TEXTO,
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", t.ACENTO)])

    # ------------------------------------------------------------ ações
    def _executar(self):
        dt_ini, dt_fim = self.entry_ini.get().strip(), self.entry_fim.get().strip()
        if not dt_ini or not dt_fim:
            messagebox.showwarning("Aviso", "Preencha as duas datas.", parent=self)
            return
        self.btn_filtrar.configure(state="disabled", text="Processando...")
        self.lbl_status.configure(text="Cruzando dados... aguarde.")
        threading.Thread(target=self._worker, args=(dt_ini, dt_fim), daemon=True).start()

    def _worker(self, dt_ini, dt_fim):
        from ...common import carregar_base_aconex
        from ...status_backend import calcular_mudancas_base
        try:
            if self._base is None:
                self._base = carregar_base_aconex(self.path_aconex, self.sheet_aconex)
            cods = None if self.is_todos else self.codigos
            ok, arvore, total = calcular_mudancas_base(
                self._base, dt_ini, dt_fim,
                coluna_agrupar=self.var_agrup.get(), tipo_visao=self.var_visao.get(), codigos=cods)
        except Exception as e:  # noqa: BLE001
            ok, arvore, total = False, str(e), 0
        self.after(0, self._concluir, ok, arvore, total)

    def _concluir(self, ok, arvore, total):
        self.btn_filtrar.configure(state="normal", text="Verificar Mudanças")
        if not ok:
            messagebox.showerror("Erro", f"Falha: {arvore}", parent=self)
            self.lbl_status.configure(text="Erro na análise.")
            self.btn_exportar.configure(state="disabled")
            return
        self.arvore = arvore
        self._repovoar()
        self.lbl_status.configure(text=f"Análise concluída. {total} mudança(s) por {self.var_agrup.get()}.")
        self.btn_exportar.configure(state="normal" if total else "disabled")

    def _itens_do_grupo(self, grupo):
        """Achata os itens do grupo (o Delta da base usa o nível único '—')."""
        return [it for lst in self.arvore[grupo].values() for it in lst]

    def _repovoar(self):
        self.tree.delete(*self.tree.get_children())
        if not self.arvore:
            return
        self.tree.heading("#0", text=f"{self.var_agrup.get()} / Documento")
        if self.var_visao.get() == "Efetiva":
            self.tree.configure(displaycolumns=("raw_antes", "real_antes", "seta", "raw_depois", "real_depois"))
        else:
            self.tree.configure(displaycolumns=("info_antes", "raw_antes", "real_antes", "seta",
                                                "info_depois", "raw_depois", "real_depois"))
        ocultar = self.var_ocultar.get()
        exibidos = 0
        for grupo in sorted(self.arvore.keys()):
            itens = [d for d in self._itens_do_grupo(grupo)
                     if not (ocultar and str(d["real_antes"]).strip() in _APROVADOS)]
            if not itens:
                continue
            id_g = self.tree.insert("", "end", text=f"📂 {grupo} ({len(itens)})", open=True)
            for d in itens:
                exibidos += 1
                info_a = f"Rev {d.get('rev_antes', '-')} ({d.get('data_antes', '-')})" if d.get("rev_antes", "-") != "-" else "-"
                info_d = f"Rev {d.get('rev_depois', '-')} ({d.get('data_depois', '-')})" if d.get("rev_depois", "-") != "-" else "-"
                self.tree.insert(id_g, "end", text=f"📄 {d['doc']}",
                                 values=(info_a, d["raw_antes"], d["real_antes"], "➜",
                                         info_d, d["raw_depois"], d["real_depois"]))
        if ocultar:
            self.lbl_status.configure(text=f"Exibindo {exibidos} documento(s) (filtro ativo).")

    def _duplo_clique(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        texto = self.tree.item(item, "text")
        if "📄" in texto:
            codigo = texto.replace("📄", "").strip()
            self.clipboard_clear()
            self.clipboard_append(codigo)
            self.update()
            messagebox.showinfo("Copiado", f"Código copiado:\n{codigo}", parent=self)

    def _exportar(self):
        if not self.arvore:
            return
        import pandas as pd

        from ...common import exportar_dataframe
        ocultar = self.var_ocultar.get()
        linhas = []
        for grupo in sorted(self.arvore.keys()):
            for d in self._itens_do_grupo(grupo):
                if ocultar and str(d["real_antes"]).strip() in _APROVADOS:
                    continue
                linhas.append({
                    self.var_agrup.get(): grupo, "Documento": d["doc"], "Título": d["titulo"],
                    "Status Aconex (Antes)": d["raw_antes"], "Status Efetivo (Antes)": d["real_antes"],
                    "Status Aconex (Depois)": d["raw_depois"], "Status Efetivo (Depois)": d["real_depois"],
                    "Rev (Antes)": d.get("rev_antes", "-"), "Data (Antes)": d.get("data_antes", "-"),
                    "Rev (Depois)": d.get("rev_depois", "-"), "Data (Depois)": d.get("data_depois", "-"),
                })
        if not linhas:
            messagebox.showinfo("Delta", "Nada a exportar.", parent=self)
            return
        d1 = self.entry_ini.get().strip().replace("/", ".")
        d2 = self.entry_fim.get().strip().replace("/", ".")
        ctx = getattr(getattr(self, "master", None), "ctx", None)
        caminho = pedir_salvar(getattr(ctx, "config", None), "saida",
                               f"Delta_Status_{d1}_ate_{d2}.xlsx", parent=self)
        if not caminho:
            return
        ok, msg = exportar_dataframe(pd.DataFrame(linhas), caminho, sheet_name="Delta")
        (messagebox.showinfo if ok else messagebox.showerror)("Exportação", msg, parent=self)
