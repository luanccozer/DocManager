"""Escrita cirúrgica num .xlsx: mexe só no XML que precisa mudar (ADR 0002).

Por que não o openpyxl: abrir e salvar a planilha de pendências (sem alterar
nada) PERDEU os estilos e cores dos gráficos, as configurações de impressão e
as opções dos gráficos dinâmicos, reescreveu tabelas dinâmicas e desenhos e
fez a coluna oculta reaparecer (medido em 11/2026). Pandas e XlsxWriter
recriam o arquivo, pior ainda.

Aqui:
- a LEITURA usa `zipfile` + `xml.etree.ElementTree`;
- a ESCRITA edita o TEXTO do XML: só o `<sheetData>` e o `<dimension>` da aba,
  o `ref` da tabela (e do `autoFilter`/`sortState` dela) e, quando um estilo
  novo é necessário, um `<xf>` acrescentado NO FIM de `<cellXfs>`;
- todas as outras partes do zip são copiadas byte a byte, na mesma ordem, com
  uma CÓPIA do `ZipInfo` de origem (passar o próprio `info` faz o `zipfile`
  alterá-lo ao gravar, e a leitura da origem passa a falhar com Bad CRC-32).

Nunca reserializar com ElementTree: ele renomeia os prefixos (`x14ac`, `xr`...)
e quebra o `mc:Ignorable`, e o Excel acusa arquivo corrompido.

Este módulo não sabe nada de pendências: acha UMA tabela pela coluna-chave,
recusa o que não dá para deslocar com segurança (`recusas`) e aplica uma
`Edicao` (linhas novas no topo do corpo, células trocadas, estilo de linha).
"""
from __future__ import annotations

import copy
import html
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from ..core.normalize import normalizar_cabecalho

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_N = f"{{{NS}}}"

LIMITE_TEXTO = 32767
MARCA_CORTE = "… [cortado pelo DocManager]"
_EPOCA_EXCEL = date(1899, 12, 30)
_FORMATOS_DATA_EMBUTIDOS = set(range(14, 23)) | {45, 46, 47}


class ErroXlsx(ValueError):
    """A planilha não pode ser atualizada com segurança; o motivo é para a tela."""


class _Manter:
    def __repr__(self):
        return "MANTER"


MANTER = _Manter()   # numa edição de célula: mantém o valor, troca só o estilo


# --- Endereços -------------------------------------------------------------------

def letra(col: int) -> str:
    s = ""
    while col:
        col, resto = divmod(col - 1, 26)
        s = chr(65 + resto) + s
    return s


def numero_coluna(letras: str) -> int:
    n = 0
    for ch in letras.upper():
        n = n * 26 + ord(ch) - 64
    return n


_RE_REF = re.compile(r"^\$?([A-Z]{1,3})\$?(\d+)$")


def _celula(ref: str) -> tuple[int, int]:
    m = _RE_REF.match(ref.strip())
    if not m:
        raise ErroXlsx(f"endereço de célula inesperado: {ref!r}")
    return numero_coluna(m.group(1)), int(m.group(2))


def _intervalo(ref: str) -> tuple[int, int, int, int]:
    """'A4:V132' → (col_ini, lin_ini, col_fim, lin_fim)."""
    partes = ref.split(":")
    c1, l1 = _celula(partes[0])
    c2, l2 = _celula(partes[-1])
    return c1, l1, c2, l2


def _ref_intervalo(c1, l1, c2, l2) -> str:
    return f"{letra(c1)}{l1}:{letra(c2)}{l2}"


# --- Modelo lido -------------------------------------------------------------------

@dataclass
class Celula:
    col: int
    s: str | None
    t: str | None
    valor: object          # str, int, float, bool, date ou None
    xml: str               # o texto original do <c>


@dataclass
class Linha:
    r: int
    abertura: str          # o texto do <row ...> (ou <row .../>)
    xml: str               # o texto inteiro da linha
    attrs: dict[str, str]
    celulas: dict[int, Celula] = field(default_factory=dict)
    segmentos: list[str] = field(default_factory=list)   # os <c> na ordem original

    @property
    def s(self) -> str | None:
        return self.attrs.get("s")


