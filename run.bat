@echo off
REM ============================================================
REM  DocManager Itaipu - launcher (Windows)
REM  Cria o ambiente virtual na 1a vez, instala dependencias e
REM  abre o aplicativo. Basta dar duplo-clique neste arquivo.
REM
REM  Rede corporativa (Zscaler): crie um arquivo pip_corporativo.txt
REM  na pasta do projeto com os seus argumentos de pip numa unica
REM  linha, por exemplo:
REM    --isolated --index-url https://SEU-MIRROR/simple --trusted-host SEU-HOST
REM  (ou defina a variavel de ambiente DOCMANAGER_PIP_ARGS).
REM ============================================================
setlocal
cd /d "%~dp0"

set "PIP_ARGS="
if defined DOCMANAGER_PIP_ARGS set "PIP_ARGS=%DOCMANAGER_PIP_ARGS%"
if exist "pip_corporativo.txt" set /p PIP_ARGS=<pip_corporativo.txt

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
    if defined PIP_ARGS echo      usando pip args: %PIP_ARGS%
    python -m pip install %PIP_ARGS% --upgrade pip
    python -m pip install %PIP_ARGS% -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERRO ao instalar dependencias. Se estiver na rede da empresa (Zscaler),
        echo crie o arquivo pip_corporativo.txt com --index-url/--trusted-host. Veja o README.
        pause
        exit /b 1
    )
) else (
    call ".venv\Scripts\activate.bat"
)

echo [3/3] Iniciando DocManager...
python -m docmanager
if errorlevel 1 pause
