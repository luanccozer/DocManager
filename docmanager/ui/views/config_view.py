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

        # --- Base do atraso CMI na revisão 0A ---
        card2 = Card(body, "Base do atraso CMI na 1ª emissão (revisão 0A)")
        card2.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.base_cmi = ctk.CTkSegmentedButton(
            card2, values=["Reprogramação (quando houver)", "Data prevista (base)"],
            font=t.corpo(12), selected_color=t.ACENTO, selected_hover_color=t.ACENTO_HOVER,
            command=self._set_base_cmi)
        atual = self.ctx.config.settings.base_atraso_cmi_0a
        self.base_cmi.set("Data prevista (base)" if atual == "prevista" else "Reprogramação (quando houver)")
        card2.add(self.base_cmi, pady=(2, 8))
        txt2 = ("Escolhe sobre qual data o atraso do CMI na revisão 0A é contado:\n\n"
                "• Reprogramação (quando houver): usa a data reprogramada do Controle se "
                "existir, senão a data prevista.\n"
                "• Data prevista (base): usa sempre a data prevista original, ignorando a "
                "reprogramação. Afeta o Histórico Consolidado e o Dashboard.")
        card2.add(ctk.CTkLabel(card2, text=txt2, font=t.corpo(12), text_color=t.TEXTO_FRACO,
                               justify="left", wraplength=680), pady=(0, 14))

    def _toggle(self):
        ligado = bool(self.switch.get())
        self.ctx.config.set_setting("regra_estrita_vip", ligado)

    def _set_base_cmi(self, valor):
        base = "prevista" if valor.startswith("Data prevista") else "reprogramacao"
        self.ctx.config.set_setting("base_atraso_cmi_0a", base)
