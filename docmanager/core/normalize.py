"""Normalizações canônicas de revisão, código e texto (KB §3, §6).

Toda regra de normalização vive AQUI — nunca duplicar em views/relatórios.
"""
from __future__ import annotations

import re
import unicodedata

_RE_FLOAT_FANTASMA = re.compile(r"^\d+\.0$")


def normalizar_revisao(rev) -> str:
    """Porta fiel do legado (data_manager L112-115).

    upper, remove TODO 'R', strip, e ljust(3, 'z'). O preenchimento com 'z'
    produz a ordenação lexicográfica correta do ciclo de vida:
        '0AA' < '0Az' (=0A) < '0zz' (=0) < '1Az' (=1A) < '1zz' (=1)
    (ciclo interno < revisão-letra < revisão definitiva, por família).
    """
    if not rev:
        return ""
    r = str(rev).upper().replace("R", "").strip()
    return r.ljust(3, "z")


REV_LIMITE_0A = normalizar_revisao("0A")  # '0Az' — limite da "primeira emissão da vida útil"


def sort_key_revisao(rev) -> str:
    """LEGADO — NÃO usar para ordenar o ciclo de vida. Porta da chave de 3 níveis
    (data_manager L1192-1196). ERRADA para famílias: joga TODOS os números secos
    ('0','1','2' = aprovações) para o fim, depois das letras de famílias
    posteriores (ex.: '0' cai depois de '2A'). Para a ordem correta do ciclo use
    `normalizar_revisao` (ljust-'z'). Mantida só para reproduzir o legado no
    harness de regressão.

        letras puras ('A')  -> '00_A'   (primeiro)
        revisões-letra ('0A') -> '10_0A' (segundo)
        numéricas ('0','12') -> '20_000' (terceiro, zfill 3)
    """
    r = str(rev).strip().upper()
    if r.isalpha():
        return "00_" + r
    if not r.isdigit():
        return "10_" + r
    return "20_" + r.zfill(3)


def normalizar_codigo(cod) -> str:
    """Normalização de códigos de documento (Itaipu/CMI) para matching.

    strip + upper + remoção do '.0' fantasma que o Excel cria quando um
    código puramente numérico é lido como float (ex.: '12345.0' -> '12345').
    Só remove o sufixo se o restante for todo dígito — códigos reais com
    pontos ('8501.20.15400.P') passam intactos.
    """
    if cod is None:
        return ""
    s = str(cod).strip().upper()
    if s in ("NAN", "NONE", "NAT"):
        return ""
    if _RE_FLOAT_FANTASMA.fullmatch(s):
        s = s[:-2]
    return s


def remover_acentos(texto) -> str:
    """Remove acentos preservando o resto (comparações 'sem acento, upper')."""
    if texto is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c))
