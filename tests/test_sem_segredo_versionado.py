"""Nenhum segredo pode estar sob controle de versão (guarda trazida do Corella Suite).

No Corella isto já aconteceu: o `.env` com o client_secret real do Aconex foi
commitado e empurrado. O `.gitignore` sozinho NÃO impede - ele só vale para
arquivo ainda não rastreado; um arquivo que entrou no índice continua sendo
versionado a cada alteração, ignorado ou não.

O DocManager lida com dois segredos: o Client Secret do Aconex (o `.env`
legado, o `credenciais.json` do cofre) e o token de leitura dos Releases
(`docmanager/_update_auth.py`, que o build gera). Estes testes falham se algum
deles - ou um token do GitHub colado num arquivo qualquer - voltar ao índice.
"""
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent

# Arquivos que NUNCA podem ser rastreados, em qualquer pasta. O `.env.example` é
# o modelo, sem valor real, e continua versionado de propósito.
PROIBIDOS = {".env", ".env.local", ".env.production", "secrets.json", "credentials.json",
             "credenciais.json", "_update_auth.py", "pip_corporativo.txt"}

# Tokens do GitHub no formato real (o PAT fine-grained tem 22 + 59 caracteres
# depois do prefixo; o clássico, 36). Um texto de exemplo nos testes, mais
# curto, não casa.
TOKEN_GITHUB = re.compile(r"github_pat_[A-Za-z0-9]{22}_[A-Za-z0-9]{59}|gh[pousr]_[A-Za-z0-9]{36}")
EXTENSOES_TEXTO = {".py", ".md", ".txt", ".yml", ".yaml", ".json", ".iss", ".bat", ".spec",
                   ".toml", ".cfg", ".ini", ".example", ".ps1", ".sh"}


def _arquivos_rastreados() -> list[str]:
    try:
        saida = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True,
                               text=True, check=False)
    except FileNotFoundError:
        return []
    return [linha.strip() for linha in saida.stdout.splitlines() if linha.strip()]


@pytest.fixture(scope="module")
def rastreados():
    lista = _arquivos_rastreados()
    if not lista:
        pytest.skip("não é um clone git")
    return lista


def test_nenhum_arquivo_de_credencial_esta_rastreado(rastreados):
    encontrados = sorted(p for p in rastreados if Path(p).name in PROIBIDOS)
    assert not encontrados, (
        f"arquivo de credencial sob controle de versão: {encontrados}. Rode "
        "`git rm --cached <arquivo>` - isso tira do índice e MANTÉM o arquivo no "
        "disco. Depois revogue o segredo que vazou (o push já o publicou).")


def test_nenhum_token_do_github_em_arquivo_rastreado(rastreados):
    achados = []
    for rel in rastreados:
        caminho = RAIZ / rel
        if caminho.suffix.lower() not in EXTENSOES_TEXTO or not caminho.is_file():
            continue
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        achados += [f"{rel}: {m.group()[:14]}…" for m in TOKEN_GITHUB.finditer(texto)]
    assert not achados, f"token do GitHub em arquivo versionado: {achados}. Revogue-o."


def test_o_modelo_env_example_continua_versionado(rastreados):
    """Sem ele, quem ainda usa o .env legado não sabe o formato."""
    assert ".env.example" in rastreados


def test_o_env_example_nao_tem_segredo_de_verdade():
    """O modelo existe para mostrar o FORMATO, nunca um valor usável. As
    linhas são todas comentadas; mesmo comentado, um valor real ali vaza."""
    modelo = RAIZ / ".env.example"
    if not modelo.is_file():
        pytest.skip(".env.example ausente")
    for numero, linha in enumerate(modelo.read_text(encoding="utf-8").splitlines(), 1):
        linha = linha.lstrip("# ").strip()
        if "=" not in linha or " " in linha.partition("=")[0]:
            continue
        chave, _, valor = linha.partition("=")
        valor = valor.strip().strip("'\"")
        if not valor or not chave.upper().startswith(("SECRET", "DOCMANAGER_UPDATE_TOKEN")):
            continue
        parece_placeholder = (set(valor.lower()) <= set("x") or valor.startswith("<")
                              or valor.endswith("...") or len(valor) < 12)
        assert parece_placeholder, (
            f".env.example linha {numero}: {chave} parece ter um valor real "
            f"({len(valor)} caracteres). O modelo só pode ter placeholder.")
