# Power BI: três visões, Baseline OTD, Say-do e curva S

Roteiro de cliques para o `Dashboard - Doc List Mapping.pbix`, no Power BI Desktop em
português. As decisões estão nas rodadas 3 e 4 do planejamento
(`.planning/2026-10-28-otd-say-do-doc-list/task_plan.md`); as regras dos indicadores,
na KB §27.7. Escrito em 2026-10-29 e conferido contra o modelo do `.pbix` (nomes de
tabelas, colunas, medidas e relações) e contra a planilha de 28/10, que deu os números
dos passos 9 a 11. O passo 12 (2026-11-10) foi conferido contra o `.pbix` e a planilha de
06/11.

**O que muda no painel**

- Página **Unidade Geradora**: o gráfico DOCUMENTOS PARA EMISSÃO ganha três botões.
  - **ATUAL** é o gráfico de hoje, pela data-alvo.
  - **OTD** conta pela data prevista, a baseline.
  - **SAY-DO** mostra só o backlog, pela data reprogramada.
  - O painel abre na ATUAL.
- Um cartão que acompanha os botões: o índice em destaque (por exemplo, "59,3%") e, no
  título, emitidos/previstos ("29/59"). Ele segue o filtro PERÍODO e os filtros do topo
  (sistema, fase, responsável).
- Página **Curva** (a antiga Página 1): na curva S, os previstos entram na data-alvo e os
  emitidos na data em que saíram; o documento adiantado de verdade já entra no 1º dia do
  período.
- Página **Projeção** (nova, passo 12):
  - o projeto inteiro numa curva só: baseline, realizado e a projeção pelo replanejado;
  - o cartão **A recuperar**;
  - a lista desses documentos, que abre por grupo, sistema e documento.

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

**Como ler o gráfico**

- Cada degrau da linha **escura** são documentos com data-alvo naquele dia.
- Cada degrau da linha **clara** são documentos que entraram naquele dia: saíram nesse dia
  ou, se já tiveram revisão, estavam previstos para esse dia.
- **Clara acima da escura** é adiantamento real: documento na 1ª revisão que saiu antes da
  data-alvo, ou previsto para o período seguinte que saiu neste. Documento com revisão
  posterior nunca puxa a clara para cima, porque entra no dia previsto.
- **Clara abaixo da escura** são documentos previstos até aquele dia que ainda não saíram, ou
  que saíram atrasados (esses entram no dia em que saíram).
- A distância entre as duas no dia de hoje é, grosso modo, o que estava previsto até hoje e
  não saiu, menos o que saiu adiantado. Para ver quais documentos são, use a visão ATUAL da
  página Unidade Geradora (barras vermelhas, pendentes vencidos).
- Depois de hoje só aparece a escura: o que ainda está previsto até o fim do período.
- Dia sem nenhum documento contado não tem ponto: o Power BI não desenha o zero. Por isso a
  escura pode começar alguns dias depois do início do período.
- Os filtros do topo (sistema, fase, responsável) valem para as duas linhas.

**Confira** com **2026 → outubro** (planilha de 28/10):

| Dia | Previstos | Emitidos |
|---|---|---|
| 1/10 | 0 | 3 |
| 10/10 | 23 | 22 |
| 20/10 | 32 | 26 |
| 28/10 | 34 | 27 |

### Opcional: escolher a data da curva (data-alvo ou data prevista)

Para a curva também poder ser vista pela **data prevista** (a baseline, a ideia do OTD), a
Página 1 ganha os botões **ATUAL | OTD**, os mesmos nomes da página Unidade Geradora:

- **ATUAL**: as duas linhas pela data-alvo, como acima;
- **OTD**: as duas linhas pela **data prevista**. Um documento reprogramado fica no período
  em que estava previsto originalmente, e a distância entre as linhas é o atraso contra a
  baseline. As regras dos emitidos são as mesmas, trocando a data-alvo pela prevista.

