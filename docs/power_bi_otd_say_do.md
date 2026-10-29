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
- Dois cartões, **BASELINE OTD** e **SAY-DO**, no lugar das notas amarelas. Eles seguem
  o filtro PERÍODO e os filtros do topo (sistema, fase, responsável).
- **Página 1**: a curva S passa a acumular desde o início do projeto. O filtro de mês só
  escolhe o trecho mostrado, e os previstos passam a contar pela data prevista.

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

```dax
Baseline OTD (cartão) = IF(ISBLANK([Baseline OTD]), "—", FORMAT([Baseline OTD], "0.0%"))
```

```dax
Baseline OTD (título) =
VAR previstos = [OTD previstos]
RETURN
IF(
    ISBLANK(previstos),
    "BASELINE OTD · nada previsto no período",
    "BASELINE OTD · " & (previstos - [OTD atrasados]) & " de " & previstos & " sem atraso"
)
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

```dax
Say-do (cartão) = IF(ISBLANK([Say-do]), "—", FORMAT([Say-do], "0.0%"))
```

```dax
Say-do (título) =
VAR backlog = [Backlog]
RETURN
IF(
    ISBLANK(backlog),
    "SAY-DO · sem backlog no período",
    "SAY-DO · " & (backlog - [Backlog atrasado]) & " de " & backlog & " sem atraso"
)
```

### 5.4 Formato de porcentagem

No painel Dados, clique em **Baseline OTD**. Na faixa **Ferramentas de medida**, clique
no botão **%** e deixe **1** casa decimal. Faça o mesmo em **Say-do**. As medidas
"(cartão)" já saem prontas, como texto.

**Confira:** são 12 medidas novas em Calendario, e nenhuma tem o triângulo amarelo de
erro.

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

4. Em **Visual → Colunas → Cores**, acerte a cor de cada situação. Clique no quadradinho
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
5. Em **Visual → Legenda → Opções → Posição**, escolha uma das posições **Inferior**
   (por exemplo, **Inferior central**). A legenda desce e abre espaço em cima para os
   botões do passo 7.
6. Em **Geral → Título → Texto**, clique no **fx** ao lado da caixa de texto:
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

## Passo 9: os dois cartões

Copie um cartão que já existe, para herdar o estilo: número azul-marinho em negrito e
borda arredondada.

1. Clique no cartão do canto superior direito da página, ao lado do logo da CMI (o que
   mostra o total de documentos). Tecle **Ctrl+C** e **Ctrl+V**: aparece uma cópia.
2. Com a cópia selecionada, em **Criar visual → Campos**, tire o campo que está lá
   (clique no X) e arraste **Baseline OTD (cartão)**.
3. Em **Formatar visual → Geral → Título**:
   - ligue o título;
   - em **Texto**, clique no **fx**, escolha **Valor do campo → Baseline OTD (título)** e
     clique **OK**;
   - use fonte 9, em negrito, na mesma cor azul-marinho do número.
4. Em **Geral → Propriedades**, use Altura **72** e Largura **200**, Horizontal **745** e
   Vertical **98**. É onde estava a nota amarela "BL OTD".
5. Repita os passos 1 a 4 para o Say-do:
   - campo **Say-do (cartão)**;
   - título **Say-do (título)**;
   - Horizontal **960**, Vertical **98**.
6. Recomendado: impedir que os cartões mudem quando alguém clica numa barra ou fatia.
   1. Selecione o gráfico DOCUMENTAÇÃO GERAL.
   2. Na faixa **Formato**, clique em **Editar interações**.
   3. Em cima de cada cartão novo, clique no ícone **Nenhum** (o círculo cortado).
   4. Repita com as três pizzas e com DOCUMENTOS PARA EMISSÃO.
   5. Clique em **Editar interações** de novo para sair. Os cartões antigos já são assim.

Os filtros que vieram com a cópia (NÍVEL = 2 e N° ITAIPU não vazio) podem ficar: as
medidas já contam só o nível 2.

**Confira** com **2026 → outubro** (planilha de 28/10):
- **BASELINE OTD · 35 de 59 sem atraso**, valor **59,3%**;
- **SAY-DO · 5 de 5 sem atraso**, valor **100,0%**.

Num mês sem backlog, o SAY-DO mostra "—". Com a planilha de 28/10, isso vale para todos
os meses de 2026 menos outubro.

---

## Passo 10: a curva S da Página 1

1. Vá para a **Página 1**.
2. No painel **Dados**, em **Calendario**, clique em **Previstos Acum**. Na barra de
   fórmulas, selecione tudo (**Ctrl+A**), cole a fórmula abaixo e tecle **Enter**:

```dax
Previstos Acum =
VAR DataAtual = MAX(Calendario[Date])
RETURN
CALCULATE(
    [Previstos],
    USERELATIONSHIP(Calendario[Date], 'Unidade Geradora'[DATA PREVISTA Aux]),
    FILTER(
        ALL(Calendario),
        Calendario[Date] <= DataAtual
    )
)
```

3. Clique em **Emitidos Acum**, selecione tudo (**Ctrl+A**), cole e tecle **Enter**:

```dax
Emitidos Acum =
VAR DataAtual = MAX(Calendario[Date])
RETURN
IF(
    DataAtual > TODAY(),
    BLANK(),
    CALCULATE(
        [Emitidos],
        FILTER(
            ALL(Calendario),
            Calendario[Date] <= DataAtual
        )
    )
)
```

O que mudou nas duas:
- `ALLSELECTED` virou `ALL`: a curva acumula desde o início do projeto, e o filtro de mês
  só escolhe o trecho mostrado;
- os previstos passam a contar pela DATA PREVISTA, com `USERELATIONSHIP`.

**Confira** com **2026 → outubro** (planilha de 28/10):
- a curva não começa do zero. Em 31/10 os previstos chegam a **905**, e os emitidos ficam
  em **841** (a linha para em hoje);
- antes, a curva mostrava **48** previstos e **14** emitidos. Os 25 documentos previstos
  para outubro que saíram antes de 1/10 (o caso do previsto para 10/10 e emitido em
  30/09) ficavam fora da conta dos emitidos;
- a distância entre as duas linhas é o atraso acumulado.

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
| As cores voltaram ao padrão | Refaça o item 4 do passo 6. |
| O cartão mostra "—" | Não há documento previsto (ou backlog) no período. É o esperado. |
| A curva S ainda começa do zero no mês | Confira se as duas medidas do passo 10 usam `ALL(Calendario)`, e não `ALLSELECTED`. |

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
| Medidas "(cartão)" e "(título)" | O número do cartão (ou "—") e a linha "x de y sem atraso". |
| `Previstos Acum`, `Emitidos Acum` | A curva S, acumulada desde o início. |

As situações são gravadas pelo DocManager (KB §27.5 e §27.7). O Power BI só conta.
