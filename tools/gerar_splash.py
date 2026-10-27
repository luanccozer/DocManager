"""Gera `assets/splash.png` - a tela de carregamento NATIVA do executável.

Essa imagem é mostrada pelo bootloader do PyInstaller (objeto `Splash` no
`docmanager.spec`) já no duplo-clique, enquanto o Python e as bibliotecas
carregam; a splash do Qt (`ui/splash.py`) assume com a MESMA imagem e a
nativa fecha por baixo dela, sem troca visível de tela.

É uma imagem ESTÁTICA (o bootloader não anima). Antes o "carregando" vinha de
uma barra parcial, que ficava feia; agora a tela é limpa - logo + título +
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

from docmanager.ui.tokens import ESCURO  # noqa: E402  (cores = as do app)

W, H = 440, 260
SAIDA = os.path.join(RAIZ, "assets", "splash.png")
LOGO = os.path.join(RAIZ, "assets", "logo_definitivo.ico")
# A fonte da própria interface (vai no pacote): a imagem sai igual em qualquer
# máquina que a gere, e com a mesma letra da janela que vem depois dela.
ROBOTO = os.path.join(RAIZ, "docmanager", "ui", "recursos", "fontes", "Roboto-Regular.ttf")

# A splash da janela (`ui/splash.py`) mostra ESTA imagem, na mesma posição: a
# troca da nativa (do bootloader) para a do Qt não se vê. Antes eram duas telas
# diferentes, uma depois da outra, e a troca parecia defeito.
FUNDO = ESCURO["superficie"]
BORDA = ESCURO["primaria"]
TEXTO = ESCURO["texto"]
TEXTO_SUAVE = ESCURO["texto_suave"]


def _fonte(tam: int):
    try:
        return ImageFont.truetype(ROBOTO, tam)
    except OSError:
        return ImageFont.load_default()


def _centrado(d: ImageDraw.ImageDraw, texto: str, fonte, y: int, cor: str, *, negrito=False) -> None:
    # O Roboto do pacote é só o Regular: o negrito sai do contorno no mesmo tom.
    contorno = 1 if negrito else 0
    largura = d.textlength(texto, font=fonte) + 2 * contorno
    d.text(((W - largura) / 2, y), texto, font=fonte, fill=cor,
           stroke_width=contorno, stroke_fill=cor)


def _logo(lado: int):
    """Logo definitivo redimensionado (RGBA), ou None se indisponível."""
    try:
        return Image.open(LOGO).convert("RGBA").resize((lado, lado), Image.LANCZOS)
    except Exception:  # noqa: BLE001
        return None


def gerar() -> str:
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W - 1, H - 1], outline=BORDA, width=2)

    # Logo centralizado no topo - dá cara de tela intencional (não "vazia").
    y = 32
    logo = _logo(84)
    if logo is not None:
        img.paste(logo, ((W - logo.width) // 2, y), logo)
        y += logo.height + 16
    else:
        y += 26

    _centrado(d, "DocManager Itaipu", _fonte(29), y, TEXTO, negrito=True)
    y += 46
    _centrado(d, "Gestão documental · CMI · Itaipu", _fonte(13), y, TEXTO_SUAVE)
    y += 30
    _centrado(d, "Carregando...", _fonte(12), y, TEXTO_SUAVE)

    img.save(SAIDA)
    return SAIDA


if __name__ == "__main__":
    print("splash gerado:", gerar())
