"""Identidade do BUILD - escrita pelo CI, nunca editada à mão em release.

Esta é a fonte única da versão do app. O workflow `.github/workflows/release.yml`
reescreve este arquivo a partir da tag do Git (`v3.1.0` → `VERSAO = "3.1.0"`)
antes de rodar o PyInstaller, de modo que o executável SEMPRE sabe qual versão
ele é - que é justamente o que o verificador de atualização compara com o
último Release do GitHub.

Por que não vem mais do `.env` (como até a v3.0.0): o `.env` é um arquivo do
USUÁRIO e sobrevive à atualização. Se a versão viesse de lá, o app recém
atualizado continuaria se declarando "3.0.0" e ficaria baixando a mesma
atualização para sempre. Versão é característica do BINÁRIO, não do usuário.

Os valores abaixo são só o rótulo dos builds locais (feitos pelo `build.bat`).
"""
from __future__ import annotations

# Sobrescrito pelo CI a partir da tag. Em build local fica como está.
VERSAO = "3.3.0"

# Commit curto e data do build (o CI preenche; local fica vazio).
COMMIT = ""
DATA_BUILD = ""

# "github-actions" quando gerado pelo workflow; "local" no build.bat.
ORIGEM = "local"


def descricao() -> str:
    """Linha de diagnóstico, ex.: '3.1.0 (github-actions · a1b2c3d · 2026-09-18)'."""
    extras = [p for p in (ORIGEM, COMMIT, DATA_BUILD) if p]
    return f"{VERSAO} ({' · '.join(extras)})" if extras else VERSAO
