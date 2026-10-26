"""Consulta rápida: o histórico de N códigos direto da API, sem a base completa.

Melhoria trazida do Corella Suite (`aconex_api.register.buscar`). A mini-base
sai no MESMO formato da extração, e o mesmo motor do Status Documentos dá o
status real - aqui sem rede, com uma sessão falsa.
"""
from __future__ import annotations

import pytest

from docmanager import aconex_backend as ab
from docmanager.status_backend import analisar_status_pares


def _doc(did, docno, cmi, rev, versao, status, data, current, tracking="T1"):
    return (f'<Document DocumentId="{did}"><DocumentNumber>{docno}</DocumentNumber>'
            f'<ControlDelEmisor_singleLineText>{cmi}</ControlDelEmisor_singleLineText>'
            f'<Revision>{rev}</Revision><VersionNumber>{versao}</VersionNumber>'
            f'<DocumentStatus>{status}</DocumentStatus><DateModified>{data}</DateModified>'
            f'<Current>{current}</Current><TrackingId>{tracking}</TrackingId>'
            f'<Title>Memorial</Title><DocumentType>Documento Técnico</DocumentType></Document>')


HISTORICO_IT1 = ("<RegisterSearch><SearchResults>"
                 + _doc("1", "IT-1", "CMI-1", "0A", 1, "Em Processo", "2025-03-01T10:00:00Z", "false")
                 + _doc("2", "IT-1", "CMI-1", "0A", 2, "Aprovado", "2025-03-20T10:00:00Z", "true")
                 + "</SearchResults></RegisterSearch>").encode("utf-8")
VAZIO = b"<RegisterSearch><SearchResults/></RegisterSearch>"


class _Resposta:
    def __init__(self, status, conteudo):
        self.status_code, self.content, self.text = status, conteudo, ""


class _Sessao:
    def __init__(self, por_codigo):
        self.por_codigo = por_codigo
        self.pedidos = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.pedidos.append(params)
        cod = params["search_query"].strip('"')
        return _Resposta(200, self.por_codigo.get(cod, VAZIO))


@pytest.fixture
def sessao(monkeypatch):
    s = _Sessao({"IT-1": HISTORICO_IT1, "CMI-1": HISTORICO_IT1})
    monkeypatch.setattr(ab, "_estabelecer_sessao", lambda cfg, log=None: (s, "tok"))
    monkeypatch.setattr(ab, "_injetar_certificados", lambda log=None: None)
    return s


CFG = ab.AconexConfig(client_id="c", client_secret="s", user_id="1", project_id="1",
                      instance="https://aconex")


def test_busca_exata_com_historico_e_os_campos_da_extracao(sessao):
    ab.consultar_codigos(CFG, ["IT-1"], log_cb=lambda *_: None)
    p = sessao.pedidos[0]
    assert p["search_query"] == '"IT-1"'
    assert p["show_document_history"] == "true"
    assert p["return_fields"] == CFG.campos


def test_mini_base_no_formato_da_extracao(sessao):
    r = ab.consultar_codigos(CFG, ["IT-1", "NADA"], log_cb=lambda *_: None)
    assert r.nao_encontrados == ["NADA"]
    assert list(r.base["Versão"]) == ["1", "2"]
    assert set(r.base["No. do Documento"]) == {"IT-1"}
    assert r.base.loc[1, "Data de Alteração"] == "20/03/2025"


def test_itaipu_e_cmi_do_mesmo_documento_nao_duplicam(sessao):
    r = ab.consultar_codigos(CFG, ["IT-1", "CMI-1", "IT-1"], log_cb=lambda *_: None)
    assert len(r.base) == 2
    assert len(sessao.pedidos) == 2            # o repetido não é consultado de novo


def test_o_motor_de_status_roda_sobre_a_mini_base(sessao):
    codigos = ["IT-1", "CMI-1", "NADA"]
    r = ab.consultar_codigos(CFG, codigos, log_cb=lambda *_: None)
    pares = ab.pares_da_consulta(r.base, codigos)
    assert pares == [("IT-1", ""), ("", "CMI-1"), ("", "NADA")]
    linhas, contador, _ = analisar_status_pares(r.base, pares)
    reais = [d["Status Real"] for d in linhas]
    assert reais[:2] == ["Aprovado", "Aprovado"]
    assert reais[2] == "NÃO EMITIDO"


def test_erro_num_codigo_nao_para_os_outros(monkeypatch, sessao):
    original = sessao.get

    def get(url, headers=None, params=None, timeout=None):
        if params["search_query"] == '"RUIM"':
            return _Resposta(500, b"")
        return original(url, headers=headers, params=params, timeout=timeout)

    monkeypatch.setattr(sessao, "get", get)
    r = ab.consultar_codigos(CFG, ["RUIM", "IT-1"], log_cb=lambda *_: None)
    assert r.erros and r.erros[0][0] == "RUIM"
    assert not r.base.empty
