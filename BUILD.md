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

1. **Splash nativo do PyInstaller** (`pyi_splash`) — é o que existia no legado: aparece **no duplo-clique**, enquanto o Python e as bibliotecas carregam. Está configurado no `docmanager.spec` (objeto `Splash`, usando `assets/logo_final.png`) e é fechado por `pyi_splash.close()` em `ui/main_app.py` assim que o app fica pronto.
2. **Splash do app** (`ui/splash.py`) — a janela com o logo que já existe, mostrada logo depois.

No onedir **não há descompactação**, então a espera é curta — mas o splash nativo continua lá para o clique não parecer “sem resposta”. Para um splash mais bonito, troque `assets/logo_final.png` por um banner (ex.: 480×300 px).

---

## Passo a passo

### 1. Gerar a pasta do app

Duplo-clique em **`build.bat`** (ou rode no venv). Ele instala o PyInstaller, limpa builds antigos e gera:

```
dist\DocManager\DocManager.exe      ← o executável
dist\DocManager\_internal\...       ← dependências (não mexer)
```

> Rede corporativa: se o `pip` falhar, crie `pip_corporativo.txt` na raiz com os seus argumentos (`--index-url ... --trusted-host ...`), igual ao `run.bat`.

### 2. Colocar o `.env` (obrigatório)

O `.env` **nunca** é embutido no executável (contém segredos). O app procura, nesta ordem:

1. **ao lado do `DocManager.exe`** — precisa de admin se estiver em *Program Files*;
2. **`Documentos\DocManager_Itaipu\.env`** — *recomendado*, cada usuário edita o seu sem admin.

Use o `.env.example` como modelo (`VERSAO` e `SECRET_<NOME>`).

### 3. Testar

Abra `dist\DocManager\DocManager.exe`. Confira: splash → app abre, versão do `.env` no título/rodapé/Home, e a Extração Aconex lista o seu usuário.

### 4. (Opcional) Gerar o instalador

Instale o [Inno Setup 6](https://jrsoftware.org/isdl.php), abra `installer\docmanager.iss` e clique em **Compile** (ou `iscc installer\docmanager.iss`).

Saída: `installer\Output\DocManager_Itaipu_Setup.exe` — instala em *Program Files*, cria atalhos e avisa sobre o `.env` no final.

---

## Distribuir sem instalador

Zipe a pasta `dist\DocManager\` inteira e mande. A pessoa extrai **em uma pasta local** (não na rede/OneDrive — dá lentidão e trava de antivírus) e cria o `.env`.

---

## Problemas comuns

**`ModuleNotFoundError` ao abrir o .exe** — falta um *hidden import*. Anote o módulo e acrescente na lista `_hidden` do `docmanager.spec`, depois rebuilde. (Já cobrimos dash, dbc, plotly, customtkinter, truststore, certifi, openpyxl, xlsxwriter, PIL.)

**Antivírus bloqueou** — é o onedir sem UPX, que já é o cenário mais amigável. Se persistir, peça ao TI para liberar a pasta ou **assinar digitalmente** o `DocManager.exe` (o ideal no corporativo).

**Extração Aconex não funciona na máquina do outro** — não é o build: é rede (Zscaler/VPN). Veja o log do módulo, que testa as rotas de conexão automaticamente.

**Abre e fecha na hora** — rode pelo `cmd` (`dist\DocManager\DocManager.exe`) para ver o erro, ou gere um build com `console=True` no `.spec` para depurar.
