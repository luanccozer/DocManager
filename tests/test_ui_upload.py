# ruff: noqa: F811 - as fixtures app e caixas vêm de test_ui_telas
"""O módulo Upload de documentos na interface (Fase 1: ensaio + Capturar telas)."""
from __future__ import annotations

import pytest

from test_ui_telas import app, caixas  # noqa: F401 - fixtures

from docmanager import aconex_backend as ab
from docmanager.services import controle_docs, navegador
from docmanager.services import upload_aprovacao as ua
from test_upload_envio import CABECALHO, LINHA_1, LINHA_2


def _tela(app):
    app.selecionar("upload")
    return app._views["upload"]


@pytest.fixture
def preparar(monkeypatch):
    chamadas = []

    def falso(config, linha, controle, prazo, **kw):
        chamadas.append((config, linha, controle, prazo, kw))
        if linha.cod_cmi.endswith("-03"):
            return ua.Preparacao(False, "não está em 0C. Documento pulado.", codigo=linha.cod_cmi)
        return ua.Preparacao(True, "ok", codigo=linha.cod_cmi, prazo_dias=prazo, envio=linha,
                             documento={"No. do Documento": "#XX00=EXEMPLO", "Revisão": "0C"})

    monkeypatch.setattr(ua, "preparar_aprovacao", falso)
    monkeypatch.setattr(controle_docs, "ler_controle", lambda *a, **k: "controle lido")
    monkeypatch.setattr(ab, "usuarios_disponiveis", lambda: ["FULANO"])
    monkeypatch.setattr(ab.AconexConfig, "para_usuario", classmethod(lambda cls, n, **_k: f"config {n}"))
    return chamadas


def test_tres_opcoes_e_aprovacao_aberta(app):
    tela = _tela(app)
    assert tela.tabs.get() == "Para aprovação"
    assert tela.tabs._nomes == ["Documento novo", "Para revisão", "Para aprovação"]


def test_tabela_colada_mostra_quantos_documentos(app):
    tela = _tela(app)
    tela.tabela.setPlainText(f"{CABECALHO}\n{LINHA_1}\n\n{LINHA_2}\n")
    assert "2 documento(s)" in tela.lbl_reconhecidos.text()
    assert "0000CMI-AA01-04, 0000CMI-AA01-03" in tela.lbl_reconhecidos.text()


def test_iniciar_faz_um_documento_de_cada_vez(app, qtbot, preparar, caixas, tmp_path):
    tela = _tela(app)
    tela.tabela.setPlainText(f"{CABECALHO}\n{LINHA_1}\n\n{LINHA_2}\n")
    tela.sel_controle.path = str(tmp_path / "controle.xlsx")
    tela.prazo.setValue(7)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()
    assert [c[1].cod_cmi for c in preparar] == ["0000CMI-AA01-04", "0000CMI-AA01-03"]   # na ordem
    config, _linha, controle, prazo, kw = preparar[0]
    assert (config, controle, prazo) == ("config FULANO", "controle lido", 7)
    assert kw["perguntar_cb"] is not None
    assert caixas[0][0] == "info"
    texto = caixas[0][2]
    assert "1 de 2" in texto and "Documento pulado" in texto and "nada foi enviado" in texto
    assert "Documento 2 de 2" in tela.log.texto()


def test_sem_tabela_ou_sem_controle_nao_busca(app, qtbot, preparar, tmp_path):
    tela = _tela(app)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()
    assert "Cole a tabela" in tela.log.texto()
    tela.tabela.setPlainText(LINHA_1)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()
    assert "Escolha o Controle" in tela.log.texto()
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
