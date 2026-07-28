"""Home — tela inicial neutra: boas-vindas, módulos e novidades.

O app abre aqui. Não é um módulo de processamento (sem console de log): é um
ponto de partida que mostra os blocos e, abaixo, as atualizações recentes.
"""
from __future__ import annotations

import os

import customtkinter as ctk

from .. import theme as t

# ──────────────────────────────────────────────────────────────────────────
#  NOVIDADES — EDITE ESTA LISTA quando quiser anunciar mudanças aos usuários.
#  Cada item é uma frase curta e genérica. Deixe a lista vazia ([]) para
#  esconder a seção "O que há de novo". Nada mais precisa ser mexido.
# ──────────────────────────────────────────────────────────────────────────
NOVIDADES: list[str] = [
    "Novo módulo Doc List Mapping: follow-up da lista de documentos com dois níveis e agrupamento por escopo.",
    "Doc List Mapping traz a Análise por Período — quais documentos estão previstos para emitir nos próximos tempos.",
    "Busca das datas previstas no Controle de Documentos corrigida e com diagnóstico no log.",
    "Extração do Aconex retoma de onde parou quando a conexão cai.",
    "Tela inicial (Home) com os módulos e as novidades.",
    "Histórico com datas de previsão e reprogramação na revisão 0A.",
]

# (key da view, ícone, título, descrição) de cada bloco. A `key` casa com as
# ViewSpec da MainApp: clicar no bloco navega para o módulo.
MODULOS = [
    ("mapa", "🧭", "Mapa dos Planos", "Atualiza a planilha de mapeamento: status real, hierarquia, "
     "KPIs e atrasos. Traz também o Delta (Máquina do Tempo) por Grupo/Nível."),
    ("doclist", "📑", "Doc List Mapping", "Follow-up da lista de documentos (dois níveis, agrupamento por "
     "escopo). Traz o planejamento do Controle e a Análise por Período: o que está previsto para emitir."),
    ("status", "🔎", "Status Documentos", "Status real de uma lista, de um arquivo Excel ou de toda a base "
     "vigente. Gera Excel com gráfico e abre o Delta por período (por classificação)."),
    ("historico", "📊", "Histórico e Dashboard", "Planilha detalhada (1 linha por revisão + atrasos Itaipu/CMI) "
     "e o painel executivo com evolução do atraso, First Time Right e gargalos."),
    ("relatorios", "📋", "Relatórios", "Relatório de Avanço (prazos de devolução da Itaipu) e Auditoria de "
     "Integração (documentos presos em 0AA)."),
    ("aconex", "📥", "Extração Aconex", "Baixa a base completa do projeto direto da API do Aconex "
     "(requer o segredo no arquivo .env)."),
    ("config", "⚙️", "Configurações", "Regra da Aprovação Intermediária (VIP) e a base do atraso CMI na 0A."),
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
        self._hero(body)         # row 0
        self._modulos(body)      # row 1 — módulos PRIMEIRO
        self._novidades(body)    # row 2 — novidades depois

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
        ctk.CTkLabel(card, text="Clique em um módulo abaixo (ou use a barra lateral) para começar.",
                     font=t.corpo(13), text_color=t.TEXTO_FRACO,
                     justify="left", wraplength=760).pack(anchor="w", padx=24, pady=(0, 18))

    def _modulos(self, body):
        card = ctk.CTkFrame(body, fg_color="transparent")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure((0, 1), weight=1, uniform="mod")
        ctk.CTkLabel(card, text="🧭 Módulos", font=t.titulo(16), text_color=t.TEXTO).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for i, (key, ic, nome, desc) in enumerate(MODULOS):
            bloco = ctk.CTkFrame(card, fg_color=t.CARD, corner_radius=12,
                                 border_width=1, border_color=t.CARD_BORDA)
            bloco.grid(row=1 + i // 2, column=i % 2, sticky="nsew",
                       padx=(0 if i % 2 == 0 else 8, 8 if i % 2 == 0 else 0), pady=6)
            topo = ctk.CTkFrame(bloco, fg_color="transparent")
            topo.pack(anchor="w", padx=16, pady=(14, 2), fill="x")
            # Célula de largura travada: o glifo do emoji não empurra o nome
            # (emojis têm métricas diferentes) — mesma razão do NavItem.
            cel = ctk.CTkFrame(topo, fg_color="transparent", width=26, height=26)
            cel.pack(side="left", padx=(0, 8))
            cel.pack_propagate(False)
            ic_lbl = ctk.CTkLabel(cel, text=ic, font=t.corpo(18))
            ic_lbl.place(relx=0.5, rely=0.5, anchor="center")
            nome_lbl = ctk.CTkLabel(topo, text=nome, font=t.corpo(14, "bold"), text_color=t.TEXTO)
            nome_lbl.pack(side="left")
            desc_lbl = ctk.CTkLabel(bloco, text=desc, font=t.corpo(12), text_color=t.TEXTO_FRACO,
                                    justify="left", wraplength=340)
            desc_lbl.pack(anchor="w", padx=16, pady=(0, 14))
            # Clicar em qualquer parte do bloco abre o módulo (item 5).
            self._tornar_clicavel(bloco, key, [bloco, topo, cel, ic_lbl, nome_lbl, desc_lbl])

    def _tornar_clicavel(self, bloco, key: str, widgets):
        """Bloco inteiro clicável → navega para o módulo; hover destaca a borda."""
        def abrir(_e=None):
            if self.ctx.navegar:
                self.ctx.navegar(key)
        for w in widgets:
            w.bind("<Button-1>", abrir)
            try:
                w.configure(cursor="hand2")
            except Exception:  # noqa: BLE001 — nem todo widget aceita cursor
                pass
        bloco.bind("<Enter>", lambda _e: bloco.configure(border_color=t.ACENTO))
        bloco.bind("<Leave>", lambda _e: bloco.configure(border_color=t.CARD_BORDA))

    def _novidades(self, body):
        if not NOVIDADES:
            return
        card = ctk.CTkFrame(body, fg_color=t.CARD, corner_radius=14,
                            border_width=1, border_color=t.CARD_BORDA)
        card.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ctk.CTkLabel(card, text="✨ O que há de novo", font=t.titulo(16),
                     text_color=t.TEXTO).pack(anchor="w", padx=24, pady=(18, 8))
        for it in NOVIDADES:
            ctk.CTkLabel(card, text=f"•  {it}", font=t.corpo(13), text_color=t.TEXTO_FRACO,
                         justify="left", wraplength=760).pack(anchor="w", padx=(30, 24), pady=2)
        ctk.CTkLabel(card, text="", font=t.corpo(6)).pack(pady=(0, 10))

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
