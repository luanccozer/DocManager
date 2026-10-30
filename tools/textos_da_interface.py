"""Os textos de tela (`t("...")`) e quais faltam traduzir.

    python tools/textos_da_interface.py                 # lista todos
    python tools/textos_da_interface.py --faltando es   # os que faltam em es.json

Lê o código pela árvore sintática (`ast`), não por expressão regular: assim
um texto partido em várias linhas ("a" "b") sai inteiro, como o Python o vê.
Mesma ferramenta da CMI Suite e do SIG-FT.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "docmanager"
IDIOMAS = PACOTE / "ui" / "recursos" / "idiomas"


def textos() -> list[str]:
    achados: set[str] = set()
    for arquivo in sorted(PACOTE.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
                    and no.func.id in ("t", "marcar")
                    and no.args and isinstance(no.args[0], ast.Constant)
                    and isinstance(no.args[0].value, str)):
                achados.add(no.args[0].value)
    return sorted(achados)


def faltando(idioma: str) -> list[str]:
    try:
        traducao = json.loads((IDIOMAS / f"{idioma}.json").read_text(encoding="utf-8"))
    except OSError:
        traducao = {}
    return [texto for texto in textos() if not traducao.get(texto)]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--faltando":
        lista = faltando(sys.argv[2])
    else:
        lista = textos()
    print(json.dumps(lista, ensure_ascii=False, indent=1))
