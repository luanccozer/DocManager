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


def test_cascata_preferir_itaipu_inverte_prata_bronze():
    idx = AconexIndex(_base_multi())
    # Itaipu e CMI apontam para documentos DIFERENTES (o CMI da lista está "errado").
    # Padrão (par → CMI → Itaipu): vence o CMI → TID-B.
    assert set(idx.localizar("IT-100", "CMI-200")["Tracking ID"]) == {"TID-B"}
    # preferir_itaipu (par → Itaipu → CMI): vence o Itaipu → TID-A (o certo, para
    # o Status Documentos: o CMI errado será sinalizado, não guia a busca).
    assert set(idx.localizar("IT-100", "CMI-200", preferir_itaipu=True)["Tracking ID"]) == {"TID-A"}
    # O par exato continua vencendo em ambos os modos.
    assert set(idx.localizar("IT-100", "CMI-100", preferir_itaipu=True)["Tracking ID"]) == {"TID-A"}


def _base_codigo_reaproveitado():
    """CMI-X é de A (que ainda o usa) mas B também o teve e mexeu DEPOIS.

    Miniatura do caso real (2026-09-04): '08934100BUA20-FS00FE-02' pertencia ao
    workstatement de B02BPA20, mas outro documento o carregou até 27/05/2025 e
    depois foi renomeado — como continuou tramitando, ganhava o desempate por data.
    """
    a = (HistoricoBuilder("TID-DONO", "IT-A", "CMI-X", "DOC CERTO")
         .evento("0A", 1, "Em Processo", "01/02/2024")
         .evento("0B", 1, "Aprovado com Comentários", "14/08/2024", current=True))
    b = (HistoricoBuilder("TID-EX", "IT-B-VELHO", "CMI-X", "DOC QUE ABANDONOU O CMI-X")
         .evento("0A", 1, "Em Processo", "27/05/2025")
         .evento("1A", 1, "Para Assinatura", "12/12/2025",
                 doc="IT-B-NOVO", cmi="CMI-Y", current=True))
    return base(a, b)


def test_preferir_vigente_evita_match_fantasma():
    idx = AconexIndex(_base_codigo_reaproveitado())
    # Padrão: vence a data mais recente ENTRE AS LINHAS DO MATCH — e a mais
    # recente com CMI-X é a de quem já abandonou o código (match fantasma).
    assert set(idx.localizar("", "CMI-X")["Tracking ID"]) == {"TID-EX"}
    # preferir_vigente: só casa, de início, com quem USA o CMI-X hoje.
    assert set(idx.localizar("", "CMI-X", preferir_vigente=True)["Tracking ID"]) == {"TID-DONO"}


def test_preferir_vigente_cai_no_historico_quando_ninguem_usa_o_codigo():
    """O 'código atualizado (azul)' sobrevive: buscar pelo código ANTIGO de um
    documento renomeado continua achando o documento (último recurso da cascata)."""
    idx = AconexIndex(_base_codigo_reaproveitado())
    for cod in ("IT-B-VELHO",):
        assert set(idx.localizar(cod, "", preferir_vigente=True)["Tracking ID"]) == {"TID-EX"}


def test_resolver_expoe_via_vigencia_e_candidatos():
    idx = AconexIndex(_base_codigo_reaproveitado())
    r = idx.resolver("", "CMI-X", preferir_vigente=True)
    assert (r.via, r.vigente, r.ambiguo) == ("cmi", True, False)
    assert r.candidatos == ("TID-DONO",)
    # Achado pelo código antigo → via itaipu, mas NÃO vigente.
    r = idx.resolver("IT-B-VELHO", "", preferir_vigente=True)
    assert (r.via, r.vigente) == ("itaipu", False)
    # Nada encontrado.
    r = idx.resolver("XXXX", "YYYY", preferir_vigente=True)
    assert r.df.empty and r.via == "" and not r.ambiguo


def test_resolver_marca_ambiguidade_de_codigo_compartilhado():
    # Dois documentos VIVOS com o mesmo CMI: a eleição é por data e é um chute.
    b = base(
        HistoricoBuilder("TID-1", "IT-1", "CMI-DUP", "DOC 1")
        .evento("0B", 1, "Aprovado", "14/08/2024", current=True),
        HistoricoBuilder("TID-2", "IT-2", "CMI-DUP", "DOC 2")
        .evento("0A", 1, "Em Processo", "19/12/2023", current=True),
    )
    r = AconexIndex(b).resolver("", "CMI-DUP", preferir_vigente=True)
    assert r.ambiguo and set(r.candidatos) == {"TID-1", "TID-2"}
    assert set(r.df["Tracking ID"]) == {"TID-1"}      # o mais recente vence


def test_conhece_codigo_distingue_inexistente_de_alheio():
    idx = AconexIndex(_base_codigo_reaproveitado())
    assert idx.conhece_codigo("CMI-X")            # vigente
    assert idx.conhece_codigo("cmi-y")            # normaliza (upper)
    assert idx.conhece_codigo("IT-B-VELHO")       # histórico também conta
    assert not idx.conhece_codigo("CMI-NUNCA-VISTO")
    assert not idx.conhece_codigo("")


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
