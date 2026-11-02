---
status: accepted
---

# Planilhas com gráficos e tabelas dinâmicas são atualizadas por escrita cirúrgica no XML

Em 2026-11-02 a equipe pediu um módulo que atualiza a planilha de mapeamento de
pendências de comissionamento direto do Aconex (Campo → Questões). A planilha tem duas
tabelas dinâmicas com gráficos dinâmicos, uma coluna oculta e formatação feita à mão, e o
pedido era "não quebre nada". O DocManager passa a atualizar essa planilha editando só o
XML que precisa mudar dentro do `.xlsx` (`services/xlsx_cirurgico.py`): o `<sheetData>` e
o `<dimension>` da aba, o `ref` da tabela e, quando um estilo novo é necessário, um `<xf>`
acrescentado no fim de `<cellXfs>`. Todas as outras partes do pacote são copiadas byte a
byte. A leitura usa `zipfile` + `ElementTree`; a escrita edita o texto, nunca reserializa.

## Considered Options

- **openpyxl (carregar e salvar)**: é o que o Doc List e o Mapa usam. Medido nesta
  planilha, só abrir e salvar sem mudar nada perdeu os estilos e as cores dos gráficos,
  as configurações de impressão e as opções dos gráficos dinâmicos (`extLst`),
  reescreveu tabelas dinâmicas, desenhos e a tabela, e fez a coluna oculta M reaparecer.
- **pandas ou XlsxWriter**: recriam o arquivo inteiro; perdem ainda mais.
- **Automação do Excel (COM)**: preservaria tudo, mas exige Excel instalado em quem roda,
  não roda no CI do Linux e não tem como ser testada aqui.
- **lxml editando a árvore**: preservaria os prefixos de namespace, mas acrescenta
  dependência ao instalador e não foi provado no Excel. Trocar exige repetir a prova do
  Apêndice D da spec.

## Consequences

- O que não dá para deslocar com segurança é recusado antes de buscar o Aconex: fórmula,
  mesclagem, formatação condicional, validação, hyperlink, comentário, desenho e quebra de
  página na aba; fórmula, nome definido, série de gráfico ou cache dinâmico que aponte para
  células do corpo; macro; linha de total; coluna calculada; dado abaixo ou ao lado da
  tabela. A mensagem diz o que foi encontrado.
- Textos novos entram como `inlineStr`; o `sharedStrings.xml` não muda (o Excel 16 abriu
  sem reparo, medido).
- A cache das tabelas dinâmicas não é tocada: com `refreshOnLoad="1"` o Excel de mesa a
  atualiza ao abrir. Pré-visualizações (Box, Excel Online) podem mostrar a versão antiga.
- Antes de trocar o arquivo, o resultado é conferido parte a parte contra o original e o
  plano, e a substituição segura (`gravacao.substituir_com_seguranca`) guarda uma cópia.
- O Doc List e o Mapa continuam no openpyxl: elas não têm gráficos dinâmicos e o app
  formata células delas. Passaram a ganhar a mesma substituição segura com cópia.
