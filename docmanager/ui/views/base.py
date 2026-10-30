from __future__ import annotations

from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from ..components import LogConsole, botao, linha, rotulo
from ..idioma import t


class BaseView(QWidget):
    """Cabeçalho (título + subtítulo) + corpo rolável + console de log padronizado.

    TODA view herda o mesmo painel de log ancorado no rodapé, com altura
    dinâmica (acompanha o tamanho da janela). Como não vemos o terminal, é aqui
    que aparece o que está acontecendo e os erros. Subclasses usam `self.log`
    e montam a tela em `montar(body)`, onde `body` é um QVBoxLayout.
    """

    titulo_view = "View"
    subtitulo_view = ""

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("tela")
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 18)
        lay.setSpacing(10)

        lay.addWidget(rotulo(t(self.titulo_view), nome="titulo_view"))
        if self.subtitulo_view:
            lay.addWidget(rotulo(t(self.subtitulo_view), nome="subtitulo_view", quebra=True))

        self._rolagem = QScrollArea()
        self._rolagem.setWidgetResizable(True)
        self._rolagem.setFrameShape(QFrame.Shape.NoFrame)
        conteudo = QWidget()
        self.body = QVBoxLayout(conteudo)
        self.body.setContentsMargins(0, 6, 8, 6)
        self.body.setSpacing(14)
        self._rolagem.setWidget(conteudo)
        lay.addWidget(self._rolagem, 1)   # corpo cresce; o log fica ancorado embaixo

        self._montar_console(lay)   # cria self.log (rodapé, altura dinâmica)
        self.montar(self.body)
        self.body.addStretch(1)

    def _montar_console(self, lay) -> None:
        self._console = QFrame()
        self._console.setObjectName("card")
        cl = QVBoxLayout(self._console)
        cl.setContentsMargins(12, 8, 12, 10)
        cl.setSpacing(6)
        self.log = LogConsole()
        titulo = rotulo(t("Registro de execução"), nome="card_titulo")
        limpar = botao(t("Limpar"), variante="fantasma", icone="eraser", ao_clicar=self.log.clear)
        cl.addWidget(linha(titulo, QWidget(), limpar, esticar=1))
        cl.addWidget(self.log, 1)
        lay.addWidget(self._console)
        self.log.log("Pronto. Os passos e eventuais erros aparecem aqui.")
        self._ajustar_console()

    def resizeEvent(self, evento):  # noqa: N802 - nome do Qt
        super().resizeEvent(evento)
        self._ajustar_console()

    def _ajustar_console(self) -> None:
        """Altura do console = ~24% da tela, entre 140 e 300 px (padronizado)."""
        self._console.setFixedHeight(max(140, min(int(self.height() * 0.24), 300)))

    def montar(self, body) -> None:  # override
        raise NotImplementedError

    def ao_exibir(self) -> None:  # override
        """Chamado TODA vez que a view volta para a tela.

        As views são criadas uma vez e ficam guardadas; o que muda por fora
        delas (credenciais cadastradas em outra tela, uma opção das
        Configurações) só aparece se ela se atualizar aqui.
        """
