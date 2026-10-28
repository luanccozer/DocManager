# Task Plan: Doc List Mapping - datas de planejamento, Baseline OTD e Backlog Say-do

## Goal
O usuário entende como o DocManager atualiza hoje o Doc List Mapping (em especial DATA PREVISTA, DATA REPROGRAMADA, DATA-ALVO e datas digitadas à mão) e tem, decididos com ele, os requisitos para o pedido de `instruções.txt` (reprogramar não apaga a data original; backlog em gráfico próprio; dois OTDs: Baseline OTD e Backlog Say-do).

## Next Step
Esperar as respostas da rodada 3 (Q12-Q18). Se a fronteira esvaziar, confirmar o entendimento comum e seguir para /to-spec.

## Current Phase
Phase 6

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
- [x] Explicação do funcionamento atual para o usuário
- [x] Commit e push dos arquivos (.planning/, GLOSSARY.md) no branch designado
- **Status:** complete

### Phase 6: Spec e tickets (to-spec / to-tickets), depois das respostas
- [ ] Rodadas seguintes do grilling até a fronteira esvaziar
- [ ] /setup-matt-pocock-skills (issue tracker) antes do /to-spec
- **Status:** in_progress

### Phase 7: Implementação (tdd) e roteiro do Power BI
- [ ] Python: colunas novas e regra de congelamento da data base
- [ ] Power BI: medidas de Baseline OTD e Backlog Say-do + gráfico de backlog
- **Status:** pending

## Key Questions

Árvore de decisões (grilling). Rodada 1 = fronteira atual, enviada ao usuário em
2026-10-28; cada uma com a resposta recomendada.

Rodada 1 (respondida em 2026-10-28):
1. Q1 Baseline = a própria DATA PREVISTA, sem coluna nova → SIM. Mais um requisito
   do usuário: nunca sobrescrever data preenchida; quando o Controle trocaria uma data
   do Doc List (ou do Mapa), abrir tela com "aceitar", "não sobrescrever" e "caso a
   caso" (lista de todas as incidências, escolhendo quais sobrescrever).
2. Q2 → NÃO ENTENDEU. Reexplicar com exemplo e figura (outubro hoje x proposta).
3. Q3 → NÃO ENTENDEU. Reexplicar com exemplos de documentos e a figura.
4. Q4 Baseline OTD → SIM.
5. Q5 → pediu para eu explicar o que entendi do say-do nas instruções.
6. Q6 → SIM, com a tela de sobrescrição: o usuário decide (vale para a 2ª reprogramação).
7. Q7 → SIM. Confirmar: antes de apresentar, rodar o app e atualizar o Power BI.

Rodada 2 (respondida em 2026-10-28):
- Q2 (de novo): gráfico principal no dia da DATA PREVISTA, cor contra ela. Rec.: sim.
- Q3 (de novo): backlog = reprogramada > prevista e não saiu até a prevista. Rec.: sim.
- Q5 (de novo): say-do como entendi das instruções. Rec.: sim.
- Q8 Tela de sobrescrição: o que entra (toda célula preenchida diferente do Controle,
  mais nova ou mais antiga, inclusive texto/fórmula; vazia preenche sem perguntar;
  a tela avisa que trocar a PREVISTA muda a baseline; sem tela, padrão é não
  sobrescrever). Rec.: sim.
- Q9 Lembrar o "não" numa aba da própria planilha até o Controle mudar de novo. Rec.: sim.
- Q10 Os 15 com prevista = reprogramada: recuperar a data original pelo histórico do Box. Rec.: sim.
- Q11 Data da atualização gravada pelo app e mostrada no painel. Rec.: sim.
Respostas: Q2 SIM, e o usuário quer OTD e Say-do no MESMO gráfico, trocando por
botão. Q3 "acho que sim" + pergunta se o gráfico de say-do é o de backlog (é: mesma
coisa). Q5 SIM. Q8 SIM. Q9 "ok", lembrando que quem atualiza é o DocManager
(esclarecer: é o DocManager que grava e lê a aba). Q10: vai conferir no Box; pediu
a lista (gerada: 15 documentos). Q11 NÃO: nada de coluna nova; OBSERVAÇÕES segue manual.

Rodada 3 (enviada em 2026-10-28, aguardando resposta):
- Q12 Um gráfico só com dois botões, OTD e Say-do (indicadores + botões do Power BI);
  Say-do = backlog pela DATA REPROGRAMADA; um filtro de mês para os dois. Rec.: sim.
