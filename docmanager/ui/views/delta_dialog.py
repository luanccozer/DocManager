"""Janela de Análise Delta ("Máquina do Tempo") - aberta de DENTRO do Mapa (e do Doc List).

Mesmo layout da `DeltaView` legada: árvore Grupo/Nível/Documento, visões
Efetiva/Bruta, filtro "ocultar aprovados" e exportação Excel. A lógica vem de
`core.snapshots.calcular_mudancas_periodo` (que respeita a regra estrita via
`estrito`).
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QCheckBox

from .. import dialogos
from ..components import Seletor, botao, rotulo
from .arvore import ArvoreDialog, campo_data

_STATUS_APROVADOS = ["Aprovado", "Aprovado com Comentários", "Para Assinatura"]
_COLUNAS = [("Grupo / Nível / Documento", 320), ("Rev/Data (Antes)", 130), ("Aconex (Antes)", 140),
            ("Efetivo (Antes)", 140), ("", 34), ("Rev/Data (Depois)", 130), ("Aconex (Depois)", 140),
            ("Efetivo (Depois)", 140)]
# Colunas só da visão Bruta: as de revisão e data.
_SO_BRUTA = (1, 5)


def info_revisao(d: dict, lado: str) -> str:
    rev = d.get(f"rev_{lado}", "-")
    return f"Rev {rev} ({d.get(f'data_{lado}', '-')})" if rev != "-" else "-"


class DeltaDialog(ArvoreDialog):
    def __init__(self, parent, *, path_map, sheet_map, path_hist, sheet_hist,
                 cols_config, estrito=False, titulo=None, config=None):
        # `titulo`: o diálogo serve ao Mapa dos Planos e ao Doc List Mapping -
        # a planilha de origem muda, o motor é o mesmo.
        super().__init__(parent, titulo=titulo or "Análise de Mudanças por Período (Delta)",
                         colunas=_COLUNAS, config=config)
        self.path_map, self.sheet_map = path_map, sheet_map
        self.path_hist, self.sheet_hist = path_hist, sheet_hist
        self.cols_config = cols_config
        self.estrito = estrito
        self.dados_cache = None

        self.entry_ini = campo_data()
        self.entry_fim = campo_data(datetime.now().strftime("%d/%m/%Y"))
        self.opt_agrup = Seletor(["Grupo", "Sistema"])
        self.opt_visao = Seletor(["Efetiva", "Bruta"])
        self.opt_visao.currentTextChanged.connect(lambda _v: self._repovoar())
        self.btn_filtrar = botao("Verificar Mudanças", variante="primario", icone="search",
                                 ao_clicar=self._executar)
        self.chk_ocultar = QCheckBox("Ocultar se já estava Aprovado")
        self.chk_ocultar.toggled.connect(lambda _v: self._repovoar())
        self.adicionar_na_barra(rotulo("Período:", "destaque"), self.entry_ini, rotulo("até", "suave"),
                                self.entry_fim, rotulo("Agrupar:", "destaque"), self.opt_agrup,
                                rotulo("Visão:", "destaque"), self.opt_visao, self.btn_filtrar,
                                self.chk_ocultar)
        self.barra_lay.addStretch(1)
        self.lbl_status.setText("Informe o período e clique em Verificar Mudanças.")
        self.legenda("●  em vermelho: documento presente em mais de um grupo")
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
            from ...mapa_backend import calcular_mudancas_periodo
            try:
                return calcular_mudancas_periodo(
                    self.path_map, self.sheet_map, self.path_hist, self.sheet_hist,
                    dt_ini, dt_fim, self.cols_config, agrupador_escolhido=agrup,
                    tipo_visao=visao, estrito=self.estrito)
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
        self.dados_cache = arvore
        self._repovoar()
        self.lbl_status.setText(f"Análise concluída. {total} documento(s) com mudança no período.")
        self.btn_exportar.setEnabled(bool(total))

    def _aplicar_visao(self):
        bruta = self.opt_visao.get() == "Bruta"
        for c in _SO_BRUTA:
            self.tree.setColumnHidden(c, not bruta)

    def _repovoar(self):
        self.limpar()
        self._aplicar_visao()
        if not self.dados_cache:
            return
        self.tree.headerItem().setText(0, f"{self.opt_agrup.get()} / Nível / Documento")
        ocultar = self.chk_ocultar.isChecked()
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
            no_g = self.grupo(f"{grupo} ({total_grupo})")
            for nivel in sorted(filtrado.keys()):
                docs = filtrado[nivel]
                no_n = self.grupo(f"L {nivel} ({len(docs)})", no_g)
                for d in docs:
                    exibidos += 1
                    self.documento(no_n, d["doc"],
                                   (info_revisao(d, "antes"), d["raw_antes"], d["real_antes"], "➜",
                                    info_revisao(d, "depois"), d["raw_depois"], d["real_depois"]),
                                   "alerta" if d.get("repetido_grupos") else None)
        if ocultar:
            self.lbl_status.setText(f"Exibindo {exibidos} documentos (filtro ativo).")

    def _exportar(self):
        if not self.dados_cache:
            return
        d1 = self.entry_ini.text().strip().replace("/", ".")
        d2 = self.entry_fim.text().strip().replace("/", ".")
        aba = str(self.sheet_map).replace(" ", "_")
        caminho = dialogos.pedir_salvar(self.config, "saida", f"Delta_{aba}_{d1}_ate_{d2}.xlsx",
                                        titulo="Salvar Exportação Delta", parent=self)
        if not caminho:
            return
        from ...mapa_backend import exportar_delta_arvore
        ok, msg = exportar_delta_arvore(self.dados_cache, caminho, agrupador=self.opt_agrup.get(),
                                        visao=self.opt_visao.get(),
                                        ocultar_aprovados=self.chk_ocultar.isChecked())
        (dialogos.info if ok else dialogos.erro)("Exportação concluída" if ok else "Erro", msg, self)
