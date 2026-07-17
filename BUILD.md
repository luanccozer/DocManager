# Gerar o executável (Windows / rede corporativa)

Objetivo: entregar o DocManager para quem **não tem Python instalado**.

---

## Por que ONEDIR (pasta) e não ONEFILE (arquivo único)

O build é **onedir** de propósito. Em ambiente corporativo (GE/Zscaler/GlobalProtect) é a escolha certa:

| | **onedir** (usado aqui) | onefile |
|---|---|---|
| Abertura | **Instantânea** | Descompacta tudo no `%TEMP%` a **cada** execução (lento) |
| Antivírus / EDR | **Bem tolerado** | O auto-extrair é heurística clássica de malware → **bloqueio/quarentena** |
| AppLocker / política | Pasta comum, assinável | Executar do `%TEMP%` costuma ser **proibido** por política |
| Atualizar | Troca só os arquivos alterados | Reenviar o exe inteiro |
| Diagnóstico | Dá para ver os arquivos | Caixa-preta |

> Onefile só compensa quando o requisito é “um único arquivo por e-mail”. Aqui, o instalador resolve isso melhor.

**UPX está desligado** no `.spec` — compressão UPX é outro gatilho comum de antivírus.

---

## A tela de carregamento (splash)

São **duas coisas diferentes**:

1. **Splash nativo do PyInstaller** (`pyi_splash`) — é o que existia no legado: aparece **no duplo-clique**, enquanto o Python e as bibliotecas carregam. Configurado no `docmanager.spec` (objeto `Splash`) com **`assets/splash.png`**, e fechado por `pyi_splash.close()` em `ui/main_app.py` assim que o app fica pronto.
2. **Splash do app** (`ui/splash.py`) — a janela com o logo, mostrada logo depois.

No onedir **não há descompactação**, então a espera é curta — mas o splash nativo continua lá para o clique não parecer “sem resposta”.

**Para mudar a imagem de carregamento**: edite e rode `tools/gerar_splash.py` (usa as cores do tema do app e escreve `assets/splash.png`), depois rebuilde. Como o bootloader **não anima**, o “está carregando” é comunicado pelo texto + a barra parcialmente preenchida.

> ⚠️ **Não aponte o `Splash` para `assets/logo_final.png`** — apesar do nome, é um **placeholder** herdado do legado (a imagem tem “DM placeholder” escrito). O logo real do projeto é o `assets/logo_definitivo.ico`, usado na janela/ícone.

---

## Passo a passo (no computador da empresa)

### 0. Pré-requisitos

- **Python 3.12+** instalado, marcando **“Add Python to PATH”** na instalação.
- A pasta do projeto copiada para a máquina.

Confira no PowerShell:
```powershell
py -0p        # deve listar ao menos uma versão 3.12+
```

### 1. Preparar o ambiente (só na 1ª vez)

Duplo-clique em **`run.bat`**. Ele cria o ambiente virtual, instala tudo e abre o app — serve como teste de que está tudo certo antes de empacotar.

> **Onde o venv é criado:** em `%LOCALAPPDATA%\DocManagerItaipu\venv`, **fora do OneDrive** de propósito. Um venv tem milhares de arquivos; dentro de uma pasta sincronizada, a instalação fica lenta e chega a travar.

> **Rede corporativa (Zscaler) — já vem resolvido:** o `run.bat` e o `build.bat` já chamam o pip com os argumentos que passam pela inspeção SSL do Zscaler (sem eles o pip erra e trava):
> ```
> --isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org
> ```
> Só mexa nisso se a empresa exigir um **mirror interno** — nesse caso crie `pip_corporativo.txt` na raiz do projeto com os seus argumentos numa única linha (ou defina a variável `DOCMANAGER_PIP_ARGS`), que ele substitui o padrão:
> ```
> --index-url https://SEU-MIRROR/simple --trusted-host SEU-MIRROR
> ```

### 2. Gerar a pasta do app

Duplo-clique em **`build.bat`**. Ele instala o PyInstaller, limpa builds antigos e gera:

```
dist\DocManager\DocManager.exe      ← o executável (~30 MB)
dist\DocManager\_internal\...       ← dependências (não mexer)
```

