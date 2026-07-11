import pandas as pd
from builders import HistoricoBuilder, base

from docmanager.core.identity import (
    AconexIndex,
    construir_indice_reverso,
    obter_codigos_historicos,
)

# Oráculo: o backend legado importa sem UI (só pandas/numpy/openpyxl/xml/re).
from legacy.data_manager import DataManager


def _base_multi():
    a = (HistoricoBuilder("TID-A", "IT-100", "CMI-100", "DOC A")
         .evento("0A", 1, "Em Processo", "01/03/2024", current=False)
         .evento("0A", 2, "Aprovado", "10/03/2024", current=True))
    b = (HistoricoBuilder("TID-B", "IT-200", "CMI-200", "DOC B")
         .evento("0A", 1, "Em Processo", "05/03/2024", current=True))
    return base(a, b)


def test_cascata_ouro_prata_bronze():
    idx = AconexIndex(_base_multi())
    # Ouro: itaipu + cmi
    assert set(idx.localizar("IT-100", "CMI-100")["Tracking ID"]) == {"TID-A"}
    # Prata: só cmi
    assert set(idx.localizar("", "CMI-200")["Tracking ID"]) == {"TID-B"}
    # Bronze: só itaipu
    assert set(idx.localizar("IT-100", "")["Tracking ID"]) == {"TID-A"}
    # Não encontrado
    assert idx.localizar("XXXX", "YYYY").empty


def test_desempate_por_data_mais_recente():
    # Mesmo código Itaipu em dois trackings distintos → vence a data mais nova.
    a = HistoricoBuilder("TID-OLD", "IT-DUP", "CMI-OLD").evento("0A", 1, "Em Processo", "01/01/2024", current=True)
    b = HistoricoBuilder("TID-NEW", "IT-DUP", "CMI-NEW").evento("0A", 1, "Em Processo", "01/06/2024", current=True)
    idx = AconexIndex(base(a, b))
    assert set(idx.localizar("IT-DUP", "")["Tracking ID"]) == {"TID-NEW"}


def test_indice_reverso_pega_codigos_antigos_e_normaliza():
    # Documento trocou de código Itaipu entre revisões.
    d = (HistoricoBuilder("TID-Z", "IT-VELHO", "CMI-Z")
         .evento("0A", 1, "Em Processo", "01/02/2024", doc="IT-VELHO")
         .evento("0B", 1, "Em Processo", "01/04/2024", doc="IT-NOVO", current=True))
    rev = construir_indice_reverso(base(d))
    # Ambos os códigos Itaipu e o CMI apontam para o mesmo Tracking
    assert rev["IT-VELHO"] == "TID-Z"
    assert rev["IT-NOVO"] == "TID-Z"
    assert rev["CMI-Z"] == "TID-Z"


def test_indice_reverso_remove_ponto_zero_fantasma():
    d = HistoricoBuilder("TID-N", "12345.0", "999.0").evento("0A", 1, "Em Processo", "01/02/2024", current=True)
    rev = construir_indice_reverso(base(d))
    assert rev.get("12345") == "TID-N"
    assert rev.get("999") == "TID-N"


def test_obter_codigos_historicos():
    d = (HistoricoBuilder("TID-Z", "IT-VELHO", "CMI-Z")
         .evento("0A", 1, "Em Processo", "01/02/2024", doc="IT-VELHO")
         .evento("0B", 1, "Em Processo", "01/04/2024", doc="IT-NOVO", cmi="CMI-Z2"))
    cods = set(obter_codigos_historicos(base(d)))
    assert cods == {"IT-VELHO", "IT-NOVO", "CMI-Z", "CMI-Z2"}


# ---------------------------------------------------------------------------
# Diferencial vs legado: AconexIndex.localizar ≡ DataManager.localiza_doc_historico
# ---------------------------------------------------------------------------
def _localiza_legado(df, it, cmi):
    dm = DataManager()
    dm.df_aconex = df
    return dm.localiza_doc_historico(it, cmi)


import pytest


@pytest.mark.parametrize("it,cmi", [
    ("IT-100", "CMI-100"),   # ouro
    ("", "CMI-200"),         # prata
    ("IT-100", ""),          # bronze
    ("IT-200", "CMI-100"),   # itaipu de B, cmi de A → prata vence (CMI-100 = A)
    ("XXXX", "YYYY"),        # nada
])
def test_diferencial_localizar_vs_legado(it, cmi):
    df = _base_multi()
    novo = AconexIndex(df).localizar(it, cmi).reset_index(drop=True)
    legado = _localiza_legado(df, it, cmi).reset_index(drop=True)
    if legado.empty:
        assert novo.empty
    else:
        assert list(novo["Tracking ID"]) == list(legado["Tracking ID"])
        pd.testing.assert_frame_equal(novo[legado.columns], legado)
