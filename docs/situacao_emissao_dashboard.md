# Situação de Emissão — do Doc List Mapping ao dashboard Power BI

> **Status: lado Python IMPLEMENTADO em 2026-09-16.** As três colunas são
> calculadas e gravadas pelo app, e já existem na planilha real. **Falta só o
> roteiro do Power BI** — §10, com um .pbix pré-editado de atalho. Levantamento e implementação feitos sobre
> `Doc List Mapping.xlsx` e `Dashboard - Doc List Mapping.pbix`.
>
> As três decisões que estavam pendentes foram respondidas pelo usuário e estão
> registradas em [§11](#11-decisões-do-usuário-respondidas).

## Índice

1. [Arquivos que NÃO entram no Git](#1-arquivos-que-não-entram-no-git)
2. [Mapa do módulo Doc List Mapping](#2-mapa-do-módulo-doc-list-mapping)
3. [Pipeline de atualização, passo a passo](#3-pipeline-de-atualização-passo-a-passo)
4. [Anatomia do dashboard (PBIX)](#4-anatomia-do-dashboard-pbix)
5. [O gap: o gráfico não sabe o que foi executado](#5-o-gap-o-gráfico-não-sabe-o-que-foi-executado)
6. [Por que as colunas existentes não resolvem](#6-por-que-as-colunas-existentes-não-resolvem)
7. [A régua: a informação já existia no histórico](#7-a-régua-a-informação-já-existia-no-histórico)
8. [As três colunas novas](#8-as-três-colunas-novas)
9. [O que foi implementado, arquivo a arquivo](#9-o-que-foi-implementado-arquivo-a-arquivo)
10. [O que fazer no Power BI](#10-o-que-fazer-no-power-bi)
11. [Decisões do usuário (respondidas)](#11-decisões-do-usuário-respondidas)

---

## 1. Arquivos que NÃO entram no Git

`Doc List Mapping.xlsx` e `Dashboard - Doc List Mapping.pbix` contêm dados reais
do cliente. **Nunca versionar.** Já estão bloqueados no `.gitignore`:

```
Doc List Mapping*.xlsx
*.pbix
```

O glob cobre também os **backups** (`Doc List Mapping.backup-AAAAMMDD-HHMMSS.xlsx`)
que `tools/criar_colunas_situacao_emissao.py` grava ao lado do original.

Verificado em 2026-09-16: nenhum dos dois jamais entrou no histórico
(`git log --all` sobre eles retorna vazio). Este documento descreve
**estrutura**, nunca conteúdo — não colar códigos de documento reais aqui.

### Como reinspecionar os arquivos numa próxima sessão

O `.pbix` está no formato **PBIR** (JSON por visual), não no binário antigo.
Basta abrir como ZIP:

```python
import zipfile
z = zipfile.ZipFile('Dashboard - Doc List Mapping.pbix')
z.extractall('/tmp/pbix')
# Report/definition/pages/<pageId>/visuals/<visualId>/visual.json
```

O `DataModel` continua opaco (SSAS comprimido), mas **não é necessário**: os
nomes de tabela e coluna aparecem nos `visual.json`.

---

## 2. Mapa do módulo Doc List Mapping

Regras de domínio: KB §27. Guia prático da planilha e da tela:
[`docs/doc_list_mapping.md`](doc_list_mapping.md). Este arquivo cobre só o que
interessa à Situação de Emissão.

| Camada | Arquivo | Papel |
|---|---|---|
| Fachada | `docmanager/doclist_backend.py` | porta única do módulo |
| Núcleo puro | `docmanager/core/doclist.py` | `COLUNAS_DOCLIST`, `LinhaDocList`, `COLUNAS_CALCULADAS` |
| Núcleo puro | `docmanager/core/mapping.py` | `processar_documento` — calcula tudo de um documento |
| Núcleo puro | `docmanager/core/truth_line.py` | linha da verdade (qual revisão vale hoje) |
| Núcleo puro | `docmanager/core/kpis.py` | KPIs e atrasos acumulados — **é aqui que mora o nascedouro** |
| Núcleo puro | `docmanager/core/normalize.py` | `normalizar_revisao`, `REV_LIMITE_0A`, `celula_para_date` |
| Núcleo puro | `docmanager/core/planejamento.py` | reconciliação PREVISTA / REPROGRAMADA / ALVO |
| Núcleo puro | `docmanager/core/doclist_periodo.py` | análise "previstos para emitir" |
| I/O | `docmanager/services/doclist_io.py` | `DocListSheet` — leitura/escrita de células |
| Orquestração | `docmanager/services/doclist_update.py` | `atualizar_doclist` |
| UI | `docmanager/ui/views/doclist_view.py` | tela |
| Testes | `tests/test_doclist.py`, `tests/test_mapping.py` | |

### Cabeçalho da planilha (24 colunas)

```
GRUPO · SISTEMA · FASE DE PROJETO · Nº CMI · N° ITAIPU ·
DESCRIÇÃO DO DOCUMENTO · DATA PREVISTA EMISSÃO · DATA REPROGRAMADA ·
DATA-ALVO EMISSÃO · EMITIDO / NÃO EMITIDO · DATA ÚLTIMA EMISSÃO ·
ÚLTIMA REV. EMITIDA · DATA 1ª EMISSÃO · SITUAÇÃO EMISSÃO ·
DIAS DESVIO EMISSÃO · STATUS REAL · STATUS · RESPONSIBLE (COE/VENDOR) ·
NÍVEL · STATUS CONSOLIDADO · COM ITAIPU · PREDECESSOR · OBSERVAÇÕES ·
RESUMO QUANTIDADES
```

Na planilha real as três novas foram **anexadas no fim** (colunas X, Y, Z), não
inseridas no meio — ver §9.8. A posição é irrelevante para o código.

⚠️ **Codepoints**: `N° ITAIPU` usa **U+00B0** (grau), `Nº CMI` usa **U+00BA**
(ordinal). Trocar um pelo outro quebra a localização do cabeçalho — `N° ITAIPU`
é a âncora.

O cabeçalho é localizado dinamicamente nas 10 primeiras linhas; na planilha real
ele está na **linha 2** (linha 1 vazia, linha 3 vazia, dados a partir da 4).

### Chaves lógicas → cabeçalho

`COLUNAS_DOCLIST` em [`core/doclist.py:45`](../docmanager/core/doclist.py#L45)
mapeia `chave_logica -> "TEXTO DO CABEÇALHO"`. Todo acesso a célula usa a chave
lógica, nunca o texto.

`COLUNAS_CALCULADAS` em [`core/doclist.py:85`](../docmanager/core/doclist.py#L85)
lista o que é sobrescrito a cada atualização. O resto é input manual e nunca é
tocado.

---

## 3. Pipeline de atualização, passo a passo

`atualizar_doclist` em
[`services/doclist_update.py:137`](../docmanager/services/doclist_update.py#L137):

1. Abre a planilha, renomeia cabeçalhos legados, avisa sobre colunas ausentes.
2. Para cada linha:
   - **Nível 1** (agrupamento) → `_escrever_grupo`, não busca no Aconex.
   - **Nível 2** (documento) → resolve identidade (códigos históricos), monta o
     `df_tracking` (histórico completo daquele documento no Aconex) e chama
     `processar_documento`.
3. `processar_documento`
   ([`core/mapping.py:154`](../docmanager/core/mapping.py#L154)) devolve um
   `ResultadoDocumento`.
4. `_escrever_documento`
   ([`services/doclist_update.py:119`](../docmanager/services/doclist_update.py#L119))
   grava o resultado nas células.
5. Calcula predecessores e `RESUMO QUANTIDADES` dos grupos.

### `ResultadoDocumento` ([`core/mapping.py:29`](../docmanager/core/mapping.py#L29))

```python
revisao, data_ultimo_status, status_emissao,
cod_itaipu_atual, cod_cmi_atual, descricao_atual,
status_real, emitido_nao_emitido, status_consolidado, com_itaipu,
kpis: dict,      # calculado; o Doc List não usa
atrasos: dict,   # calculado; o Doc List não usa
data_primeira_emissao: date | None,   # <-- a régua de aderência (§7)
```

### `DocListSheet` ([`services/doclist_io.py:43`](../docmanager/services/doclist_io.py#L43))

| Método | Uso |
|---|---|
| `get_val(chave, row)` / `set_val(chave, row, valor)` | texto |
| `get_data(chave, row)` / `set_data(chave, row, date)` | **data nativa** com `number_format` |
| `colunas_ausentes` | colunas de `COLUNAS_DOCLIST` que não existem na planilha |
| `matar_zumbi(chave, row)` | limpa célula |

> 🔑 **Retrocompatibilidade de graça**: `set_val`/`set_data` retornam `False`
> quando a coluna não existe na planilha, e `atualizar_doclist` apenas **loga um
> aviso** para `colunas_ausentes` — não aborta. Ou seja: adicionar chaves novas
> em `COLUNAS_DOCLIST` **não quebra planilhas antigas**. Quem ainda não criou as
> colunas continua rodando; quem criou passa a receber os valores.

> 🔑 **Data nativa é obrigatório**: `set_data` grava `datetime.date` com formato
> `dd/mm/aaaa`. Se gravar texto, o Power BI não consegue agrupar por período —
> era exatamente para isso que `DATA-ALVO EMISSÃO` foi feita assim.

---

## 4. Anatomia do dashboard (PBIX)

**Formato:** PBIR. **Páginas:** 2, 1280×720 — `Capa do Projeto` (só imagem) e
`Unidade Geradora` (ativa, todo o conteúdo).

**Modelo de dados:** uma única tabela, `Unidade Geradora`, importada direto da
aba homônima do XLSX. **Não existe tabela-calendário**; o Power BI criou uma
*auto date hierarchy* (`LocalDateTable_41b52f7d-…`, hierarquia `Hierarquia de
datas`, níveis Ano/Trimestre/Mês/Dia) sobre `DATA-ALVO EMISSÃO`.

### Visuais da página `Unidade Geradora`

| ID | Tipo | Título | Campos |
|---|---|---|---|
| `282d005d197512984b3b` | columnChart | DOCUMENTAÇÃO GERAL | eixo `STATUS REAL` × `CountNonNull(N° ITAIPU)` |
| `2a49c2d097105b6867a6` | pieChart | DOCUMENTOS DE FABRICAÇÃO | `STATUS CONSOLIDADO` |
| `208e041094681e7d6c41` | pieChart | DOCUMENTOS DE EXECUÇÃO | `STATUS CONSOLIDADO` |
| `880cc8c9962e6407aa45` | pieChart | DOCUMENTOS POR ESCOPO | `GRUPO` |
| **`619e9572eb5195c710bb`** | **columnChart** | **DOCUMENTOS PARA EMISSÃO** | **eixo `DATA-ALVO EMISSÃO` → Dia × `CountNonNull(N° ITAIPU)`** |
| `c147dd9d9850297bc803` | card | PLANOS DE EXECUÇÃO (NÍVEL 1) | contagem `N° ITAIPU` |
| `f480a860cc86e0ec0e04` | card | PLANOS SUPORTES (NÍVEL 2) | contagem `N° ITAIPU` |
| `952a3509e91a08d4309e` | card | PLANILHAS E PROTOCOLOS (NÍVEL 3) | contagem `N° ITAIPU` |
| `6733e636581ec2db8646` | card | PLANILHAS E PROTOCOLOS (NÍVEL 3) | contagem `N° ITAIPU` |
| `214fad07c5a3d211ae75` | card | — | contagem `N° ITAIPU` |
| `bf6d8724a860d75c394d` | slicer | — | `SISTEMA` |
| `87086793be1508563786` | slicer | — | `FASE DE PROJETO` |
| `5ede2a42f235ebcc48ab` | slicer | — | `RESPONSIBLE (COE/VENDOR)` |
| `3f5ff3ee9ba109831c14` | slicer | — | `DATA-ALVO EMISSÃO` → Ano + Mês, modo Dropdown |

### O gráfico em questão — `619e9572eb5195c710bb`

Caminho:
`Report/definition/pages/8808fe0e6aa92aa8babb/visuals/619e9572eb5195c710bb/visual.json`

- Posição: `x=639, y=482, w=641, h=237`, `z=14000`
- **Category (eixo X)**: `HierarchyLevel` sobre a *PropertyVariationSource* de
  `Unidade Geradora[DATA-ALVO EMISSÃO]`, hierarquia `Hierarquia de datas`,
  **`Level: "Dia"`**
- **Y**: `Aggregation(Function: 2)` sobre `Unidade Geradora[N° ITAIPU]` =
  `CountNonNull`
- `sortDefinition`: pelo mesmo nível Dia, ascendente
- `filterConfig: null` — **sem filtro próprio**
- `legend.show = false` — **sem legenda**
- Interação: o slicer de data `3f5ff3ee…` filtra este visual (`DataFilter` no
  `page.json`); quase todos os outros visuais estão em `NoFilter` com ele

### Dois achados colaterais (dívida a limpar)

1. **Seletores órfãos no `dataPoint`** do gráfico `619e9572…`: há regras de cor
   apontando para `Riscos (Riscos gerenciais e externos)[Severidade]` e
   `Planilha riscos[Sistema]` — tabelas que **não existem neste modelo**. É lixo
   de um visual copiado de outro relatório. Nenhuma regra tem efeito hoje; a
   barra sai na cor única do tema. Ao mexer nas cores, limpar isso.
2. **Títulos "NÍVEL 1/2/3" são decorativos**: os quatro cards não têm
   `filterConfig` nenhum — contam `N° ITAIPU` sob o contexto cruzado da página.
   "NÍVEL 3" nem existe no Doc List Mapping (o módulo tem 2 níveis: 1 =
   agrupamento, 2 = documento). São rótulos herdados do Mapa dos Planos.

---

## 5. O gap: o gráfico não sabe o que foi executado

O visual DOCUMENTOS PARA EMISSÃO responde exatamente uma pergunta:

> "Quantos documentos têm **data-alvo** no dia X?"

Ele é **carga prevista**, não aderência. Não há nenhuma informação sobre se o
documento previsto para aquele dia saiu, e se saiu, se saiu no prazo.

**O que se quer:** manter a barra no dia previsto (ex.: dia 3), mas reparti-la
por cor entre *emitido no prazo*, *emitido com atraso*, *ainda pendente*.

---

## 6. Por que as colunas existentes não resolvem

A planilha já tem `DATA ÚLTIMA EMISSÃO` e `ÚLTIMA REV. EMITIDA`. **São a última
revisão, não a primeira.** Padrão típico encontrado nos dados reais:

```
DATA-ALVO EMISSÃO ..... out/2025
DATA ÚLTIMA EMISSÃO ... jul/2026     ÚLTIMA REV. EMITIDA: 0F
```

Comparar essas duas acusaria ~9 meses de atraso, quando o documento **nasceu no
prazo** e apenas evoluiu revisões depois (0A → … → 0F é ciclo normal de
aprovação). Usar `DATA ÚLTIMA EMISSÃO` como régua produz um mar de falsos
atrasos.

**A régua correta é a data de emissão da revisão nascedoura (0A).** É o momento
em que a CMI entregou o documento pela primeira vez — é isso que se compara com
`DATA-ALVO EMISSÃO`.

---

## 7. A régua: a informação já existia no histórico

Em [`core/kpis.py:130`](../docmanager/core/kpis.py#L130), dentro de
`calcular_atrasos_acumulados`, existe o bloco **"Momento A: nascedouro"**:

```python
revisoes = df[COL_REVISAO].dropna().unique()   # df já ordenado por data
...
df_nasc = df[(df[COL_REVISAO] == revisoes[0]) & (df["Status_Upper"] == "EM PROCESSO")]
if not df_nasc.empty:
    res["atraso_acumulado_cmi"] += max(0, (df_nasc["Data_Obj"].max() - dt_prev).days)
```

`revisoes[0]` é a **primeira revisão em ordem cronológica**, porque
`_preparar_historico` ([`core/kpis.py:34`](../docmanager/core/kpis.py#L34)) já
fez toda a higiene necessária:

- normaliza a revisão (upper, remove `R`, strip);
- **extermina ciclos internos** (revisões com mais de 2 caracteres, ex.: `0AA`);
- aplica o **limiar de Terminated** de
  [`core/truth_line.py`](../docmanager/core/truth_line.py)
  (`limpar_terminated_por_limiar`);
- ordena por `Data_Obj`.

E o evento que marca a emissão é a linha com `Status == "Em Processo"` daquela
revisão — a submissão para a Itaipu.

**Era só expor.** O histórico já chegava limpo ao ponto de cálculo; o Doc List
simplesmente não gravava nada disso. `core/kpis.data_primeira_emissao` formaliza
a conta numa função pura e reutilizável, e o Doc List passou a gravá-la — ver
§9.1 para por que o "Momento A" ficou como estava.

> ⚠️ Nota sobre DAX: **não dá para calcular isso no Power BI.** A regra de
> nascedouro depende do histórico do Aconex (limiar de Terminated, extermínio de
> ciclos internos), e esse histórico **não está no modelo** — só a planilha chega
> lá. O Python precisa resolver e entregar mastigado.

---

## 8. As três colunas novas

Implementadas. Todas em `COLUNAS_CALCULADAS`: são reescritas a cada atualização.

| Coluna | Tipo | Conteúdo |
|---|---|---|
| `DATA 1ª EMISSÃO` | data **nativa** (`dd/mm/aaaa`) | quando a CMI entregou o documento pela primeira vez; vazia se nunca emitido |
| `SITUAÇÃO EMISSÃO` | texto, categoria única | o balde — é a Legenda do gráfico |
| `DIAS DESVIO EMISSÃO` | **número** inteiro | `1ª emissão − data-alvo`; negativo = adiantado |

`DIAS DESVIO` vai como número e não como texto de propósito: assim o Power BI
consegue somar e tirar média (desvio médio por escopo, por fase, por responsável).

### Os baldes

| Balde | Regra |
|---|---|
| `EMITIDO NO PRAZO` | `DATA 1ª EMISSÃO` ≤ `DATA-ALVO EMISSÃO` |
| `EMITIDO COM ATRASO` | `DATA 1ª EMISSÃO` > `DATA-ALVO EMISSÃO` |
| `PENDENTE NO PRAZO` | sem 1ª emissão **e** `hoje` ≤ `DATA-ALVO EMISSÃO` |
| `PENDENTE VENCIDO` | sem 1ª emissão **e** `hoje` > `DATA-ALVO EMISSÃO` |
| `SEM PLANEJAMENTO` | sem `DATA-ALVO EMISSÃO` |
| `CANCELADO` | `STATUS CONSOLIDADO == CANCELADO` — **precede tudo**; sai do gráfico por filtro do visual |

`SEM PLANEJAMENTO` é o mesmo furo que a aba "Sem Planejamento" da Análise de
Período já denuncia — trazê-lo para o dashboard dá visibilidade ao que hoje só
aparece no Excel exportado.

Linhas de **nível 1** (agrupamento) ficam com as três células **vazias**: não são
documento e não devem poluir a legenda.

---

## 9. O que foi implementado, arquivo a arquivo

### 9.1 `core/kpis.py` — a régua

`data_primeira_emissao(df_tracking) -> date | None`, mais o helper
`_rev_nascedoura`. Reaproveita `_preparar_historico` (ciclos internos
exterminados, limiar de *Terminated* aplicado, ordenação por data) e filtra os
eventos `Em Processo`.

> **O "Momento A" de `calcular_atrasos_acumulados` foi deixado INTACTO.** Ele
> responde uma pergunta parecida, mas a revisão nascedoura lá é sempre a primeira
> cronológica — nunca prefere `0A`. Mexer nele mudaria o `atraso_acumulado_cmi`,
> que já está validado em dados reais, sem ninguém ter pedido. A divergência é
> deliberada e está anotada na docstring.

### 9.2 `core/doclist.py` — as colunas e o balde

- 3 chaves novas em `COLUNAS_DOCLIST` e em `COLUNAS_CALCULADAS`;
- constantes `SIT_*` e a tupla `SITUACOES_EMISSAO`;
- `classificar_situacao_emissao(...)` e `calcular_dias_desvio_emissao(...)`, puras.

### 9.3 `core/mapping.py` — só transporta

`ResultadoDocumento` ganhou **apenas** `data_primeira_emissao`, preenchido em
`processar_documento`.

> **Por que o balde não é calculado aqui**: `mapping.py` é o pipeline genérico do
> Mapa dos Planos. A regra dos baldes é do Doc List, então ela mora em
> `core/doclist.py` e é aplicada pelo serviço do Doc List. O genérico não pode
> depender do específico.

### 9.4 `services/doclist_update.py` — grava

`_escrever_situacao_emissao(ds, row, r, data_alvo, hoje)`, chamada logo após
`_escrever_documento`. É o serviço que tem `data_alvo` e `hoje` em mãos.
`_escrever_grupo` limpa as três células no nível 1.

### 9.5 Retrocompatibilidade

Nada a fazer: `set_val`/`set_data` devolvem `False` para coluna inexistente e
`atualizar_doclist` só loga o aviso (§3). Coberto por teste.

### 9.6 `tests/test_doclist.py`

14 testes novos (50 no arquivo, **697 na suíte, todos verdes**). Os que importam:

- `test_regua_e_a_primeira_emissao_nao_a_ultima` — 0A no prazo, 0F meses depois:
  **é o teste que justifica a coluna existir**;
- `test_reenvio_da_mesma_revisao_manda_a_data_mais_recente` — a decisão §11.1;
- `test_sem_0a_vale_a_emissao_mais_antiga_documento_sat` — a decisão §11.2;
- `test_0a_vence_mesmo_fora_de_ordem_cronologica`;
- `test_ciclo_interno_0aa_nao_conta_como_emissao`;
- `test_0a_terminada_sem_renascimento_nao_conta` e o caso do renascimento;
- `test_revisao_sem_em_processo_e_ruido`;
- `test_ciclo_completo_grava_situacao_emissao` — planilha real ponta a ponta,
  conferindo inclusive **os tipos** (data nativa, número) e o nível 1 vazio;
- `test_planilha_sem_as_colunas_novas_continua_rodando`.

### 9.7 `docs/doc_list_mapping.md`

Cabeçalho 21 → 24 colunas, tabela Calculado × Input manual, e uma seção
"Situação de emissão" com as regras.

### 9.8 A planilha — `tools/criar_colunas_situacao_emissao.py`

Script idempotente que cria as colunas já formatadas. **Já foi rodado na planilha
real** (aba `Unidade Geradora`): colunas **X, Y, Z**, autofiltro estendido de
`B3:V1182` para `B3:Z1182`, backup gravado ao lado.

Decisões do script, que valem para qualquer manutenção futura:

- **Anexa no fim, nunca insere no meio.** `ws.insert_cols()` do openpyxl move os
  valores mas **não** move larguras de coluna, ranges de formatação condicional
  nem o autofiltro — numa planilha real isso vira dano visível. Como o app acha
  coluna pelo texto do cabeçalho, a posição não importa para o código.
- Copia o estilo da **mesma linha** de uma coluna-modelo vizinha, então herda de
  graça qualquer zebra/borda que a planilha use.
- Faz backup datado antes de gravar (coberto pelo glob do `.gitignore`).

> ⚠️ **Mover, agrupar, ocultar e reordenar as colunas é seguro. Renomear não** —
> o vínculo com o código é o texto do cabeçalho.

---

## 10. O que fazer no Power BI

A **ordem importa**: a coluna precisa existir no modelo antes de o visual
conseguir usá-la.

### Passo 0 — encher as colunas (obrigatório, antes de tudo)

`tools/criar_colunas_situacao_emissao.py` criou as colunas **vazias**. Quem as
preenche é a atualização normal do Doc List pelo app, que precisa da Base Aconex
(+ Controle de Documentos). **Rode isso primeiro**, senão o gráfico sai todo
cinza de `(Em branco)`.

Confira na planilha que `SITUAÇÃO EMISSÃO` tem valores antes de abrir o Power BI.

### Passo 1 — Atualizar

Abrir o `.pbix` → **Página Inicial › Atualizar**. É isso que traz as três colunas
novas da planilha para o modelo.

> Se as colunas **não aparecerem** no painel de Campos depois do Atualizar, a
> consulta do Power Query tem uma lista fixa de colunas. Nesse caso:
> **Transformar dados**, selecionar a etapa *Origem*/*Navegação*, e conferir se
> alguma etapa posterior (`Colunas Removidas`, `Outras Colunas Removidas`) está
> barrando as novas — basta editar essa etapa.

### Passo 2 — o gráfico

No visual **DOCUMENTOS PARA EMISSÃO** (canto inferior direito):

| Campo | Onde vai |
|---|---|
| `DATA-ALVO EMISSÃO` → Dia | **Eixo X** — *não mexer*, é o que mantém a barra no dia previsto |
| `Contagem de N° ITAIPU` | **Eixo Y** — não mexer |
| **`SITUAÇÃO EMISSÃO`** | **Legenda** ← *a única adição* |
| `DATA 1ª EMISSÃO`, `DIAS DESVIO EMISSÃO` | **Dicas de ferramenta** (opcional) |

Ao soltar na Legenda o gráfico vira **coluna empilhada**: a barra do dia 3
continua no dia 3, mas se reparte por cor.

### Passo 3 — filtro do CANCELADO

Com o visual selecionado, no painel **Filtros** › *Filtros neste visual*,
arrastar `SITUAÇÃO EMISSÃO` e desmarcar **CANCELADO** (decisão §11.3).
Cancelado é terminal e não deve inflar a barra do dia.

### Passo 4 — formatação

- **Legenda**: ligar (vem desligada), posição inferior-centro.
- **Cores dos dados**, uma por balde:

  | Balde | Cor |
  |---|---|
  | `EMITIDO NO PRAZO` | `#038B25` verde |
  | `EMITIDO COM ATRASO` | `#C00000` vermelho |
  | `PENDENTE NO PRAZO` | `#EEBA00` amarelo |
  | `PENDENTE VENCIDO` | `#7B1416` vermelho escuro |
  | `SEM PLANEJAMENTO` | `#A6A6A6` cinza |

  O verde e o amarelo são os que o relatório já usa em outros visuais.

### Atalho: o `.pbix` pré-editado

Existe um `Dashboard - Doc List Mapping (situacao emissao).pbix` com os
**passos 2 e 4 já aplicados** por edição direta do JSON (o `.pbix` é formato
PBIR: um `visual.json` por visual). Nele:

- `SITUAÇÃO EMISSÃO` já está na Legenda (role `Series`);
- legenda ligada;
- as 5 cores + `CANCELADO` em cinza escuro;
- `DATA 1ª EMISSÃO` e `DIAS DESVIO EMISSÃO` no tooltip;
- os **53 seletores órfãos** de `Riscos`/`Planilha riscos` no `dataPoint`
  removidos (§4).

Só o `visual.json` desse visual mudou — `DataModel` e os outros 33 arquivos do
pacote estão byte a byte idênticos ao original.

**Ainda assim ele precisa dos passos 0, 1 e 3.** O `DataModel` é um binário
compilado que não dá para editar por fora: enquanto o Atualizar não rodar, o
modelo não conhece as colunas e o visual pode aparecer com erro de campo — some
depois do Atualizar. E o filtro do CANCELADO ficou de fora porque o schema do
`filterConfig` não é público e eu não tinha como validar o que escrevesse.

> Se o arquivo pré-editado der qualquer problema, **jogue-o fora e siga os passos
> 2 e 4 na mão** — são cinco minutos de clique e o resultado é idêntico. O
> original não foi tocado.

**Ganho:** a mesma barra deixa de ser carga prevista e vira **aderência ao
plano** — "do que estava previsto para o dia 3, quanto saiu, quanto saiu
atrasado e quanto ainda não saiu".

### Evolução posterior (não agora)

Com `DATA 1ª EMISSÃO` como data nativa no modelo, abre-se a possibilidade de um
segundo visual *previsto × realizado* no mês, sem tocar no primeiro. Aí sim
valeria introduzir uma tabela-calendário de verdade e aposentar a auto date
hierarchy.

---

## 11. Decisões do usuário (respondidas)

Respondidas em 2026-09-16; já implementadas e cobertas por teste.

### 11.1 `.max()`, não `.min()`

> *"É pra ser a data da emissão da 0A de fato; se por ventura existir um documento
> 2x reemitido, prevalece a segunda data (mais recente), pq foi pra corrigir algum
> erro da primeira."*

Dentro da revisão nascedoura vale a emissão **mais recente**. Efeito colateral
bom: é o mesmo `.max()` que o Momento A já usava, então nada mudou em produção.

### 11.2 `0A` preferida, com fallback para documentos SAT

> *"Mantém a 0A (…) fico com medo dos documentos com formatos SAT, onde geralmente
> eles são continuação de documentos já existentes de Itaipu (legado) e daí já
> começam em revisões mais altas; nesse caso seria interessante termos a primeira
> emissão pra Itaipu (ou seja, desconsiderar os lixos já descartados)."*

Implementado como as duas metades da frase: **`0A` quando existe; senão, a
emissão mais antiga do histórico limpo**. O "lixo já descartado" some sozinho —
`_preparar_historico` extermina ciclos internos (`0AA`) e aplica o limiar de
*Terminated* antes de qualquer coisa.

Isso é **diferente** do que o código fazia antes (primeira revisão cronológica,
sem preferir `0A`) — daí a divergência deliberada com o Momento A descrita em §9.1.

### 11.3 `CANCELADO` fora do gráfico

Balde próprio, com **precedência sobre todos os outros**: cancelado é terminal,
não interessa mais se nasceu no prazo. O valor é gravado na coluna para o dado
não mentir, e o gráfico o exclui por **filtro do visual** (§10, passo 4).

---

## Referências rápidas

| O quê | Onde |
|---|---|
| Regras de domínio do Doc List | KB §27 (`knowledge_base_docmanager.md`) |
| Guia prático da planilha/tela | [`docs/doc_list_mapping.md`](doc_list_mapping.md) |
| Reconciliação de datas | `docmanager/core/planejamento.py` (KB §24.13) |
| Linha da verdade / Terminated | [`core/truth_line.py:84`](../docmanager/core/truth_line.py#L84) (KB §8.9, §21.8) |
| KPIs e atrasos | [`core/kpis.py`](../docmanager/core/kpis.py) (KB §14, §15) |
| Nascedouro (Momento A) | [`core/kpis.py:130`](../docmanager/core/kpis.py#L130) |
