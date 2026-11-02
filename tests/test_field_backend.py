"""Questões do Campo (Field) do Aconex: extração e de-para para as colunas (KB §32).

Só dados sintéticos, na estrutura medida na API real (spec, Apêndice B).
"""
from __future__ import annotations

import copy

import pytest

from docmanager import aconex_backend as ab
from docmanager import field_backend as fb

CONFIG = ab.AconexConfig(client_id="c", client_secret="s", user_id="u",
                         project_id="123", instance="https://aconex.exemplo")

QUESTAO = {
    "issue_id": "00000000-0000-4000-8000-000000000150",
    "issue_number": "150",
    "description": "Durante o comissionamento do painel X constatou-se cabo solto.",
    "status": "Open",
    "location_detail": "PAINEL-A",
    "issue_type": {"id": "9001", "name": "05. Pendencia de Comisionamiento", "custom_fields": []},
    "area": {"id": "3", "name": "GEQ-001-008: GRUPO EXEMPLO",
             "path": [{"id": "1", "name": "PROJETO EXEMPLO"},
                      {"id": "2", "name": "GRUPO DE EQUIPAMENTOS"},
                      {"id": "4", "name": "PE001: PLANO EXEMPLO"}]},
    "meta_data": {"created_at": "2026-10-31T01:30:00.000Z",
                  "created_by": {"id": "7", "first_name": "FULANO", "last_name": "DE TAL",
                                 "organization": {"name": "ORGANIZACAO EXEMPLO",
                                                  "trading_name": "ORG EXEMPLO"}}},
    "assigned_at": "2026-10-31T01:30:00.000Z",
    "assigned_to": {"organization": {"id": "10", "name": "CONSORCIO EXEMPLO", "trading_name": "CMI"}},
    "assigned_by": {"organization": {"id": "20", "name": "ORGANIZACAO EXEMPLO",
                                     "trading_name": "ORG EXEMPLO"}},
    "due_date": "2026-11-05T12:00:00.000Z",
    "closed_by": None,
    "closed_at": None,
    "issue_listings": [],
    "custom_fields": [
        {"id": "111", "family_id": "F-TAG", "value": "#XX00=Z99ABC10: EQUIPAMENTO EXEMPLO"},
        {"id": "222", "family_id": "F-CLASSIF", "value": "Impeditiva"},
        {"id": "333", "family_id": "F-PASSOU", "value": "Yes"},
        {"id": "444", "family_id": "F-CIERRE", "value": None},
        {"id": "555", "family_id": "F-DATA", "value": "2026-10-30"},
    ],
}

DEFINICOES = [
    {"id": "999", "family_id": "F-TAG", "label": "TAG RDS-PP", "type": {"name": "single_select"}},
    {"id": "998", "family_id": "F-CLASSIF", "label": "Clasificación de pendencia",
     "type": {"name": "single_select"}},
    {"id": "997", "family_id": "F-PASSOU", "label": "¿Pasó a comisionamiento?",
     "type": {"name": "boolean"}},
    {"id": "996", "family_id": "F-CIERRE", "label": "Cierre", "type": {"name": "single_select"}},
    {"id": "995", "family_id": "F-DATA", "label": "Fecha prevista para corrección",
     "type": {"name": "date"}},
]


def _valores(q=QUESTAO, comentarios=None, avisos=None):
    return fb.valores_da_questao(q, fb.definicoes_por_chave(DEFINICOES), comentarios,
                                 avisar=(avisos.append if avisos is not None else None))


# --- De-para -------------------------------------------------------------------

def test_colunas_da_exportacao():
    v = _valores()
    assert v["Issue Number"] == 150            # número, não texto
    assert v["Issue Type"] == "05. Pendencia de Comisionamiento"
    assert v["Area"] == ("PROJETO EXEMPLO > GRUPO DE EQUIPAMENTOS > PE001: PLANO EXEMPLO > "
                         "GEQ-001-008: GRUPO EXEMPLO")
    assert v["Location Detail"] == "PAINEL-A"
    assert v["Issue Description"].startswith("Durante o comissionamento")
    assert v["Captured by"] == "FULANO DE TAL"
    assert v["Status"] == "Open"
    assert v["Assigned to"] == "CMI"            # nome fantasia
    assert v["Assigned By"] == "ORG EXEMPLO"
    assert v["Closed On"] == "" and v["Closed By User"] == ""


def test_captured_on_vira_o_dia_do_fuso_local():
    """01:30 UTC de 31/10 ainda é 30/10 em UTC−3."""
    assert _valores()["Captured On"] == "2026-10-30"