@dataclass
class Tabela:
    parte: str
    xml: str
    nome: str
    ref: str
    colunas: list[str]
    col_ini: int
    cabecalho: int
    col_fim: int
    ultima: int

    @property
    def primeira(self) -> int:
        return self.cabecalho + 1

    def coluna(self, nome: str) -> int | None:
        alvo = normalizar_cabecalho(nome)
        for i, c in enumerate(self.colunas):
            if normalizar_cabecalho(c) == alvo:
                return self.col_ini + i
        return None


class Estilos:
    """O `<cellXfs>` do `styles.xml`: qual fill e se é data, por índice; e os `<xf>`
    que precisarem ser acrescentados (no FIM - nenhum índice existente muda)."""

    def __init__(self, xml: str):
        self.xml = xml
        m = re.search(r"<cellXfs\b[^>]*>(.*?)</cellXfs>", xml, re.S)
        if not m:
            raise ErroXlsx("a planilha não tem a lista de estilos de célula (cellXfs)")
        self._bloco = m
        self.xfs: list[str] = re.findall(r"<xf\b[^>]*?/>|<xf\b[^>]*>.*?</xf>", m.group(1), re.S)
        self.novos: list[str] = []
        self._datas_personalizadas = self._formatos_de_data(xml)

    @staticmethod
    def _formatos_de_data(xml: str) -> set[int]:
        ids = set()
        for m in re.finditer(r'<numFmt\b[^>]*numFmtId="(\d+)"[^>]*formatCode="([^"]*)"', xml):
            codigo = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", _desescapar(m.group(2))).lower()
            if re.search(r"[dmy]", codigo):
                ids.add(int(m.group(1)))
        return ids

    def _xf(self, s) -> str:
        i = int(s or 0)
        todos = self.xfs + self.novos
        return todos[i] if 0 <= i < len(todos) else ""

    @staticmethod
    def _attr(xf: str, nome: str, padrao: str = "0") -> str:
        m = re.search(rf'\s{nome}="([^"]*)"', xf.split(">", 1)[0])
        return m.group(1) if m else padrao

    def fill(self, s) -> str:
        return self._attr(self._xf(s), "fillId")

    def e_data(self, s) -> bool:
        n = int(self._attr(self._xf(s), "numFmtId"))
        return n in _FORMATOS_DATA_EMBUTIDOS or n in self._datas_personalizadas

    def _assinatura(self, xf: str):
        abertura, _, resto = xf.partition(">")
        attrs = dict(re.findall(r'\s([\w:]+)="([^"]*)"', abertura))
        for ignorado in ("fillId", "applyFill"):
            attrs.pop(ignorado, None)
        return tuple(sorted(attrs.items())), re.sub(r"\s+", " ", resto.strip())

    def com_fill(self, s, fill_id: str) -> str:
        """O índice de um `<xf>` igual ao de `s` em tudo, menos o fill = `fill_id`;
        acrescenta um no fim se não existir."""
        base = self._xf(s)
        if self.fill(s) == fill_id:
            return str(int(s or 0))
        alvo = self._assinatura(base)
        for i, xf in enumerate(self.xfs + self.novos):
            if self._attr(xf, "fillId") == fill_id and self._assinatura(xf) == alvo:
                return str(i)
        novo = _trocar_attr(base, "fillId", fill_id, so_abertura=True)
        novo = _trocar_attr(novo, "applyFill", "1", so_abertura=True)
        self.novos.append(novo)
        return str(len(self.xfs) + len(self.novos) - 1)

    def xml_novo(self) -> str | None:
        """O `styles.xml` com os `<xf>` novos, ou None se nada mudou."""
        if not self.novos:
            return None
        m = self._bloco
        abertura = re.match(r"<cellXfs\b[^>]*>", m.group(0)).group(0)
        nova_abertura = _trocar_attr(abertura, "count", str(len(self.xfs) + len(self.novos)),
                                     so_abertura=True)
        fim_interno = m.end(1)
        return (self.xml[:m.start()] + nova_abertura + self.xml[m.start(1):fim_interno]
                + "".join(self.novos) + self.xml[fim_interno:])


