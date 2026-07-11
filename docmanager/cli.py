"""CLI headless do DocManager — usada por testes, demonstração e regressão.

    python -m docmanager.cli historico --aconex base.xlsx [--controle ctrl.xlsx] --out hist.xlsx
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from .services.controle_docs import ler_controle
from .services.excel_io import exportar_historico
from .services.historico_consolidado import gerar_historico


def _cmd_historico(args) -> int:
    df_bruto = pd.read_excel(args.aconex, sheet_name=args.aba, dtype=str).fillna("")
    controle = ler_controle(args.controle, args.aba_controle, log_cb=print) if args.controle else None
    df_wide = gerar_historico(df_bruto, controle)
    ok, msg = exportar_historico(df_wide, args.out)
    print(msg)
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="docmanager.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("historico", help="Gera o Histórico Consolidado (Excel).")
    p.add_argument("--aconex", required=True, help="Base Aconex (.xlsx).")
    p.add_argument("--aba", default=0, help="Aba da base Aconex.")
    p.add_argument("--controle", help="Controle de Documentos (.xlsx), opcional.")
    p.add_argument("--aba-controle", default=0, dest="aba_controle")
    p.add_argument("--out", required=True, help="Excel de saída.")
    p.set_defaults(func=_cmd_historico)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
