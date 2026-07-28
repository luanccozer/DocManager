"""Leitura da planilha Controle de Documentos (KB §13, §24).

Estrutura e regras documentadas em `docs/controle_de_documentos.md`. Do Controle
aproveitamos as DATAS de input manual (DATA PREVISTA DE EMISSÃO ACONEX e
REPROGRAMAÇÃO) e a FASE DE PROJETO; todo o resto (status, título, códigos) tem
prioridade do Aconex.

Leitura DINÂMICA e robusta a mudanças de layout:
  - o cabeçalho é localizado por âncora ("CODIFICAÇÃO ITAIPÚ (ACONEX)" ou
    "ITEM"+"NÚMERO INTERNO"), varrendo as primeiras linhas — não é fixo na 4ª;
  - as colunas casam por nome normalizado (sem acento, maiúsculas, TODO espaço
    em branco colapsado — inclusive as QUEBRAS DE LINHA que o Excel esconde
    dentro do cabeçalho), em três níveis: igualdade → 'contém' → todas as
    palavras do alvo presentes (§24.12);
  - as datas são lidas por coluna com day/month-first INFERIDO por VOTAÇÃO nos
    próprios valores (a planilha real mistura DD-MM-AAAA em uma coluna e
    M/D/AAAA em outra), com suporte a serial do Excel. `dtype=str` evita o
    '1234.0' fantasma em códigos numéricos.

A busca do documento no Controle é em CASCATA (§24.12): chave exata → chave
frouxa (só alfanuméricos) → 'contém' (o Ctrl+F na mão). Em todos os níveis, a
linha COM data vence a linha sem data.

A data de referência de cada documento (`data_ref`) é a REPROGRAMAÇÃO quando
preenchida, senão a DATA PREVISTA — usada por Mapa, Doc List, Histórico e demais
módulos.
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
    fase: str = ""          # FASE DE PROJETO (§24.11) — vai ao histórico/Doc List
    emitido: str = ""       # EMITIDO / NÃO EMITIDO — para o log de divergência

    @property
    def data_ref(self) -> date | None:
        """REPROGRAMAÇÃO vence a DATA PREVISTA quando preenchida."""
        return self.data_reprogramada if self.data_reprogramada is not None else self.data_prevista

    @property
    def tem_data(self) -> bool:
        return self.data_prevista is not None or self.data_reprogramada is not None

    @property
    def esta_emitido(self) -> bool:
        """A coluna EMITIDO / NÃO EMITIDO diz que o doc foi emitido. 'NÃO
        EMITIDO' → False; 'EMITIDO'/'SIM' → True; vazio → False (sem informação)."""
        v = remover_acentos(str(self.emitido)).strip().upper()
        return v.startswith("EMITIDO") or v in ("SIM", "S", "YES")


# Sujeira comum de Excel dentro de códigos: espaços internos, NBSP, invisíveis.
_INVISIVEIS = ' ​‎‏﻿'  # NBSP, zero-width, marcas RTL/LTR, BOM
_RE_INVISIVEIS = re.compile('\\s' + '|[' + _INVISIVEIS + ']')
# Célula com MAIS DE UM código (quebra de linha / ';').
_RE_SEPARA_CODIGOS = re.compile(r"[\n\r;]+")
# Chave FROUXA: só letras e dígitos.
_RE_NAO_ALNUM = re.compile(r"[^0-9A-Z]")

# Tamanho mínimo do código para entrar nas buscas de fallback (frouxa/'contém').
# Códigos curtos casariam com qualquer coisa e produziriam lixo.
MIN_LEN_FALLBACK = 8


def chave_codigo(cod) -> str:
    """Chave de casamento tolerante ("como a busca na mão"): normalizar_codigo +
    remoção de TODO espaço/invisível interno (§24.8b)."""
    return _RE_INVISIVEIS.sub("", normalizar_codigo(cod))