@dataclass
class Pasta:
    caminho: Path
    infos: list[zipfile.ZipInfo]
    partes: dict[str, bytes]
    aba_nome: str
    aba_parte: str
    aba_xml: str
    tabela: Tabela
    estilos: Estilos
    linhas: list[Linha]
    antes: str                 # texto da aba até o conteúdo do <sheetData> (inclusive a abertura)
    depois: str                # do </sheetData> até o fim
    entre: list[str]           # o que há entre as linhas (espaços), len = len(linhas) + 1
    nomes_abas: list[str]

    def linha(self, r: int) -> Linha | None:
        return next((x for x in self.linhas if x.r == r), None)

    def corpo(self) -> list[Linha]:
        return [x for x in self.linhas if self.tabela.primeira <= x.r <= self.tabela.ultima]


# --- Leitura -----------------------------------------------------------------------

def _desescapar(texto: str) -> str:
    """Entidades do XML, inclusive as numéricas (`&#202;`) que o openpyxl escreve."""
    return html.unescape(texto)


def _texto(no) -> str:
    """Texto de um <si> ou <is>: o <t> direto ou os <t> dos runs <r> (sem a fonética)."""
    if no is None:
        return ""
    direto = no.find(f"{_N}t")
    if direto is not None:
        return direto.text or ""
    return "".join((t.text or "") for r in no.findall(f"{_N}r") for t in r.findall(f"{_N}t"))


def _rels(partes: dict[str, bytes], parte: str) -> dict[str, tuple[str, str]]:
    """Id → (tipo, alvo absoluto) das relações de `parte`."""
    pasta, nome = posixpath.split(parte)
    rels = posixpath.join(pasta, "_rels", nome + ".rels")
    if rels not in partes:
        return {}
    out = {}
    for rel in ET.fromstring(partes[rels]).findall(f"{{{NS_PKG}}}Relationship"):
        alvo = rel.get("Target", "")
        alvo = alvo.lstrip("/") if alvo.startswith("/") else posixpath.normpath(posixpath.join(pasta, alvo))
        out[rel.get("Id")] = (rel.get("Type", "").rsplit("/", 1)[-1], alvo)
    return out


def _attrs(abertura: str) -> dict[str, str]:
    return dict(re.findall(r'\s([\w:]+)="([^"]*)"', abertura))


_RE_LINHA = re.compile(r"<row\b[^>]*?/>|<row\b[^>]*>.*?</row>", re.S)
_RE_CEL = re.compile(r"<c\b[^>]*?/>|<c\b[^>]*>.*?</c>", re.S)


