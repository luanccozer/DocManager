# Doc List Mapping — estrutura e regras de uso

> Módulo criado a partir do Mapa dos Planos para acompanhar uma **lista de
> documentos** com regras próprias. Regras de domínio na KB §27; este arquivo é
> o guia prático da planilha e da tela.

## Para que serve

Follow-up semanal de uma documentação já definida: você mantém a planilha, roda
o módulo, e ele atualiza status, hierarquia, resumo por escopo e as datas de
planejamento a partir da base do Aconex e do Controle de Documentos.

## Cabeçalho oficial (21 colunas)

```
GRUPO · SISTEMA · FASE DE PROJETO · Nº CMI · N° ITAIPU ·
DESCRIÇÃO DO DOCUMENTO · DATA PREVISTA EMISSÃO · DATA REPROGRAMADA ·
DATA-ALVO EMISSÃO · EMITIDO / NÃO EMITIDO · DATA ÚLTIMA EMISSÃO ·
ÚLTIMA REV. EMITIDA · STATUS REAL · STATUS · RESPONSIBLE (COE/VENDOR) ·
NÍVEL · STATUS CONSOLIDADO · COM ITAIPU · PREDECESSOR · OBSERVAÇÕES ·
RESUMO QUANTIDADES
```

⚠️ Atenção aos codepoints: `N° ITAIPU` usa **U+00B0** (sinal de grau) e
`Nº CMI` usa **U+00BA** (ordinal) — trocar um pelo outro faz a localização do
cabeçalho falhar. O botão **"Criar planilha modelo"** gera o arquivo com os
caracteres certos.

O cabeçalho é localizado dinamicamente nas 10 primeiras linhas (âncora
`N° ITAIPU`), e os nomes são comparados sem acento, em maiúsculas e com espaços
colapsados — cabeçalho quebrado em duas linhas dentro da célula continua sendo
reconhecido.

### Cabeçalhos legados

Quem veio da planilha adaptada do mapeamento tem nomes antigos. Eles são
reconhecidos e **renomeados automaticamente** na primeira atualização:

| Antes | Agora |
|---|---|
| `TROCAR` | `DATA-ALVO EMISSÃO` |
| `RESPONSÁVEL` | `RESPONSIBLE (COE/VENDOR)` |
| `OBSERVAÇÃO` | `OBSERVAÇÕES` |
| `DATA PREVISTA EMISSÃO ETAPA 1` | `DATA PREVISTA EMISSÃO` |

## Níveis: 1 é agrupamento, 2 é documento

- **Nível 1** — um por escopo das Unidades Geradoras. **Não é um documento**:
  não é procurado no Aconex nem no Controle. Recebe `NÃO EMITIDO` nas colunas de
  status, `CMI` em `COM ITAIPU`, o próprio código em `PREDECESSOR` e o
  `RESUMO QUANTIDADES` dos seus filhos.
- **Nível 2** — os documentos. `PREDECESSOR` = código do grupo imediatamente
  acima na ordem física da planilha (a hierarquia é posicional: **não reordene
  as linhas** sem querer mudar o agrupamento).

## O que é calculado e o que é seu

| Calculado (sobrescrito a cada atualização) | Input manual (nunca sobrescrito) |
|---|---|
| `DATA-ALVO EMISSÃO`, `EMITIDO / NÃO EMITIDO`, `DATA ÚLTIMA EMISSÃO`, `ÚLTIMA REV. EMITIDA`, `STATUS REAL`, `STATUS`, `STATUS CONSOLIDADO`, `COM ITAIPU`, `PREDECESSOR`, `RESUMO QUANTIDADES` | `GRUPO`, `SISTEMA`, `NÍVEL`, `RESPONSIBLE (COE/VENDOR)`, `OBSERVAÇÕES`, `DATA REPROGRAMADA` |

`Nº CMI`, `N° ITAIPU` e `DESCRIÇÃO DO DOCUMENTO` são atualizados quando o
Aconex traz um valor novo (o código do documento muda ao longo da vida).

