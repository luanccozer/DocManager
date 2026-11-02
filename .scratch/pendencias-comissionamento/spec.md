# Tarefa: atualizar a planilha de mapeamento de pendências direto do Aconex (Campo → Questões)

Status: ready-for-agent

**Para:** a IA que vai implementar no repositório `luanccozer/DocManager` (Python 3.10+, Qt/PySide6, pytest, ruff).

**Você não tem acesso** à planilha real, ao Box nem ao Aconex. Tudo o que importa sobre eles foi medido nos arquivos reais e na API real em 01 e 02/11/2026 e está neste documento:

- **"medido"** ou **"validado"** quer dizer conferido contra dados reais;
- **"não verificado"** quer dizer que ainda não apareceu caso real para conferir. Trate esses pontos de forma defensiva e registre no log.

---

## 0. Antes de escrever código

1. Leia, nesta ordem:
   - `CLAUDE.md`, `docs/agents/domain.md`, `docs/agents/issue-tracker.md`, `GLOSSARY.md`;
   - `docs/adr/0001-data-prevista-e-a-baseline.md`;
   - na `knowledge_base_docmanager.md`: §18.2 (API Aconex), **§24.12 (Workflows API, o modelo da extração)**, §27.1 (I/O do Doc List), §28 (extração retomável), §31 (gravar a planilha no Windows).
2. Este documento já está no repositório, no branch **`claude/pendencias-comissionamento`**, como `.scratch/pendencias-comissionamento/spec.md`. As tarefas da seção 15 estão em `.scratch/pendencias-comissionamento/issues/NN-slug.md`, com `Status: ready-for-agent`.
3. Trabalhe **nesse mesmo branch** e abra PR para `main`. Não crie tag nem mude a versão.
4. Regra do repositório: nenhuma planilha real, nome de pessoa real ou código/TAG real em arquivo versionado. Testes e documentação usam dados fictícios.
5. **Reaproveite, não recrie.** Antes de escrever qualquer função utilitária, procure no repositório (`grep`). Se já existir algo que faz o mesmo ou quase o mesmo, reutilize ou generalize no lugar. Duplicar é defeito de revisão. A seção 11 lista o que já existe; comece por ela.

---

## 1. O que o usuário quer

A equipe acompanha as **Questões** do módulo **Campo** do Aconex, que ela chama de **pendências de comissionamento**, numa planilha Excel própria: a **"ACONEX - MAPEAMENTO PENDÊNCIAS.xlsx"**. Ela nasceu de uma exportação do Aconex e ganhou:

- colunas preenchidas à mão;
- um destaque de cor;
- duas tabelas dinâmicas com gráficos;
- abas de apoio.

Hoje, atualizar essa planilha é manual. O usuário quer um **módulo novo no DocManager, chamado "Pendências"** (na barra lateral, como os outros), que faz **só isto**:

1. a pessoa escolhe a planilha de pendências;
2. o app, na hora, busca as questões direto na API do Aconex;
3. e já grava na planilha:
   - **as pendências novas entram no topo**, com as colunas preenchidas e a mesma formatação das outras linhas;
   - **as que já estavam têm as colunas do Aconex atualizadas**;
   - **as colunas manuais nunca são tocadas**;
   - **tabelas dinâmicas, gráficos e o resto da pasta de trabalho continuam funcionando**.

Nas palavras dele: "não quebre nada", "mantenha as mesmas formatações e a mesma ideia central", "a escrita no Excel não pode corromper os arquivos".

---

## 2. Decisões

### Do usuário (fixas)

- **D1 – Linhas existentes:** além de inserir as novas, regravar nas linhas existentes as colunas que vêm do Aconex. Colunas manuais: nunca.
- **D2 – Posição:** novas no **topo** da tabela, em ordem decrescente de `Issue Number` (a planilha está em ordem decrescente). As existentes descem inteiras, com as colunas manuais. Se houver algo que não dá para deslocar com segurança, **não grava e explica**.
- **D3 – Segurança:** nenhum cenário de erro pode deixar a planilha corrompida ou gravada pela metade. Formatação, tabelas dinâmicas e gráficos ficam como estão.
- **D4 – Reaproveitamento:** usar o que o app já tem (seletor de Excel, barra de execução, credenciais, gravação, tela de aceite).
- **D5 – Cor de destaque:** a linha inteira é pintada com a cor da legenda da linha 2 quando a pendência é **Impeditiva e não está Closed**. A regra vale nas **novas e nas existentes**:
  - a cor **entra** quando a linha passa a cumprir a regra;
  - a cor **sai** quando deixa de cumprir (fechou, ou deixou de ser impeditiva);
  - fonte (azul, negrito), bordas, alinhamento e alturas feitos à mão **não mudam**.
- **D6 – Apagar só com decisão:** quando, numa coluna do Aconex, a planilha tem valor e o Aconex está **vazio**, o app **mostra a lista antes de gravar** e a pessoa decide apagar ou manter (todas ou caso a caso). Valor diferente e **não vazio** é sempre atualizado.

### Do planejador (revisáveis no PR; aplique como estão se não houver motivo forte)

- **C1 – Onde fica a tela (decisão do usuário):** um **módulo novo "Pendências"**, na barra lateral e na tela inicial. **Não** é uma aba de outra tela. A tela é mínima: o seletor da planilha, a barra de execução e o log. O molde é `TranspasseView` (seção 10).
- **C2 – Tudo ou nada:** qualquer falha na API (depois das retentativas), em uma regra de segurança ou na validação significa que **nada** é gravado.
- **C3 – Sem pergunta final (decisão do usuário: "já colocar dentro da planilha"):**
  - escolher a planilha **dispara a atualização sozinha** e ela grava direto, sem "Gravar?";
  - a segurança vem da validação, do backup e da troca atômica (C2, C4, C5);
  - a única pergunta possível é a lista de apagamentos do D6, quando houver;
  - no fim, um aviso com o resumo do que mudou (seção 10);
  - se nada mudou, não grava e avisa.
