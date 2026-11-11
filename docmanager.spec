# -*- mode: python ; coding: utf-8 -*-
"""Build ONEDIR do DocManager Itaipu (recomendado para o corporativo).

Gera dist/DocManager/DocManager.exe + a pasta de dependências ao lado.
Rode dentro do venv com PyInstaller instalado:

    pyinstaller docmanager.spec --noconfirm

A versão do build vem de `docmanager/_build_info.py` (o CI a escreve a partir da
tag). Credenciais do Aconex NÃO entram aqui: desde a v3.1.0 elas são cadastradas
dentro do app e guardadas em Documentos\\DocManager_Itaipu - nenhum segredo é
empacotado no executável.
"""
from PyInstaller.utils.hooks import collect_all

# dash/dbc/plotly/truststore trazem dados e submódulos que o PyInstaller não
# descobre sozinho - collect_all pega datas + binaries + imports. O PySide6 tem
# hook próprio no PyInstaller (leva só os módulos do Qt que o app importa).
_datas, _binaries, _hidden = [], [], []
# playwright: o driver (node + pacote JS) vem como dado do pacote; sem ele o robô do
# Upload de documentos não abre o Chrome.
for _pkg in ("dash", "dash_bootstrap_components", "plotly", "truststore", "certifi", "playwright"):
    d, b, h = collect_all(_pkg)
    _datas += d
    _binaries += b
    _hidden += h

# Assets do app (logo/ícone) embutidos.
_datas += [("assets", "assets")]
# CHANGELOG na raiz do bundle: é dele que a Home tira "O que há de novo"
# (services/novidades.py) - sem isto a seção some no executável.
_datas += [("CHANGELOG.md", ".")]
# Ícones SVG e a fonte Roboto da interface Qt: ficam ao lado dos .pyc da UI
# (`ui/estilo.py` os acha pelo próprio caminho do módulo).
_datas += [("docmanager/ui/recursos", "docmanager/ui/recursos")]
# Modelo e bibliotecas de gráfico do painel HTML da UG (dashboard/painel_ug_html.py
# os acha pelo próprio caminho do módulo).
_datas += [("docmanager/dashboard/recursos", "docmanager/dashboard/recursos")]

# Reforço de imports que costumam escapar da análise estática.
_hidden += [
    "truststore", "openpyxl", "xlsxwriter",
    "pandas", "dash_bootstrap_components", "plotly.graph_objs",
    # QtSvg desenha os ícones; é importado dentro de ui/icones.py.
    "PySide6.QtSvg",
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
    # O NOSSO código fica fora do DocManager.exe, como .pyc soltos em
    # _internal\docmanager\. Sem isto ele ia para dentro do .exe junto com a
    # parte em Python de pandas/plotly/dash (~30 MB), e como a versão está no
    # código o .exe mudava inteiro a cada Release: a atualização "só do que
    # mudou" levaria esses 30 MB sempre. Assim, mudar uma tela troca um .pyc;
    # o .exe só muda quando muda uma biblioteca (ver constraints-build.txt).
    module_collection_mode={"docmanager": "pyc"},
)
pyz = PYZ(a.pure)

# Splash NATIVO: aparece já no duplo-clique, cobrindo a carga do Python/libs.
# A splash do Qt (ui/splash.py) assume com a MESMA imagem e a fecha
# (`pyi_splash.close()`, em ui/main_app.abrir()) sem troca visível de tela.
# A imagem é a de CARREGAMENTO (logo + "Carregando...", SEM barra), gerada por
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
