"""Splash de abertura (como no legado): janela sem bordas com o logo enquanto o
app carrega. Fecha sozinha e revela a janela principal."""
from __future__ import annotations

import os

import customtkinter as ctk

from .. import __version__
from . import theme as t


def _logo(app, lado: int):
    try:
        from PIL import Image

        from ..services.config import resource_path
        caminho = resource_path(os.path.join("assets", "logo_definitivo.ico"))
        if not os.path.exists(caminho):
            return None
        img = Image.open(caminho)
        ref = ctk.CTkImage(light_image=img, dark_image=img, size=(lado, lado))
        app._splash_logo_ref = ref  # evita coleta de lixo
        return ref
    except Exception:  # noqa: BLE001
        return None


def mostrar_splash(app, *, ms: int = 1600, ao_fechar=None):
    """Mostra a splash sobre a janela `app` (que deve estar oculta). Após `ms`,
    fecha e chama `ao_fechar` (tipicamente `app.deiconify`)."""
    try:
        sp = ctk.CTkToplevel(app)
        sp.overrideredirect(True)
        sp.configure(fg_color=t.SIDEBAR)
        W, H = 440, 280
        x = (sp.winfo_screenwidth() - W) // 2
        y = (sp.winfo_screenheight() - H) // 2
        sp.geometry(f"{W}x{H}+{x}+{y}")
        sp.attributes("-topmost", True)

        frame = ctk.CTkFrame(sp, fg_color=t.SIDEBAR, corner_radius=0,
                             border_width=1, border_color=t.ACENTO)
        frame.pack(fill="both", expand=True)
        logo = _logo(app, 100)
        if logo is not None:
            ctk.CTkLabel(frame, image=logo, text="").pack(pady=(42, 12))
        ctk.CTkLabel(frame, text="DocManager Itaipu", font=t.titulo(24),
                     text_color=t.TEXTO).pack()
        # Versão vinda do .env (VERSAO) — mesma fonte do título/sidebar/Home.
        ctk.CTkLabel(frame, text=f"Gestão documental · CMI ↔ Itaipu · v{__version__}",
                     font=t.corpo(12), text_color=t.TEXTO_FRACO).pack(pady=(4, 18))
        barra = ctk.CTkProgressBar(frame, width=260, height=6, progress_color=t.ACENTO,
                                   mode="indeterminate")
        barra.pack()
        barra.start()
    except Exception:  # noqa: BLE001 — se a splash falhar, segue direto para o app
        if ao_fechar:
            ao_fechar()
        return None

    def _fim():
        try:
            barra.stop()
            sp.destroy()
        except Exception:  # noqa: BLE001
            pass
        if ao_fechar:
            ao_fechar()

    app.after(ms, _fim)
    return sp