- **C4 – Backup:** antes de substituir, o app copia o original para `Documentos\DocManager_Itaipu\backups\`, mantendo os 20 últimos por nome de arquivo.
- **C5 – Substituição segura compartilhada:** a lógica de "temporário + conferência + backup + troca atômica + tentar de novo" vira **uma** função em `gravacao.py`, usada por esta funcionalidade **e** pelo `salvar_planilha` que Doc List e Mapa já usam (seção 9).
- **C6 – Escrita cirúrgica:** esta funcionalidade **não regrava a pasta com o openpyxl** (seção 4, medido). Ela edita o XML só das partes que precisam mudar e copia todas as outras **byte a byte**.
- **C7 – Colunas:** coluna do Aconex ou coluna manual é decidido pelo **nome** (seção 7). O app nunca cria, remove ou reordena colunas. As colunas da exportação que a equipe tirou da planilha são ignoradas.
- **C8 – Tipos:**
  - `Issue Number` é **número**;
  - texto novo é gravado como string embutida na célula (`inlineStr`);
  - data segue a **célula**: se a célula atual já é data real do Excel e o valor do Aconex é o mesmo dia, ela fica intocada; se mudou, grava data real (serial) com o mesmo estilo. Nas linhas novas, datas vão como texto `AAAA-MM-DD`, o tipo predominante da coluna.
- **C9 – Questão que sumiu:** se uma pendência está na planilha mas não existe mais no Aconex, a linha fica intacta e entra no log.
- **C10 – Memória das recusas (D6):** quem escolher **manter** um valor não é perguntado de novo pela mesma célula enquanto ela tiver o mesmo valor e o Aconex continuar vazio. A memória fica em `credenciais.pasta_dados()/pendencias_mantidas.json`, nunca dentro da planilha.
- **C11 – Escopo v1:** os dados precisam estar numa **Tabela do Excel** que tenha a coluna `Issue Number`, em qualquer aba. O app **acha a tabela sozinho**, sem pedir a aba. Nenhuma ou mais de uma → recusa com mensagem.
- **C12 – Credenciais:** o módulo usa o usuário do Aconex já cadastrado no app, o primeiro da lista. É a mesma regra da extração sem janela (`extracao_headless.py`). O proxy é detectado sozinho. Sem ninguém cadastrado, o módulo abre o cadastro que já existe (`credenciais_dialog.cadastrar`). Nenhum campo de credencial na tela do módulo.

### Não-objetivos (v1)

- opções na tela do módulo (seletor de aba, de usuário, de proxy, de período): **o módulo faz só isto**;
- criar colunas para campos que a planilha não tem;
- marcar visualmente o que mudou (além da regra D5);
- aceitar `.xls`, `.xlsm` ou `.xlsb`;
- escrever no Aconex (a integração é só GET);
- mexer na extração do register (`aconex_backend._baixar_pagina`);
- linha de comando;
- atualizar sozinho o cache das tabelas dinâmicas (o próprio Excel faz isso ao abrir; seção 3).

### Anti-objetivos (é falha mesmo que "funcione")

- mudar valor ou formato das colunas manuais;
- reordenar as linhas existentes;
- perder ou alterar gráfico, tabela dinâmica, coluna oculta, painel congelado, largura, altura, fonte;
- regravar a pasta com openpyxl, pandas ou XlsxWriter;
- reserializar XML com `ElementTree`;
- o Excel pedir "reparo" ao abrir;
- deixar arquivo `~$docmanager-*` para trás.

---

## 3. A planilha alvo (medida)

**"ACONEX - MAPEAMENTO PENDÊNCIAS.xlsx"**, gravada pelo Microsoft Excel, cerca de 97 KB.

**Abas, em ordem:**

| Aba | Conteúdo |
|---|---|
| `PENDÊNCIAS` | os dados (detalhes abaixo) |
| `GRÁFICO SITUAÇÃO` | tabela dinâmica (contagem de Issue Number por Status) + **gráfico dinâmico** de barras |
| `GRAFICO RESPONSÁVEL` | tabela dinâmica (por Classificação e Status) + **gráfico dinâmico** de barras |
| `TIPOS PENDÊNCIA` | texto fixo (conceitos) |
| `Planilha1` | resumo fixo digitado |

**Partes do pacote:**

- `worksheets/sheet1..5`, `sharedStrings`;
- `styles`: 103 `cellXfs`, 8 `fills`, 25 `fonts`, 26 `dxfs`;
- `theme`;
- `tables/table1` (a tabela `tbRegistros`);
- `pivotCache/pivotCacheDefinition1` + `pivotCacheRecords1`;
- `pivotTables/pivotTable1` e `pivotTable2`;
- `drawings/drawing1` e `drawing2`;
- `charts/chart1` e `chart2`, com `style` e `colors`;
- `printerSettings1.bin`.

**Tabelas dinâmicas:** o cache usa como fonte **o nome da tabela** (`worksheetSource name="tbRegistros"`) e tem `refreshOnLoad="1"`. Quando a tabela crescer, o **Excel atualiza tabelas dinâmicas e gráficos sozinho ao abrir o arquivo**. Não mexa no cache.

**Nenhuma** fórmula, nome definido, série de gráfico ou cache aponta para intervalos fixos da aba `PENDÊNCIAS` (verificado). Por isso deslocar as linhas é seguro.

### Aba `PENDÊNCIAS`

- **Linha 2:** legenda. `A2` é um quadrado com a **cor de destaque**; `B2` = `IMPEDITIVAS SITUAÇÃO "OPEN"`. Linhas 1 e 3 vazias.
- **Tabela do Excel `tbRegistros`**, `ref="A4:V132"`:
  - cabeçalho na **linha 4**;
  - **128 pendências nas linhas 5–132**;
  - `autoFilter` com a mesma `ref`;
  - sem linha de total;
  - **sem colunas calculadas**;
  - cada coluna com `dataDxfId`.
- **Ordem:** decrescente por `Issue Number` (131 no topo).
- **As 22 colunas, em ordem:**

| Col | Cabeçalho | Origem |
|---|---|---|
| A | Issue Number | Aconex (chave; **número**) |
| B | Issue Type | Aconex |
| C | Area | Aconex |
| D | Location Detail | Aconex |
| E | Issue Description | Aconex |
| F | Captured On | Aconex (texto `AAAA-MM-DD` em 107 linhas; **data real do Excel em 21**, convertidas pela equipe) |
| G | Captured by | Aconex |
| H | Status | Aconex |
| I | Departamento Responsável | **manual** |
| J | Responsável | **manual** |
| K | Acompanhamento da Ação | **manual** |
| L | Respondida Aconex | **manual** (datas como número serial) |
| M | Due Date | Aconex (**coluna oculta**) |
| N | TAG RDS-PP | Aconex (campo customizado) |
| O | Clasificación de pendencia | Aconex (campo customizado) |
| P | Documentos de referencia | Aconex (campo customizado) |
| Q | Fecha prevista para corrección | Aconex (campo customizado) |
| R | Cierre | Aconex (campo customizado) |
| S | Área del Solicitante | Aconex (campo customizado) |
| T | ¿Pasó a comisionamiento? | Aconex (campo customizado) |
| U | Área responsable SM.DT | Aconex (campo customizado) |
| V | Comments | Aconex |

A exportação do Aconex tem mais 12 colunas que a equipe tirou: Assigned On/to/By, Closed On, Closed By User/Organization, Pinned To DocNumber, Doc Title, Source, Listed In, - Contratada, Etapa del contrato. **Ignore-as.**

**Aparência da aba:**
- painel congelado em `C5` (2 colunas e 4 linhas), sem linhas de grade;
- larguras e estilo por coluna (`<col style=…>`);
- linhas de dados com altura personalizada: 25,5 ou 50,15 na maioria, algumas 50 ou 52.

**Não tem**, em nenhuma aba: fórmula, formatação condicional, validação de dados, mesclagem, hyperlink, comentário, nome definido.

### Formatação (modelo medido nas 128 linhas)

| Tipo de linha | `s` do `<row>` | Preenchimento |
|---|---|---|
| **Normal** | `s="19"` | nenhum, exceto **H (Status) cinza** (`theme=2 tint=-0.1`) e **I–L (manuais) em tom claro** (`theme=3 tint=0.9`) |
| **Destacada** (D5) | `s="22"` | **a linha inteira A–V** na cor da legenda (`theme=5 tint=0.4`) |

- **Regra do destaque, conferida em 128/128 sem exceção:** destacada ⇔ `Clasificación de pendencia` = `Impeditiva` **e** `Status` ≠ `Closed`. Hoje são 42 destacadas (36 Open, 4 In dispute, 2 Work Done) e 86 normais.
- **Formatação à mão, sem regra** (preservar sempre):
  - 10 linhas com **fonte azul** (`FF0070C0`);
  - negrito em algumas células de K e L;
  - a coluna T pintada com a cor de destaque em 29 linhas normais;
  - alturas variadas;
  - algumas células de M sem a cor nas linhas destacadas.
- Os números (`19`, `22`, temas e tons) são **deste arquivo**. **Descubra-os pelos dados** (seção 8.4); nunca fixe no código.

### Diferenças entre a planilha e o Aconex (estado de 01/11)

Explicam as decisões D1 e D6. Primeira atualização prevista:

| O que acontece | Quantidade | Detalhe |
|---|---|---|
| Novas no topo | 19 | 132 a 150; 5 entram destacadas |
| Linha que perde o destaque | 1 | passou de Work Done para Closed |
| Trocas automáticas | 2 | 1 Status e 1 descrição |
| Preenchimentos automáticos | 21 | 5 linhas tinham os valores desalinhados uma coluna para a direita, o que esvaziou TAG, Área del Solicitante, Área responsable e Location Detail; mais 1 Documentos de referencia |
| Apagamentos para decidir (D6) | 6 | 5 células de `¿Pasó a comisionamiento?` com o texto do TAG deslocado + 1 `Fecha prevista para corrección` com uma data digitada à mão |
| `Captured On` com data real e mesmo dia | 21 | **não contam como mudança** |

---

## 4. Por que a escrita é cirúrgica (medido)

Abrir e salvar essa pasta com `openpyxl.load_workbook` + `save` (sem alterar nada) produziu:

- **perda** de `xl/charts/style1.xml`, `style2.xml`, `colors1.xml`, `colors2.xml` e das relações deles;
- **perda** de `xl/printerSettings/printerSettings1.bin`;
- **perda** do `extLst` dos dois gráficos dinâmicos (opções do gráfico dinâmico);
- reescrita de tabelas dinâmicas, desenhos e da definição da tabela;
- **a coluna oculta M voltou a aparecer**.

Isso viola D3. Pandas e XlsxWriter recriam o arquivo e são piores.

Por isso a gravação desta funcionalidade:

- **altera somente** estas partes:
  - o XML da aba da tabela: só o `<sheetData>` e o `<dimension>`;
  - o XML da tabela: só o atributo `ref` do `<table>` e do `<autoFilter>`;
  - **se e só se** a regra D5 precisar de um estilo que ainda não existe: `xl/styles.xml`, **acrescentando** `<xf>` no fim de `<cellXfs>` e atualizando o `count`. Os índices existentes nunca mudam.
- **copia todas as outras partes do zip byte a byte**, com o mesmo nome, a mesma ordem e a mesma compressão.

**Leitura:** `zipfile` + `xml.etree.ElementTree` servem para **ler**.

**Escrita:** edite o **texto** XML original. **Nunca reserialize com `ElementTree`:** ele renomeia os prefixos de namespace (`x14ac`, `xr`…) e quebra `mc:Ignorable="x14ac xr xr2 xr3"`, e o Excel acusa arquivo corrompido.

**O openpyxl continua útil** para abrir o resultado no validador (só leitura) e para montar fixtures de teste.

### Escolha da biblioteca

O usuário deixou a escolha livre, desde que não quebre o Excel e escreva certo. **A escolhida é:**
- `zipfile` e `xml.etree.ElementTree` (este só para ler), da biblioteca padrão;
- mais a edição do texto XML das partes alteradas.

Motivos:
- é o único caminho **provado no próprio Excel** com esta planilha (Apêndice D): sem reparo, com tabelas dinâmicas, gráficos e coluna oculta intactos;
- não acrescenta dependência ao instalador.

Se quiser trocar (ex.: lxml para editar a árvore XML preservando os prefixos), **repita antes a prova do Apêndice D** e registre a troca no ADR.

---

## 5. A API do Aconex Field (contrato validado ao vivo)

**Base:** `{config.instance}/field-management/api/projects/{config.project_id}`. Atenção: é `/field-management/api/...`, não o `/api/projects/...` do register.

**Instância e projeto:** `https://us1.aconex.com`, projeto `1207975853` (os de `AconexConfig`).

