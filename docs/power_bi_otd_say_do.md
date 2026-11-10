# Power BI: três visões, Baseline OTD, Say-do e curva S

Roteiro de cliques para o `Dashboard - Doc List Mapping.pbix`, no Power BI Desktop em
português. As decisões estão nas rodadas 3 e 4 do planejamento
(`.planning/2026-10-28-otd-say-do-doc-list/task_plan.md`); as regras dos indicadores,
na KB §27.7. Escrito em 2026-10-29 e conferido contra o modelo do `.pbix` (nomes de
tabelas, colunas, medidas e relações) e contra a planilha de 28/10, que deu os números
dos passos 9 a 11.

**O que muda no painel**

- Página **Unidade Geradora**: o gráfico DOCUMENTOS PARA EMISSÃO ganha três botões.
  - **ATUAL** é o gráfico de hoje, pela data-alvo.
  - **OTD** conta pela data prevista, a baseline.
  - **SAY-DO** mostra só o backlog, pela data reprogramada.
  - O painel abre na ATUAL.
- Um cartão que acompanha os botões: o índice em destaque (por exemplo, "59,3%") e, no
  título, emitidos/previstos ("29/59"). Ele segue o filtro PERÍODO e os filtros do topo
  (sistema, fase, responsável).
- **Página 1**: na curva S, os previstos entram na data-alvo e os emitidos na data em que
  saíram; o documento adiantado de verdade já entra no 1º dia do período.

Leva uns 45 minutos. Faça na ordem, porque cada passo usa o anterior.

---

## Antes de começar

1. **Planilha em dia.** Rode a atualização do Doc List pelo DocManager 3.6.1 (ou pela
   versão de teste 3.6.1-rc.1). Na primeira vez, ele cria e preenche no fim da aba as
   colunas `SITUAÇÃO OTD` e `SITUAÇÃO SAY-DO`. Confira no Excel que elas têm valores.
2. **Cópia de segurança.** No Explorador de Arquivos, copie o `.pbix` e cole na mesma
   pasta (fica "… - Copia.pbix"). Se algo der errado, volte para ela.
3. **Print de referência.** Abra o `.pbix`, escolha **2026 → outubro** no PERÍODO e tire
   um print do gráfico DOCUMENTOS PARA EMISSÃO. No fim, a visão ATUAL tem de ficar igual.
4. **Como colar as fórmulas.** Copie cada fórmula deste roteiro inteira e cole, sem
   digitar nada. Se o Power BI recusar uma fórmula apontando a vírgula, ele está com
   separadores locais. Nesse caso, troque as `,` por `;` naquela fórmula, mas só as de
   fora das aspas.

---

## Passo 1: trazer as colunas novas

1. Clique em **Página Inicial → Atualizar** e espere terminar.
2. No painel **Dados** (à direita), abra a tabela **Unidade Geradora** e confira que
   aparecem **SITUAÇÃO OTD** e **SITUAÇÃO SAY-DO**.

> Não apareceram? A planilha ainda não tem as colunas: volte ao item 1 de "Antes de
> começar". A consulta do Power Query já traz sozinha as colunas que aparecem no fim da
> aba, foi assim que a SITUAÇÃO EMISSÃO entrou.

---

## Passo 2: duas colunas de data no modelo

São cópias "só data" da data prevista e da reprogramada, iguais às `DATA-ALVO Aux` e
`DATA 1ª EMISSÃO Aux` que o modelo já tem. É por elas que o Calendario se liga.

1. No painel **Dados**, clique com o botão direito em **Unidade Geradora → Nova coluna**.
2. Na barra de fórmulas, em cima, apague o que estiver escrito, cole a fórmula abaixo e
   tecle **Enter**:

```dax
DATA PREVISTA Aux =
IF(
    ISBLANK('Unidade Geradora'[DATA PREVISTA EMISSÃO]),
    BLANK(),
    DATE(YEAR('Unidade Geradora'[DATA PREVISTA EMISSÃO]), MONTH('Unidade Geradora'[DATA PREVISTA EMISSÃO]), DAY('Unidade Geradora'[DATA PREVISTA EMISSÃO]))
)
```

