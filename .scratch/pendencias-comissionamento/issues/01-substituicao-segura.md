# 01: Substituição segura da planilha (temporário, conferência, backup, troca atômica)

**What to build:** em `services/gravacao.py`, a lógica de gravar vira uma função genérica,
`substituir_com_seguranca(caminho, escrever, *, validar, assinatura, backup, retry_cb, log_cb,
tentativas, espera_s)`. O `salvar_planilha` passa a chamá-la com `wb.save`: Doc List e Mapa
ganham a mesma proteção sem função paralela.

Sequência: temporário `~$docmanager-*.xlsx` na mesma pasta → conferência (zip íntegro,
openpyxl abre, `validar`) → assinatura do arquivo inalterada → backup em
`pasta_dados()/backups` (20 por arquivo) → `os.replace` dentro do laço que já existe de
"tentar de novo / perguntar" → temporário sempre removido. Detalhes: spec, seção 9.

**Blocked by:** None (can start immediately)

**Status:** done

- [ ] Os testes atuais de `tests/test_gravacao.py` continuam passando sem mudar o que verificam
- [ ] Falha no meio da escrita: original byte a byte igual e nenhum `~$docmanager-*` sobrando
- [ ] Validador reprova: original intacto e motivo devolvido
- [ ] Arquivo mudou desde a leitura (assinatura): aborta sem trocar
- [ ] Backup criado antes da troca; só os 20 mais recentes por nome ficam
- [ ] Backup falhou: aborta sem trocar
- [ ] Recusa do Windows no `os.replace` (arquivo aberto): pergunta e, ao resolver, troca
- [ ] Testes do Doc List e do Mapa verdes
