; ============================================================
;  DocManager Itaipu - Instalador (Inno Setup 6+)
;  Gera um instalador amigavel a partir de dist\DocManager\.
;
;  Pre-requisito: rodar o build.bat ANTES (para existir dist\DocManager\).
;  Compilar: abra este .iss no Inno Setup Compiler e clique em "Compile",
;  ou linha de comando:  iscc installer\docmanager.iss
;  Saida: installer\Output\DocManager_Itaipu_Setup.exe
; ============================================================

#define AppName "DocManager Itaipu"
#define AppVersion "3.0.0"
#define AppExe "DocManager.exe"

[Setup]
AppId={{7C3B2A10-DOCM-4ITA-IPU0-DOCMANAGER01}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=CMI - Engenharia
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=DocManager_Itaipu_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Program Files exige elevacao; a config/.env do usuario fica em Documents (sem admin).
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\assets\logo_definitivo.ico
UninstallDisplayIcon={app}\{#AppExe}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"

[Files]
; Toda a pasta onedir gerada pelo PyInstaller.
Source: "..\dist\DocManager\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; Modelo do .env ao lado do exe (o real, com o secret, o usuario cria).
Source: "..\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Desinstalar {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir o {#AppName}"; Flags: nowait postinstall skipifsilent

[Messages]
brazilianportuguese.FinishedLabel=Instalacao concluida.%n%nATENCAO: para a Extracao Aconex funcionar, crie o arquivo .env com o seu SECRET.%nColoque-o em uma destas pastas:%n  - Documentos\DocManager_Itaipu\.env   (recomendado - nao precisa de admin)%n  - ou ao lado do {#AppExe} (precisa de admin).%nUse o .env.example como modelo.
