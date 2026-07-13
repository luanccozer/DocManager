# Controle de Documentos — estrutura e regras de uso

> Fonte da verdade da planilha **ITAIPU – CONTROLE DE DOCUMENTOS** (aba "PLANO
> GERAL DE ENVIO DE DOCUMENTOS"). Amostra real fornecida pelo usuário em
> 2026-07-13. Este documento existe para que a estrutura não precise ser
> reenviada: quando o usuário pedir, basta reler este arquivo.

## Para que serve no DocManager

O Controle é uma planilha de **planejamento** mantida manualmente pela equipe. O
DocManager cruza a base do Aconex (fonte da verdade dos status/datas reais) com
o Controle **apenas para as DUAS datas de input manual** que o Aconex não tem:

| Coluna do Controle | Uso |
|---|---|
| `DATA PREVISTA DE EMISSÃO ACONEX` | data planejada de 1ª emissão |
| `REPROGRAMAÇÃO` | nova data planejada quando a prevista escorregou |

**Regra de precedência (`data_ref`)**: `REPROGRAMAÇÃO` quando preenchida, senão
`DATA PREVISTA DE EMISSÃO ACONEX`. É essa `data_ref` que alimenta o cálculo de
atraso do lado CMI (nascedouro do documento) no Mapa, no Histórico e em qualquer
outro módulo que precise do prazo planejado.

> ⚠️ Todas as demais colunas do Controle que tenham equivalente no Aconex
> (status, título, revisão, datas de envio/retorno, "parados com", etc.) são
> **ignoradas** — a prioridade é sempre do Aconex. Do Controle só entram as duas
> datas acima, porque são inputs manuais que não existem no Aconex.

## Chaves de casamento (Controle ↔ Aconex)

| Coluna do Controle | Casa com (Aconex) |
|---|---|
| `CODIFICAÇÃO ITAIPÚ (ACONEX)` | `No. do Documento` (código Itaipu) |
| `NÚMERO INTERNO` | `Controle do Emissor` (código CMI) |

Os códigos são normalizados (strip, upper, remoção do `.0` fantasma de leitura
numérica) antes de casar. O casamento por documento prioriza: código Itaipu
atual → código CMI atual → qualquer código histórico do Tracking.

## Layout físico da planilha

- **Linhas 1–3**: títulos e faixas ("ITAIPU - CONTROLE DE DOCUMENTOS … /
  Planejamento Status - dd/Mmm/aaaa", "PLANO GERAL DE ENVIO DE DOCUMENTOS …
  STATUS EMISSÃO / RESPOSTA IB", e uma linha de separadores `;` `.`).
- **Linha 4**: **cabeçalho** das colunas.
- **Linha 5+**: dados (uma linha por documento; a coluna `ITEM` é sequencial).

A leitura **não fixa** o cabeçalho na linha 4: ele é localizado dinamicamente
procurando a linha que contém `CODIFICAÇÃO ITAIPÚ (ACONEX)` (ou `ITEM` +
`NÚMERO INTERNO`), varrendo as primeiras ~15 linhas. Assim, se inserirem/tirarem
uma linha de título no futuro, a leitura continua funcionando.

## Colunas do cabeçalho (linha 4), na ordem

```
ITEM · FASE DE PROJETO · TIPO DE DOCUMENTO · NÚMERO INTERNO ·
CODIFICAÇÃO ITAIPÚ (ACONEX) · DESCRIÇÃO · ÚLTIMA REVISÃO EMITIDA ·
DATA PREVISTA DE EMISSÃO ACONEX · REPROGRAMAÇÃO ·
DATA REALIZADA NO ACONEX / PRELIMINAR · DATA DO ÚLTIMO STATUS · DISCIPLINA ·
LOCAL · EIXO · UG · SUBTIPO · EQUIPAMENTO / SISTEMA ·
REFERÊNCIA DA ESPECIFICAÇÃO TÉCNICA · DEPARTAMENTO RESPONSÁVEL ·
Gestor do Documento · Elaborador do Documento · EMPRESA · TIPO EMISSÃO ·
PED Correspondente · EMITIDO / NÃO EMITIDO · ALERTA DE EMISSÃO ·
TRANSMISSÃO CMI N° · DATA DE ENVIO · Finalidade do Envio · Status real ·
Status documento em tramitação · Data de retorno · TRANSMISSÃO ITAIPU N° ·
Parados com: · dias por revisão · data para Resposta · dias de Atraso ·
ALERTA · Observação / Comentários TPMs · Status Consolidado
```

O casamento das colunas é **tolerante**: normaliza sem acento, em maiúsculas e
sem espaços sobrando, e aceita "contém" além de igualdade — pequenas variações
de grafia (ex.: `ITAIPÚ`→`ITAIPU`) não quebram a leitura.

## Formatos de data (atenção: MISTOS na planilha real)

A planilha real mistura convenções **por coluna**:

| Coluna | Exemplos reais | Convenção |
|---|---|---|
| `DATA PREVISTA DE EMISSÃO ACONEX` | `30-11-2025`, `17-07-2025` | **DD-MM-AAAA** (dia primeiro) |
| `REPROGRAMAÇÃO` | `10/20/2025`, `5/30/2035` | **M/D/AAAA** (mês primeiro, formato US) |
| `DATA DO ÚLTIMO STATUS` | `28/04/26` | DD/MM/AA (não usada) |

Por isso a leitura **infere day/month-first por coluna**, olhando os próprios
valores: se algum valor tem o 1º componente > 12, a coluna é dia-primeiro; se
algum tem o 2º componente > 12, é mês-primeiro; se tudo for ambíguo, assume o
padrão brasileiro (dia-primeiro). `dtype=str` na leitura evita que códigos
numéricos virem `1234.0`.

## Onde o Controle entra em cada módulo

- **Mapa dos Planos** (`services/mapping_update.py`): para cada documento,
  - preenche `DATA PREVISTA EMISSÃO ETAPA 1` **apenas se a célula estiver vazia**,
    usando `DATA PREVISTA DE EMISSÃO ACONEX` (nunca sobrescreve input manual);
  - se houver `REPROGRAMAÇÃO`, escreve na coluna `DATA REPROGRAMADA` da etapa 1
    (endereçada por posição — §21.1: há 4 colunas com esse nome);
  - o **atraso** (KPIs `SITUAÇÃO DO PRAZO`/`DIAS DE ATRASO`) usa a `data_ref`
    (REPROGRAMAÇÃO > PREVISTA).
- **Histórico Consolidado** (`services/historico_consolidado.py`): a `data_ref`
  por Tracking preenche a coluna interna `Data Prevista (Controle)`, que é o
  nascedouro do cálculo do **Atraso CMI** e das **linhas sintéticas** (documentos
  do Controle ainda não postados no Aconex → linha `NÃO EMITIDO` com atraso
  correndo até hoje). O Controle é **opcional**: sem ele, os mecanismos rodam
  igual, apenas sem `data_ref` e sem sintéticas.
- **Demais módulos**: qualquer consumidor do prazo planejado usa a mesma
  `data_ref` via `ControleDocs.data_ref_por_codigos(...)`.

## Contrato de código (resumo)

`services/controle_docs.py`:
- `ler_controle(caminho, sheet=0, *, log_cb=None) -> ControleDocs` — leitura
  dinâmica; nunca lança por coluna ausente (só avisa via `log_cb`).
- `ControleRow(cod_itaipu, cod_cmi, titulo, data_prevista, data_reprogramada)`
  com `.data_ref` (REPROGRAMAÇÃO > PREVISTA).
- `ControleDocs.linha_por_codigo`, `.data_ref_por_codigos(codigos)`,
  `.resolver_para_codigos(codigos, cod_itaipu_atual, cod_cmi_atual)`.
