"""Reparo mecânico dos scripts corrompidos pelo copy-paste do chat.

O copy-paste quebrou strings contendo cores hex em duas linhas físicas:

    fg_color="
    #5A5A5A", hover_color="
    #404040")

O reparo rejunta cada par numa linha só, guiado por ast.parse (que aponta a
linha da aspa aberta). Invariante de segurança: o texto reparado, removidas
as quebras de linha, é IDENTICO ao original - nada além de junções.

Os originais corrompidos estão preservados no commit baseline do git; este
script lê da raiz do projeto e grava as cópias reparadas em legacy/
(renomeando aconex_reviwer.py -> aconex_reviewer.py, que é o nome que o
launcher importa).

Uso: python tools/repair_corrupted.py
"""
from __future__ import annotations

import ast
import py_compile
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LEGACY = RAIZ / "legacy"

# (arquivo na raiz, nome no legacy/)
MAPA_ARQUIVOS = [
    ("launcher.py", "launcher.py"),
    ("aconex_reviwer.py", "aconex_reviewer.py"),  # typo corrigido: launcher importa 'aconex_reviewer'
    ("data_manager.py", "data_manager.py"),
    ("dash_ib.py", "dash_ib.py"),
]

RE_LINHA_HEX = re.compile(r"^[ \t]*#[0-9A-Fa-f]{6}")
RE_FIM_ASPA_ABERTA = re.compile(r"""["'][ \t]*$""")
MAX_JUNCOES = 200


def _junta(linhas: list[str], i: int) -> None:
    """Remove a quebra de linha entre linhas[i] e linhas[i+1]."""
    linhas[i] = linhas[i].rstrip("\r\n") + linhas[i + 1]
    del linhas[i + 1]


def reparar_sintaxe(linhas: list[str], nome: str) -> int:
    """Rejunta strings quebradas até ast.parse passar. Retorna nº de junções."""
    juncoes = 0
    while True:
        try:
            ast.parse("".join(linhas))
            return juncoes
        except SyntaxError as e:
            msg = e.msg or ""
            if "unterminated string literal" not in msg:
                raise RuntimeError(f"{nome}: SyntaxError inesperado (linha {e.lineno}): {msg}")
            i = (e.lineno or 0) - 1
            if not (0 <= i < len(linhas) - 1):
                raise RuntimeError(f"{nome}: erro aponta linha {e.lineno}, fora do arquivo")
            # Guarda anti-disparo-errado: só rejunta o padrão conhecido da corrupção
            if not RE_LINHA_HEX.match(linhas[i + 1]):
                raise RuntimeError(
                    f"{nome}: linha {e.lineno + 1} não começa com cor hex - inspeção manual necessária"
                )
            if not RE_FIM_ASPA_ABERTA.search(linhas[i].rstrip("\r\n")):
                raise RuntimeError(
                    f"{nome}: linha {e.lineno} não termina em aspa aberta - inspeção manual necessária"
                )
            _junta(linhas, i)
            juncoes += 1
            if juncoes > MAX_JUNCOES:
                raise RuntimeError(f"{nome}: excesso de junções (> {MAX_JUNCOES})")


def reparar_cosmetico(linhas: list[str], nome: str) -> int:
    """Rejunta quebras remanescentes que NÃO geram SyntaxError (ex.: dentro do
    CSS em string tripla do dash_ib). Regra: linha começando com cor hex cuja
    linha anterior não é comentário. Junções comentário->comentário (inócuas)
    ficam como estão. Semanticamente é no-op; re-valida o parse ao final."""
    juncoes = 0
    i = 1
    while i < len(linhas):
        if RE_LINHA_HEX.match(linhas[i]) and not linhas[i - 1].lstrip().startswith("#"):
            _junta(linhas, i - 1)
            juncoes += 1
        else:
            i += 1
    if juncoes:
        ast.parse("".join(linhas))  # nunca deve falhar; junções dentro de string
    return juncoes


def reparar_arquivo(origem: Path, destino: Path) -> tuple[int, int]:
    with open(origem, "r", encoding="utf-8", newline="") as f:
        texto = f.read()
    linhas = texto.splitlines(keepends=True)

    j_sintaxe = reparar_sintaxe(linhas, origem.name)
    j_cosmetico = reparar_cosmetico(linhas, origem.name)
    reparado = "".join(linhas)

    # INVARIANTE: nada além de quebras de linha foi alterado
    if texto.replace("\r", "").replace("\n", "") != reparado.replace("\r", "").replace("\n", ""):
        raise RuntimeError(f"{origem.name}: invariante violada - conteúdo alterado além de junções!")

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="") as f:
        f.write(reparado)
    py_compile.compile(str(destino), doraise=True)
    return j_sintaxe, j_cosmetico


def main() -> int:
    print(f"Reparando para {LEGACY}")
    for nome_origem, nome_destino in MAPA_ARQUIVOS:
        origem = RAIZ / nome_origem
        if not origem.exists():
            print(f"  {nome_origem}: NÃO ENCONTRADO na raiz (originais estão no commit baseline)")
            return 1
        j_sin, j_cos = reparar_arquivo(origem, LEGACY / nome_destino)
        print(f"  {nome_origem} -> legacy/{nome_destino}: {j_sin} junções de sintaxe, {j_cos} cosméticas - OK")
    (LEGACY / "__init__.py").write_text(
        '"""Scripts legados reparados e congelados - oráculo dos testes diferenciais."""\n',
        encoding="utf-8",
    )
    print("Todos os arquivos reparados, compilados e validados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