def chave_frouxa(cod) -> str:
    """Chave de fallback: só alfanuméricos. Faz `#ST00=M00MYA10&EAB010` casar com
    `ST00-M00MYA10&EAB010` ou `ST00 M00MYA10 EAB010` — variações de pontuação e
    decoração que a digitação manual introduz nas duas planilhas (§24.12)."""
    return _RE_NAO_ALNUM.sub("", chave_codigo(cod))


def partes_codigo(cod) -> list[str]:
    """Divide célula multi-código (quebra de linha/';') em códigos individuais."""
    if cod is None:
        return []
    return [p.strip() for p in _RE_SEPARA_CODIGOS.split(str(cod)) if p.strip()]


@dataclass(frozen=True)
class MatchControle:
    """Resultado da busca de um documento no Controle, com a PROVENIÊNCIA.

    `via`: 'exato' | 'frouxo' | 'contido' | '' (não encontrado). Serve ao log de
    diagnóstico — o usuário precisa saber quando a data veio de um casamento
    tolerante, não de uma igualdade perfeita.
    """
    linha: ControleRow | None = None
    via: str = ""

    def __bool__(self) -> bool:
        return self.linha is not None


class ControleDocs:
    def __init__(self, rows: list[ControleRow]):
        self.rows = rows
        self._por_codigo: dict[str, ControleRow] = {}
        self._por_frouxa: dict[str, ControleRow] = {}
        for r in rows:
            for cod_bruto in (r.cod_itaipu, r.cod_cmi):
                for parte in partes_codigo(cod_bruto):
                    cod = chave_codigo(parte)
                    if not cod:
                        continue
                    # Código duplicado (mesmo doc em mais de uma linha/aba): a
                    # linha COM data vence a sem data — linha vazia não pode
                    # "sombrear" a que tem a informação (§24.8).
                    self._indexar(self._por_codigo, cod, r)
                    frouxa = chave_frouxa(parte)
                    if len(frouxa) >= MIN_LEN_FALLBACK:
                        self._indexar(self._por_frouxa, frouxa, r)

    @staticmethod
    def _indexar(destino: dict[str, ControleRow], chave: str, r: ControleRow) -> None:
        atual = destino.get(chave)
        if atual is None or (not atual.tem_data and r.tem_data):
            destino[chave] = r

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
        m = self.resolver(codigos)
        if m.linha is None:
            return None, None
        return m.linha.data_prevista, m.linha.data_reprogramada

    def buscar_contendo(self, codigo, *, min_len: int = MIN_LEN_FALLBACK) -> ControleRow | None:
        """Busca de ÚLTIMO recurso (§24.8c), como o Ctrl+F na mão: varre as
        linhas testando se a célula CONTÉM o código (ou o inverso) — pega
        células com decoração/texto extra em volta do código. Linha com data
        vence; `min_len` evita casamentos absurdos com códigos curtos.

        Compara também pela chave FROUXA (só alfanuméricos), para que diferenças
        de pontuação não escondam o documento."""
        alvo = chave_codigo(codigo)
        alvo_frouxo = chave_frouxa(codigo)
        if len(alvo) < min_len:
            return None
        primeira: ControleRow | None = None
        for r in self.rows:
            for cod_bruto in (r.cod_itaipu, r.cod_cmi):
                for parte in partes_codigo(cod_bruto):
                    cel = chave_codigo(parte)
                    if len(cel) < min_len:
                        continue
                    cel_frouxa = chave_frouxa(parte)
                    if (alvo in cel or cel in alvo
                            or (len(alvo_frouxo) >= min_len and len(cel_frouxa) >= min_len
                                and (alvo_frouxo in cel_frouxa or cel_frouxa in alvo_frouxo))):
                        if r.tem_data:
                            return r
                        if primeira is None:
                            primeira = r
        return primeira

    # ------------------------------------------------------------------
    def resolver(self, codigos, cod_itaipu_atual="", cod_cmi_atual="",
                 *, permitir_contido: bool = True) -> MatchControle:
        """Busca em CASCATA a linha do Controle de um documento (§24.12).

        Ordem dos códigos: Itaipu atual → CMI atual → históricos do Tracking.
        Ordem das estratégias: chave exata → chave frouxa → 'contém'.

        Em TODAS as etapas a linha COM data vence a linha sem data — um código
        que casa com uma linha vazia do Controle não pode mais esconder a linha
        preenchida de outro código do mesmo documento (causa raiz de §24.8b).
        `permitir_contido=False` desliga a varredura O(n) para chamadas em lote.
        """
        ordem: list[str] = []
        vistos: set[str] = set()
        for cod in (cod_itaipu_atual, cod_cmi_atual, *(codigos or ())):
            c = str(cod).strip() if cod else ""
            if c and c not in vistos:
                vistos.add(c)
                ordem.append(c)
        if not ordem:
            return MatchControle()

        fallback: MatchControle = MatchControle()
        for indice, via, chave in ((self._por_codigo, "exato", chave_codigo),
                                   (self._por_frouxa, "frouxo", chave_frouxa)):
            for cod in ordem:
                k = chave(cod)
                if not k or (via == "frouxo" and len(k) < MIN_LEN_FALLBACK):
                    continue
                r = indice.get(k)
                if r is None:
                    continue
                if r.tem_data:
                    return MatchControle(r, via)
                if fallback.linha is None:
                    fallback = MatchControle(r, via)

        if permitir_contido:
            for cod in ordem:
                r = self.buscar_contendo(cod)
                if r is None:
                    continue
                if r.tem_data:
                    return MatchControle(r, "contido")
                if fallback.linha is None:
                    fallback = MatchControle(r, "contido")
        return fallback

    def resolver_para_codigos(self, codigos, cod_itaipu_atual="", cod_cmi_atual="") -> ControleRow | None:
        """Linha do Controle para um documento (compatibilidade). Ver `resolver`."""
        return self.resolver(codigos, cod_itaipu_atual, cod_cmi_atual).linha

    def __len__(self) -> int:
        return len(self.rows)


