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
| `DESCRIÇÃO` | título dos documentos que não estão no Aconex (2ª na prioridade) |
| `FASE DE PROJETO` | só o Histórico Consolidado (§24.11) |

**Regra de precedência (`data_ref`)**: `REPROGRAMAÇÃO` quando preenchida, senão
`DATA PREVISTA DE EMISSÃO ACONEX`. É essa `data_ref` que alimenta o cálculo de
atraso do lado CMI (nascedouro do documento) no Mapa, no Histórico e em qualquer
outro módulo que precise do prazo planejado.

> Nos módulos que escrevem numa planilha (Mapa dos Planos e Doc List Mapping), a
> `data_ref` é calculada sobre os valores **finais das células** — ver
> "Onde o Controle entra em cada módulo", mais abaixo.

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

### Cascata de busca (§24.12)

Para cada código, em três níveis de tolerância — e **em todos eles a linha COM
data vence a linha sem data** (uma linha vazia do Controle não pode esconder a
preenchida de outro código do mesmo documento):

| Nível | Como casa | Exemplo |
|---|---|---|
| `exato` | chave normalizada, sem espaços/invisíveis | `#ST00=M00MYA10&EAB010` |
| `frouxo` | só alfanuméricos (ignora `#`, `=`, `&`, `-`, `.`, espaços) | acha `#ST00-M00MYA10 EAB010` |
| `contido` | a célula **contém** o código (o Ctrl+F na mão) | acha `ver doc 08934…-01 (rev)` |

Códigos com menos de 8 caracteres não entram nos dois últimos níveis (casariam
com qualquer coisa). O log informa **por qual via** cada documento foi achado e
**nomeia** os que não casaram.

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

Por isso a leitura **infere day/month-first por coluna, por votação** nos
próprios valores: cada valor com 1º componente > 12 vota dia-primeiro, cada um
com 2º componente > 12 vota mês-primeiro, e o empate/ambíguo assume o padrão
brasileiro. Datas em ISO (`2025-10-13 00:00:00` — como o pandas devolve uma data
real do Excel com `dtype=str`) **não votam**, por não serem ambíguas.

A conversão usa `format="mixed"`, porque a mesma coluna mistura datas reais do
Excel com datas digitadas; sem isso o pandas infere um único formato pelo
primeiro valor e devolve `NaT` para todo o resto. O que não converter na passada
vetorizada é resgatado individualmente, inclusive **serial do Excel** (célula de
data lida como número). Datas fora da janela **1990–2100** são descartadas: o
pandas aceitaria `'1234'` como ano 1234 e `'2'` como dia do mês corrente, e um
código esquecido na coluna viraria "data prevista". `dtype=str` na leitura evita
que códigos numéricos virem `1234.0`.

## Onde o Controle entra em cada módulo

- **Mapa dos Planos** (`services/mapping_update.py`) e **Doc List Mapping**
  (`services/doclist_update.py`) usam a **mesma regra** de reconciliação
  (`core/planejamento.py::reconciliar_datas`, §24.13):
  - `DATA PREVISTA` — vence a **data mais recente** entre a planilha e o Controle;
  - `DATA REPROGRAMADA` — só preenche o **vazio** (input manual tem a palavra final);
  - o **atraso** (KPIs `SITUAÇÃO DO PRAZO`/`DIAS DE ATRASO`) usa a `data_ref`
    (`REPROGRAMAÇÃO > PREVISTA`) calculada sobre os valores **finais**, ou seja,
    os que ficam nas células — e não só sobre os do Controle;
  - a busca roda **também para documentos ausentes do Aconex** — são justamente
    os não emitidos que mais precisam da data planejada (§24.12).

  Os dois também usam a `DESCRIÇÃO` do Controle como segunda fonte do título:
  quando o documento não está no Aconex (o caso do previsto e ainda não emitido)
  mas é achado no Controle, a descrição de lá é gravada — **sobrescrevendo** a
  célula, porque descrição escrita à mão costuma ser genérica. Prioridade:
  Aconex > Controle > planilha.

  No Mapa a `DATA REPROGRAMADA` é endereçada **por posição** (§21.1: há 4 colunas
  com esse nome; a da etapa 1 é a vizinha à direita da `DATA PREVISTA EMISSÃO
  ETAPA 1`). O Doc List acrescenta a coluna derivada `DATA-ALVO EMISSÃO` — ver
  `docs/doc_list_mapping.md`.
- **`FASE DE PROJETO`**: lida do Controle e usada **apenas pelo Histórico
  Consolidado** (§24.11). No Doc List a coluna existe, mas é input manual —
  decisão da equipe (§27.3).
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
- `ControleRow(cod_itaipu, cod_cmi, titulo, data_prevista, data_reprogramada,
  fase, emitido)` com `.data_ref` (REPROGRAMAÇÃO > PREVISTA).
- `ControleDocs.resolver(codigos, cod_itaipu_atual, cod_cmi_atual)
  -> MatchControle(linha, via)` — **a entrada principal** (cascata completa).
- `ControleDocs.linha_por_codigo`, `.data_ref_por_codigos(codigos)`,
  `.datas_por_codigos(codigos)`, `.buscar_contendo(codigo)` e
  `.resolver_para_codigos(...)` (compatibilidade — devolve só a linha).
