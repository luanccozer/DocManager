# Entendimento do Projeto e dos Dados — DocManager Itaipu

> Documento de compreensão ativa: o que o projeto significa, como os dados reais
> estão estruturados e que insights eles já revelam. Complementa a
> `knowledge_base_docmanager.md` (que é a fonte das regras de negócio).
> Base analisada: extração real de **80.688 linhas** do Aconex (11/07/2026).

---

## 1. O que é o projeto (o significado)

Itaipu Binacional está passando por uma **modernização tecnológica** (atualização
tecnológica — "AT"). A **CMI** (consórcio executor / fornecedor) é responsável por
projetar, montar, comissionar e entregar toda a documentação de engenharia dessa
modernização. A **Itaipu (IB)** é o cliente que analisa e dá vereditos.

Toda a documentação tramita pela plataforma **Aconex** (gestão documental da Oracle).
Cada documento nasce, é enviado à Itaipu para análise, volta aprovado ou reprovado,
é reemitido quando reprovado, e assim por diante até a **aprovação final para
construção** (a revisão numérica "0"). Depois pode haver novas famílias (1A, 1B, 1…)
quando surge uma nova necessidade de alteração.

**O problema que o DocManager resolve:** o status que o Aconex mostra na linha vigente
frequentemente NÃO representa a situação real do documento (revisões canceladas,
status internos de integração, mudanças de fluxo do cliente, ciclos internos da CMI).
O sistema interpreta o histórico completo de cada documento e responde:
**"qual é o status REAL de cada documento, e quem está devendo o quê a quem?"**

Isso alimenta:
- O **Mapa dos Planos** (a estratégia de execução em 4 níveis: Plano de Execução →
  planos de suporte → planilhas de comissionamento → documentos técnicos).
- O **controle de prazos e atrasos** (SLAs de análise da Itaipu e de reemissão da CMI).
- Relatórios executivos e um dashboard.

**Por que importa:** cada dia de atraso na documentação atrasa a liberação da execução
física da modernização. Medir atraso com honestidade (quem causou, quanto) é o que dá
poder de cobrança e de negociação.

---

## 2. Estrutura dos dados (base Aconex)

A extração da API gera **uma linha por versão de cada revisão de cada documento**
(histórico completo). Volumes reais:

| Métrica | Valor |
|---|---|
| Linhas (eventos) | 80.688 |
| **Documentos reais (Tracking ID único)** | **9.465** |
| Códigos "No. do Documento" distintos | 14.000 (código muda ao longo da vida!) |
| Códigos CMI distintos | 8.232 |
| Linhas vigentes (Current=true) | 9.094 |
| Revisões canceladas (Terminated) | 1.056 |
| Janela temporal | 10/10/2022 a 11/07/2026 |

### 2.1 As 19 colunas e o que significam

| Coluna | Significado |
|---|---|
| **Tracking ID** | Chave IMUTÁVEL do documento. A identidade real (código muda, esta não). |
| No. do Documento | Código Itaipu (ex.: `#ST50=U01…`). Muda entre revisões. |
| Controle do Emissor | Código CMI (ex.: `0893410CYU20-…`). Mais estável, mas também muda. |
| Revisão | `0A→0B→…→0→1A→…`. Letra = análise; número = definitivo p/ construção; 3+ chars (`0AA`) = ciclo interno CMI. |
| Versão | Contador interno do Aconex dentro da revisão (critério de "mais recente"). |
| Status | Veredito/estado bruto daquele evento. |
| Status da Revisão | Onde aparece "Terminated" (revisão anulada). |
| Data de Alteração | Data do evento (dd/mm/yyyy). |
| Current | Flag da linha vigente. |
| Título, Tipo do Documento, Especialidade, Subespecialidade, Tipo/Subtipo DCC, Fonte, Idioma, Control CMI, Disciplina | Metadados. |

### 2.2 Distribuição de revisões (o retrato do projeto)

| Revisão | Eventos | Leitura |
|---|---|---|
| 0A | 30.417 | A maioria dos documentos ainda está na **primeira emissão**. |
| 0B | 11.861 | Segunda rodada (após comentários/reprovação). |
| **0** | 9.755 | Chegaram à **aprovação final para construção**. |
| 0AA | 7.284 | Ciclos internos de integração (não são tramitação com o cliente). |
| 0C/0D/0E… | ~11k | Rodadas seguintes. |
| 1A, 1, … | ~2k | Poucos documentos entraram em **nova família** (revisão do já aprovado). |

