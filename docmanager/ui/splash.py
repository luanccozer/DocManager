"""Splash de abertura: janela SEM bordas com o logo enquanto o app carrega.
Fecha sozinha e revela a janela principal.

Feita em tkinter PURO (e não CTkToplevel) de propósito. O CTkToplevel registra a
janela no ScalingTracker do CustomTkinter, que redetecta o DPI DEPOIS de a janela
já estar na tela e reaplica a geometria escalada — em telas corporativas com
escala de 125/150% isso fazia a splash "pular" de tamanho ao abrir (no notebook a
100% a escala já batia, então lá não pulava). Aqui o DPI é lido UMA vez, tudo é
montado escondido e em pixels físicos, e a janela só aparece pronta: sem reflow,
sem pulo, igual em qualquer máquina.
"""
from __future__ import annotations

import os
import tkinter as tk

from .. import __version__
from . import theme as t


def _carregar_logo(app, lado_px: int):
    """PhotoImage do logo definitivo redimensionado, ou None se indisponível."""
    try:
        from PIL import Image, ImageTk

        from ..services.config import resource_path
        caminho = resource_path(os.path.join("assets", "logo_definitivo.ico"))
        if not os.path.exists(caminho):
            return None
        img = Image.open(caminho).convert("RGBA").resize((lado_px, lado_px), Image.LANCZOS)
        ref = ImageTk.PhotoImage(img)
        app._splash_logo_ref = ref  # mantém referência (evita coleta de lixo)
        return ref
    except Exception:  # noqa: BLE001
        return None


def _escala_dpi(win) -> float:
    """Fator de escala do monitor (1.0 = 96 dpi/100%). Lido uma vez, à prova de erro.

    O processo já é DPI-aware (o CustomTkinter chama SetProcessDpiAwareness), então
    `winfo_fpixels('1i')` devolve o DPI real do monitor.
    """
    try:
        return min(max(win.winfo_fpixels("1i") / 96.0, 1.0), 3.0)
    except Exception:  # noqa: BLE001
        return 1.0


def mostrar_splash(app, *, ms: int = 1600, ao_fechar=None):
    """Mostra a splash sobre `app` (que deve estar oculta). Após `ms`, fecha e
    chama `ao_fechar` (tipicamente `app.deiconify`)."""
    try:
        sp = tk.Toplevel(app)
        sp.withdraw()                 # monta escondida — sem flash nem reflow
        sp.overrideredirect(True)
        sp.configure(bg=t.ACENTO)     # o fundo de acento faz de "borda" de 2 px

        esc = _escala_dpi(sp)

        def px(v: int) -> int:
            return max(1, round(v * esc))

        W, H, borda = px(430), px(250), px(2)
        sp.geometry(f"{W}x{H}")       # tamanho já correto antes de montar

        inner = tk.Frame(sp, bg=t.SIDEBAR)
        inner.place(x=borda, y=borda, width=W - 2 * borda, height=H - 2 * borda)
        cx = (W - 2 * borda) // 2     # centro horizontal do miolo

        y = px(30)
        logo = _carregar_logo(app, px(84))
        if logo is not None:
            tk.Label(inner, image=logo, bg=t.SIDEBAR, bd=0).place(x=cx, y=y, anchor="n")
            y += px(84) + px(14)
        else:
            y += px(20)

        tk.Label(inner, text="DocManager Itaipu", bg=t.SIDEBAR, fg=t.TEXTO,
                 font=("Segoe UI", -px(24), "bold")).place(x=cx, y=y, anchor="n")
        y += px(24) + px(12)
        tk.Label(inner, text=f"Gestão documental · CMI ↔ Itaipu · v{__version__}",
                 bg=t.SIDEBAR, fg=t.TEXTO_FRACO,
                 font=("Segoe UI", -px(12))).place(x=cx, y=y, anchor="n")
        y += px(12) + px(20)

        # Barra indeterminada (marquee) desenhada num Canvas — dá o "dinâmico" da
        # splash sem depender de ttk/CTk (e sem os efeitos colaterais de escala).
        bw, bh = px(250), px(6)
        canvas = tk.Canvas(inner, width=bw, height=bh, bg=t.CARD_BORDA,
                           highlightthickness=0, bd=0)
        canvas.place(x=cx, y=y, anchor="n")
        seg = max(px(60), bw // 3)
        passo = max(px(4), 4)
        estado = {"x": -seg, "vivo": True, "after": None}

        def _animar():
            if not estado["vivo"] or not canvas.winfo_exists():
                return
            canvas.delete("seg")
            estado["x"] += passo
            if estado["x"] > bw:
                estado["x"] = -seg
            x0, x1 = max(0, estado["x"]), min(bw, estado["x"] + seg)
            if x1 > x0:
                canvas.create_rectangle(x0, 0, x1, bh, fill=t.ACENTO, width=0, tags="seg")
            estado["after"] = sp.after(16, _animar)

        # Só agora revela: centralizada, no tamanho final, de uma vez.
        sp.update_idletasks()
        x = (sp.winfo_screenwidth() - W) // 2
        yy = (sp.winfo_screenheight() - H) // 2
        sp.geometry(f"{W}x{H}+{x}+{yy}")
        sp.deiconify()
        sp.lift()
        sp.attributes("-topmost", True)
        _animar()
    except Exception:  # noqa: BLE001 — se a splash falhar, segue direto para o app
        if ao_fechar:
            ao_fechar()
        return None

    def _fim():
        try:
            estado["vivo"] = False
            if estado["after"] is not None:
                sp.after_cancel(estado["after"])
            sp.destroy()
        except Exception:  # noqa: BLE001
            pass
        if ao_fechar:
            ao_fechar()

    app.after(ms, _fim)
    return sp
