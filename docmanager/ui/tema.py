"""Tema escuro, claro ou o do sistema, trocado com o app aberto.

A escolha da pessoa ("escuro", "claro" ou "sistema") fica nas configurações
(`ConfigManager`, chave `tema`); o tema DE FATO é "escuro" ou "claro":
"sistema" pergunta ao Qt o esquema de cores do Windows.

`aplicar` faz a troca inteira: grava a escolha, muda `estilo.TEMA_ATUAL`,
regera a folha do app, repinta os ícones de cada janela e emite `mudou` para
quem desenhou outra coisa com a paleta (as cores de linha das tabelas).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication

from . import estilo, icones
from .tokens import TEMAS

PADRAO = "escuro"


class _Avisador(QObject):
    mudou = Signal(str)


_avisador = _Avisador()
# Emitido depois de cada `aplicar`, com o tema efetivo ("escuro" ou "claro").
mudou = _avisador.mudou


def valida(escolha) -> str:
    return escolha if escolha in TEMAS else PADRAO


def _esquema_do_sistema() -> str:
    """"claro" ou "escuro" conforme o sistema; sem resposta, o escuro."""
    try:
        esquema = QGuiApplication.styleHints().colorScheme()
    except Exception:  # noqa: BLE001 - Qt sem a pergunta: fica o padrão
        return PADRAO
    return "claro" if esquema == Qt.ColorScheme.Light else "escuro"


def efetivo(escolha: str) -> str:
    """O tema que se pinta para a `escolha`: "sistema" vira o do Windows."""
    if escolha == "sistema":
        return _esquema_do_sistema()
    return "claro" if escolha == "claro" else "escuro"


def aplicar(app, escolha: str, config=None) -> str:
    """Troca o tema do app inteiro para `escolha` (inválida: escuro) e devolve a
    escolha que valeu. Com `config`, grava a escolha (gravar que falha não
    impede a troca)."""
    escolha = valida(escolha)
    if config is not None:
        try:
            config.set_setting("tema", escolha)
        except Exception:  # noqa: BLE001 - lembrar não pode impedir a troca
            pass
    estilo.TEMA_ATUAL = efetivo(escolha)
    _preparar_imagens()
    app.setStyleSheet(estilo.folha_de_estilo())
    for janela in app.topLevelWidgets():
        icones.reaplicar(janela)
        janela.update()
    mudou.emit(estilo.TEMA_ATUAL)
    return escolha


def _preparar_imagens() -> None:
    """A seta dos seletores e o tique da caixa de marcar, na cor do tema: a folha
    só os aceita como arquivo de imagem."""
    import tempfile
    from pathlib import Path

    p = estilo.paleta_atual()
    pasta = Path(tempfile.gettempdir()) / "docmanager_ui"
    estilo.IMAGENS["seta"] = icones.salvar_png("chevron-down", p["texto_suave"], pasta)
    estilo.IMAGENS["tique"] = icones.salvar_png("check", p["texto_sobre_primaria"], pasta)


_seguindo: list = []


def seguir_o_sistema(app, config) -> None:
    """Com "sistema" escolhido, a troca de tema do Windows com o app aberto
    também troca o do app. Liga uma vez só."""
    if _seguindo:
        return

    def _ao_mudar(_esquema) -> None:
        if valida(config.settings.tema) == "sistema":
            aplicar(QGuiApplication.instance() or app, "sistema")

    try:
        QGuiApplication.styleHints().colorSchemeChanged.connect(_ao_mudar)
    except Exception:  # noqa: BLE001 - Qt sem o sinal: segue sem acompanhar
        return
    _seguindo.append(_ao_mudar)
