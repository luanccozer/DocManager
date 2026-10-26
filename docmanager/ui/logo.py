"""O logo do app (`assets/logo_definitivo.ico`) como imagem do Qt."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

from ..services.config import resource_path

CAMINHO_ICO = resource_path(os.path.join("assets", "logo_definitivo.ico"))


def icone_do_app() -> QIcon:
    return QIcon(CAMINHO_ICO) if os.path.exists(CAMINHO_ICO) else QIcon()


def pixmap_do_logo(lado: int) -> QPixmap:
    """O logo em `lado` x `lado` px (nulo se o arquivo faltar)."""
    icone = icone_do_app()
    if icone.isNull():
        return QPixmap()
    pix = icone.pixmap(256, 256)
    return pix.scaled(lado, lado, Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)
