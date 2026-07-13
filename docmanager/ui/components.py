"""Componentes reutilizáveis da UI: cartão, seletor de arquivo, console de log,
barra de execução. Todos com o visual do theme."""
from __future__ import annotations

import os
import threading
from tkinter import filedialog

import customtkinter as ctk

from . import theme as t


class Card(ctk.CTkFrame):
    """Bloco visual com título opcional."""

    def __init__(self, master, titulo: str | None = None, **kw):
        super().__init__(master, fg_color=t.CARD, corner_radius=12, border_width=1,
                         border_color=t.CARD_BORDA, **kw)
        self.grid_columnconfigure(0, weight=1)
        self._linha = 0
        if titulo:
            lbl = ctk.CTkLabel(self, text=titulo, font=t.corpo(13, "bold"), text_color=t.TEXTO_FRACO)
            lbl.grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
            self._linha = 1

    def add(self, widget, **grid):
        grid.setdefault("padx", 16)
        grid.setdefault("pady", 6)
        grid.setdefault("sticky", "ew")
        widget.grid(row=self._linha, column=0, **grid)
        self._linha += 1
        return widget


def _listar_abas(caminho: str) -> list[str]:
    """Nomes das abas do Excel (rápido, sem ler os dados)."""
    try:
        import pandas as pd
        return list(pd.ExcelFile(caminho).sheet_names)
    except Exception:
        return []


_PLACEHOLDER_ABA = "Selecione o arquivo primeiro"


class FileSelector(ctk.CTkFrame):
    """Rótulo + caminho + botão 'Selecionar' + seletor de aba (sempre visível).

    O seletor de aba fica sempre à mostra (como no app antigo): exibe um
    placeholder até um arquivo ser escolhido e então lista as abas reais,
    permitindo trocar a qualquer momento. Expõe `.path` e `.sheet`."""

    def __init__(self, master, label: str, config=None, tipo: str = "arquivo",
                 filetypes=(("Excel", "*.xlsx *.xlsm *.xls"), ("Todos", "*.*")),
                 on_change=None, escolher_aba=True, aba_padrao: str | None = None):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        self.config_mgr = config
        self.tipo = tipo
        self.filetypes = filetypes
        self.on_change = on_change
        self.escolher_aba = escolher_aba
        self.aba_padrao = aba_padrao
        self.path: str | None = None
        self.sheet = 0

        ctk.CTkLabel(self, text=label, width=170, anchor="w", font=t.corpo(12),
                     text_color=t.TEXTO).grid(row=0, column=0, padx=(0, 8), pady=4, sticky="w")
        self.lbl = ctk.CTkLabel(self, text="Nenhum arquivo", anchor="w", font=t.corpo(11),
                                text_color=t.TEXTO_FRACO)
        self.lbl.grid(row=0, column=1, sticky="ew", padx=8)
        ctk.CTkButton(self, text="Selecionar", width=100, font=t.corpo(12),
                      fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._escolher).grid(row=0, column=2, padx=(8, 0), pady=4)

        if self.escolher_aba:
            self._aba_frame = ctk.CTkFrame(self, fg_color="transparent")
            self._aba_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 4))
            ctk.CTkLabel(self._aba_frame, text="Aba (Sheet):", font=t.corpo(11), text_color=t.TEXTO_FRACO,
                         width=170, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 8))
            self.opt_aba = ctk.CTkOptionMenu(self._aba_frame, values=[_PLACEHOLDER_ABA], width=280,
                                             font=t.corpo(11), fg_color=t.SIDEBAR_HOVER,
                                             button_color=t.SIDEBAR_ATIVO, command=self._set_aba)
            self.opt_aba.grid(row=0, column=1, sticky="w")

    def _set_aba(self, nome):
        self.sheet = nome if nome != _PLACEHOLDER_ABA else 0

    def _escolher(self):
        inicial = self.config_mgr.ultimo_dir(self.tipo) if self.config_mgr else None
        caminho = filedialog.askopenfilename(title="Selecionar arquivo", initialdir=inicial,
                                             filetypes=self.filetypes)
        if not caminho:
            return
        self.path = caminho
        self.lbl.configure(text=os.path.basename(caminho), text_color=t.TEXTO)
        if self.config_mgr:
            self.config_mgr.lembrar_dir(self.tipo, caminho)
        if self.escolher_aba:
            abas = _listar_abas(caminho)
            if abas:
                escolhida = self.aba_padrao if (self.aba_padrao and self.aba_padrao in abas) else abas[0]
                self.opt_aba.configure(values=abas)
                self.opt_aba.set(escolhida)
                self.sheet = escolhida
            else:
                self.opt_aba.configure(values=[_PLACEHOLDER_ABA])
                self.opt_aba.set(_PLACEHOLDER_ABA)
                self.sheet = 0
        if self.on_change:
            self.on_change(caminho)


class LogConsole(ctk.CTkTextbox):
    """Console de log thread-safe (use .log() de qualquer thread). Carimba a hora
    de cada linha e faz auto-scroll; `clear()` esvazia."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color="#0B1119", text_color=t.TEXTO_FRACO,
                         font=t.mono(11), corner_radius=8, **kw)
        self.configure(state="disabled")

    def log(self, msg: str):
        from datetime import datetime
        carimbo = datetime.now().strftime("%H:%M:%S")
        self.after(0, self._inserir, carimbo, str(msg))

    def _inserir(self, carimbo: str, msg: str):
        self.configure(state="normal")
        # Preserva linhas em branco iniciais (mensagens que começam com \n).
        prefixo = "\n" * (len(msg) - len(msg.lstrip("\n")))
        self.insert("end", f"{prefixo}[{carimbo}] {msg.lstrip(chr(10))}\n")
        self.see("end")
        self.configure(state="disabled")

    def clear(self):
        self.after(0, self._clear)

    def _clear(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")


class RunBar(ctk.CTkFrame):
    """Botão de ação + barra de progresso. Roda a tarefa numa thread."""

    def __init__(self, master, texto: str, tarefa, log: LogConsole | None = None):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.tarefa = tarefa
        self.log = log
        self.progress = ctk.CTkProgressBar(self, height=10, progress_color=t.ACENTO)
        self.progress.set(0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12), pady=8)
        self.btn = ctk.CTkButton(self, text=texto, width=180, height=40, font=t.corpo(14, "bold"),
                                 fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER, command=self._run)
        self.btn.grid(row=0, column=1, pady=8)

    def set_progress(self, v: float):
        self.after(0, self.progress.set, v)

    def _run(self):
        self.btn.configure(state="disabled", text="Processando...")
        self.progress.set(0)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        try:
            self.tarefa(self)
        except Exception as e:  # noqa: BLE001
            if self.log:
                self.log.log(f"ERRO: {e}")
        finally:
            self.after(0, lambda: self.btn.configure(state="normal", text=self.btn.cget("text")))
            self.set_progress(1.0)
