"""A tabela de envio colada na tela (Upload → aprovação): vários documentos, com ou sem cabeçalho."""
from __future__ import annotations

from docmanager.services import upload_envio as ue

CABECALHO = ("IDENTIFICAÇÃO DOCUMENTO CMI\tIDENTIFICAÇÃO DOCUMENTO ITAIPU\tESPECIFICAÇÃO TÉCNICA "
             "(EQUIPAMENTO/SISTEMA)\tCAPÍTULO ESPECIFICAÇÃO TÉCNICA (EQUIPAMENTO/SISTEMA)\tDESCRIÇÃO\t"
             "TIPO DE DOCUMENTO\tSUBTIPO DE DOCUMENTO\tREVISÃO\tLINK GE BOX")
LINHA_1 = ("0000CMI-AA01-04\t#XX00=EXEMPLO&EPB021\tUNIDADE GERADORA\tSISTEMA EXEMPLO / CONTROLE\t"
           "PARTE DIGITAL\tDESENHO DE FABRICANTE\tLISTA DE SOBRESSALENTE COM PREÇO\t0C\t"
           "https://exemplo.box.com/s/aaa111")
LINHA_2 = ("0000CMI-AA01-03\t#XX00=EXEMPLO&MPB021\tUNIDADE GERADORA\tSISTEMA EXEMPLO\tPARTE MECÂNICA\t"
           "DESENHO DE FABRICANTE\tLISTA DE SOBRESSALENTE COM PREÇO\t0C\thttps://exemplo.box.com/s/bbb222")


def test_tabela_colada_como_veio_do_email():
    """Do jeito que a pessoa cola: cabeçalho, linhas em branco entre os documentos."""
    docs = ue.ler_tabela(f"{CABECALHO}\n{LINHA_1}\n\n{LINHA_2}\n\n\n")
    assert [d.cod_cmi for d in docs] == ["0000CMI-AA01-04", "0000CMI-AA01-03"]   # na ordem da tabela
    assert docs[0].cod_itaipu == "#XX00=EXEMPLO&EPB021" and docs[0].revisao == "0C"
    assert docs[1].link == "https://exemplo.box.com/s/bbb222"
    assert docs[1].descricao == "PARTE MECÂNICA"


def test_sem_cabecalho_vale_a_ordem_da_lista():
    docs = ue.ler_tabela(f"{LINHA_1}\r\n{LINHA_2}\r\n")
    assert [d.link for d in docs] == ["https://exemplo.box.com/s/aaa111", "https://exemplo.box.com/s/bbb222"]


def test_celula_com_quebra_de_linha_que_o_excel_poe_entre_aspas():
    linha = LINHA_1.replace("SISTEMA EXEMPLO / CONTROLE", '"SISTEMA EXEMPLO /\nCONTROLE"')
    docs = ue.ler_tabela(f"{CABECALHO}\n{linha}\n{LINHA_2}")
    assert len(docs) == 2 and docs[0].link == "https://exemplo.box.com/s/aaa111"


def test_texto_sem_tabela_nao_reconhece_nada():
    assert ue.ler_tabela("") == []
    assert ue.ler_tabela("Seguem documentos para envio via ACONEX análise de ITAIPU:") == []


def test_buscar_por_codigo():
    docs = ue.ler_tabela(f"{CABECALHO}\n{LINHA_1}\n{LINHA_2}")
    assert ue.buscar(docs, " 0000cmi-aa01-03 ").cod_itaipu == "#XX00=EXEMPLO&MPB021"
    assert ue.buscar(docs, "OUTRO") is None
