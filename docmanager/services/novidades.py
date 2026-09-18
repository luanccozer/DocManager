"""Leitura do `CHANGELOG.md` — fonte única do "o que há de novo".

Antes a Home tinha uma lista fixa no código (`home_view.NOVIDADES`) e o release
seria escrito à mão: duas listas para manter em dia, que iam divergir no
primeiro dia corrido. Agora as duas saem daqui — a Home mostra o bloco da versão
instalada e o workflow usa o mesmo bloco como corpo do Release no GitHub.

Formato esperado (o de sempre, "Keep a Changelog" enxuto):

    ## 3.1.0 — 2026-09-18
    - primeira novidade
    - segunda novidade

    ## 3.0.0 — 2026-08-02
    - ...

Tudo aqui é função pura sobre texto: sem rede, sem Tk, testável direto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# "## 3.1.0 — 2026-09-18", "## v3.1.0 - 2026-09-18" ou só "## 3.1.0".
_CABECALHO = re.compile(r"^##\s+v?(?P<versao>\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.]+)?)"
                        r"\s*(?:[—–-]\s*(?P<data>.+?))?\s*$")
_ITEM = re.compile(r"^\s*[-*+]\s+(?P<texto>.+?)\s*$")


@dataclass(frozen=True)
class Bloco:
    versao: str
    data: str = ""
    itens: list[str] = field(default_factory=list)

    def titulo(self) -> str:
        return f"v{self.versao}" + (f" · {self.data}" if self.data else "")

    def markdown(self) -> str:
        """O bloco de volta em Markdown — é o corpo do Release no GitHub."""
        return "\n".join(f"- {i}" for i in self.itens)


def analisar(texto: str) -> list[Bloco]:
    """Todos os blocos do CHANGELOG, na ordem em que aparecem (mais novo primeiro)."""
    blocos: list[Bloco] = []
    atual: str | None = None
    data = ""
    itens: list[str] = []

    def fechar():
        if atual is not None:
            blocos.append(Bloco(versao=atual, data=data, itens=list(itens)))

    for linha in (texto or "").splitlines():
        if (m := _CABECALHO.match(linha)):
            fechar()
            atual, data, itens = m.group("versao"), (m.group("data") or "").strip(), []
            continue
        if atual is not None and (mi := _ITEM.match(linha)):
            itens.append(mi.group("texto"))
    fechar()
    return blocos


def bloco_de(texto: str, versao: str) -> Bloco | None:
    """O bloco de uma versão específica. Compara só os números (ignora 'v' e
    sufixos de pré-versão), para `3.1.0` achar `## v3.1.0`."""
    alvo = str(versao or "").lstrip("vV").split("-")[0]
    for b in analisar(texto):
        if b.versao.split("-")[0] == alvo:
            return b
    return None


def caminho_changelog() -> str:
    """Onde está o CHANGELOG.md, no executável ou no projeto.

    No `.exe` ele é embutido na raiz do bundle (ver `docmanager.spec`) e o
    `resource_path` acha direto. Em desenvolvimento o arquivo mora na RAIZ do
    repositório, um nível acima do pacote — daí o segundo candidato.
    """
    import os

    from .config import resource_path

    candidatos = [
        resource_path("CHANGELOG.md"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "CHANGELOG.md"),
    ]
    return next((c for c in candidatos if os.path.isfile(c)), candidatos[0])


def ler(versao: str | None = None) -> Bloco | None:
    """Bloco da `versao` (padrão: a versão instalada); cai para o mais recente.

    A queda para o mais recente cobre o build de desenvolvimento, cuja versão
    ainda não tem entrada no CHANGELOG — melhor mostrar as últimas novidades do
    que uma Home vazia.
    """
    from .. import __version__

    try:
        with open(caminho_changelog(), encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return None
    if (b := bloco_de(texto, versao or __version__)) is not None:
        return b
    blocos = analisar(texto)
    return blocos[0] if blocos else None
