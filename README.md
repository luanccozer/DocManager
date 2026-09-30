# DocManager Itaipu

Aplicativo desktop da engenharia da CMI para controlar a documentação do projeto
de modernização de Itaipu. Cruza a extração do **Aconex** (fonte da verdade dos
status) com as planilhas internas (Mapeamento de Planos, Controle de Documentos)
e gera mapa de planos, status de documentos, histórico consolidado, dashboard e
relatórios.

---

## Instalar (para quem vai USAR o app)

**Não precisa de Python, nem de Git, nem de baixar o projeto.**

1. Abra a página de [**Releases**](https://github.com/luanccozer/DocManager/releases)
   e baixe o `DocManager_Itaipu_Setup_<versão>.exe` mais recente.
2. Execute. O instalador pergunta onde instalar:
   - **Para todos os usuários** - vai para `C:\Program Files`, **precisa de senha
     de administrador** (na instalação e a cada atualização);
   - **Somente para mim** - vai para a sua pasta de usuário, **não precisa de
     administrador** e as atualizações são silenciosas.

   > Se você não tem senha de administrador na máquina da empresa, escolha
   > **"somente para mim"**.
3. Abra o **DocManager** pelo atalho.

> ### ⚠️ "O Windows protegeu o computador"
>
> Esse aviso **vai** aparecer, e não é vírus: o SmartScreen reclama de todo
> programa recém-compilado que ainda não tem assinatura digital.
>
> O detalhe que trava todo mundo é que o botão para continuar **começa
> escondido**. A janela só mostra *Não executar*; clique primeiro em
> **"Mais informações"** (link pequeno e cinza, logo abaixo do texto) e aí
> aparece o **"Executar assim mesmo"**.
>
> Alternativa: botão direito no `.exe` → **Propriedades** → marcar
> **"Desbloquear"** no rodapé da aba *Geral* → *Aplicar*. Depois é só abrir.
>
> Para eliminar o aviso de vez seria preciso comprar um certificado de
> assinatura de código. Ver [`BUILD.md`](BUILD.md), seção *Assinatura digital*.

### Primeiro uso: cadastrar as suas credenciais do Aconex

Só a **Extração Aconex** precisa disso. Os demais módulos (Mapa, Doc List,
Status, Histórico, Relatórios) funcionam sem cadastro nenhum, bastam os
arquivos Excel.

1. No app, abra **📥 Extração Aconex**.
2. Clique em **Cadastrar usuário**.
3. Informe os três dados que o administrador do Aconex forneceu para você:

   | Campo | O que é |
   |---|---|
   | **Client ID (APP ID)** | Identifica o aplicativo OAuth registrado no seu nome. Tem a cara de `SCP_SEU_NOME_ACONEX_client_APPID`. Não é segredo. |
   | **User ID** | O número da sua conta no Aconex (só dígitos, ex.: `1208560183`). Não é segredo. |
   | **Client Secret** | A senha do aplicativo. **Esta é a parte sigilosa.** |

4. Salve. É **uma vez só**.

O Client Secret fica guardado **nesta máquina**, cifrado pelo Windows (DPAPI) na
sua conta de usuário, em `Documentos\DocManager_Itaipu\credenciais.json`. Ele
não vai para o GitHub, não fica na pasta do programa e **continua valendo depois
de cada atualização**. Copiar esse arquivo para outra máquina não adianta,
porque a cifragem é atrelada à sua conta do Windows. Na máquina nova, cadastre
de novo.

Para trocar o secret, ver quem está cadastrado ou remover alguém:
**⚙️ Configurações → Credenciais do Aconex**. O cadastro feito por lá aparece na
Extração Aconex assim que você volta para ela.

> **Se você já usava o DocManager com um arquivo `.env`:** não precisa fazer
> nada. Na primeira abertura depois de atualizar, o app **importa sozinho** as
> credenciais do `.env` para o cadastro interno. Depois disso o `.env` pode ser
> apagado.

### Atualizações

**Automáticas.** O app verifica em segundo plano se saiu versão nova ao abrir e
enquanto fica aberto (no máximo uma vez a cada 6 horas). Quando há, aparece:

- uma faixa na tela inicial com o que mudou, e
- o aviso `✨ v3.x.x disponível` no rodapé da barra lateral.

Clique e depois em **Atualizar agora**: o app baixa o instalador, confere a
integridade do arquivo (SHA256), fecha sozinho e reabre já atualizado. Quem
instalou em *Program Files* verá o pedido de administrador do Windows; se ele
for recusado, o app continua aberto e avisa.

Para procurar na hora, use o botão **🔄 Procurar atualizações** no rodapé da
barra lateral (ou em **⚙️ Configurações → Atualizações**). Ao contrário da
checagem automática, ele **mostra o erro** se algo falhar, e é por onde começar
a diagnosticar. Nas Configurações também dá para desligar o aviso automático.

A verificação funciona **com o Zscaler e a VPN ligados**. Ela usa os certificados
do Windows, obedece o arquivo PAC da rede e ainda testa as rotas em cascata
(proxy do sistema, variáveis de ambiente, conexão direta).

> **Vindo da v3.1.0:** a primeira atualização é feita pelo código da versão que
> está instalada. Numa instalação *para todos os usuários* (Program Files), o
> app fecha e **não reabre sozinho** dessa vez: espere a janelinha de progresso
> sumir e abra o DocManager pelo atalho. A partir da v3.1.1 ele reabre sozinho
> nos dois tipos de instalação.

---

## Rodar a partir do código (desenvolvimento)

Quem vai **mexer no código** (e não só usar) roda direto do repositório:

```bat
git clone https://github.com/luanccozer/DocManager.git
```

Depois, duplo-clique em **`run.bat`**. Na primeira vez ele cria o ambiente
virtual, instala as dependências e abre o app; nas próximas, só abre.

> Precisa do **Python 3.12+** instalado (marque *"Add Python to PATH"*). Sem o
> `run.bat`:
> ```bat
> py -3 -m venv .venv
> .venv\Scripts\activate
> pip install -r requirements.txt
> python -m docmanager
> ```

Para publicar uma versão nova, veja o [**BUILD.md**](BUILD.md). Resume-se a
escrever o `CHANGELOG.md` e criar a tag; o GitHub faz o resto.

### Rede corporativa (Zscaler) - já vem resolvido

Atrás do Zscaler o `pip` erra e trava por causa da inspeção de SSL. O `run.bat` e
o `build.bat` **já chamam o pip com os argumentos que resolvem isso**, sem você
precisar fazer nada:

```
--isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

Eles apontam o índice público do PyPI e dispensam a verificação TLS **somente**
para os hosts do PyPI. Fora da empresa são inofensivos. Instalando na mão, use
os mesmos:

```powershell
python -m pip install --isolated --index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

**Só se a sua rede exigir um mirror interno**, sobrescreva o padrão criando um
`pip_corporativo.txt` na pasta do projeto com os seus argumentos numa única
linha (ou defina a variável de ambiente `DOCMANAGER_PIP_ARGS`):

```
--isolated --index-url https://SEU-MIRROR-INTERNO/simple --trusted-host SEU-HOST
```

> `pip_corporativo.txt` fica fora do Git (é específico da sua rede).

### Onde ficam os seus dados

Tudo em **`Documentos\DocManager_Itaipu\`**, fora da pasta do programa. Assim a
atualização, que reescreve a pasta de instalação, nunca encosta neles:

| Arquivo | O que guarda |
|---|---|
| `config.json` | Preferências (regra VIP, base do atraso, últimas pastas usadas) |
| `credenciais.json` | Credenciais do Aconex, com o secret cifrado pelo Windows |
| `update_token.txt` | *(opcional)* token de atualização, só para rotação de emergência |

Para desenvolvimento, `DOCMANAGER_DADOS_DIR` redireciona essa pasta inteira.

---

## Os módulos (como usar cada um)

Em **todo** seletor de arquivo há um botão de **Aba (Sheet)**: escolha a aba certa
do Excel antes de rodar (para bases Aconex, a aba "Documentos" já vem selecionada).

- **🗺️ Mapa dos Planos** - atualiza a planilha de Mapeamento (status real,
  hierarquia, KPIs, atrasos). Selecione a **Base Aconex** + o **Mapeamento** e,
  opcionalmente, o **Controle de Documentos** (preenche datas previstas /
  reprogramação). As datas que o app grava (DATA ÚLTIMA EMISSÃO e a DATA
  PREVISTA e a REPROGRAMADA da etapa 1) saem no formato **Data** do Excel, que o
  Power BI lê como data. O botão **⏳ Analisar Mudanças por Período (Delta)**
  abre a "Máquina do Tempo" comparando o status entre duas datas.
- **📑 Doc List Mapping** - follow-up de uma lista de documentos, com dois níveis
  (nível 1 = agrupamento por escopo, nível 2 = documentos) e uma única coluna
  `PREDECESSOR`. Do **Controle de Documentos** vêm as datas de planejamento,
  consolidadas na coluna `DATA-ALVO EMISSÃO` (reprogramada > prevista) que o
  dashboard lê, e a descrição dos documentos que o Aconex ainda não conhece.
  Todas as colunas de data saem no formato **Data** do Excel (não
  "Personalizado"), que o Power BI lê como data; texto digitado numa coluna de
  data é apontado no log, porque impede essa leitura.
  Duas análises que se complementam: **🗓️ Analisar Período** lista o que está
  previsto para emitir (atalhos: vencidos, próximos 7/30/90 dias, mês que vem),
  e **⏳ Analisar Mudanças por Período (Delta)** mostra o que aconteceu entre
  duas datas. Ambas exportam Excel.
  Detalhes em [`docs/doc_list_mapping.md`](docs/doc_list_mapping.md).
- **🔎 Status Documentos** - status real de documentos. Escolha a origem na aba:
  *Via Arquivo Excel* (arquivo + colunas), *Via Lista Rápida* (colar códigos) ou
  *Todos Aconex* (todos os vigentes). Botões no rodapé: **Gerar Status Atual**
  (Excel + gráfico) e **Analisar Delta do Período** (como os documentos daquela
  aba mudaram, agrupado por metadado).
- **📊 Histórico e Dashboard** - na aba *Planilha*, gera o Histórico Consolidado
  (1 linha por revisão + colunas de atraso Itaipu/CMI). Na aba *Dashboard*, sobe
  o painel web executivo (evolução do atraso, First Time Right, gargalos...).
- **📋 Relatórios** - Relatório de Avanço, Auditoria de Integração e **Fluxos em
  Andamento** (onde cada documento está e com quem: etapa atual, responsável,
  vencimento e dias de atraso). O de fluxos usa a **base de Fluxos**, que tem
  seletor de arquivo próprio - não é a base de documentos.
  Detalhes em [`docs/fluxos_de_trabalho.md`](docs/fluxos_de_trabalho.md).
- **📥 Extração Aconex** - baixa a base completa do Aconex via API (precisa das
  credenciais cadastradas; ver "Primeiro uso" acima). Operação longa (~30 min em produção). **Se a conexão cair, o progresso
  não se perde**: cada página baixada fica guardada e a próxima execução retoma
  de onde parou (o app avisa no log). Uma extração interrompida é sinalizada como
  **parcial** - você escolhe se quer o Excel do que já veio.
  Na aba **🔀 Fluxos de Trabalho** baixa os workflows (etapa, prazo e a quem cada
  documento está atribuído), com seletor de período: "tudo" leva ~20 min, mas
  "últimos 30 dias" atualiza em ~1 min.
- **⚙️ Configurações** - **Credenciais do Aconex** (cadastrar, editar, remover),
  **Atualizações** do app, a *Regra da Aprovação Intermediária* (VIP) e a base do
  atraso CMI na 0A.

---

## Arquitetura (visão rápida)

```
ui/            interface (CustomTkinter) - uma view por módulo
  ↓ importa só de
*_backend.py   backend público de cada módulo (na raiz do pacote):
               mapa_backend · doclist_backend · status_backend ·
               historico_backend · relatorios_backend · controle_backend ·
               aconex_backend
  ↓ apoiado em
common.py      funções compartilhadas (carga da base, índice de identidade,
               linha da verdade, motores de status, KPIs) - o "cérebro" comum
  ↓ implementado por
core/          lógica pura, 100% testável (constantes, status, wide, atrasos...)
services/      I/O (Excel, config, orquestrações)
dashboard/     app web (Dash/Plotly)
```

Cada módulo tem **um** backend, que é a única porta que a interface enxerga. O que
é comum a vários módulos mora em `common.py`. A implementação detalhada e testada
fica em `core/` e `services/`.

Documentos de apoio: `docs/entendimento_projeto_e_dados.md` (o que é o projeto e
os dados), `docs/controle_de_documentos.md` (estrutura do Controle),
`knowledge_base_docmanager.md` (regras de negócio do domínio).

## Desenvolvimento

```bat
pip install -r requirements-dev.txt
pytest          REM roda a suíte de testes
```
