# DocManager Itaipu

Aplicativo desktop da engenharia da CMI para controlar a documentação do projeto
de modernização de Itaipu. Cruza a extração do **Aconex** (fonte da verdade dos
status) com as planilhas internas (Mapeamento de Planos, Controle de Documentos)
e gera mapa de planos, status de documentos, histórico consolidado, dashboard e
relatórios.

---

## Como usar no notebook da empresa

### 1. Baixar o projeto

**Opção A — ZIP (mais simples):**
1. Acesse `https://github.com/luanccozer/DocManager`.
2. Botão verde **Code → Download ZIP**.
3. Extraia a pasta em um local **fora do OneDrive** (ex.: `C:\Apps\DocManager`)
   para evitar lentidão de sincronização.

**Opção B — Git (recebe atualizações com `git pull`):**
```bat
git clone https://github.com/luanccozer/DocManager.git
```

### 2. Rodar

Dê **duplo-clique em `run.bat`** (ou rode `run.bat` no terminal). Na primeira vez
ele cria o ambiente virtual `.venv`, instala as dependências e abre o app. Nas
próximas vezes, só abre — em segundos.

> Precisa do **Python 3.12+** instalado (marque *"Add Python to PATH"* no
> instalador). Se não usar o `run.bat`, dá para rodar manualmente:
> ```bat
> py -3 -m venv .venv
> .venv\Scripts\activate
> pip install -r requirements.txt
> python -m docmanager
> ```

### 3. Configurar o segredo do Aconex (só para o módulo de Extração)

O segredo da API **não** vai no GitHub (fica fora do repositório por segurança).
Para usar a **Extração Aconex**:
1. Copie `.env.example` para um arquivo chamado `.env` na raiz do projeto.
2. Preencha o seu segredo:
   ```
   SECRET_LUAN=coloque_aqui_o_client_secret
   ```
O `.env` fica só na sua máquina. Os demais módulos (Mapa, Status, Histórico,
Relatórios) funcionam sem o `.env` — bastam os arquivos Excel.

---

## Os módulos (como usar cada um)

Em **todo** seletor de arquivo há um botão de **Aba (Sheet)**: escolha a aba certa
do Excel antes de rodar (para bases Aconex, a aba "Documentos" já vem selecionada).

- **🗺️ Mapa dos Planos** — atualiza a planilha de Mapeamento (status real,
  hierarquia, KPIs, atrasos). Selecione a **Base Aconex** + o **Mapeamento** e,
  opcionalmente, o **Controle de Documentos** (preenche datas previstas /
  reprogramação). O botão **⏳ Analisar Mudanças por Período (Delta)** abre a
  "Máquina do Tempo" comparando o status entre duas datas.
- **🔎 Status Documentos** — status real de documentos. Escolha a origem na aba:
  *Via Arquivo Excel* (arquivo + colunas), *Via Lista Rápida* (colar códigos) ou
  *Todos Aconex* (todos os vigentes). Botões no rodapé: **Gerar Status Atual**
  (Excel + gráfico) e **Analisar Delta do Período** (como os documentos daquela
  aba mudaram, agrupado por metadado).
- **📊 Histórico e Dashboard** — na aba *Planilha*, gera o Histórico Consolidado
  (1 linha por revisão + colunas de atraso Itaipu/CMI). Na aba *Dashboard*, sobe
  o painel web executivo (evolução do atraso, First Time Right, gargalos...).
- **📋 Relatórios** — Relatório de Avanço e Auditoria de Integração.
- **☁️ Extração Aconex** — baixa a base completa do Aconex via API (precisa do
  `.env`). Operação longa (~30 min em produção).
- **⚙️ Configurações** — liga/desliga a *Regra da Aprovação Intermediária* (VIP).

---

## Arquitetura (visão rápida)

```
ui/            interface (CustomTkinter) — uma view por módulo
  ↓ importa só de
*_backend.py   backend público de cada módulo (na raiz do pacote):
               mapa_backend · status_backend · historico_backend ·
               relatorios_backend · controle_backend · aconex_backend
  ↓ apoiado em
common.py      funções compartilhadas (carga da base, índice de identidade,
               linha da verdade, motores de status, KPIs) — o "cérebro" comum
  ↓ implementado por
core/          lógica pura, 100% testável (constantes, status, wide, atrasos...)
services/      I/O (Excel, config, orquestrações)
dashboard/     app web (Dash/Plotly)
```

Cada módulo tem **um** backend, que é a única porta que a interface enxerga. O que
é comum a vários módulos mora em `common.py`. A implementação detalhada e testada
fica em `core/` e `services/`.

Documentos de apoio: `docs/entendimento_projeto_e_dados.md` (o que é o projeto e
os dados), `docs/controle_de_documentos.md` (estrutura do Controle),
`knowledge_base_docmanager.md` (regras de negócio do domínio).

## Desenvolvimento

```bat
pip install -r requirements-dev.txt
pytest          REM roda a suíte de testes
```
