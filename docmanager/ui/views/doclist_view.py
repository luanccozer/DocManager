"""Módulo **Doc List Mapping** - follow-up semanal de uma lista de documentos.

Mesmo fluxo do Mapa dos Planos (base Aconex + planilha + Controle opcional),
com as regras próprias do módulo. Traz as duas análises por período, que se
complementam: **Analisar Período** olha para FRENTE (o que está previsto para
emitir, pelas datas de planejamento) e **Delta** olha para TRÁS (o que mudou de
status entre duas datas, pelo histórico do Aconex). **Gerar Painel HTML** faz o
painel da Unidade Geradora, no lugar do Power BI.
"""
from __future__ import annotations

import webbrowser
from datetime import datetime
from pathlib import Path

from .. import dialogos
from ..components import Card, FileSelector, RunBar, botao, linha, rotulo
from .base import BaseView
from .sobrescricao_dialog import decidir_sobrescricoes
from .mapa_view import ler_linha_cabecalho
from ..idioma import marcar, t


class DocListView(BaseView):
    titulo_view = marcar("Doc List Mapping")
    subtitulo_view = marcar("Follow-up da lista de documentos: status, agrupamento por escopo, "
                      "planejamento de emissão e análises por período")

    # Colunas que o Delta lê da planilha - mesmos nomes do Mapa dos Planos.
    _COLS_CFG = {"doc": "N° ITAIPU", "grupo": "GRUPO", "sistema": "SISTEMA",
                 "nivel": "NÍVEL", "titulo": "DESCRIÇÃO DO DOCUMENTO",
                 "predecessor": "PREDECESSOR"}

    def montar(self, body):
        cfg = self.ctx.config
        card = Card(t("Arquivos"))
        self.sel_aconex = card.add(FileSelector(t("Base Aconex"), cfg, "aconex", aba_padrao="Documentos"))
        self.sel_doclist = card.add(FileSelector(t("Doc List Mapping"), cfg, "doclist"))
        self.sel_ctrl = card.add(FileSelector(t("Controle de Documentos (opcional)"), cfg, "controle"))
        card.add(rotulo(t("Do Controle vêm DATA PREVISTA EMISSÃO e DATA REPROGRAMADA, quando vazias, "
                        "e a descrição dos documentos que o Aconex ainda não conhece. Uma data já "
                        "preenchida só é trocada se você aceitar: o app pergunta no meio da "
                        "atualização. FASE DE PROJETO é preenchida à mão."),
                        "legenda", quebra=True))
        body.addWidget(card)

        periodo = botao(t("Analisar Período (previstos para emitir)"), icone="calendar-range",
                        ao_clicar=self._abrir_periodo)
        delta = botao(t("Analisar Mudanças por Período (Delta)"), icone="history", ao_clicar=self._abrir_delta)
        body.addWidget(linha(periodo, delta))

        self.run = RunBar(t("Iniciar Atualização"), self._tarefa, self.log)
        body.addWidget(self.run)

        painel = Card(t("Painel HTML"))
        painel.add(rotulo(t("O painel da Unidade Geradora, no lugar do Power BI: lê a planilha e a base "
                            "Aconex escolhidas acima, sem alterar nada, e abre no navegador. É um arquivo só: "
                            "salve no Box para reabrir depois ou envie a quem não tem o DocManager. "
                            "Atualize a planilha antes, para as datas de planejamento estarem em dia."),
                          "legenda", quebra=True))
        body.addWidget(painel)
        self.run_painel = RunBar(t("Gerar Painel HTML"), self._tarefa_painel, self.log)
        body.addWidget(self.run_painel)

    # ------------------------------------------------------------------
    def _abrir_periodo(self):
        """O que está previsto para emitir (olha para FRENTE, pelo planejamento)."""
        if not self.sel_doclist.path:
            dialogos.aviso(t("Aviso"), t("Selecione a planilha do Doc List Mapping primeiro."), self)
            return
        from .periodo_dialog import PeriodoDialog
        self._periodo = PeriodoDialog(self, config=self.ctx.config, path_doclist=self.sel_doclist.path,
                                      sheet=self.sel_doclist.sheet)
        self._periodo.show()

    def _abrir_delta(self):
        """O que ACONTECEU entre duas datas (olha para trás, pelo Aconex).

        Mesmo motor do Mapa dos Planos: as colunas de que ele precisa têm os
        mesmos nomes neste layout. `estrito=False` fixo - a regra das planilhas
        VIP é de níveis 3/4, que não existem aqui."""
        if not self.sel_doclist.path:
            dialogos.aviso(t("Aviso"), t("Selecione a planilha do Doc List Mapping primeiro."), self)
            return
        if not self.sel_aconex.path:
            dialogos.aviso(t("Aviso"), t("Selecione a Base Aconex para prosseguir."), self)
            return
        from ...doclist_backend import DocListSheet
        from .delta_dialog import DeltaDialog
        cfg = dict(self._COLS_CFG)
        try:
            cfg["header_row"] = ler_linha_cabecalho(self.sel_doclist.path, self.sel_doclist.sheet,
                                                    DocListSheet)
        except Exception as e:  # noqa: BLE001
            dialogos.erro(t("Erro"), t('Não foi possível ler o cabeçalho do Doc List:\n{e}', e=e), self)
            return
        self._delta = DeltaDialog(self, config=self.ctx.config, path_map=self.sel_doclist.path,
                                  sheet_map=self.sel_doclist.sheet, path_hist=self.sel_aconex.path,
                                  sheet_hist=self.sel_aconex.sheet, cols_config=cfg, estrito=False,
                                  titulo=t("Doc List Mapping - Mudanças por Período (Delta)"))
        self._delta.show()

    def _tarefa_painel(self, run: RunBar):
        """Painel HTML da Unidade Geradora (no lugar do Power BI). Só lê."""
        if not self.sel_aconex.path or not self.sel_doclist.path:
            self.log.log("Selecione a base Aconex e a planilha do Doc List Mapping.")
            return
        saida = dialogos.pedir_salvar(self.ctx.config, "painel_ug", f"Painel_UG_{datetime.now():%d%m%y}.html",
                                      filtro="Página HTML (*.html)")
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        from ...doclist_backend import gerar_painel_ug
        r = gerar_painel_ug(self.sel_aconex.path, self.sel_doclist.path, saida,
                            sheet_aconex=self.sel_aconex.sheet, sheet_doclist=self.sel_doclist.sheet,
                            log_cb=self.log.log, progress_cb=run.set_progress)
        self.log.log(r.mensagem)
        if r.ok:
            webbrowser.open(Path(saida).as_uri())
        else:
            dialogos.aviso(t("Painel HTML"), r.mensagem)

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
            retry_cb=lambda m: dialogos.tentar_de_novo(t("Salvar"), m),
            decidir_cb=lambda pendentes: decidir_sobrescricoes(pendentes, self))
        self.log.log(r.mensagem)
        if r.ok:
            dialogos.info(t("Doc List Mapping"), r.mensagem)
