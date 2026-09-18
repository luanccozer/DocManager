"""Scripts de build (`tools/`) — inclusive rodando com a codificação do Windows.

O motivo destes testes existirem: um `print("versão →")` derrubou uma publicação
inteira. No Windows o Python escreve em cp1252 por padrão, onde "→" não existe,
e o passo morria com UnicodeEncodeError DEPOIS de lint, testes e instalação de
dependências — 2 minutos de CI perdidos por causa de uma mensagem. Rodar os
scripts como subprocesso com `PYTHONIOENCODING=cp1252` reproduz exatamente esse
ambiente aqui, onde custa milissegundos.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
BUILD_INFO = RAIZ / "docmanager" / "_build_info.py"
TOKEN = RAIZ / "docmanager" / "_update_auth.py"


def rodar(*args, **kw):
    """Executa um script de tools/ com a codificação de console do Windows."""
    ambiente = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    ambiente.pop("PYTHONUTF8", None)   # não deixar o modo UTF-8 mascarar o teste
    ambiente.update(kw.pop("env", {}))
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", env=ambiente, cwd=RAIZ, **kw)


@pytest.fixture
def build_info_preservado():
    """Roda o teste e devolve `_build_info.py` (e o token) ao estado original."""
    original = BUILD_INFO.read_text(encoding="utf-8")
    token_existia = TOKEN.exists()
    yield
    BUILD_INFO.write_text(original, encoding="utf-8")
    if not token_existia:
        TOKEN.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# preparar_build.py
# --------------------------------------------------------------------------
def test_carimba_a_versao_mesmo_com_console_cp1252(build_info_preservado):
    r = rodar("tools/preparar_build.py", "4.2.1", "--origem", "teste", "--commit", "abc1234")
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"
    texto = BUILD_INFO.read_text(encoding="utf-8")
    assert 'VERSAO = "4.2.1"' in texto
    assert 'COMMIT = "abc1234"' in texto
    assert 'ORIGEM = "teste"' in texto


def test_versao_invalida_falha_com_mensagem_legivel(build_info_preservado):
    """A mensagem de erro também tem acento — ela não pode virar outro crash."""
    r = rodar("tools/preparar_build.py", "versao-errada")
    assert r.returncode != 0
    assert "inválida" in (r.stdout + r.stderr)


def test_token_embutido_quando_ha_segredo(build_info_preservado):
    from docmanager._ofuscacao import desofuscar

    r = rodar("tools/preparar_build.py", "4.2.1",
              env={"DOCMANAGER_UPDATE_TOKEN": "github_pat_de_teste"})
    assert r.returncode == 0, r.stderr
    valor = TOKEN.read_text(encoding="utf-8").split('TOKEN_OFUSCADO = "')[1].split('"')[0]
    assert desofuscar(valor) == "github_pat_de_teste"
    assert "github_pat_de_teste" not in TOKEN.read_text(encoding="utf-8")


def test_sem_segredo_o_token_sai_vazio(build_info_preservado):
    r = rodar("tools/preparar_build.py", "4.2.1", env={"DOCMANAGER_UPDATE_TOKEN": ""})
    assert r.returncode == 0, r.stderr
    assert 'TOKEN_OFUSCADO = ""' in TOKEN.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# gerar_manifesto.py
# --------------------------------------------------------------------------
CHANGELOG_EXEMPLO = """# Histórico

## 3.1.0 — 2026-09-18

- Atualização automática — com acento e travessão.
"""


def test_manifesto_tem_os_campos_que_o_app_le(tmp_path):
    from tools.gerar_manifesto import montar

    instalador = tmp_path / "Setup_3.1.0.exe"
    instalador.write_bytes(b"conteudo do instalador")
    m = montar(instalador, "3.1.0", "v3.1.0", CHANGELOG_EXEMPLO)
    assert m["versao"] == "3.1.0"
    assert m["arquivo"] == "Setup_3.1.0.exe"
    assert m["tamanho"] == len(b"conteudo do instalador")
    assert len(m["sha256"]) == 64 and m["sha256"].islower()
    # `notas` TEM que ser texto: a versão em PowerShell gravava uma lista aqui,
    # e o app espera uma string.
    assert isinstance(m["notas"], str)
    assert "Atualização automática" in m["notas"]


def test_sha256_confere_com_o_hashlib(tmp_path):
    import hashlib

    from tools.gerar_manifesto import sha256

    arq = tmp_path / "x.bin"
    dados = b"\x00\xff" * 100_000      # maior que o bloco de leitura
    arq.write_bytes(dados)
    assert sha256(arq) == hashlib.sha256(dados).hexdigest()


def test_versao_sem_bloco_no_changelog_nao_quebra(tmp_path):
    from tools.gerar_manifesto import montar

    instalador = tmp_path / "s.exe"
    instalador.write_bytes(b"x")
    assert montar(instalador, "9.9.9", "v9.9.9", CHANGELOG_EXEMPLO)["notas"] == ""


def test_corpo_do_release_avisa_quando_nao_ha_notas():
    from tools.gerar_manifesto import corpo_do_release

    assert "não trouxe notas" in corpo_do_release("9.9.9", "")
    assert "Como instalar" in corpo_do_release("3.1.0", "- algo")


def test_gera_os_dois_arquivos_com_console_cp1252(tmp_path):
    """O fim a fim: é este o passo que rodava no Windows e quebrava."""
    instalador = tmp_path / "DocManager_Itaipu_Setup_3.1.0.exe"
    instalador.write_bytes(b"0" * 1024)
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG_EXEMPLO, encoding="utf-8")
    manifesto, notas = tmp_path / "latest.json", tmp_path / "notas.md"

    r = rodar("tools/gerar_manifesto.py", "--instalador", instalador,
              "--versao", "3.1.0", "--tag", "v3.1.0", "--changelog", changelog,
              "--saida-manifesto", manifesto, "--saida-notas", notas)
    assert r.returncode == 0, f"stdout:\n{r.stdout}\nstderr:\n{r.stderr}"

    bruto = manifesto.read_bytes()
    assert not bruto.startswith(b"\xef\xbb\xbf"), "latest.json saiu com BOM — o app não lê"
    dados = json.loads(bruto.decode("utf-8"))
    assert dados["sha256"] and "Atualização" in dados["notas"]
    assert "Como instalar" in notas.read_text(encoding="utf-8")


def test_instalador_inexistente_falha_cedo(tmp_path):
    r = rodar("tools/gerar_manifesto.py", "--instalador", tmp_path / "nao_existe.exe",
              "--versao", "3.1.0", "--tag", "v3.1.0")
    assert r.returncode != 0
    assert "nao encontrado" in (r.stdout + r.stderr).lower()
