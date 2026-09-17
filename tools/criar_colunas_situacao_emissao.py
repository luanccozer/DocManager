"""Cria na planilha do Doc List Mapping as colunas de Situação de Emissão (§27.5).

    python tools/criar_colunas_situacao_emissao.py "Doc List Mapping.xlsx" [--aba "Unidade Geradora"]

As três colunas (`DATA 1ª EMISSÃO`, `SITUAÇÃO EMISSÃO`, `DIAS DESVIO EMISSÃO`)
são **calculadas pelo app**: este script só as cria vazias, já com a cara das
outras colunas da planilha. Quem as preenche é a atualização normal do módulo.

Decisões de projeto, para quem for mexer depois:

- **Anexa no fim, nunca insere no meio.** `ws.insert_cols()` do openpyxl move os
  valores mas NÃO move larguras de coluna, ranges de formatação condicional nem
  o autofiltro — numa planilha real isso aparece como dano visível. Como o app
  localiza coluna pelo TEXTO do cabeçalho (`DocListSheet`), a posição é
  irrelevante para o código: arraste as colunas para onde quiser depois.
- **Idempotente**: coluna que já existe é deixada em paz (comparação sem acento,
  maiúsculas e espaços colapsados, igual à do app).
- **Faz backup** antes de gravar.

⚠️ Renomear o cabeçalho quebra o vínculo com o código — mover, agrupar, ocultar
ou reordenar, não.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from copy import copy
from datetime import datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from docmanager.core.doclist import COLUNAS_DOCLIST  # noqa: E402
from docmanager.services.doclist_io import DocListSheet, _norm_cabecalho  # noqa: E402

# chave lógica → (coluna-modelo para copiar o estilo, formato numérico, largura)
# A modelo é a coluna vizinha que já tem a formatação certa naquela linha, o que
# preserva de graça qualquer faixa zebrada/borda que a planilha use.
NOVAS = {
    "data_primeira_emissao": ("DATA ÚLTIMA EMISSÃO", "DD/MM/YYYY", 13.0),
    "situacao_emissao": ("STATUS REAL", "General", 20.0),
    "dias_desvio_emissao": ("ÚLTIMA REV. EMITIDA", "0", 11.0),
}


def _col_por_titulo(ws, row_header: int) -> dict[str, int]:
    return {_norm_cabecalho(c.value): c.column for c in ws[row_header] if c.value is not None}


def criar_colunas(caminho: Path, aba: str | None = None, *, log=print) -> int:
    """Cria as colunas que faltam. Devolve quantas criou."""
    wb = openpyxl.load_workbook(caminho)
    ws = wb[aba] if aba else wb.active
    log(f"Aba: {ws.title}")

    ds = DocListSheet(ws)          # valida a âncora e localiza o cabeçalho
    row_header = ds.row_header
    existentes = _col_por_titulo(ws, row_header)
    log(f"Cabeçalho na linha {row_header}; {len(existentes)} colunas encontradas.")

    faltando = [(chave, COLUNAS_DOCLIST[chave]) for chave in NOVAS
                if _norm_cabecalho(COLUNAS_DOCLIST[chave]) not in existentes]
    if not faltando:
        log("Nada a fazer: as três colunas já existem.")
        return 0

    backup = caminho.with_name(
        f"{caminho.stem}.backup-{datetime.now():%Y%m%d-%H%M%S}{caminho.suffix}")
    shutil.copy2(caminho, backup)
    log(f"Backup: {backup.name}")

    destino = ws.max_column + 1
    ultima_linha = ws.max_row
    for chave, titulo in faltando:
        titulo_modelo, numfmt, largura = NOVAS[chave]
        col_modelo = existentes.get(_norm_cabecalho(titulo_modelo))
        if col_modelo is None:
            raise SystemExit(f"Coluna-modelo '{titulo_modelo}' não existe na aba — abortado.")

        # Cabeçalho: mesma cara do cabeçalho vizinho.
        origem = ws.cell(row_header, col_modelo)
        alvo = ws.cell(row_header, destino)
        alvo.value = titulo
        alvo._style = copy(origem._style)
        alvo.number_format = "General"

        # Corpo: copia o estilo da MESMA linha da coluna-modelo (preserva zebra).
        for r in range(row_header + 1, ultima_linha + 1):
            celula = ws.cell(r, destino)
            celula._style = copy(ws.cell(r, col_modelo)._style)
            celula.number_format = numfmt

        ws.column_dimensions[alvo.column_letter].width = largura
        log(f"  + {titulo} -> coluna {alvo.column_letter}")
        destino += 1

    # Autofiltro: estende até a última coluna, senão as novas ficam de fora dos
    # dropdowns (e filtrar por SITUAÇÃO EMISSÃO é o uso principal delas).
    if ws.auto_filter.ref:
        from openpyxl.utils import get_column_letter, range_boundaries
        min_c, min_r, _max_c, max_r = range_boundaries(ws.auto_filter.ref)
        novo = (f"{get_column_letter(min_c)}{min_r}:"
                f"{get_column_letter(ws.max_column)}{max_r}")
        log(f"Autofiltro: {ws.auto_filter.ref} -> {novo}")
        ws.auto_filter.ref = novo

    try:
        wb.save(caminho)
    except PermissionError:
        raise SystemExit(f"'{caminho.name}' está aberto no Excel. Feche e rode de novo.") from None
    log(f"Salvo. {len(faltando)} coluna(s) criada(s).")
    return len(faltando)


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
