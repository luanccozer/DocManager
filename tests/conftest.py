"""Isolamento dos dados do usuário durante os testes.

Config e credenciais moram em `Documentos\\DocManager_Itaipu`. Sem isolar, a
suíte leria (e escreveria!) o cofre real de quem está rodando os testes - e o
resultado mudaria de máquina para máquina. `DOCMANAGER_DADOS_DIR` redireciona a
pasta inteira para um diretório temporário por teste.
"""
import gc
import os

import pytest

# Telas Qt sem monitor (CI do Linux, Release do Windows): o pytest-qt cria o
# QApplication com esta plataforma, que desenha em memória.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from docmanager.services import credenciais


@pytest.fixture(autouse=True)
def dados_isolados(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANAGER_DADOS_DIR", str(tmp_path / "dados"))
    # O cofre é um singleton em memória: zera para o teste pegar a pasta nova.
    monkeypatch.setattr(credenciais, "_cofre", None, raising=False)
    yield
    credenciais._cofre = None


@pytest.fixture(autouse=True)
def lixo_do_qt_coletado_na_thread_da_interface(request):
    """Teste de tela coleta o próprio lixo ao terminar, nesta thread. Deixado para
    depois, o coletor podia rodar na thread de trabalho de outro teste e destruir um
    objeto do Qt fora da thread da interface, e o Qt derruba o processo (falha de
    segmentação no CI, 2026-10-29)."""
    yield
    if "qtbot" in request.fixturenames:
        gc.collect()


@pytest.fixture(autouse=True)
def interface_em_portugues(request, monkeypatch):
    """Os testes conferem os textos em português, a língua de origem. Sem isto, a
    tela seguiria o idioma do Windows de quem roda - e o runner do Release, em
    inglês, reprovava os testes de tela (3.6.5-rc.1)."""
    from docmanager.ui import idioma

    idioma.definir("pt")
    if "qtbot" in request.fixturenames:
        monkeypatch.setattr("docmanager.ui.main_app._idiomas_do_windows", lambda: ["pt-BR"])
    yield
    idioma.definir("pt")


@pytest.fixture(autouse=True)
def telas_com_senha_liberadas(request, monkeypatch):
    """Testes de tela não param na senha do Upload (ela abriria uma janela modal e
    travaria a suíte). Os testes do candado (`tests/test_ui_senha.py`) usam a de verdade."""
    if "qtbot" in request.fixturenames and "senha_de_verdade" not in request.fixturenames:
        monkeypatch.setattr("docmanager.ui.main_app.MainApp._senha_confirmada", lambda self, spec: True)
    yield
