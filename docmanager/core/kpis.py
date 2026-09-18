"""KPIs analíticos e atrasos acumulados por documento (KB §14, §15).

Porta de `DataManager.analisar_kpis_documento` (L1772) e
`calcular_atrasos_acumulados` (L1916). `hoje` é injetável (testes/determinismo).
A limpeza de Terminated delega ao limiar único de `truth_line`; o extermínio de
ciclos internos (revisões len > 2, ex.: 0AA) é específico dos KPIs (§14.1).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from .constants import (
    COL_DATA,
    COL_REVISAO,
    COL_STATUS,
    KPI_STATUS_CANCELADO_UPPER,
    KPI_STATUS_FALHA_UPPER,
    KPI_STATUS_SUCESSO_UPPER,
    NAO_EMITIDO,
    SLA_CMI_REEMISSAO,
    SLA_ITAIPU_DEMAIS,
    SLA_ITAIPU_REV_0A,
)
from .truth_line import limpar_terminated_por_limiar


def _hoje(hoje: date | None) -> pd.Timestamp:
    return pd.Timestamp(hoje) if hoje is not None else pd.Timestamp.now().normalize()


def _preparar_historico(df_tracking: pd.DataFrame) -> pd.DataFrame:
    """Limpeza padrão dos KPIs (§14.1): normaliza revisão, extermina ciclos
    internos (len > 2), aplica o limiar de Terminated, ordena por data."""
    df = df_tracking.copy()
    df[COL_REVISAO] = df[COL_REVISAO].astype(str).str.upper().str.replace("R", "", regex=False).str.strip()
    df = df[df[COL_REVISAO].str.len() <= 2]
    df = limpar_terminated_por_limiar(df)
    if df.empty:
        return df
    df["Data_Obj"] = pd.to_datetime(df[COL_DATA], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["Data_Obj"]).sort_values("Data_Obj")
    df["Status_Upper"] = df[COL_STATUS].astype(str).str.strip().str.upper()
    return df


# Revisão que marca o nascimento do documento no ciclo da Itaipu.
REV_NASCEDOURA_PADRAO = "0A"


def _rev_nascedoura(emissoes: pd.DataFrame) -> str:
    """Revisão que conta como nascimento, entre as que foram DE FATO emitidas.

    `0A` quando ela existe; senão, a da emissão mais antiga (documento SAT /
    legado, que já entra em revisão alta).
    """
    revs = emissoes[COL_REVISAO].astype(str).str.strip()
    if (revs == REV_NASCEDOURA_PADRAO).any():
        return REV_NASCEDOURA_PADRAO
    return revs.loc[emissoes["Data_Obj"].idxmin()]


def data_primeira_emissao(df_tracking: pd.DataFrame) -> date | None:
    """Data em que o documento foi emitido pela PRIMEIRA vez (KB §27.5).

    É a régua de aderência ao planejamento: comparada com a `DATA-ALVO EMISSÃO`,
    diz se o documento nasceu no prazo. **Não confundir com `DATA ÚLTIMA
    EMISSÃO`**, que é a revisão vigente — 0A→0F é ciclo normal de aprovação, e
    usar a última revisão como régua produziria um mar de falsos atrasos.

    Regras (decididas pelo usuário em 2026-09-16):

    - **A revisão nascedoura é a `0A`** quando ela existe no histórico limpo.
    - **Sem `0A`, vale a emissão mais antiga** — é o caso dos documentos SAT,
      continuação de documentos legados da Itaipu, que já entram em revisões
      altas. O que interessa ali é a primeira entrega PARA A ITAIPU, e o
      histórico já chega aqui sem o lixo descartado (ciclos internos e revisões
      mortas por Terminated).
    - **Dentro da revisão nascedoura vale a emissão MAIS RECENTE** (`.max()`):
      reenvio da mesma revisão corrigiu a entrega anterior, então é ele que
      marca a entrega válida.

    O evento de emissão é a linha com `Status == 'Em Processo'` — a submissão à
    Itaipu. Revisão que nunca teve 'Em Processo' é ruído e não conta (mesma
    leitura do Momento B em `calcular_atrasos_acumulados`).

    Devolve `None` quando o documento nunca foi emitido.

    > O "Momento A" de `calcular_atrasos_acumulados` responde a uma pergunta
    > parecida, mas **não** é a mesma conta: lá a revisão nascedoura é sempre a
    > primeira cronológica (nunca prefere `0A`). Mantido como está de propósito —
    > aquele número já está validado em dados reais e mexer nele mudaria o
    > `atraso_acumulado_cmi` em produção.
    """
    if df_tracking.empty:   # antes de _preparar_historico: sem colunas ele quebra
        return None
    df = _preparar_historico(df_tracking)
    if df.empty:
        return None
    emissoes = df[df["Status_Upper"] == "EM PROCESSO"]
    if emissoes.empty:
        return None
    rev = _rev_nascedoura(emissoes)
    datas = emissoes.loc[emissoes[COL_REVISAO].astype(str).str.strip() == rev, "Data_Obj"]
    return None if datas.empty else datas.max().date()


def analisar_kpis_documento(df_tracking: pd.DataFrame, status_real, revisao_atual,
                            data_prevista, *, hoje: date | None = None) -> dict:
    hj = _hoje(hoje)
    res = {"dias_status": "", "situacao_prazo": "-", "dias_atraso": "",
           "total_ciclos": 0, "ciclos_aprovar": 0, "downgrade": "NÃO"}

    # 1. NÃO EMITIDO: cobra a data prevista, se houver.
    if status_real == NAO_EMITIDO:
        if pd.notna(data_prevista) and str(data_prevista).strip() != "":
            dt_prev = pd.to_datetime(data_prevista, errors="coerce", dayfirst=True)
            if pd.notna(dt_prev):
                atraso = (hj - dt_prev.normalize()).days
                res["dias_atraso"] = atraso
                res["situacao_prazo"] = "Atrasado" if atraso > 0 else "No Prazo"
            else:
                res["situacao_prazo"] = "Data não informada"
        else:
            res["situacao_prazo"] = "Data não informada"
        return res

    df = _preparar_historico(df_tracking)
    if df.empty:
        return res

    # 2. Ciclos e downgrade.
    revisoes_unicas = df[COL_REVISAO].dropna().unique()
    res["total_ciclos"] = len(revisoes_unicas)
    ja_aprovado = False
    vistas: set[str] = set()
    for _, row in df.iterrows():
        vistas.add(str(row[COL_REVISAO]).strip().upper())
        if not ja_aprovado and row["Status_Upper"] in KPI_STATUS_SUCESSO_UPPER:
            ja_aprovado = True
            res["ciclos_aprovar"] = len(vistas)

    v_sucesso = df.loc[df["Status_Upper"].isin(KPI_STATUS_SUCESSO_UPPER), "Versão_Int"]
    v_falha = df.loc[df["Status_Upper"].isin(KPI_STATUS_FALHA_UPPER), "Versão_Int"]
    if not v_sucesso.empty and not v_falha.empty and (v_falha > v_sucesso.min()).any():
        res["downgrade"] = "SIM"

    # 3. SLAs (viagem no tempo).
    sr = str(status_real).strip().upper()
    if sr in KPI_STATUS_SUCESSO_UPPER:
        res.update(situacao_prazo="Doc Aprovado", dias_status="", dias_atraso="")
        return res
    if sr in KPI_STATUS_CANCELADO_UPPER:
        res.update(situacao_prazo="Doc Cancelado", dias_status="", dias_atraso="")
        return res

    if sr == "EM PROCESSO":  # bola com a Itaipu
        sla = SLA_ITAIPU_REV_0A if str(revisao_atual).strip().upper() == "0A" else SLA_ITAIPU_DEMAIS
        df_rev = df[df[COL_REVISAO].astype(str).str.strip().str.upper() == str(revisao_atual).strip().upper()]
        if not df_rev.empty:
            dias = (hj - df_rev["Data_Obj"].max()).days
            res["dias_status"] = dias
            res["dias_atraso"] = dias - sla
            res["situacao_prazo"] = "Atrasado" if res["dias_atraso"] > 0 else "No Prazo"
    else:  # bola com a CMI
        retornos = df[df["Status_Upper"].isin(
            list(KPI_STATUS_SUCESSO_UPPER) + list(KPI_STATUS_FALHA_UPPER) + list(KPI_STATUS_CANCELADO_UPPER))]
        if not retornos.empty:
            dias = (hj - retornos["Data_Obj"].max()).days
            res["dias_status"] = dias
            res["dias_atraso"] = dias - SLA_CMI_REEMISSAO
            res["situacao_prazo"] = "Atrasado" if res["dias_atraso"] > 0 else "No Prazo"
    return res


def calcular_atrasos_acumulados(df_tracking: pd.DataFrame, status_real, data_prevista,
                                *, hoje: date | None = None) -> dict:
    """Auditoria bruta (sem banco de horas) do atraso acumulado IB e CMI (§15)."""
    hj = _hoje(hoje)
    res = {"atraso_acumulado_itaipu": 0, "atraso_acumulado_cmi": 0}
    sr = str(status_real).strip().upper()

    df = df_tracking.copy()
    if df.empty and sr != NAO_EMITIDO.upper():
        return res
    if not df.empty:
        df = _preparar_historico(df)

    # Momento A: nascedouro (CMI vs data prevista).
    dt_prev = pd.NaT
    if pd.notna(data_prevista) and str(data_prevista).strip() != "":
        dt_prev = pd.to_datetime(data_prevista, errors="coerce", dayfirst=True)
        if pd.notna(dt_prev):
            dt_prev = dt_prev.normalize()
    revisoes = df[COL_REVISAO].dropna().unique() if (not df.empty and COL_REVISAO in df.columns) else []
    if pd.notna(dt_prev):
        if df.empty or sr == NAO_EMITIDO.upper():
            res["atraso_acumulado_cmi"] += max(0, (hj - dt_prev).days)
        elif len(revisoes) > 0:
            df_nasc = df[(df[COL_REVISAO] == revisoes[0]) & (df["Status_Upper"] == "EM PROCESSO")]
            if not df_nasc.empty:
                res["atraso_acumulado_cmi"] += max(0, (df_nasc["Data_Obj"].max() - dt_prev).days)
    if df.empty:
        return res

    # Momentos B (Itaipu) e C (retrabalho CMI) — bandeira documento_aprovado.
    documento_aprovado = False
    for i, rev in enumerate(revisoes):
        df_rev = df[df[COL_REVISAO] == rev]
        df_envio = df_rev[df_rev["Status_Upper"] == "EM PROCESSO"]
        if df_envio.empty:
            continue  # revisão sem "Em Processo" é ruído → ignora o ciclo
        inicio_itaipu = df_envio["Data_Obj"].max()
        df_veredito = df_rev[df_rev["Status_Upper"].isin(list(KPI_STATUS_SUCESSO_UPPER) + list(KPI_STATUS_FALHA_UPPER))]
        fim_itaipu, veredito = None, None
        if not df_veredito.empty:
            fim_itaipu = df_veredito["Data_Obj"].max()
            veredito = df_veredito.loc[df_veredito["Data_Obj"].idxmax(), "Status_Upper"]
        elif sr == "EM PROCESSO" and i == len(revisoes) - 1:
            fim_itaipu = hj

        if fim_itaipu is not None and not documento_aprovado:
            sla_it = SLA_ITAIPU_REV_0A if rev == "0A" else SLA_ITAIPU_DEMAIS
            res["atraso_acumulado_itaipu"] += max(0, (fim_itaipu - inicio_itaipu).days - sla_it)

        if veredito in KPI_STATUS_SUCESSO_UPPER or veredito in KPI_STATUS_CANCELADO_UPPER:
            documento_aprovado = True   # congela
        elif veredito in KPI_STATUS_FALHA_UPPER:
            documento_aprovado = False  # downgrade → descongela

        # Momento C: retrabalho CMI só após falha (bandeira abaixada).
        if not documento_aprovado and veredito in KPI_STATUS_FALHA_UPPER:
            inicio_cmi, fim_cmi = fim_itaipu, None
            if i + 1 < len(revisoes):
                df_prox = df[(df[COL_REVISAO] == revisoes[i + 1]) & (df["Status_Upper"] == "EM PROCESSO")]
                if not df_prox.empty:
                    fim_cmi = df_prox["Data_Obj"].max()
            if fim_cmi is None and sr not in KPI_STATUS_SUCESSO_UPPER and sr != "EM PROCESSO":
                fim_cmi = hj
            if fim_cmi is not None:
                res["atraso_acumulado_cmi"] += max(0, (fim_cmi - inicio_cmi).days - SLA_CMI_REEMISSAO)
    return res