1. Na página **Unidade Geradora**, clique nos botões ATUAL | OTD | SAY-DO e tecle **Ctrl+C**.
   Vá para a **Página 1** e tecle **Ctrl+V**. Se o Power BI perguntar se quer sincronizar
   com a segmentação da outra página, escolha **não sincronizar**: cada página escolhe a sua.
2. Com os botões colados selecionados, no painel **Filtros → Filtros neste visual**, abra
   **Visao** e desmarque **SAY-DO**. Ficam ATUAL e OTD.
3. Ponha os botões perto do filtro "Ano, Mês" e clique em **ATUAL**: é como a página abre.
   Os botões da Página 1 valem só para a curva; os da página Unidade Geradora, só para lá.
4. Troque as duas medidas (clique em cada uma em **Calendario**, **Ctrl+A**, cole, **Enter**):

```dax
Previstos Acum =
VAR DataAtual = MAX(Calendario[Date])
VAR PelaPrevista = SELECTEDVALUE(Visoes[Visao], "ATUAL") = "OTD"
RETURN
IF(
    PelaPrevista,
    CALCULATE(
        [Previstos],
        USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA PREVISTA Aux]),
        FILTER(ALLSELECTED(Calendario), Calendario[Date] <= DataAtual)
    ),
    CALCULATE(
        [Previstos],
        FILTER(ALLSELECTED(Calendario), Calendario[Date] <= DataAtual)
    )
)
```

