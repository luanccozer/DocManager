"""Análise Delta - a "Máquina do Tempo" (KB §17).

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
    COL_CURRENT,
    COL_DATA,
    COL_DOC_ITAIPU,
    COL_REVISAO,
    COL_STATUS,
    COL_TITULO,
    COL_TRACKING,
    NAO_EMITIDO,
)
from .consolidation import calcula_status_consolidado_estrito
from .status_engine import calcular_status_real
from .truth_line import limpar_terminated_por_limiar

# Metadados da base que servem de classificação flexível no Delta por documento.
METADADOS_AGRUPAVEIS = [
    "Especialidade", "Subespecialidade", "Tipo do Documento DCC",
    "Subtipo DCC", "Tipo do Documento", "Disciplina (Modelo)",
]


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

    # Pente-fino no Delta: só quando o toggle está ligado. Mesma regra do Mapa
    # (core/hierarchy.py): planilhas VIP (nível 3) restringem seus documentos de
    # nível 4; planos de (des)comissionamento (nível 2) restringem suas planilhas
    # de nível 3 (pedido do usuário).
    docs_restritos = set()
    if estrito:
        planilhas_vip = set()
        planos_comiss = set()
        for _, row in df_map.iterrows():
            cod = str(row.get(col_doc, "")).strip().upper()
            if not cod:
                continue
            nivel = str(row.get(col_nivel, "")).strip()
            desc = str(row.get(col_titulo, "")).upper()
            if nivel == "3" and "PLANILHA" in desc:
                planilhas_vip.add(cod)
            elif nivel == "2" and any(t in desc for t in
                                      ("PLANO DE COMISSIONAMENTO", "PLANO DE DESCOMISSIONAMENTO")):
                planos_comiss.add(cod)
        if planilhas_vip or planos_comiss:
            for _, row in df_map.iterrows():
                cod = str(row.get(col_doc, "")).strip().upper()
                if not cod:
                    continue
                nivel = str(row.get(col_nivel, "")).strip()
                pred = str(row.get(col_pred, "")).strip().upper()
                if (nivel == "4" and pred in planilhas_vip) or (nivel == "3" and pred in planos_comiss):
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

    total = _deduplicar_e_marcar_repetidos(arvore)
    return True, arvore, total


def _deduplicar_e_marcar_repetidos(arvore) -> int:
    """Colapsa repetições do mesmo documento dentro do grupo e sinaliza os que
    caem em grupos diferentes (regra do usuário 2026-07-19).

    O mapeamento lista o mesmo documento em várias linhas (predecessores, planos
    que aparecem em mais de um lugar): antes ele contava/aparecia N vezes no mesmo
    nível do grupo, como se fossem N documentos. Aqui um documento repetido no
    MESMO grupo vira 1 (mantém a 1ª ocorrência); um documento presente em MAIS DE
    UM grupo recebe `repetido_grupos=True` para a UI/Excel destacarem em vermelho.
    Retorna o total de documentos já deduplicados.
    """
    grupos_por_doc: dict[str, set] = {}
    for grupo, niveis in arvore.items():
        for docs in niveis.values():
            for it in docs:
                grupos_por_doc.setdefault(it["doc"].strip().upper(), set()).add(grupo)

    total = 0
    for niveis in arvore.values():
        for nivel, docs in niveis.items():
            vistos: set[str] = set()
            unicos = []
            for it in docs:
                chave = it["doc"].strip().upper()
                if chave in vistos:
                    continue
                vistos.add(chave)
                it["repetido_grupos"] = len(grupos_por_doc.get(chave, ())) > 1
                unicos.append(it)
            niveis[nivel] = unicos
            total += len(unicos)
    return total


def calcular_mudancas_base(df_base, data_ini_str, data_fim_str, *,
                           coluna_agrupar="Especialidade", tipo_visao="Efetiva",
                           codigos=None):
    """Delta FLEXÍVEL direto na base Aconex (KB §17, sem depender do mapeamento).

    Agrupa por um metadado à escolha (Especialidade, DCC, etc.) - evita usar o
    mapeamento como gambiarra para classificações que não são de plano.
    `codigos`: se dado, restringe aos documentos cujo No. do Documento/Controle
    do Emissor estão na lista. Retorna (ok, arvore{grupo: {"—": [itens]}}, total).
    """
    try:
        dt_ini = pd.to_datetime(data_ini_str, dayfirst=True)
        dt_fim = pd.to_datetime(data_fim_str, dayfirst=True).replace(hour=23, minute=59, second=59)
        dt_antes = dt_ini - pd.Timedelta(seconds=1)
    except Exception:
        return False, "Erro na data", 0
    if COL_TRACKING not in df_base.columns:
        return False, "Base sem coluna Tracking ID", 0

    df = df_base.copy()
    df["Data_Obj"] = pd.to_datetime(df[COL_DATA], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Data_Obj"])
    if coluna_agrupar not in df.columns:
        return False, f"Coluna '{coluna_agrupar}' não existe na base", 0

    filtro = None
    if codigos:
        alvo = {str(c).strip().upper() for c in codigos if str(c).strip()}
        filtro = alvo

    arvore, total = {}, 0
    for tracking, grupo in df.groupby(COL_TRACKING):
        if filtro is not None:
            cods = set(grupo[COL_DOC_ITAIPU].astype(str).str.strip().str.upper())
            cods |= set(grupo.get("Controle do Emissor", pd.Series(dtype=str)).astype(str).str.strip().str.upper())
            if not (cods & filtro):
                continue
        raw_a, real_a, rev_a, data_a = obter_snapshot_status(grupo, dt_antes)
        raw_d, real_d, rev_d, data_d = obter_snapshot_status(grupo, dt_fim)

        if tipo_visao == "Efetiva":
            mudou = real_a != real_d
        else:
            mudou = (pd.isna(data_a) and pd.notna(data_d)) or \
                    (pd.notna(data_a) and pd.notna(data_d) and data_a != data_d) or (real_a != real_d)
        if not mudou:
            continue
        total += 1
        # Classificação: metadado da linha vigente (Current) ou da última.
        cur = grupo[grupo[COL_CURRENT].astype(str).str.lower() == "true"]
        ref = cur.iloc[0] if not cur.empty else grupo.sort_values("Data_Obj").iloc[-1]
        agr = str(ref.get(coluna_agrupar, "") or "(sem classificação)").strip() or "(sem classificação)"
        doc = str(ref.get(COL_DOC_ITAIPU, "")).strip()
        item = {
            "doc": doc, "titulo": str(ref.get(COL_TITULO, "")).strip(), "nivel": "-",
            "grupo": agr, "raw_antes": raw_a, "real_antes": real_a,
            "raw_depois": raw_d, "real_depois": real_d, "rev_antes": rev_a,
            "data_antes": data_a.strftime("%d/%m/%y") if pd.notna(data_a) else "-",
            "rev_depois": rev_d,
            "data_depois": data_d.strftime("%d/%m/%y") if pd.notna(data_d) else "-",
        }
        arvore.setdefault(agr, {}).setdefault("—", []).append(item)

    return True, arvore, total
