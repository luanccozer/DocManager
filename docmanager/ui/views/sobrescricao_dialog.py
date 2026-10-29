"""Tela de sobrescrição: o Controle de Documentos trocaria datas já preenchidas (ADR 0001).

Primeiro uma pergunta com três saídas - aceitar todas, não sobrescrever, ver caso
a caso -; no caso a caso, a lista das incidências com uma caixa de marcar em
cada uma. Fechar a janela, em qualquer passo, é decidir depois: nada é trocado
nem anotado, e a pergunta volta na próxima atualização.

`decidir_sobrescricoes` é o `decidir_cb` que as telas do Doc List e do Mapa
passam para a atualização, que roda numa thread: a janela abre na thread da
interface pela `ponte`, como os outros diálogos do app.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHeaderView, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from ...controle_backend import COLUNA_PREVISTA, DecisaoSobrescricao, formatar_valor
from ..components import botao, linha, rodape, rotulo
from ..ponte import na_ui_e_esperar

_COLUNAS = [("Documento", 230), ("Descrição", 330), ("Coluna", 190), ("Na planilha", 105),
            ("No Controle", 105)]


def _resumo(pendentes) -> str:
    n = len(pendentes)
    previstas = sum(1 for p in pendentes if p.coluna == COLUNA_PREVISTA)
    partes = [f"{previstas} data{'s' if previstas != 1 else ''} prevista{'s' if previstas != 1 else ''}"]
    if n - previstas:
        partes.append(f"{n - previstas} data{'s' if n - previstas != 1 else ''} "
                      f"reprogramada{'s' if n - previstas != 1 else ''}")
    return (f"O Controle de Documentos trocaria {n} data{'s' if n != 1 else ''} já "
            f"preenchida{'s' if n != 1 else ''} na planilha ({' e '.join(partes)}).")


class EscolhaSobrescricao(QDialog):
    """O primeiro passo: aceitar todas, não sobrescrever ou ver caso a caso."""

    ACEITAR, RECUSAR, CASO_A_CASO = "aceitar", "recusar", "caso_a_caso"

    def __init__(self, pendentes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Datas que o Controle trocaria")
        self.escolha: str | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        self.lbl_resumo = rotulo(_resumo(pendentes), "destaque", quebra=True)
        self.lbl_aviso = rotulo(
            "A data prevista é a baseline: trocá-la faz o Baseline OTD medir contra a data "
            "nova, e o atraso contra a antiga deixa de aparecer. O que você não trocar fica "
            "como está e não é perguntado de novo enquanto o Controle mantiver a mesma data.",
            "suave", quebra=True)
        lay.addWidget(self.lbl_resumo)
        lay.addWidget(self.lbl_aviso)
        self.btn_caso = botao("Ver caso a caso", icone="list-checks",
                              ao_clicar=lambda: self._escolher(self.CASO_A_CASO))
        self.btn_recusar = botao("Não sobrescrever", ao_clicar=lambda: self._escolher(self.RECUSAR))
        self.btn_aceitar = botao("Aceitar todas", variante="primario", icone="check",
                                 ao_clicar=lambda: self._escolher(self.ACEITAR))
        lay.addWidget(rodape(self.btn_aceitar, self.btn_recusar, self.btn_caso))
        self.resize(560, 220)

    def _escolher(self, escolha: str) -> None:
        self.escolha = escolha
        self.accept()


class CasoACasoDialog(QDialog):
    """Lista das incidências: as marcadas são trocadas, as outras ficam e viram recusa."""

    def __init__(self, pendentes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Escolher quais datas trocar")
        self.resize(1040, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)
        lay.addWidget(rotulo("Marque as datas que devem ficar com a do Controle. As desmarcadas "
                             "ficam como estão e são anotadas como recusadas na aba "
                             "'Sobrescrições recusadas' da planilha.", "suave", quebra=True))

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(_COLUNAS))
        self.tree.setHeaderLabels([c for c, _ in _COLUNAS])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        for i, (_, largura) in enumerate(_COLUNAS):
            self.tree.setColumnWidth(i, largura)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for inc in pendentes:
            item = QTreeWidgetItem([inc.codigo, inc.descricao, inc.titulo_coluna,
                                    formatar_valor(inc.valor_planilha),
                                    formatar_valor(inc.data_controle)])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            self.tree.addTopLevelItem(item)
        self.tree.itemChanged.connect(lambda *_: self._atualizar_contagem())
        lay.addWidget(self.tree, 1)

        self.btn_marcar = botao("Marcar todas", ao_clicar=lambda: self._marcar_todas(True))
        self.btn_desmarcar = botao("Desmarcar todas", ao_clicar=lambda: self._marcar_todas(False))
        self.lbl_contagem = rotulo("", "suave")
        lay.addWidget(linha(self.btn_marcar, self.btn_desmarcar, self.lbl_contagem))
        self.btn_trocar = botao("Trocar as marcadas", variante="primario", icone="check",
                                ao_clicar=self.accept)
        self.btn_cancelar = botao("Decidir depois", ao_clicar=self.reject)
        lay.addWidget(rodape(self.btn_trocar, self.btn_cancelar))
        self._atualizar_contagem()

    def marcar(self, indice: int, marcado: bool) -> None:
        estado = Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked
        self.tree.topLevelItem(indice).setCheckState(0, estado)

    def _marcar_todas(self, marcado: bool) -> None:
        for i in range(self.tree.topLevelItemCount()):
            self.marcar(i, marcado)

    def _marcadas(self) -> frozenset[int]:
        return frozenset(i for i in range(self.tree.topLevelItemCount())
                         if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked)

    def _atualizar_contagem(self) -> None:
        self.lbl_contagem.setText(f"Marcadas: {len(self._marcadas())} de {self.tree.topLevelItemCount()}")

    def decisao(self) -> DecisaoSobrescricao:
        marcadas = self._marcadas()
        todas = frozenset(range(self.tree.topLevelItemCount()))
        return DecisaoSobrescricao(aceitas=marcadas, recusadas=todas - marcadas)


def decidir_sobrescricoes(pendentes, parent=None) -> DecisaoSobrescricao | None:
    """Pergunta o que fazer com as incidências. None = decidir depois (janela fechada).

    Cada janela é apagada (`deleteLater`) assim que responde: com dono, ela
    ficaria escondida na tela para sempre; sem dono, ficaria para o coletor de
    lixo, que pode rodar numa thread de trabalho - e o Qt derruba o processo
    quando um objeto dele morre fora da thread da interface.
    """
    def _responder(janela):
        try:
            return janela.exec() == QDialog.DialogCode.Accepted
        finally:
            janela.deleteLater()

    def _abrir():
        n = len(pendentes)
        escolha = EscolhaSobrescricao(pendentes, parent)
        if not _responder(escolha):
            return None
        if escolha.escolha == EscolhaSobrescricao.ACEITAR:
            return DecisaoSobrescricao.aceitar_todas(n)
        if escolha.escolha == EscolhaSobrescricao.RECUSAR:
            return DecisaoSobrescricao.recusar_todas(n)
        caso = CasoACasoDialog(pendentes, parent)
        if not _responder(caso):
            return None
        return caso.decisao()
    return na_ui_e_esperar(_abrir)
