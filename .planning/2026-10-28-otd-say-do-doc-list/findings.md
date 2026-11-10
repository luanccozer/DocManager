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

### Para reexplicar Q2 e Q3 (rodada 2)
- Contagem com a regra do Power BI (código distinto por barra, linhas de nível 2,
  sem cancelados): outubro pela DATA-ALVO = 48 (28 no prazo, 11 vencidos, 9 pendentes
  no prazo), bate com o print; pela DATA PREVISTA = 59 (29 no prazo, 24 vencidos,
  6 pendentes no prazo). 16 reprogramados para depois voltam para outubro; 5 que
  tinham sido reprogramados para outubro saem. Backlog com nova data em outubro: 5
  (dias 30 e 31), todos pendentes no prazo.
- Correção: o Baseline OTD de outubro com essa regra é 35/59 = 59,3% (a rodada 1
  disse 58,6%, contando cada código só na 1ª linha em que aparece).
- Figura: scratchpad/saida/q2_q3_outubro.png (enviada ao usuário; não versionada,
  porque sai dos dados reais).

### Fatos para a tela de sobrescrição (Q1 + Q6)
- A atualização roda numa thread; `ui/ponte.py::na_ui_e_esperar` já deixa a tarefa
  abrir um diálogo e esperar a resposta (é assim que funciona o "Tentar de novo" ao
  salvar). Uma tela no meio da atualização é viável sem mudar a arquitetura.
- `atualizar_doclist` e `atualizar_mapeamento` recebem callbacks (`retry_cb`); a tela
  pode entrar como mais um callback, que recebe a lista de incidências e devolve as
  escolhidas.
- A linha de comando (`docmanager.cli mapa --controle ...`) roda sem tela: precisa de
  um padrão (proposto: não sobrescrever e listar no log). Não existe comando de linha
  de comando para o Doc List.
- O app não tem como saber se uma data foi digitada à mão ou escrita por uma rodada
  anterior: as duas são só o valor da célula. A regra "nunca sobrescrever o digitado"
  vira "nunca sobrescrever célula preenchida sem aceite".

### Power BI: alternar OTD e Say-do no mesmo gráfico (pergunta do usuário na rodada 2)
- O jeito padrão: dois visuais no mesmo lugar do canvas + painel Seleção para
  mostrar/ocultar + um indicador (bookmark) por visual, com a opção "Visuais
  selecionados" + botões ligados aos indicadores (ou o "Navegador de indicadores").
  No modo de edição do Desktop, o botão responde com Ctrl+clique. Um segmentador
  sozinho não troca visual: ele filtra dados, não controla visibilidade.
  Fontes: thedataschool.co.uk (Bookmarking in PowerBI: Toggling between Charts),
  playfairdata.com (Toggle visuals with bookmarks), community.fabric.microsoft.com.
- Um filtro de mês só, para os dois visuais: eixo dos dois = Calendario[Date];
  OTD conta com USERELATIONSHIP para a DATA PREVISTA, Say-do com USERELATIONSHIP para
  a DATA REPROGRAMADA (o padrão que o modelo já usa na medida `Emitidos`).
- Formato dos arquivos: TMDL (modelo semântico em texto) é GA; PBIR é o padrão de
  relatórios novos desde jan/2026; o .pbix anexado já está em PBIR. Não achei
  confirmação de GA do projeto .pbip como um todo (blog do Power BI, posts de
  Rui Romano). Um .pbip deixaria editar medidas, relações e indicadores como texto.

### Power BI: como montar as três visões (protótipo da Q12, 2026-10-29)
- Página 'Unidade Geradora': o slicer Ano/Mês filtra pela hierarquia automática da
  DATA-ALVO EMISSÃO e só age no gráfico DOCUMENTOS PARA EMISSÃO e no cartão do nível 3
  (interação "Nenhum" para o resto). O gráfico: eixo DATA-ALVO (Dia), legenda SITUAÇÃO
  EMISSÃO, contagem distinta de N° ITAIPU, filtro do visual NÍVEL = 2.
- Para OTD e SAY-DO o slicer de período passa para o Calendario (Ano/Mês). Na visão
  ATUAL ele chega à DATA-ALVO pela relação ativa; nas outras a medida troca a relação
  com USERELATIONSHIP (DATA PREVISTA Aux, DATA REPROGRAMADA Aux, colunas novas).
- Um gráfico só, sem indicadores: tabela desconectada 'Visões' (ATUAL, OTD, SAY-DO)
  numa segmentação em blocos, tabela desconectada 'Situações' na legenda e uma medida
  que, pela visão escolhida, filtra a coluna de situação daquela visão (SITUAÇÃO
  EMISSÃO, OTD ou SAY-DO) e troca a relação de data. As cores por categoria ficam
  iguais nas três visões, e os slicers do topo (SISTEMA, FASE, RESPONSIBLE) e o filtro
  NÍVEL = 2 continuam valendo, porque a contagem é na 'Unidade Geradora'. Corrige a
  nota acima ("um segmentador sozinho não troca visual"): ele não troca o visual,
  troca o que a medida conta.