**Autenticação:** o **mesmo token Bearer** do register e dos Workflows (`_estabelecer_sessao`). Sem token, a resposta é `401 {"message":"Authentication Failed"}`. A credencial que o DocManager já usa foi aceita.

**Cabeçalhos:**
- `Accept: application/json`;
- `Authorization: Bearer <token>`.

A versão V2 (`application/vnd.aconex.issues.v2+json`) só acrescenta `permissions`: não use.

**Especificação oficial:** `https://us1.aconex.com/field-management/openapi` (Field APIs 2.6.0). Swagger: `https://us1.aconex.com/api/core/docs/index.html?urls.primaryName=Field`.

**Limites:** no máximo 5 req/s e 10 simultâneas **por organização** (todas as integrações da CMI dividem a cota). Pause 250 ms entre chamadas. Em 503 ou falha de rede, retentativa com espera crescente; em 401, renove o token.

### Rotas (todas GET)

| # | Rota | Para quê | Resposta (o que importa) |
|---|---|---|---|
| 1 | `/areas` | Achar a raiz | `{"areas":[{"id","name","children":[...aninhados...]}]}`. É a **árvore inteira**; o 1º nível são as raízes. No projeto há 1 raiz e 117 áreas. **Descubra a cada execução.** |
| 2 | `/customfields` | Tipo e rótulo dos campos customizados | `{"custom_fields":[{"id","family_id","label","type":{"name","specification":{"options":[...]}}}]}`. São cerca de 60 campos do projeto (todos os módulos). |
| 3 | `/issue_types` | **Quais** campos customizados pertencem às questões | `{"issue_types":[{"id","name","enabled","custom_fields":[{"id","family_id","label","type"}]}]}`. São 9 tipos e a resposta tem cerca de 5 MB (opções das listas). As questões de hoje usam 3 tipos, todos com os mesmos 10 campos. |
| 4 | `/areas/{raiz}/issues?include_child_areas=true&include_shared=true&page_size=200&page_number=N&sort_by=issue_number&sort_order=desc` | Todas as questões | `{"issues":[...],"total_results","total_pages","page_number",...}`. O máximo é **200 por página**. Pagine até `page_number >= total_pages` e deduplique por `issue_id`. Hoje: 147 questões, 1 página. |
| 5 | `/issues/{issue_id}/conversations/all?supportPublicConversation=true` | Texto de `Comments` | Ver 5.2. **Sem `supportPublicConversation=true` os comentários "With Everyone" não vêm.** Esta rota **não** tem `/areas/...`. |

O bloco `conversations` da rota 4 vem com `comments: []` mesmo quando há comentários: **não use**. A rota `/issues/count` responde num formato diferente do documentado; `total_results` basta.

**Custo:** 4 chamadas + 1 por página + 1 por questão (Comments). Hoje são cerca de 150 chamadas, por volta de 1 minuto. Só busque comentários se a tabela tiver a coluna `Comments`.

### 5.1 Questão: campos usados

`issue_id`, `issue_number`, `description`, `status`, `location_detail`, `issue_type{id,name}`, `area{name, path[{name}]}`, `meta_data{created_at, created_by{first_name,last_name}}`, `due_date`, `custom_fields[{id, family_id, value}]`.

- `status` é um destes: `Open`, `InDispute`, `ReadyToInspect`, `WorkDone`, `Closed`.
- `created_at` vem em UTC: `2026-09-18T16:46:45.059Z`.
- `due_date` vem como `2026-10-30T12:00:00.000Z`.
- Campo customizado do tipo `date` vem como `2026-10-30`.

Estrutura completa no Apêndice B.

### 5.2 Conversas (Comments)

```json
{"_embedded":{"conversations":[
  {"participant":{"id":"-1","name":"Everyone","trading_name":"Everyone"},
   "comments":[{"content":"texto","client_captured_at":"2026-09-30T11:23:10.953Z",
                "author":{"first_name":"FULANO","last_name":"DE TAL",
                          "organization":{"name":"CONSÓRCIO EXEMPLO","trading_name":"CMI"}}}]},
  {"participant":{"id":"20","name":"ITAIPU BINACIONAL","trading_name":"ITAIPU BINACIONAL"},"comments":[]}
]}}
```

---

## 6. De-para: coluna ← API (validado)

Uma tabela montada com estas regras ficou **idêntica** a uma exportação manual do Aconex em **4.263 de 4.263 células** (147 linhas × 29 colunas). `Comments` bateu em **35 de 35** células. O código está no Apêndice A.

| Coluna | Valor |
|---|---|
| Issue Number | `issue_number` → gravar como **número** nesta planilha |
| Issue Type | `issue_type.name` |
| Area | nomes de `area.path` + `area.name`, unidos por `" > "`. Se o último do `path` já for a própria área, não repete. |
| Location Detail | `location_detail` |
| Issue Description | `description` |
| Captured On | `meta_data.created_at` **convertido para UTC−3** → `AAAA-MM-DD` |
| Captured by | `created_by.first_name + " " + last_name` (sem mudar maiúsculas) |
| Status | `Open`→`Open`, `InDispute`→`In dispute`, `WorkDone`→`Work Done`, `Closed`→`Closed`, `ReadyToInspect`→`Ready to inspect` (**não verificado**). Valor desconhecido: grava o cru e avisa no log. |
| Due Date | `due_date`, só a data, **sem** converter fuso |
| campos customizados | ver regras abaixo |
| Comments | ver regras abaixo |

**Campos customizados** (cabeçalho = `label` do campo):

- **Casar pelo `family_id` primeiro e só depois pelo `id`.** O `id` muda a cada versão da definição: o da "TAG RDS-PP" nas questões não bate com o de `/customfields`; o `family_id` bate.
- `single_select`, `single_line_text` e `multi_line_text`: o `value` já é o texto.
- `date`: `AAAA-MM-DD`.
- `boolean`: `Yes`→`Sim`, `No`→`Não`.
- `value` nulo, ou campo ausente da questão: vazio.
- Tipos `user` e `multi_select` (**não verificados**): grave o texto cru e avise no log.

**Comments** (validado 35/35):

- Um bloco por conversa com comentário:
  - o bloco `With Everyone:` (participant `id == "-1"`) vem **primeiro**;
  - depois as organizações, na ordem da API.
- Título do bloco: `With <participant.trading_name>:`.
- Cada comentário, em ordem cronológica, numa linha:
  `"<content>" submitted by <first_name> <last_name> (<author.organization.trading_name>) on <Ddd>, <Mmm> <d>, <aaaa>, <h>:<mm>:<ss> <am|pm>`
- Data e hora em **UTC−3**, nomes em inglês, hora 1–12: `Wed, Sep 30, 2026, 8:23:10 am`. Meia-noite vira `12:..:.. am`; meio-dia vira `12:..:.. pm`.
- **Blocos separados por uma linha em branco** (`"\n\n"`); linhas do bloco por `"\n"`.

**Fuso:** UTC−3 fixo, `timezone(timedelta(hours=-3))`. Brasil e Paraguai não têm horário de verão.

---

## 7. Colunas do Aconex × colunas manuais

Os nomes das colunas vêm dos `<tableColumn name="…">` da tabela. Compare com `normalizar_cabecalho` (seção 11).

**É coluna do Aconex:**
- uma das padrão da exportação: `Issue Number`, `Issue Type`, `Area`, `Location Detail`, `Issue Description`, `Captured On`, `Captured by`, `Status`, `Due Date`, `Assigned On`, `Assigned to`, `Assigned By`, `Closed On`, `Closed By User`, `Closed By Organization`, `Listed In`, `Comments`;
- ou um **campo customizado das questões**: a união de `custom_fields` dos tipos de `/issue_types` cujo `id` aparece em `issue_type.id` das questões baixadas (hoje, os 10 da tabela da seção 3).

> **Não use** todos os cerca de 60 rótulos de `/customfields`. Eles incluem campos de outros módulos ("Especialidad", "Idioma"…). Se a equipe criar uma coluna manual com um desses nomes, ela seria tomada por coluna do Aconex e esvaziada.

**Mapeamento de `Assigned to`, `Assigned By` e `Closed …`, para quando a equipe voltar a ter essas colunas:**

| Coluna | Valor |
|---|---|
| Assigned On | `assigned_at` em UTC−3 |
| Assigned to / Assigned By | `assigned_to` / `assigned_by` → `organization.trading_name` (o nome fantasia, ex. "CMI") |
| Closed On | `closed_at` em UTC−3 |
| Closed By User | nome de `closed_by` |
| Closed By Organization | `closed_by.organization.trading_name` |
| Listed In | `issue_listings[].title` unidos por `"; "` |

`Pinned To DocNumber`, `Doc Title` e `Source` não têm fonte validada: se aparecerem, **não toque** nas existentes.

**Qualquer outra coluna é manual** e nunca é tocada. Na tabela real: I, J, K e L.

**Recusas:**
- cabeçalho do Aconex duplicado na tabela;
- `Issue Number` ausente.

Campo das questões que não tem coluna na planilha: só log.

---

## 8. Algoritmo

A lógica fica em `docmanager/services/`. A tela só chama.

### 8.1 Localizar a tabela (só leitura)

