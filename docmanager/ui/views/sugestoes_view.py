"""Sugestões: quem usa o app escreve uma ideia, um erro ou uma dúvida e o
DocManager abre um RASCUNHO de e-mail para quem cuida dele. O texto e o link
saem de `services/sugestoes.py`; o destinatário, das Configurações."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from ... import __version__
from ...services import sugestoes
from .. import dialogos
from ..components import Card, Seletor, botao, linha, rotulo
from .base import BaseView


class SugestoesView(BaseView):
    titulo_view = "Sugestões"
    subtitulo_view = "Mande uma ideia, um erro ou uma dúvida sobre o DocManager"

    def montar(self, body):
        card = Card("Escrever")
        self.sel_tipo = Seletor(sugestoes.TIPOS)
        card.add(linha(rotulo("Tipo"), self.sel_tipo))
        self.texto = QPlainTextEdit()
        self.texto.setObjectName("caixa_texto")   # a caixa de texto da folha (cor do tema)
        self.texto.setPlaceholderText("O que poderia ser melhor, o que deu errado (e em qual tela) "
                                      "ou o que ficou difícil de entender.")
        self.texto.setMinimumHeight(180)
        card.add(self.texto)
        self.lbl_destino = rotulo("", "legenda", quebra=True)
        card.add(self.lbl_destino)
        self.btn_email = botao("Abrir rascunho no e-mail", variante="primario", icone="mail",
                               ao_clicar=self._enviar)
        self.btn_copiar = botao("Copiar texto", icone="copy", ao_clicar=self._copiar)
        card.add(linha(self.btn_email, self.btn_copiar))
        card.add(rotulo("O rascunho abre no seu programa de e-mail com a versão do DocManager "
                        "anotada. Nada é enviado sem você clicar em Enviar.", "suave", quebra=True))
        body.addWidget(card)
        self.ao_exibir()

    def ao_exibir(self):
        destino = self.ctx.config.settings.email_sugestoes.strip()
        if destino:
            self.lbl_destino.setText(f"Vai para: {destino} (muda em Configurações → Sugestões).")
        else:
            self.lbl_destino.setText("Nenhum destinatário configurado: o rascunho abre sem destinatário "
                                     "para você completar (dá para fixar um em Configurações → Sugestões).")

    def _rascunho(self) -> sugestoes.Rascunho | None:
        try:
            return sugestoes.montar(self.sel_tipo.get(), self.texto.toPlainText(), __version__,
                                    self.ctx.config.settings.email_sugestoes)
        except ValueError as e:
            dialogos.aviso("Sugestões", str(e), self)
            return None

    def _copiar_texto(self, rascunho: sugestoes.Rascunho) -> None:
        QApplication.clipboard().setText(rascunho.texto)

    def _enviar(self):
        rascunho = self._rascunho()
        if rascunho is None:
            return
        if rascunho.cortado:
            self._copiar_texto(rascunho)
            self.log.log("Texto longo: copiado para a área de transferência. Cole no rascunho com Ctrl+V.")
        if QDesktopServices.openUrl(QUrl(rascunho.link)):
            self.log.log("Rascunho aberto no programa de e-mail. Revise e envie por lá.")
            return
        self._copiar_texto(rascunho)
        self.log.log("Não foi possível abrir o programa de e-mail; o texto foi copiado.")
        dialogos.aviso("Sugestões", "O Windows não abriu nenhum programa de e-mail. O texto foi copiado: "
                       "cole num e-mail novo (Ctrl+V).", self)

    def _copiar(self):
        rascunho = self._rascunho()
        if rascunho is None:
            return
        self._copiar_texto(rascunho)
        self.log.log("Texto copiado para a área de transferência.")
