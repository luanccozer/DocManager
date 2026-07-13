"""Status Documentos — status real de uma lista de códigos (KB §18.1).

Para cada código: linha da verdade → roteia para o motor comum ou o de modelos
BIM (conforme Tipo do Documento) → status real. Reúne os pré-requisitos que já
existem no core; não duplica lógica.
"""
from __future__ import annotations

import pandas as pd

from ...core.consolidation import calcular_emitido_nao_emitido
from ...core.constants import COL_TIPO_DOC, COL_TITULO, NAO_EMITIDO
from ...core.identity import AconexIndex
from ...core.status_engine import calcular_status_real
from ...core.status_model_bim import calcular_status_real_modelo
from ...core.truth_line import resolver_linha_da_verdade


def _e_modelo(df_tracking: pd.DataFrame) -> bool:
    if COL_TIPO_DOC not in df_tracking.columns or df_tracking.empty:
        return False
    return "MODEL" in str(df_tracking[COL_TIPO_DOC].iloc[0]).upper()


def analisar_status_documentos(df_base: pd.DataFrame, codigos, *, tipo_codigo="itaipu") -> pd.DataFrame:
    """tipo_codigo: 'itaipu' ou 'cmi'. Retorna 1 linha por código de entrada."""
    idx = AconexIndex(df_base)
    linhas = []
    for cod in codigos:
        cod = str(cod).strip()
        if not cod:
            continue
        df_t = idx.localizar(cod, "") if tipo_codigo == "itaipu" else idx.localizar("", cod)
        if df_t.empty:
            linhas.append({"Código": cod, "Título": "", "Revisão": "", "Status Real": NAO_EMITIDO,
                           "Emitido": NAO_EMITIDO, "É Modelo": "NÃO"})
            continue
        tl = resolver_linha_da_verdade(df_t)
        eh_modelo = _e_modelo(df_t)
        if tl.nao_emitido:
            status_real, rev = NAO_EMITIDO, ""
        else:
            rev = tl.revisao_atual
            motor = calcular_status_real_modelo if eh_modelo else calcular_status_real
            status_real = motor(tl.df_para_calculo, rev)
            rev = str(tl.linha_dinamica.get("Revisão", "")).strip()
        titulo = str(df_t[COL_TITULO].iloc[0]) if COL_TITULO in df_t.columns else ""
        linhas.append({
            "Código": cod, "Título": titulo, "Revisão": rev, "Status Real": status_real,
            "Emitido": calcular_emitido_nao_emitido(status_real), "É Modelo": "SIM" if eh_modelo else "NÃO",
        })
    return pd.DataFrame(linhas)
