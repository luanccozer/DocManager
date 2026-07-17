# -*- mode: python ; coding: utf-8 -*-
"""Build ONEDIR do DocManager Itaipu (recomendado para o corporativo).

Gera dist/DocManager/DocManager.exe + a pasta de dependências ao lado.
Rode dentro do venv com PyInstaller instalado:

    pyinstaller docmanager.spec --noconfirm

Depois: coloque o `.env` (com VERSAO e SECRET_<USUÁRIO>) AO LADO do .exe
(dist/DocManager/.env). O .env NUNCA é embutido no executável.
"""
from PyInstaller.utils.hooks import collect_all

# dash/dbc/plotly/customtkinter/truststore trazem dados e submódulos que o
# PyInstaller não descobre sozinho — collect_all pega datas + binaries + imports.
_datas, _binaries, _hidden = [], [], []
for _pkg in ("dash", "dash_bootstrap_components", "plotly",
             "customtkinter", "truststore", "certifi"):
    d, b, h = collect_all(_pkg)
    _datas += d
    _binaries += b
    _hidden += h

# Assets do app (logo/ícone) embutidos.
_datas += [("assets", "assets")]

# Reforço de imports que costumam escapar da análise estática.
_hidden += [
    "truststore", "openpyxl", "xlsxwriter", "PIL", "PIL._tkinter_finder",
    "pandas", "dash_bootstrap_components", "plotly.graph_objs",
]

a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "test", "tests", "pytest", "_pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

# Splash NATIVO: aparece já no duplo-clique, cobrindo a carga do Python/libs.
# Fechado por `pyi_splash.close()` em ui/main_app.main() quando o app fica pronto.
# A imagem é a de CARREGAMENTO (barra + "Carregando..."), gerada por
# tools/gerar_splash.py com as cores do tema. NÃO usar assets/logo_final.png:
# aquilo é um placeholder antigo ("DM placeholder"), herdado do legado.
splash = Splash(
    "assets/splash.png",
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,                       # tela de carregamento
    [],
    exclude_binaries=True,        # ONEDIR: binários vão para o COLLECT
    name="DocManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                    # UPX costuma disparar antivírus corporativo
    console=False,                # app GUI (sem janela de console)
    disable_windowed_traceback=False,
    icon="assets/logo_definitivo.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    splash.binaries,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DocManager",
)
