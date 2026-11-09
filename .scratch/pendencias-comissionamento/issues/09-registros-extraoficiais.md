# 09: Registros extraoficiais no fim da tabela ou abaixo dela

**What to build:** (pedido do usuário, 2026-11-06; ajustado em 2026-11-09) a equipe faz à mão,
"lá embaixo", registros extraoficiais, que não estão no Aconex, e a atualização automática tem
de continuar funcionando sem quebrar a planilha. Antes, uma linha da tabela sem Issue Number
inteiro ou qualquer dado abaixo da tabela fazia a atualização recusar a planilha inteira, e um
número inventado que existisse no Aconex tinha as colunas do Aconex sobrescritas sem aviso.
Em 2026-11-09 o usuário avisou que as tabelas dinâmicas deixaram de importar: o registro pode
ficar dentro da tabela (e nelas) sem problema.

Regra: na tabela, Issue Number inteiro positivo é pendência do Aconex; vazio ou com letras
("GRUPO 01") é registro extraoficial. Abaixo da tabela, tudo é extraoficial. Extraoficial nunca
é tocado (nem valor, nem formato) e só desce quando entram novas no topo. Detalhes e armadilhas
na KB §32, "Registros extraoficiais"; mudança de consequência registrada no ADR 0002.

**Blocked by:** 06

**Status:** done

- [x] Extraoficial no fim da tabela (com letras e vazio): XML igual, só o número da linha muda; sem vermelho de impeditiva; o azul feito à mão fica
- [x] Linhas abaixo da tabela, com ou sem linha em branco no meio (até com número): descem junto, sem mudança; a tabela não passa a incluí-las; rodar de novo sem novidade não grava
- [x] Extraoficial no meio da tabela fica no lugar (relativo)
- [x] Linha vazia no fim da tabela não reprova a conferência (o pandas descarta as vazias do fim)
- [x] Tabela só com extraoficiais, ou sem nenhuma linha gravada, recebe as pendências (modelo de reserva)
- [x] Número repetido na tabela: recusa com as linhas e a dica de usar letras
- [x] Número acima do último do Aconex na tabela: fica como está e o aviso final manda trocar por letras
- [x] Outra Tabela do Excel ou tabela dinâmica na aba, nas linhas que descem: recusa
- [x] Validador reprova extraoficial ou linha abaixo da tabela alterada, e linhas ou células fora de ordem (nada gravado, original byte a byte)
- [x] Conferido no LibreOffice com o formato da planilha real (leitor independente)
- [x] Texto da tela (pt, es, en), README, KB §32, GLOSSARY, CHANGELOG, ADR 0002
