"""Motor de modelos BIM: milestone lock + diferencial vs legado."""
import pytest
from builders import HistoricoBuilder

from docmanager.core.status_model_bim import calcular_status_real_modelo
from legacy.data_manager import DataManager

DM = DataManager()


def _mod(builder, rev):
    return calcular_status_real_modelo(builder.build(), rev)


def test_sem_status_valido_nao_emitido():
    b = HistoricoBuilder("T", "IT", "CMI", tipo="Modelo").evento("0A", 1, "Em Integração", "01/03/2024", current=True)
    assert _mod(b, "0A") == "NÃO EMITIDO"


def test_milestone_lock_congela_aprovacao_da_fase():
    # Aprovado LOD 350 no passado, depois regrediu para revisão de modelo → trava aprovado.
    b = (HistoricoBuilder("T", "IT", "CMI", tipo="Modelo")
         .evento("0A", 1, "S3 - LOD 350 - Aprovado", "01/03/2024")
         .evento("0B", 1, "S3 - LOD 350 - Revisão de Modelo", "05/04/2024", current=True))
    assert _mod(b, "0B") == "Aprovado - LOD 350"


def test_status_final_mapeado_sem_lock():
    b = HistoricoBuilder("T", "IT", "CMI", tipo="Modelo").evento("0A", 1, "S1 - LOD 300 - Revisão de Modelo", "01/03/2024", current=True)
    assert _mod(b, "0A") == "Em Análise - LOD 300"


def _cenarios():
    return [
        (HistoricoBuilder("T", "IT", "CMI", tipo="Modelo").evento("0A", 1, "P0 - Emissão Inicial", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI", tipo="Modelo").evento("0A", 1, "S3 - LOD 350 - Não Aprovado", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI", tipo="Modelo")
         .evento("0A", 1, "S1 - LOD 300 - Finalizado", "01/03/2024")
         .evento("0B", 1, "S1 - LOD 300 - Com Incidentes", "05/04/2024", current=True), "0B"),
        (HistoricoBuilder("T", "IT", "CMI", tipo="Modelo").evento("0A", 1, "Para Informação", "01/03/2024", current=True), "0A"),
        (HistoricoBuilder("T", "IT", "CMI", tipo="Modelo").evento("0A", 1, "Em Integração", "01/03/2024", current=True), "0A"),
    ]


@pytest.mark.parametrize("builder,rev", _cenarios())
def test_diferencial_modelo_vs_legado(builder, rev):
    df = builder.build()
    assert calcular_status_real_modelo(df, rev) == DM.calcular_status_real_modelo(df, rev)
