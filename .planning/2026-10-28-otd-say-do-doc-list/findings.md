# Findings & Decisions

## Requirements

Do pedido recebido (`instruções.txt`) e da mensagem do usuário:

- R1. "A data reprogramada para de atualizar a data inicial." Ao reprogramar, a data
  original fica preservada; o documento reprogramado aparece em OUTRO gráfico, como
  BACKLOG. Objetivo: lastro do que atrasou e qual é o novo compromisso dos atrasados.
- R2. Dois indicadores de OTD: **Baseline OTD** e **Backlog Say-do**.
  - OTD (on-time delivery): contra a data original. Ex.: previsto 1-out.
  - Say-do ("falar-fazer"): quando perde a data e assume outra (ex.: 1-nov), o
    documento entra no say-do, que mede se o NOVO compromisso foi cumprido.
  - Cálculo dado: 100 previstos = 100%; atrasou 10 de 100 → OTD 90%. Say-do idem,
    com a base = só os reprogramados (3 reprogramados = 100%).
- R3. No print, as anotações amarelas pedem: "BL OTD: xx % (calculado com o total
  previsto e quanto fizemos. Pode considerar o que está previsto como ok)" e
  "Say do: xx % (calculado com o total previsto com base na data reprogramada e
  quanto fizemos. Pode considerar o que está previsto como ok)". No gráfico
  DOCUMENTOS PARA EMISSÃO, o filtro de período mostra "2026 (Ano) + outubro (Mês)"
  com a anotação "2026 (Ano) + Outubro - Say-do".
- R4. O usuário não lembra o que acontece hoje com: data reprogramada, datas
  digitadas à mão na DATA PREVISTA do Doc List, e afins. Quer entender isso primeiro.

## Research Findings

### Mapa do módulo (docs/situacao_emissao_dashboard.md §2)
- Fachada `docmanager/doclist_backend.py`; núcleo `core/doclist.py`,
  `core/planejamento.py`, `core/mapping.py`, `core/kpis.py`; I/O
  `services/doclist_io.py`; orquestração `services/doclist_update.py`.
- Colunas achadas pelo TEXTO do cabeçalho (âncora `N° ITAIPU`, U+00B0). Ordem não
  importa; renomear quebra. Coluna ausente só gera aviso (retrocompatível).

### Regra de datas hoje (core/planejamento.py:39-58, core/doclist.py:302-329)
- `DATA PREVISTA EMISSÃO`: vem do Controle (`DATA PREVISTA DE EMISSÃO ACONEX`).
  **Vence a mais recente** entre planilha e Controle (planejamento.py:48-51).
  Consequência: se o Controle replaneja para FRENTE, a data original da planilha
  é SOBRESCRITA. Se a pessoa digita uma data mais antiga que a do Controle, o app
  troca pela do Controle. Se digita uma data MAIS NOVA que a do Controle, fica a
  digitada. Ou seja: a DATA PREVISTA hoje NÃO é uma baseline congelada.
- `DATA REPROGRAMADA`: vem da coluna `REPROGRAMAÇÃO` do Controle, mas **só preenche
  célula vazia** (planejamento.py:53-54). O que a equipe digitou nunca é
  sobrescrito; mas também: depois de preenchida, uma reprogramação NOVA no Controle
  não chega mais à planilha.
- `DATA-ALVO EMISSÃO`: calculada, sempre sobrescrita = REPROGRAMADA se houver,
  senão PREVISTA (planejamento.py:56; doclist.py:125-127).
