# Histórico de versões

Este arquivo é a **fonte única** das novidades: a seção "O que há de novo" da
tela inicial lê o bloco da versão instalada, e o GitHub Actions usa o mesmo
bloco como descrição do Release. Ao preparar uma versão, acrescente o bloco
dela aqui **antes** de criar a tag.

## 3.6.5

- Doc List Mapping: a DATA 1ª EMISSÃO dos documentos emitidos antes de 19/08/2024, quando a submissão no Aconex ainda aparecia como "Para Análise", vinha errada: ficava com a data de uma reemissão posterior, ou vazia. Por isso um documento entregue no prazo podia aparecer como EMITIDO COM ATRASO, e um documento já aprovado como PENDENTE VENCIDO. Rode a atualização do Doc List de novo: a DATA 1ª EMISSÃO, a SITUAÇÃO EMISSÃO e a SITUAÇÃO OTD desses documentos são corrigidas.

## 3.6.4 - 2026-11-09

- Pendências: a equipe pode fazer à mão registros extraoficiais, que não estão no Aconex, no fim da tabela ou logo abaixo dela. O DocManager não mexe nessas linhas, nem no valor nem na cor, e só as desloca para baixo quando entram pendências novas no topo. Antes, uma linha na tabela sem número do Aconex ou qualquer dado abaixo da tabela fazia a atualização recusar a planilha inteira.
- Pendências: na tabela, ponha letras no Issue Number dos registros extraoficiais (GRUPO 01, GRUPO 02...); Issue Number só com números continua sendo pendência do Aconex. Se um número aparece duas vezes, a mensagem diz em quais linhas. Se é maior que o último do Aconex (um registro feito à mão numerado na sequência), o aviso final pede para trocar por letras, antes que o Aconex chegue a esse número e a linha passe a ser atualizada como a pendência dele.
- Pendências: uma linha vazia no fim da tabela (estendida para digitar depois) não impede mais a atualização. Antes de trocar o arquivo, o DocManager também confere que as linhas e as células ficaram na ordem que o Excel exige.

## 3.6.3 - 2026-11-05

- Módulo novo, Upload de documentos, com três opções: Documento novo, Para revisão e Para aprovação. Por enquanto só Para aprovação, e em ensaio: cole a tabela de envio que chega por e-mail (com ou sem o cabeçalho, quantos documentos vierem), escolha o Controle de Documentos e informe o prazo do workflow em dias. O DocManager faz um documento de cada vez, na ordem da tabela: confere o código no Controle (avisa se a última revisão emitida não é 0C), acha o documento no Aconex e mostra tudo o que o robô vai fazer. Nada é enviado ainda.
- Upload de documentos é protegido por senha: o cadeado à direita do nome, na barra lateral, mostra que está bloqueado, e some quando a senha é aceita. Ela é pedida uma vez a cada vez que o DocManager é aberto. Peça a senha ao responsável.
- Upload de documentos: o botão Capturar telas abre o Google Chrome. Faça o envio para aprovação à mão uma vez e, em cada tela do Box e do Aconex, aperte F8 (ou o botão Capturar, no canto): a tecla não fecha os menus abertos, como o mouse faz. Ao fechar o Chrome, o DocManager junta as telas num .zip. É com ele que o robô aprende onde clicar.

## 3.6.2 - 2026-11-02

