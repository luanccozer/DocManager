; ============================================================
;  DocManager Itaipu - Instalador (Inno Setup 6+)
;
;  Normalmente NAO e compilado a mao: o workflow
;  .github/workflows/release.yml roda o build e o ISCC a cada tag v*.
;
;  Compilar localmente (precisa do dist\DocManager\ pronto pelo build.bat):
;      iscc /DMyAppVersion=3.1.0 installer\docmanager.iss
;  Saida: installer\Output\DocManager_Itaipu_Setup.exe
; ============================================================

; A versao vem do build (`iscc /DMyAppVersion=...`). O valor abaixo e so o
; padrao de quem compila na mao sem passar nada.
#ifndef MyAppVersion
  #define MyAppVersion "3.1.0"
#endif

; VersionInfoVersion e o numero de versao BINARIO do Windows (o que aparece nas
; Propriedades do arquivo) e so aceita DIGITOS: "3.1.0-rc.1" faz o Inno abortar
; com 'Value of [Setup] section directive "VersionInfoVersion" is invalid'.
; Por isso o pre-lancamento tem duas versoes: a de exibicao, com o sufixo, e
; esta, so numerica. O workflow calcula e passa /DMyVersionInfo=3.1.0; quem
; compilar na mao um pre-lancamento precisa passar tambem.
#ifndef MyVersionInfo
  #define MyVersionInfo MyAppVersion
#endif

#define AppName "DocManager Itaipu"
#define AppExe "DocManager.exe"

[Setup]
AppId={{7C3B2A10-DOCM-4ITA-IPU0-DOCMANAGER01}}
AppName={#AppName}
AppVersion={#MyAppVersion}
AppVerName={#AppName} {#MyAppVersion}
VersionInfoVersion={#MyVersionInfo}
AppPublisher=CMI - Engenharia
AppUpdatesURL=https://github.com/luanccozer/DocManager/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=DocManager_Itaipu_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\logo_definitivo.ico
UninstallDisplayIcon={app}\{#AppExe}

; --- Escopo da instalacao -----------------------------------------------
; O padrao continua sendo "para todos" (Program Files, com admin), mas o
; instalador PERGUNTA. Quem nao tem senha de administrador escolhe "somente
; para mim" e vai para %LOCALAPPDATA%\Programs — e ai a atualizacao automatica
; roda sem nenhum popup do UAC.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline

; --- Atualizacao por cima da versao anterior ----------------------------
; AppMutex e a peca que faz a atualizacao funcionar: o app cria este mutex
; nomeado ao abrir (ui/main_app.py, NOME_MUTEX). Com ele o Inno DESCOBRE que o
; DocManager esta rodando e o fecha antes de trocar os arquivos — sem isso a
; instalacao falha com "arquivo em uso", que e o sintoma classico de
; auto-update quebrado. Os dois nomes TEM que ser iguais.
AppMutex=DocManagerItaipu_AppMutex
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Files]
; Toda a pasta onedir gerada pelo PyInstaller.
Source: "..\dist\DocManager\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Restos do build antigo (pyc/cache) que nao constam no manifesto de instalacao.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Messages]
; As credenciais agora sao cadastradas DENTRO do app; nao existe mais .env para
; a pessoa copiar. A mensagem final diz exatamente o que fazer na 1a abertura.
brazilianportuguese.FinishedLabel=Instalacao concluida.%n%nPRIMEIRO USO: para a Extracao Aconex funcionar, abra o DocManager, va em "Extracao Aconex" e clique em CADASTRAR USUARIO. Informe o Client ID (APP ID), o User ID e o Client Secret que o administrador do Aconex forneceu para voce.%n%nE uma vez so: os dados ficam guardados nesta maquina, cifrados pelo Windows, e continuam valendo depois de cada atualizacao.%n%nOs demais modulos (Mapa, Doc List, Status, Historico, Relatorios) funcionam sem cadastro nenhum.
