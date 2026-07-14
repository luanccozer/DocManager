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

    @property
    def tem_data(self) -> bool:
        return self.data_prevista is not None or self.data_reprogramada is not None


# Sujeira comum de Excel dentro de códigos: espaços internos, NBSP, invisíveis.
_INVISIVEIS = '\xa0\u200b\u200e\u200f\ufeff'  # NBSP, zero-width, marcas RTL/LTR, BOM
_RE_INVISIVEIS = re.compile('\\s' + '|[' + _INVISIVEIS + ']')
# Célula com MAIS DE UM código (quebra de linha / ';').
_RE_SEPARA_CODIGOS = re.compile(r"[\n\r;]+")


def chave_codigo(cod) -> str:
    """Chave de casamento tolerante ("como a busca na mão"): normalizar_codigo +
    remoção de TODO espaço/invisível interno (§24.8b)."""
    return _RE_INVISIVEIS.sub("", normalizar_codigo(cod))


def partes_codigo(cod) -> list[str]:
    """Divide célula multi-código (quebra de linha/';') em códigos individuais."""
    if cod is None:
        return []
    return [p.strip() for p in _RE_SEPARA_CODIGOS.split(str(cod)) if p.strip()]


class ControleDocs:
    def __init__(self, rows: list[ControleRow]):
        self.rows = rows
        self._por_codigo: dict[str, ControleRow] = {}
        for r in rows:
            for cod_bruto in (r.cod_itaipu, r.cod_cmi):
                for parte in partes_codigo(cod_bruto):
                    cod = chave_codigo(parte)
                    if not cod:
                        continue
                    # Código duplicado (mesmo doc em mais de uma linha/aba): a
                    # linha COM data vence a sem data — linha vazia não pode
                    # "sombrear" a que tem a informação (§24.8).
                    atual = self._por_codigo.get(cod)
                    if atual is None or (not atual.tem_data and r.tem_data):
                        self._por_codigo[cod] = r

    def linha_por_codigo(self, codigo) -> ControleRow | None:
        return self._por_codigo.get(chave_codigo(codigo))

    def data_ref_por_codigos(self, codigos) -> date | None:
        """Primeira data_ref encontrada varrendo os códigos históricos do doc."""
        for cod in codigos:
            r = self._por_codigo.get(chave_codigo(cod))
            if r is not None and r.data_ref is not None:
                return r.data_ref
        return None

    def datas_por_codigos(self, codigos) -> tuple[date | None, date | None]:
        """(data_prevista, data_reprogramada) do documento. Os códigos chegam em
        ordem arbitrária (set), então uma linha SEM data não pode encerrar a
        busca: prefere a 1ª linha COM alguma data; senão a 1ª que casou (§24.8b)."""
        primeira: ControleRow | None = None
        for cod in codigos:
            r = self._por_codigo.get(chave_codigo(cod))
            if r is None:
                continue
            if r.tem_data:
                return r.data_prevista, r.data_reprogramada
            if primeira is None:
                primeira = r
        if primeira is not None:
            return primeira.data_prevista, primeira.data_reprogramada
        return None, None

    def buscar_contendo(self, codigo, *, min_len: int = 8) -> ControleRow | None:
        """Busca de ÚLTIMO recurso (§24.8c), como o Ctrl+F na mão: varre as
        linhas testando se a célula CONTÉM o código (ou o inverso) — pega
        células com decoração/texto extra em volta do código. Linha com data
        vence; `min_len` evita casamentos absurdos com códigos curtos."""
        alvo = chave_codigo(codigo)
        if len(alvo) < min_len:
            return None
        primeira: ControleRow | None = None
        for r in self.rows:
            for cod_bruto in (r.cod_itaipu, r.cod_cmi):
                for parte in partes_codigo(cod_bruto):
                    cel = chave_codigo(parte)
                    if len(cel) < min_len:
                        continue
                    if alvo in cel or cel in alvo:
                        if r.tem_data:
                            return r
                        if primeira is None:
                            primeira = r
        return primeira

    def resolver_para_codigos(self, codigos, cod_itaipu_atual="", cod_cmi_atual="") -> ControleRow | None:
        """Linha do Controle para um documento, priorizando o código Itaipu atual,
        depois o CMI atual, depois códigos históricos (com data > sem data)."""
        for pref in (cod_itaipu_atual, cod_cmi_atual):
            if pref:
                r = self.linha_por_codigo(pref)
                if r is not None:
                    return r
        primeira: ControleRow | None = None
        for cod in codigos:
            r = self._por_codigo.get(chave_codigo(cod))
            if r is None:
                continue
            if r.tem_data:
                return r
            if primeira is None:
                primeira = r
        return primeira

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


def ler_controle(caminho, sheet=0, *, log_cb=None) -> ControleDocs:
    """Lê o Controle de Documentos de forma dinâmica, da ABA SELECIONADA na
    interface (decisão do usuário, §24.8c: o seletor de aba existe exatamente
    para apontar a aba certa — não varremos as demais). Nunca lança por coluna
    ausente — avisa via `log_cb` e segue."""
    def log(msg):
        if log_cb:
            log_cb(msg)

    aba = sheet if sheet is not None else 0
    rows = _ler_aba(caminho, aba, log)
    n_com_data = sum(1 for r in rows if r.tem_data)
    log(f"Controle de Documentos: {len(rows)} linhas com código na aba selecionada "
        f"({n_com_data} com alguma data).")
    return ControleDocs(rows)