# --------------------------------------------------------------------------
# Leitura dinâmica
# --------------------------------------------------------------------------
_RE_ESPACOS = re.compile(r"\s+")


def _norm(v) -> str:
    """Normaliza um texto de cabeçalho: sem acento, MAIÚSCULAS e com TODO espaço
    em branco colapsado em um só.

    O colapso é o ponto crítico: no Controle real o cabeçalho vem quebrado em
    duas linhas dentro da própria célula ("DATA PREVISTA DE\\nEMISSÃO ACONEX").
    A versão anterior só trocava dois espaços por um, então a quebra de linha
    sobrevivia e o `_col` nunca achava a coluna — o módulo rodava inteiro sem
    nenhuma data e sem erro nenhum (causa raiz do §24.8/§24.12).
    """
    s = remover_acentos(str(v)).replace("\xa0", " ")
    return _RE_ESPACOS.sub(" ", s).strip().upper()


def _linha_e_cabecalho(cells_norm: set[str]) -> bool:
    tem_cod = any("CODIFICACAO" in c and "ACONEX" in c for c in cells_norm)
    tem_cod_interno = (any("CODIFICACAO" in c for c in cells_norm)
                       and any("NUMERO INTERNO" in c for c in cells_norm))
    tem_item = "ITEM" in cells_norm and any("NUMERO INTERNO" in c for c in cells_norm)
    tem_datas = (any("DATA PREVISTA" in c for c in cells_norm)
                 and any("REPROGRAMA" in c for c in cells_norm))
    return tem_cod or tem_cod_interno or tem_item or tem_datas


def _achar_header_row(caminho, sheet, max_scan=25) -> int:
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


def _tokens(texto: str) -> list[str]:
    return [t for t in re.split(r"[^0-9A-Z]+", texto) if t]


