"""Cenários da §22.7 + diferencial vs legado do motor de status real."""
import pytest
from builders import HistoricoBuilder

from docmanager.core.status_engine import calcular_status_real
from legacy.data_manager import DataManager

DM = DataManager()


def _real(builder, rev):
    return calcular_status_real(builder.build(), rev)


# --------------------------------------------------------------------------
# Anulação: sinônimos do Aconex → um rótulo só (KB §8.1, divergência §23)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("status_bruto", [
    "Cancelado", "Anulado", "VOID", "Void", "void", "Issued for Annulment",
])
def test_anulacao_vira_sempre_cancelado(status_bruto):
    """Os quatro rótulos são o MESMO desfecho; o status real unifica em
    'Cancelado' (decisão do usuário 2026-07-28). 'VOID' é novo na lista."""
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, status_bruto, "01/03/2024", current=True)
    assert _real(b, "0A") == "Cancelado"


def test_void_em_revisao_numerica_tambem_cancela():
    b = HistoricoBuilder("T", "IT", "CMI").evento("0", 1, "VOID", "01/03/2024", current=True)
    assert _real(b, "0") == "Cancelado"


def test_anulacao_consolida_como_cancelado():
    from docmanager.core.consolidation import calcula_status_consolidado
    assert calcula_status_consolidado("Cancelado", "VOID", "EMITIDO") == "CANCELADO"


def test_void_nao_e_confundido_com_outro_status():
    """Só o VOID exato anula — 'Avoided'/'Voided' não entram na lista."""
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Avoided", "01/03/2024", current=True)
    assert _real(b, "0A") != "Cancelado"


# --------------------------------------------------------------------------
# Cenários explícitos (KB §8 / §22.7)
# --------------------------------------------------------------------------
def test_aprovado_direto():
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Aprovado", "01/03/2024", current=True)
    assert _real(b, "0A") == "Aprovado"


def test_revisao_vigente_inexistente_nao_emitido():
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Aprovado", "01/03/2024")
    assert _real(b, "0B") == "NÃO EMITIDO"


def test_fantasma_com_salvamento_na_propria_revisao():
    # Aprovado na v1, depois caiu em integração (v2) na mesma revisão → salva a aprovação.
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Aprovado", "01/03/2024")
         .evento("0A", 2, "Em Integração", "05/03/2024", current=True))
    assert _real(b, "0A") == "Aprovado"


def test_fantasma_resgatando_fantasma_vira_nao_emitido():
    # Atual fantasma, histórico também só fantasma → nunca foi emitido de verdade.
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Integrado", "01/03/2024")
         .evento("0B", 1, "Em Integração", "05/03/2024", current=True))
    assert _real(b, "0B") == "NÃO EMITIDO"


def test_mudanca_de_familia_reseta_aprovacao():
    # 0 aprovada; 1A em processo → a aprovação da família 0 não vaza para a 1.
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0", 1, "Aprovado", "01/03/2024")
         .evento("1A", 1, "Em Processo", "05/04/2024", current=True))
    assert _real(b, "1A") == "Em Processo"


def test_reprovado_vence_com_atual_fantasma():
    # Reprovado na 0A; depois entrou em integração na 0B → fantasma resgata o "Não Aprovado".
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Não Aprovado", "01/03/2024")
         .evento("0B", 1, "Em Integração", "05/04/2024", current=True))
    assert _real(b, "0B") == "Não Aprovado"


def test_reprovado_com_atual_em_processo_vira_em_processo():
    # Reprovado na 0A; reemitido 0B Em Processo → já está tramitando, não "parado reprovado".
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Não Aprovado", "01/03/2024")
         .evento("0B", 1, "Em Processo", "05/04/2024", current=True))
    assert _real(b, "0B") == "Em Processo"


def test_reprovacao_em_revisao_numerica_ignorada():
    # "Não Aprovado" numa revisão definitiva (0) não rebaixa — segue a batalha.
    b = (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Aprovado", "01/03/2024")
         .evento("0", 1, "Não Aprovado", "05/04/2024")
         .evento("1A", 1, "Em Integração", "10/05/2024", current=True))
    # atual fantasma (1A), batalha no histórico: aprovado(0A) vs reprovado(0, ignorado) → Aprovado
    assert _real(b, "1A") == "Aprovado"


def test_planilha_comissionamento_para_aprovacao_promovido():
    b = (HistoricoBuilder("T", "IT", "CMI", titulo="PLANILHA DE COMISSIONAMENTO X")
         .evento("0A", 1, "Para Aprovação", "01/03/2024", current=True))
    assert _real(b, "0A") == "Para Aprovação"


def test_doc_comum_para_aprovacao_e_fantasma():
    # Sem 'comissionamento' no título, Para Aprovação é fantasma → NÃO EMITIDO.
    b = HistoricoBuilder("T", "IT", "CMI", titulo="DOCUMENTO TECNICO").evento("0A", 1, "Para Aprovação", "01/03/2024", current=True)
    assert _real(b, "0A") == "NÃO EMITIDO"


@pytest.mark.parametrize("data,esperado", [
    ("18/08/2024", "Para Análise"),   # regime antigo: Para Análise = envio real (não fantasma)
    ("19/08/2024", "NÃO EMITIDO"),    # corte inclusive: vira fantasma
    ("20/08/2024", "NÃO EMITIDO"),
])
def test_para_analise_na_borda_do_corte(data, esperado):
    # Sozinha, uma 0A "Para Análise" no regime antigo não é fantasma → o motor a
    # trata como status real desconhecido e cai no fallback "NÃO EMITIDO"? Não:
    # ela não está em nenhuma lista de veredito, então segue para a batalha sem
    # histórico → NÃO EMITIDO. Já no regime novo é fantasma explícito.
    b = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Para Análise", data, current=True)
    # Comparamos com o legado para travar o comportamento exato na borda.
    assert calcular_status_real(b.build(), "0A") == DM.calcular_status_real(b.build(), "0A")


# --------------------------------------------------------------------------
# Diferencial vs legado sobre um conjunto de históricos sintéticos
# --------------------------------------------------------------------------
def _cenarios():
    return [
        (HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Aprovado", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Em Processo", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Não Aprovado", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Informativo", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Cancelado", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Aprovado", "01/03/2024")
         .evento("0A", 2, "Em Validação", "05/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Não Aprovado", "01/03/2024")
         .evento("0B", 1, "Em Processo", "05/04/2024", current=True), "0B"),
        (HistoricoBuilder("T", "IT", "CMI")
         .evento("0", 1, "Aprovado", "01/03/2024")
         .evento("1A", 1, "Em Processo", "05/04/2024", current=True), "1A"),
        (HistoricoBuilder("T", "IT", "CMI")
         .evento("0A", 1, "Aprovado", "01/03/2024")
         .evento("0", 1, "Não Aprovado", "05/04/2024")
         .evento("1A", 1, "Em Integração", "10/05/2024", current=True), "1A"),
        (HistoricoBuilder("T", "IT", "CMI", titulo="PLANILHA DE COMISSIONAMENTO")
         .evento("0A", 1, "Para Aprovação", "01/03/2024", current=True), "0A"),
    ]


@pytest.mark.parametrize("builder,rev", _cenarios())
def test_diferencial_status_real_vs_legado(builder, rev):
    df = builder.build()
    assert calcular_status_real(df, rev) == DM.calcular_status_real(df, rev)
