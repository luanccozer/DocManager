"""Análise Delta — a "Máquina do Tempo" (KB §17).

Porta de `DataManager.obter_snapshot_status` (L576) e `calcular_mudancas_periodo`
(L620). Compara o estado de cada documento do mapeamento entre duas datas.

- A limpeza de Terminated no recorte usa o limiar de versão único (§21.8), que
  reconhece renascimento dentro do período (o legado excluía a revisão inteira).
- O rebaixamento estrito (docs_restritos) é condicionado ao toggle: `estrito=False`
  ⇒ nenhum documento é restrito (fluxo normal).
"""
from __future__ import annotations

import pandas as pd

from .constants import (
    COL_DATA,
    COL_DOC_ITAIPU,
    COL_REVISAO,
    COL_STATUS,
    COL_TRACKING,
    NAO_EMITIDO,
)
from .consolidation import calcula_status_consolidado_estrito
from .status_engine import calcular_status_real
from .truth_line import limpar_terminated_por_limiar


def obter_snapshot_status(df_historico_doc: pd.DataFrame, data_corte):
    """(status_bruto, status_real, revisão, data) do documento no instante `data_corte`.

    Requer a coluna `Data_Obj` (datetime) já no DataFrame.
    """
    df_cut = df_historico_doc[df_historico_doc["Data_Obj"] <= data_corte].copy()
    if df_cut.empty:
        return "N/A", NAO_EMITIDO, "-", pd.NaT
    df_cut = limpar_terminated_por_limiar(df_cut)  # + Versão_Int; respeita renascimento
    if df_cut.empty:
        return "N/A", NAO_EMITIDO, "-", pd.NaT
    linha = df_cut.sort_values(by=["Versão_Int", "Data_Obj"], ascending=[False, False]).iloc[0]
    status_raw = str(linha.get(COL_STATUS, ""))
    revisao_final = str(linha.get(COL_REVISAO, "")).strip()
    data_final = linha.get("Data_Obj", pd.NaT)
    status_real = calcular_status_real(df_cut, revisao_final)
    return status_raw, status_real, revisao_final, data_final


def calcular_mudancas_periodo(path_mapping, sheet_map, path_aconex, sheet_aconex,
                              data_ini_str, data_fim_str, cols_config, *,
                              agrupador_escolhido="Grupo", tipo_visao="Efetiva",
                              estrito=False):
    """Árvore de mudanças entre duas datas. Retorna (ok, arvore|msg, total)."""
    try:
        dt_ini = pd.to_datetime(data_ini_str, dayfirst=True)
        dt_fim = pd.to_datetime(data_fim_str, dayfirst=True).replace(hour=23, minute=59, second=59)
        dt_corte_antes = dt_ini - pd.Timedelta(seconds=1)
    except Exception:
        return False, "Erro na data", 0

    header_idx = cols_config.get("header_row", 0)
    if header_idx > 0:
        header_idx -= 1
    df_map = pd.read_excel(path_mapping, sheet_name=sheet_map, header=header_idx, dtype=str).fillna("")

    df_hist = pd.read_excel(path_aconex, sheet_name=sheet_aconex, dtype=str)
    df_hist["Data_Obj"] = pd.to_datetime(df_hist[COL_DATA], dayfirst=True, errors="coerce")
    df_hist = df_hist.dropna(subset=["Data_Obj"])
    tem_tracking = COL_TRACKING in df_hist.columns
    if tem_tracking:
        df_hist[COL_TRACKING] = df_hist[COL_TRACKING].astype(str).str.strip().str.upper()
    df_hist[COL_DOC_ITAIPU] = df_hist[COL_DOC_ITAIPU].astype(str).str.strip().str.upper()

    hist_by_tracking, map_doc_to_tracking = {}, {}
    chave_grupo = COL_TRACKING if tem_tracking else COL_DOC_ITAIPU
    for chave, grupo in df_hist.groupby(chave_grupo):
        hist_by_tracking[chave] = grupo
        for nome in grupo[COL_DOC_ITAIPU].unique():
            map_doc_to_tracking[nome] = chave

    col_doc = cols_config.get("doc", "N° ITAIPU")
    col_agrupador = cols_config.get("sistema", "SISTEMA") if agrupador_escolhido == "Sistema" else cols_config.get("grupo", "GRUPO")
    col_nivel = cols_config.get("nivel", "NÍVEL")
    col_titulo = cols_config.get("titulo", "DESCRIÇÃO DO DOCUMENTO")
    col_pred = cols_config.get("predecessor", "PREDECESSOR")
    if col_doc not in df_map.columns:
        return False, f"Coluna '{col_doc}' não encontrada.", 0

    # Pente-fino no Delta: só quando o toggle está ligado.
    docs_restritos = set()
    if estrito:
        planilhas_vip = set()
        for _, row in df_map.iterrows():
            if str(row.get(col_nivel, "")).strip() == "3" and "PLANILHA" in str(row.get(col_titulo, "")).upper():
                cod = str(row.get(col_doc, "")).strip().upper()
                if cod:
                    planilhas_vip.add(cod)
        if planilhas_vip:
            for _, row in df_map.iterrows():
                if str(row.get(col_nivel, "")).strip() == "4":
                    pred = str(row.get(col_pred, "")).strip().upper()
                    if pred in planilhas_vip:
                        cod = str(row.get(col_doc, "")).strip().upper()
                        if cod:
                            docs_restritos.add(cod)

    arvore, total = {}, 0
    for _, row in df_map.iterrows():
        raw_doc = str(row.get(col_doc, "")).strip()
        if not raw_doc:
            continue
        doc_key = raw_doc.upper()
        is_restrito = doc_key in docs_restritos
        tracking_id = map_doc_to_tracking.get(doc_key)
        df_doc = hist_by_tracking.get(tracking_id) if tracking_id is not None else None
        if df_doc is None:
            continue

        raw_a, real_a, rev_a, data_a = obter_snapshot_status(df_doc, dt_corte_antes)
        raw_d, real_d, rev_d, data_d = obter_snapshot_status(df_doc, dt_fim)
        if is_restrito:
            efet_a = calcula_status_consolidado_estrito(real_a, real_a)
            efet_d = calcula_status_consolidado_estrito(real_d, real_d)
        else:
            efet_a, efet_d = real_a, real_d

        mudou = False
        if tipo_visao == "Efetiva":
            mudou = efet_a != efet_d
        else:
            if pd.isna(data_a) and pd.notna(data_d):
                mudou = True
            elif pd.notna(data_a) and pd.notna(data_d) and data_a != data_d:
                mudou = True
            elif efet_a != efet_d:
                mudou = True

        if not mudou:
            continue
        total += 1
        valor_agr = str(row.get(col_agrupador, f"SEM {agrupador_escolhido.upper()}")).strip()
        nivel = str(row.get(col_nivel, "SEM NÍVEL")).strip()
        item = {
            "doc": raw_doc, "titulo": str(row.get(col_titulo, "")).strip(), "nivel": nivel,
            "grupo": valor_agr, "raw_antes": raw_a, "real_antes": efet_a,
            "raw_depois": raw_d, "real_depois": efet_d, "rev_antes": rev_a,
            "data_antes": data_a.strftime("%d/%m/%y") if pd.notna(data_a) else "-",
            "rev_depois": rev_d,
            "data_depois": data_d.strftime("%d/%m/%y") if pd.notna(data_d) else "-",
        }
        arvore.setdefault(valor_agr, {}).setdefault(nivel, []).append(item)

    return True, arvore, total
