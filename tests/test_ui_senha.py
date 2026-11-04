# ruff: noqa: F811 - as fixtures app e caixas vêm de test_ui_telas
"""O candado do Upload de documentos: senha uma vez por sessão (pedido de 2026-11-04)."""
from __future__ import annotations

import pytest

from test_ui_telas import app, caixas  # noqa: F401 - fixtures

from docmanager.core import acesso


@pytest.fixture
def senha_de_verdade():
    """Marca o teste: o conftest deixa a senha de verdade (sem liberar sozinho)."""


@pytest.fixture
def digitar(monkeypatch):
    """O que a pessoa digita na janela da senha (None = Cancelar); conta as perguntas."""
    from PySide6.QtWidgets import QInputDialog

    estado = {"respostas": [], "perguntas": 0}

    def get_text(*_a, **_k):
        estado["perguntas"] += 1
        r = estado["respostas"].pop(0)
        return ("", False) if r is None else (r, True)

    monkeypatch.setattr(QInputDialog, "getText", get_text)
    return estado


def test_a_senha_confere_e_o_texto_dela_nao_esta_no_codigo():
    from pathlib import Path

    assert acesso.confere("cmi1234")
    assert not acesso.confere("CMI1234") and not acesso.confere("") and not acesso.confere(None)
    assert "cmi1234" not in Path(acesso.__file__).read_text(encoding="utf-8")


def test_senha_certa_abre_e_nao_pergunta_de_novo(app, senha_de_verdade, digitar):
    digitar["respostas"] = ["cmi1234"]
    app.selecionar("upload")
    assert app._key_ativa == "upload"
    app.selecionar("home")
    app.selecionar("upload")
    assert app._key_ativa == "upload" and digitar["perguntas"] == 1


def test_senha_errada_avisa_e_fica_na_tela_de_antes(app, senha_de_verdade, digitar, caixas):
    app.selecionar("pendencias")
    digitar["respostas"] = ["errada"]
    app.selecionar("upload")
    assert app._key_ativa == "pendencias" and "upload" not in app._views
    assert caixas == [("aviso", "Acesso restrito", "Senha incorreta.")]


def test_cancelar_nao_abre_nem_avisa(app, senha_de_verdade, digitar, caixas):
    digitar["respostas"] = [None]
    app.selecionar("upload")
    assert app._key_ativa != "upload" and caixas == []


def test_o_cartao_do_inicio_tambem_pede_a_senha(app, senha_de_verdade, digitar):
    from PySide6.QtWidgets import QLabel

    from docmanager.ui.views.home_view import _BlocoModulo

    digitar["respostas"] = ["errada", "cmi1234"]
    app.selecionar("home")
    bloco = next(b for b in app._views["home"].findChildren(_BlocoModulo)
                 if any(lbl.text() == "Upload de documentos" for lbl in b.findChildren(QLabel)))
    bloco._ao_abrir()
    assert app._key_ativa == "home"
    bloco._ao_abrir()
    assert app._key_ativa == "upload"
