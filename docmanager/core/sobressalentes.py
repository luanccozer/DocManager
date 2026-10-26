"""Lista de Sobressalentes com Preço: o status 'For Partial Handover'.

A lista de sobressalentes com preço tem um status próprio no Aconex, 'For
Partial Handover' (entrega parcial). Pedido do usuário (2026-10-26):

| Rótulo no Aconex       | Vale como                        | Consolidado              |
|------------------------|----------------------------------|--------------------------|
| For Partial Handover   | aprovação (veredito da Itaipu)   | APROVAÇÃO INTERMEDIÁRIA  |

Diferente dos rótulos do comissionamento (core/comissionamento.py), ele NÃO
equivale a um status que já existe: o STATUS REAL mostra 'For Partial Handover'
e o consolidado sai APROVAÇÃO INTERMEDIÁRIA - aprovado, mas ainda não o
definitivo. No motor de status ele entra no grupo das aprovações (vence a
batalha de versões como qualquer aprovação) e nos KPIs conta como sucesso
(fecha o relógio de análise da Itaipu).

Como a lista é reconhecida
--------------------------
Pelo TÍTULO (contém `SOBRESSALENTE` e `PREÇO`, sem ligar para acento, caixa ou
plural) OU pelo CÓDIGO do documento (Itaipu ou CMI) terminado em `PB021` - o
código RDSPP da lista termina sempre assim.

Fora da lista o rótulo NÃO é reconhecido: um status desconhecido num documento
comum continua caindo onde sempre caiu (e o consolidado ERRO denuncia).
"""
from __future__ import annotations

import pandas as pd

from .constants import COL_DOC_CMI, COL_DOC_ITAIPU, COL_STATUS, COL_TITULO, STATUS_FOR_PARTIAL_HANDOVER
from .normalize import remover_acentos

SUFIXO_CODIGO = "PB021"


def _chave(texto) -> str:
    """Texto comparável: sem acento, MAIÚSCULAS, espaços simples."""
    return " ".join(remover_acentos(texto).upper().split())


_CHAVE_FPH = _chave(STATUS_FOR_PARTIAL_HANDOVER)


def e_lista_sobressalentes(titulo="", *codigos) -> bool:
    """True se o documento é a lista de sobressalentes com preço.

    `codigos`: os códigos do documento (Itaipu, CMI) - basta um terminar em
    `PB021`. Aceita 'SOBRESSALENTE' e a grafia com um S só ('SOBRESALENTE').
    """
    t = _chave(titulo)
    if ("SOBRESSALENTE" in t or "SOBRESALENTE" in t) and "PRECO" in t:
        return True
    return any(str(c).strip().upper().endswith(SUFIXO_CODIGO) for c in codigos if isinstance(c, str))


def _linha_e_lista(row: pd.Series) -> bool:
    return e_lista_sobressalentes(row.get(COL_TITULO, ""), row.get(COL_DOC_ITAIPU, ""), row.get(COL_DOC_CMI, ""))


def _so_da_lista(df: pd.DataFrame, mask: pd.Series) -> pd.Series:
    """`mask` restrita às linhas da lista. Só avalia as linhas já marcadas - a
    base inteira do Aconex tem dezenas de milhares de linhas."""
    da_lista = df.loc[mask].apply(_linha_e_lista, axis=1)
    return mask & da_lista.reindex(df.index, fill_value=False).astype(bool)


def historico_e_lista(df_tracking: pd.DataFrame) -> bool:
    """O documento (histórico de UM Tracking ID) é a lista de sobressalentes?
    Olha a primeira linha, como `historico_e_planilha` do comissionamento."""
    if df_tracking.empty:
        return False
    return _linha_e_lista(df_tracking.iloc[0])


def e_for_partial_handover(status) -> bool:
    return _chave(status) == _CHAVE_FPH


def normalizar_historico(df: pd.DataFrame, *, lista: bool | None = None) -> pd.DataFrame:
    """Cópia do histórico com 'For Partial Handover' no rótulo canônico.

    O Aconex pode gravar o rótulo com caixa ou espaços diferentes; os motores
    comparam o texto exato, então ele é padronizado aqui - SÓ nas linhas da
    lista de sobressalentes. `lista=None` decide linha a linha (bases com vários
    documentos); `lista=True/False` vale para o histórico inteiro de UM
    documento. Devolve o próprio `df` quando não há nada a mexer.
    """
    if df.empty or COL_STATUS not in df.columns or lista is False:
        return df
    alvo = df[COL_STATUS].map(e_for_partial_handover)
    if not alvo.any():
        return df
    if lista is None:
        alvo = _so_da_lista(df, alvo)
        if not alvo.any():
            return df
    df = df.copy()
    df.loc[alvo, COL_STATUS] = STATUS_FOR_PARTIAL_HANDOVER
    return df


def descartar_fora_da_lista(df: pd.DataFrame) -> pd.DataFrame:
    """Tira as linhas 'For Partial Handover' de documentos que NÃO são a lista.

    Para as bases que filtram por uma lista de status válidos: lá o rótulo é
    válido, mas só para a lista de sobressalentes.
    """
    if df.empty or COL_STATUS not in df.columns:
        return df
    fph = df[COL_STATUS] == STATUS_FOR_PARTIAL_HANDOVER
    if not fph.any():
        return df
    fora = fph & ~_so_da_lista(df, fph)
    return df[~fora] if fora.any() else df