- `None` em prevista/reprogramada significa "não mexer na célula" (nunca apaga).
- Origem da regra: decisão do usuário em 2026-07-28 ("a lógica do Doc List é
  melhor"), unificada para Mapa e Doc List (KB §24.13).

### Situação de emissão (core/doclist.py:140-193)
- Régua = `DATA 1ª EMISSÃO` (primeira submissão "Em Processo" da revisão 0A, ou a
  mais antiga se não houver 0A; reenvio da mesma revisão vale o mais recente).
- Baldes comparam a 1ª emissão (ou HOJE, se pendente) com a **DATA-ALVO**, ou seja,
  com a reprogramada quando existe. CANCELADO > SEM PLANEJAMENTO > emitido/pendente.
- `DIAS DESVIO EMISSÃO` = 1ª emissão − data-alvo (negativo = adiantado).
- Consequência para o pedido: hoje o gráfico "DOCUMENTOS PARA EMISSÃO" já é,
  na prática, um **say-do** para quem foi reprogramado (mede contra o compromisso
  novo) misturado com **OTD** para quem não foi. Não existe medida contra a data
  original de quem foi reprogramado.

### Colunas calculadas x manuais (core/doclist.py:89-94)
- Calculadas (sobrescritas): data_alvo, emitido_nao_emitido, data_ultimo_status,
  revisao, data_primeira_emissao, situacao_emissao, dias_desvio_emissao,
  status_real, status_emissao, status_consolidado, com_itaipu, predecessor,
  resumo_quantidades.
- Manuais (nunca tocadas pelo app): grupo, sistema, nivel, fase_projeto,
  responsavel, observacao, data_reprogramada (a doc diz isso), e a DATA PREVISTA
  só é tocada quando o Controle tem data mais recente.

### Power BI (docs/situacao_emissao_dashboard.md §4, levantado em 2026-09-16)
- Uma tabela `Unidade Geradora` (aba homônima do xlsx). Sem tabela calendário;
  auto date hierarchy sobre `DATA-ALVO EMISSÃO`.
- "DOCUMENTOS PARA EMISSÃO": eixo `DATA-ALVO EMISSÃO` → Dia, Y = contagem de
  `N° ITAIPU`, legenda = `SITUAÇÃO EMISSÃO` (no print: EMITIDO NO PRAZO, PENDENTE
  NO PRAZO, PENDENTE VENCIDO).
- Slicer de período = `DATA-ALVO EMISSÃO` Ano + Mês (o "2026 (Ano) + outubro (Mês)").
- Pendente conferir no .pbix atual se algo mudou desde 2026-09-16.

### Pipeline de gravação (services/doclist_update.py:148-274)
- Por linha de documento (nível 2), nesta ordem:
  1. `normalizar_data` nas colunas manuais DATA PREVISTA e DATA REPROGRAMADA
     (doclist_update.py:187-192): texto '15/10/2026', serial ou formato
     personalizado vira data do Excel. Texto que não é data ('A DEFINIR') fica e
     só é apontado no log.
  2. `resolver_datas_doclist` (doclist_update.py:203-207) com o que está na célula
     e a linha casada no Controle.
  3. Grava DATA PREVISTA só se `datas.prevista` veio (célula vazia ou Controle mais
     recente) (doclist_update.py:208); grava REPROGRAMADA só se a célula estava
     vazia e o Controle tem uma (doclist_update.py:211); DATA-ALVO sempre
     (doclist_update.py:214), inclusive apagando se não houver mais data.
  4. `processar_documento(... data_prevista=datas.data_alvo ...)`: os KPIs e
     atrasos internos usam a DATA-ALVO (doclist_update.py:219-221).
  5. SITUAÇÃO EMISSÃO e DIAS DESVIO contra a DATA-ALVO (doclist_update.py:223).
- Nível 1 (grupo): limpa DATA-ALVO e o bloco de aderência (doclist_update.py:92-111).

### Casos de borda que o código deixa passar (para a conversa)
- Texto não-data numa coluna de data (ex.: 'A DEFINIR' na REPROGRAMADA):
  `get_data` devolve None (doclist_io.py:110-114; normalize.py:81-109), então o
  app trata a célula como VAZIA e, se o Controle tiver data, ESCREVE POR CIMA do
  texto. O comentário de `normalizar_celula_data` diz "não apaga", mas o passo 3
  apaga.
- Fórmula numa coluna de data: `normalizar` pula fórmula, mas `get_data` lê a
  string da fórmula ('=G10+30') → None → também é tratada como vazia e pode ser
  sobrescrita pelo Controle. (Conferir se a planilha real tem fórmula.)
- REPROGRAMADA preenchida uma vez nunca mais acompanha o Controle: se o Controle
  reprograma de novo (2ª reprogramação), a planilha fica com a 1ª.
- PREVISTA acompanha o Controle só para FRENTE (mais recente vence). Se o Controle
  antecipa a data, a planilha mantém a mais tardia.

### Controle de Documentos (services/controle_docs.py)
- Colunas lidas: `DATA PREVISTA DE EMISSÃO ACONEX` (CTRL_COL_DATA_PREVISTA,
  constants.py:148) e a 1ª coluna cujo nome contém `REPROGRAMA`
  (constants.py:150), da ABA selecionada na tela (só uma aba).
- Busca em cascata: código exato → chave frouxa (só alfanuméricos) → "contém";
  linha COM data vence linha sem data (controle_docs.py:201-246).
- Datas: dia/mês inferido por votação por coluna; janela de sanidade 1990-2100.
- `ControleRow.data_ref` = REPROGRAMAÇÃO > DATA PREVISTA (controle_docs.py:62-65).
- O Controle tem UMA coluna de reprogramação: não guarda histórico de
  reprogramações (só o valor atual).

### KB §24.13 e §27 (regras de domínio, conferidas)
- §24.13 (2026-07-28): decisão do usuário unificou Mapa e Doc List. Antes, no Mapa,
  a PREVISTA "só escrevia se vazia" e a REPROGRAMADA "sobrescrevia sempre". Hoje:
  PREVISTA = mais recente vence; REPROGRAMADA = só preenche vazio; data_ref =
  REPROGRAMADA > PREVISTA sobre os valores finais das células.
- §27.6: texto não-data nas colunas manuais "não é apagado", só avisado no log
  (mas ver o caso de borda acima: o Controle pode escrever por cima).

### Planilha real (anexo Doc_List_Mapping.xlsx, aba 'Unidade Geradora') - só agregados
- 4 abas: 'Unidade Geradora' (a do dashboard), 'Grupo Gerador Diesel_v0',
  'Sistema Medição Faturamento' (layout do Mapa, com etapas 1-4) e 'Modelos'.
- Cabeçalho na linha 2, dados da 4 em diante; 26 colunas A..Z. Duas colunas
  'NÍVEL' (A vazia; T é a que o app usa, porque o mapa de cabeçalhos guarda a
  última). Z = 'Column30' (sobra). Sem fórmulas. Sem texto nas colunas de data.
- 1.274 linhas com código: 131 grupos (nível 1) e 1.143 documentos (nível 2);
  1.124 códigos Itaipu distintos (16 códigos repetidos, 19 linhas a mais).
- Documentos: DATA PREVISTA 1.143/1.143; DATA REPROGRAMADA 93; DATA-ALVO 1.143;
  DATA 1ª EMISSÃO 859. DATA-ALVO bate 100% com REPROGRAMADA > PREVISTA.
- SITUAÇÃO EMISSÃO: EMITIDO NO PRAZO 562, EMITIDO COM ATRASO 291, PENDENTE NO
  PRAZO 222, PENDENTE VENCIDO 62, CANCELADO 6.
- FASE: FABRICAÇÃO 739 (732 distintos), EXECUTIVO 373 (364), EXECUÇÃO 31.
- Os 93 reprogramados:
  - 78 com REPROGRAMADA > PREVISTA, 15 com REPROGRAMADA = PREVISTA (reprogramação
    "vazia"), 0 antecipados. Deslocamento típico 70-220 dias (máx. 601).
  - Novas datas concentradas em DOIS dias-mês: 2026-10 (7) e 2027-02 (86):
    parece reprogramação em lote.
  - PREVISTA original deles: jul/2025 a fev/2027 (19 em out/2026, 14 em nov/2026,
    18 em dez/2026, 15 em fev/2027).
  - 81 ainda não emitidos (hoje todos "PENDENTE NO PRAZO", porque a régua é a
    REPROGRAMADA); 11 emitidos ANTES da PREVISTA original; 1 emitido entre a
    PREVISTA e a REPROGRAMADA; 0 depois da REPROGRAMADA.
  - OBSERVAÇÕES vazia em todos (não há registro do motivo).
- Datas de PREVISTA estranhas: 1 em 2023-10, 1 em 2034-06, 1 em 2035-01 (prováveis
  erros de digitação no Controle).

### Power BI (anexo .pbix, decodificado com pbixray) - estado ATUAL
- O dashboard conta `DISTINCTCOUNT(N° ITAIPU)`: os números do print batem
  exatamente com os distintos da planilha (NÃO EMITIDO 282, Aprov. c/ Coment. 234,
  Para Assinatura 214, Aprovado 211, Em Processo 61, Cancelado 6, Informativo 5;
  total 1.124; Fabricação 732; Executivo 364). Logo o .pbix e o .xlsx anexados
  são o MESMO retrato.
- Power Query: lê a aba 'Unidade Geradora' do Excel numa pasta Box; tira a
  coluna A, pula linhas, promove cabeçalho (linha 2), tipa por NOME as colunas
  conhecidas. SITUAÇÃO EMISSÃO e DIAS DESVIO EMISSÃO entram como texto. Coluna
  nova anexada no fim entra sozinha, mas precisa de um passo de tipo para ser data.
- Tabelas: 'Unidade Geradora' + 'Calendario' (CALENDARAUTO) + auto date tables.
- Colunas DAX: `DATA-ALVO Aux` e `DATA 1ª EMISSÃO Aux` (cópias só-data).
- Relacionamentos: Calendario[Date] ← `DATA-ALVO Aux` (ATIVO);
  Calendario[Date] ← `DATA 1ª EMISSÃO Aux` (INATIVO, usado por USERELATIONSHIP).
- Medidas (tabela Calendario):
  - `Previstos` = DISTINCTCOUNT(N° ITAIPU) (filtrado pela DATA-ALVO via relação ativa)
  - `Emitidos` = CALCULATE(DISTINCTCOUNT(N° ITAIPU), USERELATIONSHIP(Calendario[Date], [DATA 1ª EMISSÃO Aux]))
  - `Previstos Acum` / `Emitidos Acum`: acumulado até a data (ALLSELECTED);
    Emitidos Acum fica em branco depois de HOJE.
- Páginas: 'Capa do Projeto'; 'Unidade Geradora' (a do print); 'Página 1' (NOVA
  desde o levantamento de 2026-09-16): curva S "DOCUMENTOS PREVISTOS E EMITIDOS"
  (Previstos Acum x Emitidos Acum por Calendario) + slicer Ano/Mês do Calendario.
- Gráfico "DOCUMENTOS PARA EMISSÃO": eixo DATA-ALVO (Dia), legenda SITUAÇÃO
  EMISSÃO, filtro NÍVEL = 2. Slicer Ano/Mês da DATA-ALVO.
- Consequência: tanto o gráfico do dia quanto a curva S de "previstos" andam junto
  com a reprogramação (usam DATA-ALVO). Reprogramar tira o documento do mês
  original nos dois visuais: é o "a data reprogramada atualiza a data inicial"
  que o pedido quer acabar.
- Não há medida de OTD nem de say-do no modelo.

### Simulação dos indicadores com os dados atuais (scratchpad/scripts/simula_otd.py)
Distintos por N° ITAIPU, sem cancelados (1.118), HOJE = 2026-10-28. Regra usada:
atrasado contra D = emitido depois de D, ou não emitido e HOJE > D; o que ainda não
venceu conta como ok ("pode considerar o que está previsto como ok").
- Baseline OTD (contra DATA PREVISTA), plano inteiro: 736/1.118 = **65,8%**
  (382 atrasados). Só o que já venceu: 507/889 = 57,0%.
- Mesma conta contra a DATA-ALVO (régua de hoje): 68,8%. A diferença (3 pontos) é
  o efeito da reprogramação "escondendo" atraso.
- Say-do (reprogramados com nova data > baseline): 77 documentos; 0 atrasados
  contra a nova data → **100%**, mas só 2 já chegaram à nova data (86 foram para
  28/02/2027). Desses 77: 33 estavam atrasados contra a baseline (backlog de
  verdade), 10 já tinham saído ANTES da baseline, e os outros foram reprogramados
  antes de vencer (reprogramação preventiva).
- Backlog vencido SEM nova data: 62 (são os PENDENTE VENCIDO de hoje). Vencido COM
  nova data: 32.
- Out/2026 (o mês do filtro no print): baseline 58 documentos, 24 atrasados →
  OTD 58,6%; say-do: 7 reprogramados para outubro, 0 atrasados → 100%.

### Sinais de que a baseline JÁ se perdeu em parte
- 15 documentos (eBOP, EXECUTIVO) têm DATA PREVISTA = DATA REPROGRAMADA =
  28/02/2027. Ou a PREVISTA foi empurrada para a data nova (regra "mais recente
  vence" copiando o replanejamento do Controle), ou eles entraram na lista já com
  essa data. Não dá para saber pela planilha; só pelo histórico de versões do
  arquivo (Box) ou do Controle.
- 12 documentos JÁ EMITIDOS têm DATA REPROGRAMADA (quase todos 28/02/2027, NEP,
  EXECUTIVO; vários "Não Aprovado" em 0B/0C/0D). A reprogramação ali parece ser a
  data da PRÓXIMA revisão/aprovação, não da 1ª emissão. Para OTD de 1ª emissão,
  isso é ruído.
- Datas mais repetidas na PREVISTA: 20/03/2026 (56 docs), 05/09/2025 (26),
  20/12/2024 (23): planejamento em lote, normal.

### Comportamento confirmado rodando o código (experimento fora do repo)
`scratchpad/experimentos/test_bordas_datas.py`, usando os helpers de
`tests/test_doclist.py` e um Controle de verdade (`ler_controle`). 6/6 passaram:

| Planilha antes | Controle | Planilha depois |
|---|---|---|
| REPROGRAMADA = 'A DEFINIR' | reprog 15/12/2026 | REPROGRAMADA = 15/12/2026 (o texto some) |
| REPROGRAMADA = fórmula `=DATE(2026,12,1)` | reprog 15/12/2026 | REPROGRAMADA = 15/12/2026 (a fórmula some) |
| PREVISTA digitada 01/03/2026 | prevista 01/09/2026 | PREVISTA = 01/09/2026 (a digitada some) |
| PREVISTA digitada 01/12/2026 | prevista 01/09/2026 | PREVISTA = 01/12/2026 (a digitada fica) |
| REPROGRAMADA digitada 10/11/2026 | reprog 15/12/2026 | REPROGRAMADA = 10/11/2026 (a 2ª reprogramação do Controle nunca chega) |
| PREVISTA 01/03/2026 | prevista 28/02/2027 (replanejou na coluna errada) | PREVISTA = 28/02/2027 (a baseline some) |

Os testes do repo continuam verdes: `tests/test_doclist.py` + `tests/test_controle_docs.py`
= 82 passed. Os dois primeiros casos contradizem o comentário de
`normalizar_celula_data` ("não apaga") e não têm teste no repo.

### Outubro/2026, o mês do print
- Pela DATA-ALVO (o painel hoje): 48 documentos distintos (28 emitidos no prazo,
  11 pendentes vencidos, 9 pendentes no prazo). Bate com as barras do print (o dia
  31, com 4, fica cortado à direita).
- Pela DATA PREVISTA, sem cancelados: 58 (28 emitidos no prazo, 24 pendentes
  vencidos, 6 pendentes no prazo); 18 deles foram reprogramados para frente.
- Backlog proposto (reprogramada > baseline e não saiu até a baseline): 67 no
  total, 5 com nova data em out/2026 e 62 em fev/2027.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
- Scripts de análise e o experimento de bordas ficaram só no scratchpad da sessão
  (temporário, não versionado): `scripts/simula_otd.py`, `scripts/simula_backlog.py`,
  `scripts/outubro.py`, `experimentos/test_bordas_datas.py`. As regras que eles
  aplicam estão descritas acima; o experimento vira teste de verdade na implementação.
- Skill planning-with-files: /home/user/othmanadi/planning-with-files/skills/planning-with-files/SKILL.md
- Skills Matt Pocock: /home/user/mattpocock/skills/skills (grilling, grill-with-docs, domain-modeling, to-spec, ask-matt)
- Anexos: /root/.claude/uploads/fd3ba3ca-0e16-5d25-86e3-62f00a653964/ (pbix, xlsx, instruções)
