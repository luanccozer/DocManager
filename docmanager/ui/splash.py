"""Tela de abertura: a MESMA imagem da tela de carregamento nativa do `.exe`.

No duplo-clique, o bootloader do PyInstaller mostra `assets/splash.png` enquanto
o Python e as bibliotecas carregam. Quando o Qt sobe, esta splash assume com a
mesma imagem, no mesmo lugar (centro da tela), e só então a nativa fecha: a
troca não se vê. Ela fica até a janela principal estar montada e aparecer.

Até a 3.3.0-rc.1 eram duas telas DIFERENTES, uma depois da outra (a nativa nas
cores antigas, a do Qt redesenhada e com 1,6 s fixos de espera), e a troca
parecia defeito na abertura. A imagem é gerada por `tools/gerar_splash.py`, com
as cores dos tokens.
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from ..services.config import resource_path

NOME_IMAGEM = os.path.join("assets", "splash.png")


def caminho_da_imagem() -> str:
    """`assets/splash.png`: no `.exe`, em `_internal/assets` (o `("assets",
    "assets")` do .spec); no código-fonte, na raiz do repositório."""
    candidatos = (resource_path(NOME_IMAGEM),
                  os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                      os.path.abspath(__file__)))), NOME_IMAGEM))
    return next((c for c in candidatos if os.path.exists(c)), "")


def mostrar_splash() -> QSplashScreen | None:
    """Mostra a splash e a desenha na hora. `None` se não der (sem imagem, sem
    tela): a abertura nunca depende dela. Feche com `splash.finish(janela)`."""
    try:
        caminho = caminho_da_imagem()
        pixmap = QPixmap(caminho) if caminho else QPixmap()
        if pixmap.isNull():
            return None
        splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        tela = QApplication.primaryScreen()
        if tela is not None:
            splash.move(tela.availableGeometry().center() - splash.rect().center())
        splash.show()
        QApplication.processEvents()   # desenha JÁ, antes de a nativa sair
        return splash
    except Exception:  # noqa: BLE001 - a splash nunca impede a abertura
        return None
