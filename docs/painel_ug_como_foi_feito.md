# Painel HTML da Unidade Geradora: como foi feito

Este documento explica, peça por peça, como o painel da UG é montado: de onde vem cada
dado, que regra calcula cada número e onde isso está no código. Os números de exemplo são
da planilha e da base do Aconex de 10/11/2026.

Para usar o painel, veja o guia [`painel_ug_html.md`](painel_ug_html.md). As regras ficam
resumidas também na seção 34 da [`knowledge_base_docmanager.md`](../knowledge_base_docmanager.md).
A decisão de fazer o painel assim está no [ADR 0003](adr/0003-painel-html-gerado-pelo-docmanager.md).

## Sumário

1. [A ideia em uma página](#1-a-ideia-em-uma-página)
2. [De onde vem cada dado](#2-de-onde-vem-cada-dado)
3. [Quais documentos entram](#3-quais-documentos-entram)
4. [Rastreamento: o Tracking ID de cada documento](#4-rastreamento-o-tracking-id-de-cada-documento)
5. [As regras do DocManager que o painel usa](#5-as-regras-do-docmanager-que-o-painel-usa)
6. [A linha do tempo de cada documento](#6-a-linha-do-tempo-de-cada-documento)
7. [O histórico de revisões: envios e retornos](#7-o-histórico-de-revisões-envios-e-retornos)
8. [Cada aba, cada gráfico](#8-cada-aba-cada-gráfico)
9. [Listas, Excel, idioma e ajuda](#9-listas-excel-idioma-e-ajuda)
10. [Como o arquivo é montado](#10-como-o-arquivo-é-montado)
11. [Onde está cada coisa no código](#11-onde-está-cada-coisa-no-código)
12. [Testes](#12-testes)
13. [Atualizar o painel e lançar a versão](#13-atualizar-o-painel-e-lançar-a-versão)
14. [Mudar um texto](#14-mudar-um-texto)
15. [Decisões tomadas e por quê](#15-decisões-tomadas-e-por-quê)
16. [Diferença para o Power BI](#16-diferença-para-o-power-bi)
17. [Limites conhecidos](#17-limites-conhecidos)
18. [Os três gráficos de % do Esforço: a matemática e como ler](#18-os-três-gráficos-de--do-esforço-a-matemática-e-como-ler)

---

## 1. A ideia em uma página

O painel é **um arquivo HTML só**, gerado pelo DocManager no módulo Doc List Mapping (botão
**Gerar Painel HTML**). Ele abre em qualquer navegador, sem internet, e pode ser guardado no
Box e reaberto depois.

```
 Doc List Mapping (aba Unidade Geradora)        Base do Aconex (extração do dia)
   quais documentos e o plano de cada um           o passado de cada documento
                 │                                            │
                 └──────────────────┬─────────────────────────┘
                                    ▼
            core/painel_ug.py  ← regras do DocManager, em Python, testadas
            (documento a documento: retrato de hoje, linha do tempo, revisões)
                                    │
                                    ▼
            dashboard/painel_ug_html.py  ← junta modelo + bibliotecas + dados
                                    │
                                    ▼
                    Painel_UG_ddmmaa.html  (arquivo único)
                    o JavaScript da página só filtra, conta e desenha
```

O princípio: **toda regra de negócio roda em Python**, com as mesmas funções que já atualizam
a planilha (status real, 1ª emissão, histórico consolidado, máquina do tempo). A página recebe
os dados prontos, documento a documento, e faz só contas simples sobre eles: filtrar, contar
por período, comparar duas datas. Assim o painel não tem uma segunda versão das regras que
possa divergir das do DocManager.

O painel é uma **foto**: mostra os dados do dia em que foi gerado. O cabeçalho diz qual base
do Aconex (e a data do último evento dela) e qual planilha foram usadas.

---

## 2. De onde vem cada dado

| Dado | Fonte | Como |
|---|---|---|
| Quais documentos entram | Doc List | As linhas de nível 2 da aba escolhida |
| Grupo, sistema, fase, responsável | Doc List | Lidos como estão (cada linha da planilha) |
| Data prevista, data reprogramada | Doc List | Lidas como estão |
| Data-alvo | Calculada | A reprogramada, se houver; senão, a prevista (a mesma regra da planilha) |
| Tracking ID | Aconex | A cascata de códigos do DocManager (seção 4) |
| Status real, status consolidado, com quem está, revisão atual, data da última emissão | Aconex | Recalculados com `processar_documento`, a mesma função da atualização do Doc List |
| Data da 1ª emissão | Aconex | `data_primeira_emissao` (seção 5.3) |
| Situação de emissão, situação OTD, situação say-do, backlog, desvio | Calculadas | As funções da planilha, com a 1ª emissão acima e as datas da planilha |
| Linha do tempo (status em cada data) | Aconex | Máquina do tempo (seção 6) |
| Revisões: envio, retorno, dias da Itaipu e da CMI | Aconex | Histórico consolidado (seção 7) |
| Descrição e Nº CMI | Aconex, senão Doc List | Os da linha atual do documento no Aconex; sem Aconex, os da planilha |

**Por que recalcular o status, em vez de ler as colunas da planilha?** Para o painel refletir a
base do Aconex escolhida, mesmo que a planilha não tenha sido atualizada com ela. Se a planilha
foi atualizada com a mesma base, os dois dão o mesmo resultado: na base de 10/11/2026, o status
recalculado bateu com o da planilha em 929 de 933 documentos achados (os 4 restantes tinham
movimento posterior à última atualização da planilha). O painel **não grava nada** na planilha
nem na base.

---

## 3. Quais documentos entram

**Documento** é cada código de nível 2 do Doc List. Grupos (nível 1) não são documentos.

- **Um código conta uma vez.** A chave é o Nº ITAIPU (ou o Nº CMI, se o Itaipu faltar). Quando o
  mesmo código aparece em várias linhas (por exemplo, em dois sistemas), vale a primeira linha
  para as datas e a descrição. Na planilha de 10/11/2026: 1.111 linhas de documento, 1.092
  códigos, 16 códigos em mais de uma linha. É a mesma conta do `DISTINCTCOUNT` do Power BI.
- **Cada linha vira uma associação** (documento × grupo × sistema × fase × responsável ×
  escopo). Os filtros olham para as associações: um documento passa no filtro de sistema se
  qualquer uma das suas linhas for daquele sistema.
- **Escopo UG ou 18A**: se o sistema da linha, ou o código do grupo de nível 1 acima dela, tem
  "18A" no nome (por exemplo `SDSC - UG 18A`, `eBOP - PRESS 18A FABR`, `MIG PLAN - 18A`), a linha é
  da 18A; senão, é UG. O PEM (planos) só tem o 18A no grupo. Na planilha de 10/11: 747 linhas UG
  e 364 da 18A.
- **Cancelados** (status consolidado CANCELADO): entram no total da Visão geral (como o cartão do
  Power BI) e ficam fora das abas Emissões, Progresso, Esforço da engenharia e Histórico, porque
  não vão mais ser emitidos nem aprovados.

### Os filtros

Os oito filtros do alto valem para todas as abas:

- **de linha**: grupo, sistema, escopo, fase, responsável;
- **de documento**: status real, com quem está, situação de emissão.

São **encadeados**: cada lista só oferece os valores que existem dentro dos outros filtros
escolhidos. O rodapé dos filtros mostra quantos documentos e quantas linhas sobraram.

---

## 4. Rastreamento: o Tracking ID de cada documento

O código de um documento pode mudar no Aconex ao longo da vida; o **Tracking ID** não muda. Por
isso o painel acha cada documento pelos códigos da planilha e, achado o Tracking ID, usa o
histórico inteiro dele.

A busca é a mesma da atualização do Doc List (`AconexIndex.resolver`, KB §6):

1. pelo **par** Nº ITAIPU + Nº CMI (os dois com mais de 3 caracteres);
2. se não achar, só pelo **Nº CMI**;
3. se não achar, só pelo **Nº ITAIPU**;
4. se o código levar a mais de um Tracking ID, vale o que teve a **alteração mais recente**.

Para cada documento o painel guarda o Tracking ID, **por qual código foi achado** e se o código
era **ambíguo** (mais de um Tracking ID). O Tracking ID aparece na lista de documentos, no Excel
exportado e na história de cada documento. A **Qualidade dos dados** conta os documentos achados
por um código só e os códigos com mais de um Tracking ID.

Conferência na base de 10/11/2026:

| | Documentos |
|---|---|
| Achados pelo par Itaipu + CMI | 906 |
| Achados só pelo Nº ITAIPU, porque o Aconex não tem Nº CMI para eles | 8 |
| Achados só pelo Nº ITAIPU com o Nº CMI da planilha diferente do do Aconex | 0 |
| Não achados (todos NÃO EMITIDO na planilha) | 178 |
| Código com mais de um Tracking ID | 0 |
| Achados por um código antigo | 0 |
| Dois códigos da planilha no mesmo Tracking ID | 0 |

**O outro código.** Achado o documento, a atualização do Doc List grava na planilha o N° ITAIPU, o
Nº CMI e a descrição da linha Current dele no Aconex (`processar_documento` →
`cod_itaipu_atual`, `cod_cmi_atual`, `descricao_atual`; `_escrever_documento` só grava o que veio
preenchido). Um código antigo ou errado é trocado, e o documento passa a ser achado pelo par. Se o
Aconex não tem o Nº CMI ("Controle do Emissor" vazio), fica o da planilha, e o documento continua
"achado só pelo Nº ITAIPU". O painel marca esse caso (`aconex_sem_cmi`) e a Qualidade dos dados o
separa do Nº CMI diferente. Na base de 10/11/2026, os 8 achados só pelo Nº ITAIPU são todos de
documentos sem Nº CMI no Aconex, em todas as linhas do histórico.

---

## 5. As regras do DocManager que o painel usa

### 5.1 Status real

O status que o Aconex mostra na linha atual muitas vezes não é a situação real do documento
(revisões canceladas, ciclos internos de integração, status de fluxo). O motor do DocManager
(`calcular_status_real`, KB §8) lê o histórico inteiro e decide o status real: Aprovado,
Aprovado com Comentários, Para Assinatura, Informativo, Em Processo, Não Aprovado, Cancelado ou
NÃO EMITIDO. É a coluna STATUS REAL da planilha. O painel chama `processar_documento`, que roda
esse motor sobre a "linha da verdade" (a linha atual, tratadas as revisões terminadas).

### 5.2 Status consolidado e com quem está

- **Status consolidado** (KB §9): agrupa o status real em APROVADO (aprovado, com comentários,
  para assinatura, informativo), EM PROCESSO, NÃO APROVADO, NÃO EMITIDO e CANCELADO.
- **Com quem está** (`calcula_parado_com`): se o status bruto da linha atual é "Em Processo", o
  documento está com a **Itaipu**; qualquer outro, inclusive não emitido, está com a **CMI**. É a
  coluna COM ITAIPU.

### 5.3 Data da 1ª emissão

A 1ª emissão é o primeiro envio do documento à Itaipu (`data_primeira_emissao`, KB §27.5):

- o envio é a linha "Em Processo" do Aconex **a partir de 19/08/2024**; **antes** dessa data, o
  envio aparecia como "Para Análise" (e "Em Processo" era trâmite interno da CMI);
- a revisão que conta é a **0A**; sem 0A (documentos SAT, que entram em revisão alta), a mais
  antiga;
- dentro dela, vale o **envio mais recente** (o reenvio corrigiu o anterior);
- revisões internas de 3 caracteres (0AA) e revisões terminadas não contam.

**Correção feita junto com o painel (versão 3.6.6):** até a 3.6.4 o regime de antes de
19/08/2024 era ignorado, e o documento emitido antes do corte ficava com a data de uma reemissão
posterior, ou sem data. Na planilha de 10/11/2026 eram 16 documentos: quatro apareciam como
EMITIDO COM ATRASO sem estar, e um já aprovado aparecia como PENDENTE VENCIDO (na verdade saiu 5
dias depois da prevista).

### 5.4 Situações e backlog

As mesmas funções que gravam as colunas da planilha (`core/doclist.py`):

| Coluna | Compara a 1ª emissão (ou hoje, se não saiu) com | Quem tem |
|---|---|---|
| Situação de emissão | a data-alvo | todo documento |
| Situação OTD | a data prevista (baseline) | todo documento |
| Situação say-do | a data reprogramada | só o backlog |

Os baldes: **emitido no prazo** (1ª emissão até a data), **emitido com atraso**, **pendente no
prazo** (não saiu e a data não chegou), **pendente vencido**, **sem planejamento** (sem data) e
**cancelado**.

**Backlog**: documento com data reprogramada posterior à prevista que não tinha saído até a
prevista.

**Desvio**: 1ª emissão − data-alvo, em dias (negativo = adiantado).

### 5.5 Aprovação total

A soma dos status reais **Aprovado + Aprovado com Comentários + Para Assinatura + Informativo**
(e For Partial Handover, que só aparece na lista de sobressalentes). O painel mostra cada um e a
soma, como pedido ("manter o status real").

---

## 6. A linha do tempo de cada documento

É a "máquina do tempo" do DocManager (`obter_snapshot_status`, KB §17), aplicada a cada
documento (`linha_do_tempo` em `core/painel_ug.py`):

1. pega todos os dias em que o histórico do documento teve algum evento no Aconex;
2. para cada dia, corta o histórico no fim daquele dia, limpa as revisões terminadas e roda o
   motor de status real **como se o tempo tivesse parado ali**;
3. guarda só os dias em que o status **mudou**. Antes do primeiro evento o documento é NÃO
   EMITIDO.

O resultado é uma lista curta, por exemplo: `05/03 Em Processo → 01/04 Não Aprovado → 10/04 Em
Processo → 30/04 Aprovado com Comentários → 12/05 Aprovado`. Com ela, a página sabe o status de
qualquer documento em qualquer data passada.

**Alinhamento com hoje.** O retrato de hoje vem da linha atual do documento; a máquina do tempo,
da maior versão até a data. Em poucos casos os dois discordam no último evento (4 na base de
10/11). Para o retrato e a evolução darem o mesmo número, a linha do tempo termina no status de
hoje, no dia do último evento.

**Onde é usada:** Progresso (tudo), aprovados da curva, "o que mudou", parte do "antes e depois"
(não aprovados aguardando, documentos que passaram a aprovados) e a faixa de status da história
do documento.

**O que ela não sabe:** as datas de planejamento do passado. O Aconex guarda os status, mas a
data prevista e a reprogramada existem só na planilha de hoje.

### 6.1 O fluxo interno: integração e validação

Antes de ir para a Itaipu, o documento do fornecedor passa pela GE, e o Aconex registra isso com
status próprios, que o status real não enxerga (KB §9: trâmite interno). Pedido da reunião de
13/11/2026: mostrar esse trecho, porque o fornecedor pode estar cumprindo as datas enquanto o
documento fica parado na GE.

| Etapa no painel | Status do Aconex | Onde aparece |
|---|---|---|
| Em integração | "Para Integraçao" (assim, sem til) e "Em Integração" | revisão interna de 3 caracteres (0AA) |
| Integrado / Não integrado | "Integrado" / "Não Integrado" | 0AA |
| Em validação | "Em Validação" | a revisão que vai para a Itaipu (0A, 0B, 0) |
| Validado / Não validado | "Validado" / "Não Validado" | 0A, 0B, 0 |

`fluxo_interno` (`core/painel_ug.py`) lê o histórico do Tracking em ordem de data e versão:
- uma etapa interna começa quando aparece um desses status; a etapa do lado da Itaipu ("Em
  Processo", vereditos, anulação) encerra o fluxo interno até a próxima etapa interna;
- "Para Aprovação" e o "Para Análise" do regime novo (desde 19/08/2024) são trâmite e não mudam a
  etapa;
- **etapa atual** = a última etapa, se o documento ainda não saiu dela para a Itaipu; **desde** =
  o dia em que entrou nela.

Na página: o quadro **Integração e validação** da Visão geral (quantos em cada etapa, a mediana
de dias na etapa, quantos há mais de 30 dias e quantos aparecem como não emitidos no status
real), as colunas **Etapa interna** e **Na etapa desde** nas listas, e a faixa **Interno** na
história do documento.

Na base de 10/11/2026: 209 documentos do Doc List passaram pelo fluxo interno; hoje 93 estão nele
(29 em integração, 3 não integrados, 49 em validação, 12 não validados), 91 deles da NEP, e 54
aparecem como NÃO EMITIDO no status real. Falta a engenharia confirmar quem está com o documento
em cada etapa (GE ou fornecedor).

---

## 7. O histórico de revisões: envios e retornos

Cada revisão do documento vira uma linha com **envio** (a submissão à Itaipu) e **retorno** (o
veredito), como no Histórico Consolidado do DocManager (`gerar_dataset_dashboard` +
`build_wide_table`, KB §18.5 e §24), só para os documentos do Doc List.

### 7.1 Como envio e retorno são escolhidos

- Entram só **Documento Técnico** e **Management Document**, e só status de trâmite com o cliente
  (aprovações, reprovação, informativo, anulação, "Em Processo", "Para Análise", "Para
  Aprovação", "Para Assinatura").
- Saem as revisões terminadas e as **revisões internas** de 3 caracteres (0AA, 0AB).
- **Regime de 19/08/2024**: antes do corte, "Para Análise" é o envio e "Em Processo" é interno;
  depois, "Em Processo" é o envio e "Para Análise" é ignorado.
- **Retorno da revisão** = o último veredito dela; a data é a da **primeira** vez que esse
  veredito apareceu (a repetição do mesmo status é atualização de metadados).
- **Envio da revisão** = o último "Em Processo" até a data do retorno. Um envio depois do último
  retorno vale como ciclo novo em aberto só se for o último evento do documento (relançamento);
  senão, foi uma subida errada corrigida logo depois e é ignorado. "Depois" é data maior ou, no
  mesmo dia, versão maior: "Para Informação" seguido de "Em Processo" no mesmo dia é um envio em
  aberto, não um ciclo fechado com 0 dias (corrigido em 13/11/2026; antes, o "Em análise agora"
  do Histórico de revisões ficava 2 abaixo do "Com quem está" na base de 10/11).
- Revisão sem "Em Processo": o último "Para Aprovação" até o retorno vale como envio (como as
  revisões "0" do início do projeto subiam). Em planilha de comissionamento, "Para Aprovação" é
  retorno ("Para Assinatura"), só se a revisão teve envio.

Uma revisão tem, portanto, **no máximo um envio e um retorno**: reenvios da mesma revisão não
viram envios a mais.

### 7.2 Dias e atrasos (`calcular_atrasos`, KB §24.11)

| Coluna | Conta |
|---|---|
| Dias Itaipu | retorno − envio. Sem retorno: conta até hoje se for o envio mais recente do documento (está com a Itaipu agora); senão fica vazio |
| Atraso Itaipu | o que passou de 30 dias na 0A, ou de 15 nas demais |
| Dias CMI | na 1ª emissão: envio − data-alvo; nas outras: envio − retorno da revisão anterior |
| Atraso CMI | na 1ª emissão: todo dia depois da data-alvo; nas outras: o que passou de 15 dias |

### 7.3 Tipo do envio e retorno anterior

- **1ª emissão**: o primeiro envio do documento;
- **emissão final**: revisão só com números (0, 1...), a revisão para construção;
- **reemissão**: o resto (revisão com letra, depois de comentários ou reprovação).

A página também anota, em cada revisão, o **status do retorno anterior**. "Reemissão depois de
reprovação" é a revisão cujo retorno anterior foi "Não Aprovado".

---

## 8. Cada aba, cada gráfico

Em todas as abas, **clicar** num número, barra, fatia, ponto ou quadro abre a lista dos documentos
correspondentes (seção 9).

### 8.1 Visão geral (a primeira página do Power BI)

| Elemento | O que conta |
|---|---|
| Fluxo dos documentos | Documentos do filtro pelo status real de hoje. **Emitidos** = status real diferente de NÃO EMITIDO, sem cancelados; divididos em aprovados (aprovação total; as folhas são aprovado, com comentários, para assinatura, informativo), em processo e não aprovados. **Não emitidos** divididos pela situação de emissão: pendentes no prazo, vencidos e sem planejamento. Cancelados à parte |
| Aprovação total atual | aprovação total ÷ todos os documentos do filtro (cancelados inclusos no total) |
| Cartões | quantidade por status real e % sobre o total do filtro |
| Documentação geral | barras por status real, maiores primeiro, com quantidade e %. Status fora da lista (For Partial Handover) entram em "Outros" |
| Com quem está o documento | rosca por "com quem está" (ITAIPU ou CMI) |
| Integração e validação | os documentos hoje no fluxo interno (fornecedor → GE, antes da Itaipu), por etapa, com a mediana de dias na etapa; quantos há mais de 30 dias; quantos aparecem como não emitidos no status real (seção 6.1) |
| Documentos de fabricação, executivos, de execução | uma pizza por fase de projeto, pelo status consolidado. Um documento entra na fase de cada linha que ele tem nela (dentro dos filtros) |
| Documentos por escopo | pizza pelo grupo da primeira linha do documento |
| Documentos por grupo e status | barras empilhadas: grupo da primeira linha × status consolidado (as barras somam o total) |
| Documentos por sistema | tabela: para cada sistema, os documentos que têm linha nele (um documento pode contar em vários sistemas); aprovados (aprovação total), em processo, não aprovados, não emitidos, pendentes vencidos e compartilhados (documentos em mais de um sistema) |
| Qualidade dos dados | contagens da planilha (linhas, documentos, códigos repetidos, grupos, sistemas com documentos, sistemas que só aparecem em grupos) e incidências: emitido sem data da 1ª emissão, sem data prevista nem reprogramada, não achados no Aconex, achado só pelo Nº ITAIPU (o Aconex não tem Nº CMI, ou Nº CMI diferente do Aconex), achado só pelo Nº CMI, código com mais de um Tracking ID, documentos compartilhados (o mesmo código em mais de uma linha: conta uma vez, com os dados da 1ª linha) e compartilhados com datas diferentes nas linhas (`datas_divergentes`: DATA PREVISTA ou REPROGRAMADA diferente entre as linhas do código). Cada quadro abre a lista; a coluna Linha mostra todas as linhas da planilha do documento |

### 8.2 Emissões (o "Documentos para emissão" e a "Curva" do Power BI)

**Régua** (escolha no alto):

| Régua | Data usada | Situação usada | Quem entra |
|---|---|---|---|
| Atual | data-alvo | situação de emissão | todos, sem cancelados |
| OTD | data prevista | situação OTD | todos, sem cancelados |
| Say-do | data reprogramada | situação say-do | só o backlog |

**Período**: ano e mês. Abre no **ano corrente**. Com um mês escolhido, as barras ficam **por dia**;
com só o ano, **por mês**. "Agrupar por" força dia, semana, mês, trimestre ou ano. Em "Todos" os
anos, o eixo vai até a data em que 98% dos documentos já estão planejados (as poucas datas muito
distantes, 2034 e 2035, ficam fora, com aviso).

| Elemento | O que conta |
|---|---|
| Cartões | documentos com a data da régua no período, por situação |
| Indicador do período | (documentos do período − atrasados) ÷ documentos do período. Atrasados = emitidos com atraso + pendentes vencidos. O que ainda não venceu conta como cumprido. Na régua OTD é o Baseline OTD; na Say-do, o Say-do; na Atual, a aderência à data-alvo |
| Status das emissões | barras empilhadas por período e situação; o número em cima é o total do período; a linha tracejada marca hoje |
| Curva de emissão e aprovação | acumulado **desde o início do projeto**, por mês (por semana com um ano escolhido, por dia com um mês): **planejado** = documentos com data-alvo até o fim do período; **baseline** (opcional) = com data prevista até o fim do período; **emitidos** = com 1ª emissão até o fim do período (ou até hoje); **aprovados** = documentos com status de aprovação no fim do período, pela linha do tempo. Adiantar dá crédito: em qualquer data, emitidos − planejado = adiantados − atrasados. O ponto do período atual soma o período inteiro do planejado; a nota embaixo dá os números exatos até hoje |
| Próximas emissões e vencidos | documentos não emitidos com data-alvo vencida, ou que vence nos próximos 30 ou 90 dias, em ordem de data; "dias" negativo = já venceu |

### 8.3 Progresso (a tendência, no modelo da aba Progresso da Sala Segura)

Tudo aqui vem da **linha do tempo** (seção 6), sem cancelados.

- **Data de referência**: 1 semana, 2 semanas, 1 mês (padrão), 3 meses atrás, início do ano ou
  outra data.
- **Cartões**: status de hoje e a variação contra a data de referência. Verde é bom, vermelho é
  ruim: mais aprovados é bom; mais não aprovados é ruim; em processo é neutro (cinza). Emitidos =
  documentos com 1ª emissão até a data.
- **Resumo em palavras**, na janela entre a data de referência e hoje:
  - aprovação total no começo e no fim, em quantidade e em %;
  - envios à Itaipu da janela por tipo (1ª emissão, reemissão, emissão final);
  - retornos da janela: aprovações (aprovado, com comentários, para assinatura, informativo) e
    reprovações;
  - não aprovados e em processo no começo e no fim;
  - ritmo médio = variação da aprovação total ÷ semanas da janela.
- **Evolução de cada status** (até 13/11/2026 se chamava "Tendência entre as datas"): quantos
  documentos estavam em cada status no fim de cada semana (janelas de 3 e 6 meses) ou de cada mês (12
  meses e tudo). A linha tracejada é a aprovação total. A "tendência" é a direção das linhas, não uma
  projeção; a janela termina hoje e não depende da data de comparação do alto da aba.
- **Evolução da carteira**: mês a mês desde o primeiro evento: aprovação total, em processo, não
  aprovados e não emitidos, empilhados até o total.
- **Histórico por data**: os pontos de "Evolução de cada status" em tabela (do mais recente para o mais antigo).
- **O que mudou desde a data**:

| Grupo | Documentos |
|---|---|
| Novas aprovações | aprovados hoje que não estavam aprovados na data |
| Novas reprovações | não aprovados hoje que não estavam não aprovados na data |
| Novas 1ªs emissões | 1ª emissão depois da data |
| Entraram em análise na Itaipu | em processo hoje que não estavam em processo na data |
| Saíram de aprovado | aprovados na data que não estão aprovados hoje (por exemplo, revisão nova depois da aprovação) |

### 8.4 Esforço da engenharia

Sem cancelados. **Período**: ano escolhido, ou tudo até hoje; agrupado por semana, mês ou
trimestre.

| Elemento | O que conta |
|---|---|
| Envios à Itaipu, 1ªs emissões, reemissões, emissões finais | revisões com envio no período, por tipo (seção 7.3) |
| Documentos trabalhados | documentos com pelo menos um envio no período |
| Retornos da Itaipu | revisões com retorno no período |
| Aprovados de primeira | entre os documentos que já tiveram algum retorno, os que tiveram aprovação no **primeiro** retorno (todo o histórico) |
| Revisões até aprovar (média) | para os documentos aprovados: quantas revisões com envio até a primeira aprovação, em média |
| Antes e depois de uma data | ver abaixo |
| Envios à Itaipu por período | barras empilhadas por tipo do envio, pela data do envio |
| Retornos da Itaipu por período | barras empilhadas pelo status do retorno, pela data do retorno |
| Prazo de reemissão da CMI | por período do envio: das reemissões depois de reprovação, a parte enviada em até 15 dias; o tooltip dá "x de n" e a mediana de dias (seção 18) |
| Prazo de análise da Itaipu | por período do retorno: a parte dos retornos dentro do prazo (30 dias na 0A, 15 nas demais); o tooltip dá "x de n" e a mediana de dias (seção 18) |
| Taxa de aprovação dos retornos | por período do retorno: aprovados ÷ (aprovados + não aprovados); o tooltip dá "x de n" (seção 18). Nos três gráficos de %, período com menos de 10 casos (5 na semana) não vira ponto, e os três começam no mesmo período |
| Em que revisão o documento foi aprovado | para cada documento aprovado, a revisão do primeiro retorno de aprovação: 0A, 0B, 0C, 0D, "0E+" (as letras seguintes), revisão numérica, ou "1x" para outras famílias |
| Há quanto tempo está com a Itaipu | documentos em processo: dias desde o último envio, em faixas (até 15, 16 a 30, 31 a 60, mais de 60) |
| Há quanto tempo espera reemissão da CMI | documentos não aprovados: dias desde o último retorno, nas mesmas faixas |
| Envios por responsável | os 15 responsáveis (COE/VENDOR da primeira linha do documento) com mais envios no período, por tipo |

**Antes e depois de uma data.** Duas janelas de mesma duração: **depois** = da data de corte até
hoje; **antes** = o mesmo número de dias antes da data de corte. A data de corte padrão é o 1º dia
de três meses atrás. Contagens viram **média por mês** (× 30,4 ÷ dias da janela).

| Linha | Conta |
|---|---|
| Reemissões, 1ªs emissões e emissões finais (por mês) | envios da janela, por tipo |
| Retornos aprovados (por mês) | retornos de aprovação na janela |
| Taxa de aprovação dos retornos | aprovados ÷ (aprovados + não aprovados), na janela |
| Documentos que passaram a aprovados (por mês) | aprovação total no fim da janela − no começo, pela linha do tempo |
| Dias para reemitir depois da reprovação (mediana) | Dias CMI das revisões enviadas na janela cujo retorno anterior foi "Não Aprovado" |
| Reemitidos em até 15 dias | dessas, a parte com Dias CMI ≤ 15 |
| Dias de análise da Itaipu (mediana) e Itaipu no prazo | retornos da janela |
| Não aprovados aguardando reemissão | documentos não aprovados no fim de cada janela |

A coluna "Variação" fica verde quando melhorou e vermelha quando piorou (menos dias é melhor; mais
reemissões, aprovações e % no prazo é melhor; menos não aprovados aguardando é melhor). Quando a
equipe reemite documentos parados há muito tempo, a mediana de dias para reemitir sobe mesmo com
melhora: por isso ela deve ser lida junto com os não aprovados aguardando.

### 8.5 Histórico de revisões

| Elemento | O que conta |
|---|---|
| Revisões (ciclos) | revisões dos documentos do filtro (seção 7) |
| Em análise agora | revisões com envio, sem retorno, ainda contando dias (o envio mais recente do documento) |
| Dias Itaipu (média e mediana), Itaipu no prazo | revisões com retorno; no prazo = Atraso Itaipu zero |
| Dias CMI p/ reemitir (média e mediana), CMI no prazo | revisões que não são a 1ª emissão e têm Dias CMI; no prazo = Atraso CMI zero |
| Tabela | uma linha por revisão (Nº ITAIPU, Tracking ID, descrição, grupo, sistema, fase, revisão, tipo, envio, retorno, status do retorno, SLA, dias e atrasos). Documento não emitido entra com uma linha só, com o Atraso CMI contando desde a data-alvo (0 se a data-alvo não chegou). Filtros: só sem retorno, só com atraso da Itaipu, só com atraso da CMI. Mostra até 1.200 linhas; o Excel leva todas |

**História do documento** (clique em qualquer documento de qualquer lista):

- cabeçalho com Nº ITAIPU (e o código atual, se mudou), Nº CMI, Tracking ID, status real,
  situação de emissão, descrição, grupo, sistemas, fase, responsável, datas e desvio;
- **linha do tempo** desenhada a partir dos dados das seções 6 e 7: no alto, a data prevista (◆) e
  a reprogramada (○) e a linha de hoje; uma faixa por revisão, onde a **barra grossa** vai do envio
  ao retorno (o tempo com a Itaipu), na cor do retorno (âmbar se ainda sem retorno), com o veredito
  e os dias; a **barra fina** vai do retorno ao envio seguinte (o tempo com a CMI), vermelha depois
  de reprovação; embaixo, a **faixa de status real** ao longo do tempo;
- a tabela das revisões do documento.

---

## 9. Listas, Excel, idioma e ajuda

- **Listas**: o clique em qualquer elemento abre, embaixo, a lista dos documentos (ou das revisões,
  nos gráficos de envios e retornos), com busca por qualquer coluna. A lista de documentos tem 23
  colunas, entre elas Nº ITAIPU, Nº CMI, Tracking ID, status, situações, datas, revisão, desvio e a
  linha da planilha.
- **Exportar Excel**: grava um .xlsx com a lista filtrada pela busca: uma aba, cabeçalho com filtro
  e congelado, datas como data do Excel. O arquivo é escrito pela própria página, sem biblioteca.
- **Idioma**: o botão do alto troca entre português e inglês; os nomes de status também são
  traduzidos.
- **Ajuda**: o botão **📘 Como ler o painel** e o **i** de cada gráfico abrem as explicações
  (lista `AJUDA` no modelo).

---

## 10. Como o arquivo é montado

1. **Leitura** (`services/painel_ug.py`): as linhas do Doc List na ordem da planilha
   (`ler_linhas_doclist`) e a base do Aconex como texto (`carregar_base_aconex`).
2. **Cálculo** (`core/painel_ug.py`, `montar_dados_painel`): para cada documento, rastreamento,
   retrato de hoje, linha do tempo e revisões. Leva cerca de 1 minuto na base real: a parte mais
   pesada é a máquina do tempo, que roda o motor de status em cada dia com evento.
3. **Página** (`dashboard/painel_ug_html.py`, `renderizar`):
   - lê o modelo `dashboard/recursos/painel_ug.html`;
   - embute as bibliotecas de gráfico **Chart.js 4.4.4** e **chartjs-plugin-datalabels 2.2.0**
     (licença MIT, com o cabeçalho de licença), para o arquivo abrir sem internet (a rede
     corporativa pode bloquear sites de bibliotecas);
   - converte os dados para listas compactas (`compactar`): a **ordem dos campos** é o contrato com
     o JavaScript, travada por teste;
   - protege o texto contra `</script>` dentro dos dados (uma descrição com isso quebraria a página).
4. **Gravação**: o arquivo vai para onde a pessoa escolher; a pasta fica lembrada. Tamanho: cerca de
   1,3 MB.
5. **Na tela do DocManager** (`ui/views/doclist_view.py`): o botão roda tudo numa tarefa com barra de
   progresso e, no fim, abre o arquivo no navegador.

---

## 11. Onde está cada coisa no código

| Arquivo | O que faz |
|---|---|
| `docmanager/core/painel_ug.py` | Regras do painel: `escopo_da_linha`, `chave_documento`, `tipo_de_envio`, `linha_do_tempo`, `historico_de_revisoes`, `montar_dados_painel` |
| `docmanager/dashboard/painel_ug_html.py` | `compactar` (dados → listas) e `renderizar` (modelo + bibliotecas + dados) |
| `docmanager/dashboard/recursos/painel_ug.html` | A página: estilo, textos, filtros, abas, gráficos, listas, Excel, ajuda |
| `docmanager/dashboard/recursos/chart.umd.js`, `chartjs-plugin-datalabels.min.js` | Bibliotecas de gráfico embutidas |
| `docmanager/services/painel_ug.py` | `gerar_painel_ug`: lê, calcula, desenha e grava |
| `docmanager/doclist_backend.py` | Expõe `gerar_painel_ug` para a tela |
| `docmanager/ui/views/doclist_view.py` | Botão Gerar Painel HTML |
| `docmanager.spec` | Leva `dashboard/recursos` para dentro do executável |
| Já existentes, reaproveitados | `core/identity.py` (rastreamento), `core/mapping.py` (`processar_documento`), `core/status_engine.py` (status real), `core/consolidation.py`, `core/kpis.py` (1ª emissão), `core/doclist.py` (situações), `core/snapshots.py` (máquina do tempo), `core/wide.py` (envios e retornos), `core/delays.py` (dias e atrasos) |

---

## 12. Testes

`pytest` roda a suíte inteira (no CI do Linux também). Os do painel:

| Teste | Garante |
|---|---|
| `tests/test_painel_ug.py` | escopo UG/18A; tipo do envio; linha do tempo só com mudanças e terminando no status de hoje; um código conta uma vez e as linhas viram associações; retrato de hoje igual ao da atualização da planilha (status, 1ª emissão, situações, backlog); histórico de revisões com dias, atrasos e tipo; Dias CMI da 1ª emissão contra a data-alvo; rastreamento (por qual código, ambíguo); a página é um arquivo só, sem nada da internet; descrição com `</script>` não quebra a página; ordem dos campos (o contrato com o JavaScript); geração de ponta a ponta com planilha e base de teste; planilha sem documentos avisa e não grava |
| `tests/test_ui_telas.py` | o botão do Doc List gera o arquivo e abre o navegador |
| `tests/test_empacotamento.py` | os recursos do painel vão para o executável |
| `tests/test_doclist.py` | a regra da 1ª emissão com o corte de 19/08/2024 |

Os testes usam planilhas e históricos fabricados, nunca dados reais. A conferência com a base real
foi feita à parte (seções 2 e 4) e nenhum código de documento entrou no repositório.

---

## 13. Atualizar o painel e lançar a versão

**No dia a dia:**

1. Baixe a base do dia (Extração Aconex, ou o histórico diário).
2. No Doc List Mapping, escolha a base e a planilha e rode **Iniciar Atualização**.
3. Clique em **Gerar Painel HTML** e salve no Box. O mesmo nome sempre (por exemplo
   `Painel UG.html`) substitui o anterior; com a data no nome, guarda o histórico.
4. Quem consulta abre o arquivo no navegador, sem o DocManager.

**Lançar a versão:** o botão chega a todos com a versão 3.7.0. É preciso levar a branch do painel
para a main, pôr a data nos blocos 3.6.6 e 3.7.0 do CHANGELOG e criar a tag; o GitHub Actions monta o
instalador e o DocManager se atualiza sozinho (ver `BUILD.md`). A correção da 1ª emissão (3.6.6)
está num commit separado. A 3.6.5 é a correção de Pendências (fórmula de contagem em A2), feita em
outra branch e trazida para esta, para a 3.7.0 levar as duas. Para testar antes, a versão de teste
(pré-lançamento, por exemplo 3.7.0-rc.1) sai pelo Release do GitHub disparado à mão na branch e fica
na página de Releases; os DocManager instalados não a recebem sozinhos.

---

## 14. Mudar um texto

- **Textos do painel** (títulos, notas, botões): em `docmanager/dashboard/recursos/painel_ug.html`,
  cada texto aparece em português dentro de `T("...")`. A versão em inglês está na lista `EN`, no
  começo do script, com o texto em português como chave: ao mudar um texto, mude também a chave,
  senão o inglês passa a mostrar o português.
- **Explicações do 📘 e do i**: no mesmo arquivo, a lista `AJUDA`; cada item tem o id, a aba, o
  título e o texto em português e o título e o texto em inglês.
- **Textos da tela do DocManager** (botão, quadro): `docmanager/ui/views/doclist_view.py`, com as
  traduções em `docmanager/ui/recursos/idiomas/es.json` e `en.json`;
  `python tools/textos_da_interface.py --faltando es` lista o que faltar.

Depois de mudar, gere o painel de novo (o arquivo leva o modelo do momento em que é gerado) e rode
`pytest tests/test_painel_ug.py`.

---

## 15. Decisões tomadas e por quê

| Decisão | Por quê |
|---|---|
| HTML gerado pelo DocManager, não um HTML que lê o Excel no navegador | As regras (status real, 1ª emissão, máquina do tempo) já estão testadas em Python; refazer em JavaScript criaria uma segunda versão que divergiria. "Pelo menos por enquanto" (ADR 0003) |
| Família visual do painel da Sala Segura e RTA | O pessoal já conhece e gostou: cabeçalho, abas, árvore de fluxo, cartões clicáveis, listas com Excel, aba Progresso |
| Manter todas as visões da 1ª página do Power BI, pizzas como pizza, com os filtros de ano e mês | Pedido do usuário depois do primeiro protótipo |
| Data-alvo como meta principal, baseline opcional | Pedido do usuário; a baseline mostra o que a reprogramação esconde |
| Mostrar o status real (não só o consolidado) | Pedido do usuário; a aprovação total é a soma |
| "Tendência" como conceito, sem projeção matemática | Pedido do usuário: ver como as aprovações evoluem, não uma reta projetada |
| Adiantar dá crédito na curva acumulada | Decisão do usuário: "o acumulado é isso" |
| Histórico de revisões como o módulo Histórico do DocManager, só com os documentos do Doc List | Pedido do usuário (não o dashboard antigo do app) |
| Português com botão inglês, sem espanhol | Pedido do usuário |
| UG e 18A juntos, com filtro | Pedido do usuário |
| Arquivo único, bibliotecas embutidas | Abre sem internet, pode ficar no Box, a rede corporativa pode bloquear sites de bibliotecas |
| Corrigir a 1ª emissão antes de 19/08/2024 | Achado durante o painel; aprovado pelo usuário |

---

## 16. Diferença para o Power BI

As fórmulas do `Dashboard - Doc List Mapping.pbix` (extraídas do arquivo) fazem a curva de um jeito
diferente do painel:

- **Previstos Acum** conta pela data-alvo (ou pela prevista, no botão OTD), mas **só dentro do
  período escolhido** (`ALLSELECTED`): a curva recomeça do zero no início do período.
- **Emitidos Acum** só conta documentos com data-alvo dentro do período e, para os que já passaram
  da 1ª revisão e saíram antes da data-alvo, conta o documento **na data-alvo**, não no dia em que
  saiu (439 dos 858 emitidos).

No período inteiro, em 10/11/2026: Power BI 845 previstos × 826 emitidos; painel 840 × 853. O painel
conta cada documento no dia em que realmente saiu, acumulando desde o início do projeto.

---

## 17. Limites conhecidos

- **O plano do passado não existe**: a data-alvo de uma data passada não é conhecida (só as datas da
  planilha de hoje). A baseline é estável, então o OTD de meses passados se reconstrói; a
  reprogramação, não. Proposta em aberto: guardar as datas da planilha a cada geração.
- **Um envio e um retorno por revisão**: reenvios dentro da mesma revisão não contam como esforço a
  mais, e retornos intermediários se perdem (fica o último veredito).
- **Foto do dia**: o arquivo não se atualiza sozinho; é preciso gerar de novo.
- **Total da Visão geral inclui os cancelados** (como o cartão do Power BI): o % de aprovação total de
  lá (672 ÷ 1.092 = 61,5%) é um pouco menor que o do Progresso (672 ÷ 1.086 = 61,9%), que exclui os
  cancelados.
- **O ponto do período atual na curva** soma o período inteiro do planejado; a nota embaixo do gráfico
  dá os números exatos até hoje.
- **Datas previstas muito antes da 1ª emissão**: 330 documentos saíram mais de 30 dias antes da data
  prevista (116, mais de 6 meses), e boa parte dessas datas coincide com eventos posteriores (outro
  envio, um retorno da Itaipu). Até 29/10/2026 o Controle sobrescrevia a data prevista a cada
  atualização (ADR 0001), então a "baseline" de parte dos documentos é o plano de outubro, não o
  original.
- **Geração leva cerca de 1 minuto** na base real.

---

## 18. Os três gráficos de % do Esforço: a matemática e como ler

**Prazo de reemissão da CMI**, **Prazo de análise da Itaipu** e **Taxa de aprovação dos retornos**
fazem a mesma conta: uma **proporção por período**. Cada ponto é "quantos casos atenderam a
condição" ÷ "quantos casos houve no período", × 100. Muda só quem é um caso, qual é a condição e
qual data põe o caso num período. Os números de exemplo são da base de 10/11/2026.

### 18.1 A conta comum

Para um período *P* (semana, mês ou trimestre, no agrupamento da aba):

```
casos(P) = as revisões que caem em P, pela data de cada gráfico (tabela abaixo)
bons(P)  = os casos que atendem a condição
ponto(P) = 100 × bons(P) ÷ casos(P)       só se casos(P) ≥ 10 (≥ 5 na semana)
```

| Gráfico | Quem é um caso | Que data põe o caso no período | Condição ("bom") | Dias |
|---|---|---|---|---|
| Prazo de reemissão da CMI | revisão enviada depois de uma revisão **Não Aprovada** | o **envio** da nova revisão | Dias CMI ≤ 15 | Dias CMI = envio da revisão − retorno (reprovação) da revisão anterior |
| Prazo de análise da Itaipu | revisão que **voltou** da Itaipu | o **retorno** | Dias Itaipu ≤ prazo: 30 na 0A, 15 nas demais | Dias Itaipu = retorno − envio |
| Taxa de aprovação dos retornos | revisão que voltou como **aprovação ou reprovação** | o **retorno** | o retorno foi aprovação | — |

- Os dias são **corridos** (fins de semana e feriados contam), como no Histórico Consolidado (seção 7.2).
- **Aprovação** = Aprovado, Aprovado com Comentários, Para Assinatura, Informativo e For Partial
  Handover (a aprovação total, seção 5.5). **Reprovação** = Não Aprovado. Cancelado e anulado não
  entram em cima nem embaixo.
- Um documento aparece em vários períodos, uma vez por revisão.
- O **tooltip** mostra o ponto, "x de n" e a mediana de dias (na taxa, quantos não aprovados).
  **Clicar** no ponto abre as revisões do período, com revisão, prazo (SLA), Dias e Atraso da Itaipu
  e da CMI, e exporta para Excel.
- Período com menos de 10 casos (5 na semana) não vira ponto (seção 18.3). Os três gráficos começam
  no mesmo período, o primeiro que tem ponto em algum deles, para comparar um com o outro.

No código: `pintarEsforco` em `docmanager/dashboard/recursos/painel_ug.html` (as listas `rp`,
`posRep` e `retP`, o mínimo `MIN`); os dias vêm de `calcular_atrasos` (`docmanager/core/delays.py`).

### 18.2 A mediana

A **mediana** é o valor do meio quando os valores são postos em ordem: metade dos casos levou
menos, metade levou mais. Com um número par de valores, é a média dos dois do meio. O painel usa a
mediana, e não a média, porque poucos valores extremos (um documento parado há um ano) puxam a média
para longe do caso típico; a mediana não se mexe com eles.

### 18.3 Exemplo: outubro de 2026

**Prazo de reemissão da CMI.** Em outubro, a CMI enviou 35 revisões depois de reprovação. Os dias
de cada uma (envio − reprovação anterior), em ordem:

> 1, 3, 6, 6, 17, 19, 26, 26, 34, 36, 36, 37, 39, 42, 47, 50, 61, **61**, 70, 70, 82, 93, 118,
> 130, 133, 202, 235, 294, 308, 388, 505, 505, 505, 505, 516

- Em até 15 dias: 1, 3, 6 e 6, ou seja **4**. Ponto = 100 × 4 ÷ 35 = **11,4%**.
- Mediana: com 35 valores, o do meio é o 18º, **61 dias**.
- Média: 5.206 ÷ 35 = **148,7 dias**, mais que o dobro da mediana. As cinco revisões de 505 e 516
  dias (cinco documentos reprovados entre maio e junho de 2025 e reenviados juntos em 20/10/2026)
  puxam a média; a mediana não liga para elas.
- 14 das 35 (40%) esperavam havia mais de 90 dias: outubro foi, em boa parte, **limpeza de
  antigos**. É trabalho bom, mas derruba o % e sobe a mediana (seção 18.6).

**Prazo de análise da Itaipu.** Em outubro voltaram 141 revisões:

| | Retornos | Em até 15 dias | 16 a 30 dias | Mais de 30 | No prazo |
|---|---|---|---|---|---|
| 0A (prazo de 30 dias) | 21 | 3 | 9 | 9 | 3 + 9 = **12** |
| Demais revisões (prazo de 15) | 120 | 43 | 54 | 23 | **43** |
| Total | 141 | 46 | 63 | 32 | **55** |

- Ponto = 100 × 55 ÷ 141 = **39,0%**. Mediana: o 71º de 141 valores, **22 dias**.
- Leitura: 54 revisões que não eram 0A (90 das 120 eram reemissões) voltaram entre 16 e 30 dias:
  atrasadas para o prazo de 15, mas em menos de 30. Se o prazo de todas fosse 30 dias, o ponto seria
  (12 + 43 + 54) ÷ 141 = 77%. O que puxa o % para baixo é o prazo de 15 dias das revisões depois da
  0A, mais do que análises muito longas (só 1 passou de 60 dias).

**Taxa de aprovação dos retornos.** Em outubro, 139 revisões voltaram como aprovação ou reprovação:
109 aprovações (Para Assinatura 42, Aprovado com Comentários 41, Aprovado 23, For Partial Handover
2, Informativo 1) e 30 Não Aprovado.

- Ponto = 100 × 109 ÷ 139 = **78,4%**.
- 28 das 109 aprovações foram de **emissão final** (revisão só com números). As 30 reprovações foram
  todas de revisões com letra. Só nas revisões com letra, a taxa é 81 ÷ 111 = 73,0%.

### 18.4 Por que poucos casos enganam

Cada caso vale **100 ÷ n** pontos percentuais. Com n = 3, um documento a mais ou a menos muda o ponto
em 33 pontos; com n = 10, em 10; com n = 141, em 0,7. Por isso os meses de 2023 e 2024, quase sempre
com 1 a 4 reemissões depois de reprovação, pulavam entre 0% e 100%. O painel só desenha o ponto com
10 casos ou mais (5 na semana, que tem cerca de um quarto dos casos do mês).

Para saber se uma diferença entre dois pontos é real, use a variação que uma proporção *p* com *n*
casos tem por acaso, cerca de **± 2 × √(p × (1 − p) ÷ n)** (o intervalo de 95%, aproximado):

| Ponto de outubro de 2026 | p | n | Varia por acaso cerca de |
|---|---|---|---|
| Taxa de aprovação | 78,4% | 139 | ± 7 pontos |
| Itaipu no prazo | 39,0% | 141 | ± 8 pontos |
| Reemissão em até 15 dias | 11,4% | 35 | ± 11 pontos |

Exemplo: √(0,784 × 0,216 ÷ 139) = √0,00122 = 0,035; × 2 = 0,07 = 7 pontos. Então uma taxa de 72%
num mês depois de 78% no outro não é piora; três meses seguidos abaixo de 72%, sim. É uma
aproximação: serve para não tirar conclusão de um mês só.

### 18.5 A tendência: por trimestre

No agrupamento **trimestre**, cada ponto junta cerca de três vezes mais casos, e a variação por acaso
cai quase pela metade (√3 ≈ 1,7). Os três por trimestre (o 4º trimestre de 2026 vai até a data da
base):

| Trimestre | Reemissão em até 15 dias | Mediana para reemitir | Itaipu no prazo | Mediana da Itaipu | Taxa de aprovação |
|---|---|---|---|---|---|
| 2025 T1 | 7 de 32 = 21,9% | 47,5 dias | 50 de 119 = 42,0% | 27 dias | 63 de 119 = 52,9% |
| 2025 T2 | 5 de 62 = 8,1% | 42,5 | 115 de 226 = 50,9% | 24 | 147 de 226 = 65,0% |
| 2025 T3 | 5 de 68 = 7,4% | 57,5 | 130 de 300 = 43,3% | 20 | 214 de 300 = 71,3% |
| 2025 T4 | 4 de 74 = 5,4% | 40,5 | 116 de 307 = 37,8% | 23 | 202 de 307 = 65,8% |
| 2026 T1 | 6 de 98 = 6,1% | 49,5 | 138 de 349 = 39,5% | 27 | 229 de 349 = 65,6% |
| 2026 T2 | 10 de 102 = 9,8% | 51,5 | 158 de 409 = 38,6% | 24 | 304 de 409 = 74,3% |
| 2026 T3 | 10 de 87 = 11,5% | 57 | 136 de 389 = 35,0% | 21 | 316 de 390 = 81,0% |
| 2026 T4 (parcial) | 4 de 49 = 8,2% | 70 | 67 de 168 = 39,9% | 22 | 131 de 166 = 78,9% |

O que a tabela diz:

- **A taxa de aprovação subiu de verdade**: de 65% a 66% (2025 T4 e 2026 T1) para 74% (2026 T2) e
  81% (2026 T3). Com cerca de 400 casos por trimestre, o acaso explica ± 4 a 5 pontos; a subida foi
  de 15.
- **A Itaipu cumpre o prazo em cerca de 4 de cada 10 análises** em 2026, menos que os 51% de 2025 T2.
  A queda aparece nos dois grupos (0A: 54% → 36%; demais: 48% → 35%, de 2025 T2 para 2026 T3). A
  mediana ficou entre 20 e 27 dias: acima dos 15 dias das revisões depois da 0A (reemissões e
  emissões finais), que são a maior parte dos retornos (83% em 2026 T3).
- **A reemissão em até 15 dias é baixa o tempo todo** (5% a 12% por trimestre; os 21,9% de 2025 T1
  têm só 32 casos). A subida para 10% a 11% em 2026 T2 e T3 está dentro do acaso (± 6 pontos com
  cerca de 100 casos). A mediana subiu para 57 e 70 dias porque a equipe passou a reemitir
  documentos antigos. Se a fila está andando, quem diz são os não aprovados aguardando (124 → 107 no
  Antes e depois com corte em 01/08/2026) e a fatia vermelha de "Há quanto tempo espera reemissão da
  CMI".

### 18.6 Armadilhas de leitura

1. **Cada gráfico tem a sua data.** Reemissão conta no mês do envio; Itaipu e taxa, no mês do
   retorno. Uma revisão enviada em setembro e devolvida em outubro conta em outubro nos dois últimos.
2. **Só entra quem já andou.** O documento reprovado que ainda não foi reemitido não está no gráfico
   de reemissão; o que está em análise não está no da Itaipu. Se a equipe deixa os difíceis parados e
   só reemite os fáceis, o % sobe e a fila cresce. Leia sempre com as pizzas "Há quanto tempo".
3. **Limpar antigos piora o mês.** Reemitir um documento parado há 500 dias é bom, mas entra como um
   caso fora do prazo e sobe a mediana.
4. **A taxa conta revisões, não documentos.** Um documento reprovado três vezes pesa três vezes, e a
   emissão final volta como aprovação. Para documentos, use **Aprovados de primeira** (381 de 820 =
   46,5% dos documentos que já tiveram retorno) e **Em que revisão o documento foi aprovado** (0A em
   377 dos 686 aprovados = 55,0%). As bases são diferentes (820 com retorno; 686 aprovados), por isso
   46,5% e 55,0% não se contradizem.
5. **O mês corrente está incompleto.** Novembro de 2026 tinha só os primeiros dias: 14 reemissões,
   nenhuma em até 15 dias, mediana de 135 dias. Poucos casos e quase todos antigos: espere o mês
   fechar.
6. **Um pico não é tendência.** Compare com a variação por acaso (seção 18.4) ou mude o agrupamento
   para trimestre.
