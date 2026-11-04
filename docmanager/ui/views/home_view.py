"""Home - tela inicial neutra: boas-vindas, módulos e novidades.

O app abre aqui. Não é um módulo de processamento (sem console de log): é um
ponto de partida que mostra os blocos e, depois de uma atualização, o cartão
"O que mudou na vX" (uma vez, como na CMI Suite).

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
from ..idioma import marcar, t

# (key da view, ícone, título, descrição) de cada bloco. A `key` casa com as
# ViewSpec da MainApp: clicar no bloco navega para o módulo.
MODULOS = [
    ("mapa", "compass", marcar("Mapa dos Planos"), marcar("Atualiza a planilha de mapeamento: status real, hierarquia, "
     "KPIs e atrasos. Traz também o Delta (Máquina do Tempo) por Grupo/Nível.")),
    ("doclist", "list-checks", marcar("Doc List Mapping"), marcar("Follow-up da lista de documentos (dois níveis, agrupamento "
     "por escopo). Traz o planejamento do Controle e a Análise por Período: o que está previsto para emitir.")),
    ("status", "search", marcar("Status Documentos"), marcar("Status real de uma lista, de um arquivo Excel ou de toda a "
     "base vigente. Gera Excel com gráfico e abre o Delta por período (por classificação).")),
    ("historico", "chart-column", marcar("Histórico e Dashboard"), marcar("Planilha detalhada (1 linha por revisão + "
     "atrasos Itaipu/CMI) e o painel executivo com evolução do atraso, First Time Right e gargalos.")),
    ("relatorios", "clipboard-list", marcar("Relatórios"), marcar("Relatório de Avanço (prazos de devolução da Itaipu) e "
     "Auditoria de Integração (documentos presos em 0AA).")),
    ("transpasse", "calendar-range", marcar("Transpasse de Fase"), marcar("Quadro dia a dia de cada grupo de equipamentos: "
     "convocação, inspeção IB, CCMLC, transpasse e início do comissionamento, desenhado a partir das planilhas.")),
    ("pendencias", "file-spreadsheet", marcar("Pendências"), marcar("Atualiza a planilha de mapeamento de pendências "
     "de comissionamento direto do Aconex (Campo → Questões): as novas entram no topo e as colunas do Aconex ficam "
     "em dia; as colunas preenchidas à mão não são tocadas.")),
    ("upload", "lock", marcar("Upload de documentos"), marcar("O robô sobe documentos no Aconex a partir da "
     "pasta do Box. Por enquanto, o envio para aprovação: confere o código e mostra o que vai fazer.")),
    ("aconex", "download", marcar("Extração Aconex"), marcar("Baixa a base completa do projeto direto da API do Aconex. "
     "Na primeira vez, cadastre as suas credenciais na própria tela.")),
    ("config", "settings", marcar("Configurações"), marcar("Aparência, credenciais do Aconex, atualizações do app, Regra "
     "da Aprovação Intermediária (VIP), a base do atraso CMI na 0A e o e-mail das sugestões.")),
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
        titulo = rotulo(t(nome), "secao")
        titulo.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        topo = QHBoxLayout()
        topo.setSpacing(10)
        topo.addWidget(ic)
        topo.addWidget(titulo, 1)
        lay.addLayout(topo)
        texto = rotulo(t(desc), "suave", quebra=True)
        texto.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        lay.addWidget(texto)
        lay.addStretch(1)

    def mouseReleaseEvent(self, evento):  # noqa: N802 - nome do Qt
        if evento.button() == Qt.MouseButton.LeftButton:
            self._ao_abrir()
        super().mouseReleaseEvent(evento)


class HomeView(QWidget):
    titulo_view = marcar("Início")

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
        self._novidades()         # uma vez, depois de atualizar (como na CMI Suite)
        self._modulos()
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
        texto.addWidget(rotulo(t("DocManager Itaipu"), "titulo"))
        texto.addWidget(rotulo(t('Gestão documental · CMI ↔ Itaipu · v{versao}', versao=self.ctx.versao), "suave"))
        texto.addWidget(rotulo(t("Clique em um módulo abaixo (ou use a barra lateral) para começar."),
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
        lay.addWidget(botao(t("Ver e atualizar"), variante="primario", icone="download",
                            ao_clicar=lambda: self.ctx.abrir_atualizacao and self.ctx.abrir_atualizacao()))
        self._faixa.hide()
        self._body.addWidget(self._faixa)

    def _mostrar_aviso(self, info):
        try:
            self._faixa_txt.setText(t('Saiu a versão v{versao}. Você está na v{versao2}. Clique para ver o que mudou e atualizar.', versao=info.versao, versao2=self.ctx.versao))
            self._faixa.show()
        except RuntimeError:   # a tela pode já ter sido destruída
            pass

    def faixa_visivel(self) -> bool:
        return not self._faixa.isHidden()

    def _modulos(self):
        self._body.addWidget(rotulo(t("Módulos"), "secao"))
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
        """O cartão "O que mudou na vX", igual ao da CMI Suite: aparece UMA vez,
        na primeira abertura depois de atualizar, e some no "Entendi". Na
        primeira instalação não aparece (não há "antes" para comparar)."""
        self.cartao_novidades = None
        cfg = self.ctx.config
        bloco = novidades_svc.ler(self.ctx.versao)
        anterior = cfg.versao_anterior()
        if not novidades_svc.deve_mostrar(self.ctx.versao, anterior, bloco):
            if anterior != self.ctx.versao:
                self._leu_novidades()     # 1ª instalação ou versão sem nota: só anota
            return
        card = QFrame()
        card.setObjectName("novidades")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(6)
        topo = QHBoxLayout()
        ic = QLabel()
        icones.aplicar(ic, "sparkles", papel_cor="primaria", tamanho=18)
        topo.addWidget(ic)
        topo.addWidget(rotulo(t('O que mudou na v{versao}', versao=self.ctx.versao), nome="novidades_titulo"), 1)
        lay.addLayout(topo)
        for it in bloco.itens:
            lay.addWidget(rotulo(f"•  {it}", quebra=True))   # o CHANGELOG é em português
        self.btn_entendi = botao(t("Entendi"), variante="primario", ao_clicar=self._leu_novidades)
        rod = QHBoxLayout()
        rod.addStretch(1)
        rod.addWidget(self.btn_entendi)
        lay.addLayout(rod)
        self.cartao_novidades = card
        self._body.addWidget(card)

    def novidades_visiveis(self) -> bool:
        """Para os testes (`isVisible()` depende da janela estar na tela)."""
        return self.cartao_novidades is not None and not self.cartao_novidades.isHidden()

    def _leu_novidades(self):
        if self.cartao_novidades is not None:
            self.cartao_novidades.setVisible(False)
        self.ctx.config.set_setting("versao_vista", self.ctx.versao)
