# Fluxos de Trabalho (Workflows) — guia prático

> Espelha a aba **Fluxos de Trabalho** do Aconex. É o único lugar que responde
> *"este documento está parado com quem, desde quando e vence quando?"* — a base
> de documentos (register) nunca teve essa informação.
> Regras de domínio e histórico da descoberta na KB **§24.12**; este arquivo é o
> guia de operação.

## Para que serve

A base do Aconex (register) diz **o que aconteceu** com cada revisão: enviou,
voltou, com qual veredito. Ela não diz **onde a coisa está agora**. A coluna
`Fonte` carrega o `WF-…`, mas só o número — nem a etapa, nem o responsável.

A Workflows API preenche exatamente esse buraco: etapa atual, prazo, dias de
atraso e **a quem está atribuída**, com nome e organização.

## O caminho, em duas etapas

```
Extração Aconex → aba "Fluxos de Trabalho"  →  Aconex_Workflows_<data>.xlsx
                                                        │
Relatórios → "Fluxos em Andamento" ─────────────────────┘
                                                        ↓
                                        Fluxos_Andamento_<data>.xlsx (3 abas)
```

São **dois arquivos diferentes** e dois seletores diferentes na tela. A base de
fluxos não substitui a base de documentos — elas se complementam.

### 1. Extrair

Em **Extração Aconex**, aba **Fluxos de Trabalho**. As credenciais são as mesmas
das outras abas (`.env`). Escolha o período:

| Período | Registros (set/2026) | Tempo |
|---|---:|---:|
| Tudo | ~96.000 | ~20 min |
| Últimos 12 meses | ~49.000 | ~10 min |
| Últimos 30 dias | ~9.000 | ~1 min |
| Últimos 7 dias | ~2.700 | ~40 s |

O período filtra por **data de alteração do fluxo** (`updated_after`), não por
data de criação: "últimos 30 dias" traz todo fluxo que se mexeu nesse intervalo,
inclusive um aberto há dois anos que recebeu uma ação ontem.

Se a conexão cair, o progresso fica salvo e a próxima execução retoma da página
seguinte — igual à extração de documentos. Uma extração interrompida é
sinalizada como **parcial**.

Pela linha de comando:

```bash
python -m docmanager.cli extrair-fluxos --out fluxos.xlsx            # tudo
python -m docmanager.cli extrair-fluxos --dias 30 --out fluxos.xlsx  # incremental
```

### 2. Gerar o relatório

Em **Relatórios**, card *Base de Fluxos de Trabalho*, botão **Fluxos em
Andamento**. Aponte o Excel da extração (aba `Fluxos`).

```bash
python -m docmanager.cli fluxos --fluxos fluxos.xlsx --out andamento.xlsx
```

## O que o relatório traz (3 abas)

**`Fluxos em Andamento`** — uma linha por etapa aberta, mais atrasada primeiro:
nº do fluxo, documento, revisão, título, etapa, **atribuído a**, organização,
recebimento, vencimento, **dias em aberto**, **dias de atraso** e situação
(`Atrasado` / `Vence hoje` / `No prazo` / `Sem prazo`, com semáforo).

**`Por Responsável`** — quem está segurando o quê: fluxos, atrasados, %
atrasados, atraso médio e máximo, e há quanto tempo espera o mais antigo.

**`Por Organização`** — o mesmo corte, por empresa.

### A regra do "em aberto"

Só entram linhas com **`Status do Fluxo` = `Em Andamento`** *e* **`Status da
Etapa` ∈ {`Atual`, `Em Atraso`}**.

Etapa `Concluído` é passado e `Previsão` ainda não começou — nenhuma das duas
responde "com quem está". Um mesmo fluxo tem várias etapas na base; só a aberta
aparece no relatório.

### Por que a soma "não bate"

Na aba **Por Responsável**, uma etapa com 10 revisores conta **1 para cada um** —
a pergunta é "o que está na mão do fulano". Então a soma da coluna `Fluxos`
passa do total de etapas, de propósito. A aba **Por Organização** não explode
pessoas: ali a soma fecha.

## Juntando com a base de documentos

As duas chaves já existem dos dois lados, e as colunas de documento na base de
fluxos usam **os mesmos nomes** do register justamente para isso:

| Base de Fluxos | Base de Documentos |
|---|---|
| `Tracking ID` (de `DocumentTrackingId`) | `Tracking ID` — identidade canônica |
| `Nº do Fluxo` (`WF-…`) | coluna `Fonte` |

O `Tracking ID` é a junção confiável (o documento pode trocar de código; o
tracking, não).

## Contrato da API (para quem for mexer no código)

```
GET https://us1.aconex.com/api/projects/{project_id}/workflows
Accept: application/vnd.aconex.workflow.v1+xml
    page_size      até 1000 (o guia diz "padrão 25")
    page_number    começa em 1
    updated_after  RFC3339 — 2026-08-01T00:00:00Z
    updated_before RFC3339
```

Rotas confirmadas funcionando neste projeto:

- `/workflows` — todos
- `/workflows/initiated-by/us` e `/workflows/initiated-by/others`
- `/workflows/assigned-to/us` e `/workflows/assigned-to/others`

Guia oficial (PDF) em `help.aconex.com/aconex/aconex-apis/` → *Workflows API
Developer Guide*. Existe também uma **Tasks API** (`/tasks`, exige `task_type`)
ainda não explorada.

### Campos da resposta

