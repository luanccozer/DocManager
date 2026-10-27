"""Backend do Transpasse de Fase: lê as planilhas, monta o quadro e grava a
página HTML (a Planilha1 desenhada a partir das datas).

A planilha principal (acompanhamento do transpasse) é obrigatória; a
complementar (controle do início do comissionamento) é opcional: é dela que vem
o início do comissionamento (preto) e, com ele, a coluna Dias. As regras moram
em `core/transpasse.py`; ver também `docs/transpasse_de_fase.md`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .core.transpasse import montar_quadro
from .dashboard.transpasse_html import renderizar
from .services.transpasse_io import ler_planilha_complementar, ler_planilha_principal


@dataclass
class ResultadoTranspasse:
    ok: bool
    mensagem: str
    caminho: str = ""
    grupos: int = 0


def gerar_painel_transpasse(caminho_principal, caminho_saida, caminho_complementar=None, *,
                            hoje: date | None = None, log_cb=None) -> ResultadoTranspasse:
    log = log_cb or (lambda _msg: None)
    hoje = hoje or date.today()
    try:
        principal = ler_planilha_principal(caminho_principal)
        complementar = ler_planilha_complementar(caminho_complementar) if caminho_complementar else None
    except ValueError as e:   # planilha errada ou sem uma coluna: a mensagem já diz qual
        return ResultadoTranspasse(False, str(e))
    log(f"Planilha principal: {len(principal)} grupos.")
    if complementar is None:
        log("Sem a planilha complementar: o início do comissionamento (preto) e a coluna Dias ficam vazios.")
    else:
        log(f"Planilha complementar: {len(complementar)} grupos.")

    quadro = montar_quadro(principal, complementar, hoje)
    if com_aviso := sum(1 for g in quadro.grupos if g.avisos):
        log(f"{com_aviso} grupos têm datas a conferir: o card de cada um (passe o mouse no painel) diz o quê.")

    fontes = [Path(c).name for c in (caminho_principal, caminho_complementar) if c]
    html = renderizar(quadro, hoje=hoje, fontes=fontes, gerado_em=datetime.now())
    try:
        Path(caminho_saida).write_text(html, encoding="utf-8")
    except OSError as e:
        return ResultadoTranspasse(False, f"Não foi possível salvar o painel em {caminho_saida}: {e}")
    n = len(quadro.grupos)
    return ResultadoTranspasse(True, f"Painel gerado com {n} grupo{'' if n == 1 else 's'}: {caminho_saida}",
                               str(caminho_saida), n)
