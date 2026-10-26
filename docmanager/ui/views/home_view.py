"""Home - tela inicial neutra: boas-vindas, módulos e novidades.

O app abre aqui. Não é um módulo de processamento (sem console de log): é um
ponto de partida que mostra os blocos e, abaixo, as atualizações recentes.

As novidades NÃO ficam escritas aqui: elas vêm do `CHANGELOG.md`, que é o
mesmo texto publicado no Release do GitHub. Para anunciar algo, basta abrir um
bloco novo lá - esta tela e a página do Release passam a mostrar a mesma coisa.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ...services import novidades as novidades_svc
from .. import icones
from ..components import botao, rotulo
from ..logo import pixmap_do_logo
from ..ponte import na_ui

# (key da view, ícone, título, descrição) de cada bloco. A `key` casa com as
# ViewSpec da MainApp: clicar no bloco navega para o módulo.
MODULOS = [
    ("mapa", "compass", "Mapa dos Planos", "Atualiza a planilha de mapeamento: status real, hierarquia, "
     "KPIs e atrasos. Traz também o Delta (Máquina do Tempo) por Grupo/Nível."),
    ("doclist", "list-checks", "Doc List Mapping", "Follow-up da lista de documentos (dois níveis, agrupamento "
     "por escopo). Traz o planejamento do Controle e a Análise por Período: o que está previsto para emitir."),
    ("status", "search", "Status Documentos", "Status real de uma lista, de um arquivo Excel ou de toda a "
     "base vigente. Gera Excel com gráfico e abre o Delta por período (por classificação)."),
    ("historico", "chart-column", "Histórico e Dashboard", "Planilha detalhada (1 linha por revisão + "
     "atrasos Itaipu/CMI) e o painel executivo com evolução do atraso, First Time Right e gargalos."),
    ("relatorios", "clipboard-list", "Relatórios", "Relatório de Avanço (prazos de devolução da Itaipu) e "
     "Auditoria de Integração (documentos presos em 0AA)."),
    ("aconex", "download", "Extração Aconex", "Baixa a base completa do projeto direto da API do Aconex. "
     "Na primeira vez, cadastre as suas credenciais na própria tela."),
    ("config", "settings", "Configurações", "Aparência, credenciais do Aconex, atualizações do app, Regra "
     "da Aprovação Intermediária (VIP) e a base do atraso CMI na 0A."),
]


class _BlocoModulo(QFrame):
    """Cartão clicável de um módulo: o bloco inteiro abre a tela."""

    def __init__(self, key, icone, nome, desc, ao_abrir):
        super().__init__()
        self.setObjectName("card")
        self.setProperty("clicavel", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ao_abrir = lambda: ao_abrir(key)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)
        ic = QLabel()
        icones.aplicar(ic, icone, papel_cor="primaria", tamanho=20)
        titulo = rotulo(nome, "secao")
        titulo.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        topo = QHBoxLayout()
        topo.setSpacing(10)
        topo.addWidget(ic)
        topo.addWidget(titulo, 1)
        lay.addLayout(topo)
        texto = rotulo(desc, "suave", quebra=True)
        texto.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        lay.addWidget(texto)
        lay.addStretch(1)

    def mouseReleaseEvent(self, evento):  # noqa: N802 - nome do Qt
        if evento.button() == Qt.MouseButton.LeftButton:
            self._ao_abrir()
        super().mouseReleaseEvent(evento)


class HomeView(QWidget):
    titulo_view = "Início"

    def __init__(self, ctx, parent=None):
        super().__init__(parent)
        self.setObjectName("tela")
        self.ctx = ctx
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)
        conteudo = QWidget()
        self._body = QVBoxLayout(conteudo)
        self._body.setContentsMargins(28, 24, 28, 24)
        self._body.setSpacing(16)
        rolagem.setWidget(conteudo)
        externo.addWidget(rolagem)

        self._hero()
        self._aviso_versao()      # some quando não há atualização
        self._modulos()
        self._novidades()
        self._body.addStretch(1)
        # A checagem termina depois desta tela existir; o contexto avisa quando
        # (e já avisa na hora se a resposta chegou antes de a Home ser criada).
        self.ctx.ao_achar_atualizacao(lambda info: na_ui(self._mostrar_aviso, info))

    def _hero(self):
        card = QFrame()
        card.setObjectName("card")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(18)
        logo = QLabel()
        if not (pix := pixmap_do_logo(64)).isNull():
            logo.setPixmap(pix)
            lay.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        texto = QVBoxLayout()
        texto.setSpacing(4)
        texto.addWidget(rotulo("DocManager Itaipu", "titulo"))
        texto.addWidget(rotulo(f"Gestão documental · CMI ↔ Itaipu · v{self.ctx.versao}", "suave"))
        texto.addWidget(rotulo("Clique em um módulo abaixo (ou use a barra lateral) para começar.",
                               "suave", quebra=True))
        lay.addLayout(texto, 1)
        self._body.addWidget(card)

    def _aviso_versao(self):
        """Faixa "há uma nova versão" - criada escondida e revelada pelo aviso."""
        self._faixa = QFrame()
        self._faixa.setObjectName("card")
        self._faixa.setProperty("destaque", True)
        lay = QHBoxLayout(self._faixa)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(14)
        ic = QLabel()
        icones.aplicar(ic, "sparkles", papel_cor="primaria", tamanho=22)
        self._faixa_txt = rotulo("", quebra=True)
        lay.addWidget(ic)
        lay.addWidget(self._faixa_txt, 1)
        lay.addWidget(botao("Ver e atualizar", variante="primario", icone="download",
                            ao_clicar=lambda: self.ctx.abrir_atualizacao and self.ctx.abrir_atualizacao()))
        self._faixa.hide()
        self._body.addWidget(self._faixa)

    def _mostrar_aviso(self, info):
        try:
            self._faixa_txt.setText(f"Saiu a versão v{info.versao}. Você está na v{self.ctx.versao}. "
                                    f"Clique para ver o que mudou e atualizar.")
            self._faixa.show()
        except RuntimeError:   # a tela pode já ter sido destruída
            pass

    def faixa_visivel(self) -> bool:
        return not self._faixa.isHidden()

    def _modulos(self):
        self._body.addWidget(rotulo("Módulos", "secao"))
        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(12)
        for i, (key, ic, nome, desc) in enumerate(MODULOS):
            grade.addWidget(_BlocoModulo(key, ic, nome, desc, self._navegar), i // 2, i % 2)
        grade.setColumnStretch(0, 1)
        grade.setColumnStretch(1, 1)
        self._body.addLayout(grade)

    def _navegar(self, key: str):
        if self.ctx.navegar:
            self.ctx.navegar(key)

    def _novidades(self):
        bloco = novidades_svc.ler(self.ctx.versao)
        if bloco is None or not bloco.itens:
            return
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(6)
        topo = QHBoxLayout()
        ic = QLabel()
        icones.aplicar(ic, "sparkles", papel_cor="primaria")
        topo.addWidget(ic)
        topo.addWidget(rotulo("O que há de novo", "secao"))
        topo.addWidget(rotulo(bloco.titulo(), "legenda"))
        topo.addStretch(1)
        lay.addLayout(topo)
        for it in bloco.itens:
            lay.addWidget(rotulo(f"•  {it}", "suave", quebra=True))
        self._body.addWidget(card)
