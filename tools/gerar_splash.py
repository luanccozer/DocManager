"""Gera `assets/splash.png` — a tela de carregamento NATIVA do executável.

Essa imagem é mostrada pelo bootloader do PyInstaller (objeto `Splash` no
`docmanager.spec`) já no duplo-clique, enquanto o Python e as bibliotecas
carregam; `ui/main_app.main()` a fecha quando o app fica pronto.

É uma imagem ESTÁTICA (o bootloader não anima), então o "está carregando" é
comunicado pelo texto + uma barra parcialmente preenchida. As cores saem do
tema do app, para o splash e a janela combinarem.

Rodar (dentro do venv):  python tools/gerar_splash.py
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from docmanager.ui import theme as t  # noqa: E402  (cores = as do app)

W, H = 440, 260
SAIDA = os.path.join(RAIZ, "assets", "splash.png")
TRILHA = t.CARD_BORDA          # trilho da barra
FONTES = r"C:\Windows\Fonts"


def _fonte(nome: str, tam: int):
    """Segoe UI (padrão do Windows); cai no default do PIL se faltar."""
    try:
        return ImageFont.truetype(os.path.join(FONTES, nome), tam)
    except OSError:
        return ImageFont.load_default()


def _centrado(d: ImageDraw.ImageDraw, texto: str, fonte, y: int, cor: str) -> None:
    largura = d.textlength(texto, font=fonte)
    d.text(((W - largura) / 2, y), texto, font=fonte, fill=cor)


def gerar() -> str:
    img = Image.new("RGB", (W, H), t.SIDEBAR)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=t.ACENTO, width=2)

    _centrado(d, "DocManager Itaipu", _fonte("segoeuib.ttf", 30), 74, t.TEXTO)
    _centrado(d, "Gestão documental · CMI ↔ Itaipu", _fonte("segoeui.ttf", 13), 116, t.TEXTO_FRACO)

    # Barra parcial: num splash estático, é o que comunica "carregando".
    x0, x1, y, alt = 84, W - 84, 164, 8
    d.rounded_rectangle([x0, y, x1, y + alt], radius=alt // 2, fill=TRILHA)
    d.rounded_rectangle([x0, y, x0 + (x1 - x0) * 0.45, y + alt], radius=alt // 2, fill=t.ACENTO)

    _centrado(d, "Carregando...", _fonte("segoeui.ttf", 12), 186, t.TEXTO_FRACO)

    img.save(SAIDA)
    return SAIDA


if __name__ == "__main__":
    print("splash gerado:", gerar())