```dax
Emitidos Acum =
VAR DataAtual = MAX(Calendario[Date])
VAR Inicio = CALCULATE(MIN(Calendario[Date]), ALLSELECTED(Calendario))
VAR Fim = CALCULATE(MAX(Calendario[Date]), ALLSELECTED(Calendario))
VAR PelaPrevista = SELECTEDVALUE(Visoes[Visao], "ATUAL") = "OTD"
VAR Linhas =
    FILTER(
        CALCULATETABLE(
            'Unidade Geradora',
            CROSSFILTER('Unidade Geradora'[DATA-ALVO Aux], Calendario[Date], None)
        ),
        VAR Alvo =
            IF(PelaPrevista, 'Unidade Geradora'[DATA PREVISTA Aux], 'Unidade Geradora'[DATA-ALVO Aux])
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

5. Opcional, o título dizendo qual data está valendo. Crie a medida abaixo e, no gráfico, em
   **Formatar visual → Geral → Título → Texto**, clique no **fx** → **Valor do campo** →
   **Título (curva S)**:

```dax
Título (curva S) =
IF(
    SELECTEDVALUE(Visoes[Visao], "ATUAL") = "OTD",
    "DOCUMENTOS PREVISTOS E EMITIDOS · BASELINE (DATA PREVISTA)",
    "DOCUMENTOS PREVISTOS E EMITIDOS · DATA-ALVO"
)
```

O que muda nas fórmulas: `PelaPrevista` lê o botão escolhido. Nos previstos, o
`USERELATIONSHIP` liga o Calendario à DATA PREVISTA Aux, como nas medidas do OTD. Nos
emitidos, `Alvo` passa a ser a DATA PREVISTA Aux. Sem botão escolhido, vale a ATUAL.

Um documento reprogramado que sai depois da data prevista não entra na curva de nenhum mês
na visão OTD: no mês previsto ele ainda não tinha saído, e no mês em que saiu ele é atrasado
de período anterior. É o mesmo que o Baseline OTD mede.

**Confira** com **2026 → outubro** (planilha de 28/10):

| Dia | ATUAL: previstos × emitidos | OTD: previstos × emitidos |
|---|---|---|
| 10/10 | 23 × 22 | 28 × 24 |
| 20/10 | 32 × 26 | 45 × 28 |
| 31/10 | 48 × 29 | 60 × 31 |

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

## Passo 12: a página Projeção (curva do projeto e lista a recuperar)

Uma página nova com o projeto inteiro, para ver o que está atrasado e quando ele é
recuperado (decisões do usuário, 2026-11-10: Q21, Q22 e Q23 = A). Pode ser feita em outro
dia: não mexe em nada dos passos 1 a 11. Leva uns 30 minutos.

- **Gráfico**: três linhas no mesmo eixo, de ago/2024 a out/2027.
  - **Baseline** (azul escuro, cheia): cada documento entra na **data prevista**.
  - **Realizado** (azul claro, cheia, até hoje): cada documento entra no dia em que
    **saiu** (1ª emissão). Se já teve revisão depois, entra na data prevista, como na curva
    do passo 10, ou no dia em que saiu, se saiu depois dela.
  - **Projeção** (azul claro, tracejada, de hoje em diante): o realizado de hoje mais cada
    pendente na sua **data-alvo**, se ela ainda não venceu. O pendente com a data-alvo
    vencida não entra, então o vão que sobra no fim é quem precisa de data nova.
- **Cartão A recuperar**: os documentos que não saíram e cuja data prevista já passou (o
  PENDENTE VENCIDO da SITUAÇÃO OTD). O título diz quantos têm **data nova** (data-alvo que
  ainda não venceu) e quantos não têm.
- **Lista**: os mesmos documentos numa matriz que abre por grupo, sistema e documento.
  - **SEM DATA NOVA**: precisam ser **encaixados**, isto é, ganhar data reprogramada no
    Controle de Documentos.
  - **COM DATA NOVA**: já têm data; **adiantá-la** fecha o vão mais cedo.

Cancelado e documento sem data prevista ficam fora de tudo. "A recuperar" não é "backlog":
no painel, backlog é só o documento reprogramado (o do Say-do).

### 12.1 A página

1. Embaixo, clique com o botão direito na aba **Curva** (a antiga Página 1) e escolha
   **Duplicar página**.
2. Clique duas vezes na aba nova e renomeie para **Projeção**.
3. Na Projeção, apague o gráfico da curva, o filtro **Ano, Mês** e os botões
   **ATUAL | OTD** (clique em cada um e tecle **Delete**). Ficam os logos, o título e os
   três filtros do topo (sistema, fase, responsável). Deixe os filtros em tudo.

### 12.2 A tabela dos grupos

Como no passo 4: clique em **Modelagem → Nova tabela**, cole e tecle **Enter**:

```dax
Recuperacao = DATATABLE("Grupo", STRING, "Ordem", INTEGER, {{"SEM DATA NOVA", 1}, {"COM DATA NOVA", 2}})
```

No painel **Dados**, abra **Recuperacao**, clique em **Grupo** e escolha
**Ferramentas de coluna → Classificar por coluna → Ordem**. Não ligue a tabela a nada.

### 12.3 As medidas

Como no passo 5 (botão direito em **Calendario → Nova medida**, cole a fórmula inteira,
**Enter**). Primeiro as três da curva:

```dax
Baseline (projeto) =
VAR Dia = MAX(Calendario[Date])
VAR Linhas =
    FILTER(
        CALCULATETABLE('Unidade Geradora', REMOVEFILTERS(Calendario)),
        NOT ISBLANK('Unidade Geradora'[DATA PREVISTA Aux])
            && 'Unidade Geradora'[DATA PREVISTA Aux] <= Dia
            && 'Unidade Geradora'[STATUS CONSOLIDADO] <> "CANCELADO"
    )
RETURN
COUNTROWS(SUMMARIZE(Linhas, 'Unidade Geradora'[N° ITAIPU]))
```

```dax
Realizado (projeto) =
VAR Dia = MAX(Calendario[Date])
VAR Linhas =
    FILTER(
        CALCULATETABLE('Unidade Geradora', REMOVEFILTERS(Calendario)),
        VAR Prevista = 'Unidade Geradora'[DATA PREVISTA Aux]
        VAR Emissao = 'Unidade Geradora'[DATA 1ª EMISSÃO Aux]
        VAR SoPrimeiraRevisao =
            ISBLANK('Unidade Geradora'[DATA ÚLTIMA EMISSÃO])
                || 'Unidade Geradora'[DATA ÚLTIMA EMISSÃO] <= Emissao
        VAR Entrada = IF(SoPrimeiraRevisao, Emissao, MAX(Emissao, Prevista))
        RETURN
            NOT ISBLANK(Prevista) && NOT ISBLANK(Emissao)
                && 'Unidade Geradora'[STATUS CONSOLIDADO] <> "CANCELADO"
                && Entrada <= Dia
    )