**Insight estrutural:** o projeto está majoritariamente na fase de primeira análise
(0A/0B). Poucos documentos "renasceram" numa família 1 — o que faz sentido: a família
1 só nasce quando algo já aprovado precisa mudar.

### 2.3 Distribuição de status (top)

`Para Análise` (17.271) e `Em Processo` (14.778) dominam — coerente com o **marco de
19/08/2024**: a partir dele a submissão virou fluxo (workflow), e "Em Processo" passou
a significar "chegou à Itaipu". `Para Aprovação`, `Para Integração`, `Em Validação`,
`Validado` são **status fantasmas** de integração (ciclos internos, não tramitação real
com o cliente) — o motor de status real os ignora. **69.244 das 80.688 linhas são
pós-corte** (regime novo).

### 2.4 Tipos de documento

`Documento Técnico` 72.440 · `Modelo` (BIM) 6.589 · `Management Document` 850. O
histórico consolidado considera só Documento Técnico e Management Document; Modelos têm
motor próprio (fases LOD).

---

## 3. Insights da base real (11/07/2026)

Calculados sobre o histórico consolidado (13.105 revisões, 5.098 documentos com envio real).

### 3.1 A Itaipu tem impactado os atrasos? **Sim.**

- **51%** das revisões voltam **com atraso** da Itaipu (6.310 de 12.282).
- Tempo médio de análise: **23,5 dias**; atraso médio: **7,4 dias**.
- **Total: ~90.868 dias-documento** de atraso atribuíveis à Itaipu.

### 3.2 O SLA de 15 dias é mais difícil que o de 30

| Revisão | SLA | Análise média | % atrasadas |
|---|---|---|---|
| 0A (primeira emissão) | 30 dias | 28,9 dias | **43%** |
| Demais revisões | 15 dias | 20,5 dias | **56%** |

A Itaipu quase cumpre os 30 dias da 0A, mas estoura com frequência os 15 dias das
reemissões — as rodadas seguintes é que mais atrasam.

### 3.3 Onde a Itaipu mais atrasa (por especialidade)

`SERVIÇOS AUXILIARES ELÉTRICOS` é o pior gargalo: **68% das revisões atrasadas**, atraso
médio 12,4 dias, sobre volume alto (2.236 revisões). Seguem `Segurança Cibernética`,
`Serviços Auxiliares Mecânicos`. `Unidade Geradora` (2.383 rev) e `Controle Centralizado`
(3.885 rev) têm ~50% de atraso sobre volumes grandes.

### 3.4 Itaipu vs CMI

| Lado | Dias-documento de atraso | Revisões | Por incidente |
|---|---|---|---|
| **Itaipu** (análise) | 90.868 | 12.282 | 7,4 (frequente, espalhado) |
| **CMI** (retrabalho pós-reprovação) | 164.534 | 2.543 | 64,7 (raro, mas profundo) |

Leitura: a Itaipu atrasa **com frequência** (em metade de tudo), a CMI atrasa **fundo**
(poucos casos, mas cada retrabalho após reprovação demora muito). ⚠️ O total da CMI
ainda **não inclui o nascedouro** (atraso da primeira emissão vs data prevista) — isso
depende do Controle de Documentos, ainda não integrado; quando entrar, o número da CMI
sobe.

### 3.5 Piores atrasos individuais da Itaipu

Documentos com >500 dias de atraso existem (ex.: `#ST00=C01CBD01&ACC051` 0B com 551
dias), quase todos Documento Técnico. São candidatos a investigação pontual.

---

## 4. Perguntas que os dados podem responder (roadmap de análise)

- Evolução do atraso ao longo do tempo (a Itaipu está melhorando ou piorando?).
- Atraso nos documentos **estruturantes** (níveis 1-2 do Mapa) — os que travam a execução.
- First Time Right: % de 0A aprovadas de primeira (sem reprovação).
- Correlação entre especialidade/DCC e número de ciclos até aprovar.
- Backlog diário de documentos "com a bola na Itaipu" acima do SLA.

---

*Atualizar quando novas extrações ou o Controle de Documentos mudarem o quadro.*