3. Repita com esta:

```dax
DATA REPROGRAMADA Aux =
IF(
    ISBLANK('Unidade Geradora'[DATA REPROGRAMADA]),
    BLANK(),
    DATE(YEAR('Unidade Geradora'[DATA REPROGRAMADA]), MONTH('Unidade Geradora'[DATA REPROGRAMADA]), DAY('Unidade Geradora'[DATA REPROGRAMADA]))
)
```

**Confira:** as duas aparecem em Unidade Geradora, no painel Dados.

---

## Passo 3: duas relações inativas com o Calendario

1. Clique em **Exibição de modelo**, o terceiro ícone da barra da esquerda (o das
   tabelas ligadas por linhas).
2. Ache as caixas **Calendario** e **Unidade Geradora**. Arraste **Date** (do Calendario)
   e solte em cima de **DATA PREVISTA Aux** (da Unidade Geradora).
3. Se abrir uma janela de relação, confira os itens abaixo e clique **OK** (ou
   **Salvar**):
   - cardinalidade **Muitos para um (\*:1)**, ou **Um para muitos (1:\*)** se as tabelas
     estiverem na ordem inversa;
   - direção do filtro cruzado **Única**;
   - **Tornar esta relação ativa** desmarcado.
4. Repita arrastando **Date** para **DATA REPROGRAMADA Aux**.

**Confira:** as duas linhas novas saem **tracejadas**, isto é, inativas. É o certo: a
relação ativa continua a da DATA-ALVO Aux, e as medidas ligam as outras só quando
precisam, com `USERELATIONSHIP` (a medida `Emitidos` já faz assim com a
DATA 1ª EMISSÃO Aux). Se uma ficou com linha contínua, clique duas vezes nela e
desmarque **Tornar esta relação ativa**.

---

## Passo 4: duas tabelas pequenas (os botões e a legenda)

São tabelas soltas, sem relação com nada. Uma diz qual visão está escolhida. A outra dá
a legenda, para as cores serem as mesmas nas três visões.

1. Volte para a **Exibição de relatório**, o primeiro ícone da barra da esquerda.
2. Clique em **Modelagem → Nova tabela**, cole a fórmula abaixo e tecle **Enter**:

```dax
Visoes = DATATABLE("Visao", STRING, "Ordem", INTEGER, {{"ATUAL", 1}, {"OTD", 2}, {"SAY-DO", 3}})
```

3. Clique em **Modelagem → Nova tabela** de novo e cole esta:

```dax
Situacoes = DATATABLE("Situacao", STRING, "Ordem", INTEGER, {{"EMITIDO NO PRAZO", 1}, {"EMITIDO COM ATRASO", 2}, {"PENDENTE NO PRAZO", 3}, {"PENDENTE VENCIDO", 4}})
```

4. Acerte a ordem dos botões. No painel Dados, abra **Visoes** e clique na coluna
   **Visao**. Na faixa **Ferramentas de coluna**, clique em
   **Classificar por coluna → Ordem**.
5. Faça o mesmo na outra tabela: abra **Situacoes**, clique em **Situacao** e escolha
   **Ferramentas de coluna → Classificar por coluna → Ordem**.

Não ligue essas duas tabelas a nada na Exibição de modelo. Os nomes ficaram sem acento de
propósito, como o Calendario: as fórmulas citam os nomes exatamente assim.

---

## Passo 5: as medidas

As medidas ficam todas na tabela Calendario, junto das que já existem. Para cada fórmula
abaixo:

1. No painel **Dados**, clique com o botão direito em **Calendario → Nova medida**.
2. Apague o que estiver na barra de fórmulas, cole a fórmula inteira e tecle **Enter**.

### 5.1 O gráfico

