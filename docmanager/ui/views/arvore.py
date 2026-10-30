"""Base das janelas de árvore (Delta do Mapa/Doc List, Delta do Status, Período).

As três têm a mesma forma: uma barra de filtros em cima, a árvore
"grupo → documento" no meio e, embaixo, o status da análise e "Exportar Excel".
O que se repetia nas três mora aqui:

* a análise roda numa thread e volta pela `ponte` (`rodar_em_thread`);
* duplo clique num documento copia o código;
* linha "em alerta" (documento repetido em mais de um grupo, data vencida) e
  "apagada" (já emitido) ganham a cor do tema - e a recebem de novo quando o
  tema troca.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import dialogos, estilo, icones, tema
from ..components import botao, rotulo
from ..ponte import na_ui
from ..idioma import t

PAPEL_DOC = Qt.ItemDataRole.UserRole + 1     # código do documento (para copiar)
PAPEL_ESTADO = Qt.ItemDataRole.UserRole + 2  # "alerta" / "apagado" / None


def campo_data(texto: str = "", dica: str = "DD/MM/AAAA", largura: int = 120) -> QLineEdit:
    campo = QLineEdit(texto)
    campo.setPlaceholderText(dica)
    campo.setFixedWidth(largura)
    return campo


class ArvoreDialog(QDialog):
    """Janela não modal com barra de filtros, árvore e rodapé."""

    def __init__(self, parent, *, titulo: str, colunas: list[tuple[str, int]], config=None,
                 largura: int = 1180, altura: int = 640):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.resize(largura, altura)
        self.config = config
        self._rodando = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        self.barra = QFrame()
        self.barra.setObjectName("barra_ferramentas")
        self.barra_lay = QHBoxLayout(self.barra)
        self.barra_lay.setContentsMargins(12, 8, 12, 8)
        self.barra_lay.setSpacing(8)
        lay.addWidget(self.barra)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(colunas))
        self.tree.setHeaderLabels([t(c) for c, _ in colunas])   # nomes marcados com `marcar`
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        for i, (_, largura_col) in enumerate(colunas):
            self.tree.setColumnWidth(i, largura_col)
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)
        self.tree.itemDoubleClicked.connect(self._duplo_clique)
        lay.addWidget(self.tree, 1)

        rod = QWidget()
        self.rodape_lay = QHBoxLayout(rod)
        self.rodape_lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_status = rotulo("", "suave")
        self.rodape_lay.addWidget(self.lbl_status, 1)
        self.btn_exportar = botao(t("Exportar Excel"), icone="file-spreadsheet", ao_clicar=self._exportar)
        self.btn_exportar.setEnabled(False)
        self.rodape_lay.addWidget(self.btn_exportar)
        lay.addWidget(rod)

        tema.mudou.connect(self._recolorir)

    # ------------------------------------------------------------- barra
    def adicionar_na_barra(self, *widgets) -> None:
        for w in widgets:
            self.barra_lay.addWidget(w)

    def legenda(self, texto: str) -> None:
        """Explicação da cor de alerta, no rodapé."""
        self.rodape_lay.insertWidget(1, rotulo(texto, "erro"))

    # ------------------------------------------------------------- árvore
    def limpar(self) -> None:
        self.tree.clear()

    def grupo(self, texto: str, pai: QTreeWidgetItem | None = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem([texto])
        f = item.font(0)
        f.setBold(True)
        item.setFont(0, f)
        item.setIcon(0, icones.icone("folder", estilo.paleta_atual()["texto_suave"], 16))
        (pai.addChild(item) if pai is not None else self.tree.addTopLevelItem(item))
        item.setExpanded(True)
        return item

    def documento(self, pai: QTreeWidgetItem, codigo: str, valores, estado: str | None = None):
        item = QTreeWidgetItem([codigo, *[str(v) for v in valores]])
        item.setIcon(0, icones.icone("file", estilo.paleta_atual()["texto_suave"], 16))
        item.setData(0, PAPEL_DOC, codigo)
        item.setData(0, PAPEL_ESTADO, estado)
        pai.addChild(item)
        self._pintar(item)
        return item

    def _pintar(self, item: QTreeWidgetItem) -> None:
        cor = estilo.cor_da_linha(item.data(0, PAPEL_ESTADO) or "")
        pincel = QBrush(QColor(cor)) if cor else QBrush()
        for c in range(self.tree.columnCount()):
            item.setForeground(c, pincel)

    def _recolorir(self, _tema=None) -> None:
        cor_icone = estilo.paleta_atual()["texto_suave"]
        pilha = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        while pilha:
            item = pilha.pop()
            e_doc = item.data(0, PAPEL_DOC) is not None
            item.setIcon(0, icones.icone("file" if e_doc else "folder", cor_icone, 16))
            if e_doc:
                self._pintar(item)
            pilha.extend(item.child(i) for i in range(item.childCount()))

    def _duplo_clique(self, item: QTreeWidgetItem, _coluna: int) -> None:
        codigo = item.data(0, PAPEL_DOC)
        if codigo:
            QApplication.clipboard().setText(codigo)
            dialogos.info(t("Copiado"), t('Código copiado:\n{codigo}', codigo=codigo), self)

    # ------------------------------------------------------------- análise
    def rodar_em_thread(self, botao_acao, texto_rodando: str, trabalho, ao_concluir) -> None:
        """Roda `trabalho()` numa thread e entrega o resultado a
        `ao_concluir(resultado)` na thread da interface."""
        if self._rodando:
            return
        self._rodando = True
        texto_original = botao_acao.text()
        botao_acao.setEnabled(False)
        botao_acao.setText(texto_rodando)

        def _fim(resultado):
            self._rodando = False
            botao_acao.setEnabled(True)
            botao_acao.setText(texto_original)
            ao_concluir(resultado)

        threading.Thread(target=lambda: na_ui(_fim, trabalho()), daemon=True).start()

    def _exportar(self) -> None:  # override
        raise NotImplementedError

    def done(self, r):  # noqa: D102 - solta o sinal do tema ao fechar
        try:
            tema.mudou.disconnect(self._recolorir)
        except (RuntimeError, TypeError):
            pass
        super().done(r)
