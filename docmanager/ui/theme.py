"""Nomes antigos das cores, derivados dos tokens - sem biblioteca gráfica.

A interface lê as cores de `ui/tokens.py` (por papel, nos dois temas). Este
módulo fica só para quem roda FORA da janela e precisa de uma cor fixa: o
`tools/gerar_splash.py`, que desenha a imagem da tela de carregamento nativa
do executável com o Pillow (o tema escuro, que é o padrão).
"""
from __future__ import annotations

from .tokens import ESCURO

SIDEBAR = ESCURO["superficie"]
FUNDO = ESCURO["fundo"]
CARD = ESCURO["superficie"]
CARD_BORDA = ESCURO["borda"]
ACENTO = ESCURO["primaria"]
TEXTO = ESCURO["texto"]
TEXTO_FRACO = ESCURO["texto_suave"]
