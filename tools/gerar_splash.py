"""Gera `assets/splash.png` — a tela de carregamento NATIVA do executável.

Essa imagem é mostrada pelo bootloader do PyInstaller (objeto `Splash` no
`docmanager.spec`) já no duplo-clique, enquanto o Python e as bibliotecas
carregam; `ui/main_app.main()` a fecha quando o app fica pronto.

É uma imagem ESTÁTICA (o bootloader não anima). Antes o "carregando" vinha de
uma barra parcial, que ficava feia; agora a tela é limpa — logo + título +
subtítulo + um "Carregando..." discreto, SEM barra. As cores saem do tema do
app, para o splash e a janela combinarem.

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
LOGO = os.path.join(RAIZ, "assets", "logo_definitivo.ico")
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


def _logo(lado: int):
    """Logo definitivo redimensionado (RGBA), ou None se indisponível."""
    try:
        return Image.open(LOGO).convert("RGBA").resize((lado, lado), Image.LANCZOS)
    except Exception:  # noqa: BLE001
        return None


def gerar() -> str:
    img = Image.new("RGB", (W, H), t.SIDEBAR)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=t.ACENTO, width=2)

    # Logo centralizado no topo — dá cara de tela intencional (não "vazia").
    y = 32
    logo = _logo(84)
    if logo is not None:
        img.paste(logo, ((W - logo.width) // 2, y), logo)
        y += logo.height + 16
    else:
        y += 26

    _centrado(d, "DocManager Itaipu", _fonte("segoeuib.ttf", 30), y, t.TEXTO)
    y += 46
    _centrado(d, "Gestão documental · CMI ↔ Itaipu", _fonte("segoeui.ttf", 13), y, t.TEXTO_FRACO)
    y += 30
    _centrado(d, "Carregando...", _fonte("segoeui.ttf", 12), y, t.TEXTO_FRACO)

    img.save(SAIDA)
    return SAIDA


if __name__ == "__main__":
    print("splash gerado:", gerar())
