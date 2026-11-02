# 06: Atualizar a planilha de pendências

**What to build:** `docmanager/services/pendencias_update.py` com
`atualizar_pendencias(config, caminho, *, log_cb, progress_cb, retry_cb, decidir_cb)`:
extrai as questões (03), monta os valores (04), planeja (seção 8.3: novas no topo em ordem
decrescente, trocas e preenchimentos automáticos, apagamentos pela tela com memória em
`pendencias_mantidas.json`), aplica a cor de destaque das impeditivas não fechadas nas novas
e nas existentes (seção 8.4, só o preenchimento), escreve pelo 05 e troca o arquivo pelo 01
com o validador da seção 13. Sem pergunta final: grava direto e devolve o resumo.

**Blocked by:** 01, 03, 04, 05

**Status:** ready-for-agent

- [ ] Fixture 128 pendências + API simulada com 147: 19 novas no topo, decrescentes
- [ ] Colunas manuais intactas (valor e estilo) em todas as existentes
- [ ] Coluna manual com nome de campo de outro módulo não é tocada
- [ ] Destaque: nova impeditiva aberta entra pintada; existente que fecha perde a cor; fonte azul preservada; sem exemplo de destaque na planilha não inventa cor
- [ ] Apagamentos: apagar todas, manter todas (memorizado), caso a caso, janela fechada (mantém sem memorizar); mantido antes não é perguntado de novo enquanto o valor for o mesmo
- [ ] Data real igual ao Aconex não conta como mudança; data real que mudou vira serial
- [ ] Pendência só na planilha: intacta e no log
- [ ] Nada mudou: não grava e avisa
- [ ] Erro em qualquer etapa: arquivo byte a byte igual
- [ ] Sucesso: backup criado e caminho no resumo
