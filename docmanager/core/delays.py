"""Atrasos por revisão do histórico consolidado (feature nova principal).

Decisão do usuário (2026-07-11): QUATRO colunas — dias corridos brutos (tempo
de ciclo) E atraso com desconto de SLA, para cada lado (Itaipu e CMI):

  Dias Itaipu    = (Data Retorno − Data Envio).days
  Atraso Itaipu  = max(0, Dias Itaipu − SLA[30 se 0A senão 15])
  Dias CMI       = 1ª emissão: (Data Envio − data_ref).days
                   reemissão APÓS REPROVAÇÃO: (Data Envio − Retorno anterior).days
  Atraso CMI     = 1ª emissão: max(0, Dias CMI)         (SEM desconto — a data
                                                          prevista já É o prazo)
                   reemissão após reprovação: max(0, Dias CMI − 15)
                   sintética (não postada): max(0, hoje − data_ref)  ← correndo

REGRA DE NECESSIDADE (2026-07): a reemissão só conta atraso CMI quando a
revisão ANTERIOR foi REPROVADA ('Não Aprovado') — é aí que a CMI tem obrigação
de retrabalho. Se a revisão anterior foi aprovada, o ciclo se encerrou; uma
reemissão posterior (ex.: nova família 1A após o "0" final aprovado) NÃO é
atraso — é uma nova necessidade que nasce depois. Isso espelha a "bandeira
documento_aprovado" dos atrasos acumulados (KB §15, Momento C).

Qualquer descontinuidade (sem envio, sem retorno, rev anterior sem retorno,
rev anterior aprovada, datas invertidas, sem data_ref) → célula VAZIA.

`data_ref` chega pré-calculada na coluna 'Data Prevista (Controle)' de cada
linha do wide (REPROGRAMAÇÃO > DATA PREVISTA, resolvida em wide.py).
Opera por Tracking, na ordem canônica de revisão (o wide já vem ordenado).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .constants import (
    COL_REVISAO,
    COL_TRACKING,
    KPI_STATUS_FALHA_UPPER,
    SLA_ITAIPU_DEMAIS,
    SLA_ITAIPU_REV_0A,
)
from .wide import COL_DATA_ENVIO, COL_DATA_RETORNO, COL_STATUS_ENVIO, COL_STATUS_RETORNO

COL_DIAS_ITAIPU = "Dias Itaipu"
COL_ATRASO_ITAIPU = "Atraso Itaipu"
COL_DIAS_CMI = "Dias CMI"
COL_ATRASO_CMI = "Atraso CMI"
COL_DATA_PREVISTA_CTRL = "Data Prevista (Controle)"

_MARCADOR_SINTETICA = "NÃO EMITIDO"


@dataclass(frozen=True)
class DelayPolicy:
    sla_itaipu_0a: int = SLA_ITAIPU_REV_0A
    sla_itaipu_demais: int = SLA_ITAIPU_DEMAIS
    sla_cmi_reemissao: int = SLA_ITAIPU_DEMAIS
    hoje: date | None = None  # injetável para testes; None → data de hoje

    def hoje_ts(self) -> pd.Timestamp:
        return pd.Timestamp(self.hoje) if self.hoje is not None else pd.Timestamp.now().normalize()

    def sla_itaipu(self, revisao) -> int:
        return self.sla_itaipu_0a if str(revisao).strip().upper() == "0A" else self.sla_itaipu_demais


def _dias(a, b) -> int | None:
    """(a − b).days se ambos presentes e a >= b; senão None."""
    if pd.isna(a) or pd.isna(b):
        return None
    d = (pd.Timestamp(a) - pd.Timestamp(b)).days
    return d if d >= 0 else None


def calcular_atrasos(df_wide: pd.DataFrame, policy: DelayPolicy | None = None) -> pd.DataFrame:
    """Anexa as 4 colunas de atraso ao wide. Requer a coluna
    'Data Prevista (Controle)' já preenchida (data ou NaT)."""
    if df_wide.empty:
        return df_wide
    policy = policy or DelayPolicy()
    df = df_wide.copy()
    if COL_DATA_PREVISTA_CTRL not in df.columns:
        df[COL_DATA_PREVISTA_CTRL] = pd.NaT

    dias_it: list = []
    atraso_it: list = []
    dias_cmi: list = []
    atraso_cmi: list = []
    hoje = policy.hoje_ts()

    for _, grupo in df.groupby(COL_TRACKING, sort=False):
        primeira_emissao_vista = False
        retorno_anterior = pd.NaT
        status_retorno_anterior = ""
        for _, row in grupo.iterrows():
            envio = row.get(COL_DATA_ENVIO, pd.NaT)
            retorno = row.get(COL_DATA_RETORNO, pd.NaT)
            status_retorno = str(row.get(COL_STATUS_RETORNO, "")).strip()
            data_ref = row.get(COL_DATA_PREVISTA_CTRL, pd.NaT)
            sintetica = str(row.get(COL_STATUS_ENVIO, "")).strip().upper() == _MARCADOR_SINTETICA

            # --- ITAIPU ---
            di = _dias(retorno, envio)
            dias_it.append(di)
            atraso_it.append(max(0, di - policy.sla_itaipu(row.get(COL_REVISAO))) if di is not None else None)

            # --- CMI ---
            if sintetica:
                dc = None
                ac = max(0, (hoje - pd.Timestamp(data_ref)).days) if pd.notna(data_ref) else None
            elif not primeira_emissao_vista:
                dc = _dias(envio, data_ref)  # nascedouro (vs data prevista/reprogramada)
                ac = max(0, dc) if dc is not None else None  # 1ª emissão: sem desconto de SLA
            elif status_retorno_anterior.upper() in KPI_STATUS_FALHA_UPPER:
                # Reemissão obrigada por reprovação → é necessidade, conta atraso.
                dc = _dias(envio, retorno_anterior)
                ac = max(0, dc - policy.sla_cmi_reemissao) if dc is not None else None
            else:
                # Ciclo fechado com aprovação → reemissão posterior não é atraso.
                dc = None
                ac = None
            dias_cmi.append(dc)
            atraso_cmi.append(ac)

            if pd.notna(envio):
                primeira_emissao_vista = True
            if pd.notna(retorno):
                retorno_anterior = retorno
                status_retorno_anterior = status_retorno

    # Int64 nullable: valores inteiros limpos e <NA> real onde não dá para calcular
    # (evita o 40.0 fantasma do float e distingue "vazio" de "zero").
    df[COL_DIAS_ITAIPU] = pd.array(dias_it, dtype="Int64")
    df[COL_ATRASO_ITAIPU] = pd.array(atraso_it, dtype="Int64")
    df[COL_DIAS_CMI] = pd.array(dias_cmi, dtype="Int64")
    df[COL_ATRASO_CMI] = pd.array(atraso_cmi, dtype="Int64")
    return df
