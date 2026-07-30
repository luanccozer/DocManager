"""Relatórios: avanço, integração (diferencial vs legado) e status docs."""
import pandas as pd
from builders import HistoricoBuilder, base

from docmanager.core.reports.avanco import gerar_relatorio_avanco
from docmanager.core.reports.integracao import auditar_fluxo_integracao
from docmanager.core.reports.status_docs import analisar_status_documentos, analisar_status_pares
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


# --------------------------------------------------------------------------
# Status Docs: destaque do código buscado vs. o documento resolvido (Tracking).
#   texto AZUL   = código mudou no sistema ('atualizado')
#   texto LARANJA = código não pertence ao doc achado ('nao_confere' → erro)
# --------------------------------------------------------------------------
def _base_troca_codigo():
    return base(
        # Itaipu trocou de IT-OLD (0A) para IT-NEW (0B, atual); CMI estável.
        HistoricoBuilder("T1", "IT-NEW", "CMI-1", "DOC QUE TROCOU ITAIPU")
        .evento("0A", 1, "Aprovado", "01/03/2024", doc="IT-OLD")
        .evento("0B", 1, "Em Processo", "01/06/2024", current=True),
        # CMI trocou de CMI-OLD (0A) para CMI-NEW (0B, atual); Itaipu estável.
        HistoricoBuilder("T2", "IT-2", "CMI-NEW", "DOC QUE TROCOU CMI")
        .evento("0A", 1, "Aprovado", "01/03/2024", cmi="CMI-OLD")
        .evento("0B", 1, "Em Processo", "01/06/2024", current=True),
    )


def _base_codigo_errado():
    return base(
        HistoricoBuilder("T3", "IT-3003", "CMI-3003", "DOC COM CMI CERTO")
        .evento("0A", 1, "Aprovado", "01/03/2024", current=True),
        HistoricoBuilder("T4", "IT-4004", "", "DOC SEM CMI NO SISTEMA")
        .evento("0A", 1, "Em Processo", "01/03/2024", current=True),
    )


def test_status_pares_marca_itaipu_atualizado():
    linhas, _, _ = analisar_status_pares(_base_troca_codigo(), [("IT-OLD", "")])
    d = linhas[0]
    assert d["Código Itaipu"] == "IT-NEW"     # mostra o vigente, não o buscado
    assert d["_itaipu_status"] == "atualizado"
    assert d["_cmi_status"] == ""             # CMI não foi buscado → não marca


def test_status_pares_marca_cmi_atualizado():
    linhas, _, _ = analisar_status_pares(_base_troca_codigo(), [("", "CMI-OLD")])
    d = linhas[0]
    assert d["Código CMI"] == "CMI-NEW"
    assert d["_cmi_status"] == "atualizado"
    assert d["_itaipu_status"] == ""


def test_status_pares_codigo_vigente_nao_marca():
    # Buscar já pelo código atual (mesmo com caixa diferente) não deve marcar.
    linhas, _, _ = analisar_status_pares(_base_troca_codigo(), [("it-new", "")])
    assert linhas[0]["_itaipu_status"] == ""


def test_status_pares_cmi_nao_confere_mostra_o_correto():
    # Itaipu certo acha o doc; CMI colado é erro (nunca pertenceu) → nao_confere.
    linhas, _, _ = analisar_status_pares(_base_codigo_errado(), [("IT-3003", "CMI-ERRADO-XYZ")])
    d = linhas[0]
    assert d["_itaipu_status"] == ""                 # Itaipu confere
    assert d["_cmi_status"] == "nao_confere"
    assert d["Código CMI"] == "CMI-3003"             # célula mostra o CORRETO
    assert d["_cmi_buscado"] == "CMI-ERRADO-XYZ"     # o errado vai para o comentário


def test_status_pares_cmi_nao_confere_sem_cmi_no_sistema():
    # Doc achado por Itaipu, mas não tem CMI no sistema; CMI colado é espúrio.
    linhas, _, _ = analisar_status_pares(_base_codigo_errado(), [("IT-4004", "CMI-FANTASMA")])
    d = linhas[0]
    assert d["_cmi_status"] == "nao_confere"
    assert d["_cmi_real"] == ""                      # sem código real → comentário "não possui"
    assert d["Código CMI"] == "CMI-FANTASMA"         # sem correto, mantém o buscado


def test_status_pares_itaipu_manda_quando_cmi_aponta_outro_doc():
    """Cenário do usuário: Itaipu certo, CMI (número interno) errado apontando
    para OUTRO documento. Com a prioridade Itaipu → CMI, acha o doc CERTO pelo
    Itaipu e sinaliza o CMI errado — em vez de ir ao documento errado pelo CMI."""
    b = base(
        HistoricoBuilder("TX", "IT-XX01", "CMI-XX01", "DOC ALVO")
        .evento("0A", 1, "Aprovado", "01/03/2024", current=True),
        HistoricoBuilder("TY", "IT-YY02", "CMI-YY02", "OUTRO DOC")
        .evento("0A", 1, "Em Processo", "01/03/2024", current=True),
    )
    linhas, _, _ = analisar_status_pares(b, [("IT-XX01", "CMI-YY02")])
    d = linhas[0]
    assert d["Título"] == "DOC ALVO"                 # achou o doc do Itaipu, não o do CMI
    assert d["_itaipu_status"] == ""                 # Itaipu confere
    assert d["_cmi_status"] == "nao_confere"         # CMI errado sinalizado
    assert d["Código CMI"] == "CMI-XX01"             # célula mostra o CMI correto do alvo
    assert d["_cmi_buscado"] == "CMI-YY02"           # o errado vai para o comentário


def test_status_pares_export_azul_e_comentario(tmp_path):
    import openpyxl

    from docmanager.services.excel_io import exportar_status_documentos
    b = pd.concat([_base_troca_codigo(), _base_codigo_errado()], ignore_index=True)
    linhas, contador, _ = analisar_status_pares(b, [("IT-OLD", ""), ("IT-3003", "CMI-ERRADO-XYZ")])
    saida = tmp_path / "status.xlsx"
    ok, _ = exportar_status_documentos(linhas, contador, str(saida))
    assert ok
    ws = openpyxl.load_workbook(saida)["Status Documentos"]
    # Linha 1 (IT-OLD→IT-NEW): Código Itaipu em AZUL, sem preenchimento (não bold).
    assert str(ws["A2"].font.color.rgb).endswith("0070C0")
    assert not ws["A2"].font.bold
    a2_fill = ws["A2"].fill.fgColor.rgb
    assert a2_fill is None or not str(a2_fill).endswith("0070C0")
    # Linha 2 (IT-3003 + CMI errado): célula com o código correto, SEM cor, + comentário.
    assert ws["B3"].value == "CMI-3003"
    b3_color = ws["B3"].font.color
    assert b3_color is None or not str(b3_color.rgb).endswith("0070C0")
    assert ws["B3"].comment is not None and "CMI-ERRADO-XYZ" in ws["B3"].comment.text
