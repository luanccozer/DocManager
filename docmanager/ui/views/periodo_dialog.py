"""Análise por Período do Doc List Mapping - "o que está previsto para emitir".

Lê a planilha do módulo e lista os documentos cuja **DATA-ALVO EMISSÃO**
(REPROGRAMADA quando existe, senão PREVISTA) cai na janela escolhida. Atalhos
prontos (vencidos, próximos 7/30/90 dias, mês que vem) ou intervalo manual;
árvore agrupada por mês / grupo / sistema / fase; exportação para Excel com uma
aba extra dos documentos ainda **sem planejamento**.
"""
from __future__ import annotations

from datetime import date, datetime

from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout

from .. import dialogos
from ..components import Seletor, botao, rotulo
from .arvore import ArvoreDialog, campo_data
from ..idioma import marcar, t

# Os rótulos de `core/doclist_periodo.janelas_padrao`, marcados para a tradução:
# o botão mostra `t()` e a chave continua o rótulo em português.
_ATALHOS_NA_TELA = (marcar("Vencidos (não emitidos)"), marcar("Próximos 7 dias"), marcar("Próximos 30 dias"),
                    marcar("Próximos 90 dias"), marcar("Restante deste mês"), marcar("Mês que vem"),
                    marcar("Este ano"))
_AGRUPADORES = {marcar("Mês"): "mes", marcar("Grupo"): "grupo", marcar("Sistema"): "sistema",
                marcar("Fase de Projeto"): "fase_projeto"}
_COLUNAS = [(marcar("Agrupamento / Documento"), 300), (marcar("Data-Alvo"), 95), (marcar("Origem"), 100), (marcar("Dias"), 60),
            (marcar("Situação"), 95), (marcar("Descrição"), 330), (marcar("Nº CMI"), 170), (marcar("Consolidado"), 150), (marcar("Responsible"), 110)]