- Q13 Dois cartões sempre visíveis no lugar das notas amarelas (BASELINE OTD e
  SAY-DO), respondendo a todos os filtros; sem mês = plano inteiro. Rec.: sim.
- Q14 Curva S da Página 1: "previstos" pela DATA PREVISTA. Rec.: sim.
- Q15 Entrega do Power BI: projeto .pbip editado por mim + roteiro curto de
  conferência; sem .pbip, roteiro de cliques. Rec.: .pbip.
- Q16 O app cria sozinho a coluna SITUAÇÃO SAY-DO (no fim da aba) e a aba de
  recusas quando faltarem. Rec.: sim.
- Q17 Registro formal: ADR da data prevista congelada + atualizar KB §24.13 e
  docs/doc_list_mapping.md. Rec.: sim.
- Q18 Onde acompanhar a spec e as tarefas: issues no GitHub do DocManager ou
  arquivos no repositório. Rec.: GitHub.

Fora do grilling (anotado para a spec):
- Power BI: Calendario + relações inativas para DATA PREVISTA e DATA REPROGRAMADA,
  medidas com USERELATIONSHIP (mesmo padrão da medida `Emitidos`).
- Limpeza da planilha: coluna A 'NÍVEL' duplicada, 'Column30', datas 2034/2035 na prevista.

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Plano nomeado em `.planning/2026-10-28-otd-say-do-doc-list/` (init-session.sh da skill) | contrato da skill: o inicializador oficial, uma fase por cabeçalho com status nativo |
| Fatos levantados direto, sem subagente | regra da sessão: não abrir agentes sem o usuário pedir; a skill grilling só exige que fatos sejam trabalho meu |
| Sem /to-spec nesta sessão | a skill exige o grilling fechado e o issue tracker configurado antes |
| Q1: a baseline é a própria DATA PREVISTA EMISSÃO; nada de coluna nova | resposta do usuário (2026-10-28) |
| Data preenchida nunca é sobrescrita sem aceite: tela com aceitar tudo / não sobrescrever / caso a caso | requisito do usuário (2026-10-28); vale para Doc List e Mapa dos Planos; desfaz o "vence a mais recente" da KB §24.13 |
| Q4: Baseline OTD = (previstos no período − atrasados) ÷ previstos; ainda não vencido conta ok; distintos; sem cancelado | resposta do usuário (2026-10-28) |
| Q6: 2ª reprogramação do Controle também passa pela tela; o usuário decide | resposta do usuário (2026-10-28) |
| Q7: o Python grava a situação por documento; o Power BI só conta. Antes de apresentar: rodar o app e Atualizar o Power BI | resposta do usuário (2026-10-28) |
| Q2: gráfico principal no dia da DATA PREVISTA; SITUAÇÃO EMISSÃO e DIAS DESVIO comparam com ela | resposta do usuário (2026-10-28); ele quer alternar OTD e Say-do no mesmo gráfico (virou a Q12) |
| Q3: backlog = DATA REPROGRAMADA depois da DATA PREVISTA e não saiu até a DATA PREVISTA; o gráfico de say-do é o de backlog | resposta do usuário (2026-10-28, "acho que sim") |
| Q5: say-do do mês = backlog com data reprogramada no mês; falha = não saiu até ela; o que não venceu conta ok | resposta do usuário (2026-10-28) |
| Q8: tela de sobrescrição para toda data preenchida que o Controle trocaria (mais nova ou mais antiga, texto, fórmula); vazia preenche sem perguntar; aviso de mudança de baseline; sem tela, não troca | resposta do usuário (2026-10-28) |
| Q9: recusa anotada numa aba da própria planilha, escrita e lida pelo DocManager; pergunta de novo só se o Controle mudar | resposta do usuário (2026-10-28, "ok") |
| Q10: o usuário confere os 15 no histórico do Box; lista entregue (xlsx, fora do Git) | resposta do usuário (2026-10-28) |
| Q11: sem coluna de data da atualização; OBSERVAÇÕES continua manual | resposta do usuário (2026-10-28) |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| Plugins pedidos não estavam ativos na sessão | clonados os repositórios públicos e seguidas as SKILL.md; cartão de instalação do plugin do Matt Pocock oferecido |