```dax
Documentos (visão) =
SWITCH(
    SELECTEDVALUE(Visoes[Visao], "ATUAL"),
    "OTD",
        CALCULATE(
            DISTINCTCOUNT('Unidade Geradora'[N° ITAIPU]),
            USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA PREVISTA Aux]),
            TREATAS(VALUES(Situacoes[Situacao]), 'Unidade Geradora'[SITUAÇÃO OTD])
        ),
    "SAY-DO",
        CALCULATE(
            DISTINCTCOUNT('Unidade Geradora'[N° ITAIPU]),
            USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA REPROGRAMADA Aux]),
            TREATAS(VALUES(Situacoes[Situacao]), 'Unidade Geradora'[SITUAÇÃO SAY-DO])
        ),
    CALCULATE(
        DISTINCTCOUNT('Unidade Geradora'[N° ITAIPU]),
        TREATAS(VALUES(Situacoes[Situacao]), 'Unidade Geradora'[SITUAÇÃO EMISSÃO])
    )
)
```

```dax
Título (visão) =
SWITCH(
    SELECTEDVALUE(Visoes[Visao], "ATUAL"),
    "OTD", "BASELINE · PELA DATA PREVISTA",
    "SAY-DO", "BACKLOG · PELA DATA REPROGRAMADA",
    "DOCUMENTOS PARA EMISSÃO"
)
```

### 5.2 Baseline OTD

```dax
OTD previstos =
CALCULATE(
    DISTINCTCOUNT('Unidade Geradora'[N° ITAIPU]),
    USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA PREVISTA Aux]),
    'Unidade Geradora'[NÍVEL] = 2,
    'Unidade Geradora'[SITUAÇÃO OTD] IN {"EMITIDO NO PRAZO", "EMITIDO COM ATRASO", "PENDENTE NO PRAZO", "PENDENTE VENCIDO"}
)
```

```dax
OTD atrasados =
CALCULATE(
    DISTINCTCOUNT('Unidade Geradora'[N° ITAIPU]),
    USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA PREVISTA Aux]),
    'Unidade Geradora'[NÍVEL] = 2,
    'Unidade Geradora'[SITUAÇÃO OTD] IN {"EMITIDO COM ATRASO", "PENDENTE VENCIDO"}
)
```

```dax
Baseline OTD = DIVIDE([OTD previstos] - [OTD atrasados], [OTD previstos])
```

### 5.3 Say-do

```dax
Backlog =
CALCULATE(
    DISTINCTCOUNT('Unidade Geradora'[N° ITAIPU]),
    USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA REPROGRAMADA Aux]),
    'Unidade Geradora'[NÍVEL] = 2,
    'Unidade Geradora'[SITUAÇÃO SAY-DO] IN {"EMITIDO NO PRAZO", "EMITIDO COM ATRASO", "PENDENTE NO PRAZO", "PENDENTE VENCIDO"}
)
```

```dax
Backlog atrasado =
CALCULATE(
    DISTINCTCOUNT('Unidade Geradora'[N° ITAIPU]),
    USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA REPROGRAMADA Aux]),
    'Unidade Geradora'[NÍVEL] = 2,
    'Unidade Geradora'[SITUAÇÃO SAY-DO] IN {"EMITIDO COM ATRASO", "PENDENTE VENCIDO"}
)
```

```dax
Say-do = DIVIDE([Backlog] - [Backlog atrasado], [Backlog])
```

### 5.4 Formato de porcentagem

No painel Dados, clique em **Baseline OTD**. Na faixa **Ferramentas de medida**, clique
no botão **%** e deixe **1** casa decimal. Faça o mesmo em **Say-do**.

**Confira:** são 8 medidas novas em Calendario (o passo 9 cria mais duas), e nenhuma tem o
triângulo amarelo de erro.

> Montou o painel por uma versão anterior deste roteiro? As medidas
> `Baseline OTD (cartão)`, `Baseline OTD (título)`, `Say-do (cartão)` e `Say-do (título)`
> não são mais usadas. Podem ficar; para limpar, clique com o botão
> direito em cada uma → **Excluir do modelo**, depois de fazer o passo 9.

---

## Passo 6: o gráfico DOCUMENTOS PARA EMISSÃO

Na página **Unidade Geradora**, clique no gráfico DOCUMENTOS PARA EMISSÃO, no canto
inferior direito. No painel **Visualizações**, abra a aba **Criar visual** (a dos
campos):

