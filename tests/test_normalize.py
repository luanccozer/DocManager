from docmanager.core import normalize as nz


def test_normalizar_revisao_preenche_com_z():
    assert nz.normalizar_revisao("0A") == "0Az"
    assert nz.normalizar_revisao("0") == "0zz"
    assert nz.normalizar_revisao("1A") == "1Az"
    assert nz.normalizar_revisao("0AA") == "0AA"
    assert nz.normalizar_revisao("") == ""
    assert nz.normalizar_revisao(None) == ""


def test_ordem_lexicografica_do_ciclo_de_vida():
    # ciclo interno < revisão-letra < revisão definitiva, dentro da família
    seq = ["0AA", "0A", "0", "1A", "1"]
    norms = [nz.normalizar_revisao(r) for r in seq]
    assert norms == sorted(norms)


def test_remove_r_maiusculo():
    assert nz.normalizar_revisao("R0A") == "0Az"


def test_sort_key_tres_niveis():
    assert nz.sort_key_revisao("A") == "00_A"
    assert nz.sort_key_revisao("0A") == "10_0A"
    assert nz.sort_key_revisao("0") == "20_000"
    assert nz.sort_key_revisao("12") == "20_012"
    # letras < revisão-letra < numéricas
    assert nz.sort_key_revisao("A") < nz.sort_key_revisao("0A") < nz.sort_key_revisao("0")


def test_normalizar_codigo_remove_ponto_zero_fantasma():
    assert nz.normalizar_codigo("12345.0") == "12345"
    assert nz.normalizar_codigo(" abc-1 ") == "ABC-1"
    # código real com pontos NÃO é mutilado
    assert nz.normalizar_codigo("8501.20.15400.P") == "8501.20.15400.P"
    assert nz.normalizar_codigo(None) == ""
    assert nz.normalizar_codigo("nan") == ""


def test_remover_acentos():
    assert nz.remover_acentos("Comissão Ú") == "Comissao U"
    assert nz.remover_acentos(None) == ""


def test_normalizar_cabecalho_ignora_acento_caixa_e_quebra_de_linha():
    from docmanager.core.normalize import normalizar_cabecalho

    assert normalizar_cabecalho(" Clasificación de\npendencia ") == "CLASIFICACION DE PENDENCIA"
    assert normalizar_cabecalho("¿Pasó a\xa0comisionamiento?") == "¿PASO A COMISIONAMIENTO?"
