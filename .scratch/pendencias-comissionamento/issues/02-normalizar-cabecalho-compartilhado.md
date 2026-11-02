# 02: Normalização de cabeçalho compartilhada

**What to build:** mover `doclist_io._norm_cabecalho` para `core/normalize.py` como
`normalizar_cabecalho` (sem acento, maiúsculas, espaços e quebras de linha colapsados) e
usá-la no `DocListSheet` e no módulo de pendências. Comportamento do Doc List inalterado.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Uma função só no repositório (nenhuma cópia em outro módulo)
- [ ] `tests/test_doclist.py` verde sem alteração de expectativa
- [ ] Teste próprio: acento, NBSP, quebra de linha dentro da célula e espaços duplos