RETURN
IF(Dia > TODAY(), BLANK(), COUNTROWS(SUMMARIZE(Linhas, 'Unidade Geradora'[N° ITAIPU])))
```

```dax
Projeção (projeto) =
VAR Dia = MAX(Calendario[Date])
VAR Hoje = TODAY()
VAR Linhas =
    FILTER(
        CALCULATETABLE('Unidade Geradora', REMOVEFILTERS(Calendario)),
        VAR Prevista = 'Unidade Geradora'[DATA PREVISTA Aux]
        VAR Emissao = 'Unidade Geradora'[DATA 1ª EMISSÃO Aux]
        VAR Alvo = 'Unidade Geradora'[DATA-ALVO Aux]
        VAR SoPrimeiraRevisao =
            ISBLANK('Unidade Geradora'[DATA ÚLTIMA EMISSÃO])
                || 'Unidade Geradora'[DATA ÚLTIMA EMISSÃO] <= Emissao
        VAR Entrada =
            SWITCH(
                TRUE(),
                NOT ISBLANK(Emissao) && SoPrimeiraRevisao, Emissao,
                NOT ISBLANK(Emissao), MAX(Emissao, Prevista),
                Alvo >= Hoje, Alvo,
                BLANK()
            )
        RETURN
            NOT ISBLANK(Prevista) && NOT ISBLANK(Entrada)
                && 'Unidade Geradora'[STATUS CONSOLIDADO] <> "CANCELADO"
                && Entrada <= Dia
    )
RETURN
IF(Dia < Hoje, BLANK(), COUNTROWS(SUMMARIZE(Linhas, 'Unidade Geradora'[N° ITAIPU])))
```

Depois as do cartão:

```dax
A recuperar =
VAR Hoje = TODAY()
VAR Grupo = SELECTEDVALUE(Recuperacao[Grupo])
VAR Linhas =
    FILTER(
        CALCULATETABLE('Unidade Geradora', REMOVEFILTERS(Calendario)),
        VAR Prevista = 'Unidade Geradora'[DATA PREVISTA Aux]
        VAR ComDataNova = 'Unidade Geradora'[DATA-ALVO Aux] >= Hoje
        RETURN
            NOT ISBLANK(Prevista) && Prevista < Hoje
                && ISBLANK('Unidade Geradora'[DATA 1ª EMISSÃO Aux])
                && 'Unidade Geradora'[STATUS CONSOLIDADO] <> "CANCELADO"
                && SWITCH(Grupo, "COM DATA NOVA", ComDataNova, "SEM DATA NOVA", NOT ComDataNova, TRUE())
    )
RETURN
COUNTROWS(SUMMARIZE(Linhas, 'Unidade Geradora'[N° ITAIPU]))
```

```dax
A recuperar (título) =
VAR ComData = CALCULATE([A recuperar], Recuperacao[Grupo] = "COM DATA NOVA")
VAR SemData = CALCULATE([A recuperar], Recuperacao[Grupo] = "SEM DATA NOVA")
RETURN
COALESCE(ComData, 0) & " COM DATA NOVA · " & COALESCE(SemData, 0) & " SEM DATA NOVA"
```

E as quatro colunas da lista:

```dax
Descrição (a recuperar) =
IF([A recuperar] > 0, SELECTEDVALUE('Unidade Geradora'[DESCRIÇÃO DO DOCUMENTO]))
```

```dax
Prevista (a recuperar) =
MINX(
    FILTER(VALUES('Unidade Geradora'[N° ITAIPU]), [A recuperar] > 0),
    CALCULATE(MIN('Unidade Geradora'[DATA PREVISTA Aux]), REMOVEFILTERS(Calendario))
)
```

```dax
Data nova (a recuperar) =
VAR Data =
    MAXX(
        FILTER(VALUES('Unidade Geradora'[N° ITAIPU]), [A recuperar] > 0),
        CALCULATE(MAX('Unidade Geradora'[DATA-ALVO Aux]), REMOVEFILTERS(Calendario))
    )
