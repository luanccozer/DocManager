---
status: accepted
---

# A data prevista é a baseline e uma data preenchida só é trocada com aceite

Em 2026-10-29, a pedido da gestão (indicadores Baseline OTD e Say-do), a DATA PREVISTA
do Doc List e da etapa 1 do Mapa dos Planos passou a ser a baseline. O DocManager não
troca mais nenhuma data já preenchida (prevista ou reprogramada, inclusive texto e
fórmula) pela do Controle de Documentos sem que quem roda a atualização aceite, numa
tela com três saídas: aceitar todas, não sobrescrever, ou escolher caso a caso. Célula
vazia continua sendo preenchida. A recusa fica anotada na aba "Sobrescrições
recusadas" da própria planilha e não é perguntada de novo enquanto o Controle mantiver
a mesma data.

## Considered Options

- **A mais recente vence** (a regra de 2026-07-28, KB §24.13): mantinha a planilha em
  dia com o Controle, mas cada replanejamento apagava a data original. Sem data
  original não existe Baseline OTD, e o atraso some do painel.
- **Coluna nova de baseline**, deixando a DATA PREVISTA acompanhar o Controle: rejeitada
  pelo usuário ("não precisamos de outra coluna"); o painel já conhece a DATA PREVISTA.
- **Nunca trocar, sem perguntar**: perderia replanejamentos legítimos do Controle. A
  tela deixa a decisão com a pessoa.

## Consequences

- A planilha deixa de acompanhar o Controle sozinha: quem não rodar pela tela (linha de
  comando do Mapa) vê as diferenças só no log.
- Aceitar a troca da DATA PREVISTA é rebaselinar: o Baseline OTD passa a medir contra a
  data nova. A tela avisa.
- O app não sabe quem escreveu uma data (pessoa ou rodada anterior); por isso a regra
  vale para toda célula preenchida.
- A segunda reprogramação do Controle também passa pela tela; por padrão fica a
  primeira, que é o compromisso que o Say-do mede.
