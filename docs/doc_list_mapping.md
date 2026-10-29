# Doc List Mapping — estrutura e regras de uso

> Módulo criado a partir do Mapa dos Planos para acompanhar uma **lista de
> documentos** com regras próprias. Regras de domínio na KB §27; este arquivo é
> o guia prático da planilha e da tela.

## Para que serve

Follow-up semanal de uma documentação já definida: você mantém a planilha, roda
o módulo, e ele atualiza status, hierarquia, resumo por escopo e as datas de
planejamento a partir da base do Aconex e do Controle de Documentos.

## Cabeçalho oficial (26 colunas)

```
GRUPO · SISTEMA · FASE DE PROJETO · Nº CMI · N° ITAIPU ·
DESCRIÇÃO DO DOCUMENTO · DATA PREVISTA EMISSÃO · DATA REPROGRAMADA ·
DATA-ALVO EMISSÃO · EMITIDO / NÃO EMITIDO · DATA ÚLTIMA EMISSÃO ·
ÚLTIMA REV. EMITIDA · DATA 1ª EMISSÃO · SITUAÇÃO EMISSÃO ·
DIAS DESVIO EMISSÃO · SITUAÇÃO OTD · SITUAÇÃO SAY-DO · STATUS REAL · STATUS ·
RESPONSIBLE (COE/VENDOR) · NÍVEL · STATUS CONSOLIDADO · COM ITAIPU ·
PREDECESSOR · OBSERVAÇÕES · RESUMO QUANTIDADES
```

> **A ordem não importa.** As colunas são localizadas pelo TEXTO do cabeçalho,
> então mover, agrupar ou ocultar não afeta nada — só **renomear** quebra.
> `SITUAÇÃO OTD` e `SITUAÇÃO SAY-DO` o próprio app cria no fim da aba, na
> primeira atualização, com a formatação das vizinhas (o log diz em que coluna).
> Planilha sem as outras colunas de emissão continua rodando: o log avisa quais
> faltam e elas são ignoradas. Para criá-las já formatadas:
> `python tools/criar_colunas_situacao_emissao.py "Doc List Mapping.xlsx" --aba "Unidade Geradora"`

⚠️ Atenção aos codepoints: `N° ITAIPU` usa **U+00B0** (sinal de grau) e
`Nº CMI` usa **U+00BA** (ordinal) — trocar um pelo outro faz a localização do
cabeçalho falhar. Se precisar recriar a coluna, copie o texto daqui.

O cabeçalho é localizado dinamicamente nas 10 primeiras linhas (âncora
`N° ITAIPU`), e os nomes são comparados sem acento, em maiúsculas e com espaços
colapsados — cabeçalho quebrado em duas linhas dentro da célula continua sendo
reconhecido.

### Cabeçalhos legados

Quem veio da planilha adaptada do mapeamento tem nomes antigos. Eles são
reconhecidos e **renomeados automaticamente** na primeira atualização:

| Antes | Agora |
|---|---|
| `TROCAR` | `DATA-ALVO EMISSÃO` |
| `RESPONSÁVEL` | `RESPONSIBLE (COE/VENDOR)` |
| `OBSERVAÇÃO` | `OBSERVAÇÕES` |
| `DATA PREVISTA EMISSÃO ETAPA 1` | `DATA PREVISTA EMISSÃO` |

## Níveis: 1 é agrupamento, 2 é documento

- **Nível 1** — um por escopo das Unidades Geradoras. **Não é um documento**:
  não é procurado no Aconex nem no Controle. Recebe `NÃO EMITIDO` nas colunas de
  status, `CMI` em `COM ITAIPU`, o próprio código em `PREDECESSOR` e o
  `RESUMO QUANTIDADES` dos seus filhos.
- **Nível 2** — os documentos. `PREDECESSOR` = código do grupo imediatamente
  acima na ordem física da planilha (a hierarquia é posicional: **não reordene
  as linhas** sem querer mudar o agrupamento).

## O que é calculado e o que é seu

