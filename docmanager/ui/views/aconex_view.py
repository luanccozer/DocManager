from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, RunBar, pedir_salvar
from .base import BaseView


class AconexView(BaseView):
    titulo_view = "Extração Aconex (API)"
    subtitulo_view = "Baixa o histórico completo do projeto direto da API do Aconex"

    def montar(self, body):
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import OUTRO_USUARIO, usuarios_disponiveis
        self._OUTRO = OUTRO_USUARIO

        card = Card(body, "Credenciais")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        # Usuários = os que TÊM secret no .env (dinâmico) + a opção manual.
        disponiveis = usuarios_disponiveis()
        valores = disponiveis + [OUTRO_USUARIO]
        linha = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(linha, text="Usuário", width=170, anchor="w", font=t.corpo(12),
                     text_color=t.TEXTO).grid(row=0, column=0, sticky="w")
        self.opt_user = ctk.CTkOptionMenu(linha, values=valores, command=self._on_user,
                                          fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO,
                                          font=t.corpo(12))
        self.opt_user.set(disponiveis[0] if disponiveis else OUTRO_USUARIO)
        self.opt_user.grid(row=0, column=1, sticky="w")
        linha.grid_columnconfigure(1, weight=1)
        card.add(linha)

        # Entrada manual (visível só quando "Outro" é escolhido) — não é salva.
        self._manual = ctk.CTkFrame(card, fg_color="transparent")
        self.entry_client = ctk.CTkEntry(self._manual, placeholder_text="Client ID (APP ID) do Aconex",
                                         font=t.corpo(12))
        self.entry_userid = ctk.CTkEntry(self._manual, placeholder_text="User ID (numérico) do Aconex",
                                         font=t.corpo(12))
        self.entry_secret = ctk.CTkEntry(self._manual, placeholder_text="Client Secret", show="*",
                                         font=t.corpo(12))
        for w in (self.entry_client, self.entry_userid, self.entry_secret):
            w.pack(fill="x", pady=3)
        card.add(self._manual)

        self.entry_proxy = ctk.CTkEntry(card, placeholder_text="Proxy (opcional) — vazio detecta automático",
                                        font=t.corpo(12))
        card.add(self.entry_proxy)
        self._dica = ctk.CTkLabel(card, text="", font=t.corpo(11), text_color=t.TEXTO_FRACO, anchor="w")
        self._dica.grid(row=card._linha, column=0, sticky="w", padx=16, pady=(0, 12))

        self.run = RunBar(body, "Iniciar Extração", self._tarefa, self.log)
        self.run.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        self._on_user(self.opt_user.get())   # define visibilidade/dica iniciais

    def _on_user(self, escolha: str):
        """Mostra os campos manuais só na opção 'Outro'; ajusta a dica."""
        if escolha == self._OUTRO:
            self._manual.grid()
            self._dica.configure(text="Entrada manual: informe os 3 dados do usuário do Aconex. "
                                      "Valem só para esta extração (não são salvos).")
        else:
            self._manual.grid_remove()
            self._dica.configure(text="O Client Secret é lido do arquivo .env (SECRET_<USUÁRIO>).")

    def _montar_config(self):
        """Monta a AconexConfig conforme a escolha (conhecido ou manual)."""
        from ...aconex_backend import AconexConfig
        proxy = self.entry_proxy.get().strip() or None
        escolha = self.opt_user.get()
        if escolha == self._OUTRO:
            client_id = self.entry_client.get().strip()
            user_id = self.entry_userid.get().strip()
            secret = self.entry_secret.get().strip()
            if not (client_id and user_id and secret):
                raise ValueError("Preencha Client ID, User ID e Secret para o usuário manual.")
            return AconexConfig(client_id=client_id, client_secret=secret, user_id=user_id, proxy=proxy)
        return AconexConfig.para_usuario(escolha, proxy=proxy)

    def _tarefa(self, run: RunBar):
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import extrair_base, nome_arquivo_padrao, salvar_excel
        try:
            config = self._montar_config()
        except (KeyError, ValueError) as e:
            self.log.log(f"ERRO: {e}")
            return
        run.set_progress(0.1)
        self.log.log("Extração iniciada (pode levar vários minutos)...")
        df = extrair_base(config, log_cb=self.log.log)
        if df.empty:
            self.log.log("Nenhum dado retornado.")
            return
        saida = pedir_salvar(self.ctx.config, "saida", nome_arquivo_padrao())
        if not saida:
            self.log.log("Salvamento cancelado (dados perdidos da memória).")
            return
        salvar_excel(df, saida)
        run.set_progress(1.0)
        self.log.log(f"Concluído: {len(df)} linhas salvas.")
        self.after(0, lambda: messagebox.showinfo("Extração Aconex", f"{len(df)} linhas extraídas."))