def ler(caminho, coluna_chave: str) -> Pasta:
    """Abre o pacote e acha a ÚNICA tabela que tem `coluna_chave`. Só lê."""
    caminho = Path(caminho)
    try:
        with zipfile.ZipFile(caminho) as z:
            infos = z.infolist()
            partes = {i.filename: z.read(i) for i in infos}
    except (zipfile.BadZipFile, OSError) as e:
        raise ErroXlsx(f"o arquivo não é um .xlsx que o app consiga ler ({e})") from e
    if "xl/workbook.xml" not in partes:
        raise ErroXlsx("o arquivo não é uma pasta de trabalho do Excel (.xlsx)")

    wb = ET.fromstring(partes["xl/workbook.xml"])
    rels_wb = _rels(partes, "xl/workbook.xml")
    abas = []
    for sh in wb.iter(f"{_N}sheet"):
        rid = sh.get(f"{{{NS_R}}}id")
        tipo, alvo = rels_wb.get(rid, ("", ""))
        if tipo == "worksheet" and alvo in partes:
            abas.append((sh.get("name", ""), alvo))

    achadas = []
    for nome, parte in abas:
        for tipo, alvo in _rels(partes, parte).values():
            if tipo != "table" or alvo not in partes:
                continue
            tb = ET.fromstring(partes[alvo])
            colunas = [c.get("name", "") for c in tb.iter(f"{_N}tableColumn")]
            if any(normalizar_cabecalho(c) == normalizar_cabecalho(coluna_chave) for c in colunas):
                achadas.append((nome, parte, alvo, tb, colunas))
    if not achadas:
        raise ErroXlsx(f"nenhuma Tabela do Excel com a coluna '{coluna_chave}' foi encontrada. "
                       "Os dados precisam estar formatados como Tabela (Página Inicial → "
                       "Formatar como Tabela).")
    if len(achadas) > 1:
        raise ErroXlsx(f"há {len(achadas)} Tabelas do Excel com a coluna '{coluna_chave}' "
                       f"({', '.join(a[3].get('name', '?') for a in achadas)}); deixe só uma.")
    aba_nome, aba_parte, tabela_parte, tb, colunas = achadas[0]
    c1, l1, c2, l2 = _intervalo(tb.get("ref", ""))
    if c2 - c1 + 1 != len(colunas):
        raise ErroXlsx("a definição da tabela não bate com o intervalo dela; abra e salve no Excel")
    tabela = Tabela(tabela_parte, partes[tabela_parte].decode("utf-8"), tb.get("name", ""),
                    tb.get("ref", ""), colunas, c1, l1, c2, l2)

    estilos = Estilos(partes.get("xl/styles.xml", b"").decode("utf-8")) \
        if "xl/styles.xml" in partes else Estilos("<cellXfs count=\"1\"><xf/></cellXfs>")
    compartilhados = []
    if "xl/sharedStrings.xml" in partes:
        compartilhados = [_texto(si) for si in
                          ET.fromstring(partes["xl/sharedStrings.xml"]).findall(f"{_N}si")]

    aba_xml = partes[aba_parte].decode("utf-8")
    linhas, antes, depois, entre = _ler_linhas(aba_xml, estilos, compartilhados)
    return Pasta(caminho, infos, partes, aba_nome, aba_parte, aba_xml, tabela, estilos,
                 linhas, antes, depois, entre, [a[0] for a in abas])


def _ler_linhas(aba_xml: str, estilos: Estilos, compartilhados: list[str]):
    m = re.search(r"<sheetData\s*/>|<sheetData\b[^>]*>(.*?)</sheetData>", aba_xml, re.S)
    if not m:
        raise ErroXlsx("a aba da tabela não tem a área de dados (sheetData)")
    if m.group(1) is None:   # <sheetData/>
        return [], aba_xml[:m.start()] + "<sheetData>", "</sheetData>" + aba_xml[m.end():], [""]
    corpo = m.group(1)
    antes = aba_xml[:m.start(1)]
    depois = aba_xml[m.end(1):]

    linhas, entre, pos = [], [], 0
    for lm in _RE_LINHA.finditer(corpo):
        entre.append(corpo[pos:lm.start()])
        pos = lm.end()
        xml = lm.group(0)
        abertura = re.match(r"<row\b[^>]*>", xml).group(0)
        attrs = _attrs(abertura)
        if "r" not in attrs:
            raise ErroXlsx("há uma linha sem número (atributo r) na aba; abra e salve no Excel")
        linha = Linha(int(attrs["r"]), abertura, xml, attrs)
        interno = xml[len(abertura):-len("</row>")] if not abertura.endswith("/>") else ""
        resto = _RE_CEL.sub("", interno)
        if resto.strip():
            raise ErroXlsx(f"a linha {linha.r} tem conteúdo que o app não reconhece")
        for cm in _RE_CEL.finditer(interno):
            cxml = cm.group(0)
            ca = _attrs(re.match(r"<c\b[^>]*>", cxml).group(0))
            if "r" not in ca:
                raise ErroXlsx(f"há uma célula sem endereço na linha {linha.r}; abra e salve no Excel")
            col, lin = _celula(ca["r"])
            if lin != linha.r:
                raise ErroXlsx(f"a célula {ca['r']} está dentro da linha {linha.r}")
            linha.celulas[col] = Celula(col, ca.get("s"), ca.get("t"),
                                        _valor(cxml, ca, estilos, compartilhados), cxml)
            linha.segmentos.append(cxml)
        linhas.append(linha)
    entre.append(corpo[pos:])
    if any(e.strip() for e in entre):
        raise ErroXlsx("a área de dados da aba tem conteúdo que o app não reconhece")
    return linhas, antes, depois, entre


