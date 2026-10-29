# 01: Data prevista congelada e incidências, no Doc List e no Mapa

**What to build:** ao atualizar o Doc List ou o Mapa dos Planos com o Controle de
Documentos, nenhuma data preenchida (prevista ou reprogramada, inclusive texto e
fórmula) é trocada pelo Controle. Célula vazia continua sendo preenchida. Cada data
que o Controle trocaria vira uma incidência, listada no log (documento, coluna, data
da planilha, data do Controle). Sem decisão disponível, nada é trocado.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Data prevista preenchida e Controle com data mais nova: a planilha não muda e o log lista a incidência
- [ ] Data prevista preenchida e Controle com data mais antiga: idem
- [ ] Data reprogramada preenchida e Controle com outra: idem
- [ ] Texto ("A DEFINIR") ou fórmula na coluna de data: não é apagado; vira incidência
- [ ] Célula vazia: recebe a data do Controle, sem incidência
- [ ] Data igual à do Controle: nada acontece
- [ ] Data-alvo calculada sobre o que ficou nas células
- [ ] Vale igual para o Doc List e para a etapa 1 do Mapa dos Planos
