# Base de Conhecimento — DocManager Itaipu

> Documento de referência das regras de negócio, arquitetura e armadilhas do sistema de gestão de documentos de engenharia do projeto Itaipu (contexto CMI ↔ Itaipu Binacional, via Aconex).
> Objetivo: servir de fonte da verdade para a refatoração (separação backend/frontend) e para qualquer manutenção futura, garantindo que nenhuma regra de negócio validada em produção se perca.

**Versão do documento:** 1.0 · **Base:** código v2.2.x (launcher, aconex_reviewer.py, data_manager.py, dash_ib.py)

---

## 1. Visão Geral

O DocManager é um app desktop (CustomTkinter) usado pelo time de engenharia da CMI para controlar a documentação do projeto de modernização de Itaipu. Ele consome extrações da base **Aconex** (sistema de gestão documental do cliente) e cruza com planilhas internas (Mapeamento de Planos, Controle de Documentos, Kaizen, P6, Backlog, Corella).

A pergunta central que o sistema responde é: **"qual é o status REAL de cada documento?"** — porque o status bruto que o Aconex exibe na linha vigente frequentemente **não** representa a situação real do documento (revisões canceladas, status internos de integração, mudanças de fluxo do cliente, ciclos internos da CMI). Todo o valor do sistema está nos motores de interpretação descritos nas seções 8 a 16.

### Atores

| Sigla | Quem é | Papel |
|---|---|---|
| **CMI** | Consórcio executor (fornecedor) | Emite documentos, faz retrabalho após reprovações |
| **Itaipu / IB** | Itaipu Binacional (cliente) | Analisa e dá vereditos (aprova/reprova) |
| **Aconex** | Plataforma documental | Fonte de dados (histórico de revisões/versões/status) |

---

## 2. Arquitetura Atual

```
launcher (Script 1)          → Splash screen, imports pesados em thread, lê .env (VERSAO, secrets)
aconex_reviewer.py           → MONÓLITO: MainApp + 7 Views + ConfigManager + ExcelHandler + SaveRetryDialog + DeltaView
data_manager.py              → DataManager: embrião do backend (carga Aconex, motores de status, KPIs, relatórios)
dash_ib.py                   → Dashboard web (Dash/Plotly) rodando em thread local, porta 8050
.env                         → VERSAO, SECRET_<USUARIO> (credenciais API Aconex)
Documents/DocManager_Itaipu/config.json → memória de últimos caminhos de arquivo (ConfigManager)
```

### Views (módulos) do monólito

| View | Nome no menu | Função |
|---|---|---|
| `MappingView` | Mapa dos Planos | Atualiza semanalmente a planilha de mapeamento (status, KPIs, hierarquia, resumos). Módulo principal. |
| `DeltaView` | (dentro do Mapa) | "Máquina do tempo": compara o estado dos documentos entre duas datas |
| `StatusCheckView` | Status Documentos | Recebe lista de códigos (Excel, colagem ou base inteira) e gera relatório de status com gráfico |
| `AconexView` | API Aconex | Extração total do histórico via API REST do Aconex (OAuth) → gera o Excel "Base Aconex" |
| `ReportView` | Relatórios | Relatório de Avanço (SLA/devoluções) e Auditoria de Integração (0AA) |
| `DashboardView` | Histórico/Dash | Gera histórico consolidado (Excel) e lança o dashboard web (dash_ib) |
| `CorellaView` | Corella vs Aconex | Auditoria cruzada com o sistema Corella (faltantes e divergência de versões) |
| `KaizenView` | Mapa Kaizen C&C | Reconstrói a planilha Kaizen: resgata dados manuais + cascata de datas P6/Backlog + injeção de protocolos via xlwings |

### Problema arquitetural central

A lógica da **"linha da verdade"** (identificar a linha vigente do documento e tratar revisões Terminated) está **duplicada em pelo menos 4 lugares**, com implementações levemente diferentes:

1. `MappingView.iniciar_atualizacao` (loop principal)
2. `StatusCheckView.iniciar_processo`
3. `DataManager.obter_snapshot_status` (Delta)
4. `DataManager.gerar_relatorio_avanco` (Fase 0/1)

E parcialmente em `analisar_kpis_documento` / `calcular_atrasos_acumulados` (variante por limiar de versão). **A refatoração deve extrair um único resolvedor**, consumido por todos (ver seção 22).

---

## 3. Glossário e Conceitos Fundamentais

**Revisão** — identificador da emissão do documento (`0A`, `0B`, `1A`, `0`, `1`...). Sequência de vida típica: `0A → 0B → ... → 0 → 1A → ... → 1`.

- **Revisões-letra** (`0A`, `1B`) = emissões para análise/aprovação do cliente.
- **Revisões numéricas** (`0`, `1`, `2`) = **emissões definitivas** (para construção). Idealmente recebem "Aprovado", mas nem sempre (gambiarras/exceções do fluxo). Por isso, um "Não Aprovado" em revisão numérica **não tem o mesmo peso** e é tratado de forma especial (seção 8.4).
- **Revisões de 3+ caracteres** (`0AA`, `0AB`) = **ciclos internos da CMI / integração**. Não são tramitação com o cliente. São exterminadas nos cálculos de KPI e limpadas em vários motores (`len(rev) <= 2`).

**Versão** — contador interno do Aconex dentro de uma mesma revisão (cada re-upload/mudança de status incrementa). É o critério de "mais recente" dentro de uma revisão. Sempre converter para número (`Versão_Int`) antes de ordenar — ordenação de string quebra em 9 vs 10.

**Família de revisão** — o primeiro caractere da revisão (`0A` e `0B` são família `0`; `1A` é família `1`). **Mudar de família reseta aprovações anteriores** no cálculo do status real (seção 8.6).

**Current** — flag do Aconex (`true`/`false`) marcando a linha vigente do documento. É o ponto de partida da "linha da verdade", mas nunca a resposta final (pode estar Terminated ou com status fantasma).

**Terminated** — `Status da Revisão` contendo "terminated": a revisão foi **cancelada/anulada no Aconex** naquele ponto do histórico.

**REGRA CANÔNICA — limiar de versão por revisão:** o Terminated invalida apenas as versões daquela revisão **até a versão terminada**. Sobrevivem as linhas com `Versão > maior versão Terminated daquela revisão`, porque uma revisão pode **"renascer"**: se a 0B foi terminada no dia 3 e o documento foi reenviado ao cliente na mesma revisão 0B no dia 8 (versão maior), **todos os módulos devem entender que a vigente é a 0B do dia 8**. Desdobramentos:
- Revisão terminada **sem renascimento** e normalizada **≤ 0A** → o documento regride a **NÃO EMITIDO** (cancelou a primeira emissão da vida útil).
- Revisão terminada **sem renascimento** e **> 0A** → aquela revisão sai do jogo e a linha vigente passa a ser a **maior Versão** do que sobrou nas demais revisões.
- No Delta (`obter_snapshot_status`) a limpeza deve ser **iterativa**: pode haver Terminateds encadeados no recorte temporal.

⚠️ **Divergência atual no código:** hoje apenas os KPIs (`analisar_kpis_documento` e `calcular_atrasos_acumulados`) implementam o limiar de versão. Mapa dos Planos, Status Documentos, Delta e Relatório de Avanço **excluem a revisão terminada inteira**, descartando indevidamente um eventual reenvio ("renascimento") da mesma revisão. A refatoração deve unificar todos no limiar de versão (§21.8).

**Normalização de revisão** (`normalizar_revisao`) — `upper`, remove `R`, `strip`, e `ljust(3, 'z')`. Efeito: preenche com `z` até 3 chars, o que produz a ordenação lexicográfica correta do ciclo de vida:

```
"0AA" < "0Az" (=0A) < "0zz" (=0) < "1Az" (=1A) < "1zz" (=1)
```

Ou seja: ciclo interno < revisão-letra < revisão definitiva, dentro de cada família.

**Células zumbis** — células do Excel com string vazia `""` em vez de `None`. Quebram lógicas de "está vazio?" e formatações. O código converte ativamente `""` → `None` ("matador de zumbis") antes de decidir preencher.

---

## 4. Domínio: Hierarquia dos Planos (Mapa dos Planos)

O mapeamento nasce da **estratégia de execução** do projeto e organiza toda a documentação necessária para liberar a execução, em 4 níveis:

```
NÍVEL 1  Plano de Execução
 └─ NÍVEL 2  Planos suporte:
     • Plano de Migração e Transição
     • Plano de Montagem
     • Plano de Desmontagem
     • Plano de Comissionamento      ─┐ somente estes
     • Plano de Descomissionamento   ─┘ têm nível 3
         └─ NÍVEL 3  Planilhas de Comissionamento
             └─ NÍVEL 4  Documentos técnicos de engenharia
```

- Níveis 1–3 são documentos **estruturantes** (preparam a execução); nível 4 é a **parte técnica** do projeto.
- Planos suporte que **não** são de (des)comissionamento chamam **diretamente** os documentos de nível 4 (sem nível 3). Em alguns casos o próprio plano de execução (nível 1) referencia nível 4 diretamente.

### Regra de aprovação bottom-up

Para aprovar um plano de nível N, os documentos do nível inferior devem estar **no mínimo aprovados**. Flexibilização negociada: a coordenação pode acordar com o cliente que o plano superior seja analisado se **grande parte** da documentação inferior estiver aprovada e o restante ao menos **emitido**.

### Discussão em aberto (codificada como "regra estrita")

Os documentos de nível 4 encabeçados por **planilhas de nível 3** passam por **outro time do cliente**, com processos e critérios próprios de status e de aprovação de plano de comissionamento. Enquanto não há consenso, o sistema aplica a **regra estrita** (seção 10): nesses documentos, só "Aprovado" seco conta como APROVADO; aprovações parciais viram **APROVAÇÃO INTERMEDIÁRIA**.

### Colunas da planilha de mapeamento

Cabeçalho localizado dinamicamente nas primeiras 5 linhas (âncora obrigatória: `N° ITAIPU`). Dados começam em `linha_do_cabeçalho + 2`. Principais colunas (dicionário `colunas_lista_planos_execução`):

| Grupo | Colunas |
|---|---|
| Identificação | GRUPO, SISTEMA, OEP, Nº CMI, N° ITAIPU, DESCRIÇÃO DO DOCUMENTO, NÍVEL |
| Planejamento (manual) | ETAPA 1–4, MÊS DE REFERÊNCIA, DATA PREVISTA EMISSÃO ETAPA 1–4, **DATA REPROGRAMADA (4×, manual — ver §21.1)**, RESPONSÁVEL, OBSERVAÇÃO, TAG ETAPA |
| Calculadas pelo sistema | EMITIDO/NÃO EMITIDO, DATA ÚLTIMA EMISSÃO, ÚLTIMA REV. EMITIDA, STATUS (bruto Aconex), STATUS REAL, STATUS CONSOLIDADO, COM ITAIPU, PLANO DE EXECUÇÃO, PREDECESSOR, RESUMO QUANTIDADES |
| KPIs (Power BI) | DIAS NO STATUS ATUAL, SITUAÇÃO DO PRAZO, DIAS DE ATRASO, TOTAL DE CICLOS, CICLOS PARA APROVAR, DOWNGRADE, ATRASO ACUMULADO IB, ATRASO ACUMULADO CMI |