def _valor(cxml: str, attrs: dict, estilos: Estilos, compartilhados: list[str]):
    t = attrs.get("t")
    if t == "inlineStr":
        m = re.search(r"<is>.*?</is>", cxml, re.S)
        return _texto(ET.fromstring(m.group(0).replace("<is>", f'<is xmlns="{NS}">', 1))) if m else ""
    m = re.search(r"<v>(.*?)</v>", cxml, re.S)
    if not m:
        return None
    texto = _desescapar(m.group(1))
    if t == "s":
        try:
            return compartilhados[int(texto)]
        except (ValueError, IndexError):
            return ""
    if t in ("str", "e"):
        return texto
    if t == "b":
        return texto.strip() == "1"
    try:
        n = float(texto)
    except ValueError:
        return texto
    if estilos.e_data(attrs.get("s")):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=n)).date()
        except OverflowError:
            return n
    return int(n) if n.is_integer() else n


# --- Recusas (8.2 da spec) ----------------------------------------------------------

_PROIBIDOS_NA_ABA = (
    ("mergeCells", "células mescladas"),
    ("conditionalFormatting", "formatação condicional"),
    ("dataValidations", "lista suspensa ou validação de dados"),
    ("hyperlinks", "hyperlink"),
    ("legacyDrawing", "comentário de célula"),
    ("drawing", "gráfico ou imagem na própria aba de dados"),
    ("rowBreaks", "quebra de página manual"),
    ("sheetProtection", "aba protegida"),
)


def _ref_aba(nome: str):
    """Regex de referência de CÉLULA à aba `nome` (`Aba!A1`, `'Aba x'!$A$1:$B$9`, `Aba!3:5`).

    Só o formato de célula conta: o `<c:pivotSource>` dos gráficos dinâmicos cita
    o NOME DO ARQUIVO, e um teste ingênuo de substring recusaria a planilha real."""
    citado = "'" + re.escape(nome.replace("'", "''")) + "'"
    alternativas = [citado]
    if re.fullmatch(r"[^\s'!:\[\]\-+(),;&=<>\"]+", nome):
        alternativas.append(re.escape(nome))
    return re.compile(rf"(?<![\w.'])(?:{'|'.join(alternativas)})!"
                      r"(\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?|\$?\d+:\$?\d+)", re.I)


def _linhas_citadas(texto: str, rx) -> list[int]:
    """Os números de linha das referências à aba em `texto` (fórmula, nome, série)."""
    linhas = []
    for m in rx.finditer(_desescapar(texto)):
        for ponta in m.group(1).split(":"):
            n = re.search(r"(\d+)$", ponta)
            if n:
                linhas.append(int(n.group(1)))
    return linhas