class PeriodoDialog(ArvoreDialog):
    def __init__(self, parent, *, path_doclist, sheet=None, hoje: date | None = None, config=None):
        super().__init__(parent, titulo=t("Doc List Mapping - Documentos previstos por período"),
                         colunas=_COLUNAS, config=config)
        self.path_doclist, self.sheet = path_doclist, sheet
        self.hoje = hoje or date.today()
        self._linhas = None          # cache da planilha
        self._itens: list = []
        self._sem_data: list = []
        self._rotulo_janela = ""

        from ...doclist_backend import janelas_padrao
        self._janelas = {j.rotulo: j for j in janelas_padrao(self.hoje)}

        # Linha de atalhos, acima da barra de filtros.
        atalhos = QFrame()
        atalhos.setObjectName("barra_ferramentas")
        al = QHBoxLayout(atalhos)
        al.setContentsMargins(12, 8, 12, 8)
        al.addWidget(rotulo(t("Atalhos:"), "destaque"))
        for r in self._janelas:
            al.addWidget(botao(t(r), ao_clicar=lambda r=r: self._usar_atalho(r)))
        al.addStretch(1)
        self.layout().insertWidget(0, atalhos)

        self.entry_ini = campo_data(dica=t("DD/MM/AAAA (vazio = sem limite)"), largura=210)
        self.entry_fim = campo_data(dica=t("DD/MM/AAAA (vazio = sem limite)"), largura=210)
        self.opt_agrup = Seletor(opcoes=[(t(k), v) for k, v in _AGRUPADORES.items()])
        self.opt_agrup.currentTextChanged.connect(lambda _v: self._repovoar())
        self.chk_emitidos = QCheckBox(t("Incluir já emitidos"))
        self.chk_emitidos.toggled.connect(lambda _v: self._executar())
        self.btn_filtrar = botao(t("Analisar"), variante="primario", icone="search", ao_clicar=self._executar)
        self.adicionar_na_barra(rotulo(t("De:"), "destaque"), self.entry_ini, rotulo(t("até"), "suave"),
                                self.entry_fim, rotulo(t("Agrupar:"), "destaque"), self.opt_agrup,
                                self.chk_emitidos, self.btn_filtrar)
        self.barra_lay.addStretch(1)
        self.lbl_status.setText(t("Escolha um atalho ou informe o intervalo."))
        self.legenda(t("●  em vermelho: data-alvo já vencida"))

    # ------------------------------------------------------------ ações
    def _usar_atalho(self, rotulo_janela: str):
        janela = self._janelas[rotulo_janela]
        for campo, valor in ((self.entry_ini, janela.inicio), (self.entry_fim, janela.fim)):
            campo.setText(valor.strftime("%d/%m/%Y") if valor is not None else "")
        self._rotulo_janela = rotulo_janela
        self._executar()

    @staticmethod
    def _ler_data(campo) -> date | None:
        texto = campo.text().strip()
        if not texto:
            return None
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
            try:
                return datetime.strptime(texto, fmt).date()
            except ValueError:
                continue
        raise ValueError(t("Data inválida: '{texto}'. Use DD/MM/AAAA.", texto=texto))

    def _executar(self):
        try:
            inicio, fim = self._ler_data(self.entry_ini), self._ler_data(self.entry_fim)
        except ValueError as e:
            dialogos.aviso(t("Aviso"), str(e), self)
            return
        if inicio and fim and inicio > fim:
            dialogos.aviso(t("Aviso"), t("A data inicial é posterior à final."), self)
            return
        self.lbl_status.setText(t("Lendo a planilha..."))
        incluir = self.chk_emitidos.isChecked()

        def trabalho():
            from ...doclist_backend import analisar_periodo, ler_linhas_doclist, listar_sem_data
            try:
                if self._linhas is None:
                    self._linhas = ler_linhas_doclist(self.path_doclist, self.sheet)
                itens = analisar_periodo(self._linhas, inicio=inicio, fim=fim, hoje=self.hoje,
                                         incluir_emitidos=incluir)
                return itens, listar_sem_data(self._linhas, incluir_emitidos=incluir), None
            except Exception as e:  # noqa: BLE001
                return [], [], str(e)

        self.rodar_em_thread(self.btn_filtrar, "Processando...", trabalho, self._concluir)

    def _concluir(self, resultado):
        itens, sem_data, erro = resultado
        if erro:
            dialogos.erro(t("Erro"), t('Falha ao analisar:\n{erro}', erro=erro), self)
            self.lbl_status.setText(t("Erro na análise."))
            self.btn_exportar.setEnabled(False)
            return
        self._itens, self._sem_data = itens, sem_data
        self._repovoar()
        self.btn_exportar.setEnabled(bool(itens))

    def _repovoar(self):
        self.limpar()
        if not self._itens:
            self.lbl_status.setText(t("Nenhum documento previsto nesse período."))
            return
        from ...doclist_backend import agrupar_por, resumo
        chave = self.opt_agrup.chave()
        self.tree.headerItem().setText(0, t("{agrupador} / Documento", agrupador=self.opt_agrup.get()))
        for rotulo_grupo, itens in agrupar_por(self._itens, chave).items():
            no = self.grupo(f"{rotulo_grupo} ({len(itens)})")
            for it in itens:
                estado = "apagado" if it.emitido else ("alerta" if it.dias < 0 else None)
                self.documento(no, it.cod_itaipu,
                               (it.data_alvo.strftime("%d/%m/%Y"), it.origem, it.dias, it.situacao,
                                it.descricao, it.cod_cmi, it.status_consolidado, it.responsavel), estado)
        r = resumo(self._itens)
        extra = (" · " + t("{n} documento(s) sem data de planejamento", n=len(self._sem_data))) if self._sem_data else ""
        self.lbl_status.setText(
            t('{total} documento(s): {vencidos} vencido(s), {a_emitir} a emitir, {reprogramados} com data reprogramada{extra}.', total=r['total'], vencidos=r['vencidos'], a_emitir=r['a_emitir'], reprogramados=r['reprogramados'], extra=extra))

    def _exportar(self):
        if not self._itens:
            return
        from ...doclist_backend import exportar_analise_periodo, resumo
        d1 = (self.entry_ini.text().strip() or "inicio").replace("/", ".")
        d2 = (self.entry_fim.text().strip() or "fim").replace("/", ".")
        caminho = dialogos.pedir_salvar(self.config, "saida", f"DocList_Previstos_{d1}_ate_{d2}.xlsx",
                                        titulo=t("Salvar Análise por Período"), parent=self)
        if not caminho:
            return
        titulo = self._rotulo_janela or (f"{self.entry_ini.text().strip() or '-'} a "
                                         f"{self.entry_fim.text().strip() or '-'}")
        ok, msg = exportar_analise_periodo(self._itens, resumo(self._itens), caminho, titulo_janela=titulo,
                                           hoje=self.hoje, sem_data=self._sem_data)
        (dialogos.info if ok else dialogos.erro)("Exportação" if ok else "Erro", msg, self)
