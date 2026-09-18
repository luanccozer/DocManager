# Histórico de versões

Este arquivo é a **fonte única** das novidades: a seção "O que há de novo" da
tela inicial lê o bloco da versão instalada, e o GitHub Actions usa o mesmo
bloco como descrição do Release. Ao preparar uma versão, acrescente o bloco
dela aqui **antes** de criar a tag.

## 3.1.0 — 2026-09-18

- Instalador oficial: o DocManager agora é gerado e publicado pelo GitHub, com instalador próprio — acabou o passo a passo manual de gerar o executável e zipar a pasta.
- Atualização automática: o app avisa quando sai uma versão nova, mostra o que mudou e se atualiza sozinho com um clique — funciona atrás do Zscaler e da VPN.
- Credenciais do Aconex cadastradas no próprio app: não é mais preciso receber nem editar o arquivo `.env`. Quem já tinha um tem o cadastro importado automaticamente.
- O Client Secret passa a ser guardado cifrado pelo Windows (DPAPI), na conta do usuário, em vez de ficar em texto puro no `.env`.
- A versão exibida no título, na barra lateral, na tela de carregamento e na Home passa a vir do próprio programa — sempre correta depois de uma atualização.
- Novidades e Releases saem do mesmo `CHANGELOG.md`: o que aparece na Home é exatamente o que foi publicado.
- Quando a Extração Aconex não conecta, o log passa a mostrar a causa real (timeout, DNS, conexão recusada) e um diagnóstico da rede — proxy do Windows, arquivo PAC, resolução de nome e teste da porta 443 — em vez do genérico "sem conexão".

## 3.0.0 — 2026-08-02

- Novo módulo Doc List Mapping: follow-up da lista de documentos com dois níveis e agrupamento por escopo.
- Doc List Mapping traz a Análise por Período — quais documentos estão previstos para emitir nos próximos tempos.
- Busca das datas previstas no Controle de Documentos corrigida e com diagnóstico no log.
- Extração do Aconex retoma de onde parou quando a conexão cai.
- Tela inicial (Home) com os módulos e as novidades.
- Histórico com datas de previsão e reprogramação na revisão 0A.
- Relatório de Fluxos de Trabalho: onde cada documento está e com quem.
