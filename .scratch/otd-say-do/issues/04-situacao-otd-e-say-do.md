# 04: SITUAÇÃO OTD e SITUAÇÃO SAY-DO no Doc List

**What to build:** a atualização do Doc List grava, por documento, a SITUAÇÃO OTD
(contra a data prevista) e, para o backlog, a SITUAÇÃO SAY-DO (contra a data
reprogramada). Backlog = data reprogramada posterior à prevista e a 1ª emissão não
aconteceu até a prevista. Quando as colunas faltam, o app as cria no fim da aba com a
formatação das vizinhas. Linhas de grupo ficam vazias. A SITUAÇÃO EMISSÃO não muda.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Caso A (prevista vencida, reprogramada futura, não emitido): OTD pendente vencido; say-do pendente no prazo
- [ ] Caso B (reprogramado antes de vencer): no backlog
- [ ] Caso C (emitido antes da prevista, com reprogramada): fora do backlog
- [ ] Caso D (reprogramada = prevista): fora do backlog
- [ ] Caso E (vencido sem reprogramada): fora do backlog; OTD pendente vencido
- [ ] Colunas criadas quando faltam; planilha que já as tem não muda de layout
- [ ] Grupo (nível 1) com as colunas novas vazias
