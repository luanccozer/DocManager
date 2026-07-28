"""Motor de Status Real — a "Batalha de Versões" (KB §8).

Porta fiel de `DataManager.calcular_status_real` (legado L128-297). Recebe o
histórico completo do Tracking ID (já tratado de Terminated pelo chamador —
ver truth_line) e a revisão vigente, e devolve o status que o documento
realmente tem, ignorando ruídos de integração.

Alterações vs legado:
  - o literal '2024-08-19' vira `is_regime_novo` (ponto único da regra de corte,
    §21.3) — sem mudança de comportamento, pois o legado já comparava com `>=`;
  - a lista NOMINAL de `core/excecoes.py` (§21.9) libera a reprovação em revisão
    numérica para os documentos publicados com a revisão errada.

A exceção §8.2 (Para Aprovação em planilhas de comissionamento) permanece
SEMPRE ativa, independente do toggle VIP.
"""
from __future__ import annotations

import pandas as pd

from .constants import (
    COL_DATA,
    COL_REVISAO,
    COL_STATUS,
    COL_TITULO,
    COL_VERSAO,
    NAO_EMITIDO,
    PARA_ANALISE_UPPER,
    STATUS_ANULACAO_UPPER,
    STATUS_APROVACAO_UPPER,
    STATUS_EM_INTEGRACAO_UPPER,
    STATUS_INFORMATIVO_UPPER,
    STATUS_REPROVACAO_UPPER,
    is_regime_novo,
)
from .excecoes import reprovacao_numerica_vale


