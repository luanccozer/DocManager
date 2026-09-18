"""Exceções pontuais POR DOCUMENTO - dívida conhecida, não regra de domínio.

⚠️ **PENDÊNCIA ABERTA.** Cada entrada aqui é um documento cujo dado de origem
está provavelmente ERRADO no Aconex e que, até alguém corrigir na fonte, precisa
de um desvio no motor. Isto não é extensão do domínio: é remendo nomeado, com
data e motivo, para não virar regra silenciosa.

Antes de acrescentar uma entrada, confirme que o caso é MESMO isolado - se
aparecer um segundo documento com o mesmo sintoma, a regra do motor é que está
errada, e o certo é discutir a regra, não crescer esta lista.

Ao remover um documento daqui (porque a origem foi corrigida), rode a suíte: há
teste travando cada exceção.
"""
from __future__ import annotations

import re

from .constants import COL_DOC_CMI, COL_DOC_ITAIPU

_RE_SUJEIRA = re.compile(r"[\s\xa0​‎‏﻿]")


def _chave(cod) -> str:
    """Código comparável: MAIÚSCULAS, sem espaço nem invisível (sujeira de Excel)."""
    if cod is None:
        return ""
    return _RE_SUJEIRA.sub("", str(cod).strip().upper())


# ---------------------------------------------------------------------------
# Reprovação em revisão NUMÉRICA que deve valer (KB §21.9)
# ---------------------------------------------------------------------------
# Regra normal (§8.4/§8.7): revisão numérica seca ('0', '1', '2') é o marco
# DEFINITIVO da família - um "Não Aprovado" nela é contraditório e o motor o
# trata como ruído. Isso vale para 99,9% dos documentos.
#
# Os documentos abaixo são a exceção: foram emitidos DIRETO numa revisão
# numérica (sem passar pelas revisões-letra) e voltaram reprovados. O mais
# provável é erro de quem publicou - deveria ter sido '0A', não '0'. Sem o
# desvio, o motor conclui NÃO EMITIDO e o documento some das análises.
#
# PENDENTE (2026-07-28): confirmar com a Itaipu/CMI se a revisão do documento
# pode ser corrigida na origem. Corrigida lá, apague a entrada daqui.
DOCS_REPROVACAO_EM_REVISAO_NUMERICA: frozenset[str] = frozenset({
    _chave("#ITA0=C01CCA10&EDE020"),
})


def _codigos_do_documento(df_tracking) -> set[str]:
    """Todos os códigos (Itaipu e CMI) que o documento já teve, normalizados."""
    codigos: set[str] = set()
    for col in (COL_DOC_ITAIPU, COL_DOC_CMI):
        if col in df_tracking.columns:
            codigos.update(_chave(v) for v in df_tracking[col].dropna().unique())
    codigos.discard("")
    return codigos


def reprovacao_numerica_vale(df_tracking) -> bool:
    """True se ESTE documento está na lista de exceção acima.

    Casa por qualquer código histórico (Itaipu ou CMI) - o código do documento
    muda ao longo da vida, e a identidade real é o Tracking ID (§6).
    """
    if df_tracking is None or df_tracking.empty or not DOCS_REPROVACAO_EM_REVISAO_NUMERICA:
        return False
    return bool(_codigos_do_documento(df_tracking) & DOCS_REPROVACAO_EM_REVISAO_NUMERICA)
