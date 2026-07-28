"""Exceções nominais por documento (KB §21.9).

Cada teste aqui trava UM remendo: o desvio precisa valer para o documento
listado e para NENHUM outro. Se um destes testes quebrar porque a entrada foi
removida de `core/excecoes.py`, o remendo deixou de ser necessário — remova o
teste junto.
"""
from builders import HistoricoBuilder

from docmanager.core.excecoes import (
    DOCS_REPROVACAO_EM_REVISAO_NUMERICA,
    reprovacao_numerica_vale,
)
from docmanager.core.mapping import processar_documento
from docmanager.core.status_engine import calcular_status_real

# O documento da exceção: emitido direto na revisão '0' (sem passar pelas
# revisões-letra) e devolvido Não Aprovado — provável erro de publicação.
DOC_EXCECAO = "#ITA0=C01CCA10&EDE020"


def _historico(codigo, revisao="0", status="Não Aprovado"):
    return (HistoricoBuilder("T1", codigo, "CMI-1", "DOC EMITIDO EM REVISAO NUMERICA")
            .evento(revisao, 1, status, "10/03/2026", current=True)).build()


def test_documento_da_excecao_fica_nao_aprovado():
    df = _historico(DOC_EXCECAO)
    assert calcular_status_real(df, "0") == "Não Aprovado"


def test_documento_qualquer_com_o_mesmo_sintoma_continua_nao_emitido():
    """A regra geral não muda: reprovação em revisão numérica é ruído."""
    df = _historico("#OUTRO=DOC&QUALQUER01")
    assert calcular_status_real(df, "0") == "NÃO EMITIDO"


def test_excecao_casa_pelo_codigo_cmi_tambem():
    """A identidade real é o Tracking; o código muda ao longo da vida."""
    df = (HistoricoBuilder("T1", "#CODIGO-NOVO-QUALQUER", DOC_EXCECAO, "DOC")
          .evento("0", 1, "Não Aprovado", "10/03/2026", current=True)).build()
    assert calcular_status_real(df, "0") == "Não Aprovado"


def test_excecao_tolera_sujeira_de_excel_no_codigo():
    df = _historico(f"  {DOC_EXCECAO}\xa0")
    assert reprovacao_numerica_vale(df)


def test_excecao_nao_afeta_revisao_letra():
    """Revisão-letra já retornava reprovado direto — nada muda para ela."""
    for codigo in (DOC_EXCECAO, "#QUALQUER=OUTRO&DOC01"):
        df = _historico(codigo, revisao="0A")
        assert calcular_status_real(df, "0A") == "Não Aprovado"


def test_excecao_nao_afeta_aprovacao_do_mesmo_documento():
    """O desvio é só para a reprovação; aprovado segue aprovado."""
    df = _historico(DOC_EXCECAO, status="Aprovado")
    assert calcular_status_real(df, "0") == "Aprovado"


def test_pipeline_completo_marca_o_documento_como_emitido():
    """Efeito prático: o documento sai de NÃO EMITIDO e passa a contar."""
    r = processar_documento(_historico(DOC_EXCECAO), nivel="2", tag_etapa="")
    assert r.status_real == "Não Aprovado"
    assert r.emitido_nao_emitido == "EMITIDO"
    assert r.status_consolidado == "NÃO APROVADO"


def test_lista_de_excecoes_e_pequena_e_explicita():
    """Guarda-corpo: a lista é remendo, não regra. Crescer é sinal de que o
    motor precisa mudar, e não de que faltam exceções."""
    assert len(DOCS_REPROVACAO_EM_REVISAO_NUMERICA) <= 3