def _casa_por_palavras(alvo: str, coluna: str) -> bool:
    """True se TODAS as palavras do alvo aparecem no cabeçalho da coluna (ordem
    livre), aceitando prefixo para palavras longas ('REPROGRAMA' ⊂
    'REPROGRAMACAO'). Terceiro nível do `_col`: sobrevive a cabeçalhos com
    palavras a mais ('DATA PREVISTA DE EMISSÃO NO ACONEX')."""
    alvo_toks, col_toks = _tokens(alvo), _tokens(coluna)
    if not alvo_toks or not col_toks:
        return False
    for a in alvo_toks:
        if not any(c == a or (len(a) >= 4 and c.startswith(a)) for c in col_toks):
            return False
    return True


def _col(df, *nomes_alvo) -> str | None:
    """Casa uma coluna por nome normalizado, em três níveis de tolerância:
    igualdade → 'contém' → todas as palavras do alvo presentes."""
    alvos = [_norm(n) for n in nomes_alvo]
    norm_cols = {c: _norm(c) for c in df.columns}
    for c, nc in norm_cols.items():
        if nc in alvos:
            return c
    for c, nc in norm_cols.items():
        if any(a in nc for a in alvos):
            return c
    for c, nc in norm_cols.items():
        if any(_casa_por_palavras(a, nc) for a in alvos):
            return c
    return None


# Serial de data do Excel: 20000 ≈ 1954, 60000 ≈ 2064. Fora dessa janela o
# número certamente não é uma data (é código, quantidade, etc.).
_SERIAL_MIN, _SERIAL_MAX = 20000, 60000
_EPOCA_EXCEL = pd.Timestamp("1899-12-30")
_RE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")

# Janela de sanidade de uma data de PLANEJAMENTO. Existe porque o pandas aceita
# alegremente coisas como '1234' (→ ano 1234) e '2' (→ dia 2 do mês corrente):
# um código ou uma quantidade que sobrou na coluna viraria "data prevista".
_ANO_MIN, _ANO_MAX = 1990, 2100


def _data_plausivel(d: date | None) -> date | None:
    return d if (d is not None and _ANO_MIN <= d.year <= _ANO_MAX) else None


def _infer_dayfirst(series) -> bool:
    """Infere day-first por VOTAÇÃO na coluna inteira (o Controle real mistura
    formatos ENTRE colunas e, às vezes, dentro da mesma).

    A versão anterior decidia no PRIMEIRO valor com componente > 12: bastava uma
    célula ISO ('2025-10-13 00:00:00', que é como o pandas devolve uma data real
    do Excel com dtype=str) no topo de uma coluna M/D/AAAA para a coluna inteira
    ser lida ao contrário. Datas ISO não votam — não são ambíguas.
    """
    dia_primeiro = mes_primeiro = 0
    for v in series:
        s = str(v).strip()
        if not s or _RE_ISO.match(s):
            continue
        partes = re.split(r"[/\-.]", s)
        if len(partes) < 2:
            continue
        try:
            a, b = int(partes[0]), int(partes[1])
        except ValueError:
            continue
        if a > 12:
            dia_primeiro += 1    # 1º componente é dia → DD/MM
        elif b > 12:
            mes_primeiro += 1    # 2º componente é dia → MM/DD (formato US)
    return dia_primeiro >= mes_primeiro   # empate/ambíguo → padrão brasileiro


def _para_datetime(series, dayfirst: bool):
    """`pd.to_datetime` vetorizado tolerando FORMATOS MISTOS na mesma coluna.

    Sem `format='mixed'`, o pandas infere UM formato a partir do primeiro valor
    e devolve NaT para todo o resto. Como o Controle real mistura datas de
    verdade do Excel (que com `dtype=str` chegam em ISO, '2025-10-13 00:00:00')
    com datas digitadas ('10/20/2025'), uma única célula ISA no topo bastava
    para a coluna inteira virar NaT — nenhum documento recebia data e nenhum
    erro aparecia.
    """
    try:
        return pd.to_datetime(series, dayfirst=dayfirst, errors="coerce", format="mixed")
    except (TypeError, ValueError):  # pandas antigo sem format='mixed'
        return pd.to_datetime(series, dayfirst=dayfirst, errors="coerce")


