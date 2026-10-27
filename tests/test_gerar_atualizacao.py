"""Gerador da atualização "só do que mudou" (`tools/gerar_atualizacao.py`).

Errar aqui custa caro e aparece tarde: um manifesto torto vira a base errada da
versão SEGUINTE, e um pacote que esquece um arquivo deixaria a instalação de
alguém pela metade (o app confere e desfaz, mas aí ninguém recebe a pequena).
O formato do pacote e a aplicação dele estão em `tests/test_pacote.py`.
"""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from tools import gerar_atualizacao as g

RAIZ = Path(__file__).resolve().parent.parent


def _arvore(raiz: Path, arquivos: dict[str, bytes]) -> Path:
    for rel, conteudo in arquivos.items():
        destino = raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
    return raiz


def _info(conteudo: bytes) -> dict:
    return {"sha256": hashlib.sha256(conteudo).hexdigest(), "tamanho": len(conteudo)}


# ─────────────────────────────── manifesto ──────────────────────────────────

def test_manifesto_tem_hash_tamanho_e_caminhos_com_barra(tmp_path):
    dist = _arvore(tmp_path / "dist", {"DocManager.exe": b"exe",
                                       "_internal/docmanager/ui/x.pyc": b"pyc"})
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_bytes(b"# log")
    m = g.montar_manifesto("3.2.0", dist, g._extras([f"CHANGELOG.md={changelog}"]))
    assert m["versao"] == "3.2.0"
    assert m["arquivos"] == {
        "CHANGELOG.md": _info(b"# log"),
        "DocManager.exe": _info(b"exe"),
        "_internal/docmanager/ui/x.pyc": _info(b"pyc"),
    }


def test_fracao_copiada_conta_bytes_da_versao_nova():
    nova = {"grande": {"sha256": "1", "tamanho": 70}, "pequeno": {"sha256": "2", "tamanho": 30}}
    assert g.fracao_copiada(["grande"], nova) == pytest.approx(0.7)


# ──────────────────────────────── bases ─────────────────────────────────────

def _rel(tag, *, pre=False, draft=False, manifesto=True):
    assets = [{"name": "latest.json"}] + ([{"name": "arquivos.json"}] if manifesto else [])
    return {"tag_name": tag, "prerelease": pre, "draft": draft, "assets": assets}


def test_bases_sao_as_3_mais_recentes_e_sempre_a_ultima_normal():
    releases = [
        _rel("v3.3.0-rc.3", pre=True), _rel("v3.3.0-rc.2", pre=True),
        _rel("v3.3.0-rc.1", pre=True), _rel("v3.2.1"), _rel("v3.2.0"),
        _rel("v3.4.0-rc.1", pre=True, draft=True),       # rascunho: não conta
        _rel("v3.1.1", manifesto=False),                 # antes do mecanismo
    ]
    assert g.escolher_bases(releases, "3.3.0") == \
        ["v3.3.0-rc.3", "v3.3.0-rc.2", "v3.3.0-rc.1", "v3.2.1"]


def test_bases_ignoram_a_propria_versao_e_as_mais_novas():
    releases = [_rel("v3.3.0"), _rel("v3.2.1"), _rel("v3.2.0")]
    assert g.escolher_bases(releases, "3.2.1") == ["v3.2.0"]


def test_sem_nenhuma_base_com_manifesto_nao_ha_pequeno():
    assert g.escolher_bases([_rel("v3.1.1", manifesto=False)], "3.2.0") == []


def test_escolher_bases_imprime_so_lf(tmp_path):
    """No runner Windows o `\\r` grudava na tag dentro do $(...) do bash e todas
    as bases menos a última davam 'release not found'."""
    arq = tmp_path / "releases.json"
    arq.write_text(json.dumps([_rel("v3.2.1"), _rel("v3.2.0")]), encoding="utf-8")
    r = subprocess.run([sys.executable, str(RAIZ / "tools" / "gerar_atualizacao.py"),
                        "escolher-bases", "--releases", str(arq), "--versao", "3.3.0"],
                       capture_output=True, cwd=RAIZ)
    assert r.returncode == 0, r.stderr
    assert r.stdout == b"v3.2.1\nv3.2.0\n"


def test_versao_do_gerador_concorda_com_a_do_app():
    from docmanager.services import updater

    for v in ("3.2.0", "3.2.0-rc.1", "3.2.0-rc.10", "3.10.0", "v3.1", "lixo"):
        assert g.versao_em_partes(v) == updater.versao_em_partes(v), v


# ─────────────────────────────── pacotes ────────────────────────────────────

def _cenario(tmp_path, base_arquivos, nova_arquivos, extras=None):
    dist = _arvore(tmp_path / "dist" / "DocManager", nova_arquivos)
    nova = g.montar_manifesto("3.4.0", dist, extras or {})
    base = {"versao": "3.3.0", "arquivos": {r: _info(c) for r, c in base_arquivos.items()}}
    return dist, nova, base