1. **Eixo X**:
   - passe o mouse em **DATA-ALVO EMISSÃO** e clique no **X** para tirá-lo;
   - arraste **Calendario → Date** para o Eixo X. Ele entra como hierarquia (Ano,
     Trimestre, Mês, Dia);
   - tire **Ano**, **Trimestre** e **Mês** clicando no X de cada um, até sobrar só
     **Dia**.
2. **Eixo Y**: tire a contagem de **N° ITAIPU** e arraste a medida
   **Documentos (visão)**.
3. **Legenda**: tire **SITUAÇÃO EMISSÃO** e arraste **Situacoes → Situacao**.
4. **Dicas de ferramenta** e **Múltiplos pequenos**: deixe vazios. Campo da Unidade Geradora
   ali (por exemplo DATA 1ª EMISSÃO ou DIAS DESVIO EMISSÃO, sugeridos no roteiro de setembro)
   faz o Power BI mostrar "Não é possível determinar os relacionamentos entre os campos",
   porque a tabela Situacoes não tem relação com nada. Só a medida pode ficar nos valores.

O gráfico volta com as cores padrão do tema. Agora abra a aba **Formatar visual**:

5. Em **Visual → Colunas → Cores**, acerte a cor de cada situação. Clique no quadradinho
   de cor, depois em **Mais cores**, e digite o código. São as cores que o gráfico usa
   hoje:

   | Situação | Cor |
   |---|---|
   | EMITIDO NO PRAZO | `#1AAB40` |
   | EMITIDO COM ATRASO | `#FDEA21` |
   | PENDENTE NO PRAZO | `#118DFF` |
   | PENDENTE VENCIDO | `#F5012E` |

   Se aparecer uma cor só, escolha a situação na lista **Série** ou ligue
   **Mostrar tudo**.
6. Em **Visual → Legenda → Opções → Posição**, escolha uma das posições **Inferior**
   (por exemplo, **Inferior central**). A legenda desce e abre espaço em cima para os
   botões do passo 7.
7. Em **Geral → Título → Texto**, clique no **fx** ao lado da caixa de texto:
   - em **Formatar estilo**, escolha **Valor do campo**;
   - em **Em qual campo devemos nos basear?**, escolha **Título (visão)** (fica em
     Calendario);
   - clique **OK**.

**Confira:** os dias estão em ordem (3, 4, 6, 7…). Se não estiverem, clique nos **…**
(Mais opções) do gráfico, depois em **Classificar eixo → Dia** e em
**Classificar em ordem crescente**. O filtro **NÍVEL = 2** do visual continua como estava,
no painel **Filtros → Filtros neste visual**: não mexa nele.

---

## Passo 7: os botões ATUAL | OTD | SAY-DO

1. Clique numa área vazia da página, para nada ficar selecionado.
2. Em **Visualizações**, clique em **Segmentação de dados**. Arraste **Visoes → Visao**
   para **Campo**.
3. Na aba **Formatar visual → Visual**:
   - em **Configurações da segmentação → Opções → Estilo**, escolha **Bloco** (em algumas
     versões, "Blocos"): os itens viram botões lado a lado;
   - em **Configurações da segmentação → Seleção**, ligue **Seleção única** e desligue
     **Mostrar a opção "Selecionar tudo"**;
   - desligue **Cabeçalho da segmentação**;
   - em **Valores**, use fonte 9, em negrito.
4. Em **Formatar visual → Geral → Propriedades**:
   - Tamanho: Altura **30**, Largura **270**;
   - Posição: Horizontal **895**, Vertical **486**.

   Os botões ficam em cima do gráfico, à direita do título e ao lado do cartão do nível 3.
5. Em **Geral → Efeitos → Tela de fundo**, desligue, para ficar transparente sobre o
   gráfico.
6. Clique em **ATUAL** para deixá-lo escolhido. É a visão em que o painel abre.

**Teste:** clique em OTD e em SAY-DO. O título e as barras mudam, e as cores continuam as
mesmas. Na segmentação o clique funciona direto, sem Ctrl. Se alguém desmarcar o botão
escolhido, o gráfico mostra a ATUAL.

