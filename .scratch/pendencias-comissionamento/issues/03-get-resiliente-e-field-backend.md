# 03: GET com retentativa compartilhado e extração do Field (Campo → Questões)

**What to build:** generalizar o laço de retentativa de `workflows_backend._baixar_pagina_wf`
num ajudante em `aconex_backend.py` (espera crescente, 401 renova o token, reconexão) e fazer
os Workflows usá-lo. Criar `docmanager/field_backend.py`, espelhando `workflows_backend.py`,
com as rotas da spec (seção 5): áreas, campos customizados, tipos de questão, questões
paginadas (200 por página, a partir da raiz, `include_child_areas` e `include_shared`) e
conversas com `supportPublicConversation=true`. `extrair_questoes(...)` devolve
`ExtracaoQuestoes(questoes, definicoes, tipos, comentarios_por_issue)`; falha definitiva
levanta exceção (tudo ou nada). Pausa de 250 ms entre chamadas; só GET.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] `tests/test_fluxos.py` verde com os Workflows usando o ajudante
- [ ] O `_baixar_pagina` do register não muda
- [ ] Paginação por `total_pages` e deduplicação por `issue_id` (sessão simulada)
- [ ] 401 renova o token sem gastar tentativa; falha de rede tenta de novo com espera
- [ ] Falha definitiva levanta exceção com o motivo
- [ ] Chamada de conversas leva `supportPublicConversation=true`
- [ ] Sem coluna `Comments` na planilha: nenhuma chamada de conversas
