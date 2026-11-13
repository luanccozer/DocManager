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


def test_retorno_mesma_revisao_mesmo_status_usa_primeira_data():
    # Caso do gerador diesel (#ST00=B01BDV10&ACC051): 2 'Aprovado' na mesma
    # revisão → vale a 1ª data (a 2ª é atualização de metadados; não pode gerar
    # atraso artificial). Sem o fix, o retorno seria 15/05 (75 d); com, 20/03 (19 d).
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "GERADOR DIESEL")
        .evento("0A", 1, "Em Processo", "01/09/2024")     # pós-corte → envio real
        .evento("0A", 2, "Aprovado", "20/09/2024")        # 1º veredito
        .evento("0A", 3, "Aprovado", "15/11/2024", current=True)  # metadados
    )
    wide = build_wide_table(gerar_dataset_dashboard(b))
    linha = wide[wide["Revisão"] == "0A"].iloc[0]
    assert pd.Timestamp(linha["Data Retorno"]) == pd.Timestamp("2024-09-20")
    assert str(linha["Status Retorno"]) == "Aprovado"
    assert pd.Timestamp(linha["Data Envio"]) == pd.Timestamp("2024-09-01")


def test_envio_no_mesmo_dia_depois_do_retorno_e_ultimo_evento_fica_em_aberto():
    # 'Para Informação' e, no MESMO dia, 'Em Processo' (versões 1 e 2): o retorno veio
    # antes do envio. Pela data sozinha o ciclo fechava com 0 dias e o documento sumia
    # do "em análise"; a versão desempata e, como o envio é o último evento do
    # documento, a revisão fica em aberto (relançamento, KB §24.6). Caso real de
    # 2026-11 (2 documentos do Doc List da UG).
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0", 1, "Para Informação", "30/10/2026")
        .evento("0", 2, "Em Processo", "30/10/2026", current=True)
    )
    linha = build_wide_table(gerar_dataset_dashboard(b)).iloc[0]
    assert pd.Timestamp(linha["Data Envio"]) == pd.Timestamp("2026-10-30")
    assert pd.isna(linha["Data Retorno"])


def test_retorno_no_mesmo_dia_depois_do_envio_fecha_o_ciclo():
    # A ordem normal no mesmo dia (envio e depois veredito) continua fechando o ciclo.
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0", 1, "Em Processo", "30/10/2026")
        .evento("0", 2, "Para Informação", "30/10/2026", current=True)
    )
    linha = build_wide_table(gerar_dataset_dashboard(b)).iloc[0]
    assert pd.Timestamp(linha["Data Envio"]) == pd.Timestamp("2026-10-30")
    assert pd.Timestamp(linha["Data Retorno"]) == pd.Timestamp("2026-10-30")
    assert str(linha["Status Retorno"]) == "Para Informação"


def test_envio_no_mesmo_dia_depois_do_retorno_que_nao_e_o_ultimo_evento_nao_abre_ciclo():
    # Envio no mesmo dia, depois do veredito, mas seguido de outro veredito: não é
    # relançamento, e o ciclo continua fechado como antes.
    b = base(
        HistoricoBuilder("T1", "IT-1", "CMI-1", "DOC")
        .evento("0", 1, "Aprovado", "10/10/2026")
        .evento("0", 2, "Em Processo", "10/10/2026")
        .evento("0", 3, "Aprovado", "12/10/2026", current=True)
    )
    linha = build_wide_table(gerar_dataset_dashboard(b)).iloc[0]
    assert pd.Timestamp(linha["Data Envio"]) == pd.Timestamp("2026-10-10")
    assert str(linha["Status Retorno"]) == "Aprovado"


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
