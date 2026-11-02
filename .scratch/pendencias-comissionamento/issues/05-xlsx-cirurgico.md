# 05: Escrita cirúrgica no pacote .xlsx

**What to build:** `docmanager/services/xlsx_cirurgico.py`, infraestrutura genérica (sem regra
de pendências): ler o pacote (abas, tabelas, shared strings, estilos, linhas e células com
`s`), achar a única tabela com uma coluna dada, aplicar as recusas da seção 8.2, editar
`sheetData`/`dimension`/`ref` da tabela, acrescentar `<xf>` no fim de `<cellXfs>` e regravar o
zip copiando as partes não alteradas byte a byte (gravar com `copy.copy(zipinfo)`).
Biblioteca: `zipfile` + edição do texto XML (seção 4 da spec, provada no Excel no Apêndice D).
Nunca salvar a pasta com openpyxl, pandas ou XlsxWriter; nunca reserializar com ElementTree.

**Blocked by:** None (can start immediately)

**Status:** done

- [ ] Partes não alteradas byte a byte iguais (inclui gráfico e uma parte desconhecida injetada na fixture)
- [ ] Declaração XML e tag raiz das partes alteradas textualmente iguais
- [ ] Linhas inseridas no topo da tabela e as de baixo renumeradas (inclusive linhas só com estilo abaixo da tabela)
- [ ] `dimension` e `ref` da tabela e do autoFilter estendidos
- [ ] `<xf>` acrescentado com `count` atualizado; índices antigos intactos
- [ ] Texto com `&`, `<`, `>`, espaços nas pontas, quebra de linha, `=` no início e caractere de controle
- [ ] Cada recusa da seção 8.2 (A–D), sem tabela e com mais de uma tabela: arquivo byte a byte igual
- [ ] Falso positivo do `<c:pivotSource>` (nome de arquivo com o nome da aba) não recusa
