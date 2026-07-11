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
- **Tabela wide:** 1 linha por (Tracking, Revisão) com Data/Status de Envio e Retorno + `SLA_Itaipu` (30 p/ 0A, 15 demais). Sort key de revisão: letras puras < revisões-letra < numéricas.
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

*Fim do documento. Ao alterar qualquer regra descrita aqui, atualizar a seção correspondente e registrar a motivação (este arquivo é a fonte da verdade do domínio).*