def recusas(pasta: Pasta, coluna_chave: str) -> list[str]:
    """O que impede deslocar as linhas com segurança, em palavras simples. Vazio = pode."""
    out: list[str] = []
    xml = pasta.aba_xml
    aba = pasta.aba_nome
    tb = pasta.tabela

    # A. Na aba da tabela
    if re.search(r"<f\b", xml):
        out.append(f"A aba '{aba}' tem fórmula.")
    for tag, texto in _PROIBIDOS_NA_ABA:
        if re.search(rf"<{tag}\b", xml):
            out.append(f"A aba '{aba}' tem {texto}.")
    for ext in re.findall(r"<extLst\b.*?</extLst>", xml, re.S):
        if "x14:" in ext:
            out.append(f"A aba '{aba}' usa recursos avançados do Excel (extensões x14).")
            break

    # B. Na pasta toda
    if "xl/vbaProject.bin" in pasta.partes:
        out.append("A pasta de trabalho tem macros (VBA).")
    rx = _ref_aba(aba)
    afetadas = lambda texto: any(n >= tb.primeira for n in _linhas_citadas(texto, rx))  # noqa: E731
    for nome, dados in pasta.partes.items():
        if not nome.endswith(".xml"):
            continue
        if nome.startswith("xl/worksheets/") and nome != pasta.aba_parte:
            texto = dados.decode("utf-8", "replace")
            if any(afetadas(f) for f in re.findall(r"<f\b[^>]*>(.*?)</f>", texto, re.S)):
                out.append(f"Há fórmula em outra aba que aponta para células da aba '{aba}'.")
        elif nome == "xl/workbook.xml":
            texto = dados.decode("utf-8", "replace")
            if any(afetadas(f) for f in re.findall(r"<definedName\b[^>]*>(.*?)</definedName>", texto, re.S)):
                out.append(f"Há nome definido que aponta para células da aba '{aba}'.")
        elif nome.startswith("xl/charts/"):
            texto = dados.decode("utf-8", "replace")
            if any(afetadas(f) for f in re.findall(r"<c:f>(.*?)</c:f>", texto, re.S)):
                out.append(f"Há gráfico com série que aponta para células da aba '{aba}'.")
        elif nome.startswith("xl/pivotCache/"):
            texto = dados.decode("utf-8", "replace")
            for ws in re.findall(r"<worksheetSource\b[^>]*>", texto):
                a = _attrs(ws)
                if "ref" in a and _desescapar(a.get("sheet", "")).casefold() == aba.casefold():
                    out.append(f"Há tabela dinâmica cuja origem é um intervalo fixo da aba '{aba}' "
                               "(e não a Tabela). Troque a origem dela para o nome da Tabela.")

    # C. Na tabela
    txt_tabela = re.match(r"<\?xml[^>]*>\s*<table\b[^>]*>|<table\b[^>]*>", tb.xml.strip())
    a_tabela = _attrs(txt_tabela.group(0)) if txt_tabela else {}
    if a_tabela.get("totalsRowShown") == "1" or int(a_tabela.get("totalsRowCount", "0") or 0) > 0:
        out.append(f"A tabela '{tb.nome}' tem linha de total.")
    if "calculatedColumnFormula" in tb.xml:
        out.append(f"A tabela '{tb.nome}' tem coluna calculada.")
    for linha in pasta.linhas:
        com_valor = [c for c in linha.celulas.values() if c.valor not in (None, "")]
        if linha.r > tb.ultima and com_valor:
            out.append(f"Há dados abaixo da tabela (linha {linha.r}); eles colidiriam com as "
                       "linhas deslocadas.")
            break
        if linha.r >= tb.primeira and any(c.col < tb.col_ini or c.col > tb.col_fim for c in com_valor):
            out.append(f"Há dados ao lado da tabela (linha {linha.r}); eles seriam deslocados junto.")
            break

    # D. No corpo da tabela
    chave = tb.coluna(coluna_chave)
    vistos: set[int] = set()
    por_linha = {x.r: x for x in pasta.linhas}
    for r in range(tb.primeira, tb.ultima + 1):
        linha = por_linha.get(r)
        cel = linha.celulas.get(chave) if linha else None
        v = cel.valor if cel else None
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        if isinstance(v, str) and v.strip().isdigit():
            v = int(v.strip())
        if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
            out.append(f"A linha {r} da tabela não tem '{coluna_chave}' (número inteiro).")
            break
        if v in vistos:
            out.append(f"'{coluna_chave}' {v} aparece mais de uma vez na tabela.")
            break
        vistos.add(v)
    return out


# --- Escrita (8.5 da spec) --------------------------------------------------------------

_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def limpar_texto(texto: str, avisar=None) -> str:
    """O texto como ele vai ficar na célula: sem o que o XML proíbe e cortado no
    limite do Excel. Quem compara com o que está gravado compara com ISTO."""
    texto = _CONTROLE.sub("", str(texto))
    if len(texto) > LIMITE_TEXTO:
        texto = texto[:LIMITE_TEXTO - len(MARCA_CORTE)] + MARCA_CORTE
        if avisar:
            avisar("Um texto passou do limite de 32.767 caracteres do Excel e foi cortado.")
    return texto


def texto_para_celula(texto: str, avisar=None) -> str:
    """Limpa (`limpar_texto`) e escapa para dentro do XML."""
    texto = limpar_texto(texto, avisar)
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def serial(d: date) -> int:
    return (d - _EPOCA_EXCEL).days


