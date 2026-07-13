@echo off
REM ============================================================
REM  DocManager Itaipu - launcher (Windows)
REM  Cria o ambiente virtual na 1a vez, instala dependencias e
REM  abre o aplicativo. Basta dar duplo-clique neste arquivo.
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Criando ambiente virtual .venv ...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo ERRO: Python nao encontrado. Instale o Python 3.12+ e marque "Add to PATH".
        pause
        exit /b 1
    )
    call ".venv\Scripts\activate.bat"
    echo [2/3] Instalando dependencias (so na primeira vez)...
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
) else (
    call ".venv\Scripts\activate.bat"
)

echo [3/3] Iniciando DocManager...
python -m docmanager
if errorlevel 1 pause
