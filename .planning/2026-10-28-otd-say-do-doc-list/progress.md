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
