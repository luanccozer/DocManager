# Onde ficam specs e tarefas: arquivos no repositório

Specs e tarefas deste repositório são arquivos markdown em `.scratch/`.

## Convenções

- Uma pasta por funcionalidade: `.scratch/<funcionalidade>/`
- A spec é `.scratch/<funcionalidade>/spec.md`
- Uma tarefa por arquivo em `.scratch/<funcionalidade>/issues/<NN>-<slug>.md`,
  numerada a partir de `01`, nunca um arquivo único com todas
- O estado fica numa linha `Status:` no topo de cada arquivo (`ready-for-agent`,
  `needs-info`, `done`)
- Comentários e histórico vão no fim do arquivo, sob `## Comments`

## Quando uma skill disser "publicar no issue tracker"

Criar o arquivo em `.scratch/<funcionalidade>/` (criando a pasta se precisar).

## Quando uma skill disser "buscar a tarefa"

Ler o arquivo indicado. Normalmente o caminho ou o número vem junto.
