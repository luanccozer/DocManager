"""Prepara a árvore para o PyInstaller: carimba a versão e embute o token.

Rodado pelo workflow ANTES do build (e dá para rodar na mão para testar):

    python tools/preparar_build.py 3.1.0 --origem github-actions --commit a1b2c3d

Escreve dois arquivos:

  • `docmanager/_build_info.py` - a versão do binário, tirada da TAG. É o que o
    verificador de atualização compara com o último Release. Sem este passo, um
    executável marcado 3.1.0 continuaria oferecendo "atualizar para a 3.1.0"
    eternamente.

  • `docmanager/_update_auth.py` - o token de leitura do repositório (privado),
    ofuscado. Está no `.gitignore`: o token entra no build, NUNCA no Git. O
    valor vem da variável de ambiente `DOCMANAGER_UPDATE_TOKEN` (no CI, do
    segredo `UPDATE_TOKEN`); sem ela o arquivo sai vazio e o build simplesmente
    não checa atualizações - que é o certo para um build local.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


def _saida_utf8() -> None:
    """Força UTF-8 no stdout/stderr.

    No Windows o Python escreve no console em cp1252 (a code page ANSI), e um
    `print` com "versão →" morre com UnicodeEncodeError - o build falha por
    causa de uma MENSAGEM, depois de já ter rodado lint e testes. Acontece tanto
    no runner do GitHub quanto no `build.bat` de qualquer máquina da empresa.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # saída redirecionada/substituída
            pass


_saida_utf8()

from docmanager._ofuscacao import ofuscar  # noqa: E402 - depende do sys.path acima

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?$")


def escrever_build_info(versao: str, origem: str, commit: str) -> Path:
    destino = RAIZ / "docmanager" / "_build_info.py"
    texto = destino.read_text(encoding="utf-8")
    substituicoes = {
        "VERSAO": versao,
        "COMMIT": commit[:7],
        "DATA_BUILD": date.today().isoformat(),
        "ORIGEM": origem,
    }
    for chave, valor in substituicoes.items():
        novo = f'{chave} = "{valor}"'
        texto, n = re.subn(rf'^{chave} = ".*"$', novo, texto, count=1, flags=re.M)
        if n != 1:
            raise SystemExit(f"_build_info.py: não achei a linha de {chave} para substituir.")
    destino.write_text(texto, encoding="utf-8")
    return destino


CABECALHO_AUTH = '''"""Token de atualização embutido no build - GERADO, não edite.

Escrito por `tools/preparar_build.py` a partir do segredo `UPDATE_TOKEN` do
repositório. Está no `.gitignore` de propósito: assim nenhum token chega ao Git,
nem por engano. Em build local o arquivo não existe (ou vem vazio) e o app
apenas não procura atualizações.
"""
'''


def escrever_token(token: str) -> Path:
    destino = RAIZ / "docmanager" / "_update_auth.py"
    valor = ofuscar(token) if token else ""
    destino.write_text(f'{CABECALHO_AUTH}\nTOKEN_OFUSCADO = "{valor}"\n', encoding="utf-8")
    return destino


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("versao", help="versão do build, sem o 'v' (ex.: 3.1.0)")
    ap.add_argument("--origem", default="local", help="github-actions | local")
    ap.add_argument("--commit", default="", help="SHA do commit do build")
    args = ap.parse_args()

    versao = args.versao.strip().lstrip("vV")
    if not SEMVER.match(versao):
        raise SystemExit(f"Versão inválida: '{args.versao}'. Use MAJOR.MINOR.PATCH "
                         f"(ex.: 3.1.0), opcionalmente com -beta.1.")

    print(f"versão  → {escrever_build_info(versao, args.origem, args.commit)}  ({versao})")
    token = os.getenv("DOCMANAGER_UPDATE_TOKEN", "").strip()
    escrever_token(token)
    print("token   → docmanager/_update_auth.py  "
          + (f"({len(token)} caracteres, ofuscado)" if token
             else "(VAZIO - este build não terá atualização automática)"))


if __name__ == "__main__":
    main()