1. Abra o `.xlsx` com `zipfile`. Guarde a **assinatura** do arquivo (`st_mtime_ns`, `st_size`).
2. Percorra as abas: `xl/workbook.xml` (`<sheet name r:id>`) → `xl/_rels/workbook.xml.rels` → `xl/worksheets/sheetN.xml`.
3. Para cada aba, ache as tabelas dela: `xl/worksheets/_rels/sheetN.xml.rels` (`…/table`) → `xl/tables/tableM.xml`.
   - Use **a única tabela da pasta** que tem `<tableColumn name="Issue Number">`. A aba dela é a aba de dados.
   - Nenhuma ou mais de uma → recusa (C11). A tela não pede a aba.
4. Pela `ref` da tabela (ex.: `A4:V132`):
   - cabeçalho = primeira linha;
   - corpo `d..L` = segunda linha até a última;
   - colunas = da primeira à última letra, na ordem dos `<tableColumn>`.
5. Leia `xl/sharedStrings.xml` (texto de cada `<si>`, juntando os `<t>` de runs `<r>`) e `xl/styles.xml`:
   - `<cellXfs>`, `<fills>`, `numFmts`;
   - quais `numFmtId` são de data: os embutidos 14–22 e 45–47, e os personalizados cujo código tem `d`, `m` ou `y` fora de aspas e colchetes.
6. Leia as linhas do corpo. Para cada `<c>`:
   - **valor**: `t="s"` → shared string; `t="inlineStr"` → texto de `<is>`; sem `t` → número (data, se o estilo for de data); `t="str"` ou `t="b"` → texto ou booleano;
   - **estilo**: `s`.
   Guarde também os atributos de cada `<row>`.

### 8.2 Regras de segurança (checar ANTES; se alguma falhar, recusar sem gravar)

A mensagem explica, em palavras simples, o que foi encontrado e o que fazer.

**A. Na aba da tabela, recuse se houver:**

| Elemento | Em palavras simples |
|---|---|
| `<f>` | fórmula |
| `<mergeCells>` | células mescladas |
| `<conditionalFormatting>` | formatação condicional |
| `<dataValidations>` | lista suspensa ou validação |
| `<hyperlinks>` | hyperlink |
| `<legacyDrawing>` | comentário de célula |
| `<drawing>` | gráfico ou imagem na própria aba de dados |
| `<rowBreaks>` | quebra de página manual |
| `<sheetProtection>` | aba protegida |
| `<extLst>` com `x14:` | recursos avançados do Excel |

**B. Na pasta toda, recuse se houver:**
- fórmula (`<f>` em qualquer aba), **nome definido**, **série de gráfico** (`<c:f>` em `xl/charts/*.xml`) ou **origem de cache dinâmico** (`<worksheetSource ref=… sheet=…>`) que aponte para **intervalo de células** da aba da tabela;
- `xl/vbaProject.bin`.

Cache cuja origem é o **nome** da tabela (`worksheetSource name=`) é permitido: é o caso real.

> **Cuidado com falso positivo.** Os gráficos dinâmicos citam o nome do arquivo no `<c:pivotSource>` (ex.: `[ACONEX - MAPEAMENTO PENDÊNCIAS_x.xlsx]GRÁFICO SITUAÇÃO!Tabela dinâmica3`), e o nome contém "PENDÊNCIAS". Só conta como referência à aba o formato de célula: `Aba!A1`, `Aba!$A$1:$B$9` ou `'Aba com espaço'!A1`, com o nome exato da aba antes do `!`. Um teste ingênuo de substring recusaria a planilha real.

**C. Na tabela, recuse se:**
- tiver linha de total (`totalsRowCount` ou `totalsRowShown="1"`);
- tiver coluna calculada (`calculatedColumnFormula`);
- houver **qualquer célula com valor abaixo de `L`** na aba.

**D. No corpo da tabela, recuse se:**
- alguma linha não tiver `Issue Number` inteiro positivo;
- houver número repetido;
- faltar o atributo `r` em algum `<row>` ou `<c>` (o Excel sempre escreve).

### 8.3 Planejar (em memória)

1. Busque a API (seção 5) e monte os valores por questão (Apêndice A).
2. Classifique:
   - **novas** = na API e não na tabela, em ordem decrescente;
   - **existentes** = nas duas;
   - **só na planilha** = linha intacta + log.
3. **Existentes**, em cada coluna do Aconex, compare o valor atual com o novo:
   - normalize: `None` = `""`, `strip`, espaços colapsados;
   - **data compara como data**: data real `2026-10-26` = texto `"2026-10-26"`;
   - `Issue Number` como número.

   | Planilha | Aconex | O que fazer |
   |---|---|---|
   | igual | igual | nada |
   | qualquer | valor diferente, não vazio | **troca automática** |
   | vazio | valor | **preenchimento automático** |
   | valor | vazio | **apagamento** → vai para a lista do D6 |

4. **Destaque (D5)** com os valores finais (depois das decisões do D6): `destacada = (Clasificación de pendencia == "Impeditiva") and (Status != "Closed")`. Compare com a situação atual da linha. Uma linha é "destacada hoje" quando a célula da coluna A tem o fill de destaque (8.4). Se as colunas da regra não existirem na tabela, não aplique D5 e avise.
5. **Apagamentos (D6):**
   - tire da lista os já mantidos antes (C10);
   - se sobrar algum, chame `decidir_cb(lista)`, a tela de aceite generalizada (seção 10).
   - Escolhas:
     - "Apagar todas";
     - "Manter todas" (grava na memória C10);
     - "Caso a caso" (as marcadas são apagadas, as desmarcadas mantidas e memorizadas);
     - fechar a janela = manter todas **sem** memorizar.
6. Se não há novas nem mudanças de valor ou de cor: **não grave** e avise "A planilha já está atualizada".
7. Grave (8.5 e seção 9), **sem pergunta final** (C3), e devolva o resumo para o aviso da seção 10.

### 8.4 Estilos (descobertos pelos dados, nunca fixos)

Com as linhas do corpo divididas em **destacadas** (cumprem a regra **hoje**, pelos valores **atuais** da planilha) e **normais**:

- **fill de destaque** = fill mais comum da coluna A nas destacadas;
- **fill normal da coluna X** = fill mais comum da coluna X nas normais;
- **estilo de linha** normal e destacado = `s` mais comum do `<row>` em cada grupo, com os demais atributos de `<row>` (`spans`, `customFormat`, `ht`, `customHeight`, `x14ac:dyDescent`) da linha mais comum do grupo;
- **modelo de célula** para linhas novas, por coluna e por grupo = o `s` mais comum dessa coluna naquele grupo;
- **sem nenhuma linha destacada** (sem exemplo da cor): não aplique D5, use só o modelo normal e avise no log. Nunca invente uma cor.

**Trocar a cor de uma célula existente (D5):**
- muda **só o `fillId`**:
  - entrando no destaque: só as células cujo fill atual é o **fill normal da coluna** dela;
  - saindo do destaque: só as células cujo fill atual é o **fill de destaque**;
  - outras células ficam como estão.
- para o novo `s`:
  - procure em `<cellXfs>` um `<xf>` **idêntico em tudo** (`numFmtId`, `fontId`, `borderId`, `xfId`, todos os `apply*`, `<alignment>`, `<protection>`) exceto `fillId` = alvo e use o índice dele;
  - se não existir, **acrescente** um `<xf>` no fim de `<cellXfs>` (cópia com o `fillId` trocado e `applyFill="1"`) e atualize o `count`.
- troque também o `s` do `<row>` (normal ↔ destacada).
- fonte, borda, alinhamento, formato de número e altura **nunca mudam**.

### 8.5 Escrever (no texto XML)

Seja `k` o número de novas.

**Aba da tabela (`sheetN.xml`):**

1. Isole `<sheetData>…</sheetData>`. Separe os `<row …>…</row>` ou `<row …/>` (não se aninham).
2. Linhas antes de `d` (legenda, cabeçalho): **intactas**.
3. **Novas**, em `d…d+k-1`, em ordem decrescente. Cada linha:
   - tag `<row>` copiada do modelo do grupo (normal ou destacada), trocando só o `r`;
   - uma `<c>` por coluna da tabela, com o `s` do modelo e o valor:
     - número (`Issue Number`): `<c r="A5" s="…"><v>150</v></c>`;
     - texto: `<c r="B5" s="…" t="inlineStr"><is><t xml:space="preserve">…</t></is></c>`;
     - vazio: `<c r="I5" s="…"/>`.
4. **Existentes**, renumeradas `+k`. Isso vale para **toda** `<row>` com `r ≥ d`, inclusive as que estiverem abaixo de `L` só com formatação (o Excel às vezes as grava); senão elas colidiriam com as linhas deslocadas.
   - no `<row>`, `r="N"` → `r="N+k"`;
   - em cada `<c>`, `r="XN"` → `r="X(N+k)"`. Nada mais na linha tem número de linha (a regra 8.2-A já excluiu fórmulas);
   - aplique as trocas e preenchimentos: substitua só o `<c>` daquela célula, mantendo o `s` (ou o novo `s` do D5);
   - apagamento aceito: `<c r=".." s=".."/>`;
   - data real que mudou: `<v>serial</v>` (serial = dias desde 1899-12-30), mantendo o `s`.
