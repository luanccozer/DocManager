# Atualização do Controle de Documentos — processo manual e plano de automação

> **Status: NÃO IMPLEMENTADO — registro de conhecimento.**
> A pedido do usuário (2026-07-29), este arquivo guarda 100% do processo manual e
> a análise de automação de um **potencial módulo** ("Atualização do Relatório
> Detalhado Itaipu" / atualização semanal da planilha **Controle de Documentos**),
> para não precisar reexplicar. Quando o assunto voltar, **basta reler este .md**.
> O usuário DECIDIU adiar a construção do módulo; a única tarefa ativa derivada
> daqui é a inclusão do **"Transmitido em"** na extração do Aconex (ver seção final).

---

## 1. Para que serve

Toda semana a equipe atualiza a planilha **ITAIPU – CONTROLE DE DOCUMENTOS** (o
arquivo com as abas `Controle de Documentos`, `BD_ACONEX1`, `Dashboard GE`,
`Curvas S`, …). O processo pega um extrato de documentos do Aconex, converte o
status cru no vocabulário de controle, joga na base de dados interna (aba
`BD_ACONEX`) e atualiza os status na aba `Controle de Documentos`. No fim, arquiva
o semanal e alimenta um dashboard (Power BI). **A parte de Power BI e e-mail está
FORA de escopo** — o objetivo é automatizar só a atualização da planilha.

## 2. O processo manual, na íntegra (como enviado pelo usuário)

> Reproduzido fielmente. Comentários do usuário destinados ao Claude aparecem como
> citação. As fotos citadas: **foto 1 → tópico 3** (lista de status), **foto 2 →
> tópico 10** (aba BD com a linha destacada), **foto 3 → tópico 11** (mapa de
> colunas RELAÇÃO→BD), **foto 4 → tópico 13** (a RELAÇÃO com a linha destacada).

### Extração da Relação de Documentos

**1.** Acessar o Aconex e baixar a relação completa de documentos conforme o
procedimento "09 – Relação de Documentos – Aconex", no diretório:
`Box\Hydro_Eng_OTR\BR_089341_Itaipu\01-System Integration\19 - Documents for Submission\0 - Documents Control\6 - Procedimentos\1 - Padronizações – CMI`.

> **Comentário do usuário (importante):** essa seção ensina a extrair um relatório
> via web que é basicamente o MESMO que o DocManager baixa, só que **sem o
> histórico habilitado** e **sem o Tracking ID** (que é recurso só de API) — como
> se eu habilitasse `Current = True`. Só que o relatório da web tem **uma coluna a
> mais** que o meu não tem: **"Transmitido em"**, que é DIFERENTE do meu "Fonte"
> (o meu "Fonte" se assemelha ao "Fonte de Revisão" da web). Precisamos achar esse
> "Transmitido em"; não sei como solicitá-lo. Teste com o documento
> `#BA00=B04BMA10UC013-UC901&ELD020`, que foi **transmitido em `ITAIPU-WTR-023502`
> na revisão 0**.

### Tratamento inicial da planilha

**2.** Abrir o arquivo exportado e filtrar todas as revisões que **não** pertencem
à fase de aprovação do cliente, mantendo apenas as **revisões de integração**.

**3.** Selecionar, na **coluna F**, apenas os status que **não** pertencem ao fluxo
de aprovação padrão — ou seja, todos os status **diferentes** dos listados na
**foto 1**: `Anulado, Aprovado, Aprovado com Comentários, Cancelado, Em Processo,
For Cancellation, Informativo, Issued for Annulment, Não Aprovado, Para Análise,
Para Aprovação, Para Assinatura, Para Informação`.

**4.** Selecionar os status **"Anulado", "For Cancellation", "Void", "Issued for
Annulment"** e alterar para **"Cancelado"**.

**5.** Filtrar o status **"Em Processo"** e desmarcar todas as transmissões
existentes na **coluna NA** (ou seja, manter só as linhas SEM transmissão).

**6.** Alterar todos esses (Em Processo sem transmissão) para **"Para Análise"**.

**7.** Filtrar as revisões fechadas (numéricas: 0, 1, 2, …) na **coluna E** e
alterar seus status para **"Para Aprovação"**.

**8.** Usar Localizar e Selecionar > Substituir do Excel para as substituições
necessárias (tabela não totalmente legível na amostra — **confirmar depois**).

### Atualização da base de dados (aba BD_ACONEX)

**9.** Copiar cada coluna para sua posição na aba **BD_Aconex** da planilha
principal, **inserindo ao final** da base existente e atualizando a data do banco.

**10.** Destacar a **primeira linha inserida** com uma cor de identificação (a
"linha destacada" — azul nas fotos 2 e 4), para as etapas seguintes.

**11.** Mapear as colunas (**foto 3**), RELAÇÃO → BD:

| RELAÇÃO (extrato) | BD_ACONEX | Provável significado |
|---|---|---|
| Coluna B | Coluna A | Código do documento |
| Coluna E | Coluna F | Revisão |
| Coluna F | Coluna H | Status |
| Coluna G | Coluna I | Data |
| Coluna AN | Coluna G | **"Transmitido em"** (transmittal) |

**12.** Identificar todos os registros **duplicados na coluna A** (código).

**13.** Localizar a linha destacada e **excluir todos os registros acima dela**
(os da semana anterior que foram substituídos).

**14.** Dos documentos que permanecerem acima da linha destacada: **manter** os que
estão **destacados em amarelo** (fase de **validação**). Como validação não faz
parte do controle, o status IB é mantido, a célula fica **amarela com fonte
vermelha**.

**15.** Para os que permanecerem **em branco**, consultar cada um no Aconex:
- se estiver em **validação** → destacar amarelo, fonte vermelha;
- se estiver no fluxo normal e só tiver **mudado o código** → a linha pode ser
  **excluída** da BD.

### Atualização de status (aba Controle de Documentos)

**16.** Na aba **Controle de Documentos**, verificar na **coluna AC** os documentos
com status **NÃO EMITIDO**; aplicar filtro na **coluna AI** selecionando todos os
status **diferentes de** NÃO EMITIDO.

**17.** Selecionar os códigos desses documentos, colar na BD e remover duplicados.
São documentos que **foram emitidos em algum momento mas tiveram o fluxo
encerrado**.

**18.** Na **coluna AI**, selecionar cada status individualmente e copiá-lo para a
**coluna AH** — **exceto** "Para Análise", "Para Assinatura" e "Para Aprovação",
que **não** devem ser copiados (são os status "em voo", input manual).

**19.** Na **coluna AI**, selecionar "Para Aprovação"; filtrar a **coluna S** para o
subtipo **"PLANILHA DE COMISSIONAMENTO / PLANILHA DE DESCOMISSIONAMENTO"**; copiar
os códigos RDS-PP, colar na BD e alterar o status para **"Para Aprovação - PC"**.

**20.** Conferir se as colunas com fórmula estão ok e atualizar a **coluna A**
(item).

### Arquivamento e distribuição (FORA de escopo, exceto salvar/arquivar)

**21.** Salvar, fechar, duplicar o arquivo renomeado com a data, mover a cópia para
a pasta **"Obsoleto"** (histórico dos semanais).
**22.** Copiar o arquivo para a pasta **"08 – Dashboard"** com o nome original
(`Box\CMI - Consórcio Itaipu\07 - Ger. Comunicação\08 - Dashboard`).
**23.** No arquivo do Dashboard, excluir todas as colunas a partir da **coluna AR**.
**24.** Abrir o Power BI e atualizar — **NÃO necessário automatizar**.
**25.** Atualizar o anexo do último e-mail semanal e enviar ao time — **fora de
escopo** (verificar destinatários novos).

## 3. Como isso mapeia no que o DocManager JÁ faz

A rotina manual, tirando o andaime do Excel, tem **dois objetivos**: (a)
materializar o status atual de cada documento no vocabulário de controle, e (b)
escrever esse status na aba Controle preservando o que é manual. **A extração da
API do DocManager é melhor que o extrato web** (tem histórico completo + Tracking
ID), e o motor de status já resolve o coração dos passos 2-8:

| Passo manual | Já existe |
|---|---|
| 2 — separar integração × aprovação | `verificar_se_integracao` em `core/status_engine.py` (corte 19/08) |
| 4 — VOID/Anulado/Issued for Annulment → Cancelado | `calcular_status_real` já unifica em "Cancelado" |
| 3,5,6,7 — status cru → status de controle | a "batalha de versões" do `calcular_status_real` resolve com o histórico (sem precisar de "Transmitido em") |
| 19 — Para Aprovação - PC (comissionamento) | `is_planilha` (§8.2) já trata comissionamento como "Para Aprovação"; o "- PC" seria derivado (status == "Para Aprovação" AND subtipo comissionamento) |
| Emitido/Não Emitido, Consolidado | `core/consolidation.py` |
| Casar doc ↔ código Itaipu/CMI | `ControleDocs.resolver` (cascata ouro/prata/bronze) |
| Escrever preservando colunas manuais | padrão de `services/doclist_update.py` / `services/mapping_update.py` |

**Vocabulário de status de controle** (o que a rotina produz): `Para Análise,
Para Aprovação, Para Aprovação - PC, Para Assinatura, Aprovado, Aprovado com
Comentários, Não Aprovado, Cancelado, Informativo, Para Informação`. É
praticamente o vocabulário de `STATUS REAL`, com dois ajustes ("Para Análise" para
Em-Processo-sem-transmissão; sufixo "- PC" para comissionamento).

## 4. Arquitetura proposta (esqueleto, para quando retomar)

Molde do **Doc List Mapping** — mais um "atualizador de planilha":

```
Base Aconex (API, histórico + Tracking) ─┐
                                          ├─► core/controle_status.py  (NOVO)
Controle de Documentos (aba real) ────────┘        status → vocabulário do Controle
                                                    (+ regra "não sobrescrever in-flight",
                                                     + Para Aprovação - PC, + preservar validação)
                                                    ▼
                              services/controle_update.py (NOVO, molde do doclist_update)
                                                    ▼
                              escreve na aba Controle preservando colunas manuais + UI view
```

- **Reaproveita:** `aconex_backend.extrair_base`, `truth_line.resolver_linha_da_verdade`,
  `status_engine.calcular_status_real` (+ `status_model_bim`), `core/consolidation.py`,
  `ControleDocs.resolver`, e a máquina de escrita-preservando-manual do Doc List.
- **Novo:** só o adaptador `status_real → status de controle` (com as 2-3 regras) +
  orquestração + escrita + tela. Já existe `docmanager/controle_backend.py` (hoje só
  LÊ o Controle para os outros módulos) — o novo módulo acrescentaria a ESCRITA.

## 5. Decisões preliminares do usuário (2026-07-29) — sujeitas a revisão

O módulo foi **adiado**; estas são leituras iniciais, não finais:

- **Entrega (Q1):** *Atualizar a planilha no lugar* — escrever direto na aba
  Controle de Documentos, preservando colunas manuais e as linhas de validação
  (amarelo/vermelho), como o Doc List/Mapa já fazem.
- **Fonte do status (Q2):** *Replicar a rotina do Excel* — o usuário preferiu, por
  ora, reproduzir literalmente os filtros/substituições dos passos 3-8 sobre o
  extrato `current=True`, em vez de usar o motor `calcular_status_real`.
  **Observação do Claude:** o motor já faz quase tudo isso com mais precisão (usa
  Tracking); ao retomar, vale comparar as duas saídas contra uma semana feita à
  mão antes de decidir. Registrado como está para respeitar a escolha do usuário.
- **Aba BD_ACONEX (Q3):** *Indefinido* — depende de as outras abas (`Dashboard GE`,
  `Curvas S`) puxarem dados da BD por fórmula. **Verificar** antes de decidir se o
  módulo precisa manter a BD (append/dedupe/preservar validação) ou pode pular.
- **Transmitido em (Q4):** por ora, o usuário quer **apenas** o "Transmitido em" na
  extração (ver seção 7); a arquitetura do módulo fica para depois.

## 6. O que ainda falta (inputs/gaps a resolver antes de construir)

1. **A planilha real e ATUAL** do "ITAIPU – CONTROLE DE DOCUMENTOS". O
   `docs/controle_de_documentos.md` (13/jul) está desatualizado: as letras
   **AC/AH/AI/S** citadas na rotina **não batem** com aquele layout (lá AC =
   "Finalidade do Envio", AH = "Parados com:", AI = "dias por revisão", S =
   "Departamento"). A planilha evoluiu — o mapeamento tem de ser por **nome de
   cabeçalho**, não por letra. Preciso do arquivo atual para ver a coluna oficial
   de status (AH), a coluna de status calculado (AI), a de NÃO EMITIDO (AC) e a de
   subtipo (S).
2. **Um par "antes/depois" de uma semana** (pasta "Obsoleto") — melhor teste
   possível: rodar o módulo sobre o "antes" e comparar com o "depois" feito à mão.
3. **Tabela de substituições do passo 8** (ilegível na amostra).
4. **Regra de "validação" (passos 14-15):** como identificar/preservar as linhas
   amarelo+vermelho (fase de validação) na escrita.
5. **Papel exato de AH × AI** na planilha atual (status oficial × status calculado)
   e a regra de "não sobrescrever in-flight" (passo 18).

## 7. Tarefa ativa desacoplada — "Transmitido em" na extração do Aconex

Único item que o usuário quer AGORA. **VERIFICADO AO VIVO em 2026-07-29** (ferramenta
`tools/descobrir_transmitido_em.py`, read-only, conectada ao Aconex real):

**Conclusão: o "Transmitido em" NÃO é obtível pela extração atual (register).** Não é
uma coluna a habilitar — é objeto da **Mail API**.

- **`/register/schema`** (HTTP 200) expõe **31 campos consultáveis**, e **NENHUM** é
  de transmittal. Lista completa: `AccessList, DocumentNumber, DocumentStatusId,
  DocumentTypeId, HasFile, Revision, Title, confidential, current, docno, doctype,
  fileSize, fileType, filename, id, markupLastModifiedDate, markupdate, modifiedby,
  numberOfMarkups, registered, reviewSource, reviewstatus, revision, statusid, type,
  uploaddate, versionNumber, trackingid` (+ internos `TempDocumentIds`/`tempDocument`/
  `AccessList`). O único campo "de origem" é `reviewSource` = a coluna **"Fonte"** que
  já extraímos. Confirma a KB §24.5. → Adicionar `return_field` a `CAMPOS_STRING` **não
  traz** o "Transmitido em".
- **Mail API acessível neste projeto:** `GET /api/projects/{pid}/mail/schema` → **HTTP
  200** (campos `ToUserId`, `BccUserId`, `Cc`, `subject`, …). Logo, os transmittals
  (`ITAIPU-WTR-…`) **existem e são acessíveis** por lá — o "Transmitido em" é viável,
  mas por **integração da Mail API**, não pelo register.
  - Detalhe pendente: `mail_box=sent` retornou **400 `INVALID_PARAMETER_VALUE`** — o
    token de caixa é outro (ex.: `SENT_BOX`/`sentbox`, a confirmar no guia da Mail API).

### 7.1 Contrato da Mail API — MAPEADO ao vivo (2026-07-29, `tools/probe_mail_aconex.py`)

- **Caixa:** `mail_box=SENTBOX` (enviados) e `INBOX` (recebidos) são válidos. O
  `INBOX` deu **504 (timeout)** ao listar tudo — pesado.
- **Volume:** `SENTBOX` tem **12.911 mails** (`TotalResults`). Cada mail traz, inline:
  `MailNo` (o nº do transmittal, ex.: `CMI-2305-WTR-005845`), `CorrespondenceType`
  (ex.: `Workflow Transmittal`), `SentDate`, `Subject`, `AttachedDocumentCount` —
  **mas NÃO os docnos anexados**.
- **Docnos anexados:** só no DETALHE `GET /mail/{MailId}` (HTTP 200), que lista
  `DocumentNo` + `Revision` + `RegisteredDocumentAttachment` por anexo. → 1 chamada
  por mail.
- **Busca por documento (barata!):** `GET /mail?mail_box=SENTBOX&search_query='"<docno>"'`
  (com ASPAS) devolve **direto** o(s) transmittal(is) que anexaram aquele documento —
  ex.: `"#BA00=B04BMA10UC013-UC901&ELD020"` → **1 resultado**, `CMI-2305-WTR-005845`,
  em ~1s. Sem aspas dá timeout (busca ampla).
- **Nuance CMI × ITAIPU (CRÍTICA):** o `SENTBOX` (busca direcionada ~1s) devolve o
  transmittal **CMI** que ENVIOU o doc (`CMI-…-WTR-…`). Mas o "Transmitido em" que o
  usuário citou (`ITAIPU-WTR-023502`) é o transmittal da **ITAIPU**, que fica no
  `INBOX` — e a busca no `INBOX`, **mesmo direcionada com aspas, deu TIMEOUT (>50s)**.
  Ou seja: só o transmittal **CMI é barato**; o **ITAIPU (o do relatório web) NÃO é
  obtível de forma rápida** por esta via — precisaria de outra abordagem (paginação
  com filtro de data, ou verificar se o web usa outro campo). **Decisão/necessidade a
  confirmar com o usuário:** serve o transmittal CMI, ou tem de ser o da ITAIPU?

### 7.2 Veredito de TEMPO (a pergunta central do usuário)

**Adicionar "Transmitido em" à extração INTEIRA aumenta MUITO o tempo — não é grátis:**
- Hoje a extração leva ~30 min (80.688 linhas / ~161 páginas do register).
- Para preencher o transmittal de todos os ~9.465 docs vigentes seria **1 busca de mail
  por documento** (~1–2s cada) → **~2,6 a 5 horas** a mais; ou varrer os 12.911 mails +
  1 detalhe cada → **~1–2 h** a mais (e o INBOX cheio dá 504). Qualquer caminho
  **soma horas** à extração.
- **Barato só por LISTA:** 1 busca por código (~1–2s). Uma lista de 50 códigos ≈ <2 min.

**Estratégias possíveis (decisão do usuário):**
1. **Sob demanda por lista** (recomendado) — nova ação "Transmitido em por lista",
   igual ao download por lista: cola os códigos, recebe `código → transmittal`. Rápido,
   proporcional à lista, **zero impacto na extração**.
2. **Mapa cacheado incremental** — montar o mapa doc→transmittal UMA vez (~1 h),
   salvar em disco, e nas próximas só buscar mails novos por `sentdate`. Cobre a base
   inteira, mas a 1ª carga é lenta e adiciona complexidade.
3. **Não fazer base-wide** — só quando precisar, via (1).

Enquanto o usuário decide, NADA foi adicionado à extração (para não aumentar o tempo).
Ferramentas de descoberta: `tools/descobrir_transmitido_em.py` e `tools/probe_mail_aconex.py`.
