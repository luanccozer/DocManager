"""Calcula o número da próxima versão do DocManager a partir das tags do Git.

Uso (na raiz do repositório):

    python .claude/skills/versionamento/proxima_versao.py            # mostra a atual e as 3 opções
    python .claude/skills/versionamento/proxima_versao.py patch      # imprime só o número (ex.: 3.6.1)
    python .claude/skills/versionamento/proxima_versao.py minor
    python .claude/skills/versionamento/proxima_versao.py major
    python .claude/skills/versionamento/proxima_versao.py --checar 3.6.1

A base é sempre a ÚLTIMA VERSÃO NORMAL publicada (tag vX.Y.Z sem sufixo). As
rc (vX.Y.Z-rc.N) são ensaios: não contam como base, mas são listadas para
mostrar o que está em teste. As tags vêm do `origin` (as locais podem estar
desatualizadas); sem rede, cai para as tags locais e avisa.

`--checar X.Y.Z` confere, antes de criar a tag, que:
  • X.Y.Z é exatamente um passo (patch, minor ou major) depois da última normal;
  • a tag vX.Y.Z ainda não existe;
  • o primeiro bloco do CHANGELOG.md é o "## X.Y.Z - AAAA-MM-DD".
Sai com código 1 se algo não bater.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)(-[0-9A-Za-z.]+)?$")
BLOCO = re.compile(r"^## (\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?) - \d{4}-\d{2}-\d{2}\s*$", re.M)

for fluxo in (sys.stdout, sys.stderr):  # console do Windows em cp1252
    try:
        fluxo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _tags() -> list[str]:
    try:
        saida = subprocess.run(["git", "ls-remote", "--tags", "origin"], cwd=RAIZ,
                               capture_output=True, text=True, timeout=30, check=True).stdout
        return [ln.split("refs/tags/", 1)[1].removesuffix("^{}")
                for ln in saida.splitlines() if "refs/tags/" in ln]
    except (subprocess.SubprocessError, OSError):
        print("aviso: sem acesso ao origin, usando as tags locais (podem estar velhas).",
              file=sys.stderr)
        return subprocess.run(["git", "tag"], cwd=RAIZ, capture_output=True,
                              text=True, check=True).stdout.split()


def _versoes() -> tuple[list[tuple[int, int, int]], list[str]]:
    normais, rcs = set(), set()
    for tag in _tags():
        if m := TAG.match(tag):
            if m.group(4):
                rcs.add(tag[1:])
            else:
                normais.add(tuple(int(x) for x in m.groups()[:3]))
    return sorted(normais), sorted(rcs)


def proximas(atual: tuple[int, int, int]) -> dict[str, str]:
    ma, mi, pa = atual
    return {"patch": f"{ma}.{mi}.{pa + 1}",
            "minor": f"{ma}.{mi + 1}.0",
            "major": f"{ma + 1}.0.0"}


def _texto(v: tuple[int, int, int]) -> str:
    return ".".join(map(str, v))


def checar(versao: str, atual: tuple[int, int, int], rcs: list[str]) -> int:
    erros = []
    opcoes = proximas(atual)
    base = versao.split("-", 1)[0]
    if base not in opcoes.values():
        erros.append(f"{versao} não é o próximo passo depois da {_texto(atual)}. "
                     f"Opções válidas: {', '.join(f'{v} ({k})' for k, v in opcoes.items())}.")
    existentes = {_texto(v) for v in _versoes()[0]} | set(rcs)
    if versao in existentes:
        erros.append(f"a tag v{versao} já existe - número publicado não se reaproveita.")
    if "-" not in versao:  # rc não precisa de bloco no CHANGELOG
        changelog = (RAIZ / "CHANGELOG.md").read_text(encoding="utf-8")
        primeiro = BLOCO.search(changelog)
        if not primeiro or primeiro.group(1) != versao:
            achado = primeiro.group(1) if primeiro else "nenhum"
            erros.append(f"o primeiro bloco do CHANGELOG.md é {achado}, não {versao}. "
                         f"Acrescente '## {versao} - AAAA-MM-DD' no topo.")
    if erros:
        for e in erros:
            print(f"ERRO: {e}")
        return 1
    print(f"OK: v{versao} pode ser criada.")
    return 0


def main(argv: list[str]) -> int:
    normais, rcs = _versoes()
    if not normais:
        print("Nenhuma tag vX.Y.Z normal encontrada.", file=sys.stderr)
        return 1
    atual = normais[-1]
    if len(argv) == 2 and argv[0] == "--checar":
        return checar(argv[1].removeprefix("v"), atual, rcs)
    if len(argv) == 1 and argv[0] in ("patch", "minor", "major"):
        print(proximas(atual)[argv[0]])
        return 0
    if argv:
        print(__doc__)
        return 2
    print(f"Última versão publicada: {_texto(atual)}")
    em_teste = [r for r in rcs if tuple(int(x) for x in r.split("-")[0].split(".")) > atual]
    if em_teste:
        print(f"Ensaios (rc) acima dela: {', '.join(em_teste)}")
    for nivel, versao in proximas(atual).items():
        print(f"  {nivel:<5} -> {versao}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
