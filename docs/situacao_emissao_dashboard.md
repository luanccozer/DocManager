# Situação de Emissão — do Doc List Mapping ao dashboard Power BI

> **Status: proposta mapeada, nada implementado.** Este documento existe para que
> uma próxima sessão possa clonar o repositório e codar direto, sem refazer o
> levantamento. Levantamento feito em 2026-09-16 sobre
> `Doc List Mapping.xlsx` e `Dashboard - Doc List Mapping.pbix`.

## Índice

1. [Arquivos que NÃO entram no Git](#1-arquivos-que-não-entram-no-git)
2. [Mapa do módulo Doc List Mapping](#2-mapa-do-módulo-doc-list-mapping)
3. [Pipeline de atualização, passo a passo](#3-pipeline-de-atualização-passo-a-passo)
4. [Anatomia do dashboard (PBIX)](#4-anatomia-do-dashboard-pbix)
5. [O gap: o gráfico não sabe o que foi executado](#5-o-gap-o-gráfico-não-sabe-o-que-foi-executado)
6. [Por que as colunas existentes não resolvem](#6-por-que-as-colunas-existentes-não-resolvem)
7. [A informação já é calculada e descartada](#7-a-informação-já-é-calculada-e-descartada)
8. [Proposta: 2 (ou 3) colunas novas](#8-proposta-2-ou-3-colunas-novas)
9. [Plano de implementação, arquivo a arquivo](#9-plano-de-implementação-arquivo-a-arquivo)
10. [O que fazer no Power BI depois](#10-o-que-fazer-no-power-bi-depois)
11. [Decisões pendentes do usuário](#11-decisões-pendentes-do-usuário)

---

## 1. Arquivos que NÃO entram no Git

`Doc List Mapping.xlsx` e `Dashboard - Doc List Mapping.pbix` contêm dados reais
do cliente. **Nunca versionar.** Já estão bloqueados no `.gitignore`:

```
Doc List Mapping.xlsx
*.pbix
```

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

### Cabeçalho da planilha (21 colunas)

```
GRUPO · SISTEMA · FASE DE PROJETO · Nº CMI · N° ITAIPU ·
DESCRIÇÃO DO DOCUMENTO · DATA PREVISTA EMISSÃO · DATA REPROGRAMADA ·
DATA-ALVO EMISSÃO · EMITIDO / NÃO EMITIDO · DATA ÚLTIMA EMISSÃO ·
ÚLTIMA REV. EMITIDA · STATUS REAL · STATUS · RESPONSIBLE (COE/VENDOR) ·
NÍVEL · STATUS CONSOLIDADO · COM ITAIPU · PREDECESSOR · OBSERVAÇÕES ·
RESUMO QUANTIDADES
```

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
kpis: dict,      # <-- calculado e DESCARTADO pelo Doc List
atrasos: dict,   # <-- calculado e DESCARTADO pelo Doc List
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

## 7. A informação já é calculada e descartada

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

**Conclusão:** `processar_documento` já devolve `kpis` e `atrasos` no
`ResultadoDocumento`, mas `_escrever_documento` grava só as 10 colunas
calculadas e **joga os dois dicionários fora**. A informação já existe a cada
atualização; falta só expô-la.

> ⚠️ Nota sobre DAX: **não dá para calcular isso no Power BI.** A regra de
> nascedouro depende do histórico do Aconex (limiar de Terminated, extermínio de
> ciclos internos), e esse histórico **não está no modelo** — só a planilha chega
> lá. O Python precisa resolver e entregar mastigado.

---

## 8. Proposta: 2 (ou 3) colunas novas

### Coluna A — `DATA 1ª EMISSÃO`

Tipo: **data nativa** (`set_data`, `dd/mm/aaaa`).
Valor: data do evento `Em Processo` da revisão nascedoura.
Vazia quando o documento é `NÃO EMITIDO`.

### Coluna B — `SITUAÇÃO EMISSÃO`

Tipo: texto, **categoria única** (é o que o Power BI vai colorir).

| Balde | Regra |
|---|---|
| `EMITIDO NO PRAZO` | `DATA 1ª EMISSÃO` ≤ `DATA-ALVO EMISSÃO` |
| `EMITIDO COM ATRASO` | `DATA 1ª EMISSÃO` > `DATA-ALVO EMISSÃO` |
| `PENDENTE NO PRAZO` | sem 1ª emissão **e** `hoje` ≤ `DATA-ALVO EMISSÃO` |
| `PENDENTE VENCIDO` | sem 1ª emissão **e** `hoje` > `DATA-ALVO EMISSÃO` |
| `SEM PLANEJAMENTO` | sem `DATA-ALVO EMISSÃO` |
| `CANCELADO` | `STATUS CONSOLIDADO == CANCELADO` *(decisão pendente — ver §11)* |

`SEM PLANEJAMENTO` é o mesmo furo que a aba "Sem Planejamento" da Análise de
Período já denuncia — trazê-lo para o dashboard dá visibilidade ao que hoje só
aparece no Excel exportado.

### Coluna C (opcional) — `DIAS DESVIO EMISSÃO`

Tipo: inteiro. `(DATA 1ª EMISSÃO - DATA-ALVO EMISSÃO).days`.
Negativo = adiantado, positivo = atrasado, vazio quando não emitido.
Serve para tooltip e para medidas de desvio médio.

---

## 9. Plano de implementação, arquivo a arquivo

### 9.1 `docmanager/core/kpis.py`

Extrair o cálculo do nascedouro para uma função pura reutilizável — hoje ele
está embutido dentro de `calcular_atrasos_acumulados` e só produz um número de
dias.

```python
def data_primeira_emissao(df_tracking: pd.DataFrame) -> date | None:
    """Data em que a revisão nascedoura foi emitida ('Em Processo').

    Usa a mesma higiene de _preparar_historico (ciclos internos exterminados,
    limiar de Terminated aplicado, ordenado por data). None quando o documento
    nunca foi emitido.
    """
```

Refatorar o "Momento A" para consumir essa função — **uma regra, um lugar**.
Cuidado: hoje o Momento A usa `.max()`; ver decisão §11.1 antes de mudar.

### 9.2 `docmanager/core/doclist.py`

Acrescentar as chaves em `COLUNAS_DOCLIST` (linha 45), **na posição desejada da
planilha** — sugestão: logo depois de `ÚLTIMA REV. EMITIDA`:

```python
"data_primeira_emissao": "DATA 1ª EMISSÃO",
"situacao_emissao": "SITUAÇÃO EMISSÃO",
"dias_desvio_emissao": "DIAS DESVIO EMISSÃO",   # opcional
```

E incluir as mesmas chaves em `COLUNAS_CALCULADAS` (linha 85) — são calculadas,
sobrescritas a cada atualização.

Adicionar a função pura de classificação (aqui, não no service):

```python
def classificar_situacao_emissao(
    *, data_primeira_emissao: date | None,
    data_alvo: date | None,
    status_consolidado: str,
    hoje: date,
) -> str:
```

### 9.3 `docmanager/core/mapping.py`

Adicionar os campos ao `ResultadoDocumento` (linha 29) e preenchê-los em
`processar_documento` (linha 154). `processar_documento` **já recebe
`data_prevista` e `hoje`** — mas atenção: o parâmetro chama-se `data_prevista` e
o que interessa aqui é a **DATA-ALVO** (reprogramada quando houver, senão
prevista). Conferir o que `doclist_update` está passando antes de assumir.

### 9.4 `docmanager/services/doclist_update.py`

Em `_escrever_documento` (linha 119), gravar:

```python
ds.set_data("data_primeira_emissao", row, r.data_primeira_emissao)
ds.set_val("situacao_emissao", row, r.situacao_emissao)
ds.set_val("dias_desvio_emissao", row, r.dias_desvio_emissao)
```

Em `_escrever_grupo` (linha 103), decidir o que o **Nível 1** recebe. Coerente
com o resto do módulo: `SITUAÇÃO EMISSÃO` vazio ou um marcador próprio — o
agrupamento não é documento e não deve poluir a contagem do gráfico. (Na
prática o gráfico só conta linhas com `DATA-ALVO`, e grupos não têm.)

### 9.5 `docmanager/services/excel_io.py`

Contém um mapa espelho de cabeçalhos (`"data_ultimo_status": "DATA ÚLTIMA
EMISSÃO", "revisao": "ÚLTIMA REV. EMITIDA"` por volta da linha 124). Verificar
se precisa acompanhar.

### 9.6 `docs/doc_list_mapping.md`

Atualizar: o cabeçalho passa de 21 para 23/24 colunas, e a tabela
"Calculado × Input manual" ganha as linhas novas.

### 9.7 `tests/test_doclist.py`

Casos mínimos a cobrir:

- doc emitido antes do alvo → `EMITIDO NO PRAZO`
- doc emitido depois do alvo → `EMITIDO COM ATRASO`
- doc com várias revisões (0A…0F) onde a **última** é posterior ao alvo mas a
  **primeira** não → tem de dar `EMITIDO NO PRAZO` *(este é o teste que prova o
  ponto todo)*
- doc não emitido, alvo no futuro → `PENDENTE NO PRAZO`
- doc não emitido, alvo no passado → `PENDENTE VENCIDO`
- doc sem `DATA-ALVO` → `SEM PLANEJAMENTO`
- doc cujo 0A foi *Terminated* sem renascimento → não conta como emitido
- doc com ciclo interno `0AA` antes do `0A` → o `0AA` é ignorado
- planilha **sem** as colunas novas → roda normalmente, só loga aviso

### 9.8 Planilha

As colunas precisam ser criadas manualmente na aba (ou via script). Enquanto não
existirem, o app roda e apenas avisa — ver §3, retrocompatibilidade.

---

## 10. O que fazer no Power BI depois

**Não implementado. Passos manuais no Power BI Desktop:**

1. Atualizar a fonte (a planilha agora tem as colunas novas).
2. Abrir o visual **DOCUMENTOS PARA EMISSÃO** (`619e9572eb5195c710bb`).
3. Eixo X **inalterado** — `DATA-ALVO EMISSÃO` → Dia. *A barra continua no dia
   previsto.*
4. Arrastar `SITUAÇÃO EMISSÃO` para **Legenda** → vira coluna empilhada; a barra
   se reparte por cor.
5. Ligar a legenda (hoje `legend.show = false`).
6. Definir cores por categoria. Sugestão alinhada à paleta já presente no
   arquivo:

   | Balde | Cor |
   |---|---|
   | `EMITIDO NO PRAZO` | verde `#038B25` |
   | `EMITIDO COM ATRASO` | vermelho |
   | `PENDENTE NO PRAZO` | amarelo `#EEBA00` |
   | `PENDENTE VENCIDO` | vermelho escuro |
   | `SEM PLANEJAMENTO` | cinza |

7. **Limpar os seletores órfãos** de `Riscos` / `Planilha riscos` no `dataPoint`
   desse visual (§4).
8. Tooltip: adicionar `DATA 1ª EMISSÃO` e `DIAS DESVIO EMISSÃO`.

**Ganho:** a mesma barra deixa de ser carga prevista e vira **aderência ao
plano** — "do que estava previsto para o dia 3, quanto saiu, quanto saiu
atrasado e quanto ainda não saiu".

### Evolução posterior (não agora)

Com `DATA 1ª EMISSÃO` como data nativa no modelo, abre-se a possibilidade de um
segundo visual *previsto × realizado* no mês, sem tocar no primeiro. Aí sim
valeria introduzir uma tabela-calendário de verdade e aposentar a auto date
hierarchy.

---

## 11. Decisões pendentes do usuário

Responder antes de codar — mudam o resultado.

### 11.1 `.max()` ou `.min()` na data de emissão?

O código hoje usa `df_nasc["Data_Obj"].max()`. Se a mesma revisão 0A foi
reenviada, a data "anda" para frente. Para *data da primeira emissão*, `.min()`
é mais fiel ao conceito. **Atenção:** mudar isso altera também o
`atraso_acumulado_cmi` já em produção — pode ser necessário manter `.max()` no
Momento A e usar `.min()` só na coluna nova.

### 11.2 Nascedoura ≠ literalmente `0A`

O código pega a primeira revisão cronológica, seja ela qual for (documento que
entrou direto em `0B`, herdado de outro contrato, etc.). Manter assim (mais
robusto) ou exigir literalmente `0A`?

### 11.3 `CANCELADO`

Balde próprio na `SITUAÇÃO EMISSÃO`, ou fica fora do gráfico?

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
