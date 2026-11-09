# DocManager Itaipu

Controle da documentação que a CMI emite para a Itaipu no projeto de atualização
tecnológica. Este glossário cobre, por enquanto, o vocabulário de planejamento e
aderência do Doc List Mapping.

## Language

### Planilhas e fontes

**Aconex**:
O sistema onde a CMI submete cada documento à Itaipu. É a fonte da verdade do
status e da data de cada emissão.

**Controle de Documentos**:
A planilha de planejamento da equipe: diz quando cada documento deve ser emitido
e, quando houver, a reprogramação.
_Evite_: "controle" solto (confunde com o Doc List)

**Doc List Mapping**:
A planilha de acompanhamento da documentação das Unidades Geradoras, que alimenta
o painel "Gestão de Documentação de Execução".
_Evite_: mapeamento, Mapa dos Planos (são outra planilha)

**Grupo**:
Linha de agrupamento por escopo no Doc List (nível 1). Não é documento e não entra
em indicador nenhum.
_Evite_: plano, documento de nível 1

**Documento**:
Item de nível 2 do Doc List, identificado pelo código Itaipu. Os indicadores contam
cada código uma vez, mesmo que ele apareça em mais de um grupo.
_Evite_: plano, item

### Datas

**Data prevista**:
A data planejada para a 1ª emissão do documento. É a baseline: uma vez definida,
só muda quando alguém aceita a troca.
_Evite_: data inicial, data original, data base

**Data reprogramada**:
A nova data assumida para a 1ª emissão de um documento que perdeu, ou ia perder,
a data prevista.
_Evite_: reprogramação (quando se fala da data, e não do ato)

**Data-alvo**:
A data que vale hoje para cobrar a emissão: a reprogramada, se existir; senão, a
prevista.
_Evite_: TROCAR (nome antigo da coluna)

**1ª emissão**:
A primeira submissão do documento à Itaipu: a revisão 0A ou, no documento que já
nasce em revisão alta, a submissão mais antiga.
_Evite_: última emissão (é a revisão mais recente, outra coisa)

**Sobrescrição**:
A troca de uma data já preenchida na planilha pela data do Controle de Documentos.
Só acontece com o aceite de quem roda a atualização.
_Evite_: atualização (é a rodada inteira, não a troca de uma data)

**Incidência**:
Cada data preenchida da planilha que o Controle de Documentos trocaria, isto é,
cada sobrescrição pendente de decisão.

### Aderência

**Situação de emissão**:
A categoria única de aderência de um documento à data-alvo: emitido no prazo,
emitido com atraso, pendente no prazo, pendente vencido, sem planejamento ou
cancelado. É a visão atual do painel.

**Situação OTD**:
A mesma categoria, medida contra a data prevista (a baseline).

**Pendente vencido**:
Documento ainda não emitido cuja data de referência já passou.
_Evite_: atrasado (sem dizer contra qual data)

**Atrasado**:
Documento que saiu depois de uma data, ou que não saiu e essa data já passou.
Sempre se diz contra qual data: a prevista ou a reprogramada.

### Indicadores

**Backlog**:
O documento cuja data reprogramada é posterior à data prevista e que não tinha
saído até a data prevista. Entra no backlog quando é reprogramado.
_Evite_: reprogramados (inclui quem já tinha saído no prazo), atrasados

**Baseline OTD**:
A parcela dos documentos com data prevista no período que não atrasaram contra
ela. O que ainda não venceu conta como cumprido.
_Evite_: BL OTD, OTD (sem dizer contra qual data)

**Say-do**:
A parcela dos documentos do backlog com data reprogramada no período que não
atrasaram contra ela. O que ainda não venceu conta como cumprido. É o "falar-fazer":
mede se o novo compromisso foi cumprido.
_Evite_: Backlog Say-do (mesmo indicador)

**Situação say-do**:
A categoria de aderência de um documento do backlog à data reprogramada; fora do
backlog, não existe.

### Pendências (Aconex Campo)

**Questão**:
O registro do módulo Campo (Field) do Aconex. Na API e na exportação, "Issue".
_Evite_: issue (em texto para a equipe), ocorrência

**Pendência de comissionamento**:
Uma questão do Campo acompanhada pela equipe na planilha de mapeamento de pendências.
_Evite_: pendência solta quando puder confundir com pendência de documento

**Planilha de mapeamento de pendências**:
A planilha da equipe ("ACONEX - MAPEAMENTO PENDÊNCIAS") que o módulo Pendências atualiza:
uma Tabela do Excel com as questões, colunas manuais e tabelas dinâmicas com gráficos.
_Evite_: Mapa dos Planos, mapeamento (são outra planilha)

**Coluna do Aconex**:
Coluna da planilha de pendências cujo nome é o de uma coluna da exportação do Aconex ou de
um campo customizado dos tipos de questão em uso. O app a mantém igual ao Aconex.
_Evite_: coluna automática

**Coluna manual**:
Qualquer outra coluna da planilha de pendências; preenchida pela equipe e nunca tocada.
_Evite_: coluna extra

**Registro extraoficial**:
Linha feita à mão pela equipe com algo que não está no Aconex: no fim da tabela de
pendências, sem número do Aconex no Issue Number (com letras, como GRUPO 01, ou vazio),
ou logo abaixo da tabela. O app nunca a toca, nem valor nem formato: só a desloca para
baixo quando entram pendências novas no topo.
_Evite_: pendência manual (pendência de comissionamento é uma questão do Aconex), registro
manual, linha manual (confunde com coluna manual)

**Destaque de impeditiva**:
O texto da linha inteira em vermelho, sem preenchimento, quando a pendência é Impeditiva
e não está Closed. Entra e sai sozinho a cada atualização; só a cor do texto muda.
_Evite_: cor de status, formatação condicional (não é uma)

**Azul da atualização**:
O texto em azul (#0070C0) das pendências novas e das células que a última atualização
trocou ou preencheu. Na atualização seguinte que trouxer algo novo, volta ao preto.
_Evite_: azul manual

## Relações

- Um **Grupo** reúne vários **Documentos**; um **Documento** pode aparecer em mais
  de um **Grupo**.
- A **Data-alvo** de um **Documento** é a **Data reprogramada** quando ela existe,
  senão a **Data prevista**.
- A **Situação de emissão** compara a **1ª emissão** (ou o dia de hoje, se o
  documento não saiu) com a **Data-alvo**; a **Situação OTD**, com a **Data
  prevista**; a **Situação say-do**, com a **Data reprogramada**, só para o
  **Backlog**.
- Um documento do **Backlog** conta como atrasado no **Baseline OTD** e fica em
  aberto no **Say-do** até a **Data reprogramada**.

## Ambiguidades resolvidas

- "Data inicial" e "baseline" (instruções) são a **Data prevista** (rodada 1).
- "BL OTD" (print) e "Baseline OTD" (instruções) são o mesmo indicador: **Baseline
  OTD** (rodada 2).
- "Say do" (print) e "Backlog Say-do" (instruções) são o mesmo indicador: **Say-do**;
  o gráfico de say-do é o gráfico do **Backlog** (rodada 2).
- Documento já emitido no prazo com data reprogramada (a data é de outra revisão)
  não é **Backlog** (rodada 2).
- A **Situação de emissão** continua contra a **Data-alvo** (visão atual); a régua da
  **Data prevista** é a **Situação OTD** (rodada 3: o painel mantém as três visões).