def test_due_date_nao_converte_fuso():
    q = dict(QUESTAO, due_date="2026-11-05T01:00:00.000Z")
    assert _valores(q)["Due Date"] == "2026-11-05"


def test_area_nao_repete_quando_o_path_ja_termina_nela():
    q = dict(QUESTAO, area={"name": "B", "path": [{"name": "A"}, {"name": "B"}]})
    assert _valores(q)["Area"] == "A > B"


def test_campos_customizados_casam_pelo_family_id():
    v = _valores()
    assert v["TAG RDS-PP"] == "#XX00=Z99ABC10: EQUIPAMENTO EXEMPLO"   # id 111 ≠ 999
    assert v["Clasificación de pendencia"] == "Impeditiva"
    assert v["Cierre"] == ""                                         # value nulo
    assert v["Fecha prevista para corrección"] == "2026-10-30"


def test_booleano_vira_sim_e_nao():
    assert _valores()["¿Pasó a comisionamiento?"] == "Sim"
    q = copy.deepcopy(QUESTAO)
    q["custom_fields"][2]["value"] = "No"
    assert _valores(q)["¿Pasó a comisionamiento?"] == "Não"


def test_status_conhecidos_e_desconhecido():
    for cru, rotulo in (("InDispute", "In dispute"), ("WorkDone", "Work Done"), ("Closed", "Closed")):
        assert _valores(dict(QUESTAO, status=cru))["Status"] == rotulo
    avisos = []
    assert _valores(dict(QUESTAO, status="Paused"), avisos=avisos)["Status"] == "Paused"
    assert avisos and "Paused" in avisos[0]


def test_tipo_de_campo_nao_verificado_grava_o_texto_e_avisa():
    defs = DEFINICOES + [{"id": "1", "family_id": "F-USR", "label": "Quem",
                          "type": {"name": "user"}}]
    q = dict(QUESTAO, custom_fields=[{"id": "2", "family_id": "F-USR", "value": "FULANO"}])
    avisos = []
    v = fb.valores_da_questao(q, fb.definicoes_por_chave(defs), avisar=avisos.append)
    assert v["Quem"] == "FULANO"
    assert avisos


def test_campo_ausente_da_questao_nao_aparece():
    assert "Cierre" not in _valores(dict(QUESTAO, custom_fields=[]))


def test_rotulos_so_dos_tipos_em_uso():
    tipos = [{"id": "9001", "custom_fields": [{"label": "TAG RDS-PP"}]},
             {"id": "7", "custom_fields": [{"label": "Especialidad"}]}]
    assert fb.rotulos_dos_campos_das_questoes(tipos, [QUESTAO]) == {"TAG RDS-PP"}


# --- Comments ------------------------------------------------------------------

def _comentario(texto, quando, nome="FULANO", org="CMI"):
    return {"content": texto, "client_captured_at": quando,
            "author": {"first_name": nome, "last_name": "DE TAL",
                       "organization": {"name": "X", "trading_name": org}}}


def test_um_bloco():
    conv = [{"participant": {"id": "-1", "trading_name": "Everyone"},
             "comments": [_comentario("ok", "2026-09-30T11:23:10.953Z")]}]
    assert fb.formatar_comentarios(conv) == (
        'With Everyone:\n"ok" submitted by FULANO DE TAL (CMI) on Wed, Sep 30, 2026, 8:23:10 am')


def test_varios_comentarios_em_ordem_cronologica():
    conv = [{"participant": {"id": "-1", "trading_name": "Everyone"},
             "comments": [_comentario("segundo", "2026-09-30T15:00:00Z"),
                          _comentario("primeiro", "2026-09-30T14:00:00Z")]}]
    linhas = fb.formatar_comentarios(conv).split("\n")
    assert linhas[1].startswith('"primeiro"') and linhas[2].startswith('"segundo"')


def test_everyone_primeiro_e_blocos_separados_por_linha_em_branco():
    conv = [{"participant": {"id": "20", "trading_name": "ORG EXEMPLO"},
             "comments": [_comentario("privado", "2026-09-30T14:00:00Z")]},
            {"participant": {"id": "30", "trading_name": "VAZIA"}, "comments": []},
            {"participant": {"id": "-1", "trading_name": "Everyone"},
             "comments": [_comentario("publico", "2026-09-30T14:00:00Z")]}]
    blocos = fb.formatar_comentarios(conv).split("\n\n")
    assert [b.split("\n")[0] for b in blocos] == ["With Everyone:", "With ORG EXEMPLO:"]