## Datas de planejamento

| Coluna | De onde vem | Regra |
|---|---|---|
| `FASE DE PROJETO` | `FASE DE PROJETO` do Controle | escreve quando o Controle tem valor; senão preserva o que está lá |
| `DATA PREVISTA EMISSÃO` | `DATA PREVISTA DE EMISSÃO ACONEX` | havendo divergência, vence a **data mais recente** |
| `DATA REPROGRAMADA` | `REPROGRAMAÇÃO` do Controle **ou** digitada por você | **nunca sobrescreve** o que já está preenchido |
| `DATA-ALVO EMISSÃO` | derivada | `REPROGRAMADA` quando existe, senão `PREVISTA` |

> As duas regras de data valem também para o **Mapa dos Planos** desde 2026-07-28
> (KB §24.13) — a implementação é uma só, em `core/planejamento.py`.

Todas gravadas como **data nativa** do Excel (`dd/mm/aaaa`), não texto — é o que
permite o dashboard agrupar por período.

> Sem o Controle de Documentos o módulo roda normalmente: apenas a fase e as
> datas não são atualizadas.

## Status consolidado

| STATUS REAL | STATUS CONSOLIDADO |
|---|---|
| `Aprovado`, `Informativo`, `Para Aprovação` | `APROVADO` |
| `Aprovado com Comentários` | `APROVADO COM COMENTÁRIOS` |
| `Para Assinatura` | `PARA ASSINATURA` |
| `Não Aprovado` | `NÃO APROVADO` (ou `EM PROCESSO`, se já reemitiu) |
| `Em Processo` | `EM PROCESSO` |
| `Cancelado`, `Anulado` | `CANCELADO` |
| documento sem histórico | `NÃO EMITIDO` |

Diferente do Mapa dos Planos, que funde as três aprovações em `APROVADO`. O
`RESUMO QUANTIDADES` acompanha a separação:

```
Total: 45
Aprovados: 20
Aprovados c/ Comentários: 5
Para Assinatura: 2
Em Processo: 1
Não Aprovados: 7
Não Emitidos: 10
```

(`Cancelados` e `Outros` só aparecem quando existem — o total sempre fecha.)

## Análise por Período

Botão **"Analisar Período"** na tela do módulo. Responde *quais documentos estão
previstos para emitir nos próximos tempos*, usando a `DATA-ALVO EMISSÃO`.

- **Atalhos**: vencidos, próximos 7/30/90 dias, restante deste mês, mês que vem,
  este ano — ou um intervalo manual (qualquer ponta pode ficar vazia).
- **Agrupamento** por Mês, Grupo, Sistema ou Fase de Projeto.
- Cada linha mostra a **origem** da data (`Prevista` ou `Reprogramada`) e os dias
  até o alvo (negativo = vencido, em vermelho).
- Agrupamentos (nível 1) ficam de fora; documentos já emitidos também, salvo se
  você marcar "Incluir já emitidos".
- O **Excel** sai com um quadro por mês, o detalhe, e uma aba
  **"Sem Planejamento"** com os documentos que não têm nenhuma data — o furo que
  a análise por período não enxerga e que precisa ser fechado no Controle.

Duplo-clique num documento copia o código para a área de transferência.

## Contrato de código

`docmanager/doclist_backend.py` é a porta única:

- `atualizar_doclist(path_aconex, path_doclist, *, sheet_aconex, sheet_doclist,
  controle, hoje, log_cb, progress_cb, retry_cb) -> ResultadoDocList`
- `ler_linhas_doclist(caminho, sheet) -> list[LinhaDocList]`
- `analisar_periodo(linhas, *, inicio, fim, hoje, incluir_emitidos)`,
  `listar_sem_data(linhas)`, `janelas_padrao(hoje)`, `resumo(itens)`,
  `agrupar_por(itens, chave)`
- `criar_modelo(caminho)`, `exportar_analise_periodo(...)`