---

## 5. Modelo de Dados Aconex (base extraída via API)

A extração da API (`AconexView`) gera um Excel com **uma linha por versão de cada revisão** de cada documento (histórico completo, `show_document_history=true`). Colunas canônicas após o rename da API:

| Coluna | Origem API | Significado |
|---|---|---|
| No. do Documento | DocumentNumber | Código Itaipu (mutável entre revisões!) |
| Controle do Emissor | ControlDelEmisor_singleLineText | Código CMI (mais estável, mas também mutável) |
| Tracking ID | TrackingId | **Chave imutável do documento** |
| Revisão / Versão | Revision / VersionNumber | Ver §3 |
| Status | DocumentStatus | Status bruto daquele evento |
| Status da Revisão | ReviewStatus | Onde aparece "Terminated" |
| Data de Alteração | DateModified | Data do evento (formatada dd/mm/yyyy na extração) |
| Current | — | Flag de linha vigente |
| Título, Tipo do Documento, Especialidade, Subespecialidade, Tipo do Documento DCC, Subtipo DCC, Fonte, Idioma, Control CMI, Disciplina (Modelo) | — | Metadados |

**Regra de carga (`carregar_aconex`):** tudo lido como `dtype=str`, `fillna('')`, `strip` nas colunas-chave. Nunca deixar o pandas inferir tipos — datas e revisões viram lixo.

### Universo de status conhecidos

Vereditos e trâmite (documentos comuns):

| Categoria | Status |
|---|---|
| Aprovação | Aprovado, Aprovado com Comentários, Para Assinatura |
| Reprovação | Não Aprovado |
| Informativo | Informativo, Para Informação |
| Anulação | Cancelado, Anulado, Issued for Annulment |
| Trâmite real | Em Processo (pós-corte), Para Análise (pré-corte) |
| **Fantasmas (integração/internos)** | Em Integração, Integrado, Não Integrado, Em Validação, Validado, Não Validado, Aceito, Não Aceito, 01 Aceito, 03 Nao Aceito, Para Aprovação, Para Integraçao, **Para Análise (se data ≥ 19/08/2024)** |
| Fora da análise | SATedms (não entra na análise atualmente), status em espanhol/inglês espelhados (Approved, No Aprobado, Apto para Firma...) |

Modelos BIM têm universo próprio (seção 16).

---

## 6. Identidade do Documento: Tracking ID acima de tudo

Um documento pode **trocar de código** (Itaipu e/ou CMI) entre revisões. A única identidade confiável é o **Tracking ID**. Toda análise de histórico deve ser feita sobre o histórico completo do Tracking ID, nunca sobre o código.

### Busca em cascata (`localiza_doc_historico`)

1. **Ouro:** match exato simultâneo de código Itaipu **e** CMI (ambos com len > 3).
2. **Prata:** só CMI (considerado mais forte/estável).
3. **Bronze:** só Itaipu (sujeito a erros de digitação, ex.: ponto faltando).
4. Se o match retornar **múltiplos Tracking IDs** → desempate pela **Data de Alteração mais recente**.
5. Retorno: **histórico completo** do Tracking ID eleito (todas as revisões/versões).

### Mapeamento reverso (Delta)

No Delta, constrói-se `map_doc_to_tracking` indexando **todos os nomes que o documento já teve** no histórico → Tracking ID. Assim, buscar pelo nome antigo ou novo cai no mesmo documento.

### Resgate hierárquico (Kaizen)

Ao resgatar dados manuais da planilha antiga, a chave de resgate segue a hierarquia **Tracking ID → código Itaipu → código CMI** (nunca perder dado manual por troca de código).

### Códigos históricos (`obter_codigos_historicos`)

Retorna o conjunto de **todos** os códigos (Itaipu + CMI) que o documento já teve. Usado na injeção da Data Prevista Etapa 1 (§13) para casar com o Controle de Documentos mesmo que este esteja com código antigo.

---

## 7. Marco Temporal: 19/08/2024 (mudança de fluxo no Aconex)

**Data canônica: 19/08/2024, inclusive** (o novo regime vale a partir deste dia).

**Por quê:** até 18/08/2024 a submissão de documentos no Aconex era feita **via transmissão**; a partir de 19/08/2024 passou a ser **via fluxo (workflow)**. Isso inverteu o significado dos status:

| Status | Antes do corte (≤ 18/08/2024) | A partir do corte (≥ 19/08/2024) |
|---|---|---|
| **Em Processo** | Trâmite **interno da CMI** (documento ainda não chegou ao cliente) | Documento **chegou à Itaipu** (envio real; relógio do cliente começa) |
| **Para Análise** | **Envio real** ao cliente | Status **interno/fantasma** (fluxo de integração; não é tramitação) |

### Onde a regra aparece no código (todas equivalentes a "≥ 19/08")

| Local | Implementação | Efeito |
|---|---|---|
| `calcular_status_real` → `verificar_se_integracao` | `Para Análise` com data `>= 2024-08-19` → fantasma | Status real |
| `gerar_relatorio_avanco` | `Data > 2024-08-18` e `Em Processo` → renomeia para `Para Análise`; `Empresa = IB` | Relatório de avanço usa a **nomenclatura antiga** invertendo o rename (ver §18.3) |
| `gerar_dataset_dashboard` | `<= 2024-08-19` `Em Processo` → `Em Processo (CMI)`; `<= corte` `Para Análise` → `Em Processo`; `> corte` `Para Análise` → **linha deletada** | Dashboard normaliza o histórico para semântica única: `Em Processo` = envio real |
| `gerar_relatorio_ciclos_avancado` | idem dataset (com `<`) | Ciclos |

⚠️ **Caso de borda conhecido:** `gerar_dataset_dashboard` usa `<= 19/08` para o regime antigo, enquanto o motor de status real usa `>= 19/08` para o regime novo — **o dia 19/08/2024 em si** é interpretado como regime antigo pelo dashboard e regime novo pelo status real. Na refatoração, padronizar: **regime novo = data ≥ 19/08/2024** em todos os motores (dataset deveria usar `< 19/08` para o passado). Documentado como dívida (§21.3).

---

## 8. Motor de Status Real — a "Batalha de Versões" (`calcular_status_real`)

É o coração do sistema. Recebe o histórico completo do Tracking ID (`df_tracking`) e a revisão vigente (`revisao_current`), e devolve o status que o documento **realmente** tem, ignorando ruídos.

### 8.1 Listas de veredito (comparação sempre em UPPER, com strip)

```
APROVAÇÃO    = [APROVADO, APROVADO COM COMENTÁRIOS, PARA ASSINATURA]
REPROVAÇÃO   = [NÃO APROVADO]
INFORMATIVO  = [INFORMATIVO, PARA INFORMAÇÃO]
ANULAÇÃO     = [CANCELADO, ANULADO, ISSUED FOR ANNULMENT]
FANTASMAS    = lista de integração (§5) + "PARA ANÁLISE" se data ≥ 19/08/2024
```

### 8.2 Exceção de tipologia: Planilhas de Comissionamento

Se o **Título** contém `PLANILHA` **e** `COMISSIONAMENTO`:
- `PARA APROVAÇÃO` é **promovido** para a lista de APROVAÇÃO;
- e **removido** da lista de fantasmas.

Motivo: no fluxo do outro time do cliente (comissionamento), "Para Aprovação" é um estágio avançado real, não um fantasma. Esta é a **única porta** pela qual "Para Aprovação" pode emergir como status real — e, quando emerge, o consolidado o mapeia para APROVADO (ou APROVAÇÃO INTERMEDIÁRIA sob a regra estrita, §10).

### 8.3 Linha da verdade (status atual)

Dentro da revisão vigente (`revisao_current`), a linha da verdade é a de **maior Versão_Int**. Se a revisão vigente não existe no histórico → `NÃO EMITIDO`.

*(Nota: o tratamento de Terminated acontece ANTES de chamar este motor — quem chama já entrega `revisao_current` e o df de cálculo pós-limpeza; ver §3-Terminated e §8.8.)*

### 8.4 Retornos imediatos (o presente definitivo vence)

Se o status atual (maior versão da revisão vigente) é:
- **Aprovação** → retorna direto.
- **Anulação** → retorna direto.
- **Reprovação** → retorna direto **somente se a revisão vigente NÃO for numérica**. Em revisão numérica (definitiva), um "Não Aprovado" é anômalo (o documento já foi aprovado antes de virar definitivo) e não deve rebaixar o status — segue para a batalha, onde reprovações em revisões-dígito também são **puladas** (`continue`).
- **Informativo** → retorna direto.

### 8.5 Cenário A — status atual é FANTASMA (integração/interno)

O documento está "na engenharia" ou sofreu erro de tramitação. Passos:

1. **Tentativa de salvamento na própria revisão:** procura, dentro da revisão vigente, algum **veredito oficial** (aprovação/reprovação/informativo) em versão anterior. Se existe → retorna o veredito de **maior versão**. (Caso típico: doc aprovado que depois entrou em fluxo de integração — a aprovação continua valendo.)
2. Se não há histórico fora da revisão vigente → `NÃO EMITIDO`.
3. Senão → a **batalha** roda sobre **todo o histórico das outras revisões** (sem restrição de família).

### 8.6 Cenário B — status atual é REAL (ex.: Em Processo)

O documento está tramitando com o cliente. Passos:

1. Se não há histórico fora da revisão vigente → `Em Processo` (se o atual é Em Processo) ou `NÃO EMITIDO`.
2. Senão → a batalha roda **apenas sobre a família atual** (revisões cujo primeiro caractere = primeiro caractere da revisão vigente). **Mudança de família (0→1) reseta aprovações**: a aprovação da família 0 não "vaza" para a família 1.
3. Se a família atual não tem histórico (primeira emissão da família, ex. 1A) → `Em Processo` ou `NÃO EMITIDO`.

### 8.7 A Batalha (Rei da Colina)

Sobre o alvo definido (A: histórico completo; B: família atual), varre linha a linha guardando a **maior Versão_Int** de cada categoria:

- maior versão **aprovada** (+ texto do status)
- maior versão **reprovada** (+ texto) — **ignorando reprovações em revisões numéricas**
- maior versão **informativa** (+ texto)

Veredito (vitória exige maioria estrita sobre as outras duas):

| Vencedor | Retorno |
|---|---|
| **Reprovado** | Se o atual é fantasma → retorna o texto "Não Aprovado" (a reprovação é a última verdade). Se o atual é real (Em Processo) → retorna **"Em Processo"** — a reemissão pós-reprovação já está tramitando; o documento não está mais "parado reprovado". |
| **Aprovado** | Retorna o texto da aprovação. |
| **Informativo** | Retorna o texto informativo. |

### 8.8 Fallback (empate ou nenhum veredito na batalha)