5. `<dimension ref="A2:V132"/>`: estenda a última linha em `+k`.
6. Nada mais da aba muda: `sheetViews`, `cols`, `pageMargins`, `tableParts`… ficam byte a byte iguais. Mantenha a declaração XML e a tag raiz exatamente como estavam.

**Texto de célula:**
- escape `&`, `<`, `>`;
- remova caracteres de controle proibidos em XML (todos abaixo de 0x20, menos `\t`, `\n`, `\r`);
- use `xml:space="preserve"`;
- corte acima de 32.767 caracteres com `… [cortado pelo DocManager]` e avise no log.

**Tabela (`tableM.xml`):** troque **só** o valor de `ref` do `<table>` e do `<autoFilter>`: `A4:V132` → `A4:V{132+k}`.

**`sharedStrings.xml` fica intacto.** Textos novos ou trocados vão como `inlineStr`, que o Excel aceita misturado com textos compartilhados. O atributo `count` do `<sst>` fica maior que o número real de referências. **Verificado no Excel 16** (Apêndice D): o arquivo abriu sem reparo.

**Estilos:** só se 8.4 precisou acrescentar `<xf>`.

**Pacote novo:** escreva no temporário um zip com **as mesmas entradas, na mesma ordem**:
- as alteradas com o conteúdo novo;
- todas as outras com **os bytes originais**.

Para manter nome, data e compressão, grave com **uma cópia** do `ZipInfo` da origem: `zout.writestr(copy.copy(info), dados)`.

> **Armadilha medida:** passar o próprio `info` da origem faz o `zipfile` alterá-lo ao gravar (posição no arquivo). A leitura da origem passa a falhar com `BadZipFile: Bad CRC-32`.

Se `k = 0`, só há atualizações nas linhas existentes: nada é renumerado e as `ref` não mudam.

---

## 9. Substituição segura (sem corromper)

Em `docmanager/services/gravacao.py`, extraia a lógica de `salvar_planilha` para **uma** função genérica, e faça `salvar_planilha` usá-la:

```python
def substituir_com_seguranca(caminho, escrever, *, validar=None, assinatura=None, backup=True,
                             retry_cb=None, log_cb=None, tentativas=3, espera_s=2.0) -> str | None:
    """`escrever(caminho_temp)` produz o arquivo novo. Devolve None se trocou, ou o motivo."""

def salvar_planilha(wb, caminho, *, retry_cb=None, log_cb=None, tentativas=3, espera_s=2.0, **kw):
    return substituir_com_seguranca(caminho, wb.save, retry_cb=retry_cb, log_cb=log_cb,
                                    tentativas=tentativas, espera_s=espera_s, **kw)
```

Sequência:

1. **Temporário na mesma pasta:** `tempfile.mkstemp(prefix="~$docmanager-", suffix=".xlsx", dir=pasta)`.
   - Mesma pasta para o `os.replace` ser atômico.
   - O `~$` é o prefixo dos arquivos de trabalho do Office, que o Box não sincroniza.
   - Feche o descritor e chame `escrever(tmp)`.
2. **Conferir:**
   - `zipfile.ZipFile(tmp).testzip() is None`;
   - `openpyxl.load_workbook(tmp, read_only=True)` abre;
   - `validar(tmp)` devolve lista vazia.
   Se falhar: apaga o temporário e devolve o motivo; **o original fica intacto**.
3. **Assinatura:** se foi passada e o arquivo mudou desde a leitura, aborte: "a planilha foi alterada enquanto o app trabalhava (Excel ou sincronização do Box); rode de novo".
4. **Backup:**
   - `shutil.copy2(original, credenciais.pasta_dados()/"backups"/f"{stem}__{AAAAmmdd-HHMMSS}{ext}")`;
   - mantenha os 20 mais recentes por `stem`;
   - se falhar, **aborte**;
   - registre o caminho no log.
5. **Troca:** `os.replace(tmp, caminho)` dentro do laço que já existe de "tentar de novo e, se continuar, perguntar":
   - o `PermissionError` pode vir de `escrever` ou do `os.replace` (Excel com o arquivo aberto);
   - o diagnóstico `motivo_da_recusa` continua igual.
6. `finally`: se o temporário ainda existir, apague-o.

**Testes:** os de `tests/test_gravacao.py` continuam passando; eles trocam o `wb.save` e isso segue valendo. Acrescente:
- falha no meio da escrita → original byte a byte igual e nenhum `~$docmanager-*`;
- validador reprova → original intacto;
- assinatura mudou → aborta;
- backup criado e só os 20 últimos mantidos;
- recusa no `os.replace` → pergunta e, ao resolver, troca.

Doc List e Mapa seguem passando nos testes deles.

---

## 10. Telas

### Módulo "Pendências" (`docmanager/ui/views/pendencias_view.py`, novo)

**Registro:**
- em `ui/main_app.py`, acrescente `ViewSpec("pendencias", "Pendências", "file-spreadsheet", PendenciasView)` em `VIEWS`, logo depois de "Transpasse de Fase";
- em `ui/views/home_view.py`, acrescente em `MODULOS` o cartão `("pendencias", "file-spreadsheet", "Pendências", "Atualiza a planilha de mapeamento de pendências de comissionamento direto do Aconex (Campo → Questões): as novas entram no topo e as colunas do Aconex ficam em dia; as colunas preenchidas à mão não são tocadas.")`.

O ícone `file-spreadsheet` já existe em `ui/recursos/icones` e nenhum módulo o usa.

**Tela** (molde: `TranspasseView`, que já é Card + FileSelector + RunBar):

| Elemento | Definição |
|---|---|
| `titulo_view` | `"Pendências"` |
| `subtitulo_view` | `"Planilha de mapeamento de pendências de comissionamento, atualizada direto do Aconex (Campo → Questões)"` |
| `Card("Planilha")` | `FileSelector("Planilha de pendências", cfg, "pendencias", filtro=dialogos.FILTRO_XLSX, escolher_aba=False, on_change=lambda _c: self.run.btn.click())`. Escolher o arquivo **dispara a atualização** (C3). Sem seletor de aba (C11). |
| Texto curto | "Ao escolher a planilha, o DocManager busca as pendências no Aconex e já grava: as novas entram no topo, as colunas do Aconex das que já estão na planilha são atualizadas e as colunas preenchidas à mão não são tocadas. Impeditivas não fechadas ficam com a cor da legenda. Antes de trocar o arquivo, o app confere o resultado e guarda uma cópia de segurança. Abra no Excel para as tabelas dinâmicas e os gráficos se atualizarem." |
| Barra | `self.run = RunBar("Atualizar Pendências", self._tarefa, self.log)`. O botão também serve para rodar de novo sem escolher o arquivo outra vez. |

**`_tarefa(run)`:**

1. Sem planilha escolhida: só avisa no log.
2. **Credenciais (C12):**
   - `nomes = aconex_backend.usuarios_disponiveis()`;
   - vazio → `na_ui_e_esperar(lambda: cadastrar(self.window()))` (de `credenciais_dialog`); se continuar vazio, avisa no log e para;
   - `config = AconexConfig.para_usuario(nomes[0])`, com o proxy detectado sozinho;
   - `KeyError` ou `ValueError` → mensagem no log.
3. `atualizar_pendencias(config, self.sel.path, log_cb=self.log.log, progress_cb=run.set_progress, retry_cb=lambda m: dialogos.tentar_de_novo("Salvar", m), decidir_cb=lambda itens: decidir_sobrescricoes(itens, self, textos=TEXTOS_PENDENCIAS))`.
4. Fim: `dialogos.info("Pendências", r.mensagem)` se ok; `dialogos.erro("Pendências", r.mensagem)` se recusa ou falha.

### Tela de aceite generalizada (`ui/views/sobrescricao_dialog.py`)

Hoje os textos são de "datas do Controle". Torne parametrizáveis o título, o resumo, o aviso, os rótulos das colunas e dos botões. Mantenha o padrão atual **idêntico** para Doc List e Mapa (os testes deles não mudam).

Para pendências:

| Elemento | Texto |
|---|---|
| Título | "Valores que o Aconex não tem mais" |
| Resumo | "N células têm valor na planilha, mas estão vazias no Aconex." |
| Aviso | "O que você mantiver não é perguntado de novo enquanto o valor for o mesmo." |
| Colunas | "Pendência", "Descrição", "Coluna", "Na planilha", "No Aconex" |
| Botões | "Apagar todas", "Manter todas", "Ver caso a caso" |

Cada item é um objeto com os atributos que o diálogo já lê: `codigo` (nº da pendência), `descricao`, `titulo_coluna`, `valor_planilha`, mais o valor novo ("(vazio)"). O retorno continua `DecisaoSobrescricao(aceitas, recusadas)`: aceitar = apagar.

### Aviso final (exemplo, depois de gravar)

"Planilha de pendências atualizada.
19 pendências novas no topo (nº 132 a 150); 5 delas impeditivas abertas, com a cor da legenda.
Atualizadas: 2 células (Status: 1; Issue Description: 1). Preenchidas: 21. Apagadas: 5. Mantidas: 1.
1 linha perdeu a cor (fechou).
Nenhuma pendência da planilha sumiu do Aconex.
Cópia de segurança: Documentos\DocManager_Itaipu\backups\…
Abra no Excel para as tabelas dinâmicas e os gráficos se atualizarem."

---

## 11. Reaproveite (não recrie)

