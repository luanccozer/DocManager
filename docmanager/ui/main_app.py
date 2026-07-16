"""Janela principal: sidebar + roteador gerados por um REGISTRO declarativo de
views. Adicionar um módulo futuro (ex.: 'Lista de Documentos') = criar a view e
acrescentar um ViewSpec nesta lista."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

import customtkinter as ctk

from .. import __version__
from ..services.config import ConfigManager, resource_path
from . import theme as t
from .app_context import AppContext
from .components import NavItem
from .views.aconex_view import AconexView
from .views.config_view import ConfigView
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
    ViewSpec("status", "Status Documentos", "🔎", StatusDocsView),
    ViewSpec("historico", "Histórico e Dashboard", "📊", HistoricoView),
    ViewSpec("relatorios", "Relatórios", "📋", ReportsView),
    ViewSpec("aconex", "Extração Aconex", "☁️", AconexView),
    ViewSpec("config", "Configurações", "⚙️", ConfigView),
]


class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        t.aplicar()
        self.title(f"DocManager Itaipu — v{__version__}")
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
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._montar_sidebar()
        self._views: dict[str, ctk.CTkFrame] = {}
        self._botoes: dict[str, NavItem] = {}
        self._montar_botoes()
        self.selecionar(VIEWS[0].key)

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

        rodape = ctk.CTkLabel(self.sidebar, text=f"v{__version__}", font=t.corpo(10),
                              text_color=t.TEXTO_FRACO)
        rodape.grid(row=100, column=0, sticky="w", padx=24, pady=16)

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
        # Reavalia estado dependente de config (ex.: rótulo do toggle VIP no Mapa)
        if hasattr(self._views[key], "_atualizar_vip"):
            self._views[key]._atualizar_vip()

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


def main():
    app = MainApp()
    app.withdraw()   # oculta enquanto a splash aparece
    # Fecha o splash NATIVO do PyInstaller (pyi_splash) — cobriu a carga desde o
    # duplo-clique no .exe. Em desenvolvimento não existe → ignora.
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:  # noqa: BLE001
        pass
    from .splash import mostrar_splash
    mostrar_splash(app, ms=1600, ao_fechar=lambda: (app.deiconify(), app.lift()))
    app.mainloop()


if __name__ == "__main__":
    main()
