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
A categoria única de aderência de um documento: emitido no prazo, emitido com
atraso, pendente no prazo, pendente vencido, sem planejamento ou cancelado.

**Pendente vencido**:
Documento ainda não emitido cuja data de referência já passou.
_Evite_: atrasado (sem dizer contra qual data)

## Relações

- Um **Grupo** reúne vários **Documentos**; um **Documento** pode aparecer em mais
  de um **Grupo**.
- A **Data-alvo** de um **Documento** é a **Data reprogramada** quando ela existe,
  senão a **Data prevista**.
- A **Situação de emissão** compara a **1ª emissão** (ou o dia de hoje, se o
  documento não saiu) com uma data de referência.

## Ambiguidades sinalizadas

Termos novos do pedido de `instruções.txt`, ainda em discussão no grilling.
Entram em **Language** quando forem decididos. Resolvido na rodada 1: "data
inicial" e "baseline" são a **Data prevista**.

- **"Backlog"**: pode ser (a) todo documento reprogramado, (b) todo documento que
  perdeu a baseline ou (c) o reprogramado que não saiu até a baseline. Proposta: (c).
- **"BL OTD"** (print) = **"Baseline OTD"** (instruções): mesmo indicador. Proposta:
  usar "Baseline OTD".
- **"Say-do"** (print) = **"Backlog Say-do"** (instruções): mesmo indicador.
- **"Atrasado"**: com baseline e data reprogramada convivendo, dizer sempre contra
  qual das duas.
- **Data reprogramada de documento já emitido**: na planilha atual há documentos
  já emitidos com data reprogramada, que parece ser a data da próxima revisão, e não
  da 1ª emissão. A definição acima não cobre esse uso.
