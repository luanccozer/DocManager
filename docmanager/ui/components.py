"""Componentes reutilizáveis da UI: cartão, seletor de arquivo, console de log,
abas e barra de execução. Todos pintados pela folha de `ui/estilo.py`."""
from __future__ import annotations

import os
import threading
import traceback
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import dialogos, icones
from .dialogos import pedir_salvar  # noqa: F401 - reexportado para as telas
from .ponte import na_ui


# ─────────────────────────────── peças miúdas ────────────────────────────────

def rotulo(texto: str = "", papel: str | None = None, *, quebra: bool = False,
           nome: str | None = None) -> QLabel:
    """QLabel com `papel` de cor (`QLabel[papel=...]` da folha) e quebra de linha."""
    lbl = QLabel(texto)
    if papel:
        lbl.setProperty("papel", papel)
    if nome:
        lbl.setObjectName(nome)
    if quebra:
        lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


def botao(texto: str, *, variante: str | None = None, icone: str | None = None,
          ao_clicar=None, acao: bool = False, dica: str | None = None) -> QPushButton:
    """QPushButton com `variante` (primario, perigo, fantasma; sem = secundário),
    ícone Lucide opcional e `acao=True` para o botão alto das ações principais."""
    b = QPushButton(texto)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if variante:
        b.setProperty("variante", variante)
    if acao:
        b.setProperty("acao", True)
    if icone:
        icones.aplicar(b, icone)
    if ao_clicar is not None:
        b.clicked.connect(lambda _=False: ao_clicar())
    if dica:
        b.setToolTip(dica)
    return b


