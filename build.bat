@echo off
REM ============================================================
REM  DocManager Itaipu - BUILD LOCAL (plano B)
REM
REM  O jeito NORMAL de gerar uma versao e pelo GitHub: basta criar
REM  a tag (git tag v3.1.1 ^&^& git push origin v3.1.1) que o
REM  workflow monta o executavel, o instalador e publica o Release.
REM  Veja o BUILD.md.
REM
REM  Este .bat serve para (a) testar o empacotamento na sua maquina
REM  antes de criar a tag, ou (b) gerar um build quando o GitHub
REM  Actions estiver indisponivel.
REM
REM  ATENCAO: o build local sai SEM o token de atualizacao, ou seja,
REM  o executavel gerado aqui NAO avisa de versoes novas. Para
REM  distribuir de verdade, use a tag.
REM
REM  Rede corporativa (Zscaler): crie pip_corporativo.txt com os
REM  seus argumentos de pip --index-url/--trusted-host, igual ao run.bat.
REM
REM  AO EDITAR: dentro de um bloco "if ( ... )" um parentese solto
REM  num echo FECHA o bloco e quebra o script inteiro. Escape com ^) .
REM ============================================================
setlocal
cd /d "%~dp0"

REM --- Argumentos do pip --------------------------------------------
set "PIP_ARGS=--isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org"
if defined DOCMANAGER_PIP_ARGS set "PIP_ARGS=%DOCMANAGER_PIP_ARGS%"
if exist "pip_corporativo.txt" set /p PIP_ARGS=<pip_corporativo.txt

REM Ativa um ambiente virtual (prioriza o .venv do projeto; senao C:\venvs\docmanager).
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "C:\venvs\docmanager\Scripts\activate.bat" (
    call "C:\venvs\docmanager\Scripts\activate.bat"
) else if exist "%LOCALAPPDATA%\DocManagerItaipu\venv\Scripts\activate.bat" (
    call "%LOCALAPPDATA%\DocManagerItaipu\venv\Scripts\activate.bat"
) else (
    echo ERRO: nenhum ambiente virtual encontrado. Rode o run.bat uma vez para criar o venv.
    pause
    exit /b 1
)

echo [1/4] Instalando/atualizando dependencias + PyInstaller...
python -m pip install %PIP_ARGS% -r requirements.txt
python -m pip install %PIP_ARGS% "pyinstaller>=6,<7"
if errorlevel 1 (
    echo ERRO ao instalar. Na rede da empresa, use o pip_corporativo.txt. Veja o BUILD.md.
    pause
    exit /b 1
)

echo [2/4] Carimbando a versao no build...
REM Sem isto o executavel usaria a versao que estiver no _build_info.py.
REM Passe a versao desejada como argumento: build.bat 3.1.1
set "VERSAO=%~1"
if "%VERSAO%"=="" (
    for /f "usebackq tokens=*" %%v in (`python -c "import sys;sys.path.insert(0,'.');from docmanager._build_info import VERSAO;print(VERSAO)"`) do set "VERSAO=%%v"
)
python tools\preparar_build.py %VERSAO% --origem local
if errorlevel 1 (
    echo ERRO ao preparar o build. Versao invalida? Use: build.bat 3.1.1
    pause
    exit /b 1
)

echo [3/4] Limpando build anterior...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo [4/4] Gerando o executavel. Leva cerca de 2 MINUTOS.
echo        NAO FECHE esta janela: o .exe so aparece no fim, na ultima etapa.
echo.
pyinstaller docmanager.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ERRO no PyInstaller. Se faltar algum modulo em tempo de execucao,
    echo veja a secao "hidden imports" do BUILD.md e acrescente o modulo no .spec.
    pause
    exit /b 1
)

REM O .exe e copiado para o dist so na ultima etapa. Se ele nao existe, o build
REM foi interrompido ou o antivirus removeu o arquivo.
if not exist "dist\DocManager\DocManager.exe" (
    echo.
    echo ERRO: o executavel NAO foi gerado.
    echo Causas comuns:
    echo   - a janela foi fechada antes do fim do build;
    echo   - o antivirus removeu o DocManager.exe recem-criado.
    echo Rode o build.bat de novo sem fechar a janela e, se persistir,
    echo peca ao TI para liberar a pasta dist do projeto.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  PRONTO: dist\DocManager\DocManager.exe   ^(v%VERSAO%^)
echo.
echo  NAO e mais preciso copiar nenhum .env: as credenciais do
echo  Aconex sao cadastradas DENTRO do app ^(Extracao Aconex -^>
echo  Cadastrar usuario^) e ficam em Documentos\DocManager_Itaipu.
echo.
echo  Para gerar o instalador a partir desta pasta:
echo     iscc /DMyAppVersion=%VERSAO% installer\docmanager.iss
echo.
echo  LEMBRE-SE: este build NAO tem atualizacao automatica.
echo  Para distribuir de verdade, crie a tag e deixe o GitHub
echo  montar tudo:   git tag v%VERSAO%  ^&^&  git push origin v%VERSAO%
echo ============================================================
pause