- **Atual fantasma:** pega a linha de **maior versão** do alvo da batalha. Se o status resgatado **também for fantasma** → `NÃO EMITIDO` (o documento nunca foi emitido de verdade — ficou preso na integração). Se for `Em Processo` → `Em Processo`. Senão → retorna o status resgatado.
- **Atual real:** `Em Processo` (se o atual é Em Processo), senão `NÃO EMITIDO`.

### 8.9 Preparação feita por quem chama (Mapa dos Planos / Status Docs)

Antes de invocar o motor, o chamador resolve a **linha dinâmica** (a que alimenta as colunas visuais Revisão / Data Última Emissão / Status):

1. Linha Current=True existe e **não** é Terminated → linha dinâmica = ela; base de cálculo = histórico completo.
2. Current Terminated com revisão ≤ 0A → linha dinâmica = None; base de cálculo **vazia** → `NÃO EMITIDO` (e colunas visuais limpas com `None`).
3. Current Terminated com revisão > 0A → exclui a revisão terminada; linha dinâmica = maior versão do restante; base de cálculo = restante.
4. Sem Current no histórico → linha dinâmica = maior versão do histórico (fallback).

---

## 9. Status Consolidado (`calcula_status_consolidado`)

Reduz (Status Real, Status bruto Aconex, Emitido/Não Emitido) a buckets executivos:

| Condição | Consolidado |
|---|---|
| Status Real ∈ {Aprovado, Aprovado com Comentários, Para Assinatura, Informativo, Para Aprovação} | **APROVADO** |
| Real = Não Aprovado **e** bruto = Não Aprovado | **NÃO APROVADO** |
| Real = Não Aprovado **e** bruto ∈ fantasmas (ou "Para Análise") | **NÃO APROVADO** |
| Real = Não Aprovado **e** bruto = Em Processo | **EM PROCESSO** (reemissão já tramitando) |
| Real ∈ {Anulado, Cancelado, Issued for Annulment} | **CANCELADO** |
| Real = NÃO EMITIDO | **NÃO EMITIDO** |
| Real = Em Processo **e** bruto = Em Processo | **EM PROCESSO** |
| Real vazio **e** ene = SATedms | SATedms *(não entra na análise atualmente — legado)* |
| bruto = Em Processo **e** real = "Análise 1ª Emissão" | EM PROCESSO *(regra morta — "Análise 1ª Emissão" não é produzido por nenhum motor atual)* |
| **Qualquer outra combinação** | **ERRO** |

⚠️ O bucket **ERRO** é intencional: funciona como **detector de combinações não previstas**. Se aparecer ERRO na planilha, uma regra nova precisa ser mapeada. Fragilidade conhecida: `Real = Em Processo` com bruto ≠ `Em Processo` cai em ERRO (§21.4).

### Emitido / Não Emitido (`calcular_emitido_nao_emitido`)

Derivação trivial do Status Real: vazio ou `NÃO EMITIDO` → **NÃO EMITIDO**; qualquer outra coisa → **EMITIDO**.

### Com quem está a bola (`calcula_parado_com` → coluna COM ITAIPU)

Baseado no **status bruto** da linha dinâmica: `Em Processo` → **ITAIPU**; qualquer outro (inclusive vazio/não emitido) → **CMI**. (Semântica pós-corte: Em Processo = chegou ao cliente.)

---

## 10. Regra Estrita — Planilhas VIP e o "Pente Fino"

Implementa a discussão em aberto do §4 (outro time do cliente para comissionamento).

**Passo 1 — identificar as planilhas VIP:** toda linha de **nível 3** cuja DESCRIÇÃO contém `PLANILHA` → seu código Itaipu entra em `planilhas_vip`.

**Passo 2 — rebaixar os filhos:** toda linha de **nível 4** cujo PREDECESSOR ∈ `planilhas_vip` tem o Status Consolidado reprocessado por `calcula_status_consolidado_estrito`:

| Status Real | Consolidado estrito |
|---|---|
| `Aprovado` (seco, exato) | **APROVADO** |
| Aprovado com Comentários, Para Assinatura, Informativo, Para Aprovação | **APROVAÇÃO INTERMEDIÁRIA** |
| Qualquer outro | mantém o consolidado já calculado |

O status **APROVAÇÃO INTERMEDIÁRIA** só existe nesse contexto. O Resumo de Quantidades do nível 3 exibe a quebra extra "Aprovação Intermediária" (níveis 1 e 2 mantêm a visualização limpa).

O Delta aplica a mesma regra: monta `docs_restritos` (filhos nível 4 de planilhas VIP) e passa os snapshots por `calcula_status_consolidado_estrito` antes de comparar.

---

## 11. Campos Derivados do Mapa dos Planos

### 11.1 PREDECESSOR e PLANO DE EXECUÇÃO (loop de hierarquia)

A hierarquia é **posicional** (ordem das linhas na planilha):

- Nível 1 → `PREDECESSOR = PLANO DE EXECUÇÃO = próprio código`.
- Demais níveis → varre as linhas **acima**: o primeiro código com **nível menor** que o atual vira PREDECESSOR; o primeiro código de **nível 1** vira PLANO DE EXECUÇÃO. Linhas com nível não numérico são puladas.

⚠️ Consequência: **a ordem física das linhas é regra de negócio.** Reordenar a planilha quebra a hierarquia. A refatoração deve considerar tornar isso explícito (coluna de vínculo) ou ao menos validar.

### 11.2 RESUMO QUANTIDADES (loop de resumo)

Somente para níveis 1, 2 e 3, contando **apenas filhos diretos** (`predecessor == código do pai`, excluindo a própria linha e filhos sem código):

- Nível 1/2 já `APROVADO` no consolidado → texto fixo `"Plano Aprovado"` (não conta filhos).
- Nível 3: `Total / Aprovados / Aprovação Intermediária / Em Processo / Não Aprovados / Não Emitidos`.
- Níveis 1/2: mesmo texto **sem** a linha de Aprovação Intermediária.

### 11.3 Documento não encontrado no histórico (NÃO EMITIDO)

Quando `localiza_doc_historico` volta vazio: limpa colunas visuais (None), crava `STATUS REAL = STATUS CONSOLIDADO = EMITIDO/NÃO EMITIDO = NÃO EMITIDO`, `COM ITAIPU = CMI`, e **ainda assim** calcula KPIs e atrasos acumulados (para cobrar a data prevista de emissão).

---

## 12. Filtro TAG ETAPA (níveis 1 e 2)

Planos de nível 1/2 podem ter execução faseada ("Etapa 1 e 2" etc.) com revisões antigas referentes a etapas anteriores. Se a coluna **TAG ETAPA** tem texto e a linha é nível 1 ou 2:

- O histórico completo do documento é pré-filtrado por `filtrar_historico_por_titulo`: mantém apenas linhas cujo **Título contém** o texto do filtro (comparação normalizada: sem acentos, upper, strip).
- Se o filtro esvaziar o histórico (ex.: erro de digitação no Excel) → o documento é tratado como não encontrado (**NÃO EMITIDO**) — comportamento seguro proposital.
- Esse filtro acontece **antes** de qualquer cálculo (linha da verdade, status real, KPIs).

---

## 13. Data Prevista Etapa 1 — injeção via Controle de Documentos

Arquivo opcional no Mapa dos Planos. Leitura: `header=3` (cabeçalho na linha 4). Colunas: `CODIFICAÇÃO ITAIPÚ (ACONEX)`, `NÚMERO INTERNO` (CMI), `DATA PREVISTA DE EMISSÃO ACONEX`.

**Dicionário "The Flash":** cada data válida é indexada **duas vezes** (pela chave Itaipu e pela CMI), permitindo lookup O(1) sem consultar a base Aconex.

**Regras de injeção na coluna DATA PREVISTA EMISSÃO ETAPA 1 do mapeamento:**

1. **Matador de zumbis:** célula com string vazia → convertida para `None` antes de decidir.
2. Só injeta se a célula está **realmente vazia** (nunca sobrescreve data existente — a coluna aceita input manual).
3. Coleta **todos os códigos históricos** do documento (§6) e busca cada um no dicionário.
4. **Uma única data encontrada** → usa (fast path).
5. **Datas conflitantes** (códigos do mesmo doc com datas diferentes no Controle) → desempate: data atrelada ao **código Itaipu atual** do mapeamento → senão, ao **código CMI atual** → senão, a **data mais nova** (segurança).
6. Formato visual: `dd/mm/yyyy`.

---

## 14. KPIs Analíticos (`analisar_kpis_documento`)

Saída: `dias_status`, `situacao_prazo`, `dias_atraso`, `total_ciclos`, `ciclos_aprovar`, `downgrade`.

### 14.1 Limpeza prévia do histórico (padrão dos KPIs)

1. Revisão: upper, remove `R`, strip.
2. **Extermina revisões com len > 2** (ciclos internos 0AA).
3. `Versão_Int` numérica.
4. **Terminated por limiar:** por revisão, calcula a maior versão Terminated; sobrevivem apenas linhas com `Versão_Int >` esse limiar.
5. Datas convertidas (`dayfirst=True`), linhas sem data descartadas, ordenação cronológica.

### 14.2 Documento NÃO EMITIDO

- Com data prevista válida: `dias_atraso = hoje − data_prevista`; `situacao_prazo = Atrasado` se > 0, senão `No Prazo`.
- Sem data prevista (ou inválida): `situacao_prazo = "Data não informada"`.

### 14.3 Ciclos

- `total_ciclos` = quantidade de revisões únicas (pós-limpeza).
- `ciclos_aprovar` = número de revisões distintas vistas **até o primeiro status de sucesso**, em leitura cronológica. Lista de sucesso dos KPIs inclui, além das aprovações padrão: `Approved`, `Approved with Comments`, `Informativo`, `Para Informação`, **`Apto para Firma`**.

### 14.4 Downgrade (batalha de versões absoluta)

`DOWNGRADE = SIM` se existe **qualquer "Não Aprovado" com Versão_Int estritamente maior** que a versão da **primeira aprovação** (mínima versão entre os sucessos). Ou seja: o documento foi aprovado e depois reprovado.

### 14.5 SLAs e "com quem está o relógio"

- Status Real de **sucesso** → `situacao_prazo = "Doc Aprovado"`, demais campos limpos.
- Status Real **cancelado** → `"Doc Cancelado"`, campos limpos.
- **EM PROCESSO (bola com a Itaipu):** SLA = **30 dias se revisão = 0A**, senão **15**. Referência: **maior data** da revisão atual (última movimentação da emissão). `dias_status = hoje − ref`; `dias_atraso = dias_status − SLA`.
- **Demais (bola com a CMI — ex. Não Aprovado):** SLA = **15 dias**. Referência: **maior data entre os retornos** (sucesso + falha + cancelado).

---

## 15. Atrasos Acumulados (`calcular_atrasos_acumulados`)

Auditoria **bruta, sem banco de horas** (`max(0, dias − SLA)` por trecho; adiantamento não compensa atraso). Mesma limpeza prévia dos KPIs (§14.1). Duas contas separadas: **ATRASO ACUMULADO IB** e **ATRASO ACUMULADO CMI**.

