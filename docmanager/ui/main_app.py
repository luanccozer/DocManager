"""Janela principal: barra lateral + pilha de telas gerados por um REGISTRO
declarativo de views. Adicionar um módulo futuro = criar a view e acrescentar
um ViewSpec nesta lista.

Interface em Qt (PySide6) desde a 3.3.0, com o mesmo sistema visual do SIG-FT:
tokens de cor por papel (`ui/tokens.py`), tema escuro/claro/do Windows trocado
com o app aberto (`ui/tema.py`) e ícones SVG (`ui/icones.py`).
"""
from __future__ import annotations

import os
import sys
import threading
import traceback
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..services import updater
from ..services.config import ConfigManager
from . import atualizacao_textos as txt
from . import dialogos, estilo, icones, tema
from .app_context import AppContext
from .components import RunBar, botao, rotulo
from .logo import icone_do_app, pixmap_do_logo
from .ponte import na_ui
from .views.aconex_view import AconexView
from .views.config_view import ConfigView
from .views.doclist_view import DocListView
from .views.historico_view import HistoricoView
from .views.home_view import HomeView
from .views.mapa_view import MapaView
from .views.reports_view import ReportsView
from .views.status_view import StatusDocsView


@dataclass(frozen=True)
class ViewSpec:
    key: str
    label: str
    icone: str
    factory: Callable


VIEWS = [
    ViewSpec("home", "Início", "house", HomeView),
    ViewSpec("mapa", "Mapa dos Planos", "compass", MapaView),
    ViewSpec("doclist", "Doc List Mapping", "list-checks", DocListView),
    ViewSpec("status", "Status Documentos", "search", StatusDocsView),
    ViewSpec("historico", "Histórico e Dashboard", "chart-column", HistoricoView),
    ViewSpec("relatorios", "Relatórios", "clipboard-list", ReportsView),
    ViewSpec("aconex", "Extração Aconex", "download", AconexView),
    ViewSpec("config", "Configurações", "settings", ConfigView),
]


class _Rodape(QLabel):
    """A versão instalada, no pé da barra. Clicável: abre a atualização."""

    def __init__(self, texto, ao_clicar):
        super().__init__(texto)
        self.setObjectName("rodape_versao")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ao_clicar = ao_clicar

    def mouseReleaseEvent(self, evento):  # noqa: N802 - nome do Qt
        if evento.button() == Qt.MouseButton.LeftButton:
            self._ao_clicar()
        super().mouseReleaseEvent(evento)


