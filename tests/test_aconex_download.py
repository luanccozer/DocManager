"""Download por lista: COM os comentários (o de sempre) ou o ORIGINAL.

Melhoria trazida do Corella Suite (`tests/core/test_aconex_sem_comentarios.py`
de lá, validado em produção na v1.4.1). No modo original, duas causas de
comentário saem - a versão escolhida (a que voltou "Aprovado com Comentários"
é a vigente; a "Em Processo" fica no histórico) e o endpoint (`/markedup`
aplica as marcações do Aconex). No modo marcado, nada muda.
"""
from __future__ import annotations

import pytest

from docmanager import aconex_backend as ab
from docmanager.aconex_backend import (
    MODO_MARCADO,
    MODO_ORIGINAL,
    VersaoAconex,
    escolher_versao_sem_comentarios,
    parse_versoes,
)


def _v(did, versao, status, revisao="0A", corrente=False, tracking="T1", filename="doc.pdf"):
    return VersaoAconex(document_id=did, filename=filename, revisao=revisao, versao=versao,
                        status=status, tracking_id=tracking, corrente=corrente)


# --------------------------------------------------------------- a escolha
def test_caso_real_baixa_a_41_em_processo():
    """Exemplo de produção do Corella: versão 41 "Em processo" (a do emitente)
    e 43 "Aprovado com Comentários" (a vigente)."""
    versoes = [_v("D41", 41, "Em processo"), _v("D43", 43, "Aprovado com Comentários", corrente=True)]
    escolhida, aviso = escolher_versao_sem_comentarios(versoes)
    assert escolhida.document_id == "D41"
    assert "43" in aviso and "41" in aviso


def test_sem_versao_comentada_baixa_a_vigente_sem_aviso():
    versoes = [_v("D1", 1, "Em processo"), _v("D2", 2, "Aprovado", corrente=True)]
    assert escolher_versao_sem_comentarios(versoes) == (versoes[1], "")


def test_a_revisao_nunca_recua():
    versoes = [_v("D1", 1, "Em processo", revisao="0A"),
               _v("D2", 2, "Aprovado com Comentários", revisao="0B", corrente=True)]
    escolhida, aviso = escolher_versao_sem_comentarios(versoes)
    assert escolhida.document_id == "D2"
    assert "só tem versão com comentários" in aviso


def test_outro_documento_na_busca_nao_entra():
    versoes = [_v("X9", 50, "Em processo", tracking="OUTRO"),
               _v("D43", 43, "Aprovado com Comentários", corrente=True)]
    assert escolher_versao_sem_comentarios(versoes)[0].document_id == "D43"


def test_versao_sem_arquivo_nao_e_escolhida():
    versoes = [_v("D42", 42, "Em processo", filename=""), _v("D41", 41, "Em processo"),
               _v("D43", 43, "Aprovado com Comentários", corrente=True)]
    assert escolher_versao_sem_comentarios(versoes)[0].document_id == "D41"


@pytest.mark.parametrize("status", ["Aprovado com Comentários", "APROVADO COM COMENTARIOS",
                                    "Approved with comments"])
def test_status_com_comentarios_em_qualquer_grafia(status):
    assert _v("D", 1, status).tem_comentarios


def test_status_da_revisao_tambem_conta():
    v = _v("D", 1, "")
    v.status_revisao = "Aprovado com comentários"
    assert v.tem_comentarios


def test_lista_vazia():
    assert escolher_versao_sem_comentarios([]) == (None, "")


XML = """<?xml version="1.0" encoding="UTF-8"?>
<RegisterSearch><SearchResults>
  <Document DocumentId="D41">
    <Current>false</Current><DocumentStatus>Em processo</DocumentStatus>
    <Filename>EGVP.pdf</Filename><Revision>0A</Revision>
    <TrackingId>T1</TrackingId><VersionNumber>41</VersionNumber>
  </Document>
  <Document DocumentId="D43">
    <Current>true</Current><DocumentStatus>Aprovado com Comentários</DocumentStatus>
    <Filename>EGVP.pdf</Filename><Revision>0A</Revision>
    <TrackingId>T1</TrackingId><VersionNumber>43</VersionNumber>
  </Document>
</SearchResults></RegisterSearch>""".encode("utf-8")


def test_parse_le_versao_status_e_vigente():
    versoes = parse_versoes(XML)
    assert [(v.document_id, v.versao, v.corrente) for v in versoes] == [("D41", 41, False), ("D43", 43, True)]
    assert versoes[1].status == "Aprovado com Comentários"


# --------------------------------------------------------------- o download
class _Resposta:
    def __init__(self, status, conteudo):
        self.status_code, self.content, self.text = status, conteudo, ""


class _Sessao:
    def __init__(self):
        self.pedidos = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.pedidos.append((url, params))
        if params is not None:
            return _Resposta(200, XML)
        return _Resposta(200, b"%PDF-1.7 conteudo")


@pytest.fixture
def sessao(monkeypatch):
    s = _Sessao()
    monkeypatch.setattr(ab, "_estabelecer_sessao", lambda cfg, log=None: (s, "tok"))
    monkeypatch.setattr(ab, "_injetar_certificados", lambda log=None: None)
    return s


CFG = ab.AconexConfig(client_id="c", client_secret="s", user_id="1",
                      project_id="1", instance="https://aconex")
BASE = "https://aconex/api/projects/1/register"


def _arquivos(sessao):
    return [u for u, p in sessao.pedidos if p is None]


def test_original_baixa_a_versao_limpa_sem_markedup(sessao, tmp_path):
    res = ab.baixar_documentos(CFG, ["EGVP00519/CF-5R-LC-8006"], tmp_path, modo=MODO_ORIGINAL,
                               log_cb=lambda *_: None)
    assert res.baixados == 1
    assert _arquivos(sessao) == [f"{BASE}/D41"]
    assert res.versoes["EGVP00519/CF-5R-LC-8006"].versao == 41
    assert (tmp_path / "EGVP.pdf").read_bytes() == b"%PDF-1.7 conteudo"


def test_original_pede_o_historico_com_aspas(sessao, tmp_path):
    ab.baixar_documentos(CFG, ["#ST60=B01"], tmp_path, modo=MODO_ORIGINAL, log_cb=lambda *_: None)
    params = [p for _, p in sessao.pedidos if p is not None][0]
    assert params["search_query"] == '"#ST60=B01"'
    assert params["show_document_history"] == "true"
    assert "statusid" in params["return_fields"] and "trackingId" in params["return_fields"]


def test_marcado_continua_como_sempre(sessao, tmp_path):
    """O padrão não mudou: a vigente, pelo /markedup."""
    res = ab.baixar_documentos(CFG, ["#A"], tmp_path, log_cb=lambda *_: None)
    assert res.baixados == 1
    assert _arquivos(sessao) == [f"{BASE}/D43/markedup"]
    assert MODO_MARCADO == "marcado"


def test_xml_no_lugar_do_arquivo_e_erro_e_nao_vira_pdf(sessao, tmp_path, monkeypatch):
    original = sessao.get

    def get(url, headers=None, params=None, timeout=None):
        if params is None:
            return _Resposta(200, b"<?xml version='1.0'?><Error/>")
        return original(url, headers=headers, params=params, timeout=timeout)

    monkeypatch.setattr(sessao, "get", get)
    res = ab.baixar_documentos(CFG, ["#A"], tmp_path, modo=MODO_ORIGINAL, log_cb=lambda *_: None)
    assert res.baixados == 0
    assert res.erros and "XML" in res.erros[0][1]
    assert not any(tmp_path.iterdir())
