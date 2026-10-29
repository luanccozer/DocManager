"""Regra única das datas de planejamento: planilha × Controle de Documentos.

A data preenchida na planilha (digitada à mão ou escrita numa rodada anterior)
nunca é trocada pelo Controle sem o aceite de quem roda a atualização: cada troca
possível vira uma incidência (ADR 0001). Célula vazia continua sendo preenchida.
"""
from datetime import date, datetime

from docmanager.core.planejamento import (
    COLUNA_PREVISTA,
    COLUNA_REPROGRAMADA,
    Incidencia,
    reconciliar_datas,
)


def _reconciliar(prevista=None, reprogramada=None, prevista_ctrl=None, reprogramada_ctrl=None,
                 aceitas=frozenset()):
    return reconciliar_datas(prevista_planilha=prevista, reprogramada_planilha=reprogramada,
                             prevista_controle=prevista_ctrl, reprogramada_controle=reprogramada_ctrl,
                             aceitas=aceitas)


def test_celula_vazia_recebe_a_data_do_controle():
    d = _reconciliar(prevista_ctrl=date(2026, 3, 1), reprogramada_ctrl=date(2026, 5, 5))
    assert (d.prevista, d.reprogramada) == (date(2026, 3, 1), date(2026, 5, 5))
    assert d.incidencias == ()
    assert d.data_ref == date(2026, 5, 5)


def test_data_prevista_preenchida_nunca_e_trocada_pelo_controle():
    """O Controle replanejou para frente: a baseline da planilha fica."""
    d = _reconciliar(prevista=date(2026, 3, 1), prevista_ctrl=date(2026, 9, 1))
    assert d.prevista is None                     # não mexer na célula
    assert d.data_ref == date(2026, 3, 1)
    assert d.incidencias == (Incidencia(COLUNA_PREVISTA, date(2026, 3, 1), date(2026, 9, 1)),)


def test_controle_com_data_mais_antiga_tambem_vira_incidencia():
    d = _reconciliar(prevista=date(2026, 9, 1), prevista_ctrl=date(2026, 3, 1))
    assert d.prevista is None
    assert d.incidencias == (Incidencia(COLUNA_PREVISTA, date(2026, 9, 1), date(2026, 3, 1)),)


def test_reprogramada_preenchida_diferente_do_controle_vira_incidencia():
    """A 2ª reprogramação do Controle não chega à planilha sem aceite."""
    d = _reconciliar(prevista=date(2026, 1, 1), reprogramada=date(2026, 11, 10),
                     prevista_ctrl=date(2026, 1, 1), reprogramada_ctrl=date(2026, 12, 15))
    assert d.reprogramada is None
    assert d.data_ref == date(2026, 11, 10)
    assert d.incidencias == (Incidencia(COLUNA_REPROGRAMADA, date(2026, 11, 10), date(2026, 12, 15)),)


def test_texto_na_celula_de_data_vira_incidencia_e_nao_e_apagado():
    d = _reconciliar(reprogramada="A DEFINIR", prevista=date(2026, 3, 1),
                     prevista_ctrl=date(2026, 3, 1), reprogramada_ctrl=date(2026, 12, 15))
    assert d.reprogramada is None
    assert d.incidencias == (Incidencia(COLUNA_REPROGRAMADA, "A DEFINIR", date(2026, 12, 15)),)
    assert d.data_ref == date(2026, 3, 1)         # o texto não é data: vale a prevista


def test_formula_na_celula_de_data_vira_incidencia():
    d = _reconciliar(reprogramada="=DATE(2026,12,1)", reprogramada_ctrl=date(2026, 12, 15))
    assert d.reprogramada is None
    assert d.incidencias == (Incidencia(COLUNA_REPROGRAMADA, "=DATE(2026,12,1)", date(2026, 12, 15)),)


def test_data_igual_a_do_controle_nao_e_incidencia():
    """A célula vem do Excel como datetime; o Controle, como date."""
    d = _reconciliar(prevista=datetime(2026, 3, 1), prevista_ctrl=date(2026, 3, 1))
    assert d.incidencias == () and d.prevista is None
    assert d.data_ref == date(2026, 3, 1)


def test_texto_que_e_data_e_comparado_como_data():
    d = _reconciliar(prevista="01/03/2026", prevista_ctrl=date(2026, 3, 1))
    assert d.incidencias == ()


def test_incidencia_aceita_grava_a_data_do_controle():
    d = _reconciliar(prevista=date(2026, 3, 1), prevista_ctrl=date(2026, 9, 1),
                     aceitas=frozenset({COLUNA_PREVISTA}))
    assert d.prevista == date(2026, 9, 1)
    assert d.data_ref == date(2026, 9, 1)
    # A incidência continua listada: é ela que o log conta como troca aceita.
    assert d.incidencias == (Incidencia(COLUNA_PREVISTA, date(2026, 3, 1), date(2026, 9, 1)),)


def test_aceitar_uma_coluna_nao_troca_a_outra():
    d = _reconciliar(prevista=date(2026, 3, 1), reprogramada=date(2026, 6, 1),
                     prevista_ctrl=date(2026, 4, 1), reprogramada_ctrl=date(2026, 8, 1),
                     aceitas=frozenset({COLUNA_REPROGRAMADA}))
    assert d.prevista is None
    assert d.reprogramada == date(2026, 8, 1)
    assert d.data_ref == date(2026, 8, 1)


def test_sem_controle_a_data_ref_vem_da_planilha():
    d = _reconciliar(prevista=date(2026, 6, 6))
    assert (d.prevista, d.reprogramada, d.incidencias) == (None, None, ())
    assert d.data_ref == date(2026, 6, 6)
