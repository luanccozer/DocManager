# Task Plan: Doc List Mapping - datas de planejamento, Baseline OTD e Backlog Say-do

## Goal
O usuário entende como o DocManager atualiza hoje o Doc List Mapping (em especial DATA PREVISTA, DATA REPROGRAMADA, DATA-ALVO e datas digitadas à mão) e tem, decididos com ele, os requisitos para o pedido de `instruções.txt` (reprogramar não apaga a data original; backlog em gráfico próprio; dois OTDs: Baseline OTD e Backlog Say-do).

## Next Step
Commit e push; entregar a explicação e a rodada 1. Depois: esperar as respostas e montar a rodada 2.

## Current Phase
Phase 5

## Phases

### Phase 1: Requirements & Discovery
- [x] Ler `instruções.txt` e o print do dashboard
- [x] Ler README, CHANGELOG, docs/doc_list_mapping.md, docs/situacao_emissao_dashboard.md
- [x] Carregar as skills pedidas (planning-with-files, mattpocock/skills) direto dos repositórios
- **Status:** complete

### Phase 2: Fatos do código (como o Excel é atualizado hoje)
- [x] Regra de datas: core/planejamento.py, core/doclist.py
- [x] Pipeline: services/doclist_update.py, services/doclist_io.py
- [x] Leitura do Controle de Documentos: services/controle_docs.py
- [x] KB §24.13 e §27 (regras de domínio)
- [x] Testes que fixam o comportamento (tests/test_doclist.py) + experimento de bordas
- **Status:** complete

### Phase 3: Fatos dos dados (Excel real + Power BI)
- [x] Doc_List_Mapping.xlsx: abas, cabeçalho, preenchimento das colunas de data
- [x] Quantos documentos têm reprogramada, prevista, alvo; casos estranhos (texto em coluna de data, reprogramada < prevista, etc.)
- [x] .pbix: visuais, campos, medidas; de onde saem os números do print
- [x] Simulação de Baseline OTD e Say-do com os dados atuais
- **Status:** complete

### Phase 4: Grill-with-docs, rodada 1 (grilling + domain-modeling)
- [x] Montar a árvore de decisões do pedido
- [x] Rodada 1: perguntas da fronteira, cada uma com resposta recomendada
- [x] GLOSSARY.md com os termos já firmes e as ambiguidades sinalizadas
- **Status:** complete

### Phase 5: Entrega desta sessão
- [ ] Explicação do funcionamento atual para o usuário
- [ ] Commit e push dos arquivos (.planning/, GLOSSARY.md) no branch designado
- **Status:** in_progress

### Phase 6: Spec e tickets (to-spec / to-tickets), depois das respostas
- [ ] Rodadas seguintes do grilling até a fronteira esvaziar
- [ ] /setup-matt-pocock-skills (issue tracker) antes do /to-spec
- **Status:** pending

### Phase 7: Implementação (tdd) e roteiro do Power BI
- [ ] Python: colunas novas e regra de congelamento da data base
- [ ] Power BI: medidas de Baseline OTD e Backlog Say-do + gráfico de backlog
- **Status:** pending

## Key Questions

Árvore de decisões (grilling). Rodada 1 = fronteira atual, enviada ao usuário em
2026-10-28; cada uma com a resposta recomendada.

Rodada 1 (aguardando resposta):
1. Q1 Baseline: congelar a própria DATA PREVISTA (app só preenche vazio)? Rec.: sim.
2. Q2 Gráfico principal (eixo, SITUAÇÃO EMISSÃO, DIAS DESVIO) passa a medir contra a baseline? Rec.: sim.
3. Q3 Backlog = reprogramada > baseline e não saiu até a baseline; entra ao ser reprogramado? Rec.: sim.
4. Q4 Baseline OTD = (previstos no período − atrasados) ÷ previstos; futuro conta ok; distintos; sem cancelado? Rec.: sim.
5. Q5 Backlog Say-do = mesma conta sobre o backlog, pela data reprogramada? Rec.: sim.
6. Q6 Segunda reprogramação: manter a 1ª (como hoje) e avisar no log? Rec.: sim.
7. Q7 Python grava as situações por documento; Power BI só conta? Rec.: sim.

Rodada 2 (depende da 1):
- Data prevista mais nova no Controle depois do congelamento: só log, ou vira reprogramação? (depende de Q1)
- A regra nova vale também para o Mapa dos Planos? A regra de datas é compartilhada desde a KB §24.13. (depende de Q1)
- Recuperar a baseline perdida (15 docs com prevista = reprogramada; outros empurrados pelo Controle): histórico de versões do Box? (depende de Q1)
- Texto/fórmula nas colunas de data sobrescritos pelo Controle: corrigir junto? (bug achado no experimento)
- Layout: onde ficam os 2 cartões e o gráfico de BACKLOG; a curva S passa a usar a baseline? (depende de Q2, Q3)
- Power BI: medidas DAX com Calendario + relações inativas (USERELATIONSHIP) para baseline e reprogramada. (depende de Q4, Q5, Q7)
- Limpeza: coluna A 'NÍVEL' duplicada, 'Column30', datas 2034/2035 na prevista.
- Antes do /to-spec: /setup-matt-pocock-skills (issue tracker: GitHub Issues ou .scratch local).

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Plano nomeado em `.planning/2026-10-28-otd-say-do-doc-list/` (init-session.sh da skill) | contrato da skill: o inicializador oficial, uma fase por cabeçalho com status nativo |
| Fatos levantados direto, sem subagente | regra da sessão: não abrir agentes sem o usuário pedir; a skill grilling só exige que fatos sejam trabalho meu |
| Sem /to-spec nesta sessão | a skill exige o grilling fechado e o issue tracker configurado antes |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| Plugins pedidos não estavam ativos na sessão | clonados os repositórios públicos e seguidas as SKILL.md; cartão de instalação do plugin do Matt Pocock oferecido |
