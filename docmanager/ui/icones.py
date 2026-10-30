"""Os ícones da interface: SVG de traço do Lucide, pintados na cor do tema.

Mesma peça do SIG-FT (`sigft/app_qt/icones.py`). O emoji dependia da fonte de
cada máquina (colorido, preto e branco ou um quadrado vazio) e não seguia o
tema; o SVG é o mesmo em toda máquina e sai na cor que se pedir.

Os arquivos moram em `ui/recursos/icones/` (só os usados, copiados do
`lucide-static@0.460.0`, licença ISC no LICENSE da pasta). O traço deles é
`stroke="currentColor"`: aqui o `currentColor` vira a cor pedida e o
`QSvgRenderer` desenha num `QPixmap` (1x e 2x, para tela de alta densidade).

`aplicar` guarda no widget o nome do ícone e o papel da cor; `reaplicar(raiz)`
repinta todos com a paleta do tema de agora (a troca de tema chama).
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QByteArray, QEvent, QObject, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from . import estilo
from .propriedades import ler

_log = logging.getLogger(__name__)

PASTA = estilo.PASTA_ICONES

# Os que a interface usa; a pasta tem exatamente estes (teste).
NOMES = frozenset({
    "house", "compass", "list-checks", "search", "chart-column", "clipboard-list",
    "download", "settings", "refresh-cw", "sparkles", "folder-open", "folder", "file",
    "play", "sun", "moon", "monitor", "trash-2", "key-round", "user-plus", "pencil",
    "history", "calendar-range", "file-spreadsheet", "table", "workflow", "eraser",
    "chevron-down", "check", "lightbulb", "mail", "copy",
})

TAMANHO_PADRAO = 18
_ESCALAS = (1, 2)
_CACHE: dict[tuple[str, str, int], QIcon] = {}


def _desenhar(svg: bytes, lado: int, escala: int) -> QPixmap:
    renderizador = QSvgRenderer(QByteArray(svg))
    if not renderizador.isValid():
        return QPixmap()
    pixmap = QPixmap(lado * escala, lado * escala)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderizador.render(pintor, QRectF(0, 0, lado * escala, lado * escala))
    pintor.end()
    pixmap.setDevicePixelRatio(escala)
    return pixmap


def icone(nome: str, cor: str, tamanho: int = TAMANHO_PADRAO) -> QIcon:
    """O ícone `nome` na cor `cor` ("#RRGGBB"). Nome desconhecido ou arquivo que
    não desenha: `QIcon()` vazio e um aviso no log - botão sem ícone, e não a
    tela que não abre."""
    chave = (nome, cor, tamanho)
    if chave not in _CACHE:
        _CACHE[chave] = _montar(nome, cor, tamanho)
    return _CACHE[chave]


def _montar(nome: str, cor: str, tamanho: int) -> QIcon:
    caminho = PASTA / f"{nome}.svg"
    try:
        svg = caminho.read_bytes().replace(b"currentColor", cor.encode("ascii"))
    except OSError:
        _log.warning("icone %r nao encontrado em %s", nome, PASTA)
        return QIcon()
    resultado = QIcon()
    for escala in _ESCALAS:
        pixmap = _desenhar(svg, tamanho, escala)
        if pixmap.isNull():
            _log.warning("icone %r nao desenhou (%s)", nome, caminho)
            return QIcon()
        resultado.addPixmap(pixmap)
    return resultado


def salvar_png(nome: str, cor: str, destino, tamanho: int = 14) -> str:
    """Grava o ícone como PNG (2x) e devolve o caminho com "/" - é o que a folha
    QSS aceita em `image: url(...)` (seta do QComboBox, tique da caixa de marcar),
    que não tem como pintar um SVG de `currentColor`. '' se não deu."""
    from pathlib import Path

    try:
        svg = (PASTA / f"{nome}.svg").read_bytes().replace(b"currentColor", cor.encode("ascii"))
        pixmap = _desenhar(svg, tamanho, 2)
        arq = Path(destino) / f"{nome}_{cor.lstrip('#')}.png"
        arq.parent.mkdir(parents=True, exist_ok=True)
        if pixmap.isNull() or not pixmap.save(str(arq), "PNG"):
            return ""
        return arq.as_posix()
    except OSError:
        return ""


def conferir() -> list[str]:
    """Os nomes de `NOMES` que não desenham - um SVG ou o QtSvg fora do `.exe`
    dariam botões em branco, calados."""
    return sorted(n for n in NOMES if icone(n, estilo.paleta_atual()["texto"]).isNull())


def _cor(widget: QWidget) -> str:
    papel = ler(widget, "icone_cor")
    destacado = bool(ler(widget, "ativo")) or (
        bool(ler(widget, "icone_sob_mouse")) and widget.isEnabled())
    if destacado and ler(widget, "icone_cor_ativo"):
        papel = ler(widget, "icone_cor_ativo")
    if papel and (cor := estilo.cor_do_papel(papel)) is not None:
        return cor
    return estilo.cor_do_texto_da_variante(ler(widget, "variante"))


class _SegueOMouse(QObject):
    """Repinta o ícone ao entrar e ao sair o mouse: o `:hover` da folha muda a
    cor do TEXTO, e o ícone não tem `:hover`."""

    def eventFilter(self, alvo, evento) -> bool:  # noqa: N802 - nome do Qt
        if evento.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            alvo.setProperty("icone_sob_mouse", evento.type() == QEvent.Type.Enter)
            _pintar(alvo)
        return False


def _pintar(widget: QWidget) -> None:
    tamanho = int(ler(widget, "icone_tamanho") or TAMANHO_PADRAO)
    desenho = icone(ler(widget, "icone"), _cor(widget), tamanho)
    if isinstance(widget, QAbstractButton):
        widget.setIcon(desenho)
        widget.setIconSize(QSize(tamanho, tamanho))
    elif isinstance(widget, QLabel):
        widget.setPixmap(desenho.pixmap(tamanho, tamanho))


def aplicar(widget: QWidget, nome: str, *, papel_cor: str | None = None,
            papel_cor_ativo: str | None = None, tamanho: int = TAMANHO_PADRAO) -> QWidget:
    """Põe o ícone `nome` num botão (ao lado do texto) ou num rótulo (como
    desenho). A cor é a do texto da variante do botão, ou a do `papel_cor` da
    paleta; `papel_cor_ativo` vale com o widget `ativo` ou o mouse em cima.
    Devolve o widget."""
    widget.setProperty("icone", nome)
    widget.setProperty("icone_cor", papel_cor)
    widget.setProperty("icone_cor_ativo", papel_cor_ativo)
    widget.setProperty("icone_tamanho", tamanho)
    if papel_cor_ativo and not ler(widget, "icone_segue_mouse"):
        widget.setProperty("icone_segue_mouse", True)
        widget.installEventFilter(_SegueOMouse(widget))
    _pintar(widget)
    return widget


def reaplicar(raiz: QWidget) -> None:
    """Repinta, com a paleta de agora, todo ícone posto por `aplicar` em `raiz`
    e nos filhos dela."""
    for widget in [raiz, *raiz.findChildren(QWidget)]:
        if ler(widget, "icone"):
            _pintar(widget)