RETURN
IF(Data >= TODAY(), Data)
```

```dax
Dias de atraso (a recuperar) =
VAR Prevista = [Prevista (a recuperar)]
RETURN
IF(NOT ISBLANK(Prevista), DATEDIFF(Prevista, TODAY(), DAY))
```

Formato: clique em **Prevista (a recuperar)** e, na faixa **Ferramentas de medida**, em
**Formato**, escolha a data curta (14/03/2001). Faça o mesmo em **Data nova (a recuperar)**.

Como funcionam:

- Todas pegam as linhas da planilha que passam nos filtros do topo, sem o filtro de data do
  gráfico (`REMOVEFILTERS(Calendario)`), e comparam as datas direto.
- Contam códigos distintos, como o resto do painel.
- `TODAY()` é o dia em que o painel é aberto.
- **A recuperar** lê o grupo da linha da lista com `SELECTEDVALUE`, como as medidas do
  passo 5 leem o botão. No cartão não há grupo, e ela conta os dois.
- As medidas da lista só devolvem valor para quem está a recuperar. É por isso que a matriz
  mostra só esses documentos.

**Confira:** são 9 medidas novas em Calendario, sem o triângulo amarelo de erro.

### 12.4 O gráfico

1. Clique numa área vazia da página. Em **Visualizações**, clique em **Gráfico de linhas**.
2. **Eixo X**: arraste **Calendario → Date**. Ele entra como hierarquia: clique na setinha
   ao lado de **Date**, no Eixo X, e escolha **Date** (em vez de **Hierarquia de datas**).
3. **Eixo Y**: arraste, nesta ordem, **Baseline (projeto)**, **Realizado (projeto)** e
   **Projeção (projeto)**. Para a legenda ficar limpa, clique duas vezes em cada uma, no
   Eixo Y, e renomeie para **Baseline (data prevista)**, **Realizado** e
   **Projeção (data-alvo)**.
4. **Período**:
   1. No painel **Filtros → Filtros neste visual**, abra **Date** e escolha
      **Filtragem avançada**.
   2. Preencha **é posterior ou igual a** 01/08/2024, **E**, **é anterior ou igual a**
      31/10/2027, e clique em **Aplicar filtro**.

   O filtro só escolhe os dias desenhados: a baseline continua contando o que estava
   previsto antes de agosto/2024.
5. Na aba **Formatar visual**:
   - **Visual → Eixo X → Tipo**: **Contínuo**.
   - **Visual → Linhas**: em **Série**, escolha cada linha e acerte a cor (**Mais cores**,
     digite o código):
     - Baseline `#12239E`, o azul escuro dos previstos na Curva;
     - Realizado `#118DFF`, o azul claro dos emitidos;
     - Projeção `#118DFF`, com **Estilo da linha: Tracejado**.
   - **Visual → Legenda → Opções → Posição**: **Inferior central**.
   - **Geral → Título**: ligue, com o texto **CURVA DO PROJETO · BASELINE, REALIZADO E
     PROJEÇÃO**, fonte 12, negrito, cor `#0E1A77` (a do título da Curva).
   - **Geral → Propriedades**: Largura **940**, Altura **320**, Horizontal **10**,
     Vertical **80**.
