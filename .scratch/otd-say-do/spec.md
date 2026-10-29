# Spec: data prevista como baseline, tela de sobrescrição, Baseline OTD e Say-do

Status: ready-for-agent

Origem: `instruções.txt` (pedido da gestão) e o grilling de 2026-10-28/29, registrado em
`.planning/2026-10-28-otd-say-do-doc-list/`. Vocabulário: `GLOSSARY.md`. Decisão
registrada em `docs/adr/0001-data-prevista-e-a-baseline.md`.

## Problem Statement

Quem acompanha a documentação de execução das Unidades Geradoras não consegue mostrar
o que atrasou. Quando um documento é reprogramado, a data nova toma o lugar da antiga
em todo o painel: o documento sai do mês original e aparece no mês novo como "no
prazo". Pior, a própria data prevista da planilha muda sozinha quando o Controle de
Documentos traz uma data mais nova, e uma data digitada à mão pode ser apagada sem
aviso. A gestão pediu dois indicadores, Baseline OTD (contra a data original) e Say-do
(contra a data reprogramada), e um gráfico de backlog com o novo compromisso dos
atrasados. Hoje não há como calcular nenhum dos dois.

## Solution

A data prevista vira a baseline: o DocManager nunca mais a troca sozinho. Sempre que o
Controle de Documentos trocaria uma data já preenchida no Doc List ou no Mapa dos
Planos (data prevista ou data reprogramada), o app mostra as incidências e quem roda a
atualização decide: aceitar todas, não sobrescrever nenhuma, ou escolher caso a caso.
Uma recusa fica anotada na própria planilha e não volta a ser perguntada enquanto o
Controle mantiver a mesma data. No Doc List, o app passa a gravar, por documento, a
situação contra a data prevista (SITUAÇÃO OTD) e, para o backlog, a situação contra a
data reprogramada (SITUAÇÃO SAY-DO), criando as colunas quando faltarem. A SITUAÇÃO
EMISSÃO continua como está (contra a data-alvo), para a visão atual do painel. O Power
BI só conta: três visões no mesmo gráfico (Atual, OTD, Say-do) e dois cartões de %.
A parte do Power BI sai como roteiro de cliques, depois do DocManager.

## User Stories

1. Como coordenador da documentação, quero que a data prevista de um documento não mude sozinha, para que ela seja a baseline contra a qual o atraso é medido.
2. Como coordenador, quero ser avisado quando o Controle de Documentos trocaria uma data prevista já preenchida, para decidir se aceito a nova baseline.
3. Como coordenador, quero ser avisado quando o Controle trocaria uma data reprogramada já preenchida, para decidir se aceito o novo compromisso.
4. Como coordenador, quero aceitar todas as trocas de uma vez, para não perder tempo quando sei que o Controle está certo.
5. Como coordenador, quero recusar todas as trocas de uma vez, para manter a planilha como está.
6. Como coordenador, quero ver todas as incidências numa lista e marcar quais trocar, para decidir caso a caso.
7. Como coordenador, quero ver em cada incidência o documento, a descrição, a coluna, a data da planilha e a data do Controle, para decidir sem abrir as duas planilhas.
8. Como coordenador, quero ser lembrado de que trocar a data prevista muda a baseline, para não apagar um atraso sem querer.
9. Como coordenador, quero que uma data digitada à mão nunca seja apagada sem o meu aceite, para confiar no que a equipe escreve na planilha.
10. Como coordenador, quero que um texto como "A DEFINIR" ou uma fórmula numa coluna de data também apareça como incidência, em vez de ser apagado em silêncio.
11. Como coordenador, quero que uma célula de data vazia seja preenchida pelo Controle sem pergunta, porque ali não há nada a perder.
12. Como coordenador, quero que uma troca que recusei não seja perguntada de novo, enquanto o Controle mantiver a mesma data.
13. Como coordenador, quero ser perguntado de novo quando o Controle mudar a data outra vez, porque é uma informação nova.
14. Como coordenador, quero ver as recusas numa aba da própria planilha, para saber o que foi recusado, por quem e quando.
15. Como coordenador, quero poder apagar uma linha da aba de recusas para ser perguntado de novo sobre ela.
16. Como colega que roda o DocManager em outra máquina, quero que as recusas valham para mim também, porque a planilha é compartilhada.
17. Como coordenador, quero poder fechar a tela sem decidir, e então nada é trocado nem anotado, para decidir numa próxima rodada.
18. Como coordenador, quero que a mesma regra e a mesma tela valham para o Mapa dos Planos.
19. Como quem roda o Mapa pela linha de comando, quero que nada seja trocado sem tela e que as incidências apareçam no log.
20. Como coordenador, quero que o log diga quantas datas foram preenchidas, quantas incidências houve e quantas foram aceitas, recusadas, adiadas ou já estavam recusadas.
21. Como gestor, quero, para cada documento do Doc List, a situação contra a data prevista (emitido no prazo, emitido com atraso, pendente no prazo, pendente vencido, sem planejamento, cancelado), para calcular o Baseline OTD.
22. Como gestor, quero, para cada documento do backlog, a situação contra a data reprogramada, para calcular o Say-do.
23. Como gestor, quero que só entre no backlog o documento com data reprogramada posterior à data prevista e que não saiu até a data prevista.
24. Como gestor, quero que um documento reprogramado mas já emitido no prazo não entre no backlog, porque a data reprogramada dele é de outra revisão.
25. Como gestor, quero que uma reprogramação igual à data prevista não conte como backlog, porque a data não mudou.
26. Como gestor, quero que o documento entre no backlog assim que é reprogramado, mesmo antes de a data prevista vencer.
27. Como gestor, quero que a SITUAÇÃO EMISSÃO continue igual (contra a data-alvo), para que a visão atual do painel não mude.
28. Como coordenador, quero que as colunas novas sejam criadas pelo app no fim da aba, com a formatação das vizinhas, para não ter de mexer na planilha.
29. Como coordenador, quero que as linhas de grupo (nível 1) fiquem com as colunas novas vazias, como já acontece com a SITUAÇÃO EMISSÃO.
30. Como gestor, quero que o "vencido" seja o do dia em que o app rodou, e saber que antes de apresentar é preciso rodar o app e atualizar o Power BI.
31. Como gestor, quero ver no Power BI as três visões (Atual, OTD e Say-do) no mesmo gráfico, trocando por botão.
32. Como gestor, quero dois cartões, Baseline OTD e Say-do, que sigam os filtros do painel.
33. Como gestor, quero que a curva S use a data prevista e não recomece o acumulado no mês filtrado.
34. Como quem mantém o DocManager, quero a decisão registrada (ADR) e a base de conhecimento atualizada, para ninguém "corrigir" isso de volta.

