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


def test_reemissao_cmi_conta_sempre():
    # No histórico base, toda reemissão conta (o recorte por reprovação é da
    # camada de análise). 0A retorno 01/04; 0B envio 30/04 → 29 dias; −15 → 14.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-01", "retorno": "2024-04-01", "sla": 30, "prev": "2024-02-28"},
        {"tracking": "T", "rev": "0B", "envio": "2024-04-30", "retorno": None, "sla": 15},
    ]), POLICY)
    linha_0b = df[df["Revisão"] == "0B"].iloc[0]
    assert linha_0b[COL_DIAS_CMI] == 29
    assert linha_0b[COL_ATRASO_CMI] == 14


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
        # sem retorno mas SUPERADA por envio mais novo → Itaipu vazio (doc seguiu adiante)
        {"tracking": "A", "rev": "0A", "envio": "2024-03-01", "retorno": None, "sla": 30, "prev": "2024-02-01"},
        {"tracking": "A", "rev": "0B", "envio": "2024-04-05", "retorno": "2024-04-20", "sla": 15},
        # datas invertidas (retorno antes do envio) → Itaipu vazio
        {"tracking": "B", "rev": "0A", "envio": "2024-04-01", "retorno": "2024-03-01", "sla": 30},
        # 1ª emissão sem data_ref → CMI vazio
        {"tracking": "C", "rev": "0A", "envio": "2024-03-01", "retorno": "2024-03-20", "sla": 30},
    ]), POLICY)
    a = df[(df["Tracking ID"] == "A") & (df["Revisão"] == "0A")].iloc[0]
    assert pd.isna(a[COL_DIAS_ITAIPU]) and pd.isna(a[COL_ATRASO_ITAIPU])
    b = df[df["Tracking ID"] == "B"].iloc[0]
    assert pd.isna(b[COL_DIAS_ITAIPU])
    c = df[df["Tracking ID"] == "C"].iloc[0]
    assert pd.isna(c[COL_DIAS_CMI]) and pd.isna(c[COL_ATRASO_CMI])


def test_em_aberto_com_itaipu_conta_ate_hoje():
    """Pedido do usuário (2026-07-14): enviado e ainda não devolvido = o relógio
    corre até hoje NAS PRÓPRIAS colunas Dias/Atraso Itaipu - mas só para o envio
    mais recente do documento (revisões superadas continuam vazias)."""
    df = calcular_atrasos(_wide([
        # documento com uma única revisão pendente: 01/09 → 31/12 = 121 dias
        {"tracking": "P", "rev": "0A", "envio": "2024-09-01", "retorno": None, "sla": 30},
        # documento em que a 0A pendente foi superada pela 0B (também pendente):
        # só a 0B (envio mais recente) conta; a 0A fica vazia
        {"tracking": "Q", "rev": "0A", "envio": "2024-03-01", "retorno": None, "sla": 30, "prev": "2024-02-25"},
        {"tracking": "Q", "rev": "0B", "envio": "2024-04-30", "retorno": None, "sla": 15},
    ]), POLICY)
    p = df[df["Tracking ID"] == "P"].iloc[0]
    assert p[COL_DIAS_ITAIPU] == 121          # 01/09 → 31/12
    assert p[COL_ATRASO_ITAIPU] == 91         # 121 − SLA 30
    q0a = df[(df["Tracking ID"] == "Q") & (df["Revisão"] == "0A")].iloc[0]
    assert pd.isna(q0a[COL_DIAS_ITAIPU]) and pd.isna(q0a[COL_ATRASO_ITAIPU])
    q0b = df[(df["Tracking ID"] == "Q") & (df["Revisão"] == "0B")].iloc[0]
    assert q0b[COL_DIAS_ITAIPU] == 245        # 30/04 → 31/12
    assert q0b[COL_ATRASO_ITAIPU] == 230      # 245 − SLA 15


def test_reemissao_sem_retorno_anterior_vira_vazio():
    # 0B sem que a 0A tenha retorno → não dá para ancorar o ciclo CMI da 0B.
    df = calcular_atrasos(_wide([
        {"tracking": "T", "rev": "0A", "envio": "2024-03-01", "retorno": None, "sla": 30, "prev": "2024-02-25"},
        {"tracking": "T", "rev": "0B", "envio": "2024-04-30", "retorno": None, "sla": 15},
    ]), POLICY)
    linha_0b = df[df["Revisão"] == "0B"].iloc[0]
    assert pd.isna(linha_0b[COL_DIAS_CMI])
    assert pd.isna(linha_0b[COL_ATRASO_CMI])
