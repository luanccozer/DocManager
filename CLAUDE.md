# DocManager Itaipu

App desktop (Python, Qt) que cruza a extração do Aconex com as planilhas internas
(Mapa dos Planos, Doc List Mapping, Controle de Documentos). Visão geral no `README.md`;
regras de negócio na `knowledge_base_docmanager.md`; vocabulário no `GLOSSARY.md`.

Rodar os testes: `pytest` (a suíte inteira roda no CI do Linux, com Qt sem monitor).
Lint: `ruff check .`.

Planilhas e painéis reais do cliente (`Doc List Mapping*.xlsx`, `*.pbix`) nunca entram
no Git, nem códigos de documento reais nos documentos versionados.

## Agent skills

### Issue tracker

Specs e tarefas são arquivos markdown em `.scratch/`. Ver `docs/agents/issue-tracker.md`.

### Domain docs

Um contexto só: `GLOSSARY.md` na raiz e ADRs em `docs/adr/`. Ver `docs/agents/domain.md`.

## Idioma da interface

Texto de tela vai em português dentro de `t("...")` (`docmanager/ui/idioma.py`;
constante de módulo em `marcar()` e `t()` na hora de mostrar), com a tradução em
`docmanager/ui/recursos/idiomas/es.json` e `en.json`. Texto novo na tela:
`t()` + `python tools/textos_da_interface.py --faltando es` (e `en`);
`tests/test_idioma.py` reprova o que faltar. O log, os erros dos serviços e os
nomes de colunas e status das planilhas ficam em português.