class MainApp(QMainWindow):
    TEXTO_PROCURAR = "Procurar atualizações"

    # A checagem automática se repete enquanto o app fica aberto: quem deixa o
    # DocManager aberto a semana inteira também precisa ser avisado. Aqui só se
    # PERGUNTA de hora em hora; quem decide se é hora de ir ao GitHub é
    # `updater.deve_verificar` (no máximo a cada 6 h com o app aberto).
    VERIFICAR_A_CADA_MS = 60 * 60 * 1000
    # Atraso da checagem e da janela de aviso: a splash ainda está na tela.
    CHECAR_APOS_MS = 1200
    AVISO_APOS_MS = 2500

    def __init__(self, config: ConfigManager | None = None):
        super().__init__()
        self.setWindowTitle(f"DocManager Itaipu - v{__version__}")
        self.resize(1200, 760)
        self.setMinimumSize(980, 640)
        self.setWindowIcon(icone_do_app())

        self.ctx = AppContext(config=config or ConfigManager(), versao=__version__)
        self.ctx.navegar = self.selecionar   # Home usa para abrir módulos ao clicar
        self.ctx.abrir_atualizacao = self.abrir_atualizacao
        self.ctx.verificar_atualizacao = self.verificar_atualizacao
        self._procurando = False              # checagem manual em andamento
        self._saindo_para_atualizar = False   # ver main()
        self._dialogo_atualizacao = None      # um aviso só, ver abrir_atualizacao
        self._views: dict[str, QWidget] = {}
        self._botoes: dict[str, QPushButton] = {}
        self._key_ativa: str | None = None

        central = QWidget()
        central.setObjectName("conteudo")
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._montar_sidebar())
        self._pilha = QStackedWidget()
        lay.addWidget(self._pilha, 1)
        self.setCentralWidget(central)
        self.selecionar(VIEWS[0].key)

        # Checagem automática: em thread, e só depois de a janela estar montada -
        # nada disso pode atrasar a abertura do app.
        QTimer.singleShot(self.CHECAR_APOS_MS, self.verificar_na_abertura)
        self._periodica = QTimer(self)
        self._periodica.setInterval(self.VERIFICAR_A_CADA_MS)
        self._periodica.timeout.connect(lambda: self.verificar_atualizacao(False))
        # Ctrl+K: "Procurar atualizações" de qualquer tela.
        QShortcut(QKeySequence("Ctrl+K"), self, activated=lambda: self.verificar_atualizacao(True))

    # ------------------------------------------------------------------ barra
    def _montar_sidebar(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("sidebar")
        barra.setFixedWidth(estilo.LARGURA_BARRA_LATERAL)
        lay = QVBoxLayout(barra)
        lay.setContentsMargins(14, 22, 14, 14)
        lay.setSpacing(4)

        # Marca: logo definitivo do projeto + título.
        marca = QHBoxLayout()
        marca.setSpacing(10)
        logo = QLabel()
        if not (pix := pixmap_do_logo(40)).isNull():
            logo.setPixmap(pix)
            marca.addWidget(logo)
        marca.addWidget(rotulo("DocManager", nome="app_nome"), 1)
        lay.addLayout(marca)
        lay.addWidget(rotulo("Itaipu · Gestão Documental", nome="app_sub"))
        lay.addSpacing(18)

        for spec in VIEWS:
            b = QPushButton(spec.label)
            b.setProperty("menu", True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            icones.aplicar(b, spec.icone, papel_cor="texto_suave",
                           papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO)
            b.clicked.connect(lambda _=False, k=spec.key: self.selecionar(k))
            lay.addWidget(b)
            self._botoes[spec.key] = b
        lay.addStretch(1)

        # Procurar atualização na hora, de qualquer tela.
        self._btn_procurar = botao(self.TEXTO_PROCURAR, icone="refresh-cw",
                                   ao_clicar=lambda: self.verificar_atualizacao(True),
                                   dica="Também pelo atalho Ctrl+K")
        lay.addWidget(self._btn_procurar)
        # Rodapé: a versão instalada. Quando sai uma nova, este mesmo rótulo
        # vira o aviso - é o canto onde a pessoa já olha para conferir a versão.
        self._rodape = _Rodape(f"v{__version__}", self.abrir_atualizacao)
        lay.addSpacing(4)
        lay.addWidget(self._rodape)
        self.ctx.ao_achar_atualizacao(lambda info: na_ui(self._marcar_rodape, info))
        return barra

    def _marcar_rodape(self, info):
        self._rodape.setText(f"v{info.versao} disponível - clique para ver")
        estilo.definir_propriedade(self._rodape, "novo", True)

    def selecionar(self, key: str):
        for k, b in self._botoes.items():
            estilo.definir_propriedade(b, "ativo", k == key)
            icones.reaplicar(b)
        if key not in self._views:  # instanciação lazy
            spec = next(s for s in VIEWS if s.key == key)
            self._views[key] = spec.factory(self.ctx)
            self._pilha.addWidget(self._views[key])
        self._pilha.setCurrentWidget(self._views[key])
        self._key_ativa = key
        # A view foi criada antes e ficou guardada: ela relê o que pode ter
        # mudado enquanto estava fora da tela (ex.: usuário do Aconex cadastrado
        # nas Configurações, que tem de aparecer na Extração).
        if (ao_exibir := getattr(self._views[key], "ao_exibir", None)) is not None:
            ao_exibir()

    def view_ativa(self):
        return self._views.get(self._key_ativa)

    # ------------------------------------------------------------------ update
    def verificar_na_abertura(self):
        """Toda abertura pergunta ao GitHub, sem intervalo mínimo (uma requisição
        por abertura fica muito abaixo do limite do token), e abre o aviso se
        houver versão nova. Erros vão para o log e somem: a abertura do app não
        pode depender do GitHub."""
        updater.verificar_em_segundo_plano(self.ctx.config, __version__,
                                           lambda info: na_ui(self._anunciar_e_avisar, info),
                                           intervalo_horas=0)
        self._periodica.start()

    def _anunciar_e_avisar(self, info):
        self.ctx.anunciar_atualizacao(info)
        QTimer.singleShot(self.AVISO_APOS_MS, self.abrir_atualizacao)

    def verificar_atualizacao(self, manual: bool = False):
        """Procura uma versão nova. `manual=True` (botão da barra lateral, das
        Configurações ou Ctrl+K) ignora o intervalo e a versão pulada, e SEMPRE
        responde: em dia, o erro, ou por que esta cópia não se atualiza."""
        if manual:
            self._verificar_agora()
            return
        updater.verificar_em_segundo_plano(
            self.ctx.config, __version__, lambda info: na_ui(self.ctx.anunciar_atualizacao, info))

    @staticmethod
    def tarefa_em_andamento() -> bool:
        return any(rb.rodando() for rb in list(RunBar.em_andamento))

    def _verificar_agora(self):
        """Checagem pedida pela pessoa: roda em thread mas fala o resultado."""
        if self._procurando:
            return   # clique repetido enquanto a primeira ainda responde
        if (motivo := updater.motivo_para_nao_verificar()):
            dialogos.info("Atualização automática", motivo, self)
            return
        self._procurando = True
        self._btn_procurar.setEnabled(False)
        self._btn_procurar.setText("Procurando...")

        def _fim():
            self._procurando = False
            self._btn_procurar.setEnabled(True)
            self._btn_procurar.setText(self.TEXTO_PROCURAR)

        def _erro(e):
            _fim()
            dialogos.aviso("Não foi possível verificar",
                           f"{e}\n\nVocê pode continuar usando o DocManager normalmente.", self)

        def _resposta(info):
            _fim()
            if info is None:
                dialogos.info("Tudo em dia", txt.em_dia(__version__), self)
                return
            self.ctx.anunciar_atualizacao(info)
            self.abrir_atualizacao()

        def _trabalho():
            try:
                info = updater.checar(__version__, canal_testes=updater.canal_de_testes(self.ctx.config))
            except Exception as e:  # noqa: BLE001 - aqui o erro É a resposta
                na_ui(_erro, e)
                return
            updater.registrar_verificacao(self.ctx.config)
            na_ui(_resposta, info)

        threading.Thread(target=_trabalho, daemon=True).start()

    def abrir_atualizacao(self):
        """Abre a janela da atualização já encontrada (ou procura uma, se não houver)."""
        info = self.ctx.atualizacao
        if info is None:
            self.verificar_atualizacao(True)
            return None
        aberto = self._dialogo_atualizacao
        if aberto is not None and aberto.isVisible():
            aberto.trazer_para_frente()   # nunca dois avisos
            return None
        from .views.update_dialog import AtualizacaoDialog
        self._dialogo_atualizacao = AtualizacaoDialog(
            self, info, __version__, fechar_app=self._fechar_para_instalar,
            ao_pular=lambda v: updater.ignorar_versao(self.ctx.config, v),
            tarefa_em_andamento=self.tarefa_em_andamento)
        self._dialogo_atualizacao.show()
        return self._dialogo_atualizacao

    def _fechar_para_instalar(self):
        """Sai de cena para o instalador poder sobrescrever os arquivos - o
        Windows não deixa regravar um .exe que está rodando. O `main()` encerra
        o processo em seguida (ver lá)."""
        self._saindo_para_atualizar = True
        self.close()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # ------------------------------------------------------------------ fechar
    def closeEvent(self, evento):  # noqa: N802 - nome do Qt
        """Fechar com uma tarefa rodando perguntaria nada e a interromperia no
        meio (um Excel pela metade, a extração parada). Pergunta - o padrão é
        NÃO fechar. Saindo para atualizar, a janela da atualização já perguntou."""
        if (not self._saindo_para_atualizar and self.tarefa_em_andamento()
                and not dialogos.perguntar(
                    "Tarefa em andamento",
                    "Há uma tarefa em andamento. Fechar o DocManager agora a interrompe.\n\n"
                    "Fechar mesmo assim?", padrao_nao=True, parent=self)):
            evento.ignore()
            return
        super().closeEvent(evento)

    # ------------------------------------------------------------------ erros
    def mostrar_erro_inesperado(self, tipo, valor, tb) -> None:
        """Erro num slot (thread da interface): vai para o log da tela ativa e
        numa caixa, já que no `.exe` ninguém vê o terminal."""
        msg = "".join(traceback.format_exception_only(tipo, valor)).strip()
        view = self.view_ativa()
        if view is not None and hasattr(view, "log"):
            view.log.log(f"ERRO: {msg}")
        dialogos.erro("Erro inesperado", msg, self)


# Nome do mutex do app. TEM QUE SER IGUAL ao `AppMutex` do installer/docmanager.iss:
# é por ele que o Inno Setup descobre que o DocManager está aberto e o fecha
# antes de sobrescrever os arquivos (a opção /CLOSEAPPLICATIONS da atualização).
NOME_MUTEX = "DocManagerItaipu_AppMutex"
_handle_mutex = None


def _registrar_mutex():
    """Cria o mutex nomeado do Windows. Sem ele o instalador não enxerga o app
    aberto e a atualização falha com 'arquivo em uso'."""
    global _handle_mutex
    if os.name != "nt":
        return
    try:
        import ctypes
        _handle_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, NOME_MUTEX)
    except Exception:  # noqa: BLE001 - sem mutex o app abre igual
        pass


def criar_app(argv=None) -> QApplication:
    """O QApplication com fonte, tema e folha do DocManager (reaproveita o que
    já existir - os testes criam o deles)."""
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("DocManager Itaipu")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(icone_do_app())
    estilo.carregar_fontes()
    return app


def main():
    from ..services import diario

    _registrar_mutex()
    diario.iniciar(__version__)
    # Quem vem da v3.0.0 tem as credenciais num .env: importa uma vez para o
    # cofre do app, para a lista da Extração não aparecer vazia depois de atualizar.
    try:
        from ..aconex_backend import migrar_env_para_cofre
        migrar_env_para_cofre()
    except Exception:  # noqa: BLE001 - migração nunca impede a abertura
        pass

    app = criar_app()
    config = ConfigManager()
    tema.aplicar(app, config.settings.tema)
    tema.seguir_o_sistema(app, config)
    janela = MainApp(config)

    gancho_anterior = sys.excepthook

    def _gancho(tipo, valor, tb):
        gancho_anterior(tipo, valor, tb)    # o do diário: grava o traceback
        try:
            janela.mostrar_erro_inesperado(tipo, valor, tb)
        except Exception:  # noqa: BLE001 - o gancho nunca pode levantar
            pass

    sys.excepthook = _gancho
    app.aboutToQuit.connect(diario.encerrar)

    # Fecha o splash NATIVO do PyInstaller (pyi_splash) - cobriu a carga desde o
    # duplo-clique no .exe. Em desenvolvimento não existe → ignora.
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:  # noqa: BLE001
        pass
    from .splash import mostrar_splash
    mostrar_splash(1600, ao_fechar=lambda: (janela.show(), janela.raise_(), janela.activateWindow()))
    app.exec()
    if janela._saindo_para_atualizar:
        # O instalador está esperando o mutex sumir, e ele só some com o fim do
        # PROCESSO. Sair na hora: uma thread de biblioteca ou um finalizador
        # lento segurando o processo faria a atualização desistir.
        os._exit(0)


if __name__ == "__main__":
    main()
