"""Cadastro das credenciais do Aconex — a janela que substituiu o `.env`.

Aparece sozinha quando a pessoa tenta extrair sem ter usuário cadastrado, e
também pelo botão "Cadastrar usuário" (Extração) ou pelas Configurações.

A janela EXPLICA o que é cada campo: quem recebe o app pelo instalador não faz
ideia do que é "Client ID" nem de onde tirar o "User ID", e antes essa
informação só existia num comentário do `.env.example` que ninguém mais recebe.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from ...services.credenciais import cofre
from .. import theme as t

AJUDA = (
    "A Extração Aconex usa a API oficial, que exige uma credencial OAuth pessoal — "
    "a mesma que você usaria no Postman. São três dados, todos fornecidos pelo "
    "administrador do Aconex / pelo portal de integrações da Oracle quando o "
    "aplicativo é registrado para você:\n\n"
    "• Client ID (APP ID) — identifica o aplicativo registrado no seu nome. "
    "Costuma ter a cara de SCP_SEU_NOME_ACONEX_client_APPID.\n"
    "• User ID — o número da sua conta no Aconex (só dígitos, ex.: 1208560183).\n"
    "• Client Secret — a senha do aplicativo. É a única parte sigilosa.\n\n"
    "O Client ID e o User ID não são segredo. O Client Secret é guardado nesta "
    "máquina cifrado pelo Windows (DPAPI), na sua conta de usuário: ele não vai "
    "para o GitHub, não fica na pasta do programa e continua valendo depois de "
    "cada atualização do DocManager."
)


class CadastroCredencialDialog(ctk.CTkToplevel):
    """Modal de cadastro/edição. Depois de `wait_window`, leia `.resultado`
    (nome salvo) — fica `None` se a pessoa cancelar."""

    def __init__(self, master, nome: str | None = None):
        super().__init__(master)
        self.resultado: str | None = None
        self._editando = nome

        self.title("Cadastrar usuário do Aconex" if not nome else f"Editar — {nome}")
        self.configure(fg_color=t.FUNDO)
        self.resizable(False, False)
        self.transient(master)

        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(quadro, text="Credenciais do Aconex", font=t.titulo(18),
                     text_color=t.TEXTO).pack(anchor="w")
        ctk.CTkLabel(quadro, text=AJUDA, font=t.corpo(12), text_color=t.TEXTO_FRACO,
                     justify="left", wraplength=560).pack(anchor="w", pady=(8, 16))

        self._campos: dict[str, ctk.CTkEntry] = {}
        self._campo(quadro, "nome", "Nome (como aparece na lista)", "Ex.: Luan Cozer")
        self._campo(quadro, "client_id", "Client ID (APP ID)", "SCP_SEU_NOME_ACONEX_client_APPID")
        self._campo(quadro, "user_id", "User ID (numérico)", "1208560183")
        self._campo(quadro, "secret", "Client Secret", "cole aqui o segredo", segredo=True)

        # Mostrar/ocultar o segredo: colar um secret às cegas é o erro mais comum.
        self._ver = ctk.CTkCheckBox(quadro, text="Mostrar o Client Secret", font=t.corpo(11),
                                    fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER,
                                    command=self._alternar_segredo)
        self._ver.pack(anchor="w", pady=(2, 14))

        if nome and (cred := cofre().obter(nome)):
            self._campos["nome"].insert(0, cred.nome)
            self._campos["client_id"].insert(0, cred.client_id)
            self._campos["user_id"].insert(0, cred.user_id)
            self._campos["secret"].insert(0, cred.secret)

        botoes = ctk.CTkFrame(quadro, fg_color="transparent")
        botoes.pack(fill="x")
        ctk.CTkButton(botoes, text="Cancelar", width=110, font=t.corpo(12),
                      fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._cancelar).pack(side="right")
        ctk.CTkButton(botoes, text="Salvar", width=130, font=t.corpo(12, "bold"),
                      fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER,
                      command=self._salvar).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._salvar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        self._centralizar(master)
        # grab_set só depois da janela existir de fato, senão o Tk recusa o grab.
        self.after(60, self._tornar_modal)
        self._campos["nome"].focus_set()

    # --- montagem ---
    def _campo(self, pai, chave: str, rotulo: str, placeholder: str, segredo: bool = False):
        ctk.CTkLabel(pai, text=rotulo, font=t.corpo(12), text_color=t.TEXTO).pack(anchor="w")
        entry = ctk.CTkEntry(pai, placeholder_text=placeholder, font=t.corpo(12), width=560,
                             show="*" if segredo else "")
        entry.pack(fill="x", pady=(2, 10))
        self._campos[chave] = entry
        return entry

    def _centralizar(self, master):
        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:  # noqa: BLE001 — posição é cosmética
            pass

    def _tornar_modal(self):
        try:
            self.grab_set()
            self.lift()
        except tk.TclError:
            pass

    def _alternar_segredo(self):
        self._campos["secret"].configure(show="" if self._ver.get() else "*")

    # --- ações ---
    def _valor(self, chave: str) -> str:
        return self._campos[chave].get().strip()

    def _salvar(self):
        try:
            cred = cofre().salvar(self._valor("nome"), self._valor("client_id"),
                                  self._valor("user_id"), self._valor("secret"))
        except ValueError as e:
            messagebox.showwarning("Dados incompletos", str(e), parent=self)
            return
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Erro ao salvar", str(e), parent=self)
            return
        # Renomear = salvar com nome novo; apaga o registro antigo para não duplicar.
        if self._editando and self._editando != cred.nome:
            cofre().remover(self._editando)
        self.resultado = cred.nome
        self._fechar()

    def _cancelar(self):
        self.resultado = None
        self._fechar()

    def _fechar(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def cadastrar(master, nome: str | None = None) -> str | None:
    """Abre o modal e espera. Devolve o nome salvo, ou None se cancelou."""
    dlg = CadastroCredencialDialog(master, nome)
    master.wait_window(dlg)
    return dlg.resultado