def celula_xml(ref: str, s: str | None, valor, avisar=None) -> str:
    estilo = f' s="{s}"' if s is not None else ""
    if valor is None or valor == "":
        return f'<c r="{ref}"{estilo}/>'
    if isinstance(valor, bool):
        valor = "Sim" if valor else "Não"
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        return f'<c r="{ref}"{estilo}><v>{serial(valor)}</v></c>'
    if isinstance(valor, (int, float)):
        n = int(valor) if float(valor).is_integer() else valor
        return f'<c r="{ref}"{estilo}><v>{n!r}</v></c>'
    return (f'<c r="{ref}"{estilo} t="inlineStr"><is><t xml:space="preserve">'
            f"{texto_para_celula(valor, avisar)}</t></is></c>")


def _trocar_attr(texto: str, nome: str, valor: str, *, so_abertura: bool = False) -> str:
    """Troca (ou acrescenta) o atributo `nome` na primeira tag de `texto`."""
    m = re.match(r"<[^>]*?(/?)>", texto, re.S)
    abertura = m.group(0)
    if re.search(rf'\s{re.escape(nome)}="[^"]*"', abertura):
        nova = re.sub(rf'(\s{re.escape(nome)}=")[^"]*(")', rf"\g<1>{valor}\g<2>", abertura, count=1)
    else:
        fim = "/>" if abertura.endswith("/>") else ">"
        nova = abertura[:-len(fim)] + f' {nome}="{valor}"' + fim
    return nova + texto[len(abertura):]


@dataclass
class LinhaNova:
    abertura: str                       # <row ...> do modelo (o r é trocado aqui)
    valores: list[tuple[object, str | None]]   # (valor, s), uma por coluna da tabela


@dataclass
class Edicao:
    novas: list[LinhaNova] = field(default_factory=list)
    celulas: dict[tuple[int, int], tuple[object, str | None]] = field(default_factory=dict)
    estilo_linha: dict[int, str] = field(default_factory=dict)    # linha original → s do <row>


def _renumerar(abertura: str, novo_r: int) -> str:
    return re.sub(r'(\sr=")\d+(")', rf"\g<1>{novo_r}\g<2>", abertura, count=1)


def _nova_celula(cel: Celula | None, col: int, r: int, valor, s, avisar) -> str:
    ref = f"{letra(col)}{r}"
    if valor is MANTER:
        base = re.sub(r'(\sr=")[A-Z]+\d+(")', rf"\g<1>{ref}\g<2>", cel.xml, count=1) if cel \
            else f'<c r="{ref}"/>'
        return _trocar_attr(base, "s", s) if s is not None else base
    return celula_xml(ref, s, valor, avisar)


def _linha_xml(linha: Linha, novo_r: int, edicoes: dict[int, tuple[object, str | None]],
               s_linha: str | None, avisar) -> str:
    abertura = _renumerar(linha.abertura, novo_r)
    if s_linha is not None:
        abertura = _trocar_attr(abertura, "s", s_linha)
        abertura = _trocar_attr(abertura, "customFormat", "1")
    if abertura.endswith("/>") and edicoes:
        abertura = abertura[:-2] + ">"
    if abertura.endswith("/>"):
        return abertura
    pendentes = dict(edicoes)
    pedacos = []
    for seg in linha.segmentos:
        col = _celula(_attrs(re.match(r"<c\b[^>]*>", seg).group(0))["r"])[0]
        for c in sorted(k for k in pendentes if k < col):
            pedacos.append(_nova_celula(None, c, novo_r, *pendentes.pop(c), avisar))
        if col in pendentes:
            pedacos.append(_nova_celula(linha.celulas[col], col, novo_r, *pendentes.pop(col), avisar))
        else:
            pedacos.append(re.sub(r'(\sr=")([A-Z]+)\d+(")', rf"\g<1>\g<2>{novo_r}\g<3>", seg, count=1))
    for c in sorted(pendentes):
        pedacos.append(_nova_celula(None, c, novo_r, *pendentes[c], avisar))
    return abertura + "".join(pedacos) + "</row>"


