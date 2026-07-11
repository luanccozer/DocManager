"""Leitura da planilha Controle de Documentos (KB §13).

Corrige dois bugs latentes do legado (data_manager L426-430): lê tudo como
`dtype=str` (códigos numéricos não viram '1234.0') e faz parse de datas com
`dayfirst=True` (não inverte dia/mês).

Novidade (req. do usuário): lê a coluna REPROGRAMAÇÃO. A data de referência de
cada documento (`data_ref`) é a REPROGRAMAÇÃO quando preenchida, senão a DATA
PREVISTA DE EMISSÃO ACONEX.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from ..core.constants import (
    CTRL_COL_CMI,
    CTRL_COL_DATA_PREVISTA,
    CTRL_COL_ITAIPU,
    CTRL_COL_REPROGRAMACAO_HINT,
    CTRL_HEADER_ROW,
)
from ..core.normalize import normalizar_codigo


@dataclass(frozen=True)
class ControleRow:
    cod_itaipu: str
    cod_cmi: str
    titulo: str
    data_prevista: date | None
    data_reprogramada: date | None

    @property
    def data_ref(self) -> date | None:
        """REPROGRAMAÇÃO vence a DATA PREVISTA quando preenchida."""
        return self.data_reprogramada if self.data_reprogramada is not None else self.data_prevista


class ControleDocs:
    def __init__(self, rows: list[ControleRow]):
        self.rows = rows
        self._por_codigo: dict[str, ControleRow] = {}
        for r in rows:
            for cod in (normalizar_codigo(r.cod_itaipu), normalizar_codigo(r.cod_cmi)):
                if cod:
                    self._por_codigo.setdefault(cod, r)

    def linha_por_codigo(self, codigo) -> ControleRow | None:
        return self._por_codigo.get(normalizar_codigo(codigo))

    def data_ref_por_codigos(self, codigos) -> date | None:
        """Primeira data_ref encontrada varrendo os códigos históricos do doc."""
        for cod in codigos:
            r = self._por_codigo.get(normalizar_codigo(cod))
            if r is not None and r.data_ref is not None:
                return r.data_ref
        return None

    def __len__(self) -> int:
        return len(self.rows)


def _achar_coluna_reprogramacao(colunas) -> str | None:
    for c in colunas:
        if CTRL_COL_REPROGRAMACAO_HINT in str(c).strip().upper():
            return c
    return None


def _to_date(valor) -> date | None:
    if valor is None:
        return None
    dt = pd.to_datetime(valor, dayfirst=True, errors="coerce")
    return None if pd.isna(dt) else dt.date()


def ler_controle(caminho, sheet=0, *, log_cb=None) -> ControleDocs:
    """Lê o Controle de Documentos. Nunca lança por coluna ausente — apenas
    avisa via `log_cb` e segue com o que houver."""
    def log(msg):
        if log_cb:
            log_cb(msg)

    df = pd.read_excel(caminho, sheet_name=sheet, header=CTRL_HEADER_ROW, dtype=str).fillna("")
    col_reprog = _achar_coluna_reprogramacao(df.columns)

    if CTRL_COL_ITAIPU not in df.columns and CTRL_COL_CMI not in df.columns:
        log(f"Aviso: nenhuma coluna de código ('{CTRL_COL_ITAIPU}'/'{CTRL_COL_CMI}') no Controle.")
    if CTRL_COL_DATA_PREVISTA not in df.columns:
        log(f"Aviso: coluna '{CTRL_COL_DATA_PREVISTA}' ausente no Controle.")
    if col_reprog is None:
        log("Aviso: coluna de REPROGRAMAÇÃO não encontrada no Controle (precedência desativada).")

    rows: list[ControleRow] = []
    for _, r in df.iterrows():
        cod_it = str(r.get(CTRL_COL_ITAIPU, "")).strip()
        cod_cmi = str(r.get(CTRL_COL_CMI, "")).strip()
        if not cod_it and not cod_cmi:
            continue
        rows.append(ControleRow(
            cod_itaipu=cod_it,
            cod_cmi=cod_cmi,
            titulo=str(r.get("DESCRIÇÃO", r.get("TÍTULO", ""))).strip(),
            data_prevista=_to_date(r.get(CTRL_COL_DATA_PREVISTA, "")),
            data_reprogramada=_to_date(r.get(col_reprog, "")) if col_reprog else None,
        ))
    log(f"Controle de Documentos: {len(rows)} linhas com código.")
    return ControleDocs(rows)
