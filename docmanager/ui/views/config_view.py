from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from ... import __version__
from ...services import updater
from ...services.credenciais import cofre
from .. import theme as t
from ..components import Card
from .base import BaseView


class ConfigView(BaseView):
    titulo_view = "Configurações"
    subtitulo_view = "Ajustes que valem para todos os módulos"

    def montar(self, body):
        self._credenciais(body, linha=0)
        self._atualizacoes(body, linha=1)
        self._regra_vip(body, linha=2)
        self._base_atraso(body, linha=3)

    # ─────────────────────────── credenciais do Aconex ──────────────────────
    def _credenciais(self, body, linha: int):
        """Lista dos usuários cadastrados - o que substituiu editar o `.env`."""
        card = Card(body, "Credenciais do Aconex")
        card.grid(row=linha, column=0, sticky="ew", pady=(0, 16))

        card.add(ctk.CTkLabel(
            card, text="Cada pessoa usa a própria credencial do Aconex: Client ID, User ID "
                       "e Client Secret. O segredo fica só nesta máquina, cifrado pelo "
                       "Windows na sua conta de usuário. Ele não vai para o GitHub e "
                       "continua valendo depois das atualizações.",
            font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=680),
            pady=(0, 8))

        self._lista_cred = ctk.CTkLabel(card, text="", font=t.corpo(12), text_color=t.TEXTO,
                                        justify="left", anchor="w", wraplength=680)
        card.add(self._lista_cred, pady=(0, 8))

        botoes = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkButton(botoes, text="Cadastrar novo", width=150, font=t.corpo(12),
                      fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER,
                      command=lambda: self._cadastrar(None)).pack(side="left")
        self._opt_cred = ctk.CTkOptionMenu(botoes, values=["(nenhum)"], width=200, font=t.corpo(12),
                                           fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self._opt_cred.pack(side="left", padx=8)
        ctk.CTkButton(botoes, text="Editar", width=90, font=t.corpo(12),
                      fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._editar).pack(side="left")
        ctk.CTkButton(botoes, text="Remover", width=90, font=t.corpo(12),
                      fg_color=t.PERIGO, hover_color=t.PERIGO_HOVER,
                      command=self._remover).pack(side="left", padx=8)
        card.add(botoes, pady=(0, 14))
        self._atualizar_lista_cred()

    def _atualizar_lista_cred(self):
        nomes = cofre().listar()
        self._lista_cred.configure(
            text=("Cadastrados: " + ", ".join(nomes)) if nomes
            else "Nenhum usuário cadastrado. A Extração Aconex só funciona depois "
                 "que você cadastrar um.")
        self._opt_cred.configure(values=nomes or ["(nenhum)"])
        self._opt_cred.set(nomes[0] if nomes else "(nenhum)")

    def _cadastrar(self, nome: str | None):
        from .credenciais_dialog import cadastrar

        if (salvo := cadastrar(self.winfo_toplevel(), nome)):
            self._atualizar_lista_cred()
            self.log.log(f"Credenciais de '{salvo}' salvas nesta máquina.")

    def _editar(self):
        nome = self._opt_cred.get()
        if nome and nome != "(nenhum)":
            self._cadastrar(nome)

    def _remover(self):
        nome = self._opt_cred.get()
        if not nome or nome == "(nenhum)":
            return
        if not messagebox.askyesno(
                "Remover credencial",
                f"Apagar as credenciais de '{nome}' desta máquina?\n\n"
                "O usuário some da lista da Extração Aconex. No Aconex nada muda."):
            return
        cofre().remover(nome)
        self._atualizar_lista_cred()
        self.log.log(f"Credenciais de '{nome}' removidas.")

    # ───────────────────────────── atualizações ─────────────────────────────
    def _atualizacoes(self, body, linha: int):
        card = Card(body, "Atualizações do DocManager")
        card.grid(row=linha, column=0, sticky="ew", pady=(0, 16))

        self._lbl_versao = ctk.CTkLabel(card, text="", font=t.corpo(13), text_color=t.TEXTO,
                                        anchor="w", justify="left", wraplength=680)
        card.add(self._lbl_versao, pady=(0, 6))
        self._descrever_versao()

        self._sw_auto = ctk.CTkSwitch(
            card, text="  Avisar automaticamente quando sair uma versão nova",
            font=t.corpo(13), progress_color=t.ACENTO, command=self._toggle_auto)
        if self.ctx.config.settings.verificar_atualizacoes:
            self._sw_auto.select()
        card.add(self._sw_auto, pady=(2, 8))

        botoes = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkButton(botoes, text="Procurar atualizações agora", width=220, font=t.corpo(12),
                      fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER,
                      command=self._procurar).pack(side="left")
        card.add(botoes, pady=(0, 6))

        card.add(ctk.CTkLabel(
            card, text="A verificação roda em segundo plano quando o app abre, no máximo uma "
                       "vez a cada 6 horas, e funciona com o Zscaler e a VPN ligados. Suas "
                       "configurações e credenciais ficam fora da pasta do programa, então "
                       "a atualização não apaga nada.",
            font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=680),
            pady=(0, 14))

        # Se a checagem automática já achou algo (ou achar depois), reflete aqui.
        self.ctx.ao_achar_atualizacao(
            lambda _info: self.after(0, self._descrever_versao))

    def _descrever_versao(self):
        info = self.ctx.atualizacao
        if info is not None:
            texto = (f"Versão instalada: v{__version__}   ·   "
                     f"✨ disponível: v{info.versao}. Clique em 'Procurar atualizações "
                     f"agora' para instalar.")
        elif not updater.token():
            texto = (f"Versão instalada: v{__version__}   ·   este build não tem "
                     f"atualização automática (foi gerado localmente).")
        else:
            texto = f"Versão instalada: v{__version__}"
        self._lbl_versao.configure(text=texto)

    def _toggle_auto(self):
        ligado = bool(self._sw_auto.get())
        self.ctx.config.set_setting("verificar_atualizacoes", ligado)
        if ligado:
            # Voltar a ligar limpa a versão pulada: quem religa quer ser avisado.
            self.ctx.config.set_setting("versao_ignorada", "")
        self.log.log(f"Aviso automático de atualização {'ligado' if ligado else 'desligado'}.")

    def _procurar(self):
        self.log.log("Procurando atualizações...")
        if self.ctx.verificar_atualizacao:
            self.ctx.verificar_atualizacao(True)

    # ─────────────────────────── regras de negócio ──────────────────────────
    def _regra_vip(self, body, linha: int):
        card = Card(body, "Regra estrita das Planilhas VIP (pente fino)")
        card.grid(row=linha, column=0, sticky="ew", pady=(0, 16))

        self.switch = ctk.CTkSwitch(
            card, text="  Ativar rebaixamento estrito (APROVAÇÃO INTERMEDIÁRIA)",
            font=t.corpo(13), progress_color=t.ACENTO, command=self._toggle)
        if self.ctx.config.settings.regra_estrita_vip:
            self.switch.select()
        card.add(self.switch, pady=(2, 8))

        txt = ("Desligado (padrão): fluxo normal - planilhas de comissionamento e seus "
               "documentos são consolidados sem aprovação intermediária.\n\n"
               "Ligado: documentos de nível 4 sob planilhas VIP só contam como APROVADO "
               "quando o status real é 'Aprovado' seco; aprovações parciais viram "
               "APROVAÇÃO INTERMEDIÁRIA. Afeta o Mapa (consolidado + resumo do nível 3) "
               "e o Delta. A exceção do 'Para Aprovação' em planilhas de comissionamento "
               "permanece sempre ativa.")
        card.add(ctk.CTkLabel(card, text=txt, font=t.corpo(12), text_color=t.TEXTO_FRACO,
                              justify="left", wraplength=680), pady=(0, 14))

    def _base_atraso(self, body, linha: int):
        card2 = Card(body, "Base do atraso CMI na 1ª emissão (revisão 0A)")
        card2.grid(row=linha, column=0, sticky="ew", pady=(0, 16))
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
