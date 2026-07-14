"""Leitura da planilha Controle de Documentos (KB §13, §24).

Estrutura e regras documentadas em `docs/controle_de_documentos.md`. Do Controle
só aproveitamos as DATAS de input manual (DATA PREVISTA DE EMISSÃO ACONEX e
REPROGRAMAÇÃO); todo o resto (status, título, códigos) tem prioridade do Aconex.

Leitura DINÂMICA e robusta a mudanças de layout:
  - o cabeçalho é localizado por âncora ("CODIFICAÇÃO ITAIPÚ (ACONEX)" ou
    "ITEM"+"NÚMERO INTERNO"), varrendo as primeiras linhas — não é fixo na 4ª;
  - as colunas casam por nome normalizado (sem acento, maiúsculas, sem espaços
    sobrando), tolerando pequenas variações de grafia;
  - as datas são lidas por coluna com day/month-first INFERIDO dos próprios
    valores (a planilha real mistura DD-MM-AAAA em uma coluna e M/D/AAAA em
    outra). `dtype=str` evita o '1234.0' fantasma em códigos numéricos.

A data de referência de cada documento (`data_ref`) é a REPROGRAMAÇÃO quando
preenchida, senão a DATA PREVISTA — usada por Mapa, Histórico e demais módulos.
"""
from __future__ import annotations

import re
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
from ..core.normalize import normalizar_codigo, remover_acentos


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
                if not cod:
                    continue
                # Código duplicado (mesmo doc em mais de uma linha/aba): a linha
                # COM data vence a sem data — uma linha vazia não pode "sombrear"
                # a que tem a informação (§24.8).
                atual = self._por_codigo.get(cod)
                if atual is None or (atual.data_ref is None and r.data_ref is not None):
                    self._por_codigo[cod] = r

    def linha_por_codigo(self, codigo) -> ControleRow | None:
        return self._por_codigo.get(normalizar_codigo(codigo))

    def data_ref_por_codigos(self, codigos) -> date | None:
        """Primeira data_ref encontrada varrendo os códigos históricos do doc."""
        for cod in codigos:
            r = self._por_codigo.get(normalizar_codigo(cod))
            if r is not None and r.data_ref is not None:
                return r.data_ref
        return None

    def datas_por_codigos(self, codigos) -> tuple[date | None, date | None]:
        """(data_prevista, data_reprogramada) da 1ª linha do Controle que casa."""
        for cod in codigos:
            r = self._por_codigo.get(normalizar_codigo(cod))
            if r is not None:
                return r.data_prevista, r.data_reprogramada
        return None, None

    def resolver_para_codigos(self, codigos, cod_itaipu_atual="", cod_cmi_atual="") -> ControleRow | None:
        """Linha do Controle para um documento, priorizando o código Itaipu atual,
        depois o CMI atual, depois qualquer código histórico que case."""
        for pref in (cod_itaipu_atual, cod_cmi_atual):
            if pref:
                r = self.linha_por_codigo(pref)
                if r is not None:
                    return r
        for cod in codigos:
            r = self._por_codigo.get(normalizar_codigo(cod))
            if r is not None:
                return r
        return None

    def __len__(self) -> int:
        return len(self.rows)


# --------------------------------------------------------------------------
# Leitura dinâmica
# --------------------------------------------------------------------------
def _norm(v) -> str:
    return remover_acentos(str(v)).strip().upper().replace("  ", " ")


def _linha_e_cabecalho(cells_norm: set[str]) -> bool:
    tem_cod = any("CODIFICACAO" in c and "ACONEX" in c for c in cells_norm)
    tem_item = "ITEM" in cells_norm and any("NUMERO INTERNO" in c for c in cells_norm)
    return tem_cod or tem_item


def _achar_header_row(caminho, sheet, max_scan=15) -> int:
    """Índice (base 0) da linha de cabeçalho; cai no padrão se não achar."""
    try:
        raw = pd.read_excel(caminho, sheet_name=sheet, header=None, nrows=max_scan, dtype=str)
    except Exception:  # noqa: BLE001
        return CTRL_HEADER_ROW
    for i in range(len(raw)):
        cells = {_norm(v) for v in raw.iloc[i].tolist() if isinstance(v, str) and v.strip()}
        if cells and _linha_e_cabecalho(cells):
            return i
    return CTRL_HEADER_ROW


