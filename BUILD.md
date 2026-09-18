# Publicar uma versão nova

Desde a **v3.1.0** o DocManager é gerado e publicado pelo **GitHub Actions**: o
Windows da GitHub compila o executável, monta o instalador e cria o Release.
Ninguém precisa mais empacotar nada à mão, nem enviar ZIP por e-mail, nem copiar
`.env` para máquina nenhuma.

---

## O procedimento inteiro (2 passos)

### 1. Escrever o que mudou

Abra o **`CHANGELOG.md`** e acrescente o bloco da versão **no topo**:

```markdown
## 3.1.1 — 2026-09-25

- O que mudou, em uma frase que o usuário entenda.
- Outra coisa que mudou.
```

Esse texto é a **fonte única**: vira a descrição do Release no GitHub **e** a
seção "O que há de novo" da tela inicial do app. Commite normalmente.

### 2. Disparar a publicação

Duas formas — as duas fazem exatamente a mesma coisa, escolha a que preferir.

#### a) Pelo site, sem terminal (mais simples)

1. Vá em **Actions → Release → Run workflow**.
2. Em *Versão*, escreva `3.1.1` (sem o `v`).
3. **Desmarque** *Pré-lançamento* — marcado, o app não oferece a versão como
   atualização (é o modo de ensaio).
4. **Run workflow**.

O próprio workflow cria a tag e o Release. Nada para instalar na sua máquina.

#### b) Pelo terminal

```bat
git tag v3.1.1
git push origin v3.1.1
```

Em ~10 minutos o Release está publicado e **todo mundo que já tem o app
instalado é avisado sozinho** na próxima vez que abrir.

> A tag **manda na versão**: `v3.1.1` → o executável se identifica como `3.1.1`.
> Não existe versão escrita à mão em lugar nenhum.

Acompanhe em **Actions → Release**. Se algo falhar, o workflow para antes de
publicar — nunca sai um Release pela metade.

> Criar a tag pela página **Releases → Draft a new release** também funciona: o
> GitHub cria tag e release de uma vez, e o workflow anexa o instalador ao
> release que já existe em vez de tentar criar outro.

### Ensaio antes de valer

Rode o **Run workflow** com uma versão como `3.1.1-rc.1` e *Pré-lançamento*
**marcado**. Sai publicado como pré-lançamento, que o app ignora como
atualização: dá para conferir que o build e o instalador saíram certos, e baixar
para testar, sem queimar a versão de verdade.

---

## O que o workflow faz

