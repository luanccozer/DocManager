---
status: accepted
---

# O painel da Unidade Geradora é um HTML gerado pelo DocManager

Em 2026-11-11 a equipe decidiu abandonar o Power BI do Doc List Mapping e ter o painel da
Unidade Geradora em HTML, como o da Sala Segura e RTA que outra equipe fez. O DocManager
passa a gerar esse HTML no módulo Doc List Mapping: lê a planilha e a base do Aconex, calcula
tudo com as regras que já atualizam a planilha (`core/painel_ug.py`) e grava um arquivo único,
com os dados e as bibliotecas de gráfico embutidos, que abre sem internet e pode ser salvo no
Box. O JavaScript da página só filtra, conta e desenha.

## Considered Options

- **HTML que lê o Excel no navegador** (o caminho da Sala Segura e RTA, com SheetJS): não
  precisa do DocManager para atualizar, mas o painel da UG depende do histórico do Aconex
  (status real em cada data, ciclos de envio e retorno, 1ª emissão, corte de 19/08/2024).
  Refazer essas regras em JavaScript duplicaria motores testados e divergiria deles; e ler
  95 mil linhas no navegador a cada abertura é lento.
- **HTML fixo + arquivo de dados gerado pelo DocManager**: separa o código dos dados, mas são
  dois arquivos para manter juntos, e o navegador não deixa a página ler um arquivo ao lado sem
  a pessoa escolher.
- **Continuar no Power BI**: a equipe quer sair dele.

## Consequences

- Atualizar o painel é rodar o DocManager (o usuário: "pelo menos por enquanto"). Quem só
  abre o arquivo vê os dados do dia em que foi gerado; o cabeçalho diz de quando são a base e a
  planilha.
- O arquivo tem dados do cliente: nunca entra neste repositório (é público). O modelo e as
  bibliotecas, sim (`dashboard/recursos/`, no `.spec`).
- As bibliotecas vão embutidas (Chart.js 4.4.4 e chartjs-plugin-datalabels 2.2.0, MIT, com o
  cabeçalho de licença): a rede corporativa pode bloquear CDN, e o arquivo tem de abrir no Box.
- O plano do passado não existe em lugar nenhum: o Aconex reconstrói o status de cada data,
  mas as datas de planejamento são só as da planilha de hoje.
