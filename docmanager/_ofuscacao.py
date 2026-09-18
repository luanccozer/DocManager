"""Ofuscação do token de atualização embutido no build.

Mora num módulo próprio, SEM nenhum import do pacote, porque duas partes
distantes precisam dele e não podem divergir: o `services/updater.py` (que
desfaz, em tempo de execução) e o `tools/preparar_build.py` (que faz, dentro do
GitHub Actions). Se as duas implementações se separassem, o token gerado num
build deixaria de ser legível pelo app - falha silenciosa, difícil de achar.

**Isto não é criptografia.** É um XOR com chave fixa, e a chave está logo
abaixo. O único objetivo é o token não aparecer num `strings DocManager.exe`.
Quem tiver o executável e quiser, extrai. Por isso o token embutido tem que ser
um PAT *fine-grained* somente leitura e restrito a este repositório - ver a
seção "Rotação do token" do BUILD.md.
"""
from __future__ import annotations

import base64

CHAVE = b"DocManagerItaipu"


def _xor(dados: bytes) -> bytes:
    return bytes(b ^ CHAVE[i % len(CHAVE)] for i, b in enumerate(dados))


def ofuscar(token: str) -> str:
    """Texto claro → o que vai para `_update_auth.py` (feito pelo CI)."""
    return base64.b64encode(_xor(token.encode("utf-8"))).decode("ascii")


def desofuscar(texto_b64: str) -> str:
    """O inverso, usado pelo app ao procurar atualizações."""
    return _xor(base64.b64decode(texto_b64.encode("ascii"))).decode("utf-8")
