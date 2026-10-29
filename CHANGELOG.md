# Histórico de versões

Este arquivo é a **fonte única** das novidades: a seção "O que há de novo" da
tela inicial lê o bloco da versão instalada, e o GitHub Actions usa o mesmo
bloco como descrição do Release. Ao preparar uma versão, acrescente o bloco
dela aqui **antes** de criar a tag.

## 3.6.1 - 2026-10-29

- Doc List Mapping e Mapa dos Planos: uma data já preenchida na planilha (prevista ou reprogramada, digitada à mão ou não) não é mais trocada pela do Controle de Documentos sem você aceitar. Quando o Controle trocaria alguma, o DocManager pergunta: aceitar todas, não sobrescrever ou ver caso a caso, com a lista das datas para marcar quais trocar. Célula vazia continua sendo preenchida pelo Controle.
- A data prevista passa a ser a baseline: o Controle não a empurra mais para frente sozinho, e quem aceitar a troca é avisado de que o atraso passa a ser medido contra a data nova.
- As trocas recusadas ficam anotadas numa aba nova da própria planilha, "Sobrescrições recusadas", e não são perguntadas de novo enquanto o Controle mantiver a mesma data. Fechar a pergunta sem escolher deixa para decidir na próxima atualização.
- Texto como "A DEFINIR" ou uma fórmula numa coluna de data também contam como preenchidos: antes, o Controle escrevia por cima sem avisar.
- Doc List Mapping: duas colunas novas, SITUAÇÃO OTD (o documento saiu na data prevista?) e SITUAÇÃO SAY-DO (o documento reprogramado saiu na data nova?), para os indicadores Baseline OTD e Say-do do Power BI. O app cria as colunas no fim da aba na primeira atualização. A SITUAÇÃO EMISSÃO continua como estava.

## 3.6.0 - 2026-10-27

- O instalador passa a instalar sempre "somente para mim", na pasta do usuário, sem pedir senha de administrador e sem perguntar. É o jeito em que a atualização pequena funciona: as próximas versões chegam em segundos, sem pedir nada ao Windows.
- Quem instalou "para todos os usuários" (Program Files) é passado para "somente para mim" na primeira atualização: o Windows pede a permissão de administrador uma vez, para remover a instalação antiga. Preferências e credenciais continuam.

## 3.5.1 - 2026-10-27

- Versão para conferir a atualização pequena: quem está na 3.5.0 (instalada "somente para mim") deve receber só o que mudou, em segundos, e o DocManager abre de novo sozinho, já na 3.5.1. Nada muda no uso.

## 3.5.0 - 2026-10-27

- Módulo novo, Transpasse de Fase: desenha sozinho, a partir das planilhas, o quadro dia a dia de cada grupo de equipamentos (convocação, inspeção IB, emissão do CCMLC, transpasse de fase e início do comissionamento), com a mesma legenda e as mesmas cores da planilha da equipe. Basta selecionar a planilha de acompanhamento do transpasse e, se tiver, a complementar (controle do início do comissionamento, de onde vêm o início e a coluna Dias).
- O painel abre no navegador e é um arquivo único: dá para mandar por e-mail ou deixar numa pasta para quem não tem o DocManager. Para atualizar depois de mexer nas planilhas, é só gerar de novo.
- Passando o mouse sobre um grupo aparecem as datas, os dias entre cada etapa e há quanto tempo ele está parado. Etapa ainda em andamento aparece pintada até hoje.
- Datas que não fecham (fora de ordem, no futuro, ano digitado errado, texto que não é data ou datas diferentes nas duas planilhas) ficam fora do quadro e aparecem no card do grupo, para corrigir na planilha.

## 3.4.0 - 2026-10-27

- Atualização pequena no método da CMI Suite: o DocManager troca só os arquivos que mudaram com ele mesmo aberto, confere cada um e abre de novo já na versão nova, sem instalador, sem pedido de permissão do Windows e sem esperar o app fechar. Se algo não conferir, tudo volta como estava e ele baixa o instalador completo sozinho. Vale a partir da próxima versão, para quem instalou "somente para mim"; quem instalou para todos os usuários continua recebendo o instalador completo.

## 3.3.0 - 2026-10-26

- Interface nova, em Qt, com o mesmo visual do SIG-FT: barra lateral com ícones, cartões, abas e tabelas redesenhados. Todas as telas e funções continuam as mesmas.
- Tema escuro, claro ou o do Windows, escolhido em Configurações → Aparência e trocado na hora, sem reabrir o app. "Do Windows" acompanha o sistema mesmo com o app aberto.
- Abertura sem tropeço: a tela de carregamento é uma só, do duplo-clique até o app aparecer (antes eram duas telas diferentes, uma depois da outra), e o DocManager abre sempre maximizado.
- Telas mais nítidas em monitores com escala de 125% ou 150%.
- As listas de escolha não mudam mais sozinhas quando a roda do mouse passa por cima delas ao rolar a tela.
- Fechar o DocManager com uma tarefa rodando agora pergunta antes. O padrão é não fechar.
- Extração Aconex → Consulta Rápida: cole uma lista de códigos (Itaipu ou CMI) e veja em segundos o status real e a revisão de cada um, direto da API, sem baixar a base completa. Dá para exportar o resultado no mesmo Excel do Status Documentos.
- Extração Aconex → Baixar por Lista: agora dá para escolher o arquivo. "Com os comentários do Aconex" é o de sempre. "Original, sem comentários" traz a última revisão como o emitente a enviou, sem as marcações da análise.
- Diário do app (Documentos\DocManager_Itaipu\diario.log): registra abertura, fechamento e erros. Se o app fechar sozinho, é nele que se vê o que aconteceu.

