# Documentos de domínio

Como as skills de engenharia leem a documentação de domínio deste repositório.

## Antes de explorar, ler

- **`GLOSSARY.md`** na raiz: o vocabulário do domínio.
- **`docs/adr/`**: as decisões que tocam a área em que se vai mexer.
- **`knowledge_base_docmanager.md`**: as regras de negócio, seção por seção (a KB é
  anterior ao glossário e continua sendo a referência detalhada).

Se algum não existir, seguir em frente sem avisar.

## Estrutura (um contexto só)

```
/
├── GLOSSARY.md
├── knowledge_base_docmanager.md
├── docs/adr/
└── docmanager/
```

## Usar o vocabulário do glossário

Ao nomear um conceito do domínio (título de tarefa, nome de teste, mensagem de log),
usar o termo do `GLOSSARY.md`, sem os sinônimos que ele manda evitar.

## Conflito com ADR

Se algo contradiz um ADR existente, dizer explicitamente em vez de passar por cima.