- As variantes B (abas com explicação) e C (cartões que são botões) só saem com três
  gráficos sobrepostos, botões e indicadores: mais cliques e três gráficos para manter
  iguais.
- Power Query: o primeiro "Tipo Alterado" lista Column1..Column23; o que vem depois
  entra como "any" e ganha o nome do cabeçalho em "Cabeçalhos Promovidos" (foi assim
  que SITUAÇÃO EMISSÃO entrou). SITUAÇÃO OTD e SITUAÇÃO SAY-DO entram sozinhas no
  Atualizar; vale um passo de tipo Texto no fim.
- Protótipo (HTML descartável, só no scratchpad, com agregados de out/2026 e NÍVEL = 2,
  sem cancelados): variantes A/B/C × visões ATUAL (48), OTD (59) e SAY-DO (5);
  cartões 59,3% (35 de 59) e 100% (5 de 5). Conferido claro, escuro e celular.

### Power BI: o roteiro (ticket 06, 2026-10-29)
- Cores atuais do gráfico DOCUMENTOS PARA EMISSÃO (visual.json): EMITIDO NO PRAZO
  #1AAB40, EMITIDO COM ATRASO #FDEA21, PENDENTE NO PRAZO = cor 1 do tema CY24SU10
  (#118DFF), PENDENTE VENCIDO #F5012E. Trocar a legenda de campo zera as cores: o
  roteiro manda redigitar os quatro códigos.
- Cartões existentes: número 19 pt negrito azul-marinho (tema, #12239E), rótulo de
  categoria desligado, borda de 1 px raio 6. O roteiro copia o do canto superior
  direito (herda estilo e os filtros NÍVEL = 2 e N° ITAIPU não vazio).
- Notas amarelas do print: dentro do DOCUMENTAÇÃO GERAL, no alto à direita → cartões em
  x 745 e 960, y 98, 200 x 72. Botões da visão em x 895, y 486, 270 x 30 (legenda do
  gráfico vai para baixo para abrir o espaço).
- NÍVEL na planilha só tem 1 e 2; 2 linhas de nível 2 sem N° ITAIPU (DISTINCTCOUNT as
  conta como um valor vazio, como o painel já faz).
- Simulação das medidas sobre a planilha de 28/10 (scratchpad/scripts/
  simula_medidas_pbi.py): out/2026 ATUAL 48, OTD 59 (35 sem atraso, 59,3%), SAY-DO 5
  (100%); plano inteiro 65,7% (735/1.118) e 100% (67/67); só outubro de 2026 tem backlog.
  Curva S com out/2026: hoje 48 previstos x 14 emitidos; nova 905 x 841. 25 documentos
  previstos para outubro saíram antes de 1/10 (o exemplo 10/10 x 30/09 do usuário).
- Conferência do roteiro (scratchpad/scripts/confere_roteiro_pbi.py): 18 fórmulas, 12
  medidas novas + 2 alteradas; toda referência existe no modelo, é criada no roteiro ou
  chega com o Atualizar; posições não cobrem cartões nem segmentações.
- learn.microsoft.com fora da rede da sessão: rótulos da interface em português vêm do
  roteiro de 2026-09-16 (que o usuário já seguiu), de busca e do próprio .pbix.

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

### Power BI: página Projeção (2026-11-10)
- .pbix novo (repositório luanccozer/docs-aconex-ug, 10/11):
  - a Página 1 se chama "Curva" e já tem os botões ATUAL | OTD (segmentação Visoes em
    919,140);
  - as medidas do roteiro estão todas lá, inclusive as obsoletas (cartão e título antigos);
  - o Power Query tira a coluna A (o 1º NÍVEL), pula a linha 1, promove a 2 e pula a 3.
- Planilha de 06/11: 36 códigos do .pbix saíram da aba Unidade Geradora, 29 deles para a aba
  nova "Fora da 18A". O .pbix ainda não tinha sido atualizado com essa planilha.
- Todo documento com data prevista é do nível 2 (o nível 1 não tem data). Há 16 códigos
  repetidos.
- A recuperar com TODAY = 10/11 dá 91, o mesmo número de códigos com SITUAÇÃO OTD =
  PENDENTE VENCIDO na planilha. O cartão é o mesmo balde do DocManager.
- Cores:
  - tema CY24SU10; na Curva, previstos `#12239E` e emitidos `#118DFF` (padrão do tema);
  - no validador de paleta (dataviz), o par passa em daltonismo (ΔE 25,6) e em contraste;
  - só o escuro fica fora da faixa de luminosidade de categorias, de propósito: planejado
    escuro × realizado claro;
  - a projeção usa o azul do realizado, tracejada.
- O vão no fim do eixo é menor que os sem data nova quando há previstos depois do eixo que já
  saíram: 2 na planilha de 06/11, previstos para 2028.
- Os números andam com o dia, porque contam pelo TODAY:
  - 10/11: 91 (68 com data nova + 23 sem);
  - 11/11: 91 (66 + 25);
  - 17/11: 95 (66 + 29).
