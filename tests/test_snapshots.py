"""Delta: obter_snapshot_status (máquina do tempo) por data de corte."""
import pandas as pd
from builders import HistoricoBuilder

from docmanager.core.snapshots import (
    _deduplicar_e_marcar_repetidos,
    obter_snapshot_status,
)


def _com_data(df):
    df = df.copy()
    df["Data_Obj"] = pd.to_datetime(df["Data de Alteração"], dayfirst=True, errors="coerce")
    return df


def test_snapshot_volta_no_tempo():
    df = _com_data(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Em Processo", "01/03/2024")
        .evento("0A", 2, "Aprovado", "20/04/2024", current=True)
        .build())
    # Antes do veredito: estava Em Processo
    _, real_antes, rev_antes, _ = obter_snapshot_status(df, pd.Timestamp("2024-03-15"))
    assert real_antes == "Em Processo" and rev_antes == "0A"
    # Depois: Aprovado
    _, real_depois, _, _ = obter_snapshot_status(df, pd.Timestamp("2024-05-01"))
    assert real_depois == "Aprovado"


def test_snapshot_antes_de_existir_e_nao_emitido():
    df = _com_data(HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Em Processo", "01/03/2024", current=True).build())
    _, real, rev, data = obter_snapshot_status(df, pd.Timestamp("2024-01-01"))
    assert real == "NÃO EMITIDO" and rev == "-" and pd.isna(data)


def test_snapshot_ignora_terminated_sem_renascimento():
    df = _com_data(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Aprovado", "01/03/2024")
        .evento("0B", 1, "Em Processo", "01/04/2024", terminated=True)
        .build())
    # No corte após a 0B terminada, a vigente volta a ser a 0A aprovada.
    _, real, rev, _ = obter_snapshot_status(df, pd.Timestamp("2024-05-01"))
    assert rev == "0A" and real == "Aprovado"


def test_delta_deduplica_repetido_no_grupo_e_marca_entre_grupos():
    # Mesmo documento listado 3x no nível do grupo (variando caixa/espaço) e um
    # documento presente em dois grupos distintos.
    arvore = {
        "GRUPO A": {"3": [
            {"doc": "DOC-1"}, {"doc": "doc-1"}, {"doc": "DOC-1 "},
            {"doc": "DOC-2"},
        ]},
        "GRUPO B": {"4": [
            {"doc": "DOC-2"}, {"doc": "DOC-3"},
        ]},
    }
    total = _deduplicar_e_marcar_repetidos(arvore)

    # Repetido no mesmo grupo → colapsa para 1; total = docs únicos por grupo/nível.
    docs_a = [it["doc"] for it in arvore["GRUPO A"]["3"]]
    assert docs_a == ["DOC-1", "DOC-2"]
    assert total == 4

    por_doc = {it["doc"].strip().upper(): it["repetido_grupos"]
               for lst in (arvore["GRUPO A"]["3"], arvore["GRUPO B"]["4"]) for it in lst}
    # DOC-2 aparece em A e B → marcado; os que ficam num grupo só, não.
    assert por_doc["DOC-2"] is True
    assert por_doc["DOC-1"] is False
    assert por_doc["DOC-3"] is False