def test_conteudo_com_aspas_e_quebra_de_linha_vai_como_veio():
    conv = [{"participant": {"id": "-1", "trading_name": "Everyone"},
             "comments": [_comentario('diz "não"\noutra linha', "2026-09-30T14:00:00Z")]}]
    assert '"diz "não"\noutra linha" submitted by' in fb.formatar_comentarios(conv)


@pytest.mark.parametrize("utc, esperado", [
    ("2026-09-30T03:05:09Z", "Wed, Sep 30, 2026, 12:05:09 am"),   # meia-noite local
    ("2026-09-30T15:00:00Z", "Wed, Sep 30, 2026, 12:00:00 pm"),   # meio-dia local
])
def test_meia_noite_e_meio_dia(utc, esperado):
    assert fb._quando(utc) == esperado


def test_sem_comentarios_e_vazio():
    assert fb.formatar_comentarios([]) == ""
    assert fb.formatar_comentarios([{"participant": {"id": "-1"}, "comments": []}]) == ""


# --- Extração (sessão simulada) ------------------------------------------------

class _Resposta:
    def __init__(self, status, dados=None):
        self.status_code, self._dados, self.text = status, dados, ""

    def json(self):
        return self._dados


class _SessaoField:
    def __init__(self, questoes, *, por_pagina=200, falhas=None, conversas=None):
        self.questoes, self.por_pagina = questoes, por_pagina
        self.falhas = dict(falhas or {})      # rota (sufixo) → lista de status a devolver antes
        self.conversas = conversas or {}
        self.chamadas: list[tuple[str, dict, dict]] = []

    def get(self, url, headers=None, params=None, timeout=None):
        rota = url.split("/projects/123/", 1)[1]
        self.chamadas.append((rota, dict(params or {}), dict(headers or {})))
        if self.falhas.get(rota):
            status = self.falhas[rota].pop(0)
            if status == "rede":
                raise ConnectionError("conexão caiu")
            return _Resposta(status)
        if rota == "areas":
            return _Resposta(200, {"areas": [{"id": "1", "name": "RAIZ", "children": []}]})
        if rota == "customfields":
            return _Resposta(200, {"custom_fields": DEFINICOES})
        if rota == "issue_types":
            return _Resposta(200, {"issue_types": [{"id": "9001", "custom_fields": DEFINICOES}]})
        if rota == "areas/1/issues":
            p = params["page_number"]
            fatia = self.questoes[(p - 1) * self.por_pagina:p * self.por_pagina]
            total = -(-len(self.questoes) // self.por_pagina)
            return _Resposta(200, {"issues": fatia, "total_pages": total, "page_number": p,
                                   "total_results": len(self.questoes)})
        if rota.endswith("/conversations/all"):
            iid = rota.split("/")[1]
            return _Resposta(200, {"_embedded": {"conversations": self.conversas.get(iid, [])}})
        return _Resposta(404)

    def close(self):
        pass


@pytest.fixture
def sem_espera(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)


def _plugar(monkeypatch, sessao):
    monkeypatch.setattr("docmanager.aconex_backend._estabelecer_sessao",
                        lambda *_a, **_k: (sessao, "token"))


def _questoes(n):
    return [dict(QUESTAO, issue_id=f"id-{i}", issue_number=str(i)) for i in range(n, 0, -1)]


def test_pagina_ate_o_total_e_deduplica(monkeypatch, sem_espera):
    qs = _questoes(5)
    qs.insert(3, dict(qs[1]))     # a mesma questão em duas páginas
    sessao = _SessaoField(qs, por_pagina=2)
    _plugar(monkeypatch, sessao)
    r = fb.extrair_questoes(CONFIG, log_cb=lambda _m: None, com_comentarios=False)
    assert [q["issue_number"] for q in r.questoes] == ["5", "4", "3", "2", "1"]
    paginas = [p["page_number"] for rota, p, _h in sessao.chamadas if rota == "areas/1/issues"]
    assert paginas == [1, 2, 3]
    _rota, params, headers = next(c for c in sessao.chamadas if c[0] == "areas/1/issues")
    assert params["include_child_areas"] == "true" and params["include_shared"] == "true"
    assert params["page_size"] == 200
    assert headers["Accept"] == "application/json"
    assert headers["Authorization"] == "Bearer token"


def test_conversas_pedem_supportPublicConversation(monkeypatch, sem_espera):
    conv = [{"participant": {"id": "-1", "trading_name": "Everyone"}, "comments": []}]
    sessao = _SessaoField(_questoes(2), conversas={"id-2": conv})
    _plugar(monkeypatch, sessao)
    r = fb.extrair_questoes(CONFIG, log_cb=lambda _m: None)
    assert r.comentarios_por_issue == {"id-2": conv, "id-1": []}
    chamadas = [(rota, p) for rota, p, _h in sessao.chamadas if rota.endswith("conversations/all")]
    assert len(chamadas) == 2
    assert all(p == {"supportPublicConversation": "true"} for _r, p in chamadas)


def test_sem_comentarios_nao_chama_conversas(monkeypatch, sem_espera):
    sessao = _SessaoField(_questoes(3))
    _plugar(monkeypatch, sessao)
    fb.extrair_questoes(CONFIG, log_cb=lambda _m: None, com_comentarios=False)
    assert not [c for c in sessao.chamadas if "conversations" in c[0]]


def test_cota_respeitada_mesmo_com_conversas_em_paralelo(monkeypatch):
    """As conversas vão em paralelo (era ~85 s uma a uma), mas o início das chamadas
    continua espaçado pela pausa (a cota de chamadas por segundo é da organização)
    e nunca há mais que CONVERSAS_EM_PARALELO no ar."""
    import threading
    import time as tempo

    pausa = 0.05
    monkeypatch.setattr(fb, "PAUSA_ENTRE_CHAMADAS_S", pausa)
    inicios, no_ar, pico = [], [0], [0]
    trava = threading.Lock()
    base = _SessaoField(_questoes(20))
    original = base.get

    def get(url, **kw):
        with trava:
            inicios.append(tempo.monotonic())
            no_ar[0] += 1
            pico[0] = max(pico[0], no_ar[0])
        tempo.sleep(0.06)            # a latência da rede
        try:
            return original(url, **kw)
        finally:
            with trava:
                no_ar[0] -= 1

    base.get = get
    _plugar(monkeypatch, base)
    r = fb.extrair_questoes(CONFIG, log_cb=lambda _m: None)
    assert len(r.comentarios_por_issue) == 20
    # A taxa, não o intervalo mínimo: no Windows o relógio anda de ~16 em ~16 ms,
    # e duas chamadas espaçadas podem cair no mesmo tique.
    inicios.sort()
    assert inicios[-1] - inicios[0] >= 0.9 * pausa * (len(inicios) - 1)
    assert 1 < pico[0] <= fb.CONVERSAS_EM_PARALELO


def test_falha_numa_conversa_cancela_e_levanta(monkeypatch, sem_espera):
    sessao = _SessaoField(_questoes(10), falhas={"issues/id-5/conversations/all": [503] * 20})
    _plugar(monkeypatch, sessao)
    with pytest.raises(fb.ErroField, match="503"):
        fb.extrair_questoes(CONFIG, log_cb=lambda _m: None)


def test_401_renova_o_token(monkeypatch, sem_espera):
    sessao = _SessaoField(_questoes(1), falhas={"customfields": [401]})
    _plugar(monkeypatch, sessao)
    monkeypatch.setattr(ab, "_get_token", lambda *_a: "novo")
    fb.extrair_questoes(CONFIG, log_cb=lambda _m: None, com_comentarios=False)
    depois = [h for rota, _p, h in sessao.chamadas if rota == "issue_types"]
    assert depois[0]["Authorization"] == "Bearer novo"


def test_503_e_queda_de_rede_sao_retentadas(monkeypatch, sem_espera):
    sessao = _SessaoField(_questoes(1), falhas={"areas/1/issues": [503, "rede"]})
    _plugar(monkeypatch, sessao)
    r = fb.extrair_questoes(CONFIG, log_cb=lambda _m: None, com_comentarios=False)
    assert len(r.questoes) == 1


def test_falha_definitiva_levanta(monkeypatch, sem_espera):
    sessao = _SessaoField(_questoes(1), falhas={"areas/1/issues": [503] * 20})
    _plugar(monkeypatch, sessao)
    with pytest.raises(fb.ErroField, match="503"):
        fb.extrair_questoes(CONFIG, log_cb=lambda _m: None, com_comentarios=False)


# --- Os Workflows usam o mesmo GET resiliente ------------------------------------

def test_workflows_retentam_pelo_ajudante_compartilhado(monkeypatch, sem_espera):
    from docmanager import workflows_backend as wb

    respostas = [_Resposta(503), _Resposta(400)]

    class _S:
        def get(self, *_a, **_k):
            return respostas.pop(0)

    linhas, fim, erro, _s = wb._baixar_pagina_wf(_S(), CONFIG, "u", {}, {}, 1, lambda _m: None)
    assert (linhas, fim, erro) == ([], True, "")