> A linha "hoje" do protótipo não entra: no eixo por dia do Power BI não há linha
> vertical. O vermelho já mostra o que venceu.

---

## Passo 8: o filtro PERÍODO passa para o Calendario

Hoje o PERÍODO filtra a DATA-ALVO. Para as três visões, ele precisa filtrar o Calendario.

1. Clique na segmentação **PERÍODO**, dentro do gráfico, em cima à esquerda.
2. Em **Criar visual → Campo**, tire os dois itens da **DATA-ALVO EMISSÃO** (Ano e Mês)
   clicando no X.
3. Arraste **Calendario → Date** para **Campo** e tire **Trimestre** e **Dia**, deixando
   **Ano** e **Mês**.
4. Abra a lista e escolha de novo **2026 → outubro**.

O cabeçalho "PERÍODO" e o resto da formatação ficam como estão. As interações também: o
PERÍODO continua agindo só no gráfico, no cartão do nível 3 e nos cartões novos.

---

## Passo 9: um cartão que acompanha os botões

Um cartão só: o **índice** no número e **emitidos/previstos** no título (decisão do
usuário, 2026-11-02). Os três botões usam a mesma regra, cada um contra a sua data:

| Botão | Previstos (o "/N" do título) | Índice (o número) | Outubro, planilha de 28/10 |
|---|---|---|---|
| ATUAL | data-alvo no período | o que não está atrasado ÷ previstos | 77,1%, título 28/48 |
| OTD | data prevista no período | Baseline OTD | 59,3%, título 29/59 |
| SAY-DO | backlog com data reprogramada no período | Say-do | 100,0%, título 0/5 |

"Não está atrasado" = emitido no prazo ou pendente que ainda não venceu. Por isso o índice
pode ser maior que emitidos/previstos: no SAY-DO de outubro, nenhum dos 5 saiu (0/5), mas
nenhum venceu ainda (100%).

1. Crie as duas medidas, como no passo 5 (botão direito em **Calendario → Nova medida**).
   Se a medida já existe, clique nela, selecione tudo (**Ctrl+A**), cole por cima e tecle
   **Enter**:

```dax
Indicador (cartão) =
VAR previstos = CALCULATE([Documentos (visão)], 'Unidade Geradora'[NÍVEL] = 2)
VAR atrasados =
    CALCULATE([Documentos (visão)], 'Unidade Geradora'[NÍVEL] = 2,
              Situacoes[Situacao] IN {"EMITIDO COM ATRASO", "PENDENTE VENCIDO"})
RETURN
IF(ISBLANK(previstos), "—", FORMAT(DIVIDE(previstos - atrasados, previstos), "0.0%"))
```

```dax
Indicador (título) =
VAR previstos = CALCULATE([Documentos (visão)], 'Unidade Geradora'[NÍVEL] = 2)
VAR emitidos =
    CALCULATE([Documentos (visão)], 'Unidade Geradora'[NÍVEL] = 2,
              Situacoes[Situacao] IN {"EMITIDO NO PRAZO", "EMITIDO COM ATRASO"})
RETURN
COALESCE(emitidos, 0) & "/" & COALESCE(previstos, 0)
```

2. Se ainda não tem o cartão, copie um que já existe, para herdar o estilo (número
   azul-marinho em negrito, borda arredondada): clique no cartão do canto superior direito
   da página, ao lado do logo da CMI, e tecle **Ctrl+C** e **Ctrl+V**. Com a cópia
   selecionada, em **Criar visual → Campos**, tire o campo que está lá e arraste
   **Indicador (cartão)**.
3. Em **Formatar visual → Geral → Título**:
   - ligue o título;
   - em **Texto**, clique no **fx**, escolha **Valor do campo → Indicador (título)** e
     clique **OK**;
   - fonte 11, negrito, centralizado, na cor azul-marinho do número.
4. Tamanho: o número volta a ser curto ("59,3%"), então o cartão do tamanho original
   (Largura 106, fonte 19) basta, e os botões não precisam ser estreitados. Se o texto
   cortar, aumente a largura do cartão ou diminua a fonte.