### Momento A — Nascedouro (CMI)

Cobra a CMI pela demora entre a **data prevista de emissão** e o nascimento real:
- Documento não emitido e data prevista vencida → acumula `hoje − data_prevista`.
- Documento emitido → nascimento = **última** data "Em Processo" da **primeira** revisão cronológica; acumula `max(0, nascimento − prevista)`.

### Momento B — Ciclos Itaipu

Por revisão (cronologicamente): início = última data `Em Processo` da revisão (revisão sem "Em Processo" é ruído → ciclo ignorado); fim = última data de veredito (sucesso/falha) da revisão, ou **hoje** se é a última revisão e o status real é EM PROCESSO. SLA: 30 (0A) / 15.

**Bandeira `documento_aprovado`:** a Itaipu só é cobrada enquanto a bandeira está **abaixada** (documento ainda não aprovado). Veredito de sucesso ou cancelamento → **levanta a bandeira (congela relógios)**. Veredito de falha → **abaixa (descongela)** — um downgrade reabre a cobrança.

### Momento C — Retrabalho CMI

Só quando o veredito da revisão foi **falha** (bandeira abaixada): início = data do veredito; fim = última data "Em Processo" da **próxima** revisão (ou hoje, se não há próxima emissão e o status real não é sucesso nem EM PROCESSO). SLA fixo: 15 dias.

---

## 16. Motor de Modelos BIM (`calcular_status_real_modelo`)

Documentos com `Tipo do Documento` contendo `MODEL` usam um motor próprio (usado hoje no módulo **Status Documentos**; o Mapa dos Planos não roteia para ele). Três fases/milestones: **Fase Preliminar → LOD 300 → LOD 350**, cada uma com status de Aprovado / Não Aprovado / Em Análise / Emissão Inicial (listas em `DataManager.status_mod_*`).

**Regras:**
1. **Varredura de fantasmas:** só contam status pertencentes ao universo válido de modelos; o resto é ignorado. Histórico válido ordenado da maior versão para a menor.
2. Sem nenhum status válido → `NÃO EMITIDO`.
3. **Milestone Lock:** identifica a **fase** do status válido mais recente. Se em qualquer ponto do histórico houve **aprovação daquela mesma fase** → retorna `Aprovado - <fase>` (a aprovação da fase congela e vence regressões dentro da fase).
4. Sem lock → mapeia o status válido mais recente para o rótulo normalizado: `Aprovado / Não Aprovado / Em Análise / Emissão Inicial` + `- LOD 350 / - LOD 300 / - Fase Preliminar`, ou `Informativo`.

O relatório do Status Documentos só exibe as barras de status de modelo no gráfico se houver ao menos um modelo na lista analisada.

---

## 17. Análise Delta — a Máquina do Tempo

Compara o estado de cada documento do mapeamento entre duas datas (`dt_ini`, `dt_fim`). "Antes" = `dt_ini − 1s`; "Depois" = `dt_fim 23:59:59`.

### `obter_snapshot_status(df_doc, data_corte)`

1. Corta o histórico: apenas linhas com `Data_Obj <= data_corte`.
2. **Limpeza iterativa de Terminated:** ordena por (Versão desc, Data desc); se o topo é Terminated e revisão > 0A → remove a revisão inteira e repete; se ≤ 0A → histórico vazio (`NÃO EMITIDO`).
3. Retorna `(status_bruto, status_real, revisão, data)` — o status real é recalculado com `calcular_status_real` **sobre o recorte** (a batalha roda como se o tempo tivesse parado ali).

### Gatilhos de mudança (dual-engine)

| Visão | Dispara quando |
|---|---|
| **Efetiva** (executiva) | O **status efetivo** mudou entre os dois snapshots (status real, passado pela regra estrita se o doc é restrito §10) |
| **Bruta** (tramitação) | A **data** do snapshot mudou (nova tramitação), o documento **nasceu** no período, ou (fallback) o status efetivo mudou |

Agrupamento da árvore: por **Grupo** ou **Sistema** → Nível → Documento. Filtro opcional "Ocultar se já estava Aprovado" (status antes ∈ {Aprovado, Aprovado com Comentários, Para Assinatura}). Exportação Excel com colunas dinâmicas conforme a visão (a Bruta separa Revisão e Data em colunas próprias, com datas nativas do Excel).

---

## 18. Módulos Satélites

### 18.1 Status Documentos (`StatusCheckView`)

Três modos de entrada: arquivo Excel (linha de cabeçalho e colunas Itaipu/CMI configuráveis, opção "- NENHUM -"), lista colada (um código por linha, tipo selecionável) ou **base Aconex inteira** (todos os Current=True, deduplicated). Para cada código: linha da verdade (§8.9), roteamento para o motor comum ou de **modelos BIM** (§16) conforme o Tipo do Documento, e relatório Excel com formatação condicional + gráfico de barras horizontal (cores: verde = aprovações, vermelho = reprovado/não emitido, azul = em andamento, cinza = demais).

### 18.2 API Aconex (`AconexView`)

- OAuth2 `client_credentials` por usuário (Client ID hardcoded; secret via `.env` `SECRET_<NOME>`; User ID Aconex). Opção "Outros" libera digitação manual.
- `PROJECT_ID = 1207975853`; instância `us1.aconex.com`; auth em `constructionandengineering.oraclecloud.com`.
- Paginação de 500 em 500 (`search_type=PAGED`, `show_document_history=true`, sort por docno). Retry 3x, renovação de token em 401, fim da paginação em 400 ou página < 500.
- Rede corporativa: `truststore.inject_into_ssl()` (certificados do Windows p/ Zscaler), `requests.Session` persistente, proxy manual ou autodetectado do sistema.
- Pós-processamento: parse XML → DataFrame → rename para colunas canônicas (§5) → reordenação → datas dd/mm/yyyy → Excel formatado (xlsxwriter, larguras fixas, freeze, autofilter).

### 18.3 Relatório de Avanço (`gerar_relatorio_avanco`)

Foto da situação vigente com prazos de devolução:
- **Fase 0:** mata revisões Current+Terminated inteiras (chave TrackingID_Revisão).
- **Fase 1:** deduplica por Tracking ID mantendo maior Versão / data mais recente (a "linha da verdade" do relatório).
- **Fase 2 (filtros):** revisões válidas (regex: sem dupla letra, sem caracteres especiais), status válidos, exclui docs `RDI*`, lista fixa de docs-lixo, tipos excluídos (Modelo, Documento de Referência, Contractor Documents, Inspeção, Disposição de Campo — comparação sem acento).
- **Fase 3:** aplica o corte (§7) — pós-corte, `Em Processo` é **renomeado para `Para Análise`** e `Empresa = IB`; caso contrário `Empresa = CMI`. ⚠️ Este relatório usa a **nomenclatura antiga** de propósito (o público-alvo lê "Para Análise" = está com a Itaipu). **Data Devolução** = data + 30d (rev 0A) ou + 15d. Normalização de tipos (Técnico/Gerenciamento/WORKSTATEMENT/Critério por título e DCC).

### 18.4 Auditoria de Integração (`auditar_fluxo_integracao`)

Verifica quais documentos deveriam ter passado pelo fluxo de integração (revisão **0AA**) e não passaram. Universo: Current=True cujo `No. do Documento` contém um dos **27 DCCs** monitorados (LB010...BS110). Para cada Tracking ID, agrega primeiro/último evento das revisões `0AA` e `0A` (ordenado por Versão asc) e marca `Integração = SIM/NÃO` pela existência de envio 0AA.

### 18.5 Dashboard (`gerar_dataset_dashboard` → `preparar_tabela_wide` → dash_ib)

- **Dataset:** filtra Terminated, status válidos, tipos válidos (**apenas** Documento Técnico e Management Document), revisões ≤ 2 chars; aplica o corte (§7, atenção à borda §21.3); regras cirúrgicas do "Para Aprovação" (planilhas de comissionamento → viram `Para Assinatura`; o resto é **exterminado** para não contar atraso de ninguém); **backfill de metadados** por Tracking ID (último valor não-vazio sobrescreve todas as revisões); separa ENVIOS (`Em Processo`) de RETORNOS (tudo que não contém "Em Processo" — o que exclui corretamente `Em Processo (CMI)`), deduplicando por (Tracking, Revisão).
- **Tabela wide:** 1 linha por (Tracking, Revisão) com Data/Status de Envio e Retorno + `SLA_Itaipu` (30 p/ 0A, 15 demais). **Ordenação pela CANÔNICA do ciclo de vida** (`normalizar_revisao`, ljust-`z` = §3): `0AA<0AB<0A<0B<0<1A<1B<1<…`. ⚠️ Corrigido: o histórico usava a sort key de 3 níveis (`sort_key_revisao`, herdada de `criar_sort_key` do legado), que joga TODOS os números secos (`0,1,2` = aprovações) para o fim, depois das letras de famílias posteriores — desalinhando a família e **bagunçando a cadeia de atraso CMI** (mede contra o retorno da revisão imediatamente anterior).
- **dash_ib:** KPIs (Vigentes, First Time Right = % de 0A retornadas com sucesso, Ciclo Técnico e Final = médias de `calcular_kpis_revisoes`), gráfico de status vigente com drill-down, histórico emissões vs retornos, evolução temporal de prazos (`gerar_evolucao_prazos`, com teto/capping e exclusão da 0A no ciclo CMI), curva diária de backlog de atrasos (`gerar_curva_atrasos`, com opção de encerrar atraso em aprovação parcial). O filtro de busca por lista expande para o **Tracking ID** (traz histórico completo mesmo buscando por nome antigo). Status: **potencialmente descartável — decisão pendente.** As funções de dataset (`gerar_dataset_dashboard`, `preparar_tabela_wide`) são usadas também pelo relatório de histórico consolidado e devem ser mantidas no backend independentemente.

### 18.6 Corella vs Aconex (`CorellaView`)

- Leitura Corella: Excel nativo ou XML SpreadsheetML (parser manual de Rows/Cells). Conversão de revisão Corella para contagem: `'-'` → 1; letra única → `ord(letra) − 63` (A=2, B=3...).
- **Task 1 (Faltantes):** Aconex Current=True (pós-filtros de status/códigos) left-join com `Document Number` do Corella pelo `Controle do Emissor`; sobras = faltantes.
- **Task 2 (Divergência de versões):** conta revisões únicas por Tracking ID no Aconex (pós-limpeza: status válidos, remove revisões de 3 chars) vs `Qtd_rev_corella`; divergências = contagens diferentes.
- Filtros comuns: regex de códigos HNS/KKS (contains no CMI) e lista exata colada (split por linha/vírgula/;).

### 18.7 Kaizen C&C (`KaizenView`)

Reconstrói a planilha Kaizen a partir do Mapeamento oficial + resgates:

- **8 colunas Kaizen:** ID P6, FINISH DATE, SITE NEEDED DATE, VARIANCE, ACCOUNTABLE, RESPONSIBLE, SERVIÇO DE PLANILHA SUBCONTRATADO..., PROTOCOLOS DE MONTAGEM... (as duas últimas mescladas sob o cabeçalho "DoW").
- **Resgate do Kaizen antigo:** dados manuais indexados por Tracking ID → Itaipu → CMI (§6). Linhas cuja descrição contém `PROTOCOLO` são **sequestradas inteiras** (linha completa) para reinserção posterior.
- **Dicionário P6:** `ACTIVITY ID` → `FINISH` (remove sufixo `" A"` de atividades realizadas). **ID P6 duplo** no campo (split por quebra de linha ou 2+ espaços): 1º = emissão, 2º = aprovação (se só um, vale para ambos).
- **Efeito cascata de datas** (constantes configuráveis no topo do método):
  - Nível 1/2: FINISH DATE ← P6 (ID emissão); SITE NEEDED DATE ← P6 (ID aprovação) − `RECUO_P6` (hoje **0** dias).
  - Nível 3/4: SITE NEEDED DATE ← SITE NEEDED do **predecessor** − **60 dias** (memória `memoria_needed_dates` propaga em cascata pela ordem das linhas).
  - Nível 3 com match no **Backlog**: FINISH DATE ← `DATA PREVISTA DE EMISSÃO` e **STATUS esmagado** por `STATUS ATUAL` do Backlog.
  - VARIANCE = FINISH − SITE NEEDED (dias).
- **Injeção de protocolos via xlwings** (Excel invisível): mescla protocolos do Kaizen antigo com o Backlog (Backlog atualiza status/finish/predecessor/título; protocolos inéditos do Backlog entram como nível 3); localiza o pai pelo PREDECESSOR, insere a linha após o último filho, aplica **agrupamento nativo** (`api.Group()`), pinta cinza nível 3, bordas, cascata de SITE NEEDED (−60d) e VARIANCE. Dependência exclusiva de `xlwings` (requer Excel instalado no Windows).
- **Cores por nível** (`obter_cor_linha`): 1=`808080`, 2=`BFBFBF`, 3=`D9D9D9`, 4=`F2F2F2`.

---

## 19. SLAs Canônicos

| Situação | Responsável pelo relógio | SLA |
|---|---|---|
| Análise de revisão **0A** (primeira emissão) | Itaipu | **30 dias** |
| Análise de qualquer outra revisão | Itaipu | **15 dias** |
| Retrabalho/reemissão após veredito | CMI | **15 dias** |
| Emissão inicial (nascedouro) | CMI | Data Prevista de Emissão (Controle de Docs / Backlog) |

---

## 20. Persistência e Configuração

- **ConfigManager** → `Documents/DocManager_Itaipu/config.json`: último diretório por tipo de arquivo (`last_path_<tipo>`), com validação (caminho inexistente → fallback Documentos).
- **`.env`** (empacotado via `resource_path`/PyInstaller): `VERSAO` (splash e rodapé) e `SECRET_<USUARIO>` (API Aconex).
- **Salvamento com retry** (`salvar_com_retry`): loop com diálogo customizado em `PermissionError` (arquivo aberto no Excel).

---

## 21. Dívidas Técnicas e Armadilhas Mapeadas

### 21.1 ⚠️ Chaves duplicadas "DATA REPROGRAMADA"

O dicionário `colunas_lista_planos_execução` tem **4 chaves** (`coluna_reprogramada_etapa_1..4`) apontando para o **mesmo texto** `"DATA REPROGRAMADA"`. Como `find_headers` indexa por texto do cabeçalho, o dict de headers guarda **apenas a última** coluna com esse nome. Hoje é inofensivo (essas colunas são **input manual e nunca são escritas pelo código** — e devem permanecer assim), mas se qualquer código futuro usar `get_val/set_val` com essas chaves, cairá **sempre na coluna da Etapa 4**. **Regra da refatoração:** essas chaves não podem ser endereçadas por nome de cabeçalho; se um dia precisarem ser lidas, resolver por posição relativa à coluna de data prevista da etapa correspondente.

### 21.2 Duplicação da linha da verdade

Ver §2. Extrair `resolver_linha_da_verdade(df_tracking) → (linha_dinamica, df_para_calculo, revisao_atual)` como função única do backend.

### 21.3 Borda do dia 19/08/2024

`gerar_dataset_dashboard` (e ciclos) usam `<= 19/08` para o regime antigo; o motor de status real usa `>= 19/08` para o novo. Padronizar na refatoração: **regime novo ⇔ data ≥ 19/08/2024** em todos os pontos (dashboard deveria usar `< 19/08` para o passado).

### 21.4 Bucket ERRO frágil no consolidado

`Real = Em Processo` só vira EM PROCESSO se o bruto também for `Em Processo`. Combinações legítimas (ex.: real Em Processo derivado de batalha com bruto fantasma) caem em ERRO. Avaliar na refatoração se a tabela do §9 deve ganhar linhas novas — mantendo ERRO como sentinela.

### 21.5 Regra morta

`se == 'Em Processo' and sr == 'Análise 1ª Emissão'` no consolidado: nenhum motor atual produz "Análise 1ª Emissão". Candidata a remoção (com registro).

### 21.6 Hierarquia posicional

PREDECESSOR/PLANO DE EXECUÇÃO dependem da **ordem física das linhas** (§11.1). Documentar para o usuário final e/ou validar consistência na carga.

### 21.7 Acoplamentos e riscos diversos

- `MappingView`, `StatusCheckView`, `ReportView`, `DashboardView`, `CorellaView` instanciam **DataManagers separados** (bases Aconex duplicadas em memória); `KaizenView` recebe o compartilhado. Unificar em uma instância/serviço.
- Comparações de status por **string literal com acento** espalhadas (listas duplicadas de `STATUS_APROVADOS` em views). Centralizar num módulo de constantes/enums.
- `dash_ib` roda com `debug=True` em thread e injeta dados via **variável global** (`df_wide_global`). Se mantido, refatorar a injeção.
- Credenciais da API: Client IDs e User IDs hardcoded na view; mover para configuração.
- `except:` genéricos silenciando erros em vários pontos (dificulta diagnóstico).
- `SaveRetryDialog`/`salvar_com_retry` recursivo indireto via callback — funcional, mas simplificável.
- Larguras/formatações de Excel repetidas em 5+ lugares com dicionários quase iguais → extrair um `ExcelStyler`.

---

## 22. Diretrizes para a Refatoração Backend/Frontend

### Arquitetura alvo proposta

```
docmanager/
├── core/                      # BACKEND PURO (zero imports de UI; 100% testável)
│   ├── constants.py           # Listas de status, data de corte (19/08/2024), SLAs, DCCs, enums
│   ├── models.py              # Documento, Revisao, Snapshot, ResultadoKPI (dataclasses)
│   ├── identity.py            # localiza_doc_historico, obter_codigos_historicos, map reverso
│   ├── truth_line.py          # resolver_linha_da_verdade (ÚNICO; substitui as 4 duplicações)
│   ├── status_engine.py       # calcular_status_real, verificar_se_integracao, exceção planilhas
│   ├── status_model_bim.py    # motor de modelos (LOD / milestone lock)
│   ├── consolidation.py       # consolidado, estrito, emitido, parado_com
│   ├── hierarchy.py           # predecessor/plano exec, planilhas VIP, resumo de quantidades
│   ├── kpis.py                # analisar_kpis_documento, calcular_atrasos_acumulados
│   ├── snapshots.py           # obter_snapshot_status, calcular_mudancas_periodo (Delta)
│   └── reports/               # avanço, integração, dataset dashboard, corella, kaizen (lógica)
├── services/
│   ├── aconex_api.py          # OAuth, paginação, parse XML, rede (truststore/proxy)
│   ├── excel_io.py            # leitura (find_headers, header dinâmico), escrita, ExcelStyler
│   ├── config.py              # ConfigManager, .env, credenciais
│   └── xlwings_injector.py    # injeção de protocolos (isolar a dependência de Excel/Windows)
├── ui/                        # FRONTEND (só orquestra: coleta inputs → chama core/services → exibe)
│   ├── main_app.py
│   ├── views/                 # uma view por arquivo, sem regra de negócio
│   └── widgets/               # SaveRetryDialog, componentes comuns, log
└── tests/                     # testes do core com históricos sintéticos
```

### Regras de ouro da migração

1. **Preservar comportamento primeiro, melhorar depois.** Cada função extraída deve produzir saída idêntica à atual antes de qualquer "melhoria". Usar bases Aconex reais como fixtures de regressão (rodar versão antiga vs nova e diffar as planilhas geradas).
2. **Uma única linha da verdade** (§21.2) e **um único ponto para a data de corte** (§21.3) — resolver as dívidas na extração, com teste cobrindo o dia 19/08.
3. **Constantes centralizadas:** listas de status hoje vivem em 3+ lugares com variações. `constants.py` vira a fonte única; comparações sempre normalizadas (upper/strip/sem acento onde aplicável).
4. **Nunca endereçar DATA REPROGRAMADA por nome de cabeçalho** (§21.1).
5. **O core não conhece tkinter, messagebox nem filedialog.** Progresso e log via callbacks/eventos. Isso viabiliza CLI, testes e, futuramente, outra UI.
6. **Roteamento de motores explícito:** documento comum → `status_engine`; `MODEL` no tipo → `status_model_bim`. Hoje o Mapa dos Planos não roteia para o motor BIM — decidir na refatoração se deve (registrar a decisão).
7. **Casos de teste mínimos do status real** (extraídos das regras §8): aprovado direto; terminated ≤ 0A; terminated > 0A; fantasma com salvamento na própria revisão; fantasma resgatando histórico fantasma (→ NÃO EMITIDO); mudança de família 0→1; reprovado vencendo com atual fantasma vs atual real; reprovação em revisão numérica ignorada; planilha de comissionamento com Para Aprovação; Para Análise antes/depois/no dia do corte.
8. **Módulos candidatos a remoção** (decisão pendente, manter o código até lá): `dash_ib` (dashboard web). As funções de dataset ficam no core independentemente.

---

---

## 23. Log da Refatoração v3 (pacote `docmanager/`)

Refatoração backend/frontend iniciada em 2026-07. Código antigo preservado em `legacy/` (reparado da corrupção de copy-paste e congelado como **oráculo de testes diferenciais**). Novo pacote `docmanager/` com `core/` puro (zero UI), `services/`, `ui/`, `dashboard/`. Testes em `tests/` rodam nos dois pandas (3.x e 2.3.x).