def linha(*widgets, esticar: int | None = None, espaco: int = 8) -> QWidget:
    """Widgets lado a lado. `esticar`: índice do que ocupa a sobra; sem ele, a
    sobra fica no fim (tudo encostado à esquerda)."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(espaco)
    for i, item in enumerate(widgets):
        lay.addWidget(item, 1 if i == esticar else 0)
    if esticar is None:
        lay.addStretch(1)
    return w


def rodape(*botoes) -> QWidget:
    """Botões de diálogo encostados à direita; o primeiro fica mais à direita."""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addStretch(1)
    for b in reversed(botoes):
        lay.addWidget(b)
    return w


class Seletor(QComboBox):
    """Lista de escolha que a roda do mouse NÃO troca sem foco.

    As telas rolam: a roda passando por cima de um QComboBox cru trocava a aba
    do Excel ou o usuário do Aconex sem ninguém perceber (o mesmo defeito que o
    Corella Suite achou no seletor de lote). Com foco - a pessoa clicou nele -
    a roda vale."""

    def __init__(self, itens=(), parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.addItems(list(itens))

    def wheelEvent(self, evento):  # noqa: N802 - nome do Qt
        if self.hasFocus():
            super().wheelEvent(evento)
        else:
            evento.ignore()

    def get(self) -> str:
        return self.currentText()

    def definir_itens(self, itens, escolhido: str | None = None) -> None:
        """Troca os itens sem disparar `currentTextChanged` no meio."""
        self.blockSignals(True)
        self.clear()
        self.addItems(list(itens))
        if escolhido is not None and escolhido in itens:
            self.setCurrentText(escolhido)
        self.blockSignals(False)


def _emitir(sinal, *args) -> None:
    """Emite sem levantar: a janela pode ter fechado com a tarefa rodando, e
    um sinal de objeto já destruído levanta RuntimeError NA THREAD da tarefa -
    que morreria no meio do trabalho por causa de um log."""
    try:
        sinal.emit(*args)
    except RuntimeError:
        pass


class Card(QFrame):
    """Bloco visual (#card) com título opcional. `add(widget)` empilha."""

    def __init__(self, titulo: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(18, 14, 18, 16)
        self._lay.setSpacing(8)
        if titulo:
            self._lay.addWidget(rotulo(titulo, nome="card_titulo"))

    def add(self, widget: QWidget, *, esticar: int = 0) -> QWidget:
        self._lay.addWidget(widget, esticar)
        return widget


# ─────────────────────────────── seletor de arquivo ──────────────────────────

def _listar_abas(caminho: str) -> list[str]:
    """Nomes das abas do Excel (rápido, sem ler os dados).

    Fecha o arquivo na saída. Sem o `with`, o ExcelFile só era fechado quando o
    coletor de lixo passasse - minutos depois, num app parado -, e enquanto isso
    o Excel não conseguia salvar a planilha: ele salva trocando o arquivo, e o
    Windows não troca um arquivo que outro programa tem aberto (3.6.1-rc.1).
    """
    try:
        import pandas as pd
        with pd.ExcelFile(caminho) as arquivo:
            return list(arquivo.sheet_names)
    except Exception:  # noqa: BLE001
        return []


_PLACEHOLDER_ABA = "Selecione o arquivo primeiro"
LARGURA_ROTULO = 220


class FileSelector(QWidget):
    """Rótulo + caminho + botão 'Selecionar' + seletor de aba (sempre visível).

    O seletor de aba exibe um placeholder até um arquivo ser escolhido e então
    lista as abas reais, permitindo trocar a qualquer momento. Expõe `.path` e
    `.sheet` (nome da aba, ou 0 = a primeira)."""

    def __init__(self, label: str, config=None, tipo: str = "arquivo",
                 filtro: str = dialogos.FILTRO_EXCEL, on_change=None,
                 escolher_aba: bool = True, aba_padrao: str | None = None, parent=None):
        super().__init__(parent)
        self.config_mgr = config
        self.tipo = tipo
        self.filtro = filtro
        self.on_change = on_change
        self.escolher_aba = escolher_aba
        self.aba_padrao = aba_padrao
        self.path: str | None = None
        self.sheet = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(4)
        nome = QLabel(label)
        nome.setFixedWidth(LARGURA_ROTULO)
        self.lbl = rotulo("Nenhum arquivo", "suave")
        self.lbl.setMinimumWidth(120)
        self.btn = botao("Selecionar", icone="folder-open", ao_clicar=self._escolher)
        lay.addWidget(linha(nome, self.lbl, self.btn, esticar=1))

        if escolher_aba:
            aba = rotulo("Aba (Sheet):", "legenda")
            aba.setFixedWidth(LARGURA_ROTULO)
            self.opt_aba = Seletor([_PLACEHOLDER_ABA])
            self.opt_aba.setMinimumWidth(280)
            self.opt_aba.currentTextChanged.connect(self._set_aba)
            lay.addWidget(linha(aba, self.opt_aba))

    def _set_aba(self, nome: str) -> None:
        self.sheet = nome if nome and nome != _PLACEHOLDER_ABA else 0

    def _escolher(self) -> None:
        caminho = dialogos.escolher_arquivo(self.config_mgr, self.tipo, self.filtro, parent=self)
        if caminho:
            self.definir(caminho)

    def definir(self, caminho: str) -> None:
        """Escolhe `caminho` como se viesse do diálogo (lista as abas)."""
        self.path = caminho
        self.lbl.setText(os.path.basename(caminho))
        self.lbl.setToolTip(caminho)
        self.lbl.setProperty("papel", None)
        self.lbl.style().unpolish(self.lbl)
        self.lbl.style().polish(self.lbl)
        if self.escolher_aba:
            abas = _listar_abas(caminho)
            if abas:
                escolhida = self.aba_padrao if self.aba_padrao in abas else abas[0]
                self.opt_aba.definir_itens(abas, escolhida)
                self.sheet = escolhida
            else:
                self.opt_aba.definir_itens([_PLACEHOLDER_ABA])
                self.sheet = 0
        if self.on_change:
            self.on_change(caminho)


# ─────────────────────────────── console de log ──────────────────────────────

class LogConsole(QPlainTextEdit):
    """Console de log thread-safe (use .log() de qualquer thread). Carimba a hora
    de cada linha e rola sozinho até o fim; `clear()` esvazia."""

    _linha = Signal(str)
    _limpar = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._linha.connect(self._inserir)
        self._limpar.connect(super().clear)

    def log(self, msg) -> None:
        carimbo = datetime.now().strftime("%H:%M:%S")
        msg = str(msg)
        # Preserva linhas em branco iniciais (mensagens que começam com \n).
        prefixo = "\n" * (len(msg) - len(msg.lstrip("\n")))
        _emitir(self._linha, f"{prefixo}[{carimbo}] {msg.lstrip(chr(10))}")

    def _inserir(self, texto: str) -> None:
        self.appendPlainText(texto)
        barra = self.verticalScrollBar()
        barra.setValue(barra.maximum())

    def clear(self) -> None:  # noqa: D102 - thread-safe
        _emitir(self._limpar)

    def texto(self) -> str:
        return self.toPlainText()


# ─────────────────────────────── abas ────────────────────────────────────────

class Abas(QWidget):
    """Abas no estilo do SIG-FT: uma barra de botões (#barra_abas) sobre as
    páginas. `add(nome)` devolve a página (com um QVBoxLayout); `get()` é o
    nome da aba ativa, como o `CTkTabview.get()` que as telas já usavam."""

    mudou = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self._barra = QFrame()
        self._barra.setObjectName("barra_abas")
        self._barra_lay = QHBoxLayout(self._barra)
        self._barra_lay.setContentsMargins(4, 4, 4, 4)
        self._barra_lay.setSpacing(4)
        self._barra_lay.addStretch(1)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        self._pilha = QStackedWidget()
        lay.addWidget(self._barra)
        lay.addWidget(self._pilha)
        self._nomes: list[str] = []
        self._botoes: dict[str, QPushButton] = {}

    def add(self, nome: str, icone: str | None = None) -> QWidget:
        b = QPushButton(nome)
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        if icone:
            icones.aplicar(b, icone, tamanho=16)
        indice = len(self._nomes)
        b.clicked.connect(lambda _=False, n=nome: self.set(n))
        self._grupo.addButton(b)
        self._barra_lay.insertWidget(indice, b)
        pagina = QWidget()
        pl = QVBoxLayout(pagina)
        pl.setContentsMargins(2, 0, 2, 0)
        pl.setSpacing(8)
        self._pilha.addWidget(pagina)
        self._nomes.append(nome)
        self._botoes[nome] = b
        if indice == 0:
            b.setChecked(True)
        return pagina

    def get(self) -> str:
        return self._nomes[self._pilha.currentIndex()] if self._nomes else ""

    def set(self, nome: str) -> None:
        i = self._nomes.index(nome)
        self._botoes[nome].setChecked(True)
        self._pilha.setCurrentIndex(i)
        self.mudou.emit(nome)


# ─────────────────────────────── barra de execução ───────────────────────────

class RunBar(QWidget):
    """Barra de progresso + botão de ação. Roda a tarefa numa thread.

    A tarefa recebe a própria RunBar (`run.set_progress(0.5)` de qualquer
    thread). Exceção vira "ERRO: ..." no log; o botão volta ao normal no fim."""

    # As que estão processando agora, em qualquer tela. A atualização pergunta
    # antes de fechar o app se houver alguma (ver `MainApp.tarefa_em_andamento`).
    em_andamento: set = set()

    _progresso = Signal(float)
    terminou = Signal()

    def __init__(self, texto: str, tarefa, log: LogConsole | None = None, parent=None):
        super().__init__(parent)
        self.tarefa = tarefa
        self.log = log
        self._texto = texto
        self._rodando = False
        self._desabilitado = False

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.btn = botao(texto, variante="primario", icone="play", acao=True, ao_clicar=self._run)
        self.btn.setMinimumWidth(200)
        lay.addWidget(self.progress, 1)
        lay.addWidget(self.btn)
        self._progresso.connect(lambda v: self.progress.setValue(int(max(0.0, min(v, 1.0)) * 1000)))

    def set_progress(self, v: float) -> None:
        _emitir(self._progresso, float(v))

    def rodando(self) -> bool:
        return self._rodando

    def desabilitar(self, texto: str | None = None) -> None:
        """Deixa o botão visível porém inativo (funcionalidade em desenvolvimento)."""
        self._desabilitado = True
        self.btn.setEnabled(False)
        self.btn.setText(texto or self._texto)
        icones.reaplicar(self.btn)

    def _run(self) -> None:
        if self._desabilitado or self._rodando:   # inativo ou já processando
            return
        self._rodando = True
        RunBar.em_andamento.add(self)
        self.btn.setEnabled(False)
        self.btn.setText("Processando...")
        self.progress.setValue(0)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            self.tarefa(self)
        except Exception as e:  # noqa: BLE001 - a falha vai para o log da tela
            if self.log:
                self.log.log(f"ERRO: {e}")
                self.log.log(traceback.format_exc().rstrip())
        finally:
            na_ui(self._finalizar)

    def _finalizar(self) -> None:
        self._rodando = False
        RunBar.em_andamento.discard(self)
        self.btn.setEnabled(True)
        self.btn.setText(self._texto)   # volta ao rótulo original
        self.progress.setValue(0)
        self.terminou.emit()
