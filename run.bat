@echo off
REM ============================================================
REM  DocManager Itaipu - launcher (Windows)
REM  Duplo-clique: prepara o ambiente na 1a vez e abre o aplicativo.
REM
REM  Rede corporativa (Zscaler): crie um arquivo pip_corporativo.txt
REM  na pasta do projeto com os seus argumentos de pip numa unica
REM  linha, por exemplo:
REM    --index-url https://SEU-MIRROR/simple --trusted-host SEU-HOST
REM  ou defina a variavel de ambiente DOCMANAGER_PIP_ARGS.
REM
REM  AO EDITAR: dentro de um bloco "if ( ... )" um parentese solto
REM  num echo FECHA o bloco e quebra o script inteiro. Escape com ^) .
REM ============================================================
setlocal EnableExtensions
pushd "%~dp0"

set "PIP_ARGS="
if defined DOCMANAGER_PIP_ARGS set "PIP_ARGS=%DOCMANAGER_PIP_ARGS%"
if exist "pip_corporativo.txt" set /p PIP_ARGS=<pip_corporativo.txt

REM --- Escolha do ambiente virtual ----------------------------------
REM Ordem: .venv do projeto > C:\venvs\docmanager > cria um novo.
REM Um venv NOVO vai para o LOCALAPPDATA, nunca para dentro do projeto:
REM esta pasta esta no OneDrive, e sincronizar os milhares de arquivos
REM de um venv deixa tudo lento e chega a travar a instalacao.
set "VENV=%LOCALAPPDATA%\DocManagerItaipu\venv"
if exist "C:\venvs\docmanager\Scripts\python.exe" set "VENV=C:\venvs\docmanager"
if exist ".venv\Scripts\python.exe" set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%PY%" (
    echo [1/3] Criando o ambiente virtual em:
    echo        %VENV%
    py -3.12 -m venv "%VENV%" 2>nul || py -3 -m venv "%VENV%" 2>nul || python -m venv "%VENV%"
    if not exist "%PY%" (
        echo.
        echo ERRO: nao foi possivel criar o ambiente virtual.
        echo Instale o Python 3.12 ou superior marcando "Add Python to PATH".
        pause
        popd
        exit /b 1
    )
    echo [2/3] Instalando as dependencias. Leva alguns minutos, so na primeira vez...
    if defined PIP_ARGS echo        usando pip args: %PIP_ARGS%
    "%PY%" -m pip install %PIP_ARGS% --upgrade pip
    "%PY%" -m pip install %PIP_ARGS% -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERRO ao instalar as dependencias.
        echo Na rede da empresa, crie o arquivo pip_corporativo.txt com
        echo --index-url e --trusted-host. Veja o README.md.
        pause
        popd
        exit /b 1
    )
)

echo [3/3] Iniciando o DocManager...
"%PY%" -m docmanager
if errorlevel 1 (
    echo.
    echo O aplicativo terminou com erro. Leia a mensagem acima.
    pause
)
popd
