# Progress Log

## Session: 2026-10-28

### Current Status
- **Phase:** 1 - Requirements & Discovery
- **Started:** 2026-10-28

### Actions Taken
-

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|

### Errors
| Error | Resolution |
|-------|------------|

### Actions Taken (Phase 1)
- Plugins pedidos ausentes na sessão: clonados othmanadi/planning-with-files e
  mattpocock/skills (leitura), SKILL.md lidas. Cartão do plugin do Matt Pocock oferecido.
- Plano criado com `init-session.sh "OTD Say-do Doc List"`; formato validado
  (`check-complete.sh --validate`: 7 fases).
- Lidos: README.md, CHANGELOG.md, docs/doc_list_mapping.md,
  docs/situacao_emissao_dashboard.md, core/planejamento.py, core/doclist.py.

### Actions Taken (Phases 2 e 3)
- Lidos: services/doclist_update.py, services/doclist_io.py, services/excel_io.py
  (datas), core/normalize.py, services/controle_docs.py, KB §24.12, §24.13, §27,
  core/doclist_periodo.py, testes de data de tests/test_doclist.py.
- Anexos copiados para o scratchpad (dados/ separado de scripts/). Excel
  perfilado com openpyxl; .pbix extraído (PBIR) e DataModel decodificado com
  pbixray num venv isolado (DAX, Power Query, relacionamentos).
- Simulação dos indicadores: scratchpad/scripts/simula_otd.py.
- Experimento de bordas: scratchpad/experimentos/test_bordas_datas.py (6 passed).

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| tests/test_doclist.py + tests/test_controle_docs.py | verdes | 82 passed | ok |
| experimento de bordas (texto, fórmula, prevista, 2ª reprog., baseline) | confirmar leitura do código | 6 passed | ok |

### Actions Taken (Phase 4)
- Árvore de decisões montada; rodada 1 com 7 perguntas (task_plan.md, Key Questions).
- GLOSSARY.md criado na raiz (skill domain-modeling): termos já firmes + ambiguidades
  do pedido. Sem ADR ainda: nenhuma decisão tomada.
- Números para a conversa: scratchpad/scripts/simula_backlog.py e outubro.py
  (out/2026: 48 documentos pela DATA-ALVO, como o painel mostra hoje; 58 pela
  DATA PREVISTA sem cancelados, dos quais 24 vencidos contra 11 de hoje).
- Conferido: nenhum código de documento real nos arquivos versionados.

### Actions Taken (Phase 5)
- Commit b6ee7c0 enviado para origin/claude/intelligent-franklin-g8byqp (.planning/ + GLOSSARY.md).
- Explicação do funcionamento atual e rodada 1 (Q1-Q7) entregues ao usuário no chat.
- Aguardando respostas.

## Session: 2026-10-28 (rodada 1 respondida)

### Actions Taken
- Respostas da rodada 1 registradas em task_plan.md (Key Questions, Decisions Made).
- Novo requisito: tela de sobrescrição (aceitar / não sobrescrever / caso a caso),
  para Doc List e Mapa dos Planos.
- Figura de outubro (hoje x Q2 x Q3) feita com a skill dataviz (paleta verde/azul/
  vermelho validada pelo script: todos os checks passaram), conferida visualmente
  e corrigida (títulos sobrepostos). Arquivo: scratchpad/saida/q2_q3_outubro.png.
- GLOSSARY.md: Data prevista vira a baseline; termos "sobrescrição" e "incidência".

## Session: 2026-10-28 (rodada 2 respondida)

### Actions Taken
- Respostas da rodada 2 registradas (Decisions Made); rodada 3 montada (Q12-Q18).
- Pesquisa: alternar dois visuais no mesmo lugar = indicadores (bookmarks) + painel
  Seleção + botões; TMDL GA, PBIR padrão desde jan/2026 (findings.md).
- Lista dos 15 documentos (prevista = reprogramada) para conferir no Box:
  scratchpad/saida/Lista_15_prevista_igual_reprogramada.xlsx (skill xlsx: Arial,
  colunas a preencher em amarelo, linha de exemplo, validação de data, fórmula de
  dias; recalc.py: 16 fórmulas, 0 erros; conferida em PDF). Fora do Git (dados reais).
- GLOSSARY.md: Backlog, Baseline OTD, Say-do e Situação say-do resolvidos.

## Session: 2026-10-29 (implementação)

### Actions Taken
- Ambiente: venv com requirements + dev; libegl1 instalado para os testes Qt.
  Linha de base: 1090 passed, ruff limpo.
