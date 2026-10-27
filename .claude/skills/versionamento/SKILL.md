---
name: versionamento
description: Decide o número certo da próxima versão do DocManager (MAJOR.MINOR.PATCH) e confere tag e CHANGELOG antes de publicar. Use SEMPRE que for preparar, numerar, taguear ou publicar uma versão/release do DocManager, escrever o bloco de versão no CHANGELOG.md, criar uma tag vX.Y.Z ou rc, ou quando alguém perguntar "que versão é essa?", "isso é 3.6.1 ou 3.7.0?", "lança uma versão", "faz o release".
---

# Versionamento do DocManager

A versão é `MAJOR.MINOR.PATCH` (ex.: `3.6.1`). A **tag manda**: `v3.6.1` faz o
executável se identificar como `3.6.1` (ver `BUILD.md`). Por isso o número tem
que ser decidido **antes** de escrever o CHANGELOG e criar a tag, e por uma
regra só.

## A regra

Compare o que vai sair com a **última versão normal publicada** (sem `-rc`) e
classifique pelo item **mais pesado** do pacote:

| Nível | Quando | Exemplo de passo |
|---|---|---|
| **PATCH** (terceiro número) | Pequenas alterações | `3.6.0 → 3.6.1` |
| **MINOR** (segundo número) | Alterações massivas: módulo novo, ferramenta nova de grande impacto | `3.6.4 → 3.7.0` |
| **MAJOR** (primeiro número) | Mudança sistêmica, de algo que o app inteiro usa | `3.7.2 → 4.0.0` |

Ao subir um nível, **os números à direita zeram**: `3.6.4 → 3.7.0`, nunca
`3.7.4`; `3.7.2 → 4.0.0`, nunca `4.7.2`.

### PATCH — pequenas alterações

Tudo que **ajusta** o que já existe, sem criar tela, módulo ou ferramenta:

- correção de bug (data trocando dia e mês, instalador abortando, cálculo errado);
- status novo reconhecido do Aconex/comissionamento, rótulo, texto, cor, coluna;
- opção nova pequena numa tela que já existe;
- ajuste no instalador, no build, no CI, na atualização automática;
- versão só para testar a atualização (como foi a 3.5.1).

Várias pequenas juntas continuam sendo **um** PATCH.

### MINOR — alterações massivas

Algo **novo** que o usuário enxerga como função própria:

- módulo novo na barra lateral (ex.: Transpasse de Fase, na 3.5.0);
- ferramenta nova de grande impacto dentro de um módulo (ex.: Consulta Rápida
  na Extração Aconex);
- mecanismo novo que muda como o usuário trabalha (ex.: a atualização pequena
  da 3.4.0).

### MAJOR — mudança sistêmica

Muda a **base** em que tudo roda, e não uma função:

- troca da tecnologia da interface inteira (a passagem para Qt, que saiu como
  3.3.0, pelo critério de hoje seria 4.0.0);
- formato de configuração, cofre de credenciais ou planilhas de saída que deixa
  de ser compatível com o anterior;
- reestruturação geral de navegação/arquitetura, troca do método de instalação
  ou atualização que exige ação de todo mundo;
- versão que não atualiza sozinha a partir da anterior.

### Em dúvida

- Entre PATCH e MINOR: pergunte "o usuário vai ver **algo novo** no menu/tela,
  ou a mesma coisa funcionando melhor?". Mesma coisa melhor → PATCH.
- Entre MINOR e MAJOR, ou se continuar em dúvida: **pergunte ao usuário** antes
  de criar a tag, mostrando as duas opções e o porquê. Não decida sozinho.

## Proibido (é o que deixou a numeração uma zorra)

- **Pular número**: de `3.5.1` não se vai para `3.5.3` nem para `3.7.0`.
- **Reaproveitar** um número que já tem tag, mesmo que o Release tenha sido
  apagado. Saiu errado? Publique o próximo PATCH.
- **Voltar** número ou renumerar versões já publicadas.
- **Subir nível para "marcar"** uma entrega: o nível vem do conteúdo, não da
  vontade de destacar.
- **Mudar o número no meio do ensaio**: a rc é do número que vai sair. Se a
  `3.6.1-rc.1` está em teste, a versão final é `3.6.1`. Só troque de número
  (e recomece em `-rc.1` do novo) se entrou no pacote algo que muda o nível.
- **Calcular a partir de rc**: a base é sempre a última versão **normal**.

## Procedimento

1. **Ver onde estamos** (lê as tags do `origin`):

   ```bash
   python .claude/skills/versionamento/proxima_versao.py
   ```

   Mostra a última versão publicada, rc em andamento e as três opções.

2. **Classificar** o que vai sair desde a última tag normal:

   ```bash
   git log --oneline v<ultima>..HEAD
   ```

   Aplique a regra acima pelo item mais pesado. Diga ao usuário o nível
   escolhido e o motivo em uma linha.

3. **Escrever o bloco no topo do `CHANGELOG.md`**, com a data de hoje:

   ```markdown
   ## 3.6.1 - 2026-10-28

   - O que mudou, em uma frase que o usuário entenda.
   ```

   Ensaios (`-rc.N`) não ganham bloco próprio: o bloco já é o da versão final.

4. **Conferir antes da tag** (número é o próximo passo válido, tag livre,
   CHANGELOG batendo):

   ```bash
   python .claude/skills/versionamento/proxima_versao.py --checar 3.6.1
   ```

   Só siga com `OK`.

5. **Publicar** como manda o `BUILD.md` (`git tag v3.6.1 && git push origin
   v3.6.1`, ou Actions → Release). Para ensaio, `--checar 3.6.1-rc.1` e a tag
   `v3.6.1-rc.1` como pré-lançamento. Criar ou empurrar tag é publicar para
   todos os usuários: confirme com o usuário antes.
