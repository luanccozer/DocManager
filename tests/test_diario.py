"""O diário diz como a sessão anterior terminou (ideia do Corella Suite)."""
import sys
import threading

import pytest

from docmanager.services import diario


@pytest.fixture(autouse=True)
def sem_faulthandler(monkeypatch):
    """O faulthandler é do processo inteiro (o pytest também usa): fica de fora."""
    monkeypatch.setattr(diario.faulthandler, "enable", lambda *a, **k: None)


def test_sessao_fechada_pela_janela(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    assert diario.iniciar("1.0") is None          # primeira sessão: nada antes
    diario.encerrar()
    assert diario.iniciar("1.0") is True           # a anterior fechou pela janela


def test_sessao_que_caiu_ou_foi_morta(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    diario.iniciar("1.0")                          # e não encerrou
    assert diario.iniciar("1.0") is False


def test_excecao_fica_registrada(monkeypatch):
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    monkeypatch.setattr(sys, "__excepthook__", None)
    diario.iniciar("1.0")
    try:
        raise ValueError("defeito de teste")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    texto = diario.caminho().read_text(encoding="utf-8")
    assert "EXCECAO" in texto and "defeito de teste" in texto


def test_diario_grande_gira():
    arq = diario.caminho()
    arq.write_text("x" * (diario.LIMITE_BYTES + 10), encoding="utf-8")
    diario._girar(arq)
    assert arq.with_name("diario.1.log").exists()
    assert not arq.exists()