- Ticket 01 (TDD): tests/test_planejamento.py (regra pura, 11 testes) vermelho →
  core/planejamento.py reescrito (Incidencia, aceitas, valores crus). Adaptadores do
  Doc List e do Mapa; DocListSheet/MappingSheet ganharam get_bruto; serviço novo
  services/sobrescricao.py (IncidenciaDoc, log); atualizações do Doc List e do Mapa
  em duas passadas; ControleMemo para não buscar no Controle duas vezes.
  Testes antigos de "vence a mais recente" reescritos para a regra nova.

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| suíte inteira após ticket 01 | verde | 1105 passed | ok |
| ruff check docmanager tests | limpo | All checks passed | ok |
- Ticket 02 (TDD): 6 testes de ponta a ponta no Doc List (aceitar, recusar e não
  perguntar de novo, Controle muda e volta a perguntar, linha apagada da aba,
  adiar, caso a caso) + 1 no Mapa. services/sobrescricao.py ganhou
  DecisaoSobrescricao, aba "Sobrescrições recusadas" (ler/anotar) e `decidir`.
  `decidir_cb` novo em atualizar_doclist e atualizar_mapeamento. Suíte: 1112 passed.
- Ticket 03 (TDD): ui/views/sobrescricao_dialog.py (EscolhaSobrescricao com Aceitar
  todas / Não sobrescrever / Ver caso a caso; CasoACasoDialog com caixas de marcar;
  decidir_sobrescricoes via ponte). Telas do Doc List e do Mapa passam decidir_cb.
  8 testes Qt novos, 2 deles de ponta a ponta pela tela (timer age na janela modal).
- Ticket 04 (TDD): core/doclist.py ganhou e_backlog e classificar_situacao_say_do
  (casos A-H + cancelado); COLUNAS_DOCLIST com SITUAÇÃO OTD e SITUAÇÃO SAY-DO;
  DocListSheet.criar_colunas (anexa no fim, copia estilo, estende autofiltro) usado
  pela atualização e pelo script tools/criar_colunas_situacao_emissao.py.
  Conferido na planilha real (cópia): script criou AA/AB e é idempotente; backlog
  = 67 distintos, OTD com 94 pendentes vencidos (o painel de hoje mostra 62).
- Ticket 05: docs/adr/0001-data-prevista-e-a-baseline.md; KB §24.13 marcada como
  substituída, §24.14 nova (tela de sobrescrição), §27.2 atualizada, §27.5 (faltava,
  o código já citava) e §27.7 nova (OTD e say-do); docs/doc_list_mapping.md,
  docs/controle_de_documentos.md, docs/situacao_emissao_dashboard.md, README,
  texto da tela do Doc List, GLOSSARY (Situação OTD) e CHANGELOG 3.7.0 (parser ok).

### Revisão (skill code-review do Matt Pocock, dois eixos, feita inline sem subagentes)
Ponto fixo: 9c2fff6 (spec e tarefas) → HEAD.

**Standards** (README "Arquitetura", KB §22, baseline de smells do Fowler):
- Violação documentada: a tela importava `core` e `services` direto; o README diz que
  a interface só enxerga backends → passou a importar de `controle_backend` (corrigido).
- Speculative Generality: `ControleMemo.__getattr__`/`__len__` sem uso → removidos.
- Duplicated Code (julgamento): as duas atualizações (Doc List e Mapa) têm a mesma
  forma de duas passadas, sobre planilhas e colunas diferentes. Mantido: a duplicação
  paralela já existia (Diagnóstico, escrita), e a regra em si está num lugar só.

**Spec** (.scratch/otd-say-do/spec.md):
- História 20 parcial: o log não dizia o total de incidências → linha de resumo nova.
- Correção: recusa anotada com o N° ITAIPU deixava de valer quando o Aconex trocava o
  código → a chave agora vale pelos dois códigos (teste novo).
- Correção: texto de fórmula recusado era gravado na aba como fórmula → fica texto
  (teste novo).
- Histórias 31-33 (Power BI) em aberto: ticket 06, depende da rodada 4.
Resultado: 1133 passed, ruff limpo.

## Session: 2026-10-29 (continuação: resposta à Q12)

### Actions Taken
- Skill prototype do Matt Pocock (ramo UI): protótipo descartável com três variantes
  do seletor de visões (A botões no cabeçalho, B abas, C cartões que são botões), cada
  uma com as visões ATUAL, OTD e SAY-DO e os dois cartões. Números reais agregados de
  outubro; HTML só com CSS, gerado por script no scratchpad (não versionado: dados do
  cliente). Conferido em captura: claro, escuro e 390 px; corrigidos barra com
  cantos arredondados embaixo, subtítulo repetido na B, contraste do cartão escolhido
  na C e dos botões no escuro.
- Modelo do .pbix relido para saber como montar: interações da página (o slicer de
  período só filtra o gráfico e o cartão do nível 3), eixo e legenda do gráfico,
  Power Query (colunas novas entram sozinhas). Achado registrado em findings.md.
