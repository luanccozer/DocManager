"""Paleta e tipografia - visual executivo/moderno, um só lugar."""
from __future__ import annotations

import customtkinter as ctk

# Paleta (slate + teal de acento, alinhada ao histórico)
SIDEBAR = "#1B2733"
SIDEBAR_HOVER = "#243444"
SIDEBAR_ATIVO = "#1F6F5C"
FUNDO = "#0F1620"
CARD = "#18222E"
CARD_BORDA = "#243444"
ACENTO = "#1F6F5C"
ACENTO_HOVER = "#25876F"
PERIGO = "#B23A48"
PERIGO_HOVER = "#8F2E39"
TEXTO = "#E8EDF2"
TEXTO_FRACO = "#8CA0B3"
OK = "#2ECC71"

FONTE = "Segoe UI"


def titulo(tamanho=22, peso="bold"):
    return ctk.CTkFont(family=FONTE, size=tamanho, weight=peso)


def corpo(tamanho=13, peso="normal"):
    return ctk.CTkFont(family=FONTE, size=tamanho, weight=peso)


def mono(tamanho=11):
    return ctk.CTkFont(family="Consolas", size=tamanho)


def aplicar():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