5. Interações: o cartão **tem** de ouvir os botões ATUAL | OTD | SAY-DO e o PERÍODO.
   1. Selecione a segmentação dos botões.
   2. Na faixa **Formato**, clique em **Editar interações**.
   3. Em cima do cartão, o ícone escolhido tem de ser o **Filtro** (o funil), não o
      **Nenhum**. Faça o mesmo com a segmentação PERÍODO.
   4. Para o cartão não mudar quando alguém clica numa barra ou fatia, selecione o
      DOCUMENTAÇÃO GERAL, as três pizzas e o DOCUMENTOS PARA EMISSÃO, um de cada vez, e
      clique em **Nenhum** em cima do cartão.
   5. Clique em **Editar interações** de novo para sair.

A medida já conta só o nível 2; os filtros que vieram com a cópia (NÍVEL = 2 e N° ITAIPU
não vazio) podem ficar.

---

## Passo 10: a curva S da Página 1

A regra (decisão do usuário, 2026-11-10, ajustada aos dados reais no mesmo dia):

- **Previstos** (azul escuro): cada documento entra no dia da sua **data-alvo**. É a medida
  original do painel e não muda.
- **Emitidos** (azul claro): cada documento **previsto para o período** entra:
  - no dia em que **saiu** (1ª emissão), se saiu dentro do período;
  - no **1º dia**, se saiu antes do período e ainda está na 1ª revisão: é adiantado de
    verdade, e a linha clara pode começar acima da escura;
  - no dia da **data-alvo**, se saiu antes dela e **já teve revisão depois** (0B, 0C, 0…).
    Nesses documentos a data do Doc List é de uma revisão posterior, não da 1ª emissão; eles
    contam como "emitido no prazo" no dia previsto, igual ao gráfico ATUAL. Se saiu depois
    da data-alvo, entra no dia em que saiu.
- Também entra o documento previsto para **um período seguinte** que saiu dentro deste e
  ainda está na 1ª revisão (adiantado), no dia em que saiu.
- **Não entram**: o atrasado de um período anterior emitido agora (ele é do período em que
  estava previsto) e o documento sem data-alvo. A linha para em hoje.

Por que a regra de revisão: com os dados de 26/10, 85 documentos com data-alvo em 2026
tinham a 1ª emissão em 2024 ou 2025, quase todos mais de 3 meses antes, e **todos** já
tinham revisões posteriores. Contados como adiantados, eles faziam a linha clara começar o
ano 85 documentos acima da escura.

Exemplo: em novembro estão previstos x (10/11), y (15/11) e z (20/11), ainda na 1ª revisão;
x saiu em 01/10, y em 25/09 e z em 10/11.

| Dia (novembro) | Previstos | Emitidos | Por quê |
|---|---|---|---|
| 02/11 | 0 | 2 | x e y já tinham saído antes de novembro |
| 10/11 | 1 | 3 | x previsto; z saiu |
| 20/11 | 3 | 3 | y e z previstos |

Em outubro, x conta como emitido em 01/10: estava previsto para novembro e saiu adiantado.

1. Vá para a **Página 1**.
2. No painel **Dados**, em **Calendario**, clique em **Emitidos Acum**. Na barra de
   fórmulas, selecione tudo (**Ctrl+A**), cole a fórmula abaixo e tecle **Enter**:

```dax
Emitidos Acum =
VAR DataAtual = MAX(Calendario[Date])
VAR Inicio = CALCULATE(MIN(Calendario[Date]), ALLSELECTED(Calendario))
VAR Fim = CALCULATE(MAX(Calendario[Date]), ALLSELECTED(Calendario))
VAR Linhas =
    FILTER(
        CALCULATETABLE(
            'Unidade Geradora',
            CROSSFILTER('Unidade Geradora'[DATA-ALVO Aux], Calendario[Date], None)
        ),
        VAR Alvo = 'Unidade Geradora'[DATA-ALVO Aux]
        VAR Emissao = 'Unidade Geradora'[DATA 1ª EMISSÃO Aux]
        VAR SoPrimeiraRevisao =
            ISBLANK('Unidade Geradora'[DATA ÚLTIMA EMISSÃO])
                || 'Unidade Geradora'[DATA ÚLTIMA EMISSÃO] <= Emissao
        VAR Entrada =
            SWITCH(
                TRUE(),
                ISBLANK(Emissao) || ISBLANK(Alvo), BLANK(),
                Alvo >= Inicio && Alvo <= Fim && SoPrimeiraRevisao, MAX(Emissao, Inicio),
                Alvo >= Inicio && Alvo <= Fim, MAX(Emissao, Alvo),
                Alvo > Fim && SoPrimeiraRevisao && Emissao >= Inicio, Emissao,
                BLANK()
            )
        RETURN NOT ISBLANK(Entrada) && Entrada <= DataAtual
    )
RETURN
IF(
    DataAtual > TODAY(),
    BLANK(),
    COUNTROWS(SUMMARIZE(Linhas, 'Unidade Geradora'[N° ITAIPU]))
)
```

3. Confira que **Previstos Acum** está assim (é a fórmula original do painel; se você colou
   outra versão deste roteiro, volte a esta):

```dax
Previstos Acum =
VAR DataAtual = MAX(Calendario[Date])
RETURN
CALCULATE(
    [Previstos],
    FILTER(
        ALLSELECTED(Calendario),
        Calendario[Date] <= DataAtual
    )
)
```

Como funciona a de emitidos: `Inicio` e `Fim` são o primeiro e o último dia do período do
filtro. Para cada linha da planilha, `Entrada` é o dia em que o documento entra na linha
clara, pelas regras acima (`MAX` pega a data mais tarde das duas); a medida conta os
documentos distintos que já entraram até o dia do gráfico. O `CROSSFILTER(..., None)`
desliga a relação da DATA-ALVO só dentro dessa conta, para as datas serem comparadas direto.
"Ainda na 1ª revisão" é a DATA ÚLTIMA EMISSÃO não ser posterior à 1ª emissão. Sem período
escolhido, a curva é a do projeto inteiro.

Um limite: um documento que saiu adiantado e já teve revisão entra no dia previsto, e não
no dia em que saiu. A planilha não guarda a que revisão se refere a data prevista, então não
dá para separá-lo de um documento cuja data é de uma revisão posterior.

**Confira** com **2026 → outubro** (planilha de 28/10):

| Dia | Previstos | Emitidos |
|---|---|---|
| 1/10 | 0 | 3 |
| 10/10 | 23 | 22 |
| 20/10 | 32 | 26 |
| 28/10 | 34 | 27 |

---

## Passo 11: conferir e salvar

1. **ATUAL**, com 2026 → outubro, tem de ficar igual ao print do começo. Com a planilha
   de 28/10:
   - 48 documentos: 28 emitidos no prazo, 9 pendentes no prazo e 11 vencidos;
   - a única diferença possível é que documento CANCELADO não aparece mais, como já era a
     regra.
2. **OTD**: 59 documentos (29 no prazo, 6 pendentes no prazo, 24 vencidos).
3. **SAY-DO**: 5 documentos, todos pendentes no prazo, em 30 e 31/10.
4. Sem mês escolhido no PERÍODO, os cartões mostram o plano inteiro. Com a planilha de
   28/10:
   - Baseline OTD 65,7% (735 de 1.118);
   - Say-do 100,0% (67 de 67).
5. Clique em **Arquivo → Salvar** e publique como de costume.

Os números acima são da planilha de 28/10. Com a planilha de outro dia, confira pelo Excel,
na aba Unidade Geradora, com filtros:

- **Baseline OTD do mês**:
  - filtre NÍVEL = 2 e DATA PREVISTA EMISSÃO no mês;
  - em SITUAÇÃO OTD, tire CANCELADO e SEM PLANEJAMENTO. As linhas que sobram são o
    "de N" do cartão;
  - dessas, as EMITIDO COM ATRASO e PENDENTE VENCIDO são os atrasados.
