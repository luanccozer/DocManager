# 07: Página Projeção no Power BI (curva do projeto e lista a recuperar)

**What to build:** no roteiro do Power BI, uma página nova com o projeto inteiro. Ela tem
três partes:

- a curva com a baseline (data prevista), o realizado (até hoje) e a projeção tracejada pelo
  replanejado (data-alvo);
- o cartão A recuperar: os atrasados contra a data prevista, com e sem data nova;
- uma lista com drill (grupo → sistema → documento) para ver quem encaixar e quem adiantar.

Pedido do usuário a partir do desenho de um colega (2026-11-10).

**Blocked by:** 06

**Status:** done

- [x] Decisões Q21, Q22 e Q23 = A:
  - Q21: o pendente sem data nova fica fora da projeção;
  - Q22: o cartão mostra os atrasados, com e sem data nova;
  - Q23: página própria.
- [x] Passo 12 no roteiro, conferido contra o .pbix e a planilha de 06/11
- [x] Regras testadas na planilha de teste (TESTE-10 a TESTE-12) e na aba Esperado
- [x] Glossário (A recuperar) e KB §27.7

## Comments

- 2026-11-10: antes de fazer, o desenho foi discutido com um rascunho sobre os dados de 26/10:
  89 a recuperar, 58 sem data nova, e a tracejada não encontra a baseline. O usuário
  respondeu Q21 a Q23 = A e pediu a lista em drill.
  - Roteiro: 9 medidas novas e a tabela Recuperacao.
  - Conferência: as 29 fórmulas passam no conferidor, e as posições na cópia da página Curva
    não têm conflito.
  - Números com a planilha de 06/11 aberta em 10/11:
    - 91 a recuperar: 68 com data nova e 23 sem;
    - hoje, 915 × 830;
    - no fim do eixo, 1.058 × 1.037.
  - Os cliques no Power BI ficam com o usuário.
