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

## Atualizar o painel

O painel é uma foto: mostra os dados do dia em que foi gerado. Para atualizar, gere de novo.

1. Baixe a base do dia (**📥 Extração Aconex**, ou use o `Aconex_Historico_*.xlsx` do dia).
2. Em **📑 Doc List Mapping**, escolha a base e a planilha (e o Controle, se for o caso) e rode
   **Iniciar Atualização**.
3. Clique em **Gerar Painel HTML** e salve na pasta do Box. Salvar sempre com o mesmo nome
   (por exemplo `Painel UG.html`) substitui o anterior, e quem abre pelo Box vê sempre o
   último; salvar com a data no nome guarda o histórico.
4. Quem só consulta abre o arquivo do Box no navegador. Não precisa do DocManager.

O botão chega a todos com a versão 3.7.0 do DocManager. Até ela sair, ele só existe rodando o
código da branch do painel (`run.bat`).

## Rastreamento: como cada documento é achado no Aconex

O mesmo caminho da atualização da planilha (`AconexIndex.resolver`, KB §6):

1. pelo par **Nº ITAIPU + Nº CMI** da planilha;
2. se não achar, só pelo **Nº CMI**;
3. se não achar, só pelo **Nº ITAIPU**;
4. se o código levar a mais de um documento do Aconex (mais de um **Tracking ID**), vale o de
   alteração mais recente.

Achado o Tracking ID, vale o histórico inteiro dele, mesmo que o código tenha mudado no caminho.
O Tracking ID aparece na lista de documentos (e no Excel exportado) e na história de cada
documento, para conferir no Aconex. A **Qualidade dos dados** mostra quantos foram achados só
por um dos códigos e quantos códigos tinham mais de um Tracking ID.

Na base de 10/11/2026: 914 dos 1.092 documentos foram achados (906 pelo par, 8 só pelo
Nº ITAIPU porque o Nº CMI da planilha não confere com o Aconex). Nenhum código tinha mais de
um Tracking ID, nenhum casou com um código antigo, e nenhum Tracking ID ficou com dois códigos
da planilha. Os 178 não achados estão todos NÃO EMITIDO na planilha.

## Como cada número é calculado

Está no próprio painel: o botão **📘 Como ler o painel** no alto e o **i** ao lado do título de
cada gráfico explicam o que ele mostra e como é calculado. As regras completas, com as funções
do DocManager por trás, estão na KB §34.

## Mudar um texto

Se preferir, mande o texto e como quer que fique: a mudança vale a partir do próximo painel
gerado. Para mudar direto no código:

- **Textos do painel** (títulos, notas, botões): `docmanager/dashboard/recursos/painel_ug.html`.
  Cada texto está em português dentro de `T("...")`. A versão em inglês está na lista `EN`, no
  começo do script, com o texto em português como chave: ao mudar um texto, mude também a chave
  dele ali, senão o inglês volta a mostrar o português.
- **Explicações do 📘 e do i**: no mesmo arquivo, a lista `AJUDA` (para cada item: o id, a aba,
  o título e o texto em português, o título e o texto em inglês).
- **Botão e quadro da tela do DocManager**: `docmanager/ui/views/doclist_view.py`, com as
  traduções em `docmanager/ui/recursos/idiomas/es.json` e `en.json`
  (`python tools/textos_da_interface.py --faltando es` lista o que faltar).

Depois de mudar, gere o painel de novo: o arquivo leva o modelo do momento em que é gerado.
`pytest tests/test_painel_ug.py` confere que a página continua sendo montada.

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
| 🛠️ Esforço da engenharia | **Antes e depois de uma data** (reemissões, aprovações, prazos e não aprovados aguardando, em duas janelas de mesma duração), envios à Itaipu por tipo (1ª emissão, reemissão, emissão final), retornos por status, prazo de reemissão da CMI, prazo de análise da Itaipu, taxa de aprovação dos retornos, em que revisão cada documento foi aprovado, há quanto tempo cada um espera, envios por responsável | Histórico do Aconex |
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
