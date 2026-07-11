"""Diferencial cartesiano do consolidado + testes da regra estrita.

Prova que a única divergência vs legado é a regra morta 'Análise 1ª Emissão'
(§21.5), isolada num único par (sr, se).
"""
import pytest
from builders import HistoricoBuilder  # noqa: F401 (mantém tests/ no path)

from docmanager.core.consolidation import (
    calcula_parado_com,
    calcula_status_consolidado,
    calcula_status_consolidado_estrito,
    calcular_emitido_nao_emitido,
)
from legacy.data_manager import DataManager

DM = DataManager()

_SR = [
    "Aprovado", "Aprovado com Comentários", "Para Assinatura", "Informativo",
    "Para Aprovação", "Não Aprovado", "Em Processo", "NÃO EMITIDO", "Anulado",
    "Cancelado", "Issued for Annulment", "Análise 1ª Emissão", "Em Integração", "",
]
_SE = ["Em Processo", "Não Aprovado", "Para Análise", "Em Integração", "Aprovado", "Integrado", ""]
_ENE = ["EMITIDO", "NÃO EMITIDO", "SATedms", ""]

# Único ponto onde a remoção da regra morta muda a saída.
_REGRA_MORTA = ("Análise 1ª Emissão", "Em Processo")


@pytest.mark.parametrize("sr", _SR)
@pytest.mark.parametrize("se", _SE)
@pytest.mark.parametrize("ene", _ENE)
def test_consolidado_diferencial_cartesiano(sr, se, ene):
    novo = calcula_status_consolidado(sr, se, ene)
    legado = DM.calcula_status_consolidado(sr, se, ene)
    if (sr, se) == _REGRA_MORTA:
        assert legado == "EM PROCESSO" and novo == "ERRO"
    else:
        assert novo == legado


@pytest.mark.parametrize("sc", ["APROVADO", "NÃO APROVADO", "EM PROCESSO", "NÃO EMITIDO", "ERRO"])
def test_emitido_diferencial(sc):
    assert calcular_emitido_nao_emitido(sc) == DM.calcular_emitido_nao_emitido(sc)


@pytest.mark.parametrize("sr", _SR)
def test_estrito_diferencial(sr):
    for cons_atual in ["EM PROCESSO", "NÃO APROVADO", "APROVADO"]:
        assert (calcula_status_consolidado_estrito(sr, cons_atual)
                == DM.calcula_status_consolidado_estrito(sr, cons_atual))


def test_estrito_rebaixa_aprovacoes_parciais():
    assert calcula_status_consolidado_estrito("Aprovado", "APROVADO") == "APROVADO"
    assert calcula_status_consolidado_estrito("Aprovado com Comentários", "APROVADO") == "APROVAÇÃO INTERMEDIÁRIA"
    assert calcula_status_consolidado_estrito("Para Aprovação", "APROVADO") == "APROVAÇÃO INTERMEDIÁRIA"
    # Não-aprovações mantêm o consolidado que já vinha
    assert calcula_status_consolidado_estrito("Em Processo", "EM PROCESSO") == "EM PROCESSO"


@pytest.mark.parametrize("st,esperado", [("Em Processo", "ITAIPU"), ("Aprovado", "CMI"), ("", "CMI")])
def test_parado_com(st, esperado):
    assert calcula_parado_com(st) == esperado == DM.calcula_parado_com(st)
