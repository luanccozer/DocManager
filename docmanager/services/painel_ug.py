"""Gera o painel HTML da Unidade Geradora a partir do Doc List e da base do Aconex.

Orquestração: lê a planilha (as linhas na ordem física) e a extração do Aconex, monta
os dados (`core/painel_ug.py`), desenha a página (`dashboard/painel_ug_html.py`) e
grava o arquivo. Não escreve nada na planilha.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .. import __version__
from ..core.painel_ug import montar_dados_painel
from ..dashboard.painel_ug_html import renderizar
from .doclist_io import ler_linhas_doclist
from .excel_io import carregar_base_aconex


@dataclass
class ResultadoPainelUG:
    ok: bool
    mensagem: str
    caminho: str = ""
    documentos: int = 0


def gerar_painel_ug(path_aconex, path_doclist, caminho_saida, *, sheet_aconex=0, sheet_doclist=None,
                    hoje: date | None = None, log_cb=None, progress_cb=None) -> ResultadoPainelUG:
    log = log_cb or (lambda _msg: None)
    avancar = progress_cb or (lambda _f: None)
    hoje = hoje or date.today()

    log("Lendo o Doc List Mapping...")
    linhas = ler_linhas_doclist(path_doclist, sheet_doclist)
    if not any(not ln.e_grupo for ln in linhas):
        return ResultadoPainelUG(False, "Nenhum documento (nível 2) na aba escolhida do Doc List Mapping.")
    avancar(0.05)
    log("Lendo a base Aconex...")
    base = carregar_base_aconex(path_aconex, sheet_aconex)
    log(f"Base carregada: {len(base)} linhas. Montando o histórico de cada documento...")
    avancar(0.15)

    dados = montar_dados_painel(linhas, base, hoje=hoje, progresso=lambda f: avancar(0.15 + 0.8 * f))
    docs = dados["documentos"]
    fora = sum(1 for d in docs if not d["no_aconex"])
    log(f"{len(docs)} documentos ({len(dados['associacoes'])} linhas da planilha); "
        f"{fora} ainda não estão no Aconex.")

    aba = sheet_doclist if isinstance(sheet_doclist, str) and sheet_doclist else "ativa"
    html = renderizar(dados, base=Path(path_aconex).name, doc_list=Path(path_doclist).name, aba=aba,
                      gerado_em=f"{datetime.now():%d/%m/%Y %H:%M}", versao=__version__)
    try:
        Path(caminho_saida).write_text(html, encoding="utf-8")
    except OSError as e:
        return ResultadoPainelUG(False, f"Não foi possível salvar o painel em {caminho_saida}: {e}")
    avancar(1.0)
    n = len(docs)
    return ResultadoPainelUG(True, f"Painel gerado com {n} documento{'' if n == 1 else 's'}: {caminho_saida}",
                             str(caminho_saida), n)