- **Say-do do mês**: filtre NÍVEL = 2, DATA REPROGRAMADA no mês e SITUAÇÃO SAY-DO
  preenchida, sem CANCELADO.
- O Excel conta linhas, e o painel conta códigos distintos: um código repetido em duas
  linhas conta uma vez no painel.

Antes de apresentar: rode o DocManager e clique em **Atualizar** no Power BI. O "vencido"
é o do dia em que o app rodou.

---

## Se algo der errado

| O que aparece | O que fazer |
|---|---|
| A fórmula é recusada e o erro aponta a vírgula | O Power BI está com separadores locais: troque `,` por `;` fora das aspas. |
| "Não é possível encontrar a coluna SITUAÇÃO OTD" (ou SAY-DO) | A planilha ainda não tem a coluna: rode o DocManager 3.6.1 no Doc List e clique em **Atualizar**. |
| Uma relação nova ficou com linha contínua | Clique duas vezes nela e desmarque **Tornar esta relação ativa**. A ativa tem de ser a da DATA-ALVO Aux. |
| "Não é possível determinar os relacionamentos entre os campos" | Sobrou campo de tabela no gráfico além de Date (Eixo X) e Situacao (Legenda): confira Eixo Y (só a medida Documentos (visão), com ícone de calculadora), Dicas de ferramenta e Múltiplos pequenos (vazios) e se não ficou DATA-ALVO EMISSÃO no Eixo X. |
| Gráfico vazio | Confira se há um botão escolhido, se **Documentos (visão)** está no Eixo Y e se o PERÍODO já é do Calendario (passo 8). |
| Botões ou legenda fora de ordem | Faltou **Classificar por coluna → Ordem** (passo 4). |
| As cores voltaram ao padrão | Refaça o item 5 do passo 6. |
| O cartão mostra "—" | Não há documento previsto (ou backlog) no período. É o esperado. |
| O texto do cartão aparece cortado | Aumente a largura do cartão ou diminua a fonte do número (passo 9, item 4). |
| O cartão não muda com os botões | A interação dos botões com o cartão está em **Nenhum**: passo 9, item 6. |
| Na curva S, os emitidos passam muito dos previstos | Confira se a medida **Emitidos Acum** é a do passo 10 (com `SoPrimeiraRevisao`); a versão de 10/11 contava como adiantados os documentos cuja data é de uma revisão posterior. |

---

## Referência: o que cada peça faz

| Peça | Para quê |
|---|---|
| `DATA PREVISTA Aux`, `DATA REPROGRAMADA Aux` | Datas sem hora, para ligar ao Calendario. |
| Relações inativas | Deixam as medidas contarem pela data prevista ou reprogramada só quando pedem (`USERELATIONSHIP`). |
| `Visoes` | Os três botões. Não tem relação: as medidas leem o botão escolhido com `SELECTEDVALUE`. |
| `Situacoes` | A legenda das três visões. Fixa as cores e deixa CANCELADO e SEM PLANEJAMENTO de fora. |
| `Documentos (visão)` | Conta, por dia, a situação da visão escolhida: SITUAÇÃO EMISSÃO pela data-alvo, SITUAÇÃO OTD pela data prevista ou SITUAÇÃO SAY-DO pela data reprogramada. |
| `Título (visão)` | O título do gráfico em cada visão. |
| `OTD previstos`, `OTD atrasados`, `Baseline OTD` | (previstos no período − atrasados) ÷ previstos, no nível 2. O que não venceu conta como cumprido. |
| `Backlog`, `Backlog atrasado`, `Say-do` | A mesma conta sobre o backlog, pela data reprogramada. |
| `Indicador (cartão)`, `Indicador (título)` | O cartão único: o índice da visão escolhida (o que não está atrasado ÷ previstos) no número e emitidos/previstos no título. |
| `Previstos Acum`, `Emitidos Acum` | A curva S do período: previstos pela data-alvo; emitidos pelas regras do passo 10 (dia em que saiu, 1º dia para o adiantado na 1ª revisão, data-alvo para quem já teve revisão). |

As situações são gravadas pelo DocManager (KB §27.5 e §27.7). O Power BI só conta.