6. Opcional, a linha de hoje:
   1. Crie a medida `Hoje (linha) = TODAY()` (em **Calendario → Nova medida**).
   2. Com o gráfico selecionado, abra o painel **Análise** (a lupa, ao lado de
      **Formatar visual**) → **Linha X constante** → **Adicionar linha**.
   3. Em **Valor**, clique no **fx** → **Valor do campo** → **Hoje (linha)** → **OK**.
      Use a cor cinza `#898781` e o estilo **Sólido**.

   Se o **Valor** não tiver o **fx** na sua versão, pule este item: o fim da linha cheia
   clara já marca o hoje.

### 12.5 O cartão

1. Na página **Unidade Geradora**, clique no cartão do índice (o do passo 9, ao lado dos
   botões ATUAL | OTD | SAY-DO) e tecle **Ctrl+C**. Volte à **Projeção** e tecle
   **Ctrl+V**.
2. Em **Criar visual → Campos**, tire **Indicador (cartão)** e arraste **A recuperar**.
3. Em **Formatar visual → Geral → Título → Texto**, clique no **fx** → **Valor do campo** →
   **A recuperar (título)** → **OK**.
4. Em **Visual**, ligue o **Rótulo de categoria**: aparece "A recuperar" embaixo do número.
5. Em **Geral → Propriedades**: Largura **310**, Altura **110**, Horizontal **960**,
   Vertical **80**. Se o título cortar, ligue **Quebra automática de texto** no título ou
   aumente a largura.

Os filtros que vieram com a cópia (NÍVEL = 2 e N° ITAIPU não vazio) podem ficar: todo
documento com data prevista é do nível 2.

### 12.6 A lista

1. Clique numa área vazia. Em **Visualizações**, clique em **Matriz**.
2. **Linhas**: arraste, nesta ordem, **Recuperacao → Grupo**,
   **Unidade Geradora → SISTEMA** e **Unidade Geradora → N° ITAIPU**.
3. **Valores**: arraste, nesta ordem, **A recuperar**, **Descrição (a recuperar)**,
   **Prevista (a recuperar)**, **Data nova (a recuperar)** e
   **Dias de atraso (a recuperar)**.
   - Renomeie cada uma, clicando duas vezes no nome em Valores: **Documentos**,
     **Descrição**, **Prevista**, **Data nova** e **Dias de atraso**.
   - Em Valores entram só essas medidas. Uma coluna da Unidade Geradora ali faz a lista
     mostrar todos os documentos.
4. Em **Formatar visual**:
   - **Visual → Cabeçalhos de linha → Ícones +/-**: ligue.
   - **Geral → Título**: ligue, com o texto **DOCUMENTOS A RECUPERAR**, fonte 12, negrito,
     cor `#0E1A77`.
   - **Geral → Propriedades**: Largura **1260**, Altura **305**, Horizontal **10**,
     Vertical **410**.
5. Clique no título da coluna **Dias de atraso** para os mais atrasados virem primeiro.
   Clique de novo para inverter.

**Como abrir e fechar:**

- O **+** ao lado de SEM DATA NOVA abre os sistemas, e o **+** de um sistema abre os
  documentos.
- Para um nível inteiro de uma vez, passe o mouse em cima da matriz e use as setas do canto:
  - **Expandir tudo um nível abaixo** (a seta dupla para baixo) desce um nível;
  - **Fazer drill up** (a seta para cima) volta um nível.
- Nas linhas de grupo e de sistema:
  - Prevista é a mais antiga;
  - Data nova é a mais tarde;
  - Dias de atraso é o maior.

### 12.7 Interações

1. Selecione o gráfico e clique em **Formato → Editar interações**.
2. Em cima do cartão e da lista, clique em **Nenhum**. Sem isso, o clique num ponto do
   gráfico filtraria a lista pela data-alvo daquele dia.
3. Clique em **Editar interações** de novo para sair.

Clicar num sistema ou documento da lista filtra o gráfico e o cartão para ele; clique de
novo para desfazer.

### 12.8 Conferir

Com a planilha de 06/11 e o painel aberto em 10/11/2026:

