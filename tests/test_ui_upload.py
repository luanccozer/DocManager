# ruff: noqa: F811 - as fixtures app e caixas vêm de test_ui_telas
"""O módulo Upload de documentos na interface (Fase 1: ensaio + Capturar telas)."""
from __future__ import annotations

import pytest

from test_ui_telas import app, caixas  # noqa: F401 - fixtures

from docmanager import aconex_backend as ab
from docmanager.services import navegador
from docmanager.services import upload_aprovacao as ua


def _tela(app):
    app.selecionar("upload")
    return app._views["upload"]


@pytest.fixture
def preparar(monkeypatch):
    chamadas = []

    def falso(config, envio, controle, codigo, prazo, **kw):
        chamadas.append((config, envio, controle, codigo, prazo, kw))
        return ua.Preparacao(True, "ok", codigo=codigo, prazo_dias=prazo,
                             documento={"No. do Documento": "#XX00=EXEMPLO", "Revisão": "0C"})

    monkeypatch.setattr(ua, "preparar_aprovacao", falso)
    monkeypatch.setattr(ab, "usuarios_disponiveis", lambda: ["FULANO"])
    monkeypatch.setattr(ab.AconexConfig, "para_usuario", classmethod(lambda cls, n, **_k: f"config {n}"))
    return chamadas


def test_tres_opcoes_e_aprovacao_aberta(app):
    tela = _tela(app)
    assert tela.tabs.get() == "Para aprovação"
    assert tela.tabs._nomes == ["Documento novo", "Para revisão", "Para aprovação"]


def test_iniciar_pede_o_codigo_e_mostra_o_ensaio(app, qtbot, preparar, caixas, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: (" 0000CMI-AA01-01 ", True))
    tela = _tela(app)
    tela.sel_envio.definir(str(tmp_path / "envio.docx"))
    tela.sel_controle.path = str(tmp_path / "controle.xlsx")
    tela.prazo.setValue(7)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()
    assert len(preparar) == 1
    config, _envio, _ctrl, codigo, prazo, kw = preparar[0]
    assert (config, codigo, prazo) == ("config FULANO", "0000CMI-AA01-01", 7)
    assert kw["perguntar_cb"] is not None
    assert [c[0] for c in caixas] == ["info"] and "nada foi enviado" in caixas[0][2]


def test_sem_arquivos_ou_sem_codigo_nao_busca(app, qtbot, preparar, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QInputDialog

    tela = _tela(app)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()
    assert "Escolha o arquivo de envio" in tela.log.texto()
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    tela.sel_envio.path = str(tmp_path / "e.docx")
    tela.sel_controle.path = str(tmp_path / "c.xlsx")
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()
    assert preparar == []


def test_capturar_telas_avisa_onde_ficou_o_zip(app, qtbot, caixas, monkeypatch, tmp_path):
    arquivo = tmp_path / "capturas.zip"
    monkeypatch.setattr(navegador, "capturar_telas", lambda **_k: arquivo)
    tela = _tela(app)
    with qtbot.waitSignal(tela.run_captura.terminou, timeout=10000):
        tela.run_captura.btn.click()
    assert caixas and caixas[0][0] == "info" and str(arquivo) in caixas[0][2]


def test_capturar_sem_chrome_explica(app, qtbot, caixas, monkeypatch):
    def sem_chrome(**_k):
        raise navegador.ErroNavegador("O Google Chrome não foi encontrado neste computador.")

    monkeypatch.setattr(navegador, "capturar_telas", sem_chrome)
    tela = _tela(app)
    with qtbot.waitSignal(tela.run_captura.terminou, timeout=10000):
        tela.run_captura.btn.click()
    assert caixas == [("aviso", "Capturar telas", "O Google Chrome não foi encontrado neste computador.")]
