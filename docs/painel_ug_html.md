# Painel HTML da Unidade Geradora

O painel da UG no lugar do Power BI do Doc List Mapping. Regras na KB §34; decisões na
spec `.scratch/painel-ug-html/spec.md`; arquitetura no ADR 0003.

## Como gerar

1. No DocManager, abra **📑 Doc List Mapping**.
2. Escolha a **Base Aconex** (a extração do dia) e o **Doc List Mapping**, na aba
   *Unidade Geradora*.
3. Rode **Iniciar Atualização** antes, para a planilha estar em dia (datas de
   planejamento, sobrescrições). O painel só lê: não grava nada na planilha nem na base.
4. Clique em **Gerar Painel HTML** e escolha onde salvar. A pasta fica lembrada: escolha
   a do Box uma vez e o próximo painel vai para lá. Leva cerca de 1 minuto.
5. O painel abre no navegador. É um arquivo só, sem nada da internet: dá para reabrir do
   Box depois ou mandar para quem não tem o DocManager.

O cabeçalho diz de qual base e de qual planilha os números saíram. O arquivo tem dados
do cliente: não vai para o repositório do DocManager.

## O que cada aba mostra

Os filtros do alto (grupo, sistema, escopo UG/18A, fase, responsável, status real, com
quem está, situação de emissão) valem para todas as abas e são encadeados: cada um só
oferece o que existe dentro dos outros. Um código conta uma vez, mesmo em várias linhas.
Todo número, barra, fatia ou quadro abre a lista dos documentos, com busca e
**Exportar Excel**; clicar num documento da lista abre a história dele.

| Aba | O que tem | De onde vem |
|---|---|---|
| 📋 Visão geral | Fluxo dos documentos (árvore), KPIs por status real, Documentação geral (status real), com quem está, pizzas de fabricação, executivo, execução e por escopo, grupo × status, tabela por sistema, qualidade dos dados | A 1ª página do Power BI + o painel da Sala Segura |
| 📅 Emissões | Status das emissões nas réguas Atual (data-alvo), OTD (data prevista) e Say-do (backlog), por ano, mês e agrupamento; o indicador do período (aderência, Baseline OTD ou Say-do); curva acumulada (meta pela data-alvo, baseline, emitidos, aprovados); vencidos e próximas emissões | "Documentos para emissão" e "Curva" do Power BI |
| 📈 Progresso | Comparação com uma data (1 semana, 1 mês, 3 meses, início do ano ou outra), KPIs com variação, resumo em palavras, tendência entre datas, evolução da carteira, histórico por data, o que mudou | A aba Progresso da Sala Segura, sobre o histórico do Aconex |
| 🛠️ Esforço da engenharia | Envios à Itaipu por tipo (1ª emissão, reemissão, emissão final), retornos por status, em que revisão cada documento foi aprovado, prazo de análise da Itaipu, há quanto tempo cada um espera, envios por responsável | Histórico do Aconex |
| 🕓 Histórico de revisões | Uma linha por revisão (envio, retorno, status, Dias/Atraso da Itaipu e da CMI) e a história de cada documento | O Histórico Consolidado do DocManager, só para os documentos do Doc List |

## Leituras que confundem

- **Aprovação total** soma aprovado, aprovado com comentários, para assinatura e
  informativo; os KPIs mostram cada um.
- **Na curva acumulada**, o ponto de hoje soma o mês inteiro; a nota embaixo dá os
  números exatos até hoje.
- **Say-do em 100%** com backlog grande quer dizer que as datas reprogramadas ainda não
  venceram.
- **"Todos" os anos** deixa de fora do eixo as poucas datas muito distantes (2034, 2035);
  o aviso diz quantas.
- **Emitidos** contam a 1ª emissão (a revisão 0A, ou a mais antiga); reemissões não
  aumentam essa conta, aparecem no Esforço da engenharia.
