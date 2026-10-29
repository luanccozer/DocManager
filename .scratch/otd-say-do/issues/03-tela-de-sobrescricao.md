# 03: Tela de sobrescrição

**What to build:** quando há incidências, o DocManager pergunta: Aceitar todas, Não
sobrescrever, ou Ver caso a caso, avisando que trocar a data prevista muda a baseline.
No caso a caso, mostra a lista (documento, descrição, coluna, data na planilha, data no
Controle) com caixa de marcar e botões para marcar e desmarcar todas; confirma
trocando as marcadas e recusando as desmarcadas. Fechar a janela = adiar. Vale nas
telas do Doc List e do Mapa dos Planos.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Os três caminhos devolvem a decisão certa
- [ ] O caso a caso mostra todas as incidências e respeita as marcações
- [ ] Fechar sem escolher devolve "adiar"
- [ ] Abre a partir da tarefa em thread, como os outros diálogos do app