- Rodada 4 enviada: Q19 (variante e visão inicial; rec. A com segmentação em blocos e
  um gráfico só, abrindo na ATUAL) e Q20 (curva S acumulando desde o começo, previstos
  pela DATA PREVISTA).


### Versão (skill de versionamento do usuário, branch claude/ecstatic-bardeen-yxm9fn)
- Rodada 4 respondida: Q19 = A (abre na ATUAL), Q20 = sim.
- O usuário apontou que a mudança é pequena: pela regra da skill (mesma função
  funcionando melhor + coluna nova = PATCH), a versão é 3.6.1, não 3.7.0. CHANGELOG
  e docstring do script renumerados; `proxima_versao.py --checar 3.6.1` e
  `--checar 3.6.1-rc.1` deram OK. Ensaio = 3.6.1-rc.1 pelo Run workflow do Release
  neste branch, com Pré-lançamento marcado (só depois do OK do usuário).

### Roteiro do Power BI (ticket 06)
- docs/power_bi_otd_say_do.md: 11 passos + antes de começar, conferência pelo Excel e
  tabela de problemas. Ligado a partir do README, docs/doc_list_mapping.md,
  docs/situacao_emissao_dashboard.md, KB §27.7 e da spec. Ticket 06 = done.
- Conferido por script contra o modelo do .pbix e simulado em Python sobre a planilha
  de 28/10 (números no roteiro). Execução dos cliques fica com o usuário.


### Versão de teste publicada
- 3.6.1-rc.1 disparada a pedido do usuário (Actions → Release, workflow_dispatch neste
  branch, Pré-lançamento). Run 40876510834 verde em ~7 min: lint e testes, executável,
  instalador, manifestos e atualizações pequenas a partir da 3.6.0 (~180 KB), da 3.5.1
  e da 3.5.2-rc.1. Release v3.6.1-rc.1 marcado como pré-lançamento, no commit fa1790f.
- Próximo: o usuário testa (Versões de teste) e segue docs/power_bi_otd_say_do.md;
  aprovada a rc, PR para a main e tag v3.6.1 com o OK dele.

### Relato da 3.6.1-rc.1: "permissão negada" ao salvar (2026-10-29)
- Hipótese 1 (arquivo preso pelo próprio app): confirmada no Linux - `_listar_abas` deixava
  o `pd.ExcelFile` aberto até o coletor de lixo (teste vermelho com gc desligado).
- Medido no Windows (workflow temporário diag-windows-salvar.yml): esse arquivo preso NÃO
  impede o `wb.save` do openpyxl (Python compartilha leitura e escrita), mas impede trocar
  o arquivo - e o Excel salva trocando. Errno 13 só com Somente leitura no experimento.
- Correção: `with pd.ExcelFile`; `services/gravacao.py::salvar_planilha` no Doc List e no
  Mapa (3 tentativas, depois motivo: Somente leitura, programa com o arquivo pelo Restart
  Manager, pasta que não aceita gravação). CHANGELOG 3.6.1 e KB §31. Suíte 1145 + 1
  (o teste do Restart Manager só roda no Windows).
- CI caiu 2 de 3 vezes com falha de segmentação: coletor de lixo na thread de trabalho do
  teste do Transpasse destruindo objeto do Qt. Gatilho: o teste novo desligava o coletor;
  origem do lixo: janelas da sobrescrição sem dono nos testes. Correções: o teste coleta
  na hora; `gravacao` sem gc.collect (roda na thread de trabalho); janelas apagadas com
  deleteLater ao responder (no app, com dono, ficavam escondidas para sempre); conftest
  coleta o lixo de todo teste de tela. Suíte 1146 + 1 em 3.13 e 3.12; KB §31.


### Versão de teste 3.6.1-rc.2 publicada
- Release run 40904706198 verde em ~4,5 min no commit 4aae358 (CI verde nele e no 692022e).
  Lint e testes no Windows passaram, inclusive o do Restart Manager (só é pulado fora do
  Windows). Release v3.6.1-rc.2 como pré-lançamento: instalador, manifestos e
  atualizações pequenas a partir da 3.6.1-rc.1 (113 KB), da 3.6.0 (197 KB) e da 3.5.2-rc.1.
- Próximo: o usuário testa salvar (DocManager e Excel com o app aberto); aprovada a rc,
  PR para a main e tag v3.6.1 com o OK dele.

### Power BI: cartão "índice · emitidos/previstos" e curva S pela data-alvo (2026-11-02)
- O usuário mandou o .pbix montado até o passo 9 (lido com pbixray, fora do Git): modelo,
  botões e cartão como o roteiro; curva S ainda com as medidas originais.
- Pedidos: cartão sem título, "índice · emitidos/previstos" nas três visões; curva S =
  documentos com data-alvo no período, previstos até o dia e quantos desses saíram de fato.
