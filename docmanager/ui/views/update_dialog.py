"""Janela "há uma nova versão" - aviso, download com progresso e instalação.

O download roda numa thread separada; todo toque na interface volta para a
thread do Tk via `self.after`, porque widgets do Tkinter só podem ser mexidos
pela thread que criou a janela (mexer de fora trava ou derruba o app).

Os textos vêm de `ui/atualizacao_textos.py`; a rede, de `services/updater.py`.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from ...services import updater
from .. import atualizacao_textos as txt
from .. import theme as t


class AtualizacaoDialog(ctk.CTkToplevel):
    """Modal do aviso de atualização.

    `fechar_app` é chamada quando o instalador está pronto: o Windows não deixa
    sobrescrever um `.exe` em execução, então o DocManager precisa sair de cena.
    `tarefa_em_andamento()` diz se há um processamento rodando - se houver, a
    janela pergunta antes de fechar o app.
    """

    def __init__(self, master, info: updater.Atualizacao, versao_atual: str,
                 *, fechar_app=None, ao_pular=None, tarefa_em_andamento=None):
        super().__init__(master)
        self.info = info
        self._fechar_app = fechar_app
        self._ao_pular = ao_pular
        self._tarefa_em_andamento = tarefa_em_andamento or (lambda: False)
        self._baixando = False

        self.title("Atualização disponível")
        self.configure(fg_color=t.FUNDO)
        self.resizable(False, False)
        self.transient(master)

        quadro = ctk.CTkFrame(self, fg_color="transparent")
        quadro.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(quadro, text="✨ " + txt.titulo(info), font=t.titulo(18),
                     text_color=t.TEXTO).pack(anchor="w")
        self.lbl_resumo = ctk.CTkLabel(quadro, text=txt.resumo(info, versao_atual),
                                       font=t.corpo(12), text_color=t.TEXTO_FRACO,
                                       justify="left", wraplength=560)
        self.lbl_resumo.pack(anchor="w", pady=(4, 12))

        notas = ctk.CTkTextbox(quadro, width=560, height=200, font=t.corpo(12),
                               fg_color=t.CARD, border_width=1, border_color=t.CARD_BORDA)
        notas.pack(fill="both", expand=True)
        notas.insert("1.0", info.notas or "(esta versão não trouxe notas)")
        notas.configure(state="disabled")

        ctk.CTkLabel(quadro, text=txt.TEXTO_REABRE, font=t.corpo(11),
                     text_color=t.TEXTO_FRACO, justify="left",
                     wraplength=560).pack(anchor="w", pady=(10, 0))
        if updater.precisa_elevacao():
            ctk.CTkLabel(quadro, text="ℹ️ " + txt.TEXTO_UAC,
                         font=t.corpo(11), text_color=t.TEXTO_FRACO, justify="left",
                         wraplength=560).pack(anchor="w", pady=(6, 0))

        self.barra = ctk.CTkProgressBar(quadro, progress_color=t.ACENTO)
        self.barra.set(0)
        self.status = ctk.CTkLabel(quadro, text="", font=t.corpo(11), text_color=t.TEXTO_FRACO,
                                   justify="left", wraplength=560)

        botoes = ctk.CTkFrame(quadro, fg_color="transparent")
        botoes.pack(fill="x", pady=(14, 0))
        self.btn_depois = ctk.CTkButton(botoes, text="Agora não", width=110, font=t.corpo(12),
                                        fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                                        command=self._fechar)
        self.btn_depois.pack(side="right")
        self.btn_atualizar = ctk.CTkButton(botoes, text="Atualizar agora", width=150,
                                           font=t.corpo(12, "bold"), fg_color=t.ACENTO,
                                           hover_color=t.ACENTO_HOVER, command=self._atualizar)
        self.btn_atualizar.pack(side="right", padx=(0, 8))
        self.btn_pular = ctk.CTkButton(botoes, text=f"Pular a v{info.versao}", width=130,
                                       font=t.corpo(11), fg_color="transparent",
                                       hover_color=t.SIDEBAR_HOVER, text_color=t.TEXTO_FRACO,
                                       command=self._pular)
        self.btn_pular.pack(side="left")

        # "X" e Esc fecham - menos durante o download (ver `_fechar`).
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.bind("<Escape>", lambda _e: self._fechar())
        self._centralizar(master)
        self.after(60, self._tornar_modal)

    # --- montagem ---
    def _centralizar(self, master):
        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:  # noqa: BLE001
            pass

    def _tornar_modal(self):
        try:
            self.grab_set()
            self.lift()
        except tk.TclError:
            pass

    def trazer_para_frente(self):
        """A checagem da abertura e o botão manual responderam juntos: em vez de
        um segundo aviso, este volta para a frente."""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    # --- ações ---
    def _dizer(self, msg: str):
        """Escreve no rótulo de status - seguro para chamar de outra thread."""
        self.after(0, lambda: self.status.configure(text=msg))

    def _progresso(self, fracao: float):
        self.after(0, lambda: self.barra.set(fracao))

    def _atualizar(self):
        if self._baixando:
            return
        if self._tarefa_em_andamento() and not messagebox.askyesno(
                "Tarefa em andamento", txt.PERGUNTA_TAREFA, default="no", parent=self):
            return
        self._baixando = True
        self.btn_atualizar.configure(state="disabled", text="Baixando...")
        self.btn_pular.configure(state="disabled")
        self.btn_depois.configure(state="disabled")
        self.barra.set(0)
        self.barra.pack(fill="x", pady=(12, 4))
        self.status.pack(anchor="w")
        self._dizer("Baixando o instalador...")
        threading.Thread(target=self._trabalho, daemon=True).start()

    def _caiu_no_completo(self, completo, _erro):
        self.after(0, lambda: self.lbl_resumo.configure(text=txt.caiu_no_completo(completo)))

    def _trabalho(self):
        """Roda FORA da thread da interface: baixa, confere e dispara o instalador.

        `instalar` só volta quando o instalador está pronto (já passou pela
        permissão do Windows, se ela foi pedida). Se ele não ficar pronto, cai no
        `_falhou` e o app segue aberto - fechar antes era o que abortava a
        atualização na v3.1.0."""
        try:
            caminho = updater.baixar(self.info, progresso_cb=self._progresso,
                                     log_cb=self._dizer,
                                     ao_cair_no_completo=self._caiu_no_completo)
            self._dizer(txt.TEXTO_CONFERIDO)
            updater.instalar(caminho, log_cb=self._dizer)
        except Exception as e:  # noqa: BLE001 - qualquer falha vira aviso na tela
            self.after(0, lambda erro=e: self._falhou(erro))
            return
        # O instalador espera o app sair; a pausa é só para dar tempo de ler.
        self.after(1500, self._encerrar_para_instalar)

    def _falhou(self, erro: Exception):
        self._baixando = False
        self.barra.pack_forget()
        self.btn_atualizar.configure(state="normal", text="Tentar de novo")
        self.btn_pular.configure(state="normal")
        self.btn_depois.configure(state="normal")
        self._dizer("")
        messagebox.showerror(
            "Não foi possível atualizar",
            f"{erro}\n\nVocê pode seguir usando esta versão normalmente. Para baixar a "
            f"nova à mão:\n{self.info.url_pagina}", parent=self)

    def _encerrar_para_instalar(self):
        self._dizer("O DocManager vai fechar e abrir de novo, já atualizado.")
        try:
            self.grab_release()
        except tk.TclError:
            pass
        if self._fechar_app:
            self._fechar_app()
        else:
            self.destroy()

    def _pular(self):
        if self._ao_pular:
            self._ao_pular(self.info.versao)
        self._fechar()

    def _fechar(self):
        if self._baixando:
            return   # não some no meio do download
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
