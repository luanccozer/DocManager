# 07: Módulo "Pendências"

**What to build:** um módulo novo na barra lateral e na tela inicial (não uma aba da
Extração Aconex), `ui/views/pendencias_view.py`, no molde da `TranspasseView`: um
`FileSelector` sem seletor de aba cujo `on_change` dispara a `RunBar`, e o log. Ao escolher a
planilha, busca a API e já grava (sem "Gravar?"). Credenciais do cadastro que já existe (o
primeiro usuário, como a extração sem janela); sem nenhum, abre `credenciais_dialog.cadastrar`.
Registrar em `VIEWS` (`main_app.py`) e `MODULOS` (`home_view.py`), ícone `file-spreadsheet`.
Generalizar os textos da tela de aceite (`sobrescricao_dialog.py`) para a lista de
apagamentos, mantendo o padrão do Doc List e do Mapa idêntico. Detalhes: spec, seção 10.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] Módulo em `VIEWS`, abre nos dois temas; cartão da tela inicial navega até ele
- [ ] Escolher a planilha chama o serviço uma vez com o caminho; o botão roda de novo
- [ ] Sem planilha: só avisa no log
- [ ] Sem credencial: abre o cadastro; cancelado, não chama o serviço
- [ ] `decidir_cb` abre a tela de aceite com os textos de pendências; `retry_cb` chega ao "tentar de novo"
- [ ] Nenhuma pergunta "Gravar?"; no fim, aviso com o resumo
- [ ] Tela de aceite do Doc List e do Mapa sem mudança visível
