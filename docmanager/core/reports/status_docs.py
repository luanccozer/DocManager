"""Status Documentos — status real de uma lista de códigos (KB §18.1).

Para cada código: linha da verdade → roteia para o motor comum ou o de modelos
BIM (conforme Tipo do Documento) → status real. Reúne os pré-requisitos que já
existem no core; não duplica lógica.
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from ...core.consolidation import calcular_emitido_nao_emitido
from ...core.constants import (
    COL_DATA,
    COL_DOC_CMI,
    COL_DOC_ITAIPU,
    COL_STATUS,
    COL_TIPO_DOC,
    COL_TITULO,
    NAO_EMITIDO,
)
from ...core.identity import AconexIndex
from ...core.normalize import normalizar_codigo
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


def analisar_status_pares(df_base: pd.DataFrame, pares) -> tuple[list[dict], Counter, bool]:
    """Status real por par (código Itaipu, código CMI) — porta de
    StatusCheckView.iniciar_processo (aconex_reviewer L1474-1581).

    Alimenta o Excel legado (Código Itaipu/CMI, Título, Revisão, Data, Status
    Aconex, Status Real) + o gráfico de barras. Retorna (linhas, contador,
    tem_modelos). `pares`: iterável de (cod_itaipu, cod_cmi).

    Cada linha carrega ainda as flags internas `_itaipu_alterado`/`_cmi_alterado`
    (prefixo '_' → não viram coluna do Excel): True quando o código VIGENTE do
    documento (resolvido via Tracking ID) difere do que foi BUSCADO — ou seja, o
    código mudou no Aconex desde a lista de busca. O exportador pinta essas
    células de azul (pedido do usuário).
    """
    idx = AconexIndex(df_base)
    linhas: list[dict] = []
    contador: Counter = Counter()
    tem_modelos = False
    for cod_it, cod_cmi in pares:
        c_it = str(cod_it or "").strip()
        c_cmi = str(cod_cmi or "").strip()
        if not c_it and not c_cmi:
            continue
        dados = {"Código Itaipu": c_it, "Código CMI": c_cmi, "Título": "", "Revisão": "",
                 "Data": "", "Status Aconex": "", "Status Real": NAO_EMITIDO,
                 "_itaipu_alterado": False, "_cmi_alterado": False}
        df_t = idx.localizar(c_it, c_cmi)
        if not df_t.empty:
            tl = resolver_linha_da_verdade(df_t)
            eh_modelo = _e_modelo(df_t)
            tem_modelos = tem_modelos or eh_modelo
            linha = tl.linha_dinamica
            if linha is not None:
                cur_it = str(linha.get(COL_DOC_ITAIPU, "")).strip()
                cur_cmi = str(linha.get(COL_DOC_CMI, "")).strip()
                if cur_it:
                    dados["Código Itaipu"] = cur_it
                    # Só é "atualizado" se o usuário buscou por esse código e o
                    # vigente difere (comparação normalizada: caixa/'.0'/espaços).
                    if c_it and normalizar_codigo(c_it) != normalizar_codigo(cur_it):
                        dados["_itaipu_alterado"] = True
                if cur_cmi:
                    dados["Código CMI"] = cur_cmi
                    if c_cmi and normalizar_codigo(c_cmi) != normalizar_codigo(cur_cmi):
                        dados["_cmi_alterado"] = True
                dados["Título"] = str(linha.get(COL_TITULO, ""))
                dados["Revisão"] = str(linha.get("Revisão", ""))
                dados["Data"] = str(linha.get(COL_DATA, ""))
                dados["Status Aconex"] = str(linha.get(COL_STATUS, ""))
            else:
                dados["Título"] = str(df_t[COL_TITULO].iloc[0]) if COL_TITULO in df_t.columns else ""
            if tl.nao_emitido:
                dados["Status Real"] = NAO_EMITIDO
            else:
                motor = calcular_status_real_modelo if eh_modelo else calcular_status_real
                dados["Status Real"] = motor(tl.df_para_calculo, tl.revisao_atual)
        contador[dados["Status Real"]] += 1
        linhas.append(dados)
    return linhas, contador, tem_modelos