- Roteiro: `Indicador (cartão)` reescrita (usa Documentos (visão) com a tabela Situacoes
  filtrada), 5 medidas de texto saem; só `Emitidos Acum` muda (Previstos Acum é a original).
- Números do .pbix enviado (emissões até 26/10), out/2026: cartão ATUAL 75,0% · 30/48, OTD
  57,6% · 31/59, SAY-DO 100,0% · 0/5; curva S em 31/10: 48 previstos e 30 emitidos. O roteiro
  usa os da planilha de 28/10 (77,1% · 28/48; 59,3% · 29/59; 100,0% · 0/5; 48 e 28).


### Curva S, quarta versão (2026-11-10)
- O usuário explicou com o exemplo x/y/z: previstos pela data-alvo (a original); emitidos
  pela data da 1ª emissão (qualquer previsão, como a original) + os previstos do período
  que saíram antes dele, no 1º dia. Ou seja: a "correção" de 10/29 sem restringir os
  emitidos à coorte. Emitidos Acum = conta original + `SairamAntes` (CROSSFILTER None na
  DATA-ALVO), parando em hoje.
- Simulado: .pbix de 11/02 (emissões até 26/10), outubro 1/10 0 x 25, 10/10 23 x 34,
  26/10 33 x 44; planilha de 28/10: 1/10 0 x 25, 10/10 23 x 34, 20/10 32 x 36, 28/10 34 x 37.

### Curva S, quinta versão (2026-11-10, mesmo dia)
- A de 10/11 (todo emitido do período + todos os do período que saíram antes) inflou os
  emitidos nos prints do usuário (ano começa em 85; novembro em 16 com 3 previstos).
- Diagnóstico no .pbix de 11/02: 85 documentos com data-alvo em 2026 e 1ª emissão em
  2024/2025, todos com revisão posterior emitida (a data do Doc List é de revisão
  posterior); outubro: dos 21 emitidos, 10 eram atrasados de meses anteriores.
- Regra R4: quem está na 1ª revisão entra no dia em que saiu (ou no 1º dia se saiu antes);
  quem já teve revisão entra no dia da data-alvo (ou no da emissão, se atrasado); adiantado
  de período seguinte (1ª revisão) entra no dia em que saiu; atrasado de período anterior e
  sem data-alvo não entram. Simulado: ano 31/03 100 x 91 (antes 192), 26/10 355 x 311;
  outubro 1/10 0 x 3, 26/10 33 x 32. Exemplo x/y/z do usuário continua valendo.

### Curva S pela data prevista, opcional (2026-11-10)
- Pedido: poder escolher a data inicial (baseline) em vez da data-alvo. Roteiro, passo 10,
  "Opcional": botões ATUAL | OTD na Página 1 (cópia não sincronizada da segmentação Visoes,
  sem SAY-DO); Previstos Acum com USERELATIONSHIP na DATA PREVISTA Aux; Emitidos Acum com
  `Alvo` = DATA PREVISTA Aux; título dinâmico opcional. Conferido contra o modelo (19
  fórmulas). Out/2026, planilha de 28/10: ATUAL 48 × 29, OTD 60 × 31 em 31/10.

### Página Projeção (2026-11-10)
- Pedido: desenho de um colega, para ver na projeção o backlog que precisa ser recuperado
  (baseline × realizado × tracejado do replanejado até encontrar a baseline). Discutido antes
  de fazer, com rascunho sobre os dados de 26/10:
  - 81 atrás da baseline: 89 atrasados menos 8 adiantados;
  - dos 89, 31 com data nova e 58 sem;
  - a tracejada não encontra a baseline;
  - lote de 76 documentos em 28/02/27.
- Respostas: Q21, Q22 e Q23 = A. O usuário pediu também uma lista em drill para ver quem
  encaixar e quem adiantar.
- Feito:
  - regras em `tools/planilha_teste_curva_s.py` (`entrada_realizado`, `entrada_projecao`,
    `grupo_recuperar`), mais TESTE-10 a TESTE-12 e a parte "Página Projeção" da aba Esperado;
  - 6 testes novos;
  - passo 12 do roteiro: tabela Recuperacao, 9 medidas, gráfico, cartão, matriz,
    interações, conferir e como ler;
  - seções de teste, problemas e referência do roteiro atualizadas.
- Conferido:
  - .pbix novo (repositório docs-aconex-ug): a Página 1 virou "Curva";
  - as 29 fórmulas passam no conferidor, e as posições não têm conflito;
  - simulado sobre a planilha de 06/11, com o painel aberto em 10/11:
    - 91 a recuperar: 68 com data nova e 23 sem;
    - hoje, 915 × 830;
    - 31/12, 1.005 × 890;
    - fim do eixo, 1.058 × 1.037.
