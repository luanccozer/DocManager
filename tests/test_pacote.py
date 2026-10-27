"""A atualização pequena (`services/pacote.py`): o método da CMI Suite.

Os testes de lá, portados: o pacote leva só o que mudou, transforma a v1 na
v2, desfaz tudo quando algo não confere e recusa caminho que sai da pasta -
com as regras do Windows (a revisão de segurança de 26/10/2026 da CMI Suite
achou três nomes que passavam pelas regras POSIX).
"""
import hashlib
import json
import zipfile
from pathlib import Path, PureWindowsPath

import pytest

from docmanager.services import pacote
from tools import gerar_atualizacao as g


def _instalacao(pasta: Path, arquivos: dict[str, bytes]) -> Path:
    for rel, dados in arquivos.items():
        caminho = pasta / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(dados)
    return pasta


V1 = {"DocManager.exe": b"exe v1", "_internal/Qt6Core.dll": b"qt" * 1000,
      "_internal/docmanager/a.pyc": b"py v1", "_internal/sai.txt": b"so na v1",
      "CHANGELOG.md": b"# 3.3.0"}
V2 = {"DocManager.exe": b"exe v2", "_internal/Qt6Core.dll": b"qt" * 1000,
      "_internal/docmanager/a.pyc": b"py v2", "_internal/novo/entra.txt": b"so na v2",
      "CHANGELOG.md": b"# 3.4.0"}


def _manifesto(pasta: Path, versao: str) -> dict:
    return g.montar_manifesto(versao, pasta, {})


@pytest.fixture
def versoes(tmp_path):
    v1 = _instalacao(tmp_path / "v1", V1)
    v2 = _instalacao(tmp_path / "v2", V2)
    m1, m2 = _manifesto(v1, "3.3.0"), _manifesto(v2, "3.4.0")
    zip_ = pacote.montar(g.fontes(v2, {}), m1, m2, tmp_path)
    return v1, v2, m1, m2, zip_


def _conteudo(pasta: Path) -> dict[str, bytes]:
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in pasta.rglob("*") if p.is_file()}


def test_pacote_leva_so_o_que_mudou(versoes):
    *_, zip_ = versoes
    assert zip_.name == "DocManager_Itaipu_Atualizacao_3.3.0_para_3.4.0.zip"
    with zipfile.ZipFile(zip_) as z:
        info = json.loads(z.read("manifesto.json"))
        assert "arquivos/_internal/Qt6Core.dll" not in z.namelist()  # o Qt não muda: não viaja
    assert info["alterados"] == ["CHANGELOG.md", "DocManager.exe", "_internal/docmanager/a.pyc",
                                 "_internal/novo/entra.txt"]
    assert info["removidos"] == ["_internal/sai.txt"]


def test_aplicar_transforma_a_v1_na_v2(versoes):
    v1, _v2, _m1, m2, zip_ = versoes
    assert pacote.aplicar(zip_, v1, m2) == ["CHANGELOG.md", "DocManager.exe",
                                            "_internal/docmanager/a.pyc", "_internal/novo/entra.txt"]
    # os antigos ficam como .dm-old até a próxima abertura
    restos = sorted(p.name for p in v1.rglob(f"*{pacote.SUFIXO_ANTIGO}"))
    assert restos == ["CHANGELOG.md.dm-old", "DocManager.exe.dm-old", "a.pyc.dm-old", "sai.txt.dm-old"]
    assert pacote.limpar_restos(v1) == 4
    assert _conteudo(v1) == V2


def test_arquivos_fora_do_manifesto_ficam(versoes):
    """O desinstalador do Inno e o que mais houver na pasta não são do pacote."""
    v1, _v2, _m1, m2, zip_ = versoes
    (v1 / "unins000.exe").write_bytes(b"inno")
    pacote.aplicar(zip_, v1, m2)
    assert (v1 / "unins000.exe").read_bytes() == b"inno"


def test_resto_de_atualizacao_anterior_nao_atrapalha(versoes):
    v1, _v2, _m1, m2, zip_ = versoes
    (v1 / "DocManager.exe.dm-old").write_bytes(b"de outra vez")
    pacote.aplicar(zip_, v1, m2)
    pacote.limpar_restos(v1)
    assert _conteudo(v1) == V2


def test_falha_no_meio_desfaz_tudo(versoes):
    v1, _v2, _m1, m2, zip_ = versoes
    errado = dict(m2, arquivos=dict(m2["arquivos"], **{"DocManager.exe": {"sha256": "0" * 64}}))
    with pytest.raises(pacote.ErroPacote, match="não confere"):
        pacote.aplicar(zip_, v1, errado)
    assert _conteudo(v1) == V1


def test_pasta_que_nao_e_a_versao_de_origem_desfaz(versoes):
    """Um arquivo que não veio no pacote e não é o da v2 (pasta mexida, outra
    versão): a conferência final pega e tudo volta."""
    v1, _v2, _m1, m2, zip_ = versoes
    (v1 / "_internal/Qt6Core.dll").write_bytes(b"outro qt")
    antes = _conteudo(v1)
    with pytest.raises(pacote.ErroPacote, match="Qt6Core.dll"):
        pacote.aplicar(zip_, v1, m2)
    assert _conteudo(v1) == antes


def test_zip_corrompido_nao_mexe_em_nada(tmp_path):
    v1 = _instalacao(tmp_path / "v1", V1)
    zip_ = tmp_path / "corrompido.zip"
    zip_.write_bytes(b"PK isto nao e um zip")
    with pytest.raises(pacote.ErroPacote, match="desfeita"):
        pacote.aplicar(zip_, v1, {"versao": "3.4.0", "arquivos": {}})
    assert _conteudo(v1) == V1