> ⚠️ **Leva ~2 minutos e NÃO pode ser interrompido.** O `.exe` só é copiado para o `dist` na **última etapa** (`COLLECT`). Se você fechar a janela antes, fica um `dist\DocManager\` só com o `_internal` **e sem o .exe** — que é exatamente o sintoma de build interrompido. Espere aparecer a mensagem **PRONTO**. O script confere isso e avisa se o `.exe` não foi gerado.

<details>
<summary>Prefere na mão? (equivalente ao build.bat)</summary>

```powershell
cd "CAMINHO\DO\PROJETO"
$py = "$env:LOCALAPPDATA\DocManagerItaipu\venv\Scripts\python.exe"
& $py -m pip install -r requirements.txt
& $py -m pip install "pyinstaller>=6,<7"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& $py -m PyInstaller docmanager.spec --noconfirm
```
</details>

### 3. Colocar o `.env` (obrigatório)

O `.env` **nunca** é embutido no executável (contém segredos) — precisa ser copiado à parte. O app procura nestes dois lugares, nesta ordem:

| Onde | Observação |
|---|---|
| **Na mesma pasta do `DocManager.exe`** | testando o build → **`dist\DocManager\.env`** |
| **`Documentos\DocManager_Itaipu\.env`** | **recomendado** no dia a dia: cada pessoa tem o seu e edita sem admin |

> ❌ **Erro comum:** deixar em `dist\.env`. Tem que ser **`dist\DocManager\.env`** — *dentro* da pasta, junto do `.exe`.

Use o `.env.example` como modelo (`VERSAO` e `SECRET_<NOME>`).

### 4. Testar

Abra `dist\DocManager\DocManager.exe`. Confira: splash → app abre, versão do `.env` no título/rodapé/Home, e a Extração Aconex lista o seu usuário.

### 5. (Opcional) Gerar o instalador

Instale o [Inno Setup 6](https://jrsoftware.org/isdl.php), abra `installer\docmanager.iss` e clique em **Compile** (ou `iscc installer\docmanager.iss`).

Saída: `installer\Output\DocManager_Itaipu_Setup.exe` — instala em *Program Files*, cria atalhos e avisa sobre o `.env` no final.

---

## Compartilhar com outras pessoas (onedir)

**O que enviar:** zipe a pasta **`dist\DocManager\` inteira** (o `.exe` sozinho não funciona — ele precisa do `_internal\` ao lado).

```powershell
Compress-Archive -Path "dist\DocManager\*" -DestinationPath "DocManager_v3.0.0.zip" -Force
```

**Instruções para quem recebe:**

1. Extrair o zip numa **pasta local** — ex.: `C:\DocManager`. **Não** rodar de dentro do OneDrive/rede: fica lento e o antivírus costuma bloquear.
2. Criar o **`.env`** em `Documentos\DocManager_Itaipu\` com o secret dela (modelo no `.env.example`).
3. Abrir o **`DocManager.exe`**.

> **Não inclua o seu `.env` no zip** — o secret é pessoal e a `.gitignore` já o mantém fora do repositório. Cada pessoa usa o dela (ou a opção *“Outro (inserir manualmente)”* na tela de extração).

Se preferir entregar um instalador em vez do zip, veja o passo 5.

---

## Problemas comuns

**`ModuleNotFoundError` ao abrir o .exe** — falta um *hidden import*. Anote o módulo e acrescente na lista `_hidden` do `docmanager.spec`, depois rebuilde. (Já cobrimos dash, dbc, plotly, customtkinter, truststore, certifi, openpyxl, xlsxwriter, PIL.)

**Antivírus bloqueou** — é o onedir sem UPX, que já é o cenário mais amigável. Se persistir, peça ao TI para liberar a pasta ou **assinar digitalmente** o `DocManager.exe` (o ideal no corporativo).

**Extração Aconex não funciona na máquina do outro** — não é o build: é rede (Zscaler/VPN). Veja o log do módulo, que testa as rotas de conexão automaticamente.

**Abre e fecha na hora** — rode pelo `cmd` (`dist\DocManager\DocManager.exe`) para ver o erro, ou gere um build com `console=True` no `.spec` para depurar.
