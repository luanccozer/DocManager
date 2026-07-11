"""Dataset + wide: diferencial vs legado (fora da borda) e correção da borda 19/08."""
import pandas as pd
from builders import HistoricoBuilder, base

from docmanager.core.wide import build_wide_table, gerar_dataset_dashboard
from legacy.data_manager import DataManager

DM = DataManager()


def _base_ciclo_completo():
    # Doc com 0A (envio+retorno) e 0B (envio), datas longe do corte.
    d = (HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC 1")
         .evento("0A", 1, "Em Processo", "01/03/2024", current=False)
         .evento("0A", 2, "Aprovado com Comentários", "20/03/2024")
         .evento("0B", 1, "Em Processo", "10/04/2024", current=True))
    d2 = (HistoricoBuilder("T2", "IT-2", "CMI-2", "DOC 2")
          .evento("0A", 1, "Em Processo", "05/02/2024")
          .evento("0A", 2, "Não Aprovado", "01/03/2024", current=True))
    return base(d, d2)


def test_dataset_diferencial_fora_da_borda():
    b = _base_ciclo_completo()
    novo = gerar_dataset_dashboard(b).reset_index(drop=True)
    legado = DM.gerar_dataset_dashboard(b).reset_index(drop=True)
    # check_dtype=False: no pandas 3 o backfill mantém o novo 'str' dtype (PDEP-14)
    # enquanto o legado rebaixa metadados para 'object'. Valores idênticos.
    pd.testing.assert_frame_equal(novo[legado.columns], legado, check_dtype=False)


def test_wide_diferencial_fora_da_borda():
    df_limpo = gerar_dataset_dashboard(_base_ciclo_completo())
    novo = build_wide_table(df_limpo)
    legado = DM.preparar_tabela_wide(df_limpo)
    # Mesmas linhas (Tracking, Revisão) e mesmo SLA; compara ordenado.
    chave = ["Tracking ID", "Revisão"]
    n = novo.sort_values(chave).reset_index(drop=True)
    g = legado.sort_values(chave).reset_index(drop=True)
    assert list(n["SLA_Itaipu"]) == list(g["SLA_Itaipu"])
    for col in ["Data Envio", "Data Retorno", "Status Envio", "Status Retorno"]:
        assert n[col].fillna("").astype(str).tolist() == g[col].fillna("").astype(str).tolist()


def test_borda_19_08_em_processo_e_regime_novo():
    # 'Em Processo' em 19/08 é ENVIO REAL no regime novo (não vira 'Em Processo (CMI)').
    b = base(HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Em Processo", "19/08/2024", current=True))
    novo = gerar_dataset_dashboard(b)
    legado = DM.gerar_dataset_dashboard(b)
    assert novo.iloc[0]["Status"] == "Em Processo"   # corrigido: 19/08 é regime novo (§21.3)
    # No legado, 19/08 caía como regime antigo → virava 'Em Processo (CMI)', que
    # não é envio nem retorno → o documento SUMIA do dataset (bug da borda).
    assert legado.empty


def test_borda_19_08_para_analise_e_fantasma_no_regime_novo():
    # 'Para Análise' em 19/08 é fantasma no regime novo → linha some do dataset.
    b = base(HistoricoBuilder("T", "IT", "CMI").evento("0A", 1, "Para Análise", "19/08/2024", current=True))
    novo = gerar_dataset_dashboard(b)
    assert novo.empty  # exterminada como lixo do futuro


def test_backfill_metadados_por_tracking():
    # Especialidade só preenchida numa revisão → propaga para todas do Tracking.
    d = HistoricoBuilder("T", "IT", "CMI", "DOC")
    d.evento("0A", 1, "Em Processo", "01/09/2024", current=True)
    d._eventos[0]["Especialidade"] = ""  # vazia na 0A
    d.evento("0B", 1, "Em Processo", "01/10/2024")
    d._eventos[1]["Especialidade"] = "ELÉTRICA"
    ds = gerar_dataset_dashboard(base(d))
    assert set(ds["Especialidade"]) == {"ELÉTRICA"}


def test_em_processo_cmi_nao_e_retorno():
    # Em Processo antigo (< corte) vira 'Em Processo (CMI)' e NÃO conta como retorno.
    b = base(HistoricoBuilder("T", "IT", "CMI")
             .evento("0A", 1, "Em Processo", "01/06/2024")  # < corte → Em Processo (CMI)
             .evento("0A", 2, "Aprovado", "01/09/2024", current=True))
    wide = build_wide_table(gerar_dataset_dashboard(b))
    linha = wide[wide["Revisão"] == "0A"].iloc[0]
    # O retorno é o 'Aprovado', não o 'Em Processo (CMI)'
    assert linha["Status Retorno"] == "Aprovado"
