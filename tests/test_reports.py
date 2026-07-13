"""Relatórios: avanço, integração (diferencial vs legado) e status docs."""
import pandas as pd
from builders import HistoricoBuilder, base

from docmanager.core.reports.avanco import gerar_relatorio_avanco
from docmanager.core.reports.integracao import auditar_fluxo_integracao
from docmanager.core.reports.status_docs import analisar_status_documentos
from legacy.data_manager import DataManager

DM = DataManager()


def _base_avanco():
    return base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "PLANO DE EXECUÇÃO X")
        .evento("0A", 1, "Em Processo", "01/09/2024", current=True),
        HistoricoBuilder("T2", "IT-2", "CMI-2", "DOC TECNICO")
        .evento("0A", 1, "Em Processo", "01/03/2024")
        .evento("0A", 2, "Aprovado", "20/03/2024", current=True),
        HistoricoBuilder("T3", "RDI-9", "CMI-3", "LIXO RDI")
        .evento("0A", 1, "Em Processo", "01/03/2024", current=True),
    )


def test_avanco_diferencial_vs_legado(tmp_path):
    b = _base_avanco()
    p = tmp_path / "base.xlsx"
    b.to_excel(p, index=False)
    ok_n, dn = gerar_relatorio_avanco(b.copy())
    ok_l, dl = DM.gerar_relatorio_avanco(str(p), 0)
    assert ok_n and ok_l
    a = dn.reset_index(drop=True).fillna("").astype(str)
    c = dl.reset_index(drop=True).fillna("").astype(str)
    assert list(a.columns) == list(c.columns)
    assert (a.values == c.values).all()


def test_integracao_diferencial_vs_legado():
    b = base(
        HistoricoBuilder("T1", "IT-BD010-1", "CMI-1", "DOC COM DCC")
        .evento("0AA", 1, "Em Processo", "01/02/2024")
        .evento("0A", 1, "Em Processo", "01/03/2024", current=True),
        HistoricoBuilder("T2", "IT-BD011-2", "CMI-2", "DOC SEM 0AA")
        .evento("0A", 1, "Em Processo", "01/03/2024", current=True),
    )
    n = auditar_fluxo_integracao(b.copy()).reset_index(drop=True).astype(str)
    leg = DM.auditar_fluxo_integracao(b.copy()).reset_index(drop=True).astype(str)
    assert list(n.columns) == list(leg.columns)
    assert (n.values == leg.values).all()
    # o doc com 0AA está integrado, o outro não
    integ = dict(zip(n["No. do Documento"], n["Integração"]))
    assert integ["IT-BD010-1"] == "SIM" and integ["IT-BD011-2"] == "NÃO"


def test_status_docs_resolve_lista():
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1")
        .evento("0A", 1, "Aprovado", "01/03/2024", current=True),
        HistoricoBuilder("T2", "IT-2", "CMI-2")
        .evento("0A", 1, "Em Processo", "01/03/2024", current=True),
    )
    r = analisar_status_documentos(b, ["IT-1", "IT-2", "IT-INEXISTENTE"], tipo_codigo="itaipu")
    por_cod = dict(zip(r["Código"], r["Status Real"]))
    assert por_cod["IT-1"] == "Aprovado"
    assert por_cod["IT-2"] == "Em Processo"
    assert por_cod["IT-INEXISTENTE"] == "NÃO EMITIDO"