- Módulo novo, Pendências: atualiza a planilha de mapeamento de pendências de comissionamento direto do Aconex (Campo → Questões). É só escolher a planilha: o DocManager busca as pendências e já grava. As novas entram no topo da tabela, em ordem decrescente; nas que já estão, as colunas do Aconex ficam em dia; as colunas preenchidas à mão nunca são tocadas. Impeditivas que não estão fechadas ficam com o texto em vermelho (sem preenchimento), e voltam ao preto quando fecham. O que a atualização trouxe (pendência nova, célula trocada ou preenchida) fica em azul; o azul da atualização anterior volta ao preto. Numa pendência nova e impeditiva, vale o vermelho. Tabelas dinâmicas, gráficos, coluna oculta e formatação ficam como estavam: abra no Excel para eles se atualizarem.
- Pendências: quando o Aconex não tem mais um valor que está na planilha, o app pergunta antes de apagar (apagar todas, manter todas ou ver caso a caso). O que você mantém não é perguntado de novo enquanto o valor for o mesmo.
- Pendências: se a planilha tiver algo que não dá para deslocar com segurança (fórmula, células mescladas, validação, dado abaixo da tabela...), nada é gravado e a mensagem diz o que foi encontrado.
- Doc List Mapping, Mapa dos Planos e Pendências passam a guardar uma cópia de segurança da planilha antes de salvar, em Documentos\DocManager_Itaipu\backups (as 20 mais recentes de cada arquivo). O arquivo novo é conferido antes de trocar o original: uma falha no meio nunca deixa a planilha pela metade.
- Idioma: a interface sai em espanhol, português ou inglês, como na CMI Suite e no SIG-FT (Configurações → Aparência → Idioma). Na primeira abertura segue o idioma do Windows; trocar vale ao abrir o DocManager de novo. O registro de execução, as mensagens de erro e as colunas das planilhas continuam em português.
- Letra grande: Configurações → Aparência → Letra aumenta todos os textos do app, na hora.
- Ctrl+, abre as Configurações de qualquer tela, como na CMI Suite e no SIG-FT.
- Sugestões do tipo Erro levam, se você deixar marcado, as últimas linhas do diário do app: quem recebe já vê o que aconteceu, sem precisar pedir o diario.log.
- A engrenagem (Configurações) sai da barra lateral e vai para o alto, à direita, como na CMI Suite e no SIG-FT. "Procurar atualizações" passa a ficar só dentro dela (e no Ctrl+K, de qualquer tela).
- As novidades ficam iguais às da CMI Suite: depois de atualizar, a tela inicial mostra uma vez o cartão "O que mudou na versão", que some no "Entendi". Na primeira instalação ele não aparece.
- Sugestões: a lâmpada ao lado da engrenagem abre uma tela para mandar uma ideia, um erro ou uma dúvida sobre o DocManager. Ela abre um rascunho no seu programa de e-mail, com o tipo e a versão do app anotados; nada é enviado sem você clicar em Enviar. O e-mail que recebe fica em Configurações → Sugestões (vazio, o rascunho abre sem destinatário). Texto longo vai pela área de transferência: é só colar.

## 3.6.1 - 2026-10-29

- Doc List Mapping e Mapa dos Planos: uma data já preenchida na planilha (prevista ou reprogramada, digitada à mão ou não) não é mais trocada pela do Controle de Documentos sem você aceitar. Quando o Controle trocaria alguma, o DocManager pergunta: aceitar todas, não sobrescrever ou ver caso a caso, com a lista das datas para marcar quais trocar. Célula vazia continua sendo preenchida pelo Controle.
- A data prevista passa a ser a baseline: o Controle não a empurra mais para frente sozinho, e quem aceitar a troca é avisado de que o atraso passa a ser medido contra a data nova.
- As trocas recusadas ficam anotadas numa aba nova da própria planilha, "Sobrescrições recusadas", e não são perguntadas de novo enquanto o Controle mantiver a mesma data. Fechar a pergunta sem escolher deixa para decidir na próxima atualização.
- Texto como "A DEFINIR" ou uma fórmula numa coluna de data também contam como preenchidos: antes, o Controle escrevia por cima sem avisar.
- Doc List Mapping: duas colunas novas, SITUAÇÃO OTD (o documento saiu na data prevista?) e SITUAÇÃO SAY-DO (o documento reprogramado saiu na data nova?), para os indicadores Baseline OTD e Say-do do Power BI. O app cria as colunas no fim da aba na primeira atualização. A SITUAÇÃO EMISSÃO continua como estava.
- A planilha escolhida na tela não fica mais presa pelo DocManager. Com o app aberto, o Excel podia recusar salvar o arquivo (acesso negado, arquivo em uso), mesmo sem ninguém mais com ele aberto.
- Quando o Windows não deixa salvar o Doc List ou o Mapa, o DocManager tenta de novo por alguns segundos e depois diz o motivo: qual programa está com a planilha aberta, se ela está marcada como Somente leitura ou se a pasta não aceita gravação. Antes dizia sempre "arquivo aberto?".
- Atualização pequena mais rápida: o DocManager confere pelo conteúdo só os arquivos que ela trocou, e os outros pelo tamanho. Antes lia todos os arquivos instalados e a janela ficava minutos parada depois do download; agora mostra "Conferindo os arquivos instalados: X de N".

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
