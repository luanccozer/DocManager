# Histórico de versões

Este arquivo é a **fonte única** das novidades: a seção "O que há de novo" da
tela inicial lê o bloco da versão instalada, e o GitHub Actions usa o mesmo
bloco como descrição do Release. Ao preparar uma versão, acrescente o bloco
dela aqui **antes** de criar a tag.

## 3.2.0 - 2026-09-30

- Planilhas de comissionamento (nível 3): os status "Aguardando Editável" e "Reviewed with No Comments" passam a ser reconhecidos. "Aguardando Editável" vale como Para Assinatura (consolidado APROVADO) e "Reviewed with No Comments" como Não Aprovado (consolidado NÃO APROVADO), no Mapa, no Doc List, no Status Documentos, no Histórico, no Dashboard e nos Relatórios. A coluna STATUS continua mostrando o rótulo do Aconex.
- Doc List: as colunas de data (DATA-ALVO EMISSÃO, DATA PREVISTA, DATA REPROGRAMADA, DATA ÚLTIMA EMISSÃO e DATA 1ª EMISSÃO) saem no formato Data do Excel, e não mais Personalizado, e o Power BI as lê como data. Data digitada como texto vira data, e texto que não é data é apontado no log.
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
