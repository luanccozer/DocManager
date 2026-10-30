"""Caixas de mensagem e de arquivo - de qualquer thread.

Substituem o `tkinter.messagebox` e o `filedialog`. Cada função roda na thread
da interface (`ponte.na_ui_e_esperar`): uma tarefa em thread pode perguntar
"Salvar como?" e seguir com a resposta, como fazia no Tk.

Os testes trocam estas funções (`monkeypatch.setattr(dialogos, "info", ...)`):
as telas sempre chamam `dialogos.info(...)`, nunca uma referência guardada.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from .idioma import marcar, t
from .ponte import na_ui_e_esperar

FILTRO_EXCEL = "Excel (*.xlsx *.xlsm *.xls);;*.*"
FILTRO_XLSX = "Excel (*.xlsx)"


def _pai(parent):
    return parent if parent is not None else QApplication.activeWindow()


def _caixa(icone, titulo: str, msg: str, parent=None) -> None:
    na_ui_e_esperar(lambda: QMessageBox(icone, titulo, msg, QMessageBox.StandardButton.Ok,
                                        _pai(parent)).exec())


def info(titulo: str, msg: str, parent=None) -> None:
    _caixa(QMessageBox.Icon.Information, titulo, msg, parent)


def aviso(titulo: str, msg: str, parent=None) -> None:
    _caixa(QMessageBox.Icon.Warning, titulo, msg, parent)


def erro(titulo: str, msg: str, parent=None) -> None:
    _caixa(QMessageBox.Icon.Critical, titulo, msg, parent)


def _pergunta(titulo: str, msg: str, botoes, padrao, sim, parent=None) -> bool:
    def _abrir():
        caixa = QMessageBox(QMessageBox.Icon.Question, titulo, msg, botoes, _pai(parent))
        caixa.setDefaultButton(padrao)
        return caixa.exec() == sim
    return bool(na_ui_e_esperar(_abrir))


def perguntar(titulo: str, msg: str, *, padrao_nao: bool = False, parent=None) -> bool:
    """Sim/Não. `padrao_nao=True`: Enter responde "Não" (pergunta arriscada)."""
    b = QMessageBox.StandardButton
    return _pergunta(titulo, msg, b.Yes | b.No, b.No if padrao_nao else b.Yes, b.Yes, parent)


def tentar_de_novo(titulo: str, msg: str, parent=None) -> bool:
    """Tentar de novo / Cancelar (ex.: planilha aberta no Excel ao salvar)."""
    b = QMessageBox.StandardButton
    return _pergunta(titulo, msg, b.Retry | b.Cancel, b.Retry, b.Retry, parent)


# ──────────────────────────────── arquivos ───────────────────────────────────

def escolher_arquivo(config=None, tipo: str = "arquivo", filtro: str = FILTRO_EXCEL,
                     titulo: str = marcar("Selecionar arquivo"), parent=None) -> str:
    """Abre no último diretório do `tipo` e o memoriza. '' se cancelar."""
    inicial = config.ultimo_dir(tipo) if config else ""
    caminho = na_ui_e_esperar(
        lambda: QFileDialog.getOpenFileName(_pai(parent), t(titulo), inicial, filtro)[0])
    if caminho and config:
        config.lembrar_dir(tipo, caminho)
    return caminho or ""


def pedir_salvar(config, tipo: str, nome_inicial: str, filtro: str = FILTRO_XLSX,
                 titulo: str = marcar("Salvar como"), parent=None) -> str:
    """"Salvar como" que abre no ÚLTIMO diretório usado e o memoriza.

    `config` = ConfigManager (ou None). `tipo` = chave de memória (ex.: 'saida').
    Devolve o caminho escolhido, ou '' se a pessoa cancelar. Garante a
    extensão do `nome_inicial` (o diálogo do Windows nem sempre a põe)."""
    inicial = config.ultimo_dir(tipo) if config else ""
    ext = os.path.splitext(nome_inicial)[1] or ".xlsx"
    sugestao = os.path.join(inicial, nome_inicial) if inicial else nome_inicial
    caminho = na_ui_e_esperar(
        lambda: QFileDialog.getSaveFileName(_pai(parent), t(titulo), sugestao, filtro)[0])
    if not caminho:
        return ""
    if not os.path.splitext(caminho)[1]:
        caminho += ext
    if config:
        config.lembrar_dir(tipo, caminho)
    return caminho


def escolher_pasta(config=None, tipo: str = "pasta", titulo: str = marcar("Escolher pasta"),
                   parent=None) -> str:
    inicial = config.ultimo_dir(tipo) if config else ""
    pasta = na_ui_e_esperar(
        lambda: QFileDialog.getExistingDirectory(_pai(parent), t(titulo), inicial))
    if pasta and config:
        # lembrar_dir guarda o DIRNAME do caminho: passa um filho para
        # memorizar a própria pasta escolhida.
        config.lembrar_dir(tipo, os.path.join(pasta, "_"))
    return pasta or ""