| Onde | O que aparece |
|---|---|
| Cartão | **91**, com o título "68 COM DATA NOVA · 23 SEM DATA NOVA" |
| Lista | SEM DATA NOVA 23, COM DATA NOVA 68, total 91 |
| Gráfico em 10/11/2026 (hoje) | baseline 915, realizado 830: 85 abaixo (91 a recuperar menos 6 adiantados) |
| 31/12/2026 | baseline 1.005, projeção 890 |
| 28/02/2027 | baseline 1.033, projeção 1.014 |
| 31/10/2027, fim do eixo | baseline 1.058, projeção 1.037: vão de 21 |

Em outro dia os números andam, porque o que vence vira atrasado. Aberto em 17/11 com a mesma
planilha, o cartão vai a 95 (66 com data nova, 29 sem).

Para conferir com outra planilha, pelo Excel, na aba Unidade Geradora:

- Se o DocManager rodou no mesmo dia, o cartão é a contagem de códigos com
  **SITUAÇÃO OTD = PENDENTE VENCIDO** (91 na planilha de 06/11).
- Se não rodou, filtre **DATA PREVISTA EMISSÃO** antes de hoje, **DATA 1ª EMISSÃO** vazia e
  **STATUS CONSOLIDADO** diferente de CANCELADO: são os a recuperar. Desses, os que têm
  **DATA-ALVO EMISSÃO** hoje ou depois têm data nova.

**Como ler o gráfico**

- Hoje, a distância entre a linha cheia escura e a clara é o que está a recuperar menos o que
  saiu adiantado.
- A tracejada sobe nas datas-alvo dos pendentes. Um degrau alto é muito documento
  reprogramado para o mesmo dia: na planilha de 06/11, 30 em 28/02/2027 e 12 em 15/02/2027.
- Até dezembro o vão cresce (115 em 31/12) e depois cai de uma vez em fevereiro. Isso
  acontece porque o que estava previsto para novembro e dezembro e foi reprogramado só entra
  na tracejada na data nova.
- No fim do eixo, o vão é o número de documentos sem data nova, menos os previstos para
  depois de out/2027 que já saíram. Na planilha de 06/11 são 2 desses, por isso o vão é 21 e
  os sem data nova são 23.
- **Para a tracejada encontrar a baseline**, os sem data nova precisam ganhar data
  reprogramada no Controle de Documentos, que o DocManager leva para a planilha. Para
  encontrar mais cedo, as datas novas da lista (COM DATA NOVA) precisam ser adiantadas.
- Os filtros do topo valem para os três visuais.
- A página conta pelo dia de hoje. Antes de apresentar, rode o DocManager e clique em
  **Atualizar**. Com a planilha antiga, o realizado fica parado na data dela, e o que venceu
  desde então aparece como atrasado.
- Para mudar o fim do eixo, troque a data do filtro do item 4 do 12.4.

---

## Teste com documentos de exemplo

Para ver as regras funcionando com poucos documentos, sem mexer no painel de verdade.

1. Gere a planilha de teste (ou peça a quem cuida do DocManager):
   `python tools/planilha_teste_curva_s.py "Teste curva S.xlsx"`. Gere no mesmo dia em que
   for conferir, porque a página Projeção conta pelo dia de hoje.
   - A planilha tem 12 documentos fictícios (TESTE-01 a TESTE-12), um para cada regra, na
     aba **Unidade Geradora**, com o mesmo layout da planilha real.
   - TESTE-10 a TESTE-12 são da página Projeção e não aparecem em outubro.
   - A aba **Esperado** traz o que o painel tem de mostrar.
2. No Explorador de Arquivos, copie o `.pbix` e abra a **cópia**.
3. **Página Inicial → Transformar dados** (a setinha) → **Configurações da fonte de dados**.
   Selecione a fonte (o caminho do Doc List Mapping) → **Alterar Fonte...** → **Procurar...**
   → escolha a planilha de teste → **OK** → **Fechar**.
