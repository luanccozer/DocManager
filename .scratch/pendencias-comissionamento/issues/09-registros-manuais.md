# 09: Registros manuais no fim da tabela

**What to build:** (pedido do usuário, 2026-11-06) a equipe quer registrar à mão, no fim da
tabela, pendências que não estão no Aconex, sem quebrar a atualização nem a planilha. Hoje uma
linha sem Issue Number inteiro faz a atualização recusar a planilha inteira, e um número
inventado que exista no Aconex tem as colunas do Aconex sobrescritas sem aviso.

Regra: Issue Number inteiro positivo é pendência do Aconex; vazio ou com letras ("M-01") é
registro manual, que nunca é tocado (nem valor, nem formato) e só desce quando entram novas.
Detalhes e armadilhas na KB §32, "Registros manuais".

**Blocked by:** 06

**Status:** done

- [x] Registro manual no fim (com letras e vazio): XML igual, só o número da linha muda; sem vermelho de impeditiva; o azul feito à mão fica
- [x] Registro manual no meio da tabela fica no lugar (relativo)
- [x] Linha vazia no fim da tabela não reprova a conferência (o pandas descarta as vazias do fim)
- [x] Tabela só com registros manuais, ou sem nenhuma linha gravada, recebe as pendências (modelo de reserva)
- [x] Número repetido: recusa com as linhas e a dica de usar letras
- [x] Número acima do último do Aconex: fica como está e o aviso final manda trocar por letras
- [x] Issue Number vazio: aviso de que fica fora da contagem das tabelas dinâmicas
- [x] Validador reprova registro manual alterado (nada gravado, original byte a byte)
- [x] Texto da tela (pt, es, en), README, KB §32, GLOSSARY, CHANGELOG