def _col(df, *nomes_alvo) -> str | None:
    """Casa uma coluna por nome normalizado (igualdade e, depois, 'contém')."""
    alvos = [_norm(n) for n in nomes_alvo]
    norm_cols = {c: _norm(c) for c in df.columns}
    for c, nc in norm_cols.items():
        if nc in alvos:
            return c
    for c, nc in norm_cols.items():
        if any(a in nc for a in alvos):
            return c
    return None


def _infer_dayfirst(series) -> bool:
    """Infere day-first pela posição do componente > 12 (o real mistura formatos)."""
    for v in series:
        s = str(v).strip()
        if not s:
            continue
        partes = re.split(r"[/\-.]", s)
        if len(partes) < 2:
            continue
        try:
            a, b = int(partes[0]), int(partes[1])
        except ValueError:
            continue
        if a > 12:
            return True   # 1º componente é dia → DD/MM
        if b > 12:
            return False  # 2º componente é dia → MM/DD (formato US)
    return True           # ambíguo → padrão brasileiro


def _parse_col_datas(series) -> list[date | None]:
    if series is None:
        return []
    dayfirst = _infer_dayfirst(series)
    dt = pd.to_datetime(series, dayfirst=dayfirst, errors="coerce")
    return [None if pd.isna(x) else x.date() for x in dt]


def _ler_aba(caminho, aba, log) -> list[ControleRow]:
    """Lê UMA aba; devolve [] se a aba não tem cara de Controle (sem códigos)."""
    header = _achar_header_row(caminho, aba)
    df = pd.read_excel(caminho, sheet_name=aba, header=header, dtype=str).fillna("")

    col_it = _col(df, CTRL_COL_ITAIPU, "CODIFICACAO ITAIPU (ACONEX)")
    col_cmi = _col(df, CTRL_COL_CMI)
    if col_it is None and col_cmi is None:
        log(f"Controle: aba '{aba}' ignorada (sem colunas de código).")
        return []
    col_prev = _col(df, CTRL_COL_DATA_PREVISTA)
    col_reprog = _col(df, CTRL_COL_REPROGRAMACAO_HINT)
    col_desc = _col(df, "DESCRIÇÃO", "TÍTULO")
    if col_prev is None:
        log(f"Aviso: aba '{aba}' sem coluna '{CTRL_COL_DATA_PREVISTA}'.")
    if col_reprog is None:
        log(f"Aviso: aba '{aba}' sem coluna de REPROGRAMAÇÃO (precedência desativada).")

    prevista = _parse_col_datas(df[col_prev]) if col_prev else [None] * len(df)
    reprog = _parse_col_datas(df[col_reprog]) if col_reprog else [None] * len(df)

    rows: list[ControleRow] = []
    for i in range(len(df)):
        cod_it = str(df.iloc[i][col_it]).strip() if col_it else ""
        cod_cmi = str(df.iloc[i][col_cmi]).strip() if col_cmi else ""
        if not cod_it and not cod_cmi:
            continue
        rows.append(ControleRow(
            cod_itaipu=cod_it,
            cod_cmi=cod_cmi,
            titulo=str(df.iloc[i][col_desc]).strip() if col_desc else "",
            data_prevista=prevista[i],
            data_reprogramada=reprog[i],
        ))
    log(f"Controle: aba '{aba}' → {len(rows)} linhas (cabeçalho na linha {header + 1}).")
    return rows


def ler_controle(caminho, sheet=None, *, log_cb=None) -> ControleDocs:
    """Lê o Controle de Documentos de forma dinâmica, varrendo TODAS AS ABAS do
    arquivo (§24.8 — o Controle real espalha documentos em várias abas, ex.
    'Dados Planilhas Comissionamento'); abas sem colunas de código são
    ignoradas com aviso. `sheet` é aceito por compatibilidade, mas não limita a
    leitura. Nunca lança por coluna ausente — avisa via `log_cb` e segue."""
    def log(msg):
        if log_cb:
            log_cb(msg)

    try:
        abas = pd.ExcelFile(caminho).sheet_names
    except Exception:  # noqa: BLE001 — deixa o read_excel padrão reportar
        abas = [sheet if sheet is not None else 0]

    rows: list[ControleRow] = []
    for aba in abas:
        try:
            rows.extend(_ler_aba(caminho, aba, log))
        except Exception as e:  # noqa: BLE001 — uma aba ruim não derruba o resto
            log(f"Aviso: falha ao ler a aba '{aba}' do Controle: {e}")
    log(f"Controle de Documentos: {len(rows)} linhas com código ({len(abas)} abas varridas).")
    return ControleDocs(rows)
