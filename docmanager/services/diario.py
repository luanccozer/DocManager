"""O diário do aplicativo: abertura, encerramento, erro e queda, num arquivo.

Ideia trazida do Corella Suite (`corella_suite/core/diario.py`). O `.exe` do
DocManager é `console=False`: `sys.stderr` é None e o traceback de uma queda
ia para lugar nenhum. O diário responde "o app fechou sozinho ou fui eu?" pela
ÚLTIMA sessão:

    ABERTO ... ENCERRADO           fechado pela janela (a pessoa)
    ABERTO ... "Fatal Python error" queda do processo (o faulthandler escreve)
    ABERTO ... nada                 encerrado de fora: Gerenciador de Tarefas,
                                    antivírus, desligamento, falta de energia

Exceção Python fora das tarefas (EXCECAO) também fica registrada: é o rastro do
erro que, no `.exe`, ninguém via.

Mora na pasta de dados do usuário (`Documentos\\DocManager_Itaipu\\diario.log`),
ao lado da config. Passando de `LIMITE_BYTES`, vira `diario.1.log`. Sem Qt: quem
liga o encerramento ao `aboutToQuit` é a `ui/main_app.main()`.
"""
from __future__ import annotations

import faulthandler
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

LIMITE_BYTES = 1024 * 1024
ABERTO = "ABERTO"
ENCERRADO = "ENCERRADO"

_arquivo_fault = None   # o faulthandler precisa do arquivo aberto o tempo todo


def caminho() -> Path:
    from .credenciais import pasta_dados

    return pasta_dados() / "diario.log"


def _girar(arq: Path) -> None:
    try:
        if arq.exists() and arq.stat().st_size > LIMITE_BYTES:
            os.replace(arq, arq.with_name("diario.1.log"))
    except OSError:
        pass


def registrar(evento: str, detalhe: str = "") -> None:
    """Acrescenta uma linha datada. Nunca levanta: o diário é para depois."""
    try:
        arq = caminho()
        linha = f"{datetime.now():%Y-%m-%d %H:%M:%S} {evento}"
        if detalhe:
            linha += " " + detalhe.replace("\n", "\n    ")
        with arq.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:  # noqa: BLE001
        pass


def ultimas_linhas(n: int = 40) -> str:
    """As `n` últimas linhas do diário ('' sem diário). Nunca levanta: serve
    para anexar ao relato de um erro (tela Sugestões)."""
    try:
        linhas = caminho().read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:  # noqa: BLE001
        return ""
    return "\n".join(linhas[-n:])


def ultima_sessao_terminou_bem() -> bool | None:
    """A sessão anterior fechou pela janela? `None` se não há sessão anterior."""
    try:
        linhas = caminho().read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    eventos = [ln for ln in linhas if f" {ABERTO}" in ln or f" {ENCERRADO}" in ln]
    if not eventos:
        return None
    return f" {ENCERRADO}" in eventos[-1]


def _excepthook(tipo, valor, tb) -> None:
    registrar("EXCECAO", "".join(traceback.format_exception(tipo, valor, tb)).rstrip())
    if sys.__excepthook__ and sys.stderr is not None:
        sys.__excepthook__(tipo, valor, tb)


def _thread_excepthook(args) -> None:
    if args.exc_type is SystemExit:
        return
    registrar("EXCECAO", f"(thread {getattr(args.thread, 'name', '?')}) " + "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)).rstrip())


def iniciar(versao: str) -> bool | None:
    """Abre a sessão no diário e liga os ganchos de erro e de queda. Devolve
    como a sessão ANTERIOR terminou (ver `ultima_sessao_terminou_bem`)."""
    global _arquivo_fault
    anterior = ultima_sessao_terminou_bem()
    arq = caminho()
    _girar(arq)
    registrar(ABERTO, f"v{versao} pid={os.getpid()}")
    try:
        _arquivo_fault = arq.open("a", encoding="utf-8")
        faulthandler.enable(_arquivo_fault)
    except Exception:  # noqa: BLE001 - sem faulthandler o app abre igual
        _arquivo_fault = None
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook
    return anterior


def encerrar() -> None:
    registrar(ENCERRADO)
