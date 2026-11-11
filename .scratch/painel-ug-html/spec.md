# Spec: painel HTML da Unidade Geradora (no lugar do Power BI do Doc List Mapping)

Status: needs-info

Origem: pedido do usuário em 2026-11-11. Vocabulário: `GLOSSARY.md` (os termos novos,
como tendência e esforço da engenharia, entram lá quando as perguntas abaixo forem
respondidas). Protótipo descartável em `prototipo/`: gera um HTML com dados reais que
**nunca** entra no Git, porque este repositório é público.

## Problem Statement

A gestão acompanha a documentação de execução das Unidades Geradoras pelo
`Dashboard - Doc List Mapping` (Power BI). Ele mostra o retrato do dia e a carga
prevista, mas não conta a história dos documentos: a curva S mistura as réguas e não
mostra para onde o ritmo atual leva, não há visão do esforço da engenharia (quantas
emissões e reemissões saem por mês), nem de como as aprovações evoluíram e para onde
tendem. A equipe quer abandonar o Power BI e ter tudo em HTML, como o painel da Sala
Segura e RTA que outra equipe fez e que foi bem recebido. A versão de UG que essa equipe
tentou não usa o histórico do Aconex e ficou incompleta.

## Solution (proposta, a confirmar)

Um painel HTML de um arquivo só, gerado pelo DocManager a partir do Doc List Mapping (o
plano e o retrato de hoje) e do Aconex Histórico (o passado de cada documento), com as
mesmas regras que já calculam a planilha. Organizado como uma história em quatro partes:

1. **Onde estamos**: indicadores do dia (documentos, emitidos, aprovados, em processo,
   não aprovados, pendentes vencidos, Baseline OTD, Say-do) e o retrato por fase, grupo,
   sistema e status real.
2. **Como chegamos aqui**: curva S com a data-alvo como meta e a baseline opcional,
   emitidos e aprovados; evolução da carteira mês a mês (máquina do tempo); esforço da
   engenharia (envios à Itaipu por tipo); respostas da Itaipu (veredito e prazo).
3. **O que vem pela frente**: documentos para emissão por mês nas três réguas (atual,
   OTD, say-do), tendência no ritmo recente e o ritmo necessário para cumprir a meta.
4. **Onde agir** (a confirmar): pendentes vencidos, backlog, documentos com a Itaipu
   fora do prazo e não aprovados esperando reemissão, por responsável e sistema.

Todo número e toda barra abre a lista dos documentos (busca e exportação para Excel).

## O que existe hoje (levantamento de 2026-11-11)

### Power BI `Dashboard - Doc List Mapping`

- **Página Unidade Geradora**: cartão do total (nível 2); DOCUMENTAÇÃO GERAL (colunas por
  STATUS REAL, sem ERRO); DOCUMENTOS DE FABRICAÇÃO e DE EXECUÇÃO (pizzas do STATUS
  CONSOLIDADO, fase FABRICAÇÃO e EXECUTIVO); DOCUMENTOS POR ESCOPO (pizza por GRUPO);
  DOCUMENTOS PARA EMISSÃO (colunas por dia do mês escolhido, legenda pela situação, botões
  ATUAL | OTD | SAY-DO) e o cartão do indicador da visão; cartões de contagem com títulos
  herdados do Mapa ("NÍVEL 1/2/3", decorativos); segmentações SISTEMA, FASE DE PROJETO e
  RESPONSIBLE (COE/VENDOR); PERÍODO (ano e mês).
- **Página Curva**: previstos e emitidos acumulados (`Previstos Acum`, `Emitidos Acum`),
  com as mesmas segmentações e os botões de visão.
- **Capa do Projeto**: só imagem.

### Painel HTML da Sala Segura e RTA (outra equipe)

Um HTML que lê a planilha da equipe no navegador (SheetJS + Chart.js), com PT/EN, escolha
de escopo na entrada, KPIs clicáveis que abrem a lista de documentos com busca e
exportação, filtros encadeados, tabela por sistema e um bloco de qualidade dos dados. A
aba de UG lê uma cópia da aba "Unidade Geradora" do Doc List (idêntica, conferido) e:

- não usa o histórico do Aconex: não há aprovações no tempo, esforço nem respostas da
  Itaipu;
- a curva S acumula por mês a data prevista, a data-alvo e a 1ª emissão, sem linha de
  hoje, sem aprovados e sem tendência;
- compara situação de emissão e situação OTD em categorias, sem o tempo; não tem os
  documentos para emissão por período nem os indicadores Baseline OTD e Say-do;
- não separa os sistemas da 18A dos demais.

## Achados nas bases (planilha e extração de 2026-11-10)

1. **Universo.** A aba Unidade Geradora tem 1.111 linhas de documento (nível 2) em 127
   grupos; são 1.092 códigos distintos (16 códigos aparecem em mais de uma linha). Sem os
   6 cancelados, o painel conta 1.086 documentos, como o `DISTINCTCOUNT` do Power BI.
2. **Casamento com o Aconex.** 933 das 1.111 linhas acham o histórico pelo `AconexIndex`
   (914 Tracking IDs). As 178 que não acham são todas NÃO EMITIDO.
3. **Máquina do tempo confiável.** O estado reconstruído por
   `snapshots.obter_snapshot_status` na data da extração bate com o STATUS CONSOLIDADO da
   planilha em 929 de 933 documentos; as 4 diferenças são movimentos posteriores à última
   atualização da planilha. Dá para mostrar o estado da carteira em qualquer data passada.
