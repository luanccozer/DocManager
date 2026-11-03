"""Upload → aprovação, Fase 1: conferências e busca no Aconex, sem gravar nada."""
from __future__ import annotations

import pandas as pd
import pytest

from builders import escrever_controle_xlsx
from docmanager.aconex_backend import ResultadoConsulta
from docmanager.services import upload_aprovacao as ua
from test_upload_envio import _xlsx

COD = "0000CMI-AA01-01"


@pytest.fixture
def arquivos(tmp_path):
    envio = _xlsx(tmp_path / "envio.xlsx")
    controle = escrever_controle_xlsx(tmp_path / "controle.xlsx", [
        {"itaipu": "#XX00=EXEMPLO&AAA010", "cmi": COD, "titulo": "DOC 1", "ultima": "0C"},
        {"itaipu": "#XX00=EXEMPLO&AAA020", "cmi": "0000CMI-AA02-01", "titulo": "DOC 2", "ultima": "0B"},
    ], incluir_ultima=True)
    return envio, controle


def _aconex(*linhas):
    """A busca no Aconex simulada: devolve as versões dadas."""
    chamadas = []

    def consultar(config, codigos, log_cb=None):
        chamadas.append(list(codigos))
        return ResultadoConsulta(pd.DataFrame(list(linhas)), total=len(codigos))

    consultar.chamadas = chamadas
    return consultar


VERSAO_0C = {"No. do Documento": "#XX00=EXEMPLO&AAA010", "Controle do Emissor": COD,
             "Título": "LISTA EXEMPLO", "Revisão": "0C", "Status da Revisão": "Apto para Firma",
             "Versão": "3", "Current": "true"}
VERSAO_0B = dict(VERSAO_0C, Revisão="0B", Versão="2", Current="false",
                 **{"Status da Revisão": "Aprovado com Comentários"})


def _preparar(arquivos, codigo=COD, prazo=10, perguntar=None, consultar=None):
    envio, controle = arquivos
    logs = []
    r = ua.preparar_aprovacao(None, envio, controle, codigo, prazo, log_cb=logs.append,
                              perguntar_cb=perguntar, consultar=consultar or _aconex(VERSAO_0B, VERSAO_0C))
    r.logs = logs
    return r


def test_tudo_certo_mostra_o_resumo_sem_gravar(arquivos):
    r = _preparar(arquivos)
    assert r.ok, r.mensagem
    assert r.envio.link == "https://exemplo.box.com/folder/111"
    assert r.ultima_revisao == "0C"
    assert r.documento["Revisão"] == "0C" and r.documento["Status da Revisão"] == "Apto para Firma"
    assert "revisão 0" in r.mensagem and "Para Aprovação" in r.mensagem and "10 dia(s)" in r.mensagem


def test_nao_esta_em_0c_pergunta_e_respeita_o_nao(arquivos):
    perguntas = []
    r = _preparar(arquivos, codigo="0000CMI-AA02-01",
                  perguntar=lambda m: perguntas.append(m) or False)
    assert not r.ok and "cancelado" in r.mensagem
    assert len(perguntas) == 1 and "'0B'" in perguntas[0]


def test_nao_esta_em_0c_e_a_pessoa_segue(arquivos):
    outra = dict(VERSAO_0C, **{"Controle do Emissor": "0000CMI-AA02-01"})
    r = _preparar(arquivos, codigo="0000CMI-AA02-01", perguntar=lambda m: True,
                  consultar=_aconex(outra))
    assert r.ok


def test_codigo_fora_do_arquivo_de_envio_nao_chega_ao_aconex(arquivos):
    consultar = _aconex(VERSAO_0C)
    r = _preparar(arquivos, codigo="NAO-EXISTE-01", consultar=consultar)
    assert not r.ok and "arquivo de envio" in r.mensagem
    assert consultar.chamadas == []


def test_documento_ausente_no_aconex(arquivos):
    r = _preparar(arquivos, consultar=_aconex())
    assert not r.ok and "não foi encontrado no Aconex" in r.mensagem


def test_dois_documentos_com_o_mesmo_controle_do_emissor_para(arquivos):
    outro = dict(VERSAO_0C, **{"No. do Documento": "#XX00=OUTRO&AAA011"})
    r = _preparar(arquivos, consultar=_aconex(VERSAO_0C, outro))
    assert not r.ok and "Mais de um documento" in r.mensagem


def test_prazo_e_codigo_obrigatorios(arquivos):
    assert "prazo" in _preparar(arquivos, prazo=0).mensagem
    assert "código" in _preparar(arquivos, codigo="  ").mensagem
