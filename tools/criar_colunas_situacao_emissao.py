"""Cria na planilha do Doc List Mapping as colunas de aderência (§27.5, §27.7).

    python tools/criar_colunas_situacao_emissao.py "Doc List Mapping.xlsx" [--aba "Unidade Geradora"]

As colunas (`DATA 1ª EMISSÃO`, `SITUAÇÃO EMISSÃO`, `DIAS DESVIO EMISSÃO`,
`SITUAÇÃO OTD`, `SITUAÇÃO SAY-DO`) são **calculadas pelo app**: este script só as
cria vazias, já com a cara das outras colunas da planilha. Quem as preenche é a
atualização normal do módulo (que, desde a v3.6.1, já cria sozinha as duas últimas).

Decisões de projeto, para quem for mexer depois:

- **Anexa no fim, nunca insere no meio.** `ws.insert_cols()` do openpyxl move os
  valores mas NÃO move larguras de coluna, ranges de formatação condicional nem
  o autofiltro - numa planilha real isso aparece como dano visível. Como o app
  localiza coluna pelo TEXTO do cabeçalho (`DocListSheet`), a posição é
  irrelevante para o código: arraste as colunas para onde quiser depois.
- **Idempotente**: coluna que já existe é deixada em paz (comparação sem acento,
  maiúsculas e espaços colapsados, igual à do app).
- **Faz backup** antes de gravar.

⚠️ Renomear o cabeçalho quebra o vínculo com o código - mover, agrupar, ocultar
ou reordenar, não.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docmanager.services.doclist_io import COLUNAS_CRIADAS_PELO_APP, DocListSheet  # noqa: E402

# chave lógica → (colunas-modelo para copiar o estilo, formato numérico, largura).
# A modelo é a coluna vizinha que já tem a formatação certa naquela linha, o que
# preserva de graça qualquer faixa zebrada/borda que a planilha use. As colunas
# de Baseline OTD e Say-do (SITUAÇÃO OTD, SITUAÇÃO SAY-DO) o próprio app cria na
# atualização; entram aqui para o script deixar a planilha completa de uma vez.
NOVAS = {
    "data_primeira_emissao": (("DATA ÚLTIMA EMISSÃO",), "DD/MM/YYYY", 13.0),
    "situacao_emissao": (("STATUS REAL",), "General", 20.0),
    "dias_desvio_emissao": (("ÚLTIMA REV. EMITIDA",), "0", 11.0),
    **COLUNAS_CRIADAS_PELO_APP,
}


def criar_colunas(caminho: Path, aba: str | None = None, *, log=print) -> int:
    """Cria as colunas que faltam. Devolve quantas criou."""
    wb = openpyxl.load_workbook(caminho)
    ws = wb[aba] if aba else wb.active
    log(f"Aba: {ws.title}")

    ds = DocListSheet(ws)          # valida a âncora e localiza o cabeçalho
    log(f"Cabeçalho na linha {ds.row_header}.")
    faltando = [chave for chave in NOVAS if chave not in ds._col_por_chave]
    if not faltando:
        log("Nada a fazer: as colunas já existem.")
        return 0

    backup = caminho.with_name(
        f"{caminho.stem}.backup-{datetime.now():%Y%m%d-%H%M%S}{caminho.suffix}")
    shutil.copy2(caminho, backup)
    log(f"Backup: {backup.name}")

    filtro_antes = ws.auto_filter.ref
    criadas = ds.criar_colunas({chave: NOVAS[chave] for chave in faltando})
    for titulo, letra in criadas:
        log(f"  + {titulo} -> coluna {letra}")
    if filtro_antes:
        log(f"Autofiltro: {filtro_antes} -> {ws.auto_filter.ref}")

    try:
        wb.save(caminho)
    except PermissionError:
        raise SystemExit(f"'{caminho.name}' está aberto no Excel. Feche e rode de novo.") from None
    log(f"Salvo. {len(criadas)} coluna(s) criada(s).")
    return len(criadas)


def main() -> None:
    # Console do Windows costuma ser cp1252 e engasga com acento no log.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("planilha", type=Path)
    p.add_argument("--aba", default=None, help="nome da aba (padrão: a ativa)")
    args = p.parse_args()
    criar_colunas(args.planilha, args.aba)


if __name__ == "__main__":
    main()
