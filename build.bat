@echo off
REM ============================================================
REM  DocManager Itaipu - GERADOR DO EXECUTAVEL (onedir)
REM  Duplo-clique para gerar dist\DocManager\DocManager.exe
REM
REM  Rede corporativa (Zscaler): crie pip_corporativo.txt com os
REM  seus argumentos de pip (--index-url/--trusted-host), igual ao run.bat.
REM ============================================================
setlocal
cd /d "%~dp0"

set "PIP_ARGS="
if defined DOCMANAGER_PIP_ARGS set "PIP_ARGS=%DOCMANAGER_PIP_ARGS%"
if exist "pip_corporativo.txt" set /p PIP_ARGS=<pip_corporativo.txt

REM Ativa um ambiente virtual (prioriza o .venv do projeto; senao C:\venvs\docmanager).
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "C:\venvs\docmanager\Scripts\activate.bat" (
    call "C:\venvs\docmanager\Scripts\activate.bat"
) else (
    echo ERRO: nenhum ambiente virtual encontrado. Rode o run.bat uma vez para criar o .venv.
    pause
    exit /b 1
)

echo [1/3] Instalando/atualizando dependencias + PyInstaller...
python -m pip install %PIP_ARGS% -r requirements.txt
python -m pip install %PIP_ARGS% "pyinstaller>=6,<7"
if errorlevel 1 (
    echo ERRO ao instalar. Na rede da empresa, use o pip_corporativo.txt. Veja o BUILD.md.
    pause
    exit /b 1
)

echo [2/3] Limpando build anterior...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [3/3] Gerando o executavel (onedir)...
pyinstaller docmanager.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ERRO no PyInstaller. Se faltar algum modulo em tempo de execucao, veja o BUILD.md
    echo (secao "hidden imports") e me avise o nome do modulo para acrescentar no .spec.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  PRONTO: dist\DocManager\DocManager.exe
echo.
echo  ULTIMO PASSO OBRIGATORIO: copie o seu arquivo .env para
echo  dist\DocManager\  (ao lado do DocManager.exe), com VERSAO
echo  e o SECRET_ do usuario. Sem o .env a extracao nao funciona.
echo ============================================================
pause