def aplicar(pasta: Pasta, edicao: Edicao, avisar=None) -> dict[str, bytes]:
    """As partes alteradas (nome → bytes). Nada é gravado aqui."""
    tb = pasta.tabela
    k = len(edicao.novas)
    por_linha: dict[int, dict[int, tuple[object, str | None]]] = {}
    for (r, col), v in edicao.celulas.items():
        por_linha.setdefault(r, {})[col] = v

    pedacos = []
    inseridas = False
    for i, linha in enumerate(pasta.linhas):
        if not inseridas and linha.r >= tb.primeira:
            pedacos.append(_novas_xml(edicao.novas, tb, avisar))
            inseridas = True
        pedacos.append(pasta.entre[i])
        novo_r = linha.r + k if linha.r >= tb.primeira else linha.r
        if linha.r in por_linha or linha.r in edicao.estilo_linha or novo_r != linha.r:
            pedacos.append(_linha_xml(linha, novo_r, por_linha.get(linha.r, {}),
                                      edicao.estilo_linha.get(linha.r), avisar))
        else:
            pedacos.append(linha.xml)
    if not inseridas:
        pedacos.append(_novas_xml(edicao.novas, tb, avisar))
    pedacos.append(pasta.entre[-1])
    aba = pasta.antes + "".join(pedacos) + pasta.depois

    if k:
        def estender(m):
            c1, l1, c2, l2 = _intervalo(m.group(2))
            if l2 >= tb.cabecalho:
                l2 += k
            return m.group(1) + _ref_intervalo(c1, l1, c2, l2) + m.group(3)
        aba = re.sub(r'(<dimension\s+ref=")([^"]+)(")', estender, aba, count=1)

    alteradas = {pasta.aba_parte: aba.encode("utf-8")}
    if k:
        nova_ref = _ref_intervalo(tb.col_ini, tb.cabecalho, tb.col_fim, tb.ultima + k)
        xml_tb = re.sub(r'(<table\b[^>]*?\sref=")[^"]+(")', rf"\g<1>{nova_ref}\g<2>", tb.xml, count=1)
        xml_tb = re.sub(r'(<autoFilter\b[^>]*?\sref=")[^"]+(")', rf"\g<1>{nova_ref}\g<2>", xml_tb, count=1)

        def sort(m):
            c1, l1, c2, l2 = _intervalo(m.group(2))
            return m.group(1) + _ref_intervalo(c1, l1, c2, l2 + k) + m.group(3)
        xml_tb = re.sub(r'(<sortState\b[^>]*?\sref=")([^"]+)(")', sort, xml_tb)
        alteradas[tb.parte] = xml_tb.encode("utf-8")
    if (estilos := pasta.estilos.xml_novo()) is not None:
        alteradas["xl/styles.xml"] = estilos.encode("utf-8")
    return alteradas


def _novas_xml(novas: list[LinhaNova], tb: Tabela, avisar) -> str:
    out = []
    for i, nova in enumerate(novas):
        r = tb.primeira + i
        abertura = _renumerar(nova.abertura, r)
        if abertura.endswith("/>"):
            abertura = abertura[:-2] + ">"
        cels = "".join(celula_xml(f"{letra(tb.col_ini + j)}{r}", s, v, avisar)
                       for j, (v, s) in enumerate(nova.valores))
        out.append(abertura + cels + "</row>")
    return "".join(out)


def gravar_zip(pasta: Pasta, alteradas: dict[str, bytes], destino) -> None:
    """O pacote com as MESMAS entradas, na MESMA ordem: as alteradas com o conteúdo
    novo, as outras com os bytes originais (e o mesmo nome, data e compressão)."""
    with zipfile.ZipFile(destino, "w") as zout:
        for info in pasta.infos:
            zout.writestr(copy.copy(info), alteradas.get(info.filename, pasta.partes[info.filename]))


def mais_comum(valores):
    """O valor mais frequente (o primeiro visto, no empate); None se vazio."""
    contagem = Counter(valores)
    if not contagem:
        return None
    maior = max(contagem.values())
    return next(v for v in valores if contagem[v] == maior)
