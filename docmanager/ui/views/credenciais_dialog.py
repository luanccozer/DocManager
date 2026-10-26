"""Cadastro das credenciais do Aconex - a janela que substituiu o `.env`.

Aparece sozinha quando a pessoa tenta extrair sem ter usuário cadastrado, e
também pelo botão "Cadastrar usuário" (Extração) ou pelas Configurações.

A janela EXPLICA o que é cada campo: quem recebe o app pelo instalador não faz
ideia do que é "Client ID" nem de onde tirar o "User ID".
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QLineEdit, QVBoxLayout

from ...services.credenciais import cofre
from .. import dialogos
from ..components import botao, rodape, rotulo

AJUDA = (
    "A Extração Aconex usa a API oficial, e ela exige uma credencial OAuth sua. "
    "São três dados, que o administrador do Aconex passa quando registra o "
    "aplicativo no seu nome:\n\n"
    "• Client ID (APP ID): identifica esse aplicativo. Costuma ter a cara de "
    "SCP_SEU_NOME_ACONEX_client_APPID.\n"
    "• User ID: o número da sua conta no Aconex. Só dígitos, por exemplo "
    "1208560183.\n"
    "• Client Secret: a senha do aplicativo. É a única parte sigilosa.\n\n"
    "O Client Secret fica guardado só nesta máquina, cifrado pelo Windows na sua "
    "conta de usuário. Ele não vai para o GitHub nem para a pasta do programa, e "
    "continua valendo depois que o DocManager se atualizar."
)


class CadastroCredencialDialog(QDialog):
    """Modal de cadastro/edição. Depois de `exec()`, leia `.resultado` (nome
    salvo) - fica `None` se a pessoa cancelar."""

    def __init__(self, parent=None, nome: str | None = None):
        super().__init__(parent)
        self.resultado: str | None = None
        self._editando = nome
        self.setWindowTitle("Cadastrar usuário do Aconex" if not nome else f"Editar - {nome}")
        self.setModal(True)
        self.setMinimumWidth(600)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(6)
        lay.addWidget(rotulo("Credenciais do Aconex", "titulo"))
        lay.addWidget(rotulo(AJUDA, "suave", quebra=True))
        lay.addSpacing(8)

        self._campos: dict[str, QLineEdit] = {}
        for chave, texto, dica in (("nome", "Nome (como aparece na lista)", "Ex.: Luan Cozer"),
                                   ("client_id", "Client ID (APP ID)", "SCP_SEU_NOME_ACONEX_client_APPID"),
                                   ("user_id", "User ID (numérico)", "1208560183"),
                                   ("secret", "Client Secret", "cole aqui o segredo")):
            lay.addWidget(rotulo(texto))
            campo = QLineEdit(placeholderText=dica)
            lay.addWidget(campo)
            lay.addSpacing(4)
            self._campos[chave] = campo
        self._campos["secret"].setEchoMode(QLineEdit.EchoMode.Password)

        # Mostrar/ocultar o segredo: colar um secret às cegas é o erro mais comum.
        self._ver = QCheckBox("Mostrar o Client Secret")
        self._ver.toggled.connect(lambda v: self._campos["secret"].setEchoMode(
            QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password))
        lay.addWidget(self._ver)

        if nome and (cred := cofre().obter(nome)):
            self._campos["nome"].setText(cred.nome)
            self._campos["client_id"].setText(cred.client_id)
            self._campos["user_id"].setText(cred.user_id)
            self._campos["secret"].setText(cred.secret)

        salvar = botao("Salvar", variante="primario", ao_clicar=self._salvar)
        salvar.setDefault(True)
        lay.addSpacing(10)
        lay.addWidget(rodape(salvar, botao("Cancelar", ao_clicar=self.reject)))
        self._campos["nome"].setFocus()

    def _valor(self, chave: str) -> str:
        return self._campos[chave].text().strip()

    def _salvar(self):
        try:
            cred = cofre().salvar(self._valor("nome"), self._valor("client_id"),
                                  self._valor("user_id"), self._valor("secret"))
        except ValueError as e:
            dialogos.aviso("Dados incompletos", str(e), self)
            return
        except Exception as e:  # noqa: BLE001
            dialogos.erro("Erro ao salvar", str(e), self)
            return
        # Renomear = salvar com nome novo; apaga o registro antigo para não duplicar.
        if self._editando and self._editando != cred.nome:
            cofre().remover(self._editando)
        self.resultado = cred.nome
        self.accept()


def cadastrar(parent=None, nome: str | None = None) -> str | None:
    """Abre o modal e espera. Devolve o nome salvo, ou None se cancelou."""
    dlg = CadastroCredencialDialog(parent, nome)
    dlg.exec()
    return dlg.resultado