def test_pacote_para_outra_versao_e_recusado(versoes):
    v1, _v2, _m1, m2, zip_ = versoes
    with pytest.raises(pacote.ErroPacote, match="leva à"):
        pacote.aplicar(zip_, v1, dict(m2, versao="9.9.9"))
    assert _conteudo(v1) == V1


def test_manifesto_so_com_o_sha_tambem_vale(versoes):
    """O formato da CMI Suite ({rel: sha}) e o do DocManager ({rel: {sha256, tamanho}})."""
    v1, _v2, _m1, m2, zip_ = versoes
    so_sha = dict(m2, arquivos={rel: v["sha256"] for rel, v in m2["arquivos"].items()})
    pacote.aplicar(zip_, v1, so_sha)
    pacote.limpar_restos(v1)
    assert _conteudo(v1) == V2


def test_caminho_fora_da_pasta_e_recusado(tmp_path):
    v1 = _instalacao(tmp_path / "v1", V1)
    zip_ = tmp_path / "mau.zip"
    with zipfile.ZipFile(zip_, "w") as z:
        z.writestr("manifesto.json", json.dumps({"de": "a", "para": "b", "alterados": ["../fora.txt"],
                                                 "removidos": []}))
        z.writestr("arquivos/../fora.txt", b"x")
    with pytest.raises(pacote.ErroPacote, match="inválido"):
        pacote.aplicar(zip_, v1, {"versao": "b", "arquivos": {}})
    assert not (tmp_path / "fora.txt").exists()


def test_contrabarra_no_pacote_e_recusada_e_nada_e_escrito(tmp_path):
    v1 = _instalacao(tmp_path / "v1", V1)
    zip_ = tmp_path / "mau.zip"
    with zipfile.ZipFile(zip_, "w") as z:
        z.writestr("manifesto.json", json.dumps({"de": "a", "para": "b",
                                                 "alterados": ["DocManager.exe", "..\\..\\evil.exe"],
                                                 "removidos": []}))
        z.writestr("arquivos/DocManager.exe", b"trocado")
        z.writestr("arquivos/..\\..\\evil.exe", b"x")
    with pytest.raises(pacote.ErroPacote, match="inválido"):
        pacote.aplicar(zip_, v1, {"versao": "b", "arquivos": {}})
    assert _conteudo(v1) == V1


BASE_WIN = PureWindowsPath(r"C:\Users\u\AppData\Local\Programs\DocManager Itaipu")


@pytest.mark.parametrize("malicioso", [
    "..\\..\\evil.exe",            # contrabarra: separador no Windows
    "sub/..\\..\\x.dll",
    "C:/Windows/System32/evil.dll",  # letra de unidade
    "C:evil.exe",
    "/etc/passwd",
    "../fora.txt",
    "a/../../fora.txt",
    "arquivo.txt:fluxo",           # fluxo alternativo do NTFS
    ".. /x", "... /x", "a./b",     # o Windows apaga ponto e espaço finais
    "", "a//b", "./a",
    "a\x00b",
])
def test_zip_slip_recusado_com_regras_do_windows(malicioso):
    with pytest.raises(pacote.ErroPacote):
        pacote.dentro(BASE_WIN, malicioso)


@pytest.mark.parametrize("legitimo", [
    "DocManager.exe", "_internal/PySide6/Qt6Core.dll", "CHANGELOG.md",
    "_internal/base_library.zip", "_internal/assets/splash.png", "_internal/certifi/cacert.pem",
])
def test_nomes_legitimos_dos_pacotes_passam(legitimo):
    destino = pacote.dentro(BASE_WIN, legitimo)
    assert str(destino).startswith(str(BASE_WIN) + "\\")


def test_gerador_recusa_montar_o_que_o_app_recusaria(tmp_path):
    origem = tmp_path / "x"
    origem.write_bytes(b"x")
    antigo = {"versao": "1", "arquivos": {}}
    novo = {"versao": "2", "arquivos": {"a:b": {"sha256": "1"}}}
    with pytest.raises(pacote.ErroPacote):
        pacote.montar({"a:b": origem}, antigo, novo, tmp_path)


def test_ferramenta_do_workflow_monta_o_pacote_que_o_app_aplica(tmp_path):
    """De ponta a ponta pela linha de comando, como no Release."""
    v1 = _instalacao(tmp_path / "v1", V1)
    v2 = _instalacao(tmp_path / "v2", V2)
    bases, saida = tmp_path / "bases", tmp_path / "saida"
    bases.mkdir()
    g.main(["manifesto", "--dist", str(v1), "--versao", "3.3.0", "--saida", str(bases / "v3.3.0.json")])
    g.main(["manifesto", "--dist", str(v2), "--versao", "3.4.0", "--saida", str(tmp_path / "arquivos.json")])
    latest = tmp_path / "latest.json"
    latest.write_text("{}", encoding="utf-8")
    g.main(["pacotes", "--manifesto", str(tmp_path / "arquivos.json"), "--bases", str(bases),
            "--dist", str(v2), "--saida", str(saida), "--latest", str(latest),
            "--lista", str(tmp_path / "lista.txt")])
    entrada = json.loads(latest.read_text(encoding="utf-8"))["pequenas"][0]
    zip_ = saida / entrada["arquivo"]
    assert hashlib.sha256(zip_.read_bytes()).hexdigest() == entrada["sha256"]
    pacote.aplicar(zip_, v1, json.loads((tmp_path / "arquivos.json").read_text(encoding="utf-8")))
    pacote.limpar_restos(v1)
    assert _conteudo(v1) == V2
