"""Checkpoint e retomada da extração Aconex (KB §28).

Nada aqui toca a rede: a sessão HTTP é simulada, e o que se testa é o contrato
de retomada - não perder página, não duplicar página e nunca devolver uma base
truncada como se estivesse completa.
"""
import json

import pytest

from docmanager.aconex_backend import AconexConfig, extrair_base
from docmanager.services.aconex_checkpoint import (
    CheckpointExtracao,
    chave_extracao,
    limpar_antigos,
)

CONFIG = AconexConfig(client_id="cid", client_secret="s", user_id="uid", project_id="P1")


# ---------------------------------------------------------------------------
# CheckpointExtracao
# ---------------------------------------------------------------------------
def test_chave_muda_quando_a_consulta_muda():
    comum = dict(project_id="P1", page_size=500, sort_field="docno", sort_direction="ASC")
    assert chave_extracao(campos="a,b", **comum) != chave_extracao(campos="a,b,c", **comum)
    assert chave_extracao(campos="a,b", **comum) == chave_extracao(campos="a,b", **comum)


def test_registrar_e_carregar_paginas(tmp_path):
    ck = CheckpointExtracao("k1", tmp_path)
    ck.registrar_pagina(1, [{"DocumentNumber": "A"}, {"DocumentNumber": "B"}])
    ck.registrar_pagina(2, [{"DocumentNumber": "C"}])
    ck.fechar()

    outro = CheckpointExtracao("k1", tmp_path)
    registros = outro.carregar()
    assert [r["DocumentNumber"] for r in registros] == ["A", "B", "C"]
    assert outro.estado.pagina == 2
    assert outro.estado.proxima_pagina == 3


def test_pagina_escrita_pela_metade_e_descartada(tmp_path):
    """Crash no meio da escrita: o meta ainda aponta a página anterior, e o
    .jsonl é truncado de volta - sem registro duplicado nem JSON quebrado."""
    ck = CheckpointExtracao("k2", tmp_path)
    ck.registrar_pagina(1, [{"DocumentNumber": "A"}])
    ck.fechar()
    # Simula o processo morrendo com meia linha gravada.
    with open(ck.path_dados, "ab") as fh:
        fh.write(b'{"DocumentNumber": "B"')

    retomado = CheckpointExtracao("k2", tmp_path)
    registros = retomado.carregar()
    assert [r["DocumentNumber"] for r in registros] == ["A"]
    assert retomado.estado.proxima_pagina == 2
    # E continuar dali produz um arquivo íntegro.
    retomado.registrar_pagina(2, [{"DocumentNumber": "B"}])
    retomado.fechar()
    assert [r["DocumentNumber"] for r in CheckpointExtracao("k2", tmp_path).carregar()] == ["A", "B"]


def test_meta_corrompido_nao_derruba_a_extracao(tmp_path):
    ck = CheckpointExtracao("k3", tmp_path)
    ck.registrar_pagina(1, [{"DocumentNumber": "A"}])
    ck.fechar()
    ck.path_meta.write_text("{lixo", encoding="utf-8")
    assert CheckpointExtracao("k3", tmp_path).carregar() == []


def test_limpar_remove_os_arquivos(tmp_path):
    ck = CheckpointExtracao("k4", tmp_path)
    ck.registrar_pagina(1, [{"DocumentNumber": "A"}])
    ck.limpar()
    assert not ck.path_dados.exists() and not ck.path_meta.exists()


def test_limpar_antigos_respeita_a_idade(tmp_path):
    import os
    import time

    ck = CheckpointExtracao("k5", tmp_path)
    ck.registrar_pagina(1, [{"DocumentNumber": "A"}])
    ck.fechar()
    assert limpar_antigos(tmp_path, dias=30) == 0        # recém-criado, fica

    # Envelhece o arquivo explicitamente: comparar com `dias=0` dependeria da
    # granularidade do mtime do sistema de arquivos (teste instável no Windows).
    antigo = time.time() - 45 * 86400
    os.utime(ck.path_meta, (antigo, antigo))
    assert limpar_antigos(tmp_path, dias=30) == 1
    assert not ck.path_dados.exists() and not ck.path_meta.exists()


# ---------------------------------------------------------------------------
# extrair_base com a API simulada
# ---------------------------------------------------------------------------
def _xml(docs):
    corpo = "".join(
        f"<Document><DocumentNumber>{d}</DocumentNumber><TrackingId>{d}</TrackingId></Document>"
        for d in docs)
    return f"<Documents>{corpo}</Documents>".encode()


class _Resposta:
    def __init__(self, status, content=b""):
        self.status_code, self.content, self.text = status, content, ""


class _SessaoFake:
    """Devolve páginas de `roteiro` (lista de respostas). `falhar_em` levanta
    exceção de rede na página indicada."""

    def __init__(self, paginas, falhar_em=None):
        self.paginas = paginas
        self.falhar_em = falhar_em or {}
        self.chamadas = []

    def get(self, _url, headers=None, params=None, timeout=None):
        page = params["page_number"]
        self.chamadas.append(page)
        if page in self.falhar_em and self.falhar_em[page] > 0:
            self.falhar_em[page] -= 1
            raise ConnectionError("conexão caiu")
        docs = self.paginas.get(page)
        if docs is None:
            return _Resposta(400)
        return _Resposta(200, _xml(docs))

    def close(self):
        pass