| Calculado (sobrescrito a cada atualização) | Input manual (nunca sobrescrito) |
|---|---|
| `DATA-ALVO EMISSÃO`, `EMITIDO / NÃO EMITIDO`, `DATA ÚLTIMA EMISSÃO`, `ÚLTIMA REV. EMITIDA`, `DATA 1ª EMISSÃO`, `SITUAÇÃO EMISSÃO`, `DIAS DESVIO EMISSÃO`, `SITUAÇÃO OTD`, `SITUAÇÃO SAY-DO`, `STATUS REAL`, `STATUS`, `STATUS CONSOLIDADO`, `COM ITAIPU`, `PREDECESSOR`, `RESUMO QUANTIDADES` | `GRUPO`, `SISTEMA`, `NÍVEL`, **`FASE DE PROJETO`**, `RESPONSIBLE (COE/VENDOR)`, `OBSERVAÇÕES` |

`DATA PREVISTA EMISSÃO` e `DATA REPROGRAMADA` ficam no meio: o Controle preenche
quando estão vazias, mas preenchidas só mudam com o seu aceite (ver "Datas de
planejamento").

`Nº CMI`, `N° ITAIPU` e `DESCRIÇÃO DO DOCUMENTO` são atualizados quando o
Aconex traz um valor novo (o código do documento muda ao longo da vida).

### Descrição: Aconex → Controle → planilha

A prioridade da `DESCRIÇÃO DO DOCUMENTO`, nessa ordem:

1. **Aconex**, quando o documento existe na base;
2. **Controle de Documentos** — se o documento não está no Aconex (o caso do
   previsto e ainda não emitido) mas é encontrado no Controle, a `DESCRIÇÃO` de
   lá é gravada, **sobrescrevendo** o que estiver na célula. É proposital:
   descrição digitada à mão costuma ser genérica, e a do Controle complementa;
3. o que já está na planilha, quando não há nenhuma das duas fontes.

## Datas de planejamento

| Coluna | De onde vem | Regra |
|---|---|---|
| `DATA PREVISTA EMISSÃO` | `DATA PREVISTA DE EMISSÃO ACONEX` ou digitada por você | vazia → a do Controle; preenchida → **só com o seu aceite**. É a **baseline** do Baseline OTD |
| `DATA REPROGRAMADA` | `REPROGRAMAÇÃO` do Controle **ou** digitada por você | vazia → a do Controle; preenchida → **só com o seu aceite** |
| `DATA-ALVO EMISSÃO` | derivada | `REPROGRAMADA` quando existe, senão `PREVISTA` |

> A regra vale também para a etapa 1 do **Mapa dos Planos** — a implementação é
> uma só, em `core/planejamento.py` (KB §24.14, ADR 0001). Até 2026-10 a
> `DATA PREVISTA` ficava com a mais recente das duas, e a data original se perdia.

### Quando o Controle trocaria uma data preenchida

Uma data já preenchida (digitada à mão ou escrita numa rodada anterior; o app não
distingue) só é trocada pela do Controle se você aceitar. Também contam como
preenchidas a célula com texto (`A DEFINIR`) e a com fórmula. Cada troca possível é
uma **incidência**, e no meio da atualização o DocManager pergunta:

- **Aceitar todas** — todas ficam com a data do Controle;
- **Não sobrescrever** — todas ficam como estão e são anotadas como recusadas;
- **Ver caso a caso** — a lista das incidências (documento, descrição, coluna, data
  na planilha, data no Controle) com caixa de marcar: as marcadas são trocadas, as
  desmarcadas ficam e são anotadas como recusadas.

Fechar a janela é decidir depois: nada é trocado nem anotado, e a pergunta volta na
próxima atualização. Trocar a `DATA PREVISTA` muda a baseline: o Baseline OTD passa a
medir contra a data nova (a tela avisa).

As recusas ficam na aba **"Sobrescrições recusadas"**, que o app cria na própria
planilha (N° ITAIPU, Nº CMI, coluna, data na planilha, data do Controle, quando e
quem). Uma recusa não é perguntada de novo enquanto o Controle mantiver a mesma data;
se ele mudar outra vez, a pergunta volta. Para ser perguntado de novo antes disso,
apague a linha da aba. O Power BI não lê essa aba.

Todas gravadas como **data nativa** do Excel, no formato **Data** (e não
"Personalizado"), que aparece como dd/mm/aaaa e que o Power BI lê como data: é o
que permite o dashboard agrupar por período. Data digitada como texto nas
colunas de planejamento vira data na próxima atualização; texto que não é data
(ex.: "A DEFINIR") fica, mas o log aponta a coluna e a linha, porque ele impede
o Power BI de ler a coluna como data.

> Sem o Controle de Documentos o módulo roda normalmente: apenas as datas de
> planejamento e o resgate da descrição não acontecem.

## Baseline OTD e Say-do

Pedido da gestão (out/2026): mostrar o que atrasou contra a data original e se o
novo compromisso dos atrasados está sendo cumprido. Vocabulário em `GLOSSARY.md`;
regra de domínio na KB §27.7.

| Coluna | Compara a 1ª emissão (ou hoje) com | Quem tem |
|---|---|---|
| `SITUAÇÃO EMISSÃO` | a `DATA-ALVO EMISSÃO` (visão atual) | todo documento |
| `SITUAÇÃO OTD` | a `DATA PREVISTA EMISSÃO` (a baseline) | todo documento |
| `SITUAÇÃO SAY-DO` | a `DATA REPROGRAMADA` (o novo compromisso) | só o **backlog** |

Os baldes são os mesmos da situação de emissão (abaixo). **Backlog** é o documento
com `DATA REPROGRAMADA` posterior à `DATA PREVISTA` que não tinha saído até a
`DATA PREVISTA`: entra assim que é reprogramado. Não entram a reprogramação igual à
prevista nem o documento que já tinha saído no prazo (a data reprogramada dele é de
outra revisão).

No Power BI, os indicadores contam códigos distintos:

- **Baseline OTD** do período = (documentos com `DATA PREVISTA` no período − atrasados
  contra ela) ÷ documentos com `DATA PREVISTA` no período;
- **Say-do** do período = a mesma conta sobre o backlog, com a `DATA REPROGRAMADA`.

Nos dois, o que ainda não venceu conta como cumprido e o cancelado fica fora. O
"vencido" é o do dia em que o app rodou: **antes de apresentar, rode o DocManager e
clique em Atualizar no Power BI.** O passo a passo do painel (três visões, cartões e
curva S) está em [`power_bi_otd_say_do.md`](power_bi_otd_say_do.md).

## Situação de emissão (aderência ao planejamento)

Responde o que o `STATUS CONSOLIDADO` não responde: **o documento saiu na data
que estava planejada?**

A régua é a `DATA 1ª EMISSÃO` — **nunca** a `DATA ÚLTIMA EMISSÃO`. Evoluir de
`0A` até `0F` é ciclo normal de aprovação; comparar a última revisão com a
data-alvo acusaria meses de atraso num documento que nasceu adiantado.

| Coluna | O que é |
|---|---|
| `DATA 1ª EMISSÃO` | data nativa; quando a CMI entregou o documento pela primeira vez |
| `SITUAÇÃO EMISSÃO` | o balde (categoria única — é a Legenda do gráfico do dashboard) |
| `DIAS DESVIO EMISSÃO` | número; `1ª emissão − data-alvo`. **Negativo = adiantado** |

### Como a `DATA 1ª EMISSÃO` é achada

O evento de emissão é a linha `Em Processo` do Aconex — a submissão à Itaipu.
Sobre o histórico já limpo (ciclos internos tipo `0AA` exterminados, revisões
mortas por *Terminated* removidas):

1. **A revisão nascedoura é a `0A`**, quando ela existe.
2. **Sem `0A`, vale a emissão mais antiga.** É o caso dos documentos **SAT**,
   que continuam documentos legados da Itaipu e já entram em revisões altas — ali
   o que interessa é a primeira entrega *para a Itaipu*, sem o lixo já descartado.
3. **Dentro da revisão nascedoura vale a emissão mais recente**: reenvio da mesma
   revisão corrigiu a entrega anterior, então é ele que marca a entrega válida.

Revisão que nunca teve `Em Processo` é ruído e não conta.

### Os baldes

| `SITUAÇÃO EMISSÃO` | Quando |
|---|---|
| `EMITIDO NO PRAZO` | 1ª emissão ≤ data-alvo |
| `EMITIDO COM ATRASO` | 1ª emissão > data-alvo |
| `PENDENTE NO PRAZO` | ainda não emitido, hoje ≤ data-alvo |
| `PENDENTE VENCIDO` | ainda não emitido, hoje > data-alvo |
| `SEM PLANEJAMENTO` | sem data-alvo — o mesmo furo da aba "Sem Planejamento" |
| `CANCELADO` | terminal; **fica fora do gráfico** por filtro do visual |

Agrupamentos (nível 1) ficam com as três células **vazias**: não são documento e
não devem poluir a legenda.

> No Power BI: `SITUAÇÃO EMISSÃO` vai na **Legenda** do gráfico
> "DOCUMENTOS PARA EMISSÃO". O eixo continua sendo a `DATA-ALVO EMISSÃO`, então
> a barra **permanece no dia planejado** e só se reparte por cor. Detalhes e
> paleta em [`situacao_emissao_dashboard.md`](situacao_emissao_dashboard.md).

## Status consolidado

| STATUS REAL | STATUS CONSOLIDADO |
|---|---|
| `Aprovado`, `Aprovado com Comentários`, `Para Assinatura`, `Informativo`, `Para Aprovação` | `APROVADO` |
| `Não Aprovado` | `NÃO APROVADO` (ou `EM PROCESSO`, se já reemitiu) |
| `Em Processo` | `EM PROCESSO` |
| `Cancelado` | `CANCELADO` |
| documento sem histórico | `NÃO EMITIDO` |

É o **mesmo consolidado do Mapa dos Planos**: os três status de aprovação caem
num balde só. O consolidado serve para **agregar** — quem precisa do detalhe usa
a coluna `STATUS REAL`, que distingue `Aprovado` de `Aprovado com Comentários` e
`Para Assinatura`. No dashboard, é só trocar de coluna.

> **Anulação**: o Aconex grava `Anulado`, `VOID`, `Issued for Annulment` ou
> `Cancelado` para a mesma coisa. O `STATUS REAL` unifica tudo em **`Cancelado`**.

O `RESUMO QUANTIDADES` do grupo acompanha:

```
Total: 45
Aprovados: 27
Em Processo: 1
Não Aprovados: 7
Não Emitidos: 10
```

(`Cancelados` e `Outros` só aparecem quando existem — o total sempre fecha.)

## As duas análises por período

O módulo tem duas, e elas olham para lados opostos:

| Botão | Olha para | Fonte | Responde |
|---|---|---|---|
| 🗓️ **Analisar Período** | frente | `DATA-ALVO EMISSÃO` da planilha | o que está **previsto para emitir** |
| ⏳ **Analisar Mudanças por Período (Delta)** | trás | histórico do Aconex | o que **aconteceu** entre duas datas |

### 🗓️ Analisar Período (previstos)

Responde *quais documentos estão previstos para emitir nos próximos tempos*,
usando a `DATA-ALVO EMISSÃO`.

- **Atalhos**: vencidos, próximos 7/30/90 dias, restante deste mês, mês que vem,
  este ano — ou um intervalo manual (qualquer ponta pode ficar vazia).
- **Agrupamento** por Mês, Grupo, Sistema ou Fase de Projeto.
- Cada linha mostra a **origem** da data (`Prevista` ou `Reprogramada`) e os dias
  até o alvo (negativo = vencido, em vermelho).
- Agrupamentos (nível 1) ficam de fora; documentos já emitidos também, salvo se
  você marcar "Incluir já emitidos".
- O **Excel** sai com um quadro por mês, o detalhe, e uma aba
  **"Sem Planejamento"** com os documentos que não têm nenhuma data — o furo que
  a análise por período não enxerga e que precisa ser fechado no Controle.

Duplo-clique num documento copia o código para a área de transferência.

### ⏳ Delta por Período (o que aconteceu)

A "Máquina do Tempo" do Mapa dos Planos, aplicada a esta planilha: compara o
status de cada documento entre duas datas e mostra quem mudou, em árvore
Grupo/Nível/Documento. Precisa da **Base Aconex** selecionada (é de lá que vem o
histórico). Visão *Efetiva* (só mudança de status real) ou *Bruta* (também nova
revisão/data), filtro para ocultar quem já estava aprovado, e exportação Excel.

Documento repetido dentro do mesmo grupo conta **uma vez**; documento presente em
mais de um grupo aparece em vermelho.

## Contrato de código

`docmanager/doclist_backend.py` é a porta única:

- `atualizar_doclist(path_aconex, path_doclist, *, sheet_aconex, sheet_doclist,
  controle, hoje, log_cb, progress_cb, retry_cb) -> ResultadoDocList`
- `ler_linhas_doclist(caminho, sheet) -> list[LinhaDocList]`
- `analisar_periodo(linhas, *, inicio, fim, hoje, incluir_emitidos)`,
  `listar_sem_data(linhas)`, `janelas_padrao(hoje)`, `resumo(itens)`,
  `agrupar_por(itens, chave)`, `exportar_analise_periodo(...)`
- `calcular_mudancas_periodo(...)`, `exportar_delta_arvore(...)` — o Delta,
  reaproveitados do Mapa dos Planos
