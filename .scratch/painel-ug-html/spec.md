# Spec: painel HTML da Unidade Geradora (no lugar do Power BI do Doc List Mapping)

Status: done

Origem: pedido do usuário em 2026-11-11; perguntas da rodada 1 respondidas no mesmo dia.
Vocabulário: `GLOSSARY.md` (seção "Painel"). Decisão de arquitetura:
`docs/adr/0003-painel-html-gerado-pelo-docmanager.md`. Regras: KB §34. Guia de uso:
`docs/painel_ug_html.md`; como cada coisa foi feita: `docs/painel_ug_como_foi_feito.md`. Tarefas em `issues/`.

## Problem Statement

A gestão acompanha a documentação de execução das Unidades Geradoras pelo
`Dashboard - Doc List Mapping` (Power BI). Ele mostra o retrato do dia e a carga
prevista, mas não conta a história dos documentos: a curva S mistura as réguas, não há
visão do esforço da engenharia (quantas emissões e reemissões saem por período) nem de
como as aprovações evoluíram. A equipe quer abandonar o Power BI e ter tudo em HTML, na
família do painel da Sala Segura e RTA que outra equipe fez e que foi bem recebido. A
versão de UG que essa equipe tentou não usa o histórico do Aconex e ficou incompleta.

## Solution

O módulo Doc List Mapping ganha o botão **Gerar Painel HTML**: lê a planilha (o plano e
quais documentos entram) e a base do Aconex (o passado de cada documento), com as mesmas
regras que atualizam a planilha, e grava um HTML único (dados e bibliotecas de gráfico
embutidos, abre sem internet), que pode ser salvo no Box e reaberto. Na família visual
da Sala Segura e RTA (cabeçalho, abas, KPIs clicáveis, árvore de fluxo, lista de
documentos com busca e exportação para Excel, PT/EN), em cinco abas:

1. **Visão geral**: as visões da 1ª página do Power BI (status real, pizzas de
   fabricação, executivo, execução e escopo) mais a árvore do fluxo, KPIs por status
   real, com quem está, grupo × status, tabela por sistema e qualidade dos dados.
2. **Emissões**: o "Documentos para emissão" do Power BI, nas três réguas (atual, OTD,
   say-do), com ano, mês e agrupamento (dia, semana, mês, trimestre, ano), o indicador
   do período, a curva acumulada (meta pela data-alvo, baseline opcional, emitidos e
   aprovados) e a lista de vencidos e próximas emissões.
3. **Progresso**: a tendência como na aba Progresso da Sala Segura, pela linha do tempo
   de cada documento: comparação com uma data (KPIs com variação), resumo em palavras,
   tendência entre datas, evolução da carteira, histórico por data e o que mudou.
4. **Esforço da engenharia**: envios à Itaipu por tipo (1ª emissão, reemissão, emissão
   final), retornos por status, em que revisão cada documento foi aprovado, prazo de
   análise da Itaipu, há quanto tempo cada documento espera e envios por responsável.
5. **Histórico de revisões**: uma linha por revisão, como no Histórico Consolidado (só
   documentos do Doc List), e a **história do documento**: a linha do tempo com o plano,
   o tempo com a Itaipu e com a CMI em cada revisão e o status ao longo do tempo.

Os filtros (grupo, sistema, escopo UG/18A, fase, responsável, status real, com quem
está, situação de emissão) são encadeados e valem para todas as abas.

## Decisões da rodada 1 (2026-11-11)