| Passo | Por quê |
|---|---|
| `ruff` + `pytest` | Portão: 2 minutos de teste antes de 10 de empacotamento. Versão quebrada publicada é muito mais cara de desfazer. |
| `tools/preparar_build.py` | Carimba a versão da tag em `_build_info.py` e embute o token de atualização em `_update_auth.py`. |
| `pyinstaller docmanager.spec` | Gera `dist\DocManager\` (onedir — ver abaixo). |
| `ISCC installer\docmanager.iss` | Monta o `DocManager_Itaipu_Setup_<versão>.exe`. |
| SHA256 + `latest.json` | O app confere o hash do instalador **antes** de executá-lo. |
| `gh release create` | Publica o Release com o instalador, o manifesto e as notas do CHANGELOG. |

O `.github/workflows/ci.yml` roda lint + testes em **todo commit** (em Linux,
mais rápido). O de Release só dispara em tag.

---

## Rotação do token de atualização

O repositório é **privado**, então o app precisa de um token para ler os
Releases. Ele é injetado no build a partir do segredo **`UPDATE_TOKEN`** e
**nunca** entra no Git (`docmanager/_update_auth.py` está no `.gitignore`).

> ⚠️ **Um token embutido num `.exe` é extraível** por quem tiver o arquivo. A
> ofuscação do `_ofuscacao.py` só impede que ele apareça num `strings` — não é
> segurança. Por isso ele **tem** que ser um PAT *fine-grained*, **somente
> leitura**, **restrito a este repositório**: no pior caso, alguém consegue ler
> o código que essa pessoa já recebeu — nada mais. Nunca use um token clássico
> nem um com permissão de escrita.

**Como criar/trocar:**

1. GitHub → *Settings* (da sua conta) → *Developer settings* → *Personal access
   tokens* → **Fine-grained tokens** → *Generate new token*.
2. **Resource owner:** você. **Repository access:** *Only select repositories* →
   `luanccozer/DocManager`.
3. **Permissions → Repository permissions → Contents: Read-only.** Nada mais.
4. Validade: um prazo que você consiga lembrar de renovar (ex.: 1 ano).
5. Copie o token e cole em: repositório → *Settings* → *Secrets and variables* →
   *Actions* → **`UPDATE_TOKEN`**.
6. Publique uma versão nova. Só os builds feitos **depois** da troca usam o token
   novo.

**Se o token vencer antes de você publicar uma versão nova**, os apps instalados
param de achar atualizações (o app continua funcionando normalmente, só deixa de
avisar). Para destravar sem refazer o build, cada pessoa pode criar o arquivo:

```
Documentos\DocManager_Itaipu\update_token.txt
```

com o token novo dentro. O app prefere esse arquivo ao token embutido. É uma
saída de emergência — o certo é publicar uma versão nova.

---

## Como a atualização funciona (e por que essa costuma quebrar)

Ao abrir, o app consulta o último Release (no máximo uma vez a cada 6 horas),
compara com a própria versão e, se houver novidade, mostra o aviso. Ao clicar em
**Atualizar agora**: baixa o instalador, confere o SHA256, executa em modo
silencioso e fecha o app para que os arquivos possam ser trocados.

Quatro armadilhas foram tratadas explicitamente — são as que costumam fazer um
auto-update "existir mas não funcionar":

1. **Repositório privado + `browser_download_url`.** Em repo privado, aquela URL
   só funciona para um navegador logado. Um download programático recebe uma
   **página HTML de login com status 200**: o update "dá certo" e grava um HTML
   de 4 KB renomeado para `.exe`, que não instala nada. O app usa o endpoint de
   API do asset (`/releases/assets/{id}` com `Accept: application/octet-stream`)
   e ainda recusa qualquer download menor que 1 MB.

2. **Zscaler / GlobalProtect.** Sem os certificados do Windows, todo HTTPS falha
   com `certificate verify failed` e o app **nunca avisa** que há versão nova —
   silenciosamente. O `services/rede.py` injeta o `truststore` e tenta, em
   ordem, proxy do sistema → variáveis de ambiente → conexão direta, com uma
   última tentativa sem verificação de TLS **apenas** se todas as falhas forem
   de certificado.

3. **Versão vinda do `.env`.** O `.env` é do usuário e sobrevive à atualização:
   o app novo continuaria se declarando na versão antiga e reofereceria a mesma
   atualização para sempre. Agora a versão vem do **binário**
   (`_build_info.py`), escrita pela tag.

4. **Instalar por cima de si mesmo.** O Windows não deixa sobrescrever um `.exe`
   em execução. O app cria um **mutex nomeado** (`NOME_MUTEX` em
   `ui/main_app.py`) e o instalador o declara em `AppMutex` (`installer/docmanager.iss`):
   é assim que o Inno descobre o app aberto e o fecha. **Os dois nomes têm que
   ser iguais** — se alguém mudar um, a atualização passa a falhar com "arquivo
   em uso".

### Escopo da instalação e o UAC

O instalador **pergunta** onde instalar:

| Escolha | Onde | Atualização |
|---|---|---|
| **Para todos os usuários** (padrão) | `C:\Program Files\DocManager Itaipu` | Pede administrador (UAC) a cada atualização |
| **Somente para mim** | `%LOCALAPPDATA%\Programs\DocManager Itaipu` | **Silenciosa, sem UAC** |

Se a sua equipe não tem senha de administrador, oriente a escolher **"somente
para mim"** — aí a atualização é um clique e nada mais.

---

## Build local (plano B)

Só para testar o empacotamento antes da tag, ou se o GitHub Actions estiver fora:

```bat
build.bat 3.1.1
```

Gera `dist\DocManager\DocManager.exe`. Para o instalador:

```bat
iscc /DMyAppVersion=3.1.1 installer\docmanager.iss
```

> **Pré-lançamento na mão:** o `VersionInfoVersion` do Windows só aceita dígitos,
> então uma versão com sufixo precisa passar *também* a versão numérica, senão o
> Inno aborta com *"VersionInfoVersion is invalid"*:
> ```bat
> iscc /DMyAppVersion=3.1.1-rc.1 /DMyVersionInfo=3.1.1 installer\docmanager.iss
> ```
> O workflow calcula e passa isso sozinho.

> ⚠️ O build local sai **sem** o token, logo o executável gerado **não avisa de
> versões novas**. Para distribuir de verdade, use a tag.

<details>
<summary>Prefere na mão? (equivalente ao build.bat)</summary>

```powershell
cd "CAMINHO\DO\PROJETO"
$py = "$env:LOCALAPPDATA\DocManagerItaipu\venv\Scripts\python.exe"
& $py -m pip install -r requirements.txt "pyinstaller>=6,<7"
& $py tools\preparar_build.py 3.1.1 --origem local
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
& $py -m PyInstaller docmanager.spec --noconfirm
```
</details>

---

## Decisões de empacotamento

### Por que ONEDIR (pasta) e não ONEFILE (arquivo único)

| | **onedir** (usado aqui) | onefile |
|---|---|---|
| Abertura | **Instantânea** | Descompacta tudo no `%TEMP%` a **cada** execução (lento) |
| Antivírus / EDR | **Bem tolerado** | O auto-extrair é heurística clássica de malware → **bloqueio/quarentena** |
| AppLocker / política | Pasta comum, assinável | Executar do `%TEMP%` costuma ser **proibido** por política |
| Atualizar | Troca só os arquivos alterados | Reenviar o exe inteiro |
| Diagnóstico | Dá para ver os arquivos | Caixa-preta |

**UPX está desligado** no `.spec` — compressão UPX é outro gatilho comum de antivírus.

### A tela de carregamento (splash)

São **duas coisas diferentes**:

1. **Splash nativo do PyInstaller** (`pyi_splash`) — aparece **no duplo-clique**,
   enquanto o Python e as bibliotecas carregam. Configurado no `docmanager.spec`
   (objeto `Splash`) com **`assets/splash.png`**, e fechado por
   `pyi_splash.close()` em `ui/main_app.py` assim que o app fica pronto.
2. **Splash do app** (`ui/splash.py`) — a janela com o logo, mostrada logo depois.

**Para mudar a imagem de carregamento**: edite e rode `tools/gerar_splash.py`,
depois rebuilde.

> ⚠️ **Não aponte o `Splash` para `assets/logo_final.png`** — apesar do nome, é
> um **placeholder** herdado do legado. O logo real é o `assets/logo_definitivo.ico`.

---

## Problemas comuns

**`ModuleNotFoundError` ao abrir o .exe** — falta um *hidden import*. Acrescente
o módulo na lista `_hidden` do `docmanager.spec` e rebuilde. (Já cobrimos dash,
dbc, plotly, customtkinter, truststore, certifi, openpyxl, xlsxwriter, PIL.)

**A seção "O que há de novo" some no .exe** — o `CHANGELOG.md` precisa estar nos
`datas` do `docmanager.spec` (`("CHANGELOG.md", ".")`). Já está.

**O app não avisa de versão nova** — nesta ordem: (1) o build tem token? As
Configurações dizem *"este build não tem atualização automática"* quando não
tem; (2) o `UPDATE_TOKEN` venceu? (3) rede: clique em **Procurar atualizações
agora** nas Configurações — ao contrário da checagem automática, esse botão
**mostra o erro**.

**"Arquivo em uso" ao atualizar** — o `AppMutex` do `.iss` e o `NOME_MUTEX` do
`ui/main_app.py` estão diferentes.

**Antivírus bloqueou** — é onedir sem UPX, o cenário mais amigável. Se persistir,
peça ao TI para liberar a pasta ou assine digitalmente o executável (abaixo).

---

## Assinatura digital (o aviso do SmartScreen)

Todo mundo que baixar o instalador vai ver **"O Windows protegeu o computador"**.
Não é falso-positivo de vírus: o SmartScreen desconfia de qualquer executável
**sem assinatura digital** e sem histórico de downloads. Dá para passar em dois
cliques (*Mais informações → Executar assim mesmo*), e as notas de cada Release
já explicam isso — mas é atrito toda vez, e assusta quem não é técnico.

**Isso não melhora sozinho.** A "reputação" do SmartScreen se constrói com
volume de downloads; um app interno com cinco usuários nunca chega lá. E como
cada versão nova gera um arquivo novo, o aviso volta a cada publicação.

As saídas, em ordem de custo:

| Caminho | Efeito | Custo |
|---|---|---|
| Conviver com os dois cliques | Funciona, mas atrita a cada versão | zero |
| Pedir ao TI para liberar (política de SmartScreen/AppLocker para o publisher ou a pasta) | Some para a empresa toda | zero, mas depende do TI |
| **Certificado de assinatura de código OV** | Assinado; a reputação ainda leva algumas semanas para amadurecer | ~US$ 200–400/ano |
| **Certificado EV** | Reputação do SmartScreen **imediata** | ~US$ 300–600/ano, exige token físico ou HSM |

Se a CMI decidir assinar, o passo é acrescentar um `signtool sign` ao workflow
entre "Montar o instalador" e "Gerar o manifesto", com o certificado guardado
nos *Secrets* do repositório. Vale assinar **os dois**: o `DocManager.exe` e o
instalador.

> Antes de comprar, pergunte ao TI: empresas com CA interna às vezes já emitem
> certificados de assinatura para uso corporativo, de graça — e aí o SmartScreen
> confia dentro do domínio.

**Abre e fecha na hora** — rode pelo `cmd` para ver o erro, ou gere um build com
`console=True` no `.spec` para depurar.
