"""Atrasos por revisão: 4 colunas + todas as descontinuidades (feature nova)."""
from datetime import date

import pandas as pd

from docmanager.core.delays import (
    COL_ATRASO_CMI,
    COL_ATRASO_ITAIPU,
    COL_DATA_PREVISTA_CTRL,
    COL_DIAS_CMI,
    COL_DIAS_ITAIPU,
    DelayPolicy,
    calcular_atrasos,
)

HOJE = date(2024, 12, 31)
POLICY = DelayPolicy(hoje=HOJE)


def _ts(s):
    return pd.Timestamp(s) if s else pd.NaT


def _wide(rows):
    """rows: dicts com tracking, rev, envio, retorno, prev, status_envio, status_retorno.

    status_retorno default 'Aprovado': por padrão o ciclo fecha em aprovação, então
    reemissões NÃO contam atraso (nova regra de necessidade)."""
    return pd.DataFrame([{
        "Tracking ID": r["tracking"],
        "Revisão": r.get("rev", "0A"),
        "Data Envio": _ts(r.get("envio")),
        "Data Retorno": _ts(r.get("retorno")),
        "Status Envio": r.get("status_envio", "Em Processo"),
        "Status Retorno": r.get("status_retorno", "Aprovado"),
        "SLA_Itaipu": r.get("sla", 30),
        COL_DATA_PREVISTA_CTRL: _ts(r.get("prev")),
    } for r in rows])


def test_atraso_itaipu_desconta_sla_0a():
    # 0A: envio 01/03, retorno 10/04 → 40 dias corridos; SLA 30 → atraso 10.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-01", "retorno": "2024-04-10", "sla": 30, "prev": "2024-02-25"},
    ]), POLICY)
    r = df.iloc[0]
    assert r[COL_DIAS_ITAIPU] == 40
    assert r[COL_ATRASO_ITAIPU] == 10


def test_atraso_itaipu_dentro_do_prazo_zera():
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-01", "retorno": "2024-03-20", "sla": 30},
    ]), POLICY)
    assert df.iloc[0][COL_DIAS_ITAIPU] == 19
    assert df.iloc[0][COL_ATRASO_ITAIPU] == 0


def test_primeira_emissao_cmi_sem_desconto():
    # 1ª emissão: envio 10/03, data_ref 01/03 → 9 dias; SEM desconto → atraso 9.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-10", "retorno": "2024-04-01", "sla": 30, "prev": "2024-03-01"},
    ]), POLICY)
    assert df.iloc[0][COL_DIAS_CMI] == 9
    assert df.iloc[0][COL_ATRASO_CMI] == 9


def test_reemissao_apos_reprovacao_conta():
    # 0A REPROVADA em 01/04; 0B envio 30/04 → 29 dias; SLA CMI 15 → atraso 14.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-01", "retorno": "2024-04-01",
         "status_retorno": "Não Aprovado", "sla": 30, "prev": "2024-02-28"},
        {"tracking": "T", "rev": "0B", "envio": "2024-04-30", "retorno": None, "sla": 15},
    ]), POLICY)
    linha_0b = df[df["Revisão"] == "0B"].iloc[0]
    assert linha_0b[COL_DIAS_CMI] == 29
    assert linha_0b[COL_ATRASO_CMI] == 14


def test_reemissao_apos_aprovacao_nao_conta():
    # 0A APROVADA; a reemissão 0B posterior não é obrigada por reprovação → vazio.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-01", "retorno": "2024-04-01",
         "status_retorno": "Aprovado com Comentários", "sla": 30, "prev": "2024-02-28"},
        {"tracking": "T", "rev": "0B", "envio": "2024-04-30", "retorno": None, "sla": 15},
    ]), POLICY)
    linha_0b = df[df["Revisão"] == "0B"].iloc[0]
    assert pd.isna(linha_0b[COL_DIAS_CMI])
    assert pd.isna(linha_0b[COL_ATRASO_CMI])


def test_reemissao_1a_apos_zero_aprovado_nao_conta():
    # Caso do usuário: ciclo fechou no "0" aprovado; 1A é nova família → não conta atraso.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0", "envio": "2024-03-01", "retorno": "2024-03-20",
         "status_retorno": "Aprovado", "sla": 15, "prev": "2024-02-28"},
        {"tracking": "T", "rev": "1A", "envio": "2025-01-10", "retorno": None, "sla": 15},
    ]), POLICY)
    linha_1a = df[df["Revisão"] == "1A"].iloc[0]
    assert pd.isna(linha_1a[COL_DIAS_CMI])
    assert pd.isna(linha_1a[COL_ATRASO_CMI])


def test_sintetica_atraso_cmi_corre_ate_hoje():
    df = calcular_atrasos(_wide([
        {"tracking": "SINT::X", "rev": "", "envio": None, "retorno": None,
         "status_envio": "NÃO EMITIDO", "prev": "2024-12-01"},
    ]), POLICY)
    r = df.iloc[0]
    assert pd.isna(r[COL_DIAS_CMI])
    assert r[COL_ATRASO_CMI] == 30  # 01/12 → 31/12


def test_descontinuidades_viram_vazio():
    df = calcular_atrasos(_wide([
        # sem retorno → Itaipu vazio
        {"tracking": "A", "rev": "0A", "envio": "2024-03-01", "retorno": None, "sla": 30, "prev": "2024-02-01"},
        # datas invertidas (retorno antes do envio) → Itaipu vazio
        {"tracking": "B", "rev": "0A", "envio": "2024-04-01", "retorno": "2024-03-01", "sla": 30},
        # 1ª emissão sem data_ref → CMI vazio
        {"tracking": "C", "rev": "0A", "envio": "2024-03-01", "retorno": "2024-03-20", "sla": 30},
    ]), POLICY)
    a = df[df["Tracking ID"] == "A"].iloc[0]
    assert pd.isna(a[COL_DIAS_ITAIPU]) and pd.isna(a[COL_ATRASO_ITAIPU])
    b = df[df["Tracking ID"] == "B"].iloc[0]
    assert pd.isna(b[COL_DIAS_ITAIPU])
    c = df[df["Tracking ID"] == "C"].iloc[0]
    assert pd.isna(c[COL_DIAS_CMI]) and pd.isna(c[COL_ATRASO_CMI])


def test_reemissao_sem_retorno_anterior_vira_vazio():
    # 0B sem que a 0A tenha retorno → não dá para ancorar o ciclo CMI da 0B.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-01", "retorno": None, "sla": 30, "prev": "2024-02-25"},
        {"tracking": "T", "rev": "0B", "envio": "2024-04-30", "retorno": None, "sla": 15},
    ]), POLICY)
    linha_0b = df[df["Revisão"] == "0B"].iloc[0]
    assert pd.isna(linha_0b[COL_DIAS_CMI])
    assert pd.isna(linha_0b[COL_ATRASO_CMI])