def test_pacote_gera_o_zip_so_com_o_que_mudou(tmp_path):
    comum = {f"_internal/lib{i}.dll": bytes([i]) * 1000 for i in range(10)}
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_bytes(b"# 3.4.0")
    extras = {"CHANGELOG.md": changelog}
    dist, nova, base = _cenario(
        tmp_path, {**comum, "DocManager.exe": b"igual", "_internal/docmanager/a.pyc": b"v1",
                   "_internal/sumiu.pyd": b"x", "CHANGELOG.md": b"# 3.3.0"},
        {**comum, "DocManager.exe": b"igual", "_internal/docmanager/a.pyc": b"v2"}, extras)
    saida = tmp_path / "saida"
    saida.mkdir()
    entrada = g.gerar_pacote(base=base, nova=nova, origens=g.fontes(dist, extras),
                             pasta_saida=saida)
    assert entrada["de"] == "3.3.0"
    assert entrada["arquivo"] == "DocManager_Itaipu_Atualizacao_3.3.0_para_3.4.0.zip"
    zip_ = saida / entrada["arquivo"]
    assert entrada["sha256"] == hashlib.sha256(zip_.read_bytes()).hexdigest()
    assert entrada["tamanho"] == zip_.stat().st_size
    with zipfile.ZipFile(zip_) as z:
        assert sorted(z.namelist()) == ["arquivos/CHANGELOG.md",
                                        "arquivos/_internal/docmanager/a.pyc", "manifesto.json"]
        info = json.loads(z.read("manifesto.json"))
        assert z.read("arquivos/CHANGELOG.md") == b"# 3.4.0"   # o extra, de fora do dist
    assert info == {"de": "3.3.0", "para": "3.4.0",
                    "alterados": ["CHANGELOG.md", "_internal/docmanager/a.pyc"],
                    "removidos": ["_internal/sumiu.pyd"]}


def test_pacote_pulado_quando_passa_de_60_por_cento(tmp_path, capsys):
    dist, nova, base = _cenario(tmp_path, {"grande.dll": b"v1" * 500, "pequeno.txt": b"p"},
                                {"grande.dll": b"v2" * 500, "pequeno.txt": b"p"})
    assert g.gerar_pacote(base=base, nova=nova, origens=g.fontes(dist, {}),
                          pasta_saida=tmp_path) is None
    assert "::warning::" in capsys.readouterr().out
    assert not list(tmp_path.glob("*.zip"))


def test_pacote_pulado_quando_nada_mudou(tmp_path, capsys):
    dist, nova, base = _cenario(tmp_path, {"a.txt": b"a"}, {"a.txt": b"a"})
    assert g.gerar_pacote(base=base, nova=nova, origens=g.fontes(dist, {}),
                          pasta_saida=tmp_path) is None
    assert "nenhum arquivo mudou" in capsys.readouterr().out


def test_pacote_que_falha_nao_derruba_o_release(tmp_path, capsys):
    comum = {f"lib{i}.dll": bytes([i]) * 1000 for i in range(5)}
    dist, nova, base = _cenario(tmp_path, {**comum, "a.pyc": b"1"}, {**comum, "a.pyc": b"2"})
    assert g.gerar_pacote(base=base, nova=nova, origens=g.fontes(dist, {}),
                          pasta_saida=tmp_path / "nao_existe") is None
    assert "o pacote nao saiu" in capsys.readouterr().out


def test_subcomando_pacotes_preenche_o_latest_json(tmp_path):
    comum = {f"lib{i}.dll": bytes([i]) * 1000 for i in range(10)}
    dist, nova, base = _cenario(tmp_path, {**comum, "a.pyc": b"1"}, {**comum, "a.pyc": b"2"})
    manifesto = tmp_path / "arquivos.json"
    manifesto.write_text(json.dumps(nova), encoding="utf-8")
    bases = tmp_path / "bases"
    bases.mkdir()
    (bases / "v3.3.0.json").write_text(json.dumps(base), encoding="utf-8")
    (bases / "v3.2.0.json").write_text("{torto", encoding="utf-8")   # pulada, não derruba
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps({"versao": "3.4.0", "sha256": "completo",
                                  "atualizacoes": [{"de": "3.3.0"}]}), encoding="utf-8")
    lista = tmp_path / "pacotes.txt"
    g.main(["pacotes", "--manifesto", str(manifesto), "--bases", str(bases), "--dist", str(dist),
            "--saida", str(tmp_path / "Output"), "--latest", str(latest), "--lista", str(lista)])
    dados = json.loads(latest.read_text(encoding="utf-8"))
    assert dados["sha256"] == "completo"            # o que o app 3.1.x lê não muda
    # `atualizacoes` some: o app 3.2.0-3.3.0 rodaria o zip novo como instalador.
    assert "atualizacoes" not in dados
    assert [e["de"] for e in dados["pequenas"]] == ["3.3.0"]
    assert dados["arquivos_json"]["sha256"] == hashlib.sha256(manifesto.read_bytes()).hexdigest()
    caminhos = lista.read_bytes().decode().splitlines()
    assert [Path(c).name for c in caminhos] == ["DocManager_Itaipu_Atualizacao_3.3.0_para_3.4.0.zip"]
    assert b"\r" not in lista.read_bytes()
