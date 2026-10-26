"""Ponte entre as threads de trabalho e a thread da interface.

No Qt, widget só pode ser mexido pela thread que criou a janela - e caixa de
diálogo só pode ABRIR nela. As tarefas longas (extração, atualização do
mapeamento, download) rodam em thread e precisam, no meio do caminho, escrever
no log, mover a barra de progresso e perguntar coisas ("Salvar como", "Tentar
de novo?"). Tudo isso passa por aqui:

* `na_ui(fn, ...)` agenda `fn` na thread da interface e volta na hora (o
  `after(0, ...)` do Tk);
* `na_ui_e_esperar(fn, ...)` roda `fn` na thread da interface e ESPERA o
  resultado - é o que deixa uma tarefa em thread abrir um diálogo e ler a
  resposta. Chamada da própria thread da interface, roda direto.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, Signal


class _Ponte(QObject):
    pedido = Signal(object)

    def __init__(self):
        super().__init__()
        self.pedido.connect(self._rodar, Qt.ConnectionType.QueuedConnection)

    @staticmethod
    def _rodar(fn) -> None:
        fn()


# Criada na importação, que acontece na thread da interface (a janela importa
# as telas antes de qualquer tarefa começar): é a thread "dona" da ponte, e a
# conexão enfileirada entrega cada pedido nela.
_ponte = _Ponte()


def na_thread_da_ui() -> bool:
    app = QCoreApplication.instance()
    return app is None or QThread.currentThread() is app.thread()


def na_ui(fn, *args, **kwargs) -> None:
    """Agenda `fn(*args, **kwargs)` na thread da interface (de qualquer thread)."""
    _ponte.pedido.emit(lambda: fn(*args, **kwargs))


def na_ui_e_esperar(fn, *args, **kwargs):
    """Roda `fn` na thread da interface e devolve o resultado (ou levanta o erro
    dela). Da própria thread da interface, roda direto."""
    if na_thread_da_ui():
        return fn(*args, **kwargs)
    pronto = threading.Event()
    caixa: dict = {}

    def _rodar():
        try:
            caixa["valor"] = fn(*args, **kwargs)
        except BaseException as e:  # noqa: BLE001 - devolve para quem pediu
            caixa["erro"] = e
        finally:
            pronto.set()

    _ponte.pedido.emit(_rodar)
    pronto.wait()
    if "erro" in caixa:
        raise caixa["erro"]
    return caixa.get("valor")
