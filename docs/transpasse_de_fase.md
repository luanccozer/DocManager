# Transpasse de Fase — como o painel funciona

> Módulo do DocManager desde a **3.4.0**. Desenha sozinho, a partir das
> planilhas de acompanhamento, o quadro de cores por dia que a equipe pintava à
> mão (a "Planilha1"). Regras em `docmanager/core/transpasse.py`; leitura das
> planilhas em `docmanager/services/transpasse_io.py`; página em
> `docmanager/dashboard/transpasse_html.py`; testes em `tests/test_transpasse.py`.

## Índice

1. [Para que serve](#1-para-que-serve)
2. [Como usar no DocManager](#2-como-usar-no-docmanager)
3. [De onde vêm os dados](#3-de-onde-vêm-os-dados)
4. [Como ler o quadro](#4-como-ler-o-quadro)
5. [A coluna "Dias"](#5-a-coluna-dias)
6. [O card (passar o mouse)](#6-o-card-passar-o-mouse)
7. [Datas que ficam fora do quadro](#7-datas-que-ficam-fora-do-quadro)

---

## 1. Para que serve

Cada grupo de equipamentos passa por cinco marcos até o comissionamento
começar. Cada etapa entre um marco e o seguinte tem prazo, e o quadro mostra,
dia a dia, onde cada grupo gastou o tempo:

| Marco | Cor | O que é |
|---|---|---|
| Convocação | 🟥 vermelho | data de convocação IB para a inspeção conjunta |
| Inspeção IB | 🟧 laranja | data da inspeção efetivamente realizada pela IB |
| Emissão CCMLC | 🟦 azul | data de emissão do CCMLC |
| Transpasse de fase | 🟩 verde | data do transpasse de fase (CCMLC emitido via Unifier) |
| Início do comissionamento | ⬛ preto | quando o time de manutenção chega no local para executar |

As cores e o texto da legenda são **os mesmos da planilha da equipe**
(vermelho `#FF0000`, laranja `#FFC000`, azul `#00B0F0`, verde `#92D050`,
preto `#000000`).

Antes, a grade era pintada à mão, célula por célula. Isso tinha três
problemas:

- **Erros de pintura:** dia trocado e mês errado passavam despercebidos.
- **Mês novo:** cada mês exigia criar colunas à mão.
- **Grupo parado:** aparecia só como uma célula no dia da convocação, então o
  tempo de espera não ficava visível.

O painel resolve os três, porque é desenhado direto das datas.

## 2. Como usar no DocManager

1. Abra **Transpasse de Fase** na barra lateral.
2. **Acompanhamento do transpasse** (obrigatória): escolha a planilha de
   acompanhamento do transpasse. Não precisa escolher aba: o app acha a aba
   certa sozinho.
3. **Planilha complementar** (opcional): escolha a planilha de controle do
   início do comissionamento. Sem ela o painel sai igual, só sem o preto e sem
   a coluna "Dias".
4. Clique em **Gerar e Abrir Painel**, escolha onde salvar o `.html` e pronto:
   ele abre no navegador.

O arquivo gerado é uma página única, sem nada da internet. Abre com dois cliques
em qualquer navegador e pode ser enviada por e-mail ou deixada numa pasta
compartilhada para quem não tem o DocManager. Para atualizar depois que alguém
mexer nas planilhas, é só gerar de novo.

O **Registro de execução** da tela diz quantos grupos foram lidos de cada
planilha e quantos têm datas a conferir.

## 3. De onde vêm os dados

### 3.1 Planilha principal — acompanhamento do transpasse (obrigatória)

O app procura, em todas as abas, a que tem a coluna **ID GRUPO EQUIPAMENTOS**.
Nela, lê:

| Coluna da planilha | Uso |
|---|---|
| ID GRUPO EQUIPAMENTOS | código do grupo (ex.: GEQ-001-002) |
| CAPÍTULO | sala — cada sala é um bloco do quadro |
| GRUPO EQUIPAMENTOS | nome do grupo, mostrado no card |
| CONVOCAÇÃO CONJUNTA REALIZADA EM | 🟥 convocação |
| DATA INSPEÇÃO REALIZADA CMI/ITAIPU | 🟧 inspeção IB |
| DATA EMISSÃO CCMLC | 🟦 emissão do CCMLC |
| DATA TRANSPASSE FASE | 🟩 transpasse de fase |

As colunas são achadas **pelo título**, não pela letra. Inserir ou mover
colunas não desalinha nada. Se faltar uma dessas colunas, o app diz qual
falta e não gera o painel.

A principal **manda na lista de grupos**: código, sala, nome e ordem saem dela.

### 3.2 Planilha complementar — controle do início do comissionamento (opcional)

Uma aba por sala. Cada grupo ocupa duas linhas: **Prevista** e **Realizada**.
O app lê **só a Realizada**, com estas colunas:

- Convocação Inspeção IB
- Inspeção IB
- Emissão CCMLC
- Transpasse de fase
- Início do Comissionamento

O que ela acrescenta:

- **O início do comissionamento (preto).** A principal não tem essa coluna, e
  é dele que sai a coluna "Dias".
- **Datas que faltam na principal.** Quando a principal está vazia num marco e
  a complementar tem a data, vale a da complementar.
- **Grupos que a principal não tem.** Entram no bloco da sala equivalente
  (a aba "60HZ" da complementar é a "SALA SEGURA 60 Hz" da principal).

A complementar não tem código de grupo, só o número (1, 2, 3...): **o grupo N
é o GEQ-001-NNN**. Por isso o app confere se o nome e a sala do mesmo número
batem nas duas planilhas. Se não batem, avisa no card (ver §6).

### 3.3 Quando as duas planilhas têm datas diferentes

Vale a da **principal**, e o card mostra a da outra. A exceção é quando a data
da principal tem problema (por exemplo, fora de ordem): aí vale a da
complementar, e o card mostra a da principal com o motivo.

## 4. Como ler o quadro

Cada linha é um grupo; cada coluna, um dia. Os meses vão do primeiro dia do mês
da data mais antiga até o último dia do mês da mais recente (ou de hoje).

### 4.1 Como cada linha é pintada

A regra é a mesma da planilha pintada à mão:

- **Vermelho, laranja e azul** vão da data do marco até a **véspera do próximo
  marco que tiver data**.
- **Verde e preto** ocupam um dia só (o dia do transpasse, o dia do início).
- **Entre o verde e o preto**, os dias ficam em branco: é o tempo entre o
  transpasse e a chegada da manutenção.
- **Marcos no mesmo dia** (ex.: inspeção e CCMLC juntos): vale a cor do marco
  mais adiantado.

Exemplo (o mesmo do teste `test_pinta_um_grupo_completo_como_a_planilha1`):
convocação e inspeção em 01/09, CCMLC em 10/09, transpasse em 17/09 e início em
23/09.

```
dia:  1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23
cor:  O O O O . . O O O B  B  .  .  B  B  B  G  .  .  .  .  .  K
```

(`.` = sem cor; 5–6, 12–13 e 19–20 são sábado e domingo.)

### 4.2 Fins de semana

As colunas de sábado e domingo ficam em amarelo-claro, como na planilha. As
cores **não pintam** sábado e domingo no meio de uma etapa. O dia do próprio
marco é pintado mesmo se cair no fim de semana (ex.: CCMLC emitido num sábado).

### 4.3 Etapa em andamento

Se o próximo marco ainda não tem data, a etapa está em andamento e a cor vai
**até hoje**. Ex.: convocado há duas semanas e ainda sem inspeção, o vermelho
ocupa as duas semanas. É assim que o tempo parado aparece.

Depois do transpasse, enquanto o comissionamento não começa, os dias ficam em
branco (como na planilha). O card diz há quantos dias ele espera.

### 4.4 A linha de hoje

A linha preta vertical marca o fim do dia de hoje, e o número do dia de hoje,
no cabeçalho, fica com moldura.

### 4.5 Código do grupo em amarelo

Grupo **ainda não convocado** (sem data de convocação válida) fica com o
código em amarelo, como na planilha.

### 4.6 Salas

Cada sala da principal é um bloco, com o nome na vertical à esquerda. Uma sala
sem **nenhum** grupo convocado ainda (ex.: uma sala de testes que não
começou) não aparece; entra sozinha quando o primeiro grupo dela for convocado.

### 4.7 Interações

- **Mouse sobre um grupo (qualquer ponto da linha)**: abre o card (§6). Pelo
  teclado, a tecla Tab passa de grupo em grupo e mostra o mesmo card.
- **Mouse sobre uma cor da legenda**: só aquela cor fica destacada no quadro
  inteiro. Ex.: em vermelho, aparece de uma vez tudo o que está ou esteve
  esperando inspeção.

## 5. A coluna "Dias"

**É o número de dias da convocação até o início do comissionamento, contando
os dois dias** (o da convocação e o do início), sábados e domingos incluídos.
É o mesmo cálculo da coluna "Dias" da planilha pintada à mão.

Exemplo: convocação em **01/09** e início em **23/09**.

- Contando os quadradinhos do calendário de 01/09 a 23/09, incluindo os dois:
  **23**. É o que a coluna mostra.
- A subtração simples (23 − 1) daria 22. A coluna dá 1 a mais porque conta o
  dia da convocação também.

Por isso, no card, a soma dos "dias entre marcos" dá 1 a menos que o total:
0 + 9 + 7 + 6 = 22 dias de intervalo, e "Dias (convocação → início): 23".

A coluna só tem número quando o grupo **já tem o preto** (início do
comissionamento). Grupo que ainda não começou fica com a coluna vazia, e o
card diz há quanto tempo ele espera (§6).

Sem a planilha complementar não há início do comissionamento, então a coluna
fica vazia em todos os grupos.

## 6. O card (passar o mouse)

Exemplo de card:

```
GEQ-001-010 · ALIMENTAÇÃO REDUNDANTE ... / QUADRO DISTRIBUIÇÃO PRINCIPAL QDX - QDY
SALA SEGURA 50 Hz
■ Convocação                 06/10
■ Inspeção IB                08/10   2 dias
■ Emissão CCMLC              08/10   0 dias
■ Transpasse de fase         14/10   6 dias
■ Início do comissionamento  —
Aguardando o início do comissionamento há 13 dias
⚠ Na planilha complementar: Emissão CCMLC = 14/10/2026
```

Linha a linha:

| Parte | O que significa |
|---|---|
| **1ª linha** | Código e nome do grupo (da planilha principal). |
| **2ª linha** | Sala do grupo. |
| **Cinco linhas dos marcos** | Para cada marco: a cor da legenda, o nome e a data que entrou no quadro (`—` = sem data). O número à direita é **quantos dias se passaram desde o marco anterior que tem data**; ex.: "6 dias" no transpasse = 6 dias entre o CCMLC (08/10) e o transpasse (14/10). Na convocação não há número (é o primeiro marco). |
| **Linha em negrito** | A situação do grupo. Ver tabela abaixo. |
| **Linhas com ⚠** | Avisos: coisas a conferir na planilha (§7). |

A linha em negrito é uma destas:

| Texto | Quando |
|---|---|
| **Dias (convocação → início): N** | o grupo já tem início do comissionamento; N é o mesmo número da coluna "Dias" (§5) |
| **Aguardando a inspeção há N dias** | convocado, sem inspeção; N = dias desde a convocação |
| **Aguardando a emissão do CCMLC há N dias** | inspecionado, sem CCMLC |
| **Aguardando o transpasse há N dias** | com CCMLC, sem transpasse |
| **Aguardando o início do comissionamento há N dias** | com transpasse, sem início |
| **Ainda não convocado** | nenhuma data |
| **Sem data de convocação** | tem datas posteriores, mas não a convocação (data faltando ou com problema) |

Os avisos (⚠) são de cinco tipos:

| Aviso | O que fazer |
|---|---|
| **Na planilha complementar: *marco* = *data*** | As duas planilhas têm datas diferentes; o quadro usa a da principal. Corrigir a que estiver errada. |
| **Na planilha principal: *marco* = *data* (*motivo*)** | A data da principal tem problema e o quadro usa a da complementar. Corrigir a principal. |
| ***marco* = *data* (*motivo*)** com o nome de uma planilha | A data tem problema e não há outra para usar: o marco fica fora do quadro. Corrigir a planilha. |
| **Na planilha complementar, este número é “*outro nome*”** (e/ou **está na sala *X***) | O número do grupo aponta para grupos diferentes nas duas planilhas. Quando termina com "confira se as datas são deste grupo", vieram datas da complementar para esse grupo — e elas podem ser de outro. Alinhar a lista de grupos das duas planilhas. |
| **Na planilha *X*: *marco* “*texto*” não é uma data** | A célula tem um texto que não dá para ler como data (ex.: `14/1O/2026`, com a letra O no lugar do zero). Corrigir a célula. |

## 7. Datas que ficam fora do quadro

Uma data **não entra no quadro** (e vai para o card com o motivo) quando:

| Motivo no card | Por quê |
|---|---|
| **data no futuro** | Todos os marcos são de coisas que já aconteceram ("realizada"). Data depois de hoje é erro de digitação ou data prevista na coluna errada. |
| **data improvável: mais de um ano antes das demais** | Ano digitado errado (ex.: 2020 num quadro de 2026). Sem esse corte, uma data assim esticaria o quadro por anos. |
| **fora de ordem: antes de *marco*, *data*** | A data é anterior a um marco que vem antes dela (ex.: CCMLC antes da inspeção). |

Data digitada como texto (ex.: `14/10/2026`) é entendida normalmente. Texto que
não dá para ler como data vira aviso no card (§6). São ignorados **sem aviso**
só: células vazias, `[Data Início]`, `-` e fórmulas (na linha "Realizada" da
complementar, fórmula é previsão, não data realizada).