| Preciso de… | Use o que já existe | Onde |
|---|---|---|
| Seletor da planilha (lembra a última pasta) e disparo ao escolher | `FileSelector(..., escolher_aba=False, on_change=...)` → `.path`; disparar = `self.run.btn.click()` | `docmanager/ui/components.py` |
| Molde de módulo simples | `TranspasseView` (Card + FileSelector + RunBar) | `ui/views/transpasse_view.py` |
| Registrar o módulo | `VIEWS` (barra lateral) e `MODULOS` (cartões da tela inicial) | `ui/main_app.py`, `ui/views/home_view.py` |
| Diálogo de arquivo / filtro `.xlsx` | `dialogos.escolher_arquivo` (o seletor já usa) / `dialogos.FILTRO_XLSX` | `docmanager/ui/dialogos.py` |
| Rodar em segundo plano com progresso e log | `RunBar(texto, tarefa, self.log)`; `run.set_progress(0..1)` | `components.py` |
| Perguntar e avisar de qualquer thread | `dialogos.perguntar`, `info`, `aviso`, `erro`, `tentar_de_novo` | `dialogos.py` |
| Tela de aceite (todas / nenhuma / caso a caso) | `decidir_sobrescricoes` + `DecisaoSobrescricao` (**generalizar os textos**, seção 10) | `ui/views/sobrescricao_dialog.py`, `services/sobrescricao.py` |
| Credenciais e `AconexConfig` | `aconex_backend.usuarios_disponiveis()` + `AconexConfig.para_usuario(nome)`. A regra "primeiro cadastrado" é a de `extracao_headless.py`. | `docmanager/aconex_backend.py` |
| Cadastro de credencial quando não há nenhuma | `credenciais_dialog.cadastrar(parent, nome=None)`, chamado pela `ponte.na_ui_e_esperar` | `ui/views/credenciais_dialog.py` |
| Sessão autenticada (proxy, PAC, Zscaler, SSL) | `aconex_backend._estabelecer_sessao(config, log_cb)` → `(session, token)` | `docmanager/aconex_backend.py` |
| Renovar token no 401 | `aconex_backend._get_token(session, config, log)` | idem |
| Retentativa | `ESPERAS_BACKOFF`, `TENTATIVAS_POR_PAGINA` e o laço de `workflows_backend._baixar_pagina_wf`. **Generalize** o laço num ajudante em `aconex_backend.py` (ex.: `_get_resiliente(session, config, url, headers, params, log_cb)`), faça os Workflows usarem-no (com `tests/test_fluxos.py` verde) e use-o no Field. **Não** mexa no `_baixar_pagina` do register. | `aconex_backend.py`, `workflows_backend.py` |
| Normalizar cabeçalho | `doclist_io._norm_cabecalho` → mova para `core/normalize.py` como `normalizar_cabecalho` e use nos dois lugares | `services/doclist_io.py`, `core/normalize.py` |
| Remover acentos | `core.normalize.remover_acentos` | `core/normalize.py` |
| Gravar com diagnóstico de arquivo preso | `gravacao.salvar_planilha` (**generalizar**, seção 9) | `services/gravacao.py` |
| Pasta de dados (backups, memória C10) | `credenciais.pasta_dados()` | `services/credenciais.py` |
| Rodar na thread da interface | `ponte.na_ui`, `ponte.na_ui_e_esperar` | `docmanager/ui/ponte.py` |
| Testes isolados da pasta do usuário | `tests/conftest.py` (`DOCMANAGER_DADOS_DIR`) | — |
| Testes de tela | fixtures `app` e `caixas` de `tests/test_ui_telas.py` | — |
| Sessão HTTP simulada | `_SessaoFake`, `_Resposta`, `_plugar` de `tests/test_aconex_checkpoint.py` | — |

**Dica de teste:** chame `ab._estabelecer_sessao` com `from . import aconex_backend as ab`. Assim o `_plugar` existente (que troca `docmanager.aconex_backend._estabelecer_sessao`) também vale para o Field.

---

## 12. Arquivos

| Arquivo | Novo/alterado | Responsabilidade |
|---|---|---|
| `docmanager/field_backend.py` | novo | Espelha `workflows_backend.py`: rotas da seção 5, pausa de 250 ms, retentativa (ajudante generalizado). `extrair_questoes(config, *, log_cb, progress_cb, com_comentarios) -> ExtracaoQuestoes(questoes, definicoes, tipos, comentarios_por_issue)`. Falha definitiva levanta exceção (tudo ou nada). Funções puras do Apêndice A. |
| `docmanager/services/xlsx_cirurgico.py` | novo | Infraestrutura genérica, reutilizável: ler o pacote (abas, tabelas, shared strings, estilos, linhas e células com `s`), localizar tabela por coluna, regras 8.2, editar `sheetData`/`dimension`/`ref`, acrescentar `<xf>`, regravar o zip copiando as partes intactas byte a byte. Sem regra de negócio de pendências. |
| `docmanager/services/pendencias_update.py` | novo | Regras D1–D6 e C7–C10 (8.3–8.4), validador (seção 13) e orquestração: `atualizar_pendencias(config, caminho, *, log_cb, progress_cb, retry_cb, decidir_cb) -> ResultadoPendencias(ok, mensagem, novas, atualizadas, preenchidas, apagadas, mantidas, cor_mudou, so_na_planilha, backup)`. |
| `docmanager/services/gravacao.py` | alterado | Seção 9. |
| `docmanager/ui/views/sobrescricao_dialog.py` | alterado | Textos parametrizáveis (seção 10). |
| `docmanager/aconex_backend.py`, `docmanager/workflows_backend.py` | alterados | Ajudante de GET com retentativa. |
| `docmanager/core/normalize.py`, `services/doclist_io.py` | alterados | `normalizar_cabecalho`. |
| `docmanager/ui/views/pendencias_view.py` | novo | Módulo "Pendências" (seção 10). |
| `docmanager/ui/main_app.py`, `docmanager/ui/views/home_view.py` | alterados | Registro do módulo (`VIEWS` e `MODULOS`). |
| `tests/…` | novos/alterados | Seção 13. |
| docs | alterados | Seção 14. |

---

## 13. Validador e testes (só dados sintéticos)

### Validador (roda no temporário; lista vazia = ok)

1. O zip abre (`testzip`) e tem **as mesmas entradas, na mesma ordem**.
2. Todas as entradas não alteradas são **byte a byte iguais** às originais. Só mudaram a aba da tabela, a tabela e, se for o caso, os estilos.
3. As partes alteradas são XML bem formado (`ET.fromstring`). A **declaração e a tag raiz** são textualmente iguais às originais (namespaces intactos).
4. Relendo a aba com o seu leitor:
   - cabeçalho e linhas acima de `d` iguais;
   - `Issue Number` de `d..L+k` = novas (decrescente) + existentes na ordem antiga;
   - **colunas manuais de toda pendência existente iguais às de antes (valor e `s`)**;
   - colunas do Aconex = planejado;
   - `s` só mudou onde o D5 mandou;
   - atributos de `<row>` iguais (fora `r` e o `s` do D5);
   - `ref` da tabela e do `autoFilter` = `…{L+k}`.
5. `openpyxl.load_workbook(tmp, read_only=True)` lê a aba.
6. `pandas.read_excel(tmp, sheet_name=aba, header=linha_cabecalho - 1, dtype=str, keep_default_na=False)` devolve `L - d + 1 + k` linhas.

### Fixture (em `tests/builders.py`)

Uma pasta montada com openpyxl que imita a estrutura da seção 3:

- aba `PENDÊNCIAS` com legenda na linha 2;
- Tabela `tbRegistros` em `A4:V{n}` com as 22 colunas;
- `Issue Number` numérico e decrescente;
- linhas normais (H cinza, I–L em tom claro) e destacadas (fill na linha toda);
- uma linha com fonte azul;
- coluna M oculta;
- painel congelado em C5;
- alturas personalizadas;
- uma segunda aba com um gráfico do openpyxl (para haver `xl/charts/…` que precisa sair intacto);
- depois de salvar, **injete no zip uma parte extra** (ex.: `customXml/item1.xml` + `Override` no `[Content_Types].xml`) só para provar que partes desconhecidas são copiadas byte a byte.

**Questões da API:** estrutura do Apêndice B, valores fictícios.

### Testes

**Mapeamento:**
- cada linha da seção 6;
- UTC→UTC−3 que muda o dia;
- `Due Date` sem conversão;
- `family_id` com `id` diferente;
- `Yes`/`No` → `Sim`/`Não`;
- status desconhecido.

**Comments:**
- um bloco;
- vários comentários;
- Everyone + organização (ordem e linha em branco);
- `content` com aspas e quebra de linha;
- 0h e 12h;
- sem comentários.

**Atualização:**
- novas no topo, decrescente, numeradas certo;
- existentes na mesma ordem, renumeradas;
- manuais intactas (valor e estilo);
- coluna manual com nome de campo de outro módulo não é tocada;
- troca, preenchimento, apagamento (aceito, recusado, caso a caso, janela fechada) e memória C10 (não pergunta de novo; pergunta se o valor mudou);
- data real igual não conta como mudança; data real que mudou vira serial;
- linha desalinhada corrigida;
- D5: nova destacada, existente que fecha perde a cor, existente que vira impeditiva ganha, fonte azul e negrito preservados, `<xf>` acrescentado quando não existe e reaproveitado quando existe, `count` atualizado, índices antigos intactos;
- sem linha destacada na planilha → não inventa cor;
- "só na planilha" intacta e no log;
- `k = 0`;
- nada mudou → não grava;
- texto com `&`, `<`, `>`, espaço no início, quebra de linha, `=` no início (continua texto) e caractere de controle;
- texto longo cortado;
- `dimension` e `ref` corretos;
- **partes intactas byte a byte** (gráfico e parte extra);
- **tag raiz e declarações de namespace inalteradas**;
- a coluna oculta continua oculta e o painel congelado igual (as partes da aba fora do `sheetData` não mudam).