4. **Página Inicial → Atualizar**. Deixe os filtros do topo (sistema, fase, responsável) em
   tudo: os documentos de teste são do sistema "TESTE", fase EXECUTIVO.
5. Escolha **2026 → outubro** e compare com a aba Esperado:

| Dia | ATUAL: previstos × emitidos | OTD: previstos × emitidos |
|---|---|---|
| 01/10 | 0 × 1 | 0 × 1 |
| 08/10 | 0 × 2 | 2 × 2 |
| 15/10 | 3 × 3 | 5 × 3 |
| 22/10 | 4 × 5 | 6 × 5 |
| 28/10 | 6 × 6 | 7 × 6 |

   Na página Unidade Geradora, o cartão em outubro: ATUAL 66,7% (5/6), OTD 42,9% (5/7),
   SAY-DO 100,0% (1/1).
6. Na página **Projeção**, compare com a parte "Página Projeção" da aba Esperado. Com a
   planilha gerada e aberta em 10/11/2026:
   - cartão **3**, título "2 COM DATA NOVA · 1 SEM DATA NOVA";
   - lista: SEM DATA NOVA tem TESTE-05; COM DATA NOVA tem TESTE-09 (data nova 16/11/2026)
     e TESTE-10 (31/03/2027);
   - gráfico em 10/11: baseline 9 e realizado 7. Os 2 de diferença são 3 atrasados menos
     o TESTE-06, que saiu adiantado;
   - no fim do eixo: baseline 12 e projeção 11. O 1 que sobra é o TESTE-05, sem data nova.
7. Feche a cópia sem salvar, ou apague-a.

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
| Cliquei em OTD e a curva S continua na data-alvo | A curva obedece aos botões da própria Página 1, não aos da página Unidade Geradora: passo 10, "Opcional", itens 1 a 3. |
| Na curva S, os emitidos passam muito dos previstos | Confira se a medida **Emitidos Acum** é a do passo 10 (com `SoPrimeiraRevisao`); a versão de 10/11 contava como adiantados os documentos cuja data é de uma revisão posterior. |
| No gráfico da Projeção, o Eixo X mostra Ano, Trimestre… | Na setinha de **Date**, no Eixo X, escolha **Date**, não **Hierarquia de datas** (12.4, item 2). |
| A linha da projeção aparece cheia | Em **Visual → Linhas**, escolha a série da projeção e mude **Estilo da linha** para **Tracejado** (12.4, item 5). |
| A lista da Projeção mostra todos os documentos | Sobrou coluna da Unidade Geradora em Valores: lá só entram as cinco medidas do 12.6. |
| Clicar no gráfico da Projeção esvazia a lista | Falta o 12.7: a interação do gráfico com o cartão e com a lista tem de estar em **Nenhum**. |
| O cartão A recuperar não bate com o PENDENTE VENCIDO da planilha | O DocManager rodou em outro dia: rode hoje e clique em **Atualizar**. |

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
| `Recuperacao` | Os dois grupos da lista da Projeção (SEM DATA NOVA, COM DATA NOVA). Não tem relação: `A recuperar` lê o grupo com `SELECTEDVALUE`. |
| `Baseline (projeto)`, `Realizado (projeto)`, `Projeção (projeto)` | A curva da Projeção. Baseline pela data prevista. Realizado pela 1ª emissão, ou pela prevista se já teve revisão. Projeção é o realizado mais os pendentes na data-alvo que não venceu. |
| `A recuperar`, `A recuperar (título)` | Os que não saíram e cuja data prevista já passou, com e sem data nova. |
| `Descrição (a recuperar)`, `Prevista (a recuperar)`, `Data nova (a recuperar)`, `Dias de atraso (a recuperar)` | As colunas da lista. Ficam vazias para quem não está a recuperar, e isso esconde essas linhas. |
| `Hoje (linha)` | Opcional: a linha vertical de hoje no gráfico da Projeção. |

As situações são gravadas pelo DocManager (KB §27.5 e §27.7). O Power BI só conta.
