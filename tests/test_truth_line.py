from builders import HistoricoBuilder

from docmanager.core.truth_line import (
    limpar_terminated_por_limiar,
    resolver_linha_da_verdade,
)


def _tl(builder):
    return resolver_linha_da_verdade(builder.build())


def test_current_vivo_e_a_linha_dinamica():
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Em Processo", "01/03/2024")
        .evento("0A", 2, "Aprovado", "10/03/2024", current=True)
    )
    assert tl.linha_dinamica is not None
    assert tl.revisao_atual == "0A"
    assert str(tl.linha_dinamica["Status"]) == "Aprovado"
    assert not tl.nao_emitido


def test_terminated_ate_0a_regride_a_nao_emitido():
    # 0A terminada (sem reenvio) → cancelou a primeira emissão da vida útil.
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Em Processo", "01/03/2024", current=True, terminated=True)
    )
    assert tl.nao_emitido
    assert tl.linha_dinamica is None
    assert tl.df_para_calculo.empty


def test_terminated_maior_que_0a_cai_para_o_restante():
    # 0B (current) terminada, sem reenvio → vigente passa a ser a 0A.
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Aprovado", "01/03/2024")
        .evento("0B", 1, "Em Processo", "10/04/2024", current=True, terminated=True)
    )
    assert tl.linha_dinamica is not None
    assert tl.revisao_atual == "0A"
    assert str(tl.linha_dinamica["Status"]) == "Aprovado"


def test_renascimento_current_na_versao_renascida():
    # 0B terminada na v3, reenviada na MESMA 0B v5 (Current) → vigente = 0B v5.
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Aprovado", "01/03/2024")
        .evento("0B", 3, "Em Processo", "05/04/2024", terminated=True)
        .evento("0B", 5, "Em Processo", "20/04/2024", current=True)
    )
    assert tl.revisao_atual == "0B"
    assert int(float(tl.linha_dinamica["Versão"])) == 5
    # a versão terminada (v3) não sobrevive na base de cálculo
    versoes_0b = tl.df_para_calculo[tl.df_para_calculo["Revisão"] == "0B"]["Versão"].tolist()
    assert versoes_0b == ["5"]


def test_renascimento_current_na_versao_terminada():
    # Caso-chave da §21.8: o flag Current ficou preso na versão terminada (v3),
    # mas existe a v5 reenviada. O limiar deve reconhecer o renascimento e
    # apontar a 0B v5 como vigente — onde o legado cairia para a 0A.
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Aprovado", "01/03/2024")
        .evento("0B", 5, "Em Processo", "20/04/2024")
        .evento("0B", 3, "Em Processo", "05/04/2024", current=True, terminated=True)
    )
    assert tl.revisao_atual == "0B"
    assert int(float(tl.linha_dinamica["Versão"])) == 5


def test_terminateds_encadeados():
    # 0B e 0C ambas terminadas; vigente cai para 0A.
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Aprovado", "01/03/2024")
        .evento("0B", 1, "Em Processo", "05/04/2024", terminated=True)
        .evento("0C", 1, "Em Processo", "10/05/2024", current=True, terminated=True)
    )
    assert tl.revisao_atual == "0A"
    assert str(tl.linha_dinamica["Status"]) == "Aprovado"


def test_sem_current_usa_maior_versao():
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Em Processo", "01/03/2024")
        .evento("0A", 2, "Aprovado", "10/03/2024")
    )
    assert tl.linha_dinamica is not None
    assert int(float(tl.linha_dinamica["Versão"])) == 2


def test_ordenacao_versao_9_vs_10_numerica():
    # Ordenação de string quebraria (9 > 10); Versão_Int resolve.
    tl = _tl(
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 9, "Em Processo", "01/03/2024")
        .evento("0A", 10, "Aprovado", "10/03/2024", current=True)
    )
    assert int(float(tl.linha_dinamica["Versão"])) == 10


def test_limpar_terminated_idempotente():
    df = (
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Em Processo", "01/03/2024", terminated=True)
        .evento("0A", 2, "Aprovado", "10/03/2024", current=True)
    ).build()
    limpo1 = limpar_terminated_por_limiar(df)
    limpo2 = limpar_terminated_por_limiar(limpo1)
    assert list(limpo1["Versão"]) == ["2"]
    assert list(limpo2["Versão"]) == ["2"]


def test_legado_exclui_revisao_ignora_renascimento():
    # Current preso na 0B terminada + 0B v5 reenviada. Com o quirk legado, a 0B
    # some inteira e a vigente vira 0A — a divergência que a §21.8 corrige.
    df = (
        HistoricoBuilder("T", "IT", "CMI")
        .evento("0A", 1, "Aprovado", "01/03/2024")
        .evento("0B", 5, "Em Processo", "20/04/2024")
        .evento("0B", 3, "Em Processo", "05/04/2024", current=True, terminated=True)
    ).build()
    tl = resolver_linha_da_verdade(df, legado_exclui_revisao=True)
    assert tl.revisao_atual == "0A"
    assert "0B" not in tl.df_para_calculo["Revisão"].tolist()
