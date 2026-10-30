"""Extração da base Aconex SEM janela, para outro programa disparar.

    DocManager.exe --extrair-aconex --saida <arquivo.xlsx> [--log <arquivo.txt>]
                   [--usuario <nome>] [--proxy <url>]

Pedido de 30/10/2026 (CMI Suite): a primeira máquina da equipe que liga no dia
extrai a base e a deixa numa pasta compartilhada, para ninguém mais precisar
baixar os ~30 min da extração completa. A CMI Suite não importa o DocManager
(cada app segue funcionando sozinho): ela roda o `.exe` com este argumento.

Faz o mesmo que o botão "Iniciar Extração" da aba Extração Completa:

- as credenciais são as do cofre DESTA máquina (`services/credenciais.py`),
  cadastradas na tela de Extração — nada de segredo na linha de comando;
  sem `--usuario`, vale o primeiro cadastrado (o mesmo que a tela seleciona);
- o checkpoint é o mesmo: uma extração interrompida (pela tela ou por aqui)
  continua da página seguinte na próxima vez;
- o `.xlsx` é gravado ao lado com outro nome e só então renomeado para
  `--saida`: quem estiver de olho na pasta nunca lê meia planilha.

O `.exe` não tem console: tudo vai para `--log` (sem ele, não há saída).

Códigos de saída (o chamador decide por eles, sem ler o log):
    0  base completa gravada em --saida
    1  falhou (rede, Aconex, disco) — nada gravado
    2  incompleta — nada gravado; o checkpoint guarda o progresso
    3  sem credencial cadastrada nesta máquina
"""
from __future__ import annotations

import argparse
import os
import traceback
from datetime import datetime
from pathlib import Path

OK, FALHOU, INCOMPLETA, SEM_CREDENCIAL = 0, 1, 2, 3


def _registrador(caminho: str | None):
    arquivo = open(caminho, "a", encoding="utf-8", buffering=1) if caminho else None  # noqa: SIM115

    def log(msg: str) -> None:
        if arquivo is not None:
            arquivo.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")

    return log, arquivo


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="DocManager.exe --extrair-aconex")
    parser.add_argument("--saida", required=True, help="Onde gravar a base (.xlsx).")
    parser.add_argument("--log", help="Arquivo de log (acrescenta).")
    parser.add_argument("--usuario", help="Usuário do cofre (padrão: o primeiro cadastrado).")
    parser.add_argument("--proxy", help="Proxy http(s); vazio força conexão direta.")
    args = parser.parse_args(argv)

    log, arquivo = _registrador(args.log)
    try:
        return _extrair(args, log)
    except Exception:  # noqa: BLE001 - o chamador só vê o código; o detalhe vai para o log
        log("ERRO inesperado:\n" + traceback.format_exc())
        return FALHOU
    finally:
        if arquivo is not None:
            arquivo.close()


def _extrair(args, log) -> int:
    from . import aconex_backend as ab

    ab.migrar_env_para_cofre(log_cb=log)
    disponiveis = ab.usuarios_disponiveis()
    usuario = args.usuario or (disponiveis[0] if disponiveis else "")
    if not usuario:
        log("Nenhum usuário do Aconex cadastrado nesta máquina (DocManager → Extração → Cadastrar usuário).")
        return SEM_CREDENCIAL
    try:
        config = ab.AconexConfig.para_usuario(usuario, proxy=args.proxy)
    except (KeyError, ValueError) as e:
        log(f"Credencial inutilizável: {e}")
        return SEM_CREDENCIAL

    log(f"Extração da base Aconex (sem janela) como {usuario}.")
    resultado = ab.extrair_base(config, log_cb=log)
    if not resultado.completa:
        log(f"Extração INCOMPLETA ({resultado.motivo}); nada gravado. O checkpoint guarda "
            f"{resultado.registros} registros para a próxima tentativa.")
        return INCOMPLETA
    if resultado.df.empty:
        log("Nenhum dado extraído.")
        return FALHOU

    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.stem + ".parcial.xlsx")
    ab.salvar_excel(resultado.df, temporario)
    os.replace(temporario, destino)
    ab.limpar_checkpoint(config)
    log(f"Base salva em {destino} ({len(resultado.df)} linhas).")
    return OK