**Recusas** (o arquivo fica byte a byte igual):
- cada item de 8.2 A–D;
- sem tabela;
- cabeçalho duplicado;
- `Issue Number` faltando.

**Field backend** (sessão simulada):
- paginação;
- deduplicação;
- 401;
- retentativa;
- falha definitiva levanta exceção;
- `supportPublicConversation=true`;
- sem coluna `Comments` → nenhuma chamada de conversas.

**Gravação:** seção 9.

**Telas:**
- o módulo "Pendências" está em `VIEWS` e abre nos dois temas (`test_todas_as_telas_abrem_nos_dois_temas` passa a cobri-lo);
- o cartão da tela inicial navega até ele;
- **escolher a planilha dispara a atualização** (serviço simulado chamado uma vez com o caminho); o botão roda de novo;
- sem planilha, só avisa;
- sem credencial cadastrada, abre o cadastro (simulado) e, se cancelar, não chama o serviço;
- com o serviço simulado, `decidir_cb` e `retry_cb` chegam aos diálogos certos e **nenhuma pergunta "Gravar?" aparece**;
- a tela de aceite com os textos padrão continua igual para Doc List e Mapa.

**Verificação final:** `pytest` e `ruff check .` verdes. O código roda com pandas 2.x e 3.x.

---

## 14. Documentação

- **ADR** `docs/adr/0002-…md`: "planilhas com gráficos e tabelas dinâmicas são atualizadas por escrita cirúrgica no XML". Inclua as opções consideradas (openpyxl com as perdas medidas na seção 4; automação do Excel via COM, descartada por exigir Excel instalado e não ter como testar no CI) e as consequências (as recusas da v1).
- **KB:** nova seção `§32 Pendências de comissionamento (Campo → Questões)`, no estilo da §24.12:
  - contrato da API e armadilhas: `/field-management`, `family_id`, `trading_name`, Sim/Não, fuso, `supportPublicConversation`, conversas vazias na listagem, `/count` diferente do documentado, campos customizados vindos dos tipos de questão;
  - as regras D1–D6 e C7–C11;
  - o modelo da planilha;
  - os pontos não verificados.
- **GLOSSARY.md:** seção "Pendências (Aconex Campo)" com:
  - **Questão**: o registro do módulo Campo; "Issue" na API e na exportação;
  - **Pendência de comissionamento**;
  - **Planilha de mapeamento de pendências**;
  - **Coluna do Aconex** e **Coluna manual**;
  - **Destaque de impeditiva**.
  Inclua os *Evite* de cada termo, no formato das entradas que já existem.
- **README.md:** em "Os módulos (como usar cada um)", um item novo para o módulo **Pendências**: escolher a planilha já atualiza; precisa do usuário do Aconex cadastrado.
- **CHANGELOG.md:** bloco novo no topo, no formato `## X.Y.Z - AAAA-MM-DD`. Sugira `3.8.0` e a data do PR e avise que versão e data são sugestão. Escreva para quem usa o app. Mencione que **Doc List e Mapa passam a guardar cópia de segurança** antes de salvar.

---

## 15. Tarefas, em ordem (uma por arquivo em `.scratch/pendencias-comissionamento/issues/`)

1. `01-substituicao-segura`: seção 9 e testes. Revise sozinha.
2. `02-normalizar-cabecalho-compartilhado`.
3. `03-get-resiliente-e-field-backend` (com sessão simulada).
4. `04-mapeamento-questao-e-comments` (Apêndice A + testes).
5. `05-xlsx-cirurgico` (leitura, recusas 8.2, escrita 8.5, cópia byte a byte, testes de integridade).
6. `06-atualizar-pendencias` (8.3, 8.4, validador e testes).
7. `07-modulo-pendencias`: módulo novo (`pendencias_view.py`, `VIEWS`, `MODULOS`) e tela de aceite generalizada.
8. `08-documentacao`: ADR 0002, KB §32, GLOSSARY, README, CHANGELOG.

Faça commits pequenos por tarefa. Ao terminar cada uma, mude o `Status:` dela para `done`.

---

## 16. Critérios de aceite

1. Na fixture com 128 pendências e a API simulada com 147:
   - 19 novas no topo, em ordem decrescente;
   - as que cumprem a regra entram destacadas;
   - uma existente que fechou perde a cor (fonte azul preservada);
   - os apagamentos passam pela tela e a decisão é respeitada;
   - colunas manuais intactas;
   - `ref` da tabela estendida;
   - **todas as outras partes byte a byte iguais**.
2. Em todo cenário de recusa ou erro (API, validação, assinatura, backup, arquivo preso sem resolver), o arquivo fica **byte a byte igual** e não sobra `~$docmanager-*`.
3. Sucesso deixa um backup e o log diz onde.
4. Doc List e Mapa continuam como antes, agora com a substituição segura. A suíte inteira fica verde.
5. **Teste do usuário (deixe o roteiro no PR):** o usuário abre o módulo **Pendências**, escolhe uma **cópia** da planilha real (a atualização começa sozinha) e depois abre a cópia no Excel de mesa. Deve conferir:
   - **nenhuma mensagem de reparo**;
   - tabelas dinâmicas e gráficos atualizados ao abrir;
   - coluna M oculta e painel congelado como antes;
   - 147 linhas, com 132 a 150 no topo;
   - 5 novas destacadas;
   - a pendência que fechou sem cor;
   - a tela listou 6 apagamentos.

---

## 17. Não verificado (defensivo + log)

- Rótulo do status `ReadyToInspect`.
- Comments: ordem entre blocos de duas organizações e se o título usa `trading_name` ou `name`.
- Formato de `Listed In` com várias listas, de `Source`, e dos campos `user` e `multi_select`.
- Pré-visualização do Box ou Excel Online: podem mostrar as tabelas dinâmicas desatualizadas até alguém abrir no Excel de mesa (o `refreshOnLoad` age ao abrir).

---

## Apêndice A: código de referência validado

Validado: 4.263/4.263 células e Comments 35/35. Adapte ao estilo do repositório, sem mudar as regras.

