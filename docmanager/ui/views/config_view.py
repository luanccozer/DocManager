from __future__ import annotations

import customtkinter as ctk

from .. import theme as t
from ..components import Card
from .base import BaseView


class ConfigView(BaseView):
    titulo_view = "Configurações"
    subtitulo_view = "Ajustes que valem para todos os módulos"

    def montar(self, body):
        card = Card(body, "Regra estrita das Planilhas VIP (pente fino)")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        self.switch = ctk.CTkSwitch(
            card, text="  Ativar rebaixamento estrito (APROVAÇÃO INTERMEDIÁRIA)",
            font=t.corpo(13), progress_color=t.ACENTO, command=self._toggle)
        if self.ctx.config.settings.regra_estrita_vip:
            self.switch.select()
        card.add(self.switch, pady=(2, 8))

        txt = ("Desligado (padrão): fluxo normal — planilhas de comissionamento e seus "
               "documentos são consolidados sem aprovação intermediária.\n\n"
               "Ligado: documentos de nível 4 sob planilhas VIP só contam como APROVADO "
               "quando o status real é 'Aprovado' seco; aprovações parciais viram "
               "APROVAÇÃO INTERMEDIÁRIA. Afeta o Mapa (consolidado + resumo do nível 3) "
               "e o Delta. A exceção do 'Para Aprovação' em planilhas de comissionamento "
               "permanece sempre ativa.")
        lbl = ctk.CTkLabel(card, text=txt, font=t.corpo(12), text_color=t.TEXTO_FRACO,
                           justify="left", wraplength=680)
        card.add(lbl, pady=(0, 14))

    def _toggle(self):
        ligado = bool(self.switch.get())
        self.ctx.config.set_setting("regra_estrita_vip", ligado)