### Decisões do usuário (2026-07-11)
- **Colunas de atraso do histórico:** QUATRO colunas — dias corridos brutos (tempo de ciclo) **e** atraso com desconto de SLA, para Itaipu e CMI (`Dias Itaipu`, `Atraso Itaipu`, `Dias CMI`, `Atraso CMI`) + `Data Prevista (Controle)`.
- **Docs previstos não postados:** entram como linhas sintéticas `NÃO EMITIDO`; `Atraso CMI = max(0, hoje − data_ref)` correndo até hoje.
- **Atraso da reemissão no histórico: conta SEMPRE** (decisão 2026-07-12). O histórico consolidado é a base bruta — toda reemissão gera Atraso CMI vs o retorno da revisão anterior. O recorte "só conta quando a revisão anterior foi reprovada" (regra de necessidade, ex.: 1A após o "0" final aprovado não deveria contar) é aplicado DEPOIS, na camada de análise de dados, que tem o Status Retorno da revisão anterior disponível. Mantém o histórico completo e move a regra de negócio para quem consome.
- **Coluna Data Prevista (Controle) é interna:** usada só para calcular o atraso; NÃO aparece no Excel do histórico.
- **Controle de Documentos é opcional:** o histórico roda com ou sem ele. Sem o Controle: não há Atraso CMI da 1ª emissão (0A, o "nascedouro" vs data prevista) nem linhas sintéticas dos documentos previstos e não postados.
- **Toggle VIP (regra estrita §10):** vira configuração persistida, **padrão DESLIGADO**. A exceção §8.2 (Para Aprovação em planilhas de comissionamento) fica **sempre ativa** — o toggle governa só o rebaixamento estrito. (A implementar nas Fases 5-6.)
- **Kaizen e Corella:** removidos (só no `legacy/`).

### Divergências de comportamento sancionadas (whitelist da regressão)
1. **Limiar de versão do Terminated em todos os motores** (§21.8): `truth_line.resolver_linha_da_verdade` unifica as 4 duplicações; revisão terminada pode "renascer" com versão maior. O legado descartava a revisão inteira.
2. **Borda 19/08 padronizada** (§21.3): regime novo ⇔ data ≥ 19/08/2024 em TODO motor (`constants.is_regime_novo`). O `gerar_dataset_dashboard` passou a usar `< 19/08` para o passado (antes `<=`, que sumia com `Em Processo` de 19/08).
3. **Regra morta removida** (§21.5): `'Análise 1ª Emissão'` no consolidado (provado inalcançável por diferencial cartesiano). Bucket `ERRO` mantido como sentinela.
4. **Ordenação de revisões do histórico** = CANÔNICA do ciclo de vida (`normalize.normalizar_revisao`, ljust-`z`), família por família (§3): `0AA<0AB<0A<0B<0<1A<…`. ~~Antes unificada na sort key de 3 níveis~~ — isso era um **ERRO** (jogava as aprovações secas `0/1/2` para depois das letras de famílias posteriores, desalinhando família e cadeia de atraso CMI). `sort_key_revisao` fica só para reproduzir o legado no harness. Builder wide ÚNICO (`core.wide.build_wide_table`) alimenta Excel e dashboard; Excel renomeia `Data Envio`→`Data de Envio` (layout legado + colunas novas ao fim).
5. **Controle de Documentos** lido com `dtype=str`/`dayfirst` (corrige códigos `'1234.0'` e datas invertidas); **REPROGRAMAÇÃO vence DATA PREVISTA**. Impacta a injeção da Data Prevista Etapa 1 do mapeamento (Fase 5).

### Mapa de módulos novos (de-para)
- `core/constants.py` ← listas de status espalhadas · `core/normalize.py` ← normalizar_revisao/sort keys/normalizar_codigo · `core/identity.py` ← localiza_doc_historico (AconexIndex O(1)) + índice reverso · `core/truth_line.py` ← 4 duplicações da linha da verdade · `core/status_engine.py` ← calcular_status_real · `core/status_model_bim.py` ← modelo BIM · `core/consolidation.py` ← consolidado/estrito/emitido/parado_com · `core/wide.py` + `core/delays.py` + `services/controle_docs.py` + `services/historico_consolidado.py` + `services/excel_io.py` ← histórico consolidado turbinado · `cli.py` ← headless.
- Pendências para o corporativo: nome exato do cabeçalho REPROGRAMAÇÃO; conferir fim do `aconex_reviwer.py` original; assets/.env reais; regressão old-vs-new com dados reais.

---

## 24. Entendimento profundo da base Aconex e avaliação do Histórico Consolidado (2026-07-14)

Estudo empírico sobre a base real (80.688 linhas, 5.181 documentos no recorte do histórico) + documentação oficial da API. **Nada desta seção foi implementado** — os itens 24.4/24.5 são um backlog de sugestões aguardando decisão do usuário.

### 24.1 Semântica real dos eventos (o que cada linha da extração É)

- Cada linha = **uma versão de uma revisão** (o Aconex incrementa `Versão` a cada re-upload/mudança de status). Mediana de 3 versões por revisão, p90 = 7, máx = 36 — a sequência de versões é a trilha de auditoria completa do trâmite.
- **`Fonte` (ReviewSource) carrega o ID do workflow** (`WF-xxxxxx`) quando a linha pertence a um ciclo de revisão; `Nenhum` caso contrário (37.898 linhas, exatamente as com `Status da Revisão` vazio). Semântica oficial: `WF-…` = Workflow, numérico = Transmittal, `SD-…` = Supplier Docs.
- **1 workflow = 1 ciclo de análise**: sequências típicas dentro de (WF, doc) são `Em Processo → veredito` (Aprovado c/ Comentários 3.756×, Para Assinatura 2.875×, Não Aprovado 2.759×, Aprovado 1.243×). Nenhum WF cobre 2 revisões do mesmo doc. Envios têm WF em 99,9%; vereditos em 87–99,6%.
- **45% dos workflows cobrem mais de um documento** → a Itaipu analisa em LOTE. Tamanho do lote é uma variável explicativa de atraso ainda não explorada.
- **Pós-corte, `Para Análise` é um ESPELHO administrativo do envio** (sem WF; gap mediano de 0 dias vs `Em Processo`; 92,6% em 0–1 dia). Descartá-lo (regra atual) perde quase nada — EXCETO 291 revisões onde ele é o único marcador de envio (não têm `Em Processo`).
- **O último retorno costuma ser formalização, não veredito**: nas 679 revisões com retornos múltiplos, o gap 1º→último é mediana 40 d / p90 243 d, com pares `Não Aprovado → Aprovado` (244×) e `Para Assinatura → Aprovado` (111×). O "Aprovado" final vem SEMPRE em outro WF (0 casos no mesmo WF) — é o ciclo de assinatura/formalização. O veredito técnico da Itaipu é o PRIMEIRO retorno do ciclo.
- Ciclo interno do consórcio é visível nos status descartados (`Para Integraçao` 5.226, `Em Validação` 4.797, `Validado` 2.817, `Em Integração` 2.381, `Não Validado` 1.291, `Integrado` 881…) e nas revisões de 3 chars (12.118 linhas, 15% da base): 253 docs têm ciclo interno E 0A, mediana 69 d de integração→0A.
- Qualidade de dados: 36 linhas com revisões anômalas (`-` 27×, `OA` 8×, `OB` 1× — letra O no lugar de zero). Volume desprezível, mas merece flag.

### 24.2 O que as regras atuais acertam (validado nos dados)

1. 1 linha por (Tracking, Revisão) com envio/retorno atende ao objetivo do relatório; ordenação por família corrigida (§18.5).
2. Filtros (Terminated, status internos, modelos, revisões 3+ chars) são CORRETOS para um relatório de trâmite com o CLIENTE.
3. Mapeamento pré-corte (`Em Processo`→interno, `Para Análise`→envio) e descarte do espelho pós-corte: empiricamente sustentados.
4. Célula vazia em descontinuidade ("nunca inventar número") e data_ref (REPROGRAMAÇÃO > prevista) + linhas sintéticas: sólidos.

### 24.3 Limitações encontradas (quantificadas)

| # | Limitação | Evidência |
|---|---|---|
| L1 | Sub-ciclos dentro da revisão são colapsados (fica só o último envio + último retorno) | 12,9% das revisões têm >1 envio (máx 7); 5,4% >1 retorno (máx 5) |
| L2 | `Dias Itaipu` usa o ÚLTIMO envio e o ÚLTIMO retorno da revisão → quando há formalização depois do veredito, mistura as duas coisas. **Verificado empiricamente (2026-07-14, novo = legado)**: no caso-teste (0B com 2 ciclos + formalização) ambos mostram 86 d, em vez dos 19 d/10 d dos ciclos reais. No caso comum (1 ciclo por revisão, ~95%) o número está CORRETO — a distorção vive na cauda | 679 revisões (5,4%); inflação mediana 40 d, p90 243 d |
| L3 | Revisões EM ABERTO **aparecem no relatório** (linha com envio preenchido e retorno vazio) — o usuário estava certo. O que falta é só o NÚMERO de dias correndo: as 4 colunas de contagem ficam `<NA>` | 625 em aberto; 349 > 15 d; 199 > 90 d |
| ~~L4~~ | **RETIRADA (2026-07-14)** — o usuário mandou reconferir com a regra do corte, e ele tinha razão: os 291 vinham de uma conta que ignorava o mapeamento pré-corte (`Para Análise` antigo → envio). Refeita a conta com o pipeline completo, um fallback de `Para Análise` pós-corte resgataria só **2** revisões. Restam 169 (T,R) com retorno sem NENHUM evento de envio na base (causa diversa, sem regra que valha) e 379 só-`Para Análise` (sem envio nem retorno) | verificação de 2026-07-14 |
| L5 | `Para Aprovação` exterminado sem registro do que é (estágio de assinatura do fluxo novo) | 8.341 eventos |
| L6 | Ciclo interno CMI (0AA/validação/integração) 100% invisível no histórico | ≈17k eventos descartados |

### 24.4 SUGESTÕES — melhorias no tratamento (backlog, aguardando decisão)

- **S1. Parear ciclos por WF id** (`Fonte`): envio↔veredito do MESMO workflow. Resolve L1/L2 na raiz. Formatos possíveis: (a) 1 linha por ciclo (muda a granularidade do Excel) ou (b) manter 1 linha por revisão e acrescentar `Nº de Ciclos`, `Data 1º Veredito`, `Status 1º Veredito` (menos invasivo).
- **S2. Separar veredito de formalização**: `Dias Itaipu (veredito)` = 1º retorno − envio; manter o status final em coluna própria (`Status Final`/`Data Formalização`). Elimina a inflação de p90 243 d.
- **S3. Aging em aberto — ✅ IMPLEMENTADA (2026-07-14, forma decidida pelo usuário)**: nas PRÓPRIAS colunas `Dias Itaipu`/`Atraso Itaipu` (não em coluna nova). Regra: revisão sem retorno cujo envio é o **mais recente do documento** conta hoje − envio (e atraso = − SLA); revisões sem retorno **superadas** por envio mais novo continuam vazias (o relógio não corre para sempre). Na base real: 569 pendências passaram a contar (238 com atraso corrente), 56 superadas vazias, 12.282 fechadas inalteradas. Séries mensais do dashboard agrupam por Data Retorno → pendências não distorcem a evolução; médias gerais passam a incluí-las (intencional).
- ~~**S4. Fallback de envio**~~ — RETIRADA: com a regra do corte aplicada, resgataria só 2 revisões (ver ~~L4~~).
- **S5. Métricas de lote**: `Docs no mesmo WF` por ciclo; cruzar tamanho do lote × tempo de resposta.
- **S6. Ciclo interno (opcional/aba separada)**: `Dias ciclo interno` (1º evento interno → envio 0A) por documento; usa os eventos hoje descartados. Contrapartida justa: mede a CMI com a mesma régua.
- **S7. % no prazo por mês** no dashboard (taxa de cumprimento de SLA) em vez de só média de atraso — média esconde bimodalidade (muitos no prazo + cauda longa).
- **S8. Flag de família**: `Reemissão pós-aprovação` (1A depois do "0" aprovado) ≠ retrabalho por reprovação — ajuda a camada de análise a cortar o atraso CMI "sempre conta" com critério (312 docs têm >1 família).
- **S9. Relatório de qualidade de dados**: revisões anômalas (`OA`, `-`), retorno sem envio, envio duplicado sem retorno etc.

