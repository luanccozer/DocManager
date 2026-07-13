"""Home — tela inicial neutra: boas-vindas, novidades e o que faz cada módulo.

O app abre aqui. Não é um módulo de processamento (sem console de log): é um
ponto de partida que explica os blocos e mostra as atualizações recentes.
"""
from __future__ import annotations

import os

import customtkinter as ctk

from .. import theme as t

# (versão, itens) — a mais recente no topo.
NOVIDADES = [
    ("Atual", [
        "Home com novidades e explicação de cada módulo.",
        "Histórico ganha colunas de Data Prevista e Reprogramação (na revisão 0A).",
        "Configuração: base do atraso CMI na 0A (reprogramação ou data prevista).",
        "Excel do Status padronizado ao visual executivo do Histórico (mantém o gráfico).",
        "Logo oficial do projeto e ícones da barra lateral alinhados.",
    ]),
    ("Recentes", [
        "Console de log padronizado e de altura dinâmica em todas as telas.",
        "Botão não fica mais preso em 'Processando...' ao rodar outra ação.",
        "Delta do Status abre em árvore (por classificação); Delta do Mapa mantém níveis.",
        "Controle de Documentos com leitura dinâmica (cabeçalho e datas robustos).",
        "Arquitetura por módulo: um backend para cada bloco + funções comuns.",
    ]),
]

# (ícone, título, descrição) de cada bloco.
MODULOS = [
    ("🗺️", "Mapa dos Planos", "Atualiza a planilha de mapeamento: status real, hierarquia, "
     "KPIs e atrasos. Traz também o Delta (Máquina do Tempo) por Grupo/Nível."),
    ("🔎", "Status Documentos", "Status real de uma lista, de um arquivo Excel ou de toda a base "
     "vigente. Gera Excel com gráfico e abre o Delta por período (por classificação)."),
    ("📊", "Histórico e Dashboard", "Planilha detalhada (1 linha por revisão + atrasos Itaipu/CMI) "
     "e o painel executivo com evolução do atraso, First Time Right e gargalos."),
    ("📋", "Relatórios", "Relatório de Avanço (prazos de devolução da Itaipu) e Auditoria de "
     "Integração (documentos presos em 0AA)."),
    ("☁️", "Extração Aconex", "Baixa a base completa do projeto direto da API do Aconex "
     "(requer o segredo no arquivo .env)."),
    ("⚙️", "Configurações", "Regra da Aprovação Intermediária (VIP) e a base do atraso CMI na 0A."),
]


class HomeView(ctk.CTkFrame):
    titulo_view = "Início"

    def __init__(self, master, ctx):
        super().__init__(master, fg_color=t.FUNDO)
        self.ctx = ctx
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew", padx=28, pady=24)
        body.grid_columnconfigure(0, weight=1)
        self._hero(body)
        self._novidades(body)
        self._modulos(body)

    def _hero(self, body):
        card = ctk.CTkFrame(body, fg_color=t.CARD, corner_radius=14,
                            border_width=1, border_color=t.CARD_BORDA)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        linha = ctk.CTkFrame(card, fg_color="transparent")
        linha.pack(anchor="w", padx=24, pady=20, fill="x")
        logo = self._logo(64)
        if logo is not None:
            ctk.CTkLabel(linha, image=logo, text="").pack(side="left", padx=(0, 16))
        texto = ctk.CTkFrame(linha, fg_color="transparent")
        texto.pack(side="left", anchor="w")
        ctk.CTkLabel(texto, text="DocManager Itaipu", font=t.titulo(26),
                     text_color=t.TEXTO).pack(anchor="w")
        ctk.CTkLabel(texto, text=f"Gestão documental · CMI ↔ Itaipu · v{self.ctx.versao}",
                     font=t.corpo(13), text_color=t.TEXTO_FRACO).pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(card, text="Escolha um módulo na barra lateral para começar. Abaixo, o que há "
                     "de novo e o que cada bloco faz.", font=t.corpo(13), text_color=t.TEXTO_FRACO,
                     justify="left", wraplength=760).pack(anchor="w", padx=24, pady=(0, 18))

    def _novidades(self, body):
        card = ctk.CTkFrame(body, fg_color=t.CARD, corner_radius=14,
                            border_width=1, border_color=t.CARD_BORDA)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(card, text="✨ O que há de novo", font=t.titulo(16),
                     text_color=t.TEXTO).pack(anchor="w", padx=24, pady=(18, 8))
        for bloco, itens in NOVIDADES:
            ctk.CTkLabel(card, text=bloco, font=t.corpo(12, "bold"),
                         text_color=t.ACENTO).pack(anchor="w", padx=24, pady=(6, 2))
            for it in itens:
                ctk.CTkLabel(card, text=f"•  {it}", font=t.corpo(13), text_color=t.TEXTO_FRACO,
                             justify="left", wraplength=760).pack(anchor="w", padx=(34, 24), pady=1)
        ctk.CTkLabel(card, text="", font=t.corpo(6)).pack(pady=(0, 8))

    def _modulos(self, body):
        card = ctk.CTkFrame(body, fg_color="transparent")
        card.grid(row=2, column=0, sticky="ew")
        card.grid_columnconfigure((0, 1), weight=1, uniform="mod")
        ctk.CTkLabel(card, text="🧭 Módulos", font=t.titulo(16), text_color=t.TEXTO).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for i, (ic, nome, desc) in enumerate(MODULOS):
            bloco = ctk.CTkFrame(card, fg_color=t.CARD, corner_radius=12,
                                 border_width=1, border_color=t.CARD_BORDA)
            bloco.grid(row=1 + i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 8,
                       8 if i % 2 == 0 else 0), pady=6)
            topo = ctk.CTkFrame(bloco, fg_color="transparent")
            topo.pack(anchor="w", padx=16, pady=(14, 2), fill="x")
            ctk.CTkLabel(topo, text=ic, font=t.corpo(18)).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(topo, text=nome, font=t.corpo(14, "bold"), text_color=t.TEXTO).pack(side="left")
            ctk.CTkLabel(bloco, text=desc, font=t.corpo(12), text_color=t.TEXTO_FRACO,
                         justify="left", wraplength=340).pack(anchor="w", padx=16, pady=(0, 14))

    def _logo(self, lado):
        try:
            from PIL import Image

            from ...services.config import resource_path
            caminho = resource_path(os.path.join("assets", "logo_definitivo.ico"))
            if not os.path.exists(caminho):
                return None
            img = Image.open(caminho)
            self._logo_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(lado, lado))
            return self._logo_ref
        except Exception:
            return None