def calcular_status_real(df_tracking: pd.DataFrame, revisao_current) -> str:
    # 1. VALIDAÇÃO BÁSICA
    if df_tracking.empty or not revisao_current:
        return NAO_EMITIDO

    # --- IDENTIFICAÇÃO DE TIPOLOGIA (EXCEÇÃO PLANILHAS §8.2, sempre ativa) ---
    is_planilha = False
    if COL_TITULO in df_tracking.columns:
        titulo_doc = str(df_tracking[COL_TITULO].iloc[0]).strip().upper()
        if "PLANILHA" in titulo_doc and "COMISSIONAMENTO" in titulo_doc:
            is_planilha = True

    # --- LISTAS ESTRITAS (cópias mutáveis) ---
    status_aprovacao = list(STATUS_APROVACAO_UPPER)
    status_reprovacao = list(STATUS_REPROVACAO_UPPER)
    status_informativo = list(STATUS_INFORMATIVO_UPPER)
    status_anulacao = list(STATUS_ANULACAO_UPPER)
    lista_integracao_upper = list(STATUS_EM_INTEGRACAO_UPPER)

    def verificar_se_integracao(status_texto, data_texto) -> bool:
        st = str(status_texto).strip().upper()
        if st in lista_integracao_upper:
            return True
        if st in PARA_ANALISE_UPPER:
            try:
                dt = pd.to_datetime(data_texto, dayfirst=True)
                if is_regime_novo(dt):
                    return True
            except Exception:
                pass
        return False

    if is_planilha:
        status_aprovacao.append("PARA APROVAÇÃO")
        if "PARA APROVAÇÃO" in lista_integracao_upper:
            lista_integracao_upper.remove("PARA APROVAÇÃO")

    df = df_tracking.copy()
    df["Versão_Int"] = pd.to_numeric(df[COL_VERSAO], errors="coerce").fillna(0)

    # 2. STATUS ATUAL (LINHA DA VERDADE dentro da revisão vigente)
    try:
        df_curr = df[df[COL_REVISAO].str.strip() == str(revisao_current).strip()]
        if df_curr.empty:
            return NAO_EMITIDO
        linha_atual = df_curr.sort_values(by=["Versão_Int"], ascending=False).iloc[0]
        status_atual_str = str(linha_atual[COL_STATUS]).strip().upper()
    except Exception:
        return NAO_EMITIDO

    # 3. RETORNOS IMEDIATOS (o presente definitivo vence)
    if status_atual_str in status_aprovacao:
        return linha_atual[COL_STATUS]
    if status_atual_str in status_anulacao:
        return linha_atual[COL_STATUS]
    if status_atual_str in status_reprovacao:
        # Revisão-letra (0A, 0B...) retorna reprovado direto. Revisão NUMÉRICA
        # seca ('0', '1') é o marco definitivo da família: uma reprovação nela é
        # contraditória e segue para a batalha, onde é tratada como ruído.
        # A exceção nominal (§21.9) cobre o documento emitido direto em revisão
        # numérica por engano de publicação — sem ela, ele viraria NÃO EMITIDO.
        if not str(revisao_current).isdigit() or reprovacao_numerica_vale(df_tracking):
            return linha_atual[COL_STATUS]
    if status_atual_str in status_informativo:
        return linha_atual[COL_STATUS]

    # 4. CAMPO DE BATALHA (histórico fora da revisão vigente)
    df_historico = df[df[COL_REVISAO].str.strip() != str(revisao_current).strip()].copy()

    # --- CENÁRIO A: STATUS ATUAL FANTASMA (integração/interno) ---
    if verificar_se_integracao(status_atual_str, linha_atual.get(COL_DATA, "")):
        # Tentativa de salvamento na própria revisão: veredito oficial anterior.
        status_oficiais = status_aprovacao + status_reprovacao + status_informativo
        df_curr_real = df_curr[df_curr[COL_STATUS].str.strip().str.upper().isin(status_oficiais)].copy()
        if not df_curr_real.empty:
            linha_salva = df_curr_real.sort_values(by=["Versão_Int"], ascending=False).iloc[0]
            return linha_salva[COL_STATUS]
        if df_historico.empty:
            return NAO_EMITIDO
        df_alvo_batalha = df_historico
    # --- CENÁRIO B: STATUS ATUAL REAL (ex.: Em Processo) ---
    else:
        if df_historico.empty:
            if status_atual_str == "EM PROCESSO":
                return "Em Processo"
            return NAO_EMITIDO
        # Filtra a FAMÍLIA ATUAL — mudar de família (0->1) reseta aprovações.
        familia_atual = str(revisao_current).strip()[0]
        mask_familia = df_historico[COL_REVISAO].astype(str).str.strip().str.startswith(familia_atual)
        df_alvo_batalha = df_historico[mask_familia]
        if df_alvo_batalha.empty:
            if status_atual_str == "EM PROCESSO":
                return "Em Processo"
            return NAO_EMITIDO

    # 5. A BATALHA DE VERSÕES (REI DA COLINA)
    versao_aprovada_max = -1
    status_aprovada_txt = ""
    versao_reprovada_max = -1
    status_reprovada_txt = ""
    versao_informativa_max = -1
    status_informativa_txt = ""
    for _, row in df_alvo_batalha.iterrows():
        st = str(row[COL_STATUS]).strip().upper()
        v = row["Versão_Int"]
        rev_row = str(row[COL_REVISAO]).strip()
        if st in status_aprovacao:
            if v > versao_aprovada_max:
                versao_aprovada_max = v
                status_aprovada_txt = row[COL_STATUS]
        elif st in status_reprovacao:
            if rev_row.isdigit():  # reprovação em revisão numérica é ignorada
                continue
            if v > versao_reprovada_max:
                versao_reprovada_max = v
                status_reprovada_txt = row[COL_STATUS]
        elif st in status_informativo:
            if v > versao_informativa_max:
                versao_informativa_max = v
                status_informativa_txt = row[COL_STATUS]

    # 6. O VEREDITO (vitória exige maioria estrita)
    if versao_reprovada_max > versao_aprovada_max and versao_reprovada_max > versao_informativa_max:
        if status_atual_str in lista_integracao_upper:
            return status_reprovada_txt  # "Não Aprovado"
        return "Em Processo"
    if versao_aprovada_max > versao_reprovada_max and versao_aprovada_max > versao_informativa_max:
        return status_aprovada_txt
    if versao_informativa_max > versao_reprovada_max and versao_informativa_max > versao_aprovada_max:
        return status_informativa_txt

    # 7. FALLBACK (empate ou sem veredito na batalha)
    if status_atual_str in lista_integracao_upper:
        if not df_alvo_batalha.empty:
            ultima_linha = df_alvo_batalha.sort_values(by=["Versão_Int"], ascending=False).iloc[0]
            st_ultima = str(ultima_linha[COL_STATUS]).strip().upper()
            if verificar_se_integracao(st_ultima, ultima_linha.get(COL_DATA, "")):
                return NAO_EMITIDO
            if st_ultima == "EM PROCESSO":
                return "Em Processo"
            return ultima_linha[COL_STATUS]
        return NAO_EMITIDO
    if status_atual_str == "EM PROCESSO":
        return "Em Processo"
    return NAO_EMITIDO
