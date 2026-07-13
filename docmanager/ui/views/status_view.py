"""Verificação de Status de Documentos.

3 abas do app antigo (Via Arquivo Excel · Via Lista Rápida · Todos Aconex), cada
uma definindo um CONJUNTO de documentos. As duas ações no rodapé operam sobre o
conjunto da aba ativa:

  • Status Atual  → status real de cada documento (Excel legado + gráfico).
  • Delta do Período → como cada documento mudou entre duas datas (agrupado por
    metadado). Assim, quem usava o Delta não precisa mais forçar arquivos avulsos
    dentro do mapeamento: escolhe a aba, informa os documentos e roda o Delta.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, FileSelector, LogConsole, RunBar
from .base import BaseView

_NENHUM = "- NENHUM -"
_TAB_EXCEL = "📄 Via Arquivo Excel"
_TAB_LISTA = "📋 Via Lista Rápida"
_TAB_TODOS = "☁️ Todos Aconex"


def _flatten(arvore) -> list[dict]:
    linhas = []
    for grupo, niveis in arvore.items():
        for _, itens in niveis.items():
            for it in itens:
                linhas.append({
                    "Classificação": grupo, "Documento": it["doc"], "Título": it["titulo"],
                    "Status Antes": it["real_antes"], "Status Depois": it["real_depois"],
                    "Rev Antes": it["rev_antes"], "Data Antes": it["data_antes"],
                    "Rev Depois": it["rev_depois"], "Data Depois": it["data_depois"],
                })
    return linhas


class StatusDocsView(BaseView):
    titulo_view = "Status Documentos"
    subtitulo_view = "Status atual e Delta por período dos documentos da aba escolhida"

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(body, "Base Aconex (obrigatória para todas as abas)")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.sel = card.add(FileSelector(card, "Base Aconex", cfg, "aconex", aba_padrao="Documentos"))

        self.tabs = ctk.CTkTabview(body, fg_color=t.CARD, segmented_button_selected_color=t.ACENTO,
                                   segmented_button_selected_hover_color=t.ACENTO_HOVER)
        self.tabs.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._montar_excel(self.tabs.add(_TAB_EXCEL))
        self._montar_lista(self.tabs.add(_TAB_LISTA))
        self._montar_todos(self.tabs.add(_TAB_TODOS))

        self._montar_acoes(body)

        self.log = LogConsole(body, height=180)
        self.log.grid(row=3, column=0, sticky="nsew", pady=(6, 0))
        self._ultimo_delta = None

    # ---------------------------------------------------------- Aba 1: Excel
    def _montar_excel(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        self.sel_lista = FileSelector(aba, "Lista de Documentos", self.ctx.config, "status_list")
        self.sel_lista.grid(row=0, column=0, sticky="ew", padx=6, pady=(8, 2))

        cfg_row = ctk.CTkFrame(aba, fg_color="transparent")
        cfg_row.grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ctk.CTkLabel(cfg_row, text="Linha do cabeçalho:", font=t.corpo(12), text_color=t.TEXTO).pack(side="left", padx=(0, 6))
        self.header_row = ctk.CTkEntry(cfg_row, width=50, font=t.corpo(12))
        self.header_row.insert(0, "1")
        self.header_row.pack(side="left")
        ctk.CTkButton(cfg_row, text="Carregar Colunas", width=140, font=t.corpo(12),
                      fg_color="#E59400", hover_color="#B87700",
                      command=self._carregar_colunas).pack(side="left", padx=12)

        map_row = ctk.CTkFrame(aba, fg_color="transparent")
        map_row.grid(row=2, column=0, sticky="w", padx=6, pady=4)
        ctk.CTkLabel(map_row, text="Coluna Cód. Itaipu:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        self.col_itaipu = ctk.CTkOptionMenu(map_row, values=["Carregue as colunas"], width=200, font=t.corpo(12),
                                            fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.col_itaipu.grid(row=0, column=1, sticky="w", pady=3)
        ctk.CTkLabel(map_row, text="Coluna Cód. CMI:", font=t.corpo(12), text_color=t.TEXTO).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        self.col_cmi = ctk.CTkOptionMenu(map_row, values=["Carregue as colunas"], width=200, font=t.corpo(12),
                                         fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.col_cmi.grid(row=1, column=1, sticky="w", pady=3)

    def _carregar_colunas(self):
        if not self.sel_lista.path:
            messagebox.showwarning("Aviso", "Selecione o arquivo da lista primeiro.")
            return
        try:
            import pandas as pd
            row_idx = max(int(self.header_row.get()) - 1, 0)
            df = pd.read_excel(self.sel_lista.path, sheet_name=self.sel_lista.sheet, header=row_idx, nrows=0)
            cols = [str(c) for c in df.columns if "Unnamed" not in str(c)]
            opcoes = [_NENHUM] + cols
            self.col_itaipu.configure(values=opcoes)
            self.col_cmi.configure(values=opcoes)
            self.col_itaipu.set(cols[0] if cols else _NENHUM)
            self.col_cmi.set(cols[1] if len(cols) > 1 else _NENHUM)
            self.log.log(f"Colunas carregadas da linha {row_idx + 1}: {len(cols)} colunas.")
        except Exception as e:  # noqa: BLE001
            self.log.log(f"Erro ao ler colunas: {e}")
            messagebox.showerror("Erro", f"Erro ao ler a linha do cabeçalho:\n{e}")

    def _pares_do_excel(self):
        import pandas as pd
        row_idx = max(int(self.header_row.get()) - 1, 0)
        df = pd.read_excel(self.sel_lista.path, sheet_name=self.sel_lista.sheet, header=row_idx, dtype=str).fillna("")
        col_it, col_cmi = self.col_itaipu.get(), self.col_cmi.get()
        vazio = pd.Series([""] * len(df))
        serie_it = df[col_it] if col_it not in (_NENHUM, "Carregue as colunas") and col_it in df.columns else vazio
        serie_cmi = df[col_cmi] if col_cmi not in (_NENHUM, "Carregue as colunas") and col_cmi in df.columns else vazio
        return [(str(a).strip(), str(b).strip()) for a, b in zip(serie_it, serie_cmi) if str(a).strip() or str(b).strip()]

    # ---------------------------------------------------------- Aba 2: Lista
    def _montar_lista(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(aba, fg_color="transparent")
        top.grid(row=0, column=0, sticky="w", padx=6, pady=(8, 4))
        ctk.CTkLabel(top, text="Tipo de código:", font=t.corpo(12), text_color=t.TEXTO).pack(side="left", padx=(0, 8))
        self.tipo_lista = ctk.CTkOptionMenu(top, values=["Código Itaipu", "Código CMI"], width=150, font=t.corpo(12),
                                            fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.tipo_lista.pack(side="left")
        ctk.CTkLabel(aba, text="Cole os códigos (um por linha):", font=t.corpo(12), text_color=t.TEXTO_FRACO).grid(
            row=1, column=0, sticky="w", padx=6, pady=(2, 2))
        self.txt_lista = ctk.CTkTextbox(aba, height=110, font=t.mono(11), fg_color="#0B1119")
        self.txt_lista.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))

    def _pares_da_lista(self):
        codigos = [c.strip() for c in self.txt_lista.get("1.0", "end").splitlines() if c.strip()]
        if self.tipo_lista.get() == "Código Itaipu":
            return [(c, "") for c in codigos]
        return [("", c) for c in codigos]

    # ---------------------------------------------------------- Aba 3: Todos
    def _montar_todos(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(aba, text="Usa automaticamente TODOS os documentos vigentes (Current) da base Aconex "
                     "carregada — tanto para o Status Atual quanto para o Delta do período.",
                     font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=680).grid(
            row=0, column=0, sticky="w", padx=6, pady=16)

    def _pares_de_todos(self, base):
        cur = base[base["Current"].astype(str).str.lower() == "true"]
        col_it = "No. do Documento" if "No. do Documento" in cur.columns else None
        col_cm = "Controle do Emissor" if "Controle do Emissor" in cur.columns else None
        lista_it = cur[col_it].tolist() if col_it else [""] * len(cur)
        lista_cm = cur[col_cm].tolist() if col_cm else [""] * len(cur)
        vistos, pares = set(), []
        for a, b in zip(lista_it, lista_cm):
            a, b = str(a).strip(), str(b).strip()
            if (a or b) and (a, b) not in vistos:
                vistos.add((a, b))
                pares.append((a, b))
        return pares

    # ---------------------------------------------------------- Ações (rodapé)
    def _montar_acoes(self, body):
        from ...core.snapshots import METADADOS_AGRUPAVEIS
        area = Card(body, "Ações (sobre os documentos da aba ativa)")
        area.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        RunBar(area, "Gerar Status Atual", self._tarefa_status, None).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(2, 8))

        hoje = datetime.now()
        linha = ctk.CTkFrame(area, fg_color="transparent")
        linha.grid(row=2, column=0, sticky="w", padx=16, pady=(2, 2))
        ctk.CTkLabel(linha, text="Delta —  De:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=0, padx=(0, 4))
        self.dt_ini = ctk.CTkEntry(linha, width=95, font=t.corpo(12))
        self.dt_ini.insert(0, (hoje - timedelta(days=30)).strftime("%d/%m/%Y"))
        self.dt_ini.grid(row=0, column=1)
        ctk.CTkLabel(linha, text="Até:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=2, padx=(10, 4))
        self.dt_fim = ctk.CTkEntry(linha, width=95, font=t.corpo(12))
        self.dt_fim.insert(0, hoje.strftime("%d/%m/%Y"))
        self.dt_fim.grid(row=0, column=3)
        ctk.CTkLabel(linha, text="Agrupar:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=4, padx=(12, 4))
        self.agrup = ctk.CTkOptionMenu(linha, values=METADADOS_AGRUPAVEIS, width=175, font=t.corpo(12),
                                       fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.agrup.grid(row=0, column=5)
        ctk.CTkLabel(linha, text="Visão:", font=t.corpo(12), text_color=t.TEXTO).grid(row=0, column=6, padx=(12, 4))
        self.visao = ctk.CTkOptionMenu(linha, values=["Efetiva", "Bruta"], width=95, font=t.corpo(12),
                                       fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.visao.grid(row=0, column=7)
        RunBar(area, "Analisar Delta do Período", self._tarefa_delta, None).grid(
            row=3, column=0, sticky="ew", padx=16, pady=(2, 10))

    # ---------------------------------------------------------- comuns
    def _carregar_base(self, run):
        from ...services.excel_io import carregar_base_aconex
        if not self.sel.path:
            self.log.log("Selecione a base Aconex no topo.")
            return None
        self.log.log("Lendo base Aconex...")
        run.set_progress(0.3)
        return carregar_base_aconex(self.sel.path, self.sel.sheet)

    def _coletar(self, run):
        """(base, pares, is_todos) conforme a aba ativa; None se faltar entrada."""
        base = self._carregar_base(run)
        if base is None:
            return None
        aba = self.tabs.get()
        if aba == _TAB_EXCEL:
            if not self.sel_lista.path:
                self.log.log("Selecione o arquivo da lista na aba 'Via Arquivo Excel'.")
                return None
            return base, self._pares_do_excel(), False
        if aba == _TAB_LISTA:
            pares = self._pares_da_lista()
            if not pares:
                self.log.log("Cole ao menos um código na aba 'Via Lista Rápida'.")
                return None
            return base, pares, False
        return base, self._pares_de_todos(base), True

    def _tarefa_status(self, run: RunBar):
        col = self._coletar(run)
        if col is None:
            return
        base, pares, _ = col
        from ...core.reports.status_docs import analisar_status_pares
        from ...services.excel_io import exportar_status_documentos
        if not pares:
            self.log.log("Nenhum código para analisar.")
            return
        self.log.log(f"Analisando status de {len(pares)} documentos...")
        run.set_progress(0.6)
        linhas, contador, tem_modelos = analisar_status_pares(base, pares)
        for st, n in contador.most_common():
            self.log.log(f"  {st}: {n}")
        run.set_progress(0.9)
        nome = f"Status_Docs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        saida = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome, filetypes=[("Excel", "*.xlsx")])
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok, msg = exportar_status_documentos(linhas, contador, saida, tem_modelos=tem_modelos)
        self.log.log(msg)
        if ok:
            self.after(0, lambda: messagebox.showinfo("Status", f"{len(linhas)} documentos analisados."))

    def _tarefa_delta(self, run: RunBar):
        col = self._coletar(run)
        if col is None:
            return
        base, pares, is_todos = col
        from ...core.snapshots import calcular_mudancas_base
        codigos = None
        if not is_todos:
            codigos = [c for par in pares for c in par if c]
            if not codigos:
                self.log.log("Nenhum código para o Delta.")
                return
        alvo = "toda a base vigente" if is_todos else f"{len(codigos)} códigos"
        self.log.log(f"Delta {self.dt_ini.get()} → {self.dt_fim.get()} ({alvo}) por {self.agrup.get()} ({self.visao.get()})...")
        run.set_progress(0.6)
        ok, arvore, total = calcular_mudancas_base(
            base, self.dt_ini.get(), self.dt_fim.get(),
            coluna_agrupar=self.agrup.get(), tipo_visao=self.visao.get(), codigos=codigos)
        run.set_progress(0.95)
        if not ok:
            self.log.log(f"ERRO: {arvore}")
            return
        self.log.log(f"\n{total} mudanças:")
        for grupo, niveis in sorted(arvore.items()):
            self.log.log(f"  ▸ {grupo}: {sum(len(v) for v in niveis.values())}")
        self._ultimo_delta = _flatten(arvore)
        if self._ultimo_delta and messagebox.askyesno("Delta", f"{total} mudanças. Exportar?"):
            import pandas as pd
            from ...services.excel_io import exportar_dataframe
            saida = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                 initialfile=f"Delta_{self.agrup.get()}.xlsx", filetypes=[("Excel", "*.xlsx")])
            if saida:
                _, msg = exportar_dataframe(pd.DataFrame(self._ultimo_delta), saida, sheet_name="Delta")
                self.log.log(msg)
