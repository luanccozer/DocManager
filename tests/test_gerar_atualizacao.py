"""Gerador da atualização "só do que mudou" (`tools/gerar_atualizacao.py`).

Errar aqui custa caro e aparece tarde: um manifesto torto vira a base errada da
versão SEGUINTE, um include do Inno mal escapado só quebra no runner Windows, e
um pacote que esquece um arquivo deixa a instalação de alguém pela metade.
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


# ─────────────────────────────── diferença ──────────────────────────────────

def test_diferenca_novo_mudado_sumido_e_igual():
    base = {"igual.dll": _info(b"a"), "mudou.pyc": _info(b"v1"),
            "velho/sub/x.txt": _info(b"x"), "velho/y.txt": _info(b"y"),
            "fica/z.txt": _info(b"z")}
    nova = {"igual.dll": _info(b"a"), "mudou.pyc": _info(b"v2"),
            "novo/n.txt": _info(b"n"), "fica/z.txt": _info(b"z")}
    d = g.diferenca(base, nova)
    assert d.copiar == ["mudou.pyc", "novo/n.txt"]
    assert d.remover == ["velho/sub/x.txt", "velho/y.txt"]
    # Da mais funda para a mais rasa; "fica" continua existindo.
    assert d.pastas_remover == ["velho/sub", "velho"]


def test_diferenca_vazia_quando_nada_mudou():
    arquivos = {"a": _info(b"a")}
    assert g.diferenca(arquivos, dict(arquivos)).vazia


def test_fracao_copiada_conta_bytes_da_versao_nova():
    nova = {"grande": {"sha256": "1", "tamanho": 70}, "pequeno": {"sha256": "2", "tamanho": 30}}
    d = g.Diferenca(copiar=["grande"])
    assert g.fracao_copiada(d, nova) == pytest.approx(0.7)


# ─────────────────────────── includes do Inno ───────────────────────────────

def test_include_de_arquivos_escapa_e_aponta_o_destdir(tmp_path):
    # Só '{' no nome: '"' é inválido em nome de arquivo no Windows (onde o
    # Release roda estes testes) - o escape dele é conferido logo abaixo, em texto.
    iss_dir = tmp_path / "installer"
    iss_dir.mkdir()
    dist = _arvore(tmp_path / "dist" / "DocManager",
                   {"DocManager.exe": b"e", "_internal/pasta {x}/ab.txt": b"t"})
    origens = g.fontes(dist, {})
    d = g.Diferenca(copiar=["DocManager.exe", "_internal/pasta {x}/ab.txt"])
    linhas = g.linhas_arquivos(d, origens, iss_dir)
    assert linhas[0] == ('Source: "..\\dist\\DocManager\\DocManager.exe"; '
                         'DestDir: "{app}"; Flags: ignoreversion')
    assert linhas[1] == ('Source: "..\\dist\\DocManager\\_internal\\pasta {{x}\\ab.txt"; '
                         'DestDir: "{app}\\_internal\\pasta {{x}"; Flags: ignoreversion')


def test_escape_do_inno_dobra_chave_e_aspas():
    assert g.escapar_inno('pasta {x}/a"b.txt') == 'pasta {{x}/a""b.txt'


def test_include_de_remocao_tem_arquivos_e_dirifempty():
    d = g.Diferenca(remover=["_internal/velho/a.pyd"], pastas_remover=["_internal/velho"])
    assert g.linhas_remover(d) == [
        'Type: files; Name: "{app}\\_internal\\velho\\a.pyd"',
        'Type: dirifempty; Name: "{app}\\_internal\\velho"',
    ]


def test_include_sai_em_utf8_com_bom(tmp_path):
    """Sem BOM o Inno lê o include na code page do Windows e um acento troca."""
    destino = tmp_path / "x.iss"
    g.gravar_include(destino, ['Type: files; Name: "{app}\\ação.txt"'], "teste")
    bruto = destino.read_bytes()
    assert bruto.startswith(b"\xef\xbb\xbf")
    assert "ação" in bruto.decode("utf-8-sig")


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

def _iscc_falso(tmp_path: Path) -> Path:
    """Faz o papel do ISCC: grava o .exe com o nome que o .iss daria, e guarda
    os includes que recebeu para o teste conferir."""
    script = tmp_path / "iscc_falso.py"
    script.write_text(
        "import sys, pathlib, re\n"
        "args = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('/D'))\n"
        "iss = pathlib.Path(sys.argv[-1])\n"
        "saida = iss.parent / 'Output'\n"
        "saida.mkdir(exist_ok=True)\n"
        "nome = f\"DocManager_Itaipu_Update_{args['VersaoDe']}_para_{args['MyAppVersion']}.exe\"\n"
        "corpo = (iss.parent / 'atualizacao_arquivos.iss').read_bytes()\n"
        "(saida / nome).write_bytes(corpo * 1000)\n", encoding="utf-8")
    return script


def _usar_iscc(monkeypatch, script):
    rodar = subprocess.run   # o original: `g.subprocess` é o mesmo módulo
    monkeypatch.setattr(g.subprocess, "run",
                        lambda cmd, **k: rodar([sys.executable, str(script), *cmd[1:]], **k))


def _cenario(tmp_path, base_arquivos, nova_arquivos):
    dist = _arvore(tmp_path / "dist" / "DocManager", nova_arquivos)
    iss = tmp_path / "installer" / "docmanager.iss"
    iss.parent.mkdir()
    iss.write_text("; falso", encoding="utf-8")
    nova = g.montar_manifesto("3.3.0", dist, {})
    base = {"versao": "3.2.0", "arquivos": {r: _info(c) for r, c in base_arquivos.items()}}
    return dist, iss, nova, base


def test_pacote_gera_exe_zip_e_entrada_do_latest(tmp_path, monkeypatch):
    comum = {f"_internal/lib{i}.dll": bytes([i]) * 1000 for i in range(10)}
    dist, iss, nova, base = _cenario(
        tmp_path, {**comum, "DocManager.exe": b"igual", "_internal/docmanager/a.pyc": b"v1",
                   "_internal/sumiu.pyd": b"x"},
        {**comum, "DocManager.exe": b"igual", "_internal/docmanager/a.pyc": b"v2"})
    iscc = _iscc_falso(tmp_path)
    _usar_iscc(monkeypatch, iscc)
    entrada = g.gerar_pacote(de="3.2.0", base=base, nova=nova, origens=g.fontes(dist, {}),
                             iss=iss, iscc="ISCC", versao="3.3.0", versao_info="3.3.0",
                             pasta_saida=iss.parent / "Output")
    assert entrada["de"] == "3.2.0"
    assert entrada["arquivo"] == "DocManager_Itaipu_Update_3.2.0_para_3.3.0.exe"
    exe = iss.parent / "Output" / entrada["arquivo"]
    assert entrada["sha256"] == hashlib.sha256(exe.read_bytes()).hexdigest()
    assert entrada["tamanho"] == exe.stat().st_size

    # O include tem SÓ o que mudou; o de remoção, o que sumiu.
    arquivos = (iss.parent / "atualizacao_arquivos.iss").read_text(encoding="utf-8-sig")
    assert "a.pyc" in arquivos and "lib0.dll" not in arquivos and "DocManager.exe" not in arquivos
    remover = (iss.parent / "atualizacao_remover.iss").read_text(encoding="utf-8-sig")
    assert 'Type: files; Name: "{app}\\_internal\\sumiu.pyd"' in remover

    # zip: sem compressão, um membro só, com o hash do de dentro.
    zip_ = iss.parent / "Output" / entrada["zip"]["arquivo"]
    with zipfile.ZipFile(zip_) as z:
        assert [i.filename for i in z.infolist()] == [entrada["arquivo"]]
        assert z.infolist()[0].compress_type == zipfile.ZIP_STORED
    assert entrada["zip"]["sha256_dentro"] == entrada["sha256"]
    assert entrada["zip"]["sha256"] == hashlib.sha256(zip_.read_bytes()).hexdigest()


def test_pacote_pulado_quando_passa_de_60_por_cento(tmp_path, monkeypatch, capsys):
    dist, iss, nova, base = _cenario(
        tmp_path, {"grande.dll": b"v1" * 500, "pequeno.txt": b"p"},
        {"grande.dll": b"v2" * 500, "pequeno.txt": b"p"})
    monkeypatch.setattr(g.subprocess, "run", lambda *a, **k: pytest.fail("não devia compilar"))
    assert g.gerar_pacote(de="3.2.0", base=base, nova=nova, origens=g.fontes(dist, {}),
                          iss=iss, iscc="ISCC", versao="3.3.0", versao_info="3.3.0",
                          pasta_saida=tmp_path) is None
    assert "::warning::" in capsys.readouterr().out


def test_pacote_pulado_quando_nada_mudou(tmp_path, monkeypatch, capsys):
    dist, iss, nova, base = _cenario(tmp_path, {"a.txt": b"a"}, {"a.txt": b"a"})
    monkeypatch.setattr(g.subprocess, "run", lambda *a, **k: pytest.fail("não devia compilar"))
    assert g.gerar_pacote(de="3.2.0", base=base, nova=nova, origens=g.fontes(dist, {}),
                          iss=iss, iscc="ISCC", versao="3.3.0", versao_info="3.3.0",
                          pasta_saida=tmp_path) is None
    assert "nenhum arquivo mudou" in capsys.readouterr().out


def test_iscc_que_falha_nao_derruba_o_release(tmp_path, monkeypatch, capsys):
    comum = {f"lib{i}.dll": bytes([i]) * 1000 for i in range(5)}
    dist, iss, nova, base = _cenario(tmp_path, {**comum, "a.pyc": b"1"}, {**comum, "a.pyc": b"2"})
    monkeypatch.setattr(g.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 2))
    assert g.gerar_pacote(de="3.2.0", base=base, nova=nova, origens=g.fontes(dist, {}),
                          iss=iss, iscc="ISCC", versao="3.3.0", versao_info="3.3.0",
                          pasta_saida=tmp_path) is None
    assert "ISCC falhou" in capsys.readouterr().out


def test_subcomando_pacotes_preenche_o_latest_json(tmp_path, monkeypatch):
    comum = {f"lib{i}.dll": bytes([i]) * 1000 for i in range(10)}
    dist, iss, nova, base = _cenario(tmp_path, {**comum, "a.pyc": b"1"}, {**comum, "a.pyc": b"2"})
    manifesto = tmp_path / "arquivos.json"
    manifesto.write_text(json.dumps(nova), encoding="utf-8")
    bases = tmp_path / "bases"
    bases.mkdir()
    (bases / "v3.2.0.json").write_text(json.dumps(base), encoding="utf-8")
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps({"versao": "3.3.0", "sha256": "completo"}), encoding="utf-8")
    lista = tmp_path / "pacotes.txt"
    iscc = _iscc_falso(tmp_path)
    _usar_iscc(monkeypatch, iscc)
    g.main(["pacotes", "--manifesto", str(manifesto), "--bases", str(bases), "--dist", str(dist),
            "--versao", "3.3.0", "--iss", str(iss), "--iscc", "ISCC",
            "--saida", str(iss.parent / "Output"), "--latest", str(latest), "--lista", str(lista)])
    dados = json.loads(latest.read_text(encoding="utf-8"))
    assert dados["sha256"] == "completo"            # o que o app 3.1.x lê não muda
    assert [e["de"] for e in dados["atualizacoes"]] == ["3.2.0"]
    caminhos = lista.read_bytes().decode().splitlines()
    assert [Path(c).suffix for c in caminhos] == [".zip", ".exe"]
    assert b"\r" not in lista.read_bytes()
