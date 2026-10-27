"""Verificação de Status de Documentos.

3 abas (Via Arquivo Excel · Via Lista Rápida · Todos Aconex), cada uma
definindo um CONJUNTO de documentos. As duas ações no rodapé operam sobre o
conjunto da aba ativa:

  • Status Atual  → status real de cada documento (Excel legado + gráfico).
  • Delta do Período → como cada documento mudou entre duas datas (agrupado por
    metadado). Assim, quem usava o Delta não precisa mais forçar arquivos avulsos
    dentro do mapeamento: escolhe a aba, informa os documentos e roda o Delta.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QFormLayout, QLineEdit, QPlainTextEdit, QWidget

from .. import dialogos
from ..components import Abas, Card, FileSelector, RunBar, Seletor, botao, linha, rotulo
from ..ponte import na_ui_e_esperar
from .base import BaseView

_NENHUM = "- NENHUM -"
_CARREGUE = "Carregue as colunas"
_TAB_EXCEL = "Via Arquivo Excel"
_TAB_LISTA = "Via Lista Rápida"
_TAB_TODOS = "Todos Aconex"


class StatusDocsView(BaseView):
    titulo_view = "Status Documentos"
    subtitulo_view = "Status atual e Delta por período dos documentos da aba escolhida"

    def montar(self, body):
        card = Card("Base Aconex (obrigatória para todas as abas)")
        self.sel = card.add(FileSelector("Base Aconex", self.ctx.config, "aconex", aba_padrao="Documentos"))
        body.addWidget(card)

        abas_card = Card()
        self.tabs = Abas()
        self._montar_excel(self.tabs.add(_TAB_EXCEL, "file-spreadsheet"))
        self._montar_lista(self.tabs.add(_TAB_LISTA, "list-checks"))
        self._montar_todos(self.tabs.add(_TAB_TODOS, "download"))
        abas_card.add(self.tabs)
        body.addWidget(abas_card)

        self._montar_acoes(body)

    # ---------------------------------------------------------- Aba 1: Excel
    def _montar_excel(self, aba):
        lay = aba.layout()
        self.sel_lista = FileSelector("Lista de Documentos", self.ctx.config, "status_list")
        lay.addWidget(self.sel_lista)

        self.header_row = QLineEdit("1")
        self.header_row.setValidator(QIntValidator(1, 100000))
        self.header_row.setFixedWidth(70)
        lay.addWidget(linha(rotulo("Linha do cabeçalho:"), self.header_row,
                            botao("Carregar Colunas", icone="table", ao_clicar=self._carregar_colunas)))

        self.col_itaipu = Seletor([_CARREGUE])
        self.col_cmi = Seletor([_CARREGUE])
        for c in (self.col_itaipu, self.col_cmi):
            c.setMinimumWidth(240)
        form = QWidget()
        fl = QFormLayout(form)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addRow("Coluna Cód. Itaipu:", self.col_itaipu)
        fl.addRow("Coluna Cód. CMI:", self.col_cmi)
        lay.addWidget(linha(form))

    def _linha_cabecalho(self) -> int:
        try:
            return max(int(self.header_row.text() or "1") - 1, 0)
        except ValueError:
            return 0

    def _carregar_colunas(self):
        if not self.sel_lista.path:
            dialogos.aviso("Aviso", "Selecione o arquivo da lista primeiro.", self)
            return
        try:
            import pandas as pd
            row_idx = self._linha_cabecalho()
            df = pd.read_excel(self.sel_lista.path, sheet_name=self.sel_lista.sheet, header=row_idx, nrows=0)
            cols = [str(c) for c in df.columns if "Unnamed" not in str(c)]
            opcoes = [_NENHUM] + cols
            self.col_itaipu.definir_itens(opcoes, cols[0] if cols else _NENHUM)
            self.col_cmi.definir_itens(opcoes, cols[1] if len(cols) > 1 else _NENHUM)
            self.log.log(f"Colunas carregadas da linha {row_idx + 1}: {len(cols)} colunas.")
        except Exception as e:  # noqa: BLE001
            self.log.log(f"Erro ao ler colunas: {e}")
            dialogos.erro("Erro", f"Erro ao ler a linha do cabeçalho:\n{e}", self)

    def _pares_do_excel(self, estado):
        import pandas as pd
        df = pd.read_excel(self.sel_lista.path, sheet_name=self.sel_lista.sheet,
                           header=estado["linha"], dtype=str).fillna("")
        col_it, col_cmi = estado["col_itaipu"], estado["col_cmi"]
        vazio = pd.Series([""] * len(df))
        serie_it = df[col_it] if col_it not in (_NENHUM, _CARREGUE) and col_it in df.columns else vazio
        serie_cmi = df[col_cmi] if col_cmi not in (_NENHUM, _CARREGUE) and col_cmi in df.columns else vazio
        return [(str(a).strip(), str(b).strip()) for a, b in zip(serie_it, serie_cmi)
                if str(a).strip() or str(b).strip()]

    # ---------------------------------------------------------- Aba 2: Lista
    def _montar_lista(self, aba):
        lay = aba.layout()
        self.tipo_lista = Seletor(["Código Itaipu", "Código CMI"])
        lay.addWidget(linha(rotulo("Tipo de código:"), self.tipo_lista))
        lay.addWidget(rotulo("Cole os códigos (um por linha):", "suave"))
        self.txt_lista = QPlainTextEdit()
        self.txt_lista.setObjectName("caixa_texto")
        self.txt_lista.setFixedHeight(120)
        lay.addWidget(self.txt_lista)

    @staticmethod
    def _pares_da_lista(estado):
        codigos = [c.strip() for c in estado["lista"].splitlines() if c.strip()]
        if estado["tipo_lista"] == "Código Itaipu":
            return [(c, "") for c in codigos]
        return [("", c) for c in codigos]

    # ---------------------------------------------------------- Aba 3: Todos
    def _montar_todos(self, aba):
        aba.layout().addWidget(rotulo(
            "Usa automaticamente TODOS os documentos vigentes (Current) da base Aconex carregada, tanto "
            "para o Status Atual quanto para o Delta do período.", "suave", quebra=True))

    @staticmethod
    def _pares_de_todos(base):
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
        area = Card("Ações (sobre os documentos da aba ativa)")
        area.add(RunBar("Gerar Status Atual", self._tarefa_status, self.log))
        area.add(linha(botao("Analisar Mudanças por Período", icone="history", ao_clicar=self._abrir_delta),
                       rotulo("Abre a árvore de mudanças (por classificação) dos documentos da aba.",
                              "legenda", quebra=True), esticar=1))
        body.addWidget(area)

    # ---------------------------------------------------------- comuns
    def _estado(self) -> dict:
        """Foto do que está na tela - lida na thread da interface, para a tarefa
        (que roda em outra thread) não tocar em widget."""
        return {"aba": self.tabs.get(), "linha": self._linha_cabecalho(),
                "col_itaipu": self.col_itaipu.get(), "col_cmi": self.col_cmi.get(),
                "tipo_lista": self.tipo_lista.get(), "lista": self.txt_lista.toPlainText()}

    def _carregar_base(self, run):
        from ...common import carregar_base_aconex
        if not self.sel.path:
            self.log.log("Selecione a base Aconex no topo.")
            return None
        self.log.log("Lendo base Aconex...")
        run.set_progress(0.3)
        return carregar_base_aconex(self.sel.path, self.sel.sheet)

    def _coletar(self, run):
        """(base, pares, is_todos) conforme a aba ativa; None se faltar entrada."""
        estado = na_ui_e_esperar(self._estado)
        base = self._carregar_base(run)
        if base is None:
            return None
        if estado["aba"] == _TAB_EXCEL:
            if not self.sel_lista.path:
                self.log.log("Selecione o arquivo da lista na aba 'Via Arquivo Excel'.")
                return None
            return base, self._pares_do_excel(estado), False
        if estado["aba"] == _TAB_LISTA:
            pares = self._pares_da_lista(estado)
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
        from ...status_backend import analisar_status_pares, exportar_status_documentos
        if not pares:
            self.log.log("Nenhum código para analisar.")
            return
        self.log.log(f"Analisando status de {len(pares)} documentos...")
        run.set_progress(0.6)
        linhas, contador, tem_modelos = analisar_status_pares(base, pares)
        for st, n in contador.most_common():
            self.log.log(f"  {st}: {n}")

        def _conta(estado):
            return sum(1 for d in linhas if estado in (d.get("_itaipu_status"), d.get("_cmi_status")))

        n_atualizados = _conta("atualizado")
        n_nao_confere = _conta("nao_confere")
        n_nao_localizado = _conta("nao_localizado")
        n_ambiguos = sum(1 for d in linhas if d.get("_ambiguo"))
        if n_atualizados:
            self.log.log(f"  {n_atualizados} com código atualizado no Aconex vs. a busca (texto azul).")
        if n_nao_confere:
            self.log.log(f"  {n_nao_confere} com código de OUTRO documento - corrigido; ver comentário na célula.")
        if n_nao_localizado:
            self.log.log(f"  {n_nao_localizado} com código não localizado no Aconex "
                         f"(possível documento não emitido) - ver comentário na célula.")
        if n_ambiguos:
            self.log.log(f"  {n_ambiguos} com código compartilhado por mais de um documento "
                         f"(texto laranja) - CONFIRA o comentário na célula.")
        run.set_progress(0.9)
        nome = f"Status_Docs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        saida = dialogos.pedir_salvar(self.ctx.config, "saida", nome)
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok, msg = exportar_status_documentos(linhas, contador, saida, tem_modelos=tem_modelos)
        self.log.log(msg)
        if ok:
            dialogos.info("Status", f"{len(linhas)} documentos analisados.")

    def _codigos_do_tab(self):
        """(codigos, is_todos) da aba ativa, SEM carregar a base; None se faltar entrada."""
        estado = self._estado()
        if estado["aba"] == _TAB_EXCEL:
            if not self.sel_lista.path:
                dialogos.aviso("Aviso", "Selecione o arquivo da lista na aba 'Via Arquivo Excel'.", self)
                return None
            try:
                pares = self._pares_do_excel(estado)
            except Exception as e:  # noqa: BLE001
                dialogos.erro("Erro", f"Erro ao ler a lista: {e}", self)
                return None
            codigos = [c for par in pares for c in par if c]
            if not codigos:
                dialogos.aviso("Aviso", "Nenhum código nas colunas escolhidas.", self)
                return None
            return codigos, False
        if estado["aba"] == _TAB_LISTA:
            codigos = [c for par in self._pares_da_lista(estado) for c in par if c]
            if not codigos:
                dialogos.aviso("Aviso", "Cole ao menos um código na aba 'Via Lista Rápida'.", self)
                return None
            return codigos, False
        return None, True  # Todos Aconex → base inteira

    def _abrir_delta(self):
        from ...status_backend import METADADOS_AGRUPAVEIS
        if not self.sel.path:
            dialogos.aviso("Aviso", "Selecione a base Aconex no topo.", self)
            return
        res = self._codigos_do_tab()
        if res is None:
            return
        codigos, is_todos = res
        from .status_delta_dialog import StatusDeltaDialog
        self._delta = StatusDeltaDialog(self, config=self.ctx.config, path_aconex=self.sel.path,
                                        sheet_aconex=self.sel.sheet, codigos=codigos, is_todos=is_todos,
                                        metadados=METADADOS_AGRUPAVEIS)
        self._delta.show()
