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
; Mutex que o app cria ao abrir (ui/main_app.py, NOME_MUTEX). Os dois nomes TEM
; que ser iguais - ver AppMutex e o [Code] no fim deste arquivo.
#define AppMutexName "DocManagerItaipu_AppMutex"

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
; para mim" e vai para %LOCALAPPDATA%\Programs - e ai a atualizacao automatica
; roda sem nenhum popup do UAC.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline

; --- Atualizacao por cima da versao anterior ----------------------------
; AppMutex: o app cria este mutex nomeado ao abrir, e e por ele que o Inno
; DESCOBRE que o DocManager esta rodando. Ele NAO fecha o app: numa instalacao
; feita na mao, mostra "feche o aplicativo"; em modo silencioso (a atualizacao
; automatica), responde Cancelar sozinho e ABORTA. Por isso a atualizacao
; automatica espera o app sair antes dessa checagem - ver InitializeSetup no
; [Code]. Quem fecha o que ainda estiver usando os arquivos e o Restart
; Manager (CloseApplications).
AppMutex={#AppMutexName}
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
; Atualizacao automatica (silenciosa): reabre o app no fim. O Restart Manager so
; reabre o que ele mesmo fechou, e o DocManager sai sozinho antes.
Filename: "{app}\{#AppExe}"; Flags: nowait runasoriginaluser; Check: ReabrirAposAtualizar

[UninstallDelete]
; Restos do build antigo (pyc/cache) que nao constam no manifesto de instalacao.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Messages]
; As credenciais agora sao cadastradas DENTRO do app; nao existe mais .env para
; a pessoa copiar. A mensagem final diz exatamente o que fazer na 1a abertura.
brazilianportuguese.FinishedLabel=Instalacao concluida.%n%nPRIMEIRO USO: para a Extracao Aconex funcionar, abra o DocManager, va em "Extracao Aconex" e clique em CADASTRAR USUARIO. Informe o Client ID (APP ID), o User ID e o Client Secret que o administrador do Aconex passou para voce.%n%nE uma vez so. Os dados ficam guardados nesta maquina, cifrados pelo Windows, e continuam valendo depois das atualizacoes.%n%nOs outros modulos (Mapa, Doc List, Status, Historico, Relatorios) funcionam sem cadastro nenhum.

[Code]
// ==========================================================================
//  Atualizacao automatica disparada pelo proprio DocManager
// ==========================================================================
// O app baixa este instalador, dispara em modo silencioso e so DEPOIS se
// fecha - leva alguns segundos para sair. Sem a espera abaixo, a checagem do
// AppMutex encontrava o app ainda aberto e abortava a atualizacao em meio
// segundo, deixando a versao antiga (reproduzido com este script no Wine).
// InitializeSetup roda ANTES daquela checagem, por isso a espera fica aqui.
//
// Parametros que o app passa (alem dos do Inno):
//   /SINAL=arquivo  o instalador cria o arquivo quando chega aqui, ja com a
//                   permissao de administrador concedida, se foi pedida. So
//                   entao o app se fecha; se o instalador terminar sem criar o
//                   arquivo (UAC recusado, por exemplo), o app segue aberto e
//                   avisa. Existe a partir da 3.2.
//   /REABRIR        o app disparou o instalador SEM elevar e o proprio Inno
//                   pediu a permissao: "runasoriginaluser" abre o app de novo
//                   na conta de quem o estava usando. Existe a partir da 3.2.
// O app 3.1.0 nao passa nenhum dos dois, e continua funcionando: a espera vale
// para ele, e a reabertura tambem, na instalacao "somente para mim".

const
  EsperaMaximaMs = 60000;
  PassoMs = 250;

function TemParametro(const Nome: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Nome) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

function InitializeSetup(): Boolean;
var
  Sinal: String;
  Esperado: Integer;
begin
  Result := True;
  Sinal := ExpandConstant('{param:SINAL|}');
  if Sinal <> '' then
    SaveStringToFile(Sinal, 'pronto', False);

  // Instalacao feita na mao: o proprio Inno pede para fechar o app.
  if not WizardSilent then
    Exit;

  Esperado := 0;
  while CheckForMutexes('{#AppMutexName}') and (Esperado < EsperaMaximaMs) do
  begin
    Sleep(PassoMs);
    Esperado := Esperado + PassoMs;
  end;
  if Esperado > 0 then
    Log(Format('DocManager: esperou %d ms o app fechar.', [Esperado]));
end;

function ReabrirAposAtualizar(): Boolean;
begin
  // Sem /REABRIR (app 3.1.0), numa instalacao para todos os usuarios o
  // instalador ja nasceu elevado: a "conta original" pode ser a do
  // administrador que digitou a senha, e o app abriria com os Documentos e as
  // credenciais de outra pessoa. Nesse caso a pessoa reabre pelo atalho.
  Result := WizardSilent and (TemParametro('/REABRIR') or
    (TemParametro('/RESTARTAPPLICATIONS') and not IsAdminInstallMode));
end;