@pytest.fixture
def sem_espera(monkeypatch):
    """Zera o backoff para o teste não dormir de verdade."""
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)


def _plugar(monkeypatch, sessao):
    monkeypatch.setattr("docmanager.aconex_backend._estabelecer_sessao",
                        lambda *_a, **_k: (sessao, "token"))


def test_extracao_completa_limpa_o_caminho_feliz(monkeypatch, tmp_path):
    _plugar(monkeypatch, _SessaoFake({1: ["A", "B"]}))
    r = extrair_base(CONFIG, log_cb=lambda _m: None, pasta_checkpoint=tmp_path)
    assert r.completa and r.ok
    assert list(r.df["No. do Documento"]) == ["A", "B"]
    assert r.checkpoint == ""        # nada a retomar


def test_falha_de_rede_nao_devolve_base_truncada_como_completa(monkeypatch, tmp_path, sem_espera):
    """O bug antigo: a paginação parava e o DataFrame parcial voltava como se
    estivesse inteiro. Agora `completa` é False e o motivo vem junto."""
    from docmanager.aconex_backend import PAGE_SIZE

    pagina_cheia = [f"D{i}" for i in range(PAGE_SIZE)]
    sessao = _SessaoFake({1: pagina_cheia, 2: ["X"]}, falhar_em={2: 99})
    _plugar(monkeypatch, sessao)

    r = extrair_base(CONFIG, log_cb=lambda _m: None, pasta_checkpoint=tmp_path)
    assert not r.completa
    assert len(r.df) == PAGE_SIZE
    assert "página 2" in r.motivo
    assert r.checkpoint                 # há de onde retomar


def test_segunda_execucao_retoma_da_pagina_seguinte(monkeypatch, tmp_path, sem_espera):
    from docmanager.aconex_backend import PAGE_SIZE

    pagina_cheia = [f"D{i}" for i in range(PAGE_SIZE)]
    # 1ª execução: página 1 vem, página 2 cai.
    _plugar(monkeypatch, _SessaoFake({1: pagina_cheia, 2: ["X"]}, falhar_em={2: 99}))
    r1 = extrair_base(CONFIG, log_cb=lambda _m: None, pasta_checkpoint=tmp_path)
    assert not r1.completa and not r1.retomada

    # 2ª execução: rede boa. A página 1 NÃO é rebaixada.
    sessao2 = _SessaoFake({1: pagina_cheia, 2: ["X"]})
    _plugar(monkeypatch, sessao2)
    r2 = extrair_base(CONFIG, log_cb=lambda _m: None, pasta_checkpoint=tmp_path)
    assert r2.completa and r2.retomada
    assert sessao2.chamadas == [2]                       # só a página que faltava
    assert len(r2.df) == PAGE_SIZE + 1
    assert list(r2.df["No. do Documento"])[-1] == "X"    # sem duplicar a página 1


def test_retentativa_bem_sucedida_nao_interrompe(monkeypatch, tmp_path, sem_espera):
    """Uma queda pontual é absorvida pelo backoff; a extração segue completa."""
    sessao = _SessaoFake({1: ["A"]}, falhar_em={1: 2})   # falha 2x, acerta na 3ª
    _plugar(monkeypatch, sessao)
    r = extrair_base(CONFIG, log_cb=lambda _m: None, pasta_checkpoint=tmp_path)
    assert r.completa and list(r.df["No. do Documento"]) == ["A"]


def test_cancelamento_preserva_o_progresso(monkeypatch, tmp_path):
    from docmanager.aconex_backend import PAGE_SIZE

    pagina_cheia = [f"D{i}" for i in range(PAGE_SIZE)]
    _plugar(monkeypatch, _SessaoFake({1: pagina_cheia, 2: pagina_cheia}))
    chamadas = {"n": 0}

    def cancelar():
        chamadas["n"] += 1
        return chamadas["n"] > 1        # cancela depois da 1ª página

    r = extrair_base(CONFIG, log_cb=lambda _m: None, pasta_checkpoint=tmp_path,
                     cancelado_cb=cancelar)
    assert not r.completa and "cancelado" in r.motivo
    ck = CheckpointExtracao(chave_extracao(project_id="P1", campos=CONFIG.campos,
                                           page_size=PAGE_SIZE, sort_field="docno",
                                           sort_direction="ASC"), tmp_path)
    assert ck.ler_meta().pagina == 1


def test_usar_checkpoint_desligado_nao_grava_nada(monkeypatch, tmp_path, sem_espera):
    _plugar(monkeypatch, _SessaoFake({1: ["A"]}))
    extrair_base(CONFIG, log_cb=lambda _m: None, pasta_checkpoint=tmp_path,
                 usar_checkpoint=False)
    assert not list(tmp_path.glob("*"))


def test_checkpoint_grava_json_legivel(tmp_path):
    ck = CheckpointExtracao("k9", tmp_path)
    ck.registrar_pagina(1, [{"DocumentNumber": "A"}])
    ck.fechar()
    meta = json.loads(ck.path_meta.read_text(encoding="utf-8"))
    assert meta["pagina"] == 1 and meta["total"] == 1 and meta["offset"] > 0
