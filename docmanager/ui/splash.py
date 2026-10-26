"""Splash de abertura: janela SEM bordas com o logo enquanto o app carrega.
Fecha sozinha e revela a janela principal.

No Qt a escala de DPI é do próprio toolkit (High-DPI ligado por padrão no Qt 6):
a splash é montada escondida, já no tamanho final, e só então aparece - sem o
"pulo" de tamanho que a do CustomTkinter tinha em telas a 125/150%.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QProgressBar, QVBoxLayout

from .. import __version__
from . import estilo
from .logo import pixmap_do_logo


def mostrar_splash(ms: int = 1600, ao_fechar=None):
    """Mostra a splash; após `ms`, fecha e chama `ao_fechar` (tipicamente
    mostrar a janela principal). Se a splash falhar, chama `ao_fechar` na hora."""
    try:
        sp = QFrame(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.WindowStaysOnTopHint)
        sp.setObjectName("splash")
        sp.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        sp.setStyleSheet(estilo.folha_da_splash())
        sp.setFixedSize(440, 260)
        lay = QVBoxLayout(sp)
        lay.setContentsMargins(30, 26, 30, 30)
        lay.setSpacing(10)
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not (pix := pixmap_do_logo(84)).isNull():
            logo.setPixmap(pix)
            lay.addWidget(logo)
        titulo = QLabel("DocManager Itaipu")
        titulo.setObjectName("splash_titulo")
        sub = QLabel(f"Gestão documental · CMI ↔ Itaipu · v{__version__}")
        sub.setObjectName("splash_sub")
        for w in (titulo, sub):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(w)
        barra = QProgressBar()
        barra.setRange(0, 0)       # indeterminada: o "carregando"
        barra.setTextVisible(False)
        barra.setFixedWidth(250)
        lay.addSpacing(8)
        lay.addWidget(barra, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)
        tela = QApplication.primaryScreen()
        if tela is not None:
            geo = tela.availableGeometry()
            sp.move(geo.center() - sp.rect().center())
        sp.show()
    except Exception:  # noqa: BLE001 - se a splash falhar, segue direto para o app
        if ao_fechar:
            ao_fechar()
        return None

    def _fim():
        try:
            sp.close()
        except RuntimeError:
            pass
        if ao_fechar:
            ao_fechar()

    QTimer.singleShot(ms, _fim)
    return sp