### 24.5 Dados novos da API — VERIFICADO NO PROJETO REAL (2026-07-14, via `/register/schema` + consultas de teste)

O schema do register DESTE projeto expõe 31 campos. Resultado dos testes (scripts no scratchpad, nenhum código do repositório alterado):

**Disponíveis mas DESCARTADOS:**
- **`numberOfMarkups`** (rótulo do schema "Número de Anotações"; tag `NumberOfMarkups`) — **❌ NÃO é a contagem de Anotações do site (§24.9, verificado 2026-07-15)**. Conta **elementos de marcação**, não anotações: no doc `6213-60-T0201-P` deu v32=344 (site 147), v93=19 (site 10); só coincide quando a anotação tem 1 elemento (v55=86, v66=7). Não há endpoint de markups (todos 404 `URL_UNKNOWN`) nem outro campo no schema → **impossível obter a contagem real por esta API; coluna REMOVIDA da extração**. O "16,6%/mediana 7" abaixo era contagem de ELEMENTOS, não de anotações.
- **`markupLastModifiedDate`** (tag `MarkupLastModifiedDate`) — data do último markup; removida junto (sem a contagem, inútil).
- `modifiedby` (tag `ModifiedBy`) — devolve **IDs numéricos de usuário** (não nomes); para distinguir CMI×Itaipu exigiria a Directory API. Valor secundário.
- `filename`, `fileType`, `confidential` — funcionam; pouco úteis para o histórico.

**Armadilhas descobertas (registrar!):**
- `page_size` do register só aceita os valores canônicos (25/50/…/500) — `page_size=1` responde **400** para QUALQUER campo (custou uma rodada inteira de falsos negativos).
- `registered` volta com a tag **`DateModified`** — é o MESMO campo que já usamos como "Data de Alteração" (por isso "não aparecia" na extração; é duplicado, não faltante).
- `markupdate` e `uploaddate` constam do schema mas são **rejeitados** como `return_fields` (provavelmente só pesquisáveis).

**NÃO existem no schema deste projeto** (embora citados no guia genérico da Documents API): `dateReviewed`, `dateForReview`, `toClientDate`, `plannedSubmissionDate`, `milestoneDate`, `comments`, `author`, `approved`, `received`, `attribute1–4`. Janelas oficiais de análise e datas planejadas, se quisermos, teriam de vir da **Workflows API** (guia em PDF; contrato a confirmar) — os `WF-…` do nosso `Fonte` e os `CMI-…-WTR-…` do Controle apontam para esses objetos. Mail API idem (transmittals/threads).

Observação: `Control CMI` (2% preenchido) é hoje extraído e quase inútil.

### 24.6 PROPOSTA EM VALIDAÇÃO — regra do "último ciclo consistente" (caso 0C/0D, 2026-07-14)

Caso real (Tracking `1353331688112390977`, doc `#ITA0=Y01YBQ00&ACC051`): a 0C real foi enviada 05/06/23 e voltou 19/06/23; em 24/07/23 subiram a emissão seguinte etiquetada "0C" por engano (corrigida para 0D no mesmo dia). Como o pipeline escolhe o ÚLTIMO envio da revisão, a 0C ficou com envio 24/07 > retorno 19/06 → datas invertidas, contagem em branco, Data de Envio errada. O usuário alertou que "pegar sempre o primeiro" também erraria: existe o caso legítimo de RELANÇAMENTO (doc volta à 0A depois da 0B — reinício de vida), onde vale a segunda parte e desprezam-se os eventos anteriores.

**Regra proposta (por revisão)** — retorno permanece o último (S2 fora desta decisão):
1. envio = último `Em Processo` com data ≤ data do retorno escolhido (par consistente);
2. envio POSTERIOR ao último retorno da revisão:
   a. se for o ÚLTIMO evento do documento inteiro (data+versão) → ciclo novo EM ABERTO: envio = ele, retorno = vazio (cai na contagem em aberto da S3) — cobre o relançamento;
   b. senão → subida errada (corrigida logo depois, como a 0C→0D) → ignorar;
3. sem retorno na revisão → último envio (comportamento atual).

**Impacto medido na base real**: altera **29 de 12.936 revisões (0,2%)** — TODAS hoje quebradas (datas invertidas/em branco). 4 viram ciclos completos corretos (padrão 0C: a linha volta a contar, ex.: 0C = 14 dias) e 25 viram "em aberto com a Itaipu" (padrão relançamento). Nenhuma linha saudável muda.

**✅ IMPLEMENTADA (2026-07-14, regra completa validada pelo usuário)** em `core/wide.py` (etapa 5 do `gerar_dataset_dashboard`), com 2 testes travando os padrões (subida errada ignorada; relançamento vira pendente). Conferido na base real: doc do exemplo com 0C = 14 d e **zero** linhas de datas invertidas no histórico (eram 29); 13.105 revisões preservadas.

### 24.7 ✅ 'Para Aprovação' como ENVIO-fallback (2026-07-14, pedido do usuário)

No início do projeto, o envio da revisão definitiva ("0") subia como **'Para Aprovação'** — que o pipeline extermina — deixando a revisão com retorno e SEM envio (ex.: doc `#ITA0=Y01YBQ00&ACC051`, rev 0: PA 17/10/23 → Aprovado 23/10/23). Regra implementada em `core/wide.py`: quando a revisão **não tem** 'Em Processo', o último `Para Aprovação` com data ≤ retorno vira o envio (rotulado 'Em Processo' no wide, mesma convenção do 'Para Análise' pré-corte). **PA nunca vira retorno e nunca substitui envio real** (os 3.407 PA em revisões com envio ficam intocados; comissionamento→'Para Assinatura' inalterado). Base real: **118 revisões resgatadas** (103 na rev "0"; 115 pré-corte; Dias Itaipu mediana 9 d) — retorno-sem-envio caiu de 169 para 51. 2 testes travam o fallback e a não-substituição.

### 24.8 ✅ Retorno fantasma de comissionamento + Controle multi-abas (2026-07-14)

Dois erros apontados pelo usuário com prints reais:

**(a) Planilha de comissionamento NUNCA emitida aparecia com retorno "Para Assinatura"** (doc `#ST50=B01BDV10&BDC031`: só `Para Aprovação`×2 + `Em Validação`, sem nenhum envio). Causa: a exceção do comissionamento (PA→`Para Assinatura`) fabricava um RETORNO para revisão sem emissão. Regra corrigida em `core/wide.py`: o `Para Assinatura` vindo do relabel (`_pa_comiss`) **só vale como retorno se a revisão tiver envio**; sem envio e sem retorno real, a revisão **não entra** no wide (e o doc vira sintética NÃO EMITIDO se estiver no Controle). Princípio do domínio: **não existe retorno de documento não emitido**. Planilhas emitidas seguem exatamente como antes. Base real: 2 fantasmas eliminados (13.105→13.103); zero `Para Assinatura` órfãos restantes.

**(b) Data Prevista em branco com a linha PREENCHIDA no Controle** (doc `#ST00=U01BFA10UC012-UC009&EDC080` / `0893410CYU20-209FDC-16`). Correções em camadas (`services/controle_docs.py`):
- ~~`ler_controle` varre todas as abas~~ → **REVERTIDO a pedido do usuário (§24.8c)**: lê **apenas a aba selecionada** no seletor da interface — o usuário aponta a aba certa; o seletor existe para isso.
- Código duplicado (mesmo doc em mais de uma linha): a linha **com data vence** a sem data.

**§24.8b — causa raiz provável (2026-07-14, segunda rodada)**: `obter_codigos_historicos` devolve um **set (ordem aleatória)** e `datas_por_codigos` retornava na PRIMEIRA linha casada **mesmo sem data** — se um dos códigos do doc casasse com uma linha sem data do Controle, o sorteio da ordem decidia se a data aparecia. Correções:
- `datas_por_codigos`/`resolver_para_codigos`: linha **com data** vence; a sem data só entra se não houver melhor.
- **Chave de casamento tolerante** (`chave_codigo`): além do `normalizar_codigo`, remove TODO espaço interno, NBSP e invisíveis (zero-width/BOM) — "como a busca na mão" do usuário.
- **Célula multi-código** (quebra de linha/';' numa célula): indexa todos os códigos; as sintéticas usam a mesma chave (senão doc postado viraria sintética duplicada).
- **Log de diagnóstico**: `gerar_historico(log_cb=...)` informa "Controle ↔ histórico: X de Y documentos casaram" no console da view.
7 testes travam os comportamentos. Beneficia igualmente o Mapa (injeção da Data Prevista Etapa 1).

**§24.8c — varredura final (2026-07-14, terceira rodada, sugestão do usuário)**: como o caso persistiu no corporativo, foi implementada a varredura de ÚLTIMO recurso em `varredura_final_controle` (historico_consolidado): ao fim do casamento normal, cada documento que ficou SEM data procura os códigos **da própria linha do wide** direto no Controle — 1º por igualdade (chave tolerante), 2º por **CONTÉM** (`ControleDocs.buscar_contendo`, como o Ctrl+F manual que o usuário usou: pega célula com decoração/texto em volta do código; `min_len=8` evita falsos positivos; linha com data vence). As linhas do Controle usadas pela varredura NÃO viram sintéticas (`ignorar_ids`). O log passou a informar "(N pela varredura final)". Decisão do usuário na mesma rodada: `ler_controle` **voltou a ler só a aba selecionada** (o seletor da interface aponta a aba certa). **Status (2026-07-15): não resolveu 100% no corporativo** — usuário decidiu deixar de lado por ora e priorizar §24.9 (comentários). A depuração com o arquivo real (compliance) fica como próximo passo quando ele retomar.

### 24.9 Extração: Tipo de Tramitação (✅ mantido) + Anotações (❌ removido) (2026-07-15, pedido do usuário)

Pedido: trazer para a **extração do Aconex** (a) os comentários de cada revisão e (b) os fluxos ("onde cada revisão foi tramitada"), sem quebrar nada. Implementado em `docmanager/aconex_backend.py` — puramente **aditivo** (só novas colunas; nada downstream lê por posição, `carregar_base_aconex` casa tudo por nome).

