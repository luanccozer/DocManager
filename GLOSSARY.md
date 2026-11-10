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

**A recuperar**:
O documento que não saiu e cuja data prevista já passou, tenha ou não data
reprogramada. Tem **data nova** quando a data-alvo ainda não venceu.
_Evite_: backlog (é só o reprogramado), atrasados (sem dizer contra qual data)

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
- Um documento do **Backlog** que não saiu e já passou da **Data prevista** está **A
  recuperar**; o **A recuperar** sem **Data reprogramada** não é **Backlog**.

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
- "O backlog daquilo que precisa ser recuperado" (desenho da curva do projeto,
  2026-11-10) é o **A recuperar**: entre eles, só os reprogramados são **Backlog**.