```python
from datetime import datetime, timedelta, timezone

FUSO_LOCAL = timezone(timedelta(hours=-3))   # Brasil/Paraguai, sem horário de verão
STATUS_ROTULO = {"Open": "Open", "InDispute": "In dispute", "ReadyToInspect": "Ready to inspect",
                 "WorkDone": "Work Done", "Closed": "Closed"}   # 'Ready to inspect': não verificado
BOOLEANO_ROTULO = {"Yes": "Sim", "No": "Não"}
PARTICIPANTE_PUBLICO = "-1"   # "Everyone"
_DIAS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MESES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _instante(iso) -> datetime:
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))


def _data(iso, *, converter_fuso: bool = True) -> str:
    """'2026-10-30T13:05:00.000Z' → '2026-10-30', no fuso local (como a exportação)."""
    if not iso:
        return ""
    try:
        dt = _instante(iso)
    except ValueError:
        return str(iso)
    if dt.tzinfo is not None and converter_fuso:
        dt = dt.astimezone(FUSO_LOCAL)
    return dt.date().isoformat()


def _pessoa(u) -> str:
    u = u or {}
    return " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x).strip()


def _organizacao(u) -> str:
    """Nome fantasia ('CMI'), não a razão social - é o que a exportação mostra."""
    org = (u or {}).get("organization") or {}
    return org.get("trading_name") or org.get("name") or ""


def _caminho_area(area) -> str:
    area = area or {}
    nomes = [x.get("name", "") for x in area.get("path") or []]
    if not nomes or nomes[-1] != area.get("name"):
        nomes.append(area.get("name", ""))
    return " > ".join(n for n in nomes if n)


def _origem(src) -> str:   # formato NÃO verificado (issue_source nulo em todas as questões reais)
    if not src:
        return ""
    return " ".join(str(x) for x in (src.get("record_type"), src.get("number"), src.get("title")) if x)


def definicoes_por_chave(definicoes: list[dict]) -> dict[str, dict]:
    """family_id PRIMEIRO: o id muda a cada versão da definição do campo."""
    mapa: dict[str, dict] = {}
    for d in definicoes:
        for chave in (d.get("family_id"), d.get("id")):
            if chave:
                mapa.setdefault(str(chave), d)
    return mapa


def valores_da_questao(q: dict, defs: dict[str, dict], comentarios: str | None = None) -> dict[str, str]:
    """Título da coluna da exportação → texto, para uma questão."""
    md = q.get("meta_data") or {}
    v = {
        "Issue Number": q.get("issue_number") or "",
        "Issue Type": (q.get("issue_type") or {}).get("name") or "",
        "Area": _caminho_area(q.get("area")),
        "Location Detail": q.get("location_detail") or "",
        "Issue Description": q.get("description") or "",
        "Captured On": _data(md.get("created_at")),
        "Captured by": _pessoa(md.get("created_by")),
        "Status": STATUS_ROTULO.get(q.get("status"), q.get("status") or ""),
        "Due Date": _data(q.get("due_date"), converter_fuso=False),   # prazo é dia, não instante
        "Assigned On": _data(q.get("assigned_at")),
        "Assigned to": _organizacao(q.get("assigned_to")),
        "Assigned By": _organizacao(q.get("assigned_by")),
        "Closed On": _data(q.get("closed_at")),
        "Closed By User": _pessoa(q.get("closed_by")),
        "Closed By Organization": _organizacao(q.get("closed_by")),
        "Pinned To DocNumber": "",
        "Doc Title": "",
        "Source": _origem(q.get("issue_source")),
        "Listed In": "; ".join(x.get("title", "") for x in q.get("issue_listings") or []),
    }
    for cf in q.get("custom_fields") or []:
        d = defs.get(str(cf.get("family_id"))) or defs.get(str(cf.get("id")))
        if not d or not d.get("label"):
            continue
        valor = cf.get("value") or ""
        tipo = str((d.get("type") or {}).get("name") or "").lower()
        if tipo == "date":
            valor = _data(valor, converter_fuso=False)
        elif tipo == "boolean":
            valor = BOOLEANO_ROTULO.get(valor, valor)
        v[d["label"]] = valor
    if comentarios is not None:
        v["Comments"] = comentarios
    return v


def _quando(iso) -> str:
    """'2026-09-30T11:23:10.953Z' → 'Wed, Sep 30, 2026, 8:23:10 am' (UTC−3, inglês, 12 h)."""
    dt = _instante(iso).astimezone(FUSO_LOCAL)
    return (f"{_DIAS[dt.weekday()]}, {_MESES[dt.month - 1]} {dt.day}, {dt.year}, "
            f"{dt.hour % 12 or 12}:{dt:%M:%S} {'am' if dt.hour < 12 else 'pm'}")


def formatar_comentarios(conversas: list[dict]) -> str:
    """Texto da coluna Comments: 'Everyone' primeiro, blocos separados por linha em branco."""
    blocos = []
    publico_primeiro = sorted(conversas, key=lambda c: str((c.get("participant") or {}).get("id")) != PARTICIPANTE_PUBLICO)
    for conv in publico_primeiro:
        coms = sorted(conv.get("comments") or [], key=lambda c: _instante(c["client_captured_at"]))
        if not coms:
            continue
        part = conv.get("participant") or {}
        linhas = [f"With {part.get('trading_name') or part.get('name')}:"]
        for c in coms:
            a = c.get("author") or {}
            org = a.get("organization") or {}
            linhas.append(f'"{c.get("content")}" submitted by {a.get("first_name")} {a.get("last_name")} '
                          f'({org.get("trading_name") or org.get("name")}) on {_quando(c["client_captured_at"])}')
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)
```

Nesta planilha, `valores_da_questao` devolve mais colunas do que a tabela tem. Use só as que existem nela (seção 7). `Issue Number` vai como número.

---

## Apêndice B: questão sintética (estrutura real, valores fictícios)

```json
{
  "issue_id": "00000000-0000-4000-8000-000000000150",
  "issue_number": "150",
  "description": "Durante o comissionamento do painel X constatou-se cabo solto.",
  "status": "Open",
  "location_detail": "PAINEL-A",
  "issue_type": {"id": "9001", "name": "05. Pendencia de Comisionamiento", "custom_fields": []},
  "area": {"id": "3", "name": "GEQ-001-008: GRUPO EXEMPLO",
           "path": [{"id": "1", "name": "PROJETO EXEMPLO"}, {"id": "2", "name": "GRUPO DE EQUIPAMENTOS"},
                    {"id": "4", "name": "PE001: PLANO EXEMPLO"}]},
  "meta_data": {"created_at": "2026-10-31T01:30:00.000Z", "updated_at": "2026-10-31T01:30:00.000Z",
                "created_by": {"id": "7", "first_name": "FULANO", "last_name": "DE TAL",
                               "organization": {"id": "20", "name": "ITAIPU BINACIONAL", "trading_name": "ITAIPU BINACIONAL"}}},
  "assigned_at": "2026-10-31T01:30:00.000Z",
  "assigned_to": {"organization": {"id": "10", "name": "CONSÓRCIO EXEMPLO", "trading_name": "CMI"}},
  "assigned_by": {"organization": {"id": "20", "name": "ITAIPU BINACIONAL", "trading_name": "ITAIPU BINACIONAL"}},
  "due_date": "2026-11-05T12:00:00.000Z",
  "closed_by": null,
  "closed_at": null,
  "issue_listings": [],
  "issue_source": null,
  "pin_status": false,
  "custom_fields": [
    {"id": "111", "family_id": "F-TAG", "value": "#XX00=Z99ABC10: EQUIPAMENTO EXEMPLO"},
    {"id": "222", "family_id": "F-CLASSIF", "value": "Impeditiva"},
    {"id": "333", "family_id": "F-PASSOU", "value": "Yes"},
    {"id": "444", "family_id": "F-CIERRE", "value": null}
  ]
}
```

Pontos a reproduzir nos testes:

- `created_at` `2026-10-31T01:30Z` vira **`2026-10-30`** (mudou o dia no fuso local);
- `Area` = `PROJETO EXEMPLO > GRUPO DE EQUIPAMENTOS > PE001: PLANO EXEMPLO > GEQ-001-008: GRUPO EXEMPLO`;
- esta questão é **Impeditiva e Open**, então entra destacada.

Definição em `/customfields`. Os `id`s diferentes de propósito exercitam o casamento por `family_id`:

```json
{"custom_fields": [
  {"id": "999", "family_id": "F-TAG", "label": "TAG RDS-PP", "type": {"name": "single_select"}},
  {"id": "998", "family_id": "F-CLASSIF", "label": "Clasificación de pendencia", "type": {"name": "single_select"}},
  {"id": "997", "family_id": "F-PASSOU", "label": "¿Pasó a comisionamiento?", "type": {"name": "boolean"}},
  {"id": "996", "family_id": "F-CIERRE", "label": "Cierre", "type": {"name": "single_select"}}
]}
```

---

## Apêndice C: XML real (sem valores) para orientar o parser

Atributos da linha, de uma célula numérica, de uma célula de texto compartilhado e de uma célula vazia com estilo:

```xml
<row r="5" spans="1:22" s="19" customFormat="1" ht="25.5" customHeight="1" x14ac:dyDescent="0.35">
  <c r="A5" s="26"><v>131</v></c><c r="B5" s="2" t="s"><v>19</v></c> … <c r="I5" s="17"/> …
</row>
```

Linha destacada: `<row r="7" spans="1:22" s="22" customFormat="1" ht="25.5" customHeight="1" x14ac:dyDescent="0.35">`.

Célula nova de texto:

```xml
<c r="B5" s="2" t="inlineStr"><is><t xml:space="preserve">texto</t></is></c>
```

Raiz da aba (manter textualmente):

```xml
<worksheet xmlns="…/spreadsheetml/2006/main" xmlns:r="…" xmlns:mc="…" mc:Ignorable="x14ac xr xr2 xr3" xmlns:x14ac="…" …>
```

Tabela:

```xml
<table … name="tbRegistros" displayName="tbRegistros" ref="A4:V132" totalsRowShown="0" headerRowDxfId="25" dataDxfId="0" …>
  <autoFilter ref="A4:V132" …/>
```

---

## Apêndice D: prova de conceito da escrita cirúrgica (medida em 02/11/2026)

Feita numa **cópia** da planilha real, com um script descartável que segue as seções 8.5 e 9:

- 2 linhas inseridas no topo da tabela:
  - `999`, destacada, com o modelo de linha e de células das destacadas;
  - `998`, normal;
- uma célula existente trocada de texto compartilhado para `inlineStr` (Status `Open` → `Closed`);
- um texto novo com espaço no início e no fim, quebra de linha, acentos, `&` e `<`;
- renumeração das linhas;
- `dimension` e `ref` da tabela e do autoFilter estendidos;
- demais partes copiadas byte a byte.

**Resultado no Python:**
- 37 de 37 partes intactas byte a byte;
- tag raiz da aba idêntica;
- XML bem formado;
- openpyxl e pandas leram as linhas novas e a célula trocada.

**Resultado no Microsoft Excel 16** (aberto por automação, só leitura):

| Verificação | Original | Com escrita cirúrgica |
|---|---|---|
| Título da janela | sem "[Reparado]" | **sem "[Reparado]"** |
| Log de reparo (`%TEMP%\error*.xml`) | nenhum | **nenhum** |
| Tabela | `A4:V132`, 128 linhas | **`A4:V134`, 130 linhas** |
| A5 / A6 / A7 | 131 / 130 / 129 | **999 (cor de destaque) / 998 (sem cor) / 131** |
| H9 (célula trocada) | Open | **Closed** |
| Texto novo | — | **espaços, quebra de linha e acentos preservados** |
| Coluna M | oculta | **oculta** |
| Total das tabelas dinâmicas após atualizar | 128 / 117 | **130 / 118** (bate: +2 novas, −1 que fechou) |
| Gráficos | 2 | **2** |

A automação do Excel serviu só para esta verificação. O produto **não** depende de Excel instalado.
