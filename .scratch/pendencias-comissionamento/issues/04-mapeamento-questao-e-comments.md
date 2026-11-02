# 04: De-para questão → colunas e texto de Comments

**What to build:** as funções puras do Apêndice A da spec (validadas contra o Aconex real:
4.263/4.263 células e Comments 35/35), adaptadas ao estilo do repositório e sem mudar as
regras: `valores_da_questao`, `definicoes_por_chave` (family_id primeiro) e
`formatar_comentarios` (Everyone primeiro, blocos separados por linha em branco, horário
UTC−3 em inglês e 12 h).

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Cada linha da tabela da seção 6 da spec tem teste
- [ ] UTC → UTC−3 que muda o dia; `Due Date` sem conversão
- [ ] Campo customizado casado por `family_id` com `id` diferente
- [ ] `Yes`/`No` → `Sim`/`Não`; status desconhecido gravado cru com aviso
- [ ] Comments: um bloco, vários comentários, Everyone + organização, aspas e quebra de linha no texto, 0h e 12h, sem comentários
