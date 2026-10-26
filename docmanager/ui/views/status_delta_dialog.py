"""Janela de Análise de Mudanças por Período do Status Documentos.

Mesma ideia do Delta do Mapa (Efetiva/Bruta, ocultar aprovados, export Excel),
porém SEM a estruturação de níveis: a árvore é apenas **Classificação
(metadado) → Documento**. Opera sobre os documentos da aba ativa do Status (via
`codigos`) ou sobre toda a base vigente (`is_todos`). Fonte:
`status_backend.calcular_mudancas_base`.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QCheckBox

from .. import dialogos
from ..components import Seletor, botao, rotulo
from .arvore import ArvoreDialog, campo_data
from .delta_dialog import _SO_BRUTA, info_revisao

_APROVADOS = {"Aprovado", "Aprovado com Comentários", "Para Assinatura"}
_COLUNAS = [("Classificação / Documento", 300), ("Rev/Data (Antes)", 130), ("Aconex (Antes)", 145),
            ("Efetivo (Antes)", 145), ("", 34), ("Rev/Data (Depois)", 130), ("Aconex (Depois)", 145),
            ("Efetivo (Depois)", 145)]


class StatusDeltaDialog(ArvoreDialog):
    def __init__(self, parent, *, path_aconex, sheet_aconex, codigos, is_todos, metadados, config=None):
        super().__init__(parent, titulo="Análise de Mudanças por Período - Status Documentos",
                         colunas=_COLUNAS, config=config, largura=1120, altura=600)
        self.path_aconex, self.sheet_aconex = path_aconex, sheet_aconex
        self.codigos = codigos
        self.is_todos = is_todos
        self._base = None          # base Aconex carregada (lazy, cacheada)
        self.arvore = None

        hoje = datetime.now()
        self.entry_ini = campo_data((hoje - timedelta(days=30)).strftime("%d/%m/%Y"))
        self.entry_fim = campo_data(hoje.strftime("%d/%m/%Y"))
        self.opt_agrup = Seletor(metadados)
        self.opt_agrup.setMinimumWidth(180)
        self.opt_visao = Seletor(["Efetiva", "Bruta"])
        self.opt_visao.currentTextChanged.connect(lambda _v: self._repovoar())
        self.btn_filtrar = botao("Verificar Mudanças", variante="primario", icone="search",
                                 ao_clicar=self._executar)
        self.chk_ocultar = QCheckBox("Ocultar se já estava Aprovado")
        self.chk_ocultar.toggled.connect(lambda _v: self._repovoar())
        self.adicionar_na_barra(rotulo("Período:", "destaque"), self.entry_ini, rotulo("até", "suave"),
                                self.entry_fim, rotulo("Classificar por:", "destaque"), self.opt_agrup,
                                rotulo("Visão:", "destaque"), self.opt_visao, self.btn_filtrar,
                                self.chk_ocultar)
        self.barra_lay.addStretch(1)
        alvo = "toda a base vigente" if is_todos else f"{len(codigos or [])} documento(s) da aba"
        self.lbl_status.setText(f"Analisando {alvo}. Informe o período e clique em Verificar Mudanças.")
        self._aplicar_visao()

    # ------------------------------------------------------------ ações
    def _executar(self):
        dt_ini, dt_fim = self.entry_ini.text().strip(), self.entry_fim.text().strip()
        if not dt_ini or not dt_fim:
            dialogos.aviso("Aviso", "Preencha as duas datas.", self)
            return
        self.lbl_status.setText("Cruzando dados... aguarde.")
        agrup, visao = self.opt_agrup.get(), self.opt_visao.get()

        def trabalho():
            from ...common import carregar_base_aconex
            from ...status_backend import calcular_mudancas_base
            try:
                if self._base is None:
                    self._base = carregar_base_aconex(self.path_aconex, self.sheet_aconex)
                cods = None if self.is_todos else self.codigos
                return calcular_mudancas_base(self._base, dt_ini, dt_fim, coluna_agrupar=agrup,
                                              tipo_visao=visao, codigos=cods)
            except Exception as e:  # noqa: BLE001
                return False, str(e), 0

        self.rodar_em_thread(self.btn_filtrar, "Processando...", trabalho, self._concluir)

    def _concluir(self, resultado):
        ok, arvore, total = resultado
        if not ok:
            dialogos.erro("Erro", f"Falha: {arvore}", self)
            self.lbl_status.setText("Erro na análise.")
            self.btn_exportar.setEnabled(False)
            return
        self.arvore = arvore
        self._repovoar()
        self.lbl_status.setText(f"Análise concluída. {total} mudança(s) por {self.opt_agrup.get()}.")
        self.btn_exportar.setEnabled(bool(total))

    def _itens_do_grupo(self, grupo):
        """Achata os itens do grupo (o Delta da base usa o nível único '—')."""
        return [it for lst in self.arvore[grupo].values() for it in lst]

    def _aplicar_visao(self):
        bruta = self.opt_visao.get() == "Bruta"
        for c in _SO_BRUTA:
            self.tree.setColumnHidden(c, not bruta)

    def _visiveis(self, grupo):
        ocultar = self.chk_ocultar.isChecked()
        return [d for d in self._itens_do_grupo(grupo)
                if not (ocultar and str(d["real_antes"]).strip() in _APROVADOS)]

    def _repovoar(self):
        self.limpar()
        self._aplicar_visao()
        if not self.arvore:
            return
        self.tree.headerItem().setText(0, f"{self.opt_agrup.get()} / Documento")
        exibidos = 0
        for grupo in sorted(self.arvore.keys()):
            itens = self._visiveis(grupo)
            if not itens:
                continue
            no_g = self.grupo(f"{grupo} ({len(itens)})")
            for d in itens:
                exibidos += 1
                self.documento(no_g, d["doc"],
                               (info_revisao(d, "antes"), d["raw_antes"], d["real_antes"], "➜",
                                info_revisao(d, "depois"), d["raw_depois"], d["real_depois"]))
        if self.chk_ocultar.isChecked():
            self.lbl_status.setText(f"Exibindo {exibidos} documento(s) (filtro ativo).")

    def _exportar(self):
        if not self.arvore:
            return
        import pandas as pd

        from ...common import exportar_dataframe
        agrup = self.opt_agrup.get()
        linhas = [{
            agrup: grupo, "Documento": d["doc"], "Título": d["titulo"],
            "Status Aconex (Antes)": d["raw_antes"], "Status Efetivo (Antes)": d["real_antes"],
            "Status Aconex (Depois)": d["raw_depois"], "Status Efetivo (Depois)": d["real_depois"],
            "Rev (Antes)": d.get("rev_antes", "-"), "Data (Antes)": d.get("data_antes", "-"),
            "Rev (Depois)": d.get("rev_depois", "-"), "Data (Depois)": d.get("data_depois", "-"),
        } for grupo in sorted(self.arvore.keys()) for d in self._visiveis(grupo)]
        if not linhas:
            dialogos.info("Delta", "Nada a exportar.", self)
            return
        d1 = self.entry_ini.text().strip().replace("/", ".")
        d2 = self.entry_fim.text().strip().replace("/", ".")
        caminho = dialogos.pedir_salvar(self.config, "saida", f"Delta_Status_{d1}_ate_{d2}.xlsx", parent=self)
        if not caminho:
            return
        ok, msg = exportar_dataframe(pd.DataFrame(linhas), caminho, sheet_name="Delta")
        (dialogos.info if ok else dialogos.erro)("Exportação", msg, self)
