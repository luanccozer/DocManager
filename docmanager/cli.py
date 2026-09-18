"""CLI headless do DocManager - usada por testes, demonstração e regressão.

    python -m docmanager.cli historico --aconex base.xlsx [--controle ctrl.xlsx] --out hist.xlsx
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from .aconex_backend import (
    AconexConfig,
    extrair_base,
    limpar_checkpoint,
    nome_arquivo_padrao,
    salvar_excel,
)
from .services.controle_docs import ler_controle
from .services.excel_io import exportar_historico
from .services.historico_consolidado import gerar_historico
from .services.mapping_update import atualizar_mapeamento
from .workflows_backend import (
    extrair_workflows,
    limpar_checkpoint_wf,
    nome_arquivo_padrao_wf,
    salvar_excel_workflows,
)


def _cmd_mapa(args) -> int:
    controle = ler_controle(args.controle, log_cb=print) if args.controle else None
    r = atualizar_mapeamento(args.aconex, args.mapa, controle=controle,
                             regra_estrita_vip=args.vip, log_cb=print)
    print(r.mensagem)
    return 0 if r.ok else 1


def _cmd_extrair(args) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    config = AconexConfig.para_usuario(args.usuario, secret=args.secret, proxy=args.proxy)
    r = extrair_base(config, log_cb=print, usar_checkpoint=not args.sem_retomada)
    if r.df.empty:
        print("Nenhum dado extraído.")
        return 1
    out = args.out or nome_arquivo_padrao()
    salvar_excel(r.df, out)
    print(f"Base salva em: {out}  ({len(r.df)} linhas)")
    if not r.completa:
        # Sai com erro: uma base parcial não pode passar por completa num script.
        print(f"ATENÇÃO: extração INCOMPLETA ({r.motivo}). Rode de novo para "
              f"continuar da página {r.paginas + 1}.")
        return 2
    limpar_checkpoint(config)
    return 0


def _cmd_extrair_fluxos(args) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    updated_after = ""
    if args.dias:
        from datetime import datetime, timedelta, timezone
        updated_after = (datetime.now(timezone.utc) - timedelta(days=args.dias)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    config = AconexConfig.para_usuario(args.usuario, secret=args.secret, proxy=args.proxy)
    r = extrair_workflows(config, log_cb=print, rota=args.rota, updated_after=updated_after,
                          usar_checkpoint=not args.sem_retomada)
    if r.df.empty:
        print("Nenhum fluxo extraído.")
        return 1
    out = args.out or nome_arquivo_padrao_wf()
    salvar_excel_workflows(r.df, out)
    print(f"Fluxos salvos em: {out}  ({len(r.df)} linhas)")
    if not r.completa:
        print(f"ATENÇÃO: extração INCOMPLETA ({r.motivo}). Rode de novo para "
              f"continuar da página {r.paginas + 1}.")
        return 2
    limpar_checkpoint_wf(config, rota=args.rota, updated_after=updated_after)
    return 0


def _cmd_fluxos(args) -> int:
    from .core.reports.fluxos import analisar_fluxos_em_andamento, resumir_por_responsavel
    from .services.excel_io import exportar_fluxos_andamento
    df = pd.read_excel(args.fluxos, sheet_name=args.aba, dtype=str).fillna("")
    detalhe = analisar_fluxos_em_andamento(df)
    if detalhe.empty:
        print("Nenhum fluxo em andamento com etapa aberta.")
        return 1
    ok, msg = exportar_fluxos_andamento(detalhe,
                                        resumir_por_responsavel(detalhe, por="pessoa"),
                                        resumir_por_responsavel(detalhe, por="organizacao"),
                                        args.out)
    print(msg)
    return 0 if ok else 1


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

    e = sub.add_parser("extrair", help="Extrai a base Aconex via API (OAuth + paginação).")
    e.add_argument("--usuario", default="Luan Cozer", help="Usuário conhecido (secret via .env).")
    e.add_argument("--secret", help="Client Secret (senão usa SECRET_<NOME> do .env).")
    e.add_argument("--proxy", help="Proxy http(s). Vazio ('') força conexão direta.")
    e.add_argument("--out", help="Excel de saída (padrão: Aconex_Historico_<timestamp>.xlsx).")
    e.add_argument("--sem-retomada", action="store_true", dest="sem_retomada",
                   help="Não usa checkpoint: sempre começa da página 1.")
    e.set_defaults(func=_cmd_extrair)

    ef = sub.add_parser("extrair-fluxos", help="Extrai os Fluxos de Trabalho (Workflows API).")
    ef.add_argument("--usuario", default="Luan Cozer", help="Usuário conhecido (secret via .env).")
    ef.add_argument("--secret", help="Client Secret (senão usa SECRET_<NOME> do .env).")
    ef.add_argument("--proxy", help="Proxy http(s). Vazio ('') força conexão direta.")
    ef.add_argument("--out", help="Excel de saída (padrão: Aconex_Workflows_<timestamp>.xlsx).")
    ef.add_argument("--rota", default="todos", help="todos | iniciados_por_nos | atribuidos_a_nos | ...")
    ef.add_argument("--dias", type=int, help="Só o que mudou nos últimos N dias (incremental).")
    ef.add_argument("--sem-retomada", action="store_true", dest="sem_retomada")
    ef.set_defaults(func=_cmd_extrair_fluxos)

    f = sub.add_parser("fluxos", help="Relatório 'Fluxos em Andamento' (onde está e com quem).")
    f.add_argument("--fluxos", required=True, help="Base de Fluxos (.xlsx da extração).")
    f.add_argument("--aba", default="Fluxos", help="Aba da base de fluxos.")
    f.add_argument("--out", required=True, help="Excel de saída.")
    f.set_defaults(func=_cmd_fluxos)

    m = sub.add_parser("mapa", help="Atualiza a planilha de Mapeamento de Planos.")
    m.add_argument("--aconex", required=True, help="Base Aconex (.xlsx).")
    m.add_argument("--mapa", required=True, help="Planilha de mapeamento (.xlsx, será sobrescrita).")
    m.add_argument("--controle", help="Controle de Documentos (.xlsx), opcional.")
    m.add_argument("--vip", action="store_true", help="Liga a regra estrita das planilhas VIP.")
    m.set_defaults(func=_cmd_mapa)

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
