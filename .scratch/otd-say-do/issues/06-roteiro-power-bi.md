# 06: Roteiro de cliques do Power BI

**What to build:** um passo a passo detalhado (onde clicar) para o usuário fazer no
Power BI Desktop: colunas e relações novas no modelo, medidas de Baseline OTD e Say-do,
as três visões no mesmo gráfico com botões (Atual, OTD, Say-do), os dois cartões e a
curva S acumulando desde o início pela data prevista.

**Blocked by:** 04, e as respostas da rodada 4 (layout das três visões e curva S)

**Status:** done

- [x] Roteiro testado contra o modelo atual (tabelas, relações e medidas existentes)
- [x] Inclui como conferir os números contra a planilha

**Notes:** abordagem recomendada na rodada 4 (Q19 = variante A): um gráfico só, com
as tabelas desconectadas 'Visões' (segmentação em blocos) e 'Situações' (legenda) e
uma medida que troca a coluna de situação e a relação de data pela visão escolhida; o
slicer de período passa da hierarquia da DATA-ALVO para o Calendario. Detalhes em
`.planning/2026-10-28-otd-say-do-doc-list/findings.md` ("como montar as três visões").

## Comments

- 2026-10-29: rodada 4 respondida (Q19 = A, abre na ATUAL; Q20 = sim). Roteiro em
  `docs/power_bi_otd_say_do.md`. Conferido por script contra o modelo do .pbix: as 18
  fórmulas só citam tabelas, colunas e medidas que existem, que o roteiro cria ou que
  chegam com o Atualizar (SITUAÇÃO OTD e SAY-DO, pelos cabeçalhos que o DocManager grava);
  parênteses e aspas fecham; posições sugeridas não cobrem cartões nem filtros. As
  medidas foram simuladas em Python sobre a planilha de 28/10 e dão os números do roteiro
  (48 / 59 / 5; 59,3% e 100%; curva S 905 x 841). Os cliques no Power BI ficam com o
  usuário: o Desktop não roda aqui.