`WorkflowId` · `WorkflowNumber` · `WorkflowName` · `WorkflowTemplate` ·
`WorkflowStatus` · `StepName` · `StepStatus` · `StepOutcome` · `Assignees`
(N × organização/nome/UserId) · `Initiator` · `Reviewer` · `DateIn` · `DateDue` ·
`OriginalDueDate` · `DateCompleted` · `DaysLate` · `Duration` ·
`DocumentNumber` · `DocumentRevision` · `DocumentTitle` · `DocumentTrackingId` ·
`DocumentVersion` · `ReasonForIssue` · `Comments` · `FileName` · `FileSize` ·
`ParentWorkflowId` · `RelatedSupplierDocumentPackage`

## Armadilhas (todas verificadas ao vivo)

**1. O header `Accept` faz a API existir.** Com `application/xml` — o header da
extração de documentos — **toda** rota de workflow responde `404 URL_UNKNOWN`,
como se o serviço não existisse no tenant. O correto é
`application/vnd.aconex.workflow.v1+xml`. Foi o que fez a primeira investigação
concluir, errado, que a API não estava disponível. **Nunca copie o `Accept` do
register.**

**2. Os valores vêm em português.** `Em Andamento`, `Concluído`, `Encerrado`,
`Atual`, `Em Atraso`, `Previsão` — **não** em inglês (`In Progress`,
`Completed`), como o guia oficial documenta. Comparar com os rótulos do PDF não
casa nada.

**3. Vários valores vêm com espaço à direita** (`Concluído ` com o espaço). O
parse faz `strip()` na origem; se for ler o XML por fora, faça também.

**4. `DaysLate` da API não é o atraso de hoje.** É o atraso histórico daquela
etapa e vem preenchido **até em etapa concluída** (visto: 631 dias numa etapa
fechada). O relatório ignora esse campo e calcula `Dias de Atraso` contra a data
de hoje. A coluna crua continua na base, com o nome `Dias em Atraso`.

**5. Grão da linha**: cada `<Workflow>` é *fluxo × documento × etapa*, não um
fluxo. 96.000 linhas ≙ ~8.300 fluxos ≙ ~7.700 documentos.

**6. Homônimos são reais.** No diretório do projeto, **58 nomes** têm contas em
organizações diferentes (`BIANCA SANTOS` = 1 conta no CMI + 2 na GE). O resumo
agrupa por (nome, organização), então esses aparecem separados — está correto.
A coluna `Organizações (por atribuído)` guarda a organização de **cada** pessoa,
pareada com `Atribuído a`; sem ela, quem atua em etapas mistas se fragmenta.

**7. Paginação profunda dá `400`** quando `page_number` passa do total — é o fim
normal, tratado como tal, não erro.

## Baseline da primeira extração (04/09/2026)

Serve de referência para saber se algo saiu do lugar:

- 95.974 linhas · 8.327 fluxos · 7.685 documentos
- `Status do Fluxo`: Concluído 85.146 · Em Andamento 6.524 · Encerrado 4.304
- `Status da Etapa`: Concluído 86.960 · Encerrado 3.873 · Previsão 3.379 ·
  Em Atraso 1.193 · Atual 569
- **1.762 etapas em aberto**, sendo **1.193 atrasadas** (68%), atraso máximo
  1.055 dias, mediana dos atrasados 184 dias
- Por organização: ITAIPU 27,8% de atraso (741 etapas) · CMI 96,7% (1.015) ·
  GE 98,1% (693)

> O contraste entre Itaipu e CMI/GE merece leitura antes de virar indicador:
> boa parte dos atrasos extremos são etapas "Consórcio GE" paradas desde 2023,
> que podem ser fluxos abandonados e nunca encerrados, não trabalho pendente.

## Backlog — lapidação do relatório

Ideias levantadas e ainda **não** implementadas:

- **Separar fluxo vivo de fluxo abandonado** (o ponto acima). Talvez um corte por
  idade, ou cruzar com a última movimentação do documento no register.
- **Filtrar por organização/etapa na própria tela**, em vez de no Excel.
- **Enriquecer o Status Documentos** com "está com quem / vence quando",
  juntando por `Tracking ID`.
- **Usar `DateDue`/`OriginalDueDate` como prazo real** nos cálculos de atraso, no
  lugar do SLA presumido de 15/30 dias (KB §19) — a KB §24.5 registrava que essa
  data só viria da Workflows API; agora ela existe.
- **Reprogramação de prazo**: `DateDue` ≠ `OriginalDueDate` indica etapa
  reprogramada — ainda não explorado.
- **Tempo por etapa** (`Duration`, `StepName`) para achar o gargalo do fluxo.
- Achar a rota de busca **por status**, que existe no guia mas cujas grafias
  testadas deram 404 (hoje o filtro é feito no cliente, o que funciona bem).

## Onde está o código

| Peça | Arquivo |
|---|---|
| Extração / parse / Excel da base | `docmanager/workflows_backend.py` |
| Relatório (puro) | `docmanager/core/reports/fluxos.py` |
| Fachada do módulo | `docmanager/relatorios_backend.py` |
| Export das 3 abas | `docmanager/services/excel_io.py` |
| Constantes de domínio (`WF_*`) | `docmanager/core/constants.py` |
| Telas | `ui/views/aconex_view.py` e `ui/views/reports_view.py` |
| CLI | `docmanager/cli.py` (`extrair-fluxos`, `fluxos`) |
| Testes | `tests/test_fluxos.py` (16) |