## Implementation Decisions

- **Regra de datas** (uma só, para Doc List e Mapa): célula vazia recebe a data do
  Controle; célula preenchida (data, texto ou fórmula) nunca é trocada sem aceite; se
  o Controle tem outra data, nasce uma incidência. Uma data igual à do Controle não é
  incidência. A data-alvo continua sendo reprogramada > prevista sobre os valores
  finais. Substitui o "vence a mais recente" (KB §24.13) e o "reprogramada só preenche
  o vazio" passa a ser caso particular da regra.
- **Incidência**: documento, coluna (prevista ou reprogramada), valor da planilha
  (data ou o texto da célula), data do Controle.
- **Decisão**: a atualização roda em duas passadas. A primeira acha as incidências de
  todas as linhas (é barata: só a busca no Controle); a decisão é pedida uma vez, por
  um callback injetado; a segunda passada grava tudo com as datas finais. O callback
  devolve as incidências aceitas e as recusadas, ou nada (adiar). Sem callback
  (linha de comando, testes), nada é trocado nem anotado e as incidências vão para o log.
- **Recusas**: aba "Sobrescrições recusadas" na própria pasta de trabalho, criada pelo
  app na primeira recusa. Chave: código do documento + coluna + data do Controle
  recusada. Colunas: N° ITAIPU, Nº CMI, COLUNA, DATA NA PLANILHA, DATA DO CONTROLE,
  RECUSADA EM, POR. Incidência com chave anotada não é perguntada.
- **Tela**: primeiro uma pergunta com três botões (Aceitar todas, Não sobrescrever,
  Ver caso a caso) e o aviso de que trocar a data prevista muda a baseline; no caso a
  caso, uma lista com caixa de marcar por incidência, marcar/desmarcar todas, e um
  botão para trocar as marcadas (as desmarcadas viram recusa). Fechar = adiar. A tela
  abre na thread da interface pela ponte que o app já usa para os diálogos.
- **Doc List, colunas novas**: SITUAÇÃO OTD (mesmos baldes da SITUAÇÃO EMISSÃO, contra
  a data prevista) e SITUAÇÃO SAY-DO (mesmos baldes, contra a data reprogramada, só
  para o backlog; vazia fora dele). Ambas calculadas (sobrescritas a cada rodada) e
  vazias no nível 1. Criadas no fim da aba quando faltarem, copiando o estilo de uma
  coluna vizinha e estendendo o autofiltro.
- **Backlog**: data reprogramada posterior à data prevista e a 1ª emissão não
  aconteceu até a data prevista.
- **SITUAÇÃO EMISSÃO e DIAS DESVIO EMISSÃO**: sem mudança (contra a data-alvo).
- **Sem coluna de data da atualização** (decisão do usuário); OBSERVAÇÕES segue manual.
- **Power BI**: fora do código; roteiro de cliques em `docs/power_bi_otd_say_do.md`
  (três visões num gráfico só, trocadas por uma segmentação em blocos; cartões; curva S
  acumulando desde o início).

## Testing Decisions

- Bons testes olham comportamento pela interface pública: a planilha gravada, a aba de
  recusas, o log. Nada de testar funções internas da orquestração.
- Seams (as mesmas que o repositório já usa):
  1. a regra pura de reconciliação de datas (preencher vazio, incidência, aceite);
  2. a atualização do Doc List de ponta a ponta, com planilha, base Aconex e Controle
     de verdade em arquivos temporários, e a decisão do usuário injetada como callback
     (fronteira do sistema);
  3. a atualização do Mapa dos Planos, idem;
  4. a classificação de backlog e situação say-do (função pura, casos A a E da conversa);
  5. a tela de sobrescrição com pytest-qt, sem monitor.
- Prior art: os testes de ciclo completo do Doc List e do Mapa, os de reconciliação de
  datas do Controle e os de telas Qt.
- Os testes antigos que fixavam "vence a mais recente" mudam junto: a regra mudou por
  decisão do usuário.

## Out of Scope

- Editar o .pbix/.pbip: o Power BI sai como roteiro de cliques.
- Histórico de todas as reprogramações de um documento (vale a primeira, salvo aceite).
- Recuperar automaticamente a baseline perdida dos 15 documentos (o usuário confere no
  histórico de versões do Box e digita).
- Limpeza da planilha (coluna A duplicada, "Column30", datas de 2034/2035).
- Coluna de data da atualização.

## Further Notes

- Mudança de régua do painel: antes de apresentar, rodar o DocManager e clicar em
  Atualizar no Power BI.
- Quem decide aceitar a troca da data prevista está rebaselinando: o Baseline OTD passa
  a medir contra a data nova.
