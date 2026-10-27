"""Janela "há uma nova versão" - aviso, download com progresso e instalação.

O download roda numa thread separada; todo toque na interface volta para a
thread da janela pela `ponte` (no Qt, widget só pode ser mexido pela thread que
o criou).

Duas formas, como na CMI Suite: a PEQUENA (só o que mudou, aplicada com o app
aberto, que então se reabre) quando o Release tem o pacote para a versão
instalada e a pasta aceita escrita; senão, ou se a pequena falhar, o instalador
COMPLETO. A pequena que falha se desfaz sozinha antes de o completo começar.

Os textos vêm de `ui/atualizacao_textos.py`; a rede, de `services/updater.py`.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget

from ...services import updater
from .. import atualizacao_textos as txt
from .. import dialogos, icones
from ..components import botao, rotulo


class AtualizacaoDialog(QDialog):
    """Aviso de atualização (modal à janela principal).

    `fechar_app` é chamada quando o instalador está pronto: o Windows não deixa
    sobrescrever um `.exe` em execução, então o DocManager precisa sair de cena.
    `tarefa_em_andamento()` diz se há um processamento rodando - se houver, a
    janela pergunta antes de fechar o app.
    """

    _status = Signal(str)
    _progresso = Signal(float)
    _resumo = Signal(str)
    _falha = Signal(object)
    _pronto = Signal()
    _aplicada = Signal(str)

    # O instalador espera o app sair; a pausa é só para dar tempo de ler.
    PAUSA_ANTES_DE_FECHAR_MS = 1500

    def __init__(self, parent, info: updater.Atualizacao, versao_atual: str,
                 *, fechar_app=None, ao_pular=None, tarefa_em_andamento=None):
        super().__init__(parent)
        self.info = info
        self._fechar_app = fechar_app
        self._ao_pular = ao_pular
        self._tarefa_em_andamento = tarefa_em_andamento or (lambda: False)
        self._baixando = False
        self._pequena = updater.pode_pequena(info)
        self.setWindowTitle("Atualização disponível")
        self.setModal(True)
        self.setMinimumWidth(620)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(8)
        ic = QLabel()
        icones.aplicar(ic, "sparkles", papel_cor="primaria", tamanho=22)
        topo = QHBoxLayout()
        topo.addWidget(ic)
        topo.addWidget(rotulo(txt.titulo(info), "titulo"), 1)
        lay.addLayout(topo)
        self.lbl_resumo = rotulo(txt.resumo(info, versao_atual, self._pequena), "suave", quebra=True)
        lay.addWidget(self.lbl_resumo)

        notas = QPlainTextEdit(info.notas or "(esta versão não trouxe notas)")
        notas.setObjectName("notas")
        notas.setReadOnly(True)
        notas.setMinimumHeight(200)
        lay.addWidget(notas, 1)

        lay.addWidget(rotulo(txt.TEXTO_REABRE, "legenda", quebra=True))
        if not self._pequena and updater.precisa_elevacao():
            lay.addWidget(rotulo(txt.TEXTO_UAC, "legenda", quebra=True))

        self.barra = QProgressBar()
        self.barra.setRange(0, 1000)
        self.barra.setTextVisible(False)
        self.barra.hide()
        self.status = rotulo("", "legenda", quebra=True)
        self.status.hide()
        lay.addWidget(self.barra)
        lay.addWidget(self.status)

        self.btn_pular = botao(f"Pular a v{info.versao}", variante="fantasma", ao_clicar=self._pular)
        self.btn_atualizar = botao("Atualizar agora", variante="primario", icone="download",
                                   ao_clicar=self._atualizar)
        self.btn_depois = botao("Agora não", ao_clicar=self._fechar)
        rod = QWidget()
        rl = QHBoxLayout(rod)
        rl.setContentsMargins(0, 10, 0, 0)
        rl.addWidget(self.btn_pular)
        rl.addStretch(1)
        rl.addWidget(self.btn_atualizar)
        rl.addWidget(self.btn_depois)
        lay.addWidget(rod)
        self.btn_atualizar.setDefault(True)

        self._status.connect(self.status.setText)
        self._progresso.connect(self._mostrar_progresso)
        self._resumo.connect(self.lbl_resumo.setText)
        self._falha.connect(self._falhou)
        self._pronto.connect(self._agendar_encerramento)
        self._aplicada.connect(self._reabrir)

    def _mostrar_progresso(self, fracao: float):
        self.barra.setValue(int(max(0.0, min(fracao, 1.0)) * 1000))

    def _agendar_encerramento(self):
        QTimer.singleShot(self.PAUSA_ANTES_DE_FECHAR_MS, self._encerrar_para_instalar)

    def trazer_para_frente(self):
        """A checagem da abertura e o botão manual responderam juntos: em vez de
        um segundo aviso, este volta para a frente."""
        self.show()
        self.raise_()
        self.activateWindow()

    # --- ações ---
    def _dizer(self, msg: str):
        """Escreve no rótulo de status - seguro para chamar de outra thread."""
        self._status.emit(msg)

    def _atualizar(self):
        if self._baixando:
            return
        if self._tarefa_em_andamento() and not dialogos.perguntar(
                "Tarefa em andamento", txt.PERGUNTA_TAREFA, padrao_nao=True, parent=self):
            return
        self._baixando = True
        self.btn_atualizar.setEnabled(False)
        self.btn_atualizar.setText("Baixando...")
        self.btn_pular.setEnabled(False)
        self.btn_depois.setEnabled(False)
        self.barra.setValue(0)
        self.barra.show()
        self.status.show()
        self._dizer("Baixando a atualização..." if self._pequena else "Baixando o instalador...")
        threading.Thread(target=self._trabalho, daemon=True).start()

    def _trabalho(self):
        """Roda FORA da thread da interface: a pequena, ou o instalador completo.

        A pequena, quando dá certo, termina em `_aplicada` (o app se reabre).
        Quando falha, a pasta já voltou ao que era e segue o completo.
        `instalar` só volta quando o instalador está pronto (já passou pela
        permissão do Windows, se ela foi pedida). Se ele não ficar pronto, cai no
        `_falhou` e o app segue aberto - fechar antes era o que abortava a
        atualização na v3.1.0."""
        if self._pequena:
            try:
                exe = updater.atualizar_pequena(self.info, progresso_cb=self._progresso.emit,
                                                log_cb=self._dizer)
            except Exception as e:  # noqa: BLE001 - qualquer falha: vai o completo
                self._resumo.emit(txt.caiu_no_completo(self.info, e))
                self._progresso.emit(0.0)
            else:
                self._aplicada.emit(str(exe))
                return
        try:
            caminho = updater.baixar(self.info, progresso_cb=self._progresso.emit,
                                     log_cb=self._dizer)
            self._dizer(txt.TEXTO_CONFERIDO)
            updater.instalar(caminho, log_cb=self._dizer)
        except Exception as e:  # noqa: BLE001 - qualquer falha vira aviso na tela
            self._falha.emit(e)
            return
        self._pronto.emit()

    def _falhou(self, erro: Exception):
        self._baixando = False
        self.barra.hide()
        self.btn_atualizar.setEnabled(True)
        self.btn_atualizar.setText("Tentar de novo")
        self.btn_pular.setEnabled(True)
        self.btn_depois.setEnabled(True)
        self._dizer("")
        dialogos.erro("Não foi possível atualizar",
                      f"{erro}\n\nVocê pode seguir usando esta versão normalmente. Para baixar a nova "
                      f"à mão:\n{self.info.url_pagina}", self)

    def _reabrir(self, exe: str):
        """A pequena foi aplicada: abre o .exe novo e este processo sai.

        Sai na HORA, sem nada pelo caminho: o `.exe` em execução já foi trocado
        no disco, e um import tardio deste processo leria o arquivo novo."""
        self._dizer(txt.TEXTO_APLICADO)
        try:
            updater.reabrir(exe)
        except OSError as e:
            self._baixando = False
            self.btn_depois.setEnabled(True)
            self.btn_atualizar.setText("Atualizado")
            dialogos.erro("Atualizado, mas não reabriu",
                          f"A versão nova já está instalada, mas o Windows não deixou abri-la "
                          f"({e}).\n\nFeche o DocManager e abra de novo.", self)
            return
        self._encerrar_para_instalar()

    def _encerrar_para_instalar(self):
        self._dizer("O DocManager vai fechar e abrir de novo, já atualizado.")
        if self._fechar_app:
            self._fechar_app()
        else:
            self.done(QDialog.DialogCode.Accepted)

    def _pular(self):
        if self._ao_pular:
            self._ao_pular(self.info.versao)
        self._fechar()

    def _fechar(self):
        if self._baixando:
            return   # não some no meio do download
        self.done(QDialog.DialogCode.Rejected)

    # "X" e Esc fecham - menos durante o download.
    def reject(self):
        self._fechar()

    def closeEvent(self, evento):  # noqa: N802 - nome do Qt
        if self._baixando:
            evento.ignore()
        else:
            super().closeEvent(evento)