**(a) Anotações por revisão — ❌ TENTADA E REMOVIDA (2026-07-15)**. Tinha sido implementada via `numberOfMarkups` + `markupLastModifiedDate` (colunas "Qtd. de Anotações"/"Data da Última Anotação"). **Removida** após verificação na API real (doc `6213-60-T0201-P`): o campo conta **elementos de marcação**, NÃO as "Anotações" do site. Comparação com o site: v32=344/**147**, v93=19/**10** (infla ~2×), coincidindo só quando a anotação tem 1 elemento (v55=86/86, v66=7/7). Investigação (scripts no scratchpad, 3 rodadas):
- **Nenhum endpoint de markups existe** — `/register/{docId}/markups`, `/markup`, `/annotations`, `/comments`, nível projeto, documento único: TODOS **404 `URL_UNKNOWN`**. O register é só busca.
- **Schema** (200): únicos campos de markup são `numberOfMarkups`, `markupLastModifiedDate`, `markupdate` (rejeitado). **Nenhum** campo de contagem de anotações.
- Sem fonte confiável e sem fórmula de correção (razões 2,34 / 1,9 / 1,0 / 1,0), a decisão do usuário foi **"melhor tirar do que ter algo errado"** → colunas removidas do `CAMPOS_STRING`/`MAPA_COLUNAS`/`ORDEM_COLUNAS`. **A contagem de anotações do site NÃO é obtível por esta API REST.** (Falso positivo intermediário: 0D/0E *pareciam* bater com 32/19, mas eram os valores da versão de veredito; com mais dados do site o usuário mostrou que não fecha.)
- Nota lateral a investigar: nas 20 versões desse doc o `current` voltou `false` em TODAS — conferir a semântica do campo `Current` no register.

**(b) Fluxos / "onde foi tramitada"** — a Fonte (ReviewSource) **já carrega** o `WF-…`/Transmittal/`SD-…` (o usuário suspeitava certo). Acrescentei a coluna derivada **`Tipo de Tramitação`** (ao lado de Fonte) via `classificar_fonte`: `WF-…`→"Fluxo", numérico→"Transmissão", `SD-…`→"Docs. Fornecedor", `Nenhum`/vazio→"". Isso torna legível o MECANISMO na própria base. **NÃO diz a etapa/organização** de destino — isso é workflow routing e também depende da Workflows API (corporativo).

**Robustez**: `import requests` virou **tardio** (dentro de `extrair_base`) — o módulo passou a importar sem a lib, então `montar_dataframe`/`classificar_fonte`/`_parse_pagina` (funções puras) rodam em qualquer ambiente. A montagem do DataFrame foi extraída para `montar_dataframe(registros)` (pura, sem rede) → testável. `tests/test_aconex_backend.py`: 10 testes (classificação da Fonte, parse de XML, rename/derivação/ordem/formatação de data, colunas desconhecidas preservadas no fim). Verde nos 2 venvs; suíte completa intacta.

**Próximo (aguardando o usuário)**: o usuário avisou (2026-07-15) que o **Histórico Consolidado será REFORMULADO** e passará a especificação depois. A contagem de anotações NÃO entra (não é obtível pela API — ver acima). Se quiser o TEXTO/roteamento dos fluxos, seria a Workflows API no corporativo.

### 24.10 ✅ Status Documentos: destaque do código buscado vs. o resolvido (2026-07-15, pedido do usuário)

O módulo de Status resolve cada código buscado pelo **Tracking ID** (via `AconexIndex`, cascata ouro/prata/bronze), então acha o documento mesmo quando o código Itaipu/CMI mudou — e a saída mostra o código **vigente**. O usuário não enxergava *quais* haviam divergido da busca. Duas causas de divergência, distinguidas (o usuário percebeu ambas ao ver 23 NÃO EMITIDO na Via Rápida por CMI vs. 6 na Via Excel com os 2 códigos → os "extras" foram achados pelo Itaipu porque o CMI colado estava errado):

- **Detecção** (`core/reports/status_docs.py`): `_classificar_codigo_busca(buscado, vigente, hist_norm)` compara por `normalizar_codigo` e devolve, por posição de código, uma de 3:
  - `''` — não buscado ou confere com o vigente;
  - `'atualizado'` — difere do vigente MAS o buscado É um código que o documento já teve (`obter_codigos_historicos`) → **mudou no sistema**;
  - `'nao_confere'` — difere e o buscado NUNCA pertenceu ao doc → o doc foi achado pelo OUTRO código e este não bate → **provável erro na lista**.
  Cada linha carrega `_itaipu_status`/`_cmi_status` + `_itaipu_buscado`/`_cmi_buscado` (o que o usuário digitou, p/ o comentário) + `_itaipu_real`/`_cmi_real`. **A célula mostra sempre o código VIGENTE (correto) do documento quando ele existe** — inclusive no `'nao_confere'` (o correto vai para a célula; o errado, para o comentário — inversão pedida pelo usuário 2026-07-15). Sem código vigente (doc não possui esse código), mantém o buscado.
- **Destaque** (`services/excel_io.py`): `'atualizado'` → **texto azul `#0070C0`** (só a fonte, sem preencher a célula, **sem negrito**, preservando a zebra). `'nao_confere'` → **SEM cor, apenas um comentário** na célula (decisão do usuário 2026-07-15): "O código informado ('X') estava errado…" (ou "…não confere — o documento não possui esse código"). Legenda (tooltip) nos cabeçalhos. As chaves `_...` NÃO viram coluna.
- **Coerência com a Via Rápida**: `'nao_confere'` só dispara quando o doc É encontrado (pelo outro código). Um código único errado na Via Rápida → não acha → NÃO EMITIDO → nada marcado (correto: não há cruzamento possível), exatamente como o usuário raciocinou.
- **UI** (`ui/views/status_view.py`): loga separadamente "N com código atualizado (azul)" e "M com código informado errado — corrigido; ver comentário".
- Testes em `test_reports.py` (6): marca Itaipu/CMI atualizado, vigente não marca, CMI não confere (célula com o CORRETO + `_cmi_buscado`), não confere sem CMI no sistema, e export lê o azul `0070C0` + o comentário do não-confere. Verde nos 2 venvs. (Obs.: usuário escreveu `#00700C0` — 7 dígitos; usado o azul padrão Office `#0070C0`.)

### 24.11 ✅ Histórico Consolidado REFORMULADO — dirigido pelo Controle (2026-07-15, spec do usuário)

**Inversão do motor**: o Histórico deixou de ser dirigido pelo Aconex (listava todos os docs + sintéticas) e passou a ser **dirigido pelo Controle (obrigatório)** — o Controle define QUAIS documentos entram; o extrato Aconex fornece o histórico de cada um. `gerar_historico(df_bruto, controle, ...)` agora **exige** o Controle (erra se `None`); a UI marcou o seletor como obrigatório.

**Fluxo** (`services/historico_consolidado.py`): `gerar_dataset_dashboard` → `build_wide_table` (todos os docs) → `AconexIndex` + índice `chave_codigo` (`_indice_chave`). Para cada linha do Controle:
- `_buscar_tracking`: cascata EXATA `idx.localizar` (par Itaipu+CMI → CMI → Itaipu, como o módulo de Status) e, se falhar, fallback tolerante por `chave_codigo` (sujeira de Excel / multi-código, §24.8b).
- **achou tracking com revisões** → as revisões do doc (do wide) + `Tracking ID` + nova coluna **`Fase de Projeto`** + Data Prevista/Reprogramação do Controle.
- **não achou** (ou tracking sem revisão válida — ex.: só integração interna/`Para Integração`, ou fantasma de comissionamento) → **1 linha `NÃO EMITIDO`** com `Tracking ID` em BRANCO (interno único durante o cálculo do atraso, apagado na saída), campos do Aconex vazios, Fase/códigos/datas do Controle. Atraso CMI "correndo até hoje" (`hoje − data_prevista`).
- **Log de divergência**: doc marcado `EMITIDO` no Controle (coluna `EMITIDO / NÃO EMITIDO`) mas SEM tracking algum → sinalizado no log (pedido do usuário). Não dispara para tracking-sem-revisão (esse tem tracking).
- Docs no Aconex mas **fora do Controle** → não aparecem.

**`controle_docs.py`**: `ControleRow` ganhou `fase` (FASE DE PROJETO) e `emitido` (+ `esta_emitido`); `_ler_aba` casa as colunas `FASE DE PROJETO`/`FASE DEL PROYECTO` e `EMITIDO / NÃO EMITIDO`.

**Outras mudanças pedidas juntas**:
- **Ordem das colunas de atraso**: `Dias CMI`, `Atraso CMI` agora vêm ANTES de `Dias Itaipu`, `Atraso Itaipu` (`excel_io._COLUNAS_NOVAS`). `Fase de Projeto` é a 1ª coluna.
- **Primeira data do retorno** (`core/wide.py::_retorno_representativo`): mesma revisão + mesmo status de retorno com 2+ datas → vale a 1ª (a 2ª é atualização de metadados, gerava atraso artificial). Caso real do gerador diesel `#ST00=B01BDV10&ACC051` (envio 03/01/2024, retorno real ~2 dias depois, não 25/09/2025). Divergência SANCIONADA do legado (só muda quando há retornos duplicados de mesmo status).
- **O motor de atraso do Histórico NÃO se propaga ao Mapa**: são caminhos separados (`core/delays.py::calcular_atrasos` vs `core/kpis.py::calcular_atrasos_acumulados`). O Mapa pode ter o mesmo problema do metadado poluído (pega a versão mais alta) — conserto seria separado, na linha da verdade.

**Validação na base real** (`dados_reais/base_aconex.xlsx`, 80.688 linhas / 9.465 trackings, × os 311 docs do Controle colados, 2026-07-15): **188 encontrados** (446 revisões), **121 não emitidos** = 71 futuros (execução 2027-2035, legítimo) + 48 ausentes da base (não emitidos de verdade / pós-extração de 12/jul / eventuais typos da transcrição) + 2 presos em integração interna (NÃO EMITIDO correto). **ZERO bugs de busca.** Todas as 6 fases fluíram; Tracking preenchido nos emitidos e em branco nos não emitidos.

**Testes**: `test_historico_consolidado.py` reescrito (26) para o fluxo Controle-dirigido (Controle obrigatório, só-docs-do-Controle, Fase+Tracking, não-emitido tracking-em-branco + atraso corrente, log emitido-sem-tracking, busca tolerante, ordem CMI<Itaipu, e todas as regras do wide preservadas via Controle). `test_wide.py`: +1 (primeira data do retorno). Verde nos 2 venvs.

**Pendências**: `EMITIDO / NÃO EMITIDO` não veio na amostra de 311 (só 5 colunas) → o log de divergência não teve como disparar no teste, mas está programado para o arquivo real completo (8289 linhas). Docs com código dirty/multi-código extremos: cobertos pelo fallback `chave_codigo`; decorado por prosa (containment, ex-`buscar_contendo`) NÃO é mais usado (Controle-dirigido busca no Aconex, não o contrário).

---

*Fim do documento. Ao alterar qualquer regra descrita aqui, atualizar a seção correspondente e registrar a motivação (este arquivo é a fonte da verdade do domínio).*