4. **Ciclos.** `wide.build_wide_table` dá 2.542 ciclos envio → retorno para esses
   documentos: é a base do esforço da engenharia e das respostas da Itaipu.
5. **Defeito na DATA 1ª EMISSÃO.** `kpis.data_primeira_emissao` só reconhece 'Em
   Processo' como envio e ignora o corte de 19/08/2024 (KB §7: antes dele, o envio era
   'Para Análise'). Os 16 documentos emitidos antes do corte ficam com a data de uma
   reemissão posterior, ou sem data: 1 documento já aprovado aparece como PENDENTE
   VENCIDO, 4 aparecem como EMITIDO COM ATRASO sem estar, e nos outros 11 só a data está
   errada. O `gerar_dataset_dashboard` já trata o corte certo.
6. **O plano do passado não está guardado.** O Aconex dá o passado dos documentos, mas as
   datas de planejamento só existem na planilha de hoje. A baseline é estável (ADR 0001),
   então o OTD de um mês passado é reconstruível; a data-alvo de uma data passada não.

## User Stories (rascunho)

1. Como gestor, quero ver numa tela se a emissão está em dia com a data-alvo e quanto está
   atrás da baseline, para saber se o replanejamento resolveu ou só empurrou o problema.
2. Como gestor, quero ver para onde o ritmo atual leva a emissão e a aprovação, comparado
   com a meta, para antecipar a cobrança de recursos.
3. Como gestor, quero ver quantos envios a engenharia faz por mês e quanto disso é
   reemissão, para entender onde o esforço está indo.
4. Como gestor, quero ver como as aprovações evoluíram e quanto a Itaipu respondeu no
   prazo, para separar o que é atraso nosso do que é do cliente.
5. Como gestor, quero alternar a régua (data-alvo, baseline, backlog) nos documentos para
   emissão por mês, como fazia no Power BI.
6. Como gestor, quero filtrar por grupo, sistema, fase e responsável, e todos os
   gráficos responderem ao mesmo filtro.
7. Como engenheiro, quero clicar num número e ver a lista dos documentos, com busca e
   exportação para Excel, para agir sobre eles.
8. Como quem atualiza o painel, quero gerá-lo no mesmo passo em que atualizo o Doc List,
   e mandar um arquivo só para quem não tem o DocManager.

## Implementation Decisions (propostas, a confirmar)

- O DocManager gera o HTML (arquivo único, dados embutidos, biblioteca de gráficos
  embutida, abre sem internet), como o Transpasse de Fase já faz. Reescrever o motor de
  status em JavaScript duplicaria regras testadas e divergiria delas.
- As séries saem de funções puras no `core/` (sem I/O), sobre o histórico do Aconex e as
  linhas do Doc List; o HTML é só apresentação.
- Universo: documento de nível 2, um código conta uma vez, cancelado fica fora.
- Curva S: acumulado mensal pela data-alvo (meta), pela data prevista (baseline,
  opcional), pela 1ª emissão e pelos aprovados (estado consolidado APROVADO no fim do mês,
  reconstruído do Aconex); tendência no ritmo das últimas 13 semanas; linha de hoje.
- Esforço da engenharia: envios à Itaipu (ciclos do `wide`) por mês, separados em 1ª
  emissão, reemissão (revisão com letra) e emissão final (revisão numérica).
- Respostas da Itaipu: retornos por veredito e a parcela dentro do prazo (30 dias na 0A,
  15 nas demais, KB §19).

## Testing Decisions (propostas)

- Cada série testada pelo comportamento, com históricos e planilhas sintéticos
  (`tests/builders.py`), nunca com dados reais.
- Um teste de ponta a ponta gera o HTML de uma planilha sintética e confere os números
  embutidos.
- Conferência manual contra a planilha real antes de publicar, registrada sem códigos.

## Out of Scope

- As outras abas do Doc List (Sistema Medição Faturamento, Modelos, Grupo Gerador Diesel).
- Ler o Controle de Documentos direto no painel (as datas já chegam pelo Doc List).
- Servidor ou hospedagem: o painel é um arquivo.

## Perguntas em aberto (rodada 1, 2026-11-11)

1. Quem atualiza e como o painel chega às pessoas: HTML gerado pelo DocManager
   (recomendado) ou HTML que lê o Excel no navegador, como o da Sala Segura?
2. Público e idioma: gestão em reunião semanal, PT com botão EN? Precisa de espanhol?
3. Escopo: os sistemas terminados em 18A (e o PEM) entram junto, com um filtro UG × 18A?
4. "Aprovado" na curva e nos indicadores é o STATUS CONSOLIDADO APROVADO (inclui aprovado
   com comentários, para assinatura e informativo), como na planilha?
5. Corrigir no DocManager a DATA 1ª EMISSÃO dos emitidos antes de 19/08/2024 (achado 5)?
6. "Versões de passado pelo Aconex Histórico": é reconstruir o passado pelo histórico
   (como no protótipo)? Incluir um "o que mudou desde a última reunião"? E guardar, a cada
   geração, as datas da planilha, para ter a história do plano daqui em diante?
7. Onde fica o HTML gerado: só na máquina e no Box/Teams, ou também no repositório privado
   Docs-Aconex-ug? Os logos da GE Vernova e da Itaipu não estão em nenhum repositório.
8. Do painel da Sala Segura, o que trazer além de KPIs clicáveis com lista e exportação,
   filtros encadeados, tabela por sistema e qualidade dos dados?

## Comments
