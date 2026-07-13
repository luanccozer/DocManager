"""Janela de Análise Delta ("Máquina do Tempo") — aberta de DENTRO do Mapa.

Porta fiel da `DeltaView` legada (CTkToplevel + ttk.Treeview): mesmo layout de
árvore Grupo/Nível/Documento, visões Efetiva/Bruta, filtro "ocultar aprovados" e
exportação Excel. A lógica vem de `core.snapshots.calcular_mudancas_periodo`
(que respeita o toggle da regra estrita via `estrito`).
"""
from __future__ import annotations

import threading
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from .. import theme as t

_STATUS_APROVADOS = ["Aprovado", "Aprovado com Comentários", "Para Assinatura"]


class DeltaDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, path_map, sheet_map, path_hist, sheet_hist,
                 cols_config, estrito=False):
        super().__init__(parent)
        self.title("Análise de Mudanças por Período (Delta)")
        self.geometry("1180x620")
        self.configure(fg_color=t.FUNDO)
        self.path_map, self.sheet_map = path_map, sheet_map
        self.path_hist, self.sheet_hist = path_hist, sheet_hist
        self.cols_config = cols_config
        self.estrito = estrito
        self.dados_cache = None

        self._montar()
        self._estilo_tree()
        self.lift()
        self.after(80, self.focus_force)

    # ---------------------------------------------------------------- UI
    def _montar(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color=t.CARD)
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        hoje = datetime.now()
        ctk.CTkLabel(top, text="Período:", font=t.corpo(12, "bold"), text_color=t.TEXTO).pack(side="left", padx=(12, 6))
        self.entry_ini = ctk.CTkEntry(top, placeholder_text="DD/MM/AAAA", width=110)
        self.entry_ini.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="até", text_color=t.TEXTO_FRACO).pack(side="left", padx=4)
        self.entry_fim = ctk.CTkEntry(top, placeholder_text="DD/MM/AAAA", width=110)
        self.entry_fim.insert(0, hoje.strftime("%d/%m/%Y"))
        self.entry_fim.pack(side="left", padx=4)

        ctk.CTkLabel(top, text="Agrupar:", font=t.corpo(12, "bold"), text_color=t.TEXTO).pack(side="left", padx=(16, 6))
        self.var_agrup = ctk.StringVar(value="Grupo")
        ctk.CTkOptionMenu(top, variable=self.var_agrup, values=["Grupo", "Sistema"], width=100,
                          fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO).pack(side="left", padx=4)

        ctk.CTkLabel(top, text="Visão:", font=t.corpo(12, "bold"), text_color=t.TEXTO).pack(side="left", padx=(16, 6))
        self.var_visao = ctk.StringVar(value="Efetiva")
        ctk.CTkSegmentedButton(top, variable=self.var_visao, values=["Efetiva", "Bruta"],
                               selected_color=t.ACENTO, selected_hover_color=t.ACENTO_HOVER,
                               command=lambda _: self._repovoar()).pack(side="left", padx=4)

        self.btn_filtrar = ctk.CTkButton(top, text="Verificar Mudanças", command=self._executar,
                                         fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER, width=160)
        self.btn_filtrar.pack(side="left", padx=16)
        self.var_ocultar = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Ocultar se já estava Aprovado", variable=self.var_ocultar,
                        command=self._repovoar).pack(side="left", padx=8)

        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        cols = ("info_antes", "raw_antes", "real_antes", "seta", "info_depois", "raw_depois", "real_depois")
        self.tree = ttk.Treeview(tree_frame, columns=cols, selectmode="browse")
        self.tree.heading("#0", text="Grupo / Nível / Documento", anchor="w")
        for c, txt, w in [("info_antes", "Rev/Data (Antes)", 120), ("raw_antes", "Aconex (Antes)", 130),
                          ("real_antes", "Efetivo (Antes)", 130), ("seta", " ", 30),
                          ("info_depois", "Rev/Data (Depois)", 120), ("raw_depois", "Aconex (Depois)", 130),
                          ("real_depois", "Efetivo (Depois)", 130)]:
            self.tree.heading(c, text=txt, anchor="w")
            self.tree.column(c, width=w, minwidth=w, anchor="center" if c == "seta" else "w")
        self.tree.column("#0", width=320, minwidth=200)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._duplo_clique)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.lbl_status = ctk.CTkLabel(footer, text="Informe o período e clique em Verificar Mudanças.",
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
        from ...mapa_backend import calcular_mudancas_periodo
        try:
            ok, arvore, total = calcular_mudancas_periodo(
                self.path_map, self.sheet_map, self.path_hist, self.sheet_hist,
                dt_ini, dt_fim, self.cols_config,
                agrupador_escolhido=self.var_agrup.get(), tipo_visao=self.var_visao.get(),
                estrito=self.estrito)
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
        self.dados_cache = arvore
        self._repovoar()
        self.lbl_status.configure(text=f"Análise concluída. Base bruta: {total} alterações.")
        self.btn_exportar.configure(state="normal" if total else "disabled")

    def _repovoar(self):
        self.tree.delete(*self.tree.get_children())
        if not self.dados_cache:
            return
        nome_agr = self.var_agrup.get()
        self.tree.heading("#0", text=f"{nome_agr} / Nível / Documento")
        if self.var_visao.get() == "Efetiva":
            self.tree.configure(displaycolumns=("raw_antes", "real_antes", "seta", "raw_depois", "real_depois"))
        else:
            self.tree.configure(displaycolumns=("info_antes", "raw_antes", "real_antes", "seta",
                                                "info_depois", "raw_depois", "real_depois"))
        ocultar = self.var_ocultar.get()
        exibidos = 0
        for grupo in sorted(self.dados_cache.keys()):
            filtrado, total_grupo = {}, 0
            for nivel, docs in self.dados_cache[grupo].items():
                validos = [d for d in docs if not (ocultar and str(d["real_antes"]).strip() in _STATUS_APROVADOS)]
                if validos:
                    filtrado[nivel] = validos
                    total_grupo += len(validos)
            if not total_grupo:
                continue
            id_g = self.tree.insert("", "end", text=f"📂 {grupo} ({total_grupo})", open=True)
            for nivel in sorted(filtrado.keys()):
                docs = filtrado[nivel]
                id_n = self.tree.insert(id_g, "end", text=f"L {nivel} ({len(docs)})", open=True)
                for d in docs:
                    exibidos += 1
                    info_a = f"Rev {d.get('rev_antes', '-')} ({d.get('data_antes', '-')})" if d.get("rev_antes", "-") != "-" else "-"
                    info_d = f"Rev {d.get('rev_depois', '-')} ({d.get('data_depois', '-')})" if d.get("rev_depois", "-") != "-" else "-"
                    self.tree.insert(id_n, "end", text=f"📄 {d['doc']}",
                                     values=(info_a, d["raw_antes"], d["real_antes"], "➜",
                                             info_d, d["raw_depois"], d["real_depois"]))
        if ocultar:
            self.lbl_status.configure(text=f"Exibindo {exibidos} documentos (filtro ativo).")

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
        if not self.dados_cache:
            return
        d1 = self.entry_ini.get().strip().replace("/", ".")
        d2 = self.entry_fim.get().strip().replace("/", ".")
        aba = str(self.sheet_map).replace(" ", "_")
        nome = f"Delta_{aba}_{d1}_ate_{d2}.xlsx"
        caminho = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome,
                                               title="Salvar Exportação Delta",
                                               filetypes=[("Excel files", "*.xlsx")], parent=self)
        if not caminho:
            return
        from ...mapa_backend import exportar_delta_arvore
        ok, msg = exportar_delta_arvore(
            self.dados_cache, caminho, agrupador=self.var_agrup.get(), visao=self.var_visao.get(),
            ocultar_aprovados=self.var_ocultar.get())
        if ok:
            messagebox.showinfo("Exportação concluída", msg, parent=self)
        else:
            messagebox.showerror("Erro", msg, parent=self)
