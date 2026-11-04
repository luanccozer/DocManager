"""Senha das telas restritas (Upload de documentos, pedido de 2026-11-04).

É uma trava de uso, não um cofre: o robô do Upload grava no Aconex e no Box, e a
senha impede que alguém o abra sem querer ou sem ter sido orientado. O código
guarda só o SHA-256 da senha (com um sal fixo), nunca o texto dela; trocar a
senha é trocar `HASH_UPLOAD` (`python -c "import hashlib; print(hashlib.sha256(
('docmanager-upload-v1' + 'nova').encode()).hexdigest())"`).
"""
from __future__ import annotations

import hashlib
import hmac

SAL = "docmanager-upload-v1"
HASH_UPLOAD = "587017a75c13c6c109c313d54de0f9620108a5faa952e7cef780fc555466832d"


def confere(senha: str, esperado: str = HASH_UPLOAD) -> bool:
    calculado = hashlib.sha256((SAL + (senha or "")).encode("utf-8")).hexdigest()
    return hmac.compare_digest(calculado, esperado)