## 3.2.0 - 2026-10-23

- Atualização mais leve: a partir da próxima versão, o app baixa só os arquivos que mudaram desde a versão instalada (alguns MB), em vez do instalador inteiro. Quando não dá, baixa o instalador completo sozinho, sem precisar fazer nada.
- O aviso de versão nova abre sozinho ao abrir o app, com o que mudou e o tamanho do download. "Agora não" fecha o aviso, que volta na próxima abertura.
- Se uma tarefa estiver em andamento, o app pergunta antes de fechar para atualizar.
- "Procurar atualizações" ganha o atalho Ctrl+K e sempre responde: se está em dia, o erro, ou por que esta cópia não se atualiza por ali.
- Nas Configurações, a opção "Versões de teste" passa a oferecer também as versões em teste.
- Lista de Sobressalentes com Preço: o status "For Partial Handover" passa a ser reconhecido como aprovação parcial. O STATUS REAL mostra o rótulo do Aconex e o consolidado sai APROVAÇÃO INTERMEDIÁRIA, no Mapa, no Doc List, no Status Documentos, no Histórico, no Dashboard e nos Relatórios; nos indicadores conta como resposta aprovada da Itaipu. A lista é reconhecida pelo título (sobressalentes com preço) ou pelo código terminado em PB021.
- Resumo de quantidades do Mapa e do Doc List: a linha "Aprovação Intermediária" aparece sempre que houver algum documento nessa situação.

## 3.1.1 - 2026-09-30

- Planilhas de comissionamento (nível 3): os status "Aguardando Editável" e "Reviewed with No Comments" passam a ser reconhecidos. "Aguardando Editável" vale como Para Assinatura (consolidado APROVADO) e "Reviewed with No Comments" como Não Aprovado (consolidado NÃO APROVADO), no Mapa, no Doc List, no Status Documentos, no Histórico, no Dashboard e nos Relatórios. A coluna STATUS continua mostrando o rótulo do Aconex.
- Doc List e Mapa dos Planos: as datas saem no formato Data do Excel, e não mais como texto ou Personalizado, e o Power BI as lê como data. No Doc List, as cinco colunas de data (inclusive a DATA-ALVO EMISSÃO); no Mapa, a DATA ÚLTIMA EMISSÃO, que era texto, e a DATA PREVISTA e a DATA REPROGRAMADA da etapa 1. Data digitada como texto vira data, e texto que não é data é apontado no log.
- Mapa dos Planos rodado sem o Controle de Documentos: o atraso trocava o dia e o mês da DATA PREVISTA quando o dia era até 12 (1º de dezembro virava 12 de janeiro). Corrigido.
- Atualização automática corrigida: o instalador desistia quando o app ainda estava fechando, e a versão antiga ficava. Agora ele espera o app sair e, no fim, reabre o DocManager já atualizado.
- Se o Windows pedir permissão de administrador para atualizar e ela for recusada, o app continua aberto e avisa, em vez de fechar sem atualizar.
- Botão "Procurar atualizações" na barra lateral, em qualquer tela. A checagem automática também passa a rodar enquanto o app fica aberto, e não só ao abrir.
- O usuário do Aconex cadastrado nas Configurações passa a aparecer na Extração Aconex. Antes só funcionava cadastrando pela própria Extração.

## 3.1.0 - 2026-09-18

- Instalador oficial: o DocManager passa a ser gerado e publicado pelo GitHub, com instalador próprio. Acabou o passo a passo manual de compilar o executável e zipar a pasta.
- Atualização automática: quando sai uma versão nova, o app avisa, mostra o que mudou e se atualiza com um clique. Funciona com o Zscaler e a VPN ligados.
- Credenciais do Aconex cadastradas no próprio app. Não é mais preciso receber nem editar o arquivo `.env`; quem já tinha um tem o cadastro importado na primeira abertura.
- O Client Secret passa a ser guardado cifrado pelo Windows, na conta do usuário, em vez de ficar em texto puro no `.env`.
- A versão que aparece no título, na barra lateral, na tela de carregamento e na Home passa a vir do próprio programa, e por isso fica sempre certa depois de atualizar.
- As novidades da Home e as notas do Release saem do mesmo arquivo, então mostram sempre a mesma coisa.
- Extração Aconex passa a funcionar com a VPN (GlobalProtect) ligada. O app agora obedece o arquivo PAC da rede, perguntando ao Windows qual proxy usar para cada endereço. Antes ele enxergava só proxy fixo e tentava sair direto, o que a VPN bloqueia.
- Quando a Extração Aconex não conecta, o log passa a mostrar a causa real (timeout, DNS, conexão recusada) e um diagnóstico da rede: proxy do Windows, arquivo PAC, resolução de nome e teste da porta 443. Antes só dizia "sem conexão".

## 3.0.0 - 2026-08-02

- Novo módulo Doc List Mapping: follow-up da lista de documentos com dois níveis e agrupamento por escopo.
- Doc List Mapping traz a Análise por Período - quais documentos estão previstos para emitir nos próximos tempos.
- Busca das datas previstas no Controle de Documentos corrigida e com diagnóstico no log.
- Extração do Aconex retoma de onde parou quando a conexão cai.
- Tela inicial (Home) com os módulos e as novidades.
- Histórico com datas de previsão e reprogramação na revisão 0A.
- Relatório de Fluxos de Trabalho: onde cada documento está e com quem.
