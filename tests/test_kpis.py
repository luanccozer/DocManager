"""KPIs: diferencial vs legado (campos independentes de data) + atrasos com hoje fixo."""
from datetime import date

from builders import HistoricoBuilder

from docmanager.core.kpis import analisar_kpis_documento, calcular_atrasos_acumulados
from legacy.data_manager import DataManager

DM = DataManager()
HOJE = date(2024, 12, 31)


def _doc_multi_ciclo():
    return (HistoricoBuilder("T", "IT", "CMI")
            .evento("0A", 1, "Em Processo", "01/03/2024")
            .evento("0A", 2, "Não Aprovado", "20/03/2024")
            .evento("0B", 1, "Em Processo", "01/04/2024")
            .evento("0B", 2, "Aprovado", "20/04/2024", current=True)).build()


def test_kpis_diferencial_campos_independentes_de_data():
    df = _doc_multi_ciclo()
    novo = analisar_kpis_documento(df, "Aprovado", "0B", None, hoje=HOJE)
    legado = DM.analisar_kpis_documento(df, "Aprovado", "0B", None)
    for campo in ("total_ciclos", "ciclos_aprovar", "downgrade"):
        assert novo[campo] == legado[campo], campo


def test_downgrade_detecta_reprovacao_apos_aprovacao():
    df = (HistoricoBuilder("T", "IT", "CMI")
          .evento("0A", 1, "Aprovado", "01/03/2024")
          .evento("0A", 2, "Não Aprovado", "20/03/2024", current=True)).build()
    assert analisar_kpis_documento(df, "Não Aprovado", "0A", None, hoje=HOJE)["downgrade"] == "SIM"


def test_nao_emitido_com_data_prevista_vencida():
    r = analisar_kpis_documento(HistoricoBuilder("T", "IT", "CMI").build(),
                                "NÃO EMITIDO", "", "01/06/2024", hoje=HOJE)
    assert r["situacao_prazo"] == "Atrasado"
    assert r["dias_atraso"] == 213  # 01/06 → 31/12


def test_em_processo_sla_0a_30_dias():
    # 0A enviada 01/12, hoje 31/12 → 30 dias no status; SLA 30 → atraso 0 (no prazo).
    df = HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Em Processo", "01/12/2024", current=True).build()
    r = analisar_kpis_documento(df, "Em Processo", "0A", None, hoje=HOJE)
    assert r["dias_status"] == 30
    assert r["situacao_prazo"] == "No Prazo"


def test_atrasos_acumulados_diferencial_estrutura():
    # Compara com o legado apenas a existência das chaves e não-negatividade
    # (o legado usa now() interno; validamos a lógica com hoje fixo aqui).
    r = calcular_atrasos_acumulados(_doc_multi_ciclo(), "Aprovado", None, hoje=HOJE)
    assert set(r) == {"atraso_acumulado_itaipu", "atraso_acumulado_cmi"}
    assert r["atraso_acumulado_itaipu"] >= 0 and r["atraso_acumulado_cmi"] >= 0


def test_atraso_itaipu_estoura_sla():
    # 0A: envio 01/03, veredito 30/04 (60 dias) → atraso 60-30 = 30.
    df = (HistoricoBuilder("T", "IT", "CMI")
          .evento("0A", 1, "Em Processo", "01/03/2024")
          .evento("0A", 2, "Aprovado", "30/04/2024", current=True)).build()
    r = calcular_atrasos_acumulados(df, "Aprovado", None, hoje=HOJE)
    assert r["atraso_acumulado_itaipu"] == 30