def _parse_valor_data(valor, dayfirst: bool) -> date | None:
    """Resgate individual do que a passada vetorizada não converteu: serial do
    Excel (célula de data lida como número) e formatos avulsos."""
    s = str(valor).strip()
    if not s or s.upper() in ("NAN", "NAT", "NONE"):
        return None
    try:
        n = float(s)
    except ValueError:
        pass
    else:
        if _SERIAL_MIN <= n <= _SERIAL_MAX:
            return (_EPOCA_EXCEL + pd.Timedelta(days=n)).date()
        return None
    try:
        x = pd.to_datetime(s, dayfirst=dayfirst, errors="coerce")
    except Exception:  # noqa: BLE001
        return None
    return None if pd.isna(x) else x.date()


def _parse_col_datas(series) -> list[date | None]:
    """Converte uma coluna de datas do Controle em `date`s, tolerando texto em
    formatos mistos, datas reais do Excel (ISO) e serial numérico."""
    if series is None:
        return []
    dayfirst = _infer_dayfirst(series)
    dt = _para_datetime(series, dayfirst)
    saida: list[date | None] = []
    for original, convertida in zip(series, dt):
        if not pd.isna(convertida):
            saida.append(_data_plausivel(convertida.date()))
        else:
            saida.append(_data_plausivel(_parse_valor_data(original, dayfirst)))
    return saida


def _ler_aba(caminho, aba, log) -> list[ControleRow]:
    """Lê UMA aba; devolve [] se a aba não tem cara de Controle (sem códigos)."""
    header = _achar_header_row(caminho, aba)
    df = pd.read_excel(caminho, sheet_name=aba, header=header, dtype=str).fillna("")

    col_it = _col(df, CTRL_COL_ITAIPU, "CODIFICACAO ITAIPU (ACONEX)", "CODIFICACAO ITAIPU")
    col_cmi = _col(df, CTRL_COL_CMI)
    if col_it is None and col_cmi is None:
        log(f"Controle: aba '{aba}' ignorada (sem colunas de código).")
        return []
    col_prev = _col(df, CTRL_COL_DATA_PREVISTA, "DATA PREVISTA EMISSAO", "DATA PREVISTA")
    col_reprog = _col(df, CTRL_COL_REPROGRAMACAO_HINT)
    col_desc = _col(df, "DESCRIÇÃO", "TÍTULO")
    col_fase = _col(df, "FASE DE PROJETO", "FASE DEL PROYECTO", "FASE DE PROYECTO")
    col_emit = _col(df, "EMITIDO / NÃO EMITIDO", "EMITIDO / NAO EMITIDO", "EMITIDO")
    if col_prev is None:
        log(f"Aviso: aba '{aba}' sem coluna '{CTRL_COL_DATA_PREVISTA}'. "
            f"Cabeçalhos lidos: {', '.join(str(c) for c in list(df.columns)[:25])}")
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
            fase=str(df.iloc[i][col_fase]).strip() if col_fase else "",
            emitido=str(df.iloc[i][col_emit]).strip() if col_emit else "",
        ))
    if col_prev is not None or col_reprog is not None:
        achadas = [n for n, c in (("DATA PREVISTA", col_prev), ("REPROGRAMAÇÃO", col_reprog)) if c]
        log(f"Controle: colunas de data localizadas → {', '.join(achadas)}.")
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
    if rows and n_com_data == 0:
        log("ATENÇÃO: nenhuma linha do Controle tem data. Confira se a aba selecionada "
            "é a certa e se as colunas DATA PREVISTA DE EMISSÃO ACONEX / REPROGRAMAÇÃO "
            "existem nela.")
    return ControleDocs(rows)
