"""Janela principal: sidebar + roteador gerados por um REGISTRO declarativo de
views. Adicionar um módulo futuro (ex.: 'Lista de Documentos') = criar a view e
acrescentar um ViewSpec nesta lista."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk

from .. import __version__
from ..services import updater
from ..services.config import ConfigManager, resource_path
from . import theme as t
from .app_context import AppContext
from .components import NavItem
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
    ViewSpec("home", "Início", "🏠", HomeView),
    ViewSpec("mapa", "Mapa dos Planos", "🧭", MapaView),
    ViewSpec("doclist", "Doc List Mapping", "📑", DocListView),
    ViewSpec("status", "Status Documentos", "🔎", StatusDocsView),
    ViewSpec("historico", "Histórico e Dashboard", "📊", HistoricoView),
    ViewSpec("relatorios", "Relatórios", "📋", ReportsView),
    # Use SEMPRE emojis de apresentação colorida nativa (blocos U+1F3xx+), de
    # codepoint único. Símbolos "texto" com seletor U+FE0F (☁️ U+2601, ⚙️ U+2699)
    # o Windows renderiza com outra fonte: ink menor e largura diferente (o ☁️
    # media 47 px contra 27 px dos demais) → o item fica destoando na sidebar.
    ViewSpec("aconex", "Extração Aconex", "📥", AconexView),
    ViewSpec("config", "Configurações", "⚙️", ConfigView),
]


class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        t.aplicar()
        self.title(f"DocManager Itaipu - v{__version__}")
        self.geometry("1180x740")
        self.minsize(980, 640)
        self.configure(fg_color=t.FUNDO)

        try:
            ico = resource_path(os.path.join("assets", "logo_definitivo.ico"))
            if os.path.exists(ico):
                self.iconbitmap(ico)
        except Exception:
            pass

        self.ctx = AppContext(config=ConfigManager(), versao=__version__)
        self.ctx.navegar = self.selecionar   # Home usa para abrir módulos ao clicar
        self.ctx.abrir_atualizacao = self.abrir_atualizacao
        self.ctx.verificar_atualizacao = self.verificar_atualizacao
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._procurando = False              # checagem manual em andamento
        self._saindo_para_atualizar = False   # ver main()

        self._montar_sidebar()
        self._views: dict[str, ctk.CTkFrame] = {}
        self._botoes: dict[str, NavItem] = {}
        self._montar_botoes()
        self.selecionar(VIEWS[0].key)

        # Checagem automática: em thread, e só depois de a janela estar montada -
        # nada disso pode atrasar a abertura do app.
        self.after(1200, self._verificacao_periodica)

    def _montar_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=t.SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(99, weight=1)

        # Marca: logo definitivo do projeto + título.
        marca = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        marca.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 20))
        topo = ctk.CTkFrame(marca, fg_color="transparent")
        topo.pack(anchor="w", fill="x")
        logo = self._carregar_logo(44)
        if logo is not None:
            ctk.CTkLabel(topo, image=logo, text="").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(topo, text="DocManager", font=t.titulo(20), text_color=t.TEXTO).pack(side="left")
        ctk.CTkLabel(marca, text="Itaipu · Gestão Documental", font=t.corpo(11),
                     text_color=t.TEXTO_FRACO).pack(anchor="w", pady=(6, 0))

    def _carregar_logo(self, lado: int):
        """CTkImage do logo definitivo (assets), ou None se indisponível."""
        try:
            from PIL import Image
            caminho = resource_path(os.path.join("assets", "logo_definitivo.ico"))
            if not os.path.exists(caminho):
                return None
            img = Image.open(caminho)
            self._logo_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(lado, lado))
            return self._logo_ref
        except Exception:
            return None

    def _montar_botoes(self):
        for i, spec in enumerate(VIEWS, start=1):
            item = NavItem(self.sidebar, spec.icone, spec.label,
                           command=lambda k=spec.key: self.selecionar(k))
            item.grid(row=i, column=0, sticky="ew", padx=12, pady=2)
            self._botoes[spec.key] = item

        # Procurar atualização na hora, de qualquer tela - antes o botão só
        # existia dentro das Configurações. Mostra o resultado, inclusive o erro.
        self._btn_procurar = ctk.CTkButton(
            self.sidebar, text=self.TEXTO_PROCURAR, height=30, font=t.corpo(11),
            fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO, text_color=t.TEXTO,
            command=lambda: self.verificar_atualizacao(True))
        self._btn_procurar.grid(row=100, column=0, sticky="ew", padx=16, pady=(8, 0))

        # Rodapé: a versão instalada. Quando sai uma nova, este mesmo rótulo
        # vira o aviso - é o canto da tela onde a pessoa já olha para conferir
        # em que versão está, então é onde a novidade faz mais sentido.
        self._rodape = ctk.CTkLabel(self.sidebar, text=f"v{__version__}", font=t.corpo(10),
                                    text_color=t.TEXTO_FRACO, cursor="hand2")
        self._rodape.grid(row=101, column=0, sticky="w", padx=24, pady=(6, 16))
        self._rodape.bind("<Button-1>", lambda _e: self.abrir_atualizacao())
        self.ctx.ao_achar_atualizacao(
            lambda info: self.after(0, lambda: self._marcar_rodape(info)))

    def _marcar_rodape(self, info):
        try:
            self._rodape.configure(text=f"✨ v{info.versao} disponível",
                                   text_color=t.OK)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ update
    TEXTO_PROCURAR = "🔄  Procurar atualizações"

    # A checagem automática se repete enquanto o app fica aberto: quem deixa o
    # DocManager aberto a semana inteira também precisa ser avisado. Aqui só se
    # PERGUNTA de hora em hora; quem decide se é hora de ir ao GitHub é
    # `updater.deve_verificar` (no máximo a cada 6 h).
    VERIFICAR_A_CADA_MS = 60 * 60 * 1000

    def _verificacao_periodica(self):
        self.verificar_atualizacao(False)
        self.after(self.VERIFICAR_A_CADA_MS, self._verificacao_periodica)

    def verificar_atualizacao(self, manual: bool = False):
        """Procura uma versão nova. `manual=True` (botão da barra lateral ou das
        Configurações) ignora o intervalo e a versão pulada, e mostra o erro."""
        if manual:
            self._verificar_agora()
            return
        updater.verificar_em_segundo_plano(
            self.ctx.config, __version__,
            lambda info: self.after(0, lambda: self.ctx.anunciar_atualizacao(info)))

    def _verificar_agora(self):
        """Checagem pedida pela pessoa: roda em thread mas fala o resultado."""
        import threading
        from tkinter import messagebox

        if self._procurando:
            return   # clique repetido enquanto a primeira ainda responde
        self._procurando = True
        self._btn_procurar.configure(state="disabled", text="Procurando...")

        def _fim():
            self._procurando = False
            self._btn_procurar.configure(state="normal", text=self.TEXTO_PROCURAR)

        def _trabalho():
            try:
                info = updater.checar(__version__)
            except Exception as e:  # noqa: BLE001 - aqui o erro É a resposta
                self.after(0, lambda erro=e: (_fim(), messagebox.showwarning(
                    "Não foi possível verificar",
                    f"{erro}\n\nVocê pode continuar usando o DocManager normalmente.")))
                return
            updater.registrar_verificacao(self.ctx.config)
            if info is None:
                self.after(0, lambda: (_fim(), messagebox.showinfo(
                    "Tudo em dia", f"Você já está na versão mais recente (v{__version__}).")))
                return
            self.after(0, lambda: (_fim(), self.ctx.anunciar_atualizacao(info),
                                   self.abrir_atualizacao()))

        threading.Thread(target=_trabalho, daemon=True).start()

    def abrir_atualizacao(self):
        """Abre a janela da atualização já encontrada (ou procura uma, se não houver)."""
        info = self.ctx.atualizacao
        if info is None:
            self.verificar_atualizacao(True)
            return
        from .views.update_dialog import AtualizacaoDialog
        AtualizacaoDialog(self, info, __version__,
                          fechar_app=self._fechar_para_instalar,
                          ao_pular=lambda v: updater.ignorar_versao(self.ctx.config, v))

    def _fechar_para_instalar(self):
        """Sai de cena para o instalador poder sobrescrever os arquivos - o
        Windows não deixa regravar um .exe que está rodando. O `main()` encerra
        o processo em seguida (ver lá)."""
        self._saindo_para_atualizar = True
        try:
            self.quit()
            self.destroy()
        except Exception:  # noqa: BLE001
            pass

    def selecionar(self, key: str):
        for k, item in self._botoes.items():
            item.set_ativo(k == key)
        for k, v in self._views.items():
            v.grid_forget()
        if key not in self._views:  # instanciação lazy
            spec = next(s for s in VIEWS if s.key == key)
            self._views[key] = spec.factory(self, self.ctx)
        self._views[key].grid(row=0, column=1, sticky="nsew")
        self._key_ativa = key
        # A view foi criada antes e ficou guardada: ela relê o que pode ter
        # mudado enquanto estava fora da tela (ex.: usuário do Aconex cadastrado
        # nas Configurações, que tem de aparecer na Extração). A Home não herda
        # de BaseView, daí o getattr.
        if (ao_exibir := getattr(self._views[key], "ao_exibir", None)) is not None:
            ao_exibir()

    def report_callback_exception(self, exc, val, tb):
        """Erros em callbacks (main thread) vão para o log da view ativa + popup,
        já que o usuário não vê o terminal."""
        import traceback
        from tkinter import messagebox
        msg = "".join(traceback.format_exception_only(exc, val)).strip()
        view = self._views.get(getattr(self, "_key_ativa", None))
        if view is not None and hasattr(view, "log"):
            try:
                view.log.log(f"ERRO: {msg}")
            except Exception:  # noqa: BLE001
                pass
        try:
            messagebox.showerror("Erro inesperado", msg)
        except Exception:  # noqa: BLE001
            pass


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


def main():
    _registrar_mutex()
    # Quem vem da v3.0.0 tem as credenciais num .env: importa uma vez para o
    # cofre do app, para a lista da Extração não aparecer vazia depois de atualizar.
    try:
        from ..aconex_backend import migrar_env_para_cofre
        migrar_env_para_cofre()
    except Exception:  # noqa: BLE001 - migração nunca impede a abertura
        pass

    app = MainApp()
    app.withdraw()   # oculta enquanto a splash aparece
    # Fecha o splash NATIVO do PyInstaller (pyi_splash) - cobriu a carga desde o
    # duplo-clique no .exe. Em desenvolvimento não existe → ignora.
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:  # noqa: BLE001
        pass
    from .splash import mostrar_splash
    mostrar_splash(app, ms=1600, ao_fechar=lambda: (app.deiconify(), app.lift()))
    app.mainloop()
    if app._saindo_para_atualizar:
        # O instalador está esperando o mutex sumir, e ele só some com o fim do
        # PROCESSO. Sair na hora: uma thread de biblioteca ou um finalizador
        # lento segurando o processo faria a atualização desistir.
        os._exit(0)


if __name__ == "__main__":
    main()
