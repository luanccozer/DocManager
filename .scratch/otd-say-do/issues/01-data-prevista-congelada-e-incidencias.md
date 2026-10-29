# 01: Data prevista congelada e incidências, no Doc List e no Mapa

**What to build:** ao atualizar o Doc List ou o Mapa dos Planos com o Controle de
Documentos, nenhuma data preenchida (prevista ou reprogramada, inclusive texto e
fórmula) é trocada pelo Controle. Célula vazia continua sendo preenchida. Cada data
que o Controle trocaria vira uma incidência, listada no log (documento, coluna, data
da planilha, data do Controle). Sem decisão disponível, nada é trocado.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Data prevista preenchida e Controle com data mais nova: a planilha não muda e o log lista a incidência
- [x] Data prevista preenchida e Controle com data mais antiga: idem
- [x] Data reprogramada preenchida e Controle com outra: idem
- [x] Texto ("A DEFINIR") ou fórmula na coluna de data: não é apagado; vira incidência
- [x] Célula vazia: recebe a data do Controle, sem incidência
- [x] Data igual à do Controle: nada acontece
- [x] Data-alvo calculada sobre o que ficou nas células
- [x] Vale igual para o Doc List e para a etapa 1 do Mapa dos Planos
