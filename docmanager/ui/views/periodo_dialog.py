"""Análise por Período do Doc List Mapping — "o que está previsto para emitir".

Lê a planilha do módulo e lista os documentos cuja **DATA-ALVO EMISSÃO**
(REPROGRAMADA quando existe, senão PREVISTA) cai na janela escolhida. Atalhos
prontos (vencidos, próximos 7/30/90 dias, mês que vem) ou intervalo manual;
árvore agrupada por mês / grupo / sistema / fase; exportação para Excel com uma
aba extra dos documentos ainda **sem planejamento**.
"""
from __future__ import annotations

import threading
from datetime import date, datetime
from tkinter import messagebox, ttk

import customtkinter as ctk

from .. import theme as t

_AGRUPADORES = {"Mês": "mes", "Grupo": "grupo", "Sistema": "sistema", "Fase de Projeto": "fase_projeto"}


class PeriodoDialog(ctk.CTkToplevel):
    def __init__(self, parent, *, path_doclist, sheet=None, hoje: date | None = None):
        super().__init__(parent)
        self.title("Doc List Mapping — Documentos previstos por período")
        self.geometry("1180x640")
        self.configure(fg_color=t.FUNDO)
        self.path_doclist, self.sheet = path_doclist, sheet
        self.hoje = hoje or date.today()
        self._linhas = None          # cache da planilha
        self._itens: list = []
        self._sem_data: list = []
        self._rotulo_janela = ""

        self._montar()
        self._estilo_tree()
        self.lift()
        self.after(80, self.focus_force)

    # ---------------------------------------------------------------- UI
    def _montar(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        from ...doclist_backend import janelas_padrao
        self._janelas = {j.rotulo: j for j in janelas_padrao(self.hoje)}

        atalhos = ctk.CTkFrame(self, fg_color=t.CARD)
        atalhos.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        ctk.CTkLabel(atalhos, text="Atalhos:", font=t.corpo(12, "bold"),
                     text_color=t.TEXTO).pack(side="left", padx=(12, 6), pady=8)
        for rotulo in self._janelas:
            ctk.CTkButton(atalhos, text=rotulo, width=130, height=28, font=t.corpo(11),
                          fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                          command=lambda r=rotulo: self._usar_atalho(r)).pack(side="left", padx=3, pady=8)

        top = ctk.CTkFrame(self, fg_color=t.CARD)
        top.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        ctk.CTkLabel(top, text="De:", font=t.corpo(12, "bold"),
                     text_color=t.TEXTO).pack(side="left", padx=(12, 6))
        self.entry_ini = ctk.CTkEntry(top, placeholder_text="DD/MM/AAAA (vazio = sem limite)", width=170)
        self.entry_ini.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="até", text_color=t.TEXTO_FRACO).pack(side="left", padx=4)
        self.entry_fim = ctk.CTkEntry(top, placeholder_text="DD/MM/AAAA (vazio = sem limite)", width=170)
        self.entry_fim.pack(side="left", padx=4)

        ctk.CTkLabel(top, text="Agrupar:", font=t.corpo(12, "bold"),
                     text_color=t.TEXTO).pack(side="left", padx=(16, 6))
        self.var_agrup = ctk.StringVar(value="Mês")
        ctk.CTkOptionMenu(top, variable=self.var_agrup, values=list(_AGRUPADORES), width=140,
                          fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO,
                          command=lambda _v: self._repovoar()).pack(side="left", padx=4)

        self.var_emitidos = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(top, text="Incluir já emitidos", variable=self.var_emitidos,
                        command=self._executar, font=t.corpo(11)).pack(side="left", padx=12)

        self.btn_filtrar = ctk.CTkButton(top, text="Analisar", command=self._executar,
                                         fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER, width=120)
        self.btn_filtrar.pack(side="left", padx=12, pady=8)

        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        cols = ("data", "origem", "dias", "situacao", "titulo", "cmi", "consolidado", "responsavel")
        self.tree = ttk.Treeview(tree_frame, columns=cols, selectmode="browse")
        self.tree.heading("#0", text="Agrupamento / Documento", anchor="w")
        for c, txt, w, anchor in [("data", "Data-Alvo", 95, "center"),
                                  ("origem", "Origem", 100, "center"),
                                  ("dias", "Dias", 60, "center"),
                                  ("situacao", "Situação", 90, "center"),
                                  ("titulo", "Descrição", 330, "w"),
                                  ("cmi", "Nº CMI", 170, "w"),
                                  ("consolidado", "Consolidado", 150, "w"),
                                  ("responsavel", "Responsible", 100, "w")]:
            self.tree.heading(c, text=txt, anchor="w")
            self.tree.column(c, width=w, minwidth=50, anchor=anchor)
        self.tree.column("#0", width=300, minwidth=200)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", self._duplo_clique)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.lbl_status = ctk.CTkLabel(footer, text="Escolha um atalho ou informe o intervalo.",
                                       text_color=t.TEXTO_FRACO, font=t.corpo(12))
        self.lbl_status.pack(side="left")
        ctk.CTkLabel(footer, text="●  em vermelho: data-alvo já vencida",
                     text_color="#E06C75", font=t.corpo(11)).pack(side="left", padx=(16, 0))
        self.btn_exportar = ctk.CTkButton(footer, text="📊 Exportar Excel", command=self._exportar,
                                          fg_color=t.SIDEBAR_ATIVO, state="disabled")
        self.btn_exportar.pack(side="right")

    def _estilo_tree(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=t.CARD, foreground=t.TEXTO, fieldbackground=t.CARD,
                        rowheight=28, font=("Segoe UI", 10), borderwidth=0)
        style.configure("Treeview.Heading", background=t.SIDEBAR, foreground=t.TEXTO,
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", t.ACENTO)])
        self.tree.tag_configure("vencido", foreground="#E06C75")
        self.tree.tag_configure("emitido", foreground=t.TEXTO_FRACO)

    # ------------------------------------------------------------ ações
    def _usar_atalho(self, rotulo: str):
        janela = self._janelas[rotulo]
        for entry, valor in ((self.entry_ini, janela.inicio), (self.entry_fim, janela.fim)):
            entry.delete(0, "end")
            if valor is not None:
                entry.insert(0, valor.strftime("%d/%m/%Y"))
        self._rotulo_janela = rotulo
        self._executar()

    def _ler_data(self, entry) -> date | None:
        texto = entry.get().strip()
        if not texto:
            return None
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Data inválida: '{texto}'. Use DD/MM/AAAA.")

    def _executar(self):
        try:
            inicio, fim = self._ler_data(self.entry_ini), self._ler_data(self.entry_fim)
        except ValueError as e:
            messagebox.showwarning("Aviso", str(e), parent=self)
            return
        if inicio and fim and inicio > fim:
            messagebox.showwarning("Aviso", "A data inicial é posterior à final.", parent=self)
            return
        self.btn_filtrar.configure(state="disabled", text="Processando...")
        self.lbl_status.configure(text="Lendo a planilha...")
        threading.Thread(target=self._worker, args=(inicio, fim), daemon=True).start()

    def _worker(self, inicio, fim):
        from ...doclist_backend import analisar_periodo, listar_sem_data, ler_linhas_doclist
        try:
            if self._linhas is None:
                self._linhas = ler_linhas_doclist(self.path_doclist, self.sheet)
            incluir = self.var_emitidos.get()
            itens = analisar_periodo(self._linhas, inicio=inicio, fim=fim, hoje=self.hoje,
                                     incluir_emitidos=incluir)
            sem_data = listar_sem_data(self._linhas, incluir_emitidos=incluir)
            erro = None
        except Exception as e:  # noqa: BLE001
            itens, sem_data, erro = [], [], str(e)
        self.after(0, self._concluir, itens, sem_data, erro)

    def _concluir(self, itens, sem_data, erro):
        self.btn_filtrar.configure(state="normal", text="Analisar")
        if erro:
            messagebox.showerror("Erro", f"Falha ao analisar:\n{erro}", parent=self)
            self.lbl_status.configure(text="Erro na análise.")
            self.btn_exportar.configure(state="disabled")
            return
        self._itens, self._sem_data = itens, sem_data
        self._repovoar()
        self.btn_exportar.configure(state="normal" if itens else "disabled")

    def _repovoar(self):
        self.tree.delete(*self.tree.get_children())
        if not self._itens:
            self.lbl_status.configure(text="Nenhum documento previsto nesse período.")
            return
        from ...doclist_backend import agrupar_por, resumo
        chave = _AGRUPADORES[self.var_agrup.get()]
        self.tree.heading("#0", text=f"{self.var_agrup.get()} / Documento")
        for rotulo, itens in agrupar_por(self._itens, chave).items():
            no = self.tree.insert("", "end", text=f"📂 {rotulo} ({len(itens)})", open=True)
            for it in itens:
                tags = ("emitido",) if it.emitido else (("vencido",) if it.dias < 0 else ())
                self.tree.insert(no, "end", text=f"📄 {it.cod_itaipu}", tags=tags,
                                 values=(it.data_alvo.strftime("%d/%m/%Y"), it.origem, it.dias,
                                         it.situacao, it.descricao, it.cod_cmi,
                                         it.status_consolidado, it.responsavel))
        r = resumo(self._itens)
        extra = f" · {len(self._sem_data)} documento(s) sem data de planejamento" if self._sem_data else ""
        self.lbl_status.configure(
            text=f"{r['total']} documento(s): {r['vencidos']} vencido(s), {r['a_emitir']} a emitir, "
                 f"{r['reprogramados']} com data reprogramada{extra}.")

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
        if not self._itens:
            return
        from ...doclist_backend import exportar_analise_periodo, resumo
        from ..components import pedir_salvar
        d1 = (self.entry_ini.get().strip() or "inicio").replace("/", ".")
        d2 = (self.entry_fim.get().strip() or "fim").replace("/", ".")
        nome = f"DocList_Previstos_{d1}_ate_{d2}.xlsx"
        ctx = getattr(getattr(self, "master", None), "ctx", None)
        caminho = pedir_salvar(getattr(ctx, "config", None), "saida", nome,
                               titulo="Salvar Análise por Período", parent=self)
        if not caminho:
            return
        titulo = self._rotulo_janela or f"{self.entry_ini.get().strip() or '—'} a {self.entry_fim.get().strip() or '—'}"
        ok, msg = exportar_analise_periodo(self._itens, resumo(self._itens), caminho,
                                           titulo_janela=titulo, hoje=self.hoje,
                                           sem_data=self._sem_data)
        (messagebox.showinfo if ok else messagebox.showerror)(
            "Exportação" if ok else "Erro", msg, parent=self)