| Pergunta | Decisão |
|---|---|
| Atualização e distribuição | HTML gerado pelo DocManager, "pelo menos por enquanto" (ADR 0003) |
| Público e idioma | Gestão na reunião semanal; português com botão inglês; sem espanhol |
| UG e 18A | Juntos, com filtro de escopo |
| O que é aprovado | Manter o status real: as visões mostram aprovado, com comentários, para assinatura e informativo; "aprovação total" é a soma deles |
| DATA 1ª EMISSÃO antes de 19/08/2024 | Corrigida no DocManager, versão própria (3.6.5) |
| Passado | Só dos documentos do Doc List; histórico das revisões como no módulo Histórico (não o dashboard antigo) |
| Onde fica o HTML | Gerado no módulo Doc List; salvo no Box para reabrir |
| Sala Segura | KPIs clicáveis com lista e exportação, filtros encadeados, tabela por sistema e qualidade dos dados; aba Progresso como modelo da tendência |
| Retorno sobre o protótipo | Pizzas continuam pizza; manter os gráficos e filtros (ano, mês...) da 1ª página do Power BI; "tendência" é o conceito do que se quer ver na curva, não uma projeção matemática |

## User Stories

1. Como gestor, quero ver numa tela se a emissão está em dia com a data-alvo e quanto
   está atrás da baseline.
2. Como gestor, quero o gráfico de status das emissões do Power BI, por ano, mês ou dia,
   nas três réguas, com o indicador do período.
3. Como gestor, quero comparar hoje com uma data passada (a última reunião) e ler em
   palavras o que mudou.
4. Como gestor, quero ver quantos envios a engenharia faz por período e quanto disso é
   reemissão.
5. Como gestor, quero ver como as aprovações evoluíram e quanto a Itaipu respondeu no
   prazo.
6. Como gestor, quero filtrar por grupo, sistema, escopo, fase e responsável, e todos os
   gráficos responderem ao mesmo filtro.
7. Como engenheiro, quero clicar num número e ver a lista dos documentos, com busca e
   exportação para Excel.
8. Como engenheiro, quero abrir a história de um documento: cada revisão, quanto tempo
   ficou com a Itaipu e com a CMI, e o plano.
9. Como quem atualiza, quero gerar o painel no módulo Doc List e salvar no Box.

## Implementation Decisions

- Regras em `core/painel_ug.py` (puro, testado): documentos únicos e associações,
  escopo UG/18A, retrato de hoje (`processar_documento` e as funções de situação da
  planilha), linha do tempo (`snapshots.obter_snapshot_status`, só as mudanças, alinhada
  ao status de hoje), histórico de revisões (`wide` + `delays`, data-alvo como régua da
  1ª emissão) e o tipo do envio.
- Página em `dashboard/painel_ug_html.py` + `dashboard/recursos/` (modelo, Chart.js
  4.4.4 e chartjs-plugin-datalabels 2.2.0, MIT). O JavaScript só filtra, conta e
  desenha; a ordem das listas compactadas é o contrato (teste trava).
- Orquestração em `services/painel_ug.py`, exposta por `doclist_backend.gerar_painel_ug`;
  botão na tela do Doc List (RunBar), salvar com a última pasta lembrada.
- Exportação para Excel escrita no próprio HTML (um .xlsx mínimo, sem biblioteca).

## Testing Decisions

- `tests/test_painel_ug.py`: escopo, tipo do envio, linha do tempo, retrato de hoje,
  histórico com Dias/Atraso, contrato da página, página sem nada da internet, ponta a
  ponta com planilha e base sintéticas.
- `tests/test_ui_telas.py`: o botão gera o arquivo e abre o navegador.
- `tests/test_empacotamento.py`: os recursos vão para o executável.
- Conferência na base real (10/11/2026), sem códigos no repositório: 1.092 documentos,
  as 5 abas sem erro de JavaScript, status de hoje igual ao da planilha.

## Out of Scope

- As outras abas do Doc List (Sistema Medição Faturamento, Modelos, Grupo Gerador Diesel).
- Guardar o plano a cada geração (história da data-alvo): proposto, não feito.
- Logos de verdade no cabeçalho (vão em texto, como no fallback da Sala Segura).

## Comments

- 2026-11-11: protótipo descartável (gráficos próprios, projeção linear) recusado pelo
  usuário; substituído por esta versão na família da Sala Segura. O código do protótipo
  ficou no histórico do Git (commit da spec em `needs-info`) e saiu da pasta.
