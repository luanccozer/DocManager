"""O arquivo de envio: a tabela "Seguem documentos para envio via ACONEX" (Upload → aprovação).

Chega como Word ou como Excel (quem usa nem sempre sabe qual): os dois são aceitos.
A tabela é achada pelo cabeçalho `IDENTIFICAÇÃO DOCUMENTO CMI`, e a coluna `LINK` é um
HIPERLINK - o que interessa é o destino (a pasta do Box), não o texto ("R0 | Pov…").

Só biblioteca padrão para o .docx (zip + XML) e openpyxl para o .xlsx.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..core.normalize import normalizar_cabecalho
from .controle_docs import chave_codigo

COL_CMI = "IDENTIFICAÇÃO DOCUMENTO CMI"
COL_ITAIPU = "IDENTIFICAÇÃO DOCUMENTO ITAIPU"
COL_DESCRICAO = "DESCRIÇÃO"
COL_REVISAO = "EMITIR REV. ITAIPÚ"
COL_LINK = "LINK"

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_RE_HYPERLINK_CAMPO = re.compile(r'HYPERLINK\s+"([^"]+)"')


class ErroEnvio(ValueError):
    """O arquivo de envio não pôde ser lido; a mensagem é para a tela."""


@dataclass(frozen=True)
class LinhaEnvio:
    cod_cmi: str
    cod_itaipu: str = ""
    descricao: str = ""
    revisao: str = ""
    link: str = ""


def ler_envio(caminho) -> list[LinhaEnvio]:
    """Todas as linhas da tabela de envio (as que têm código CMI)."""
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    if ext in (".doc", ".xls"):
        raise ErroEnvio(f"O arquivo '{caminho.name}' está no formato antigo ({ext}). Abra-o e use "
                        "Salvar como → .docx (Word) ou .xlsx (Excel).")
    if ext == ".docx":
        tabelas = _tabelas_docx(caminho)
    elif ext in (".xlsx", ".xlsm"):
        tabelas = _tabelas_xlsx(caminho)
    else:
        raise ErroEnvio(f"O arquivo '{caminho.name}' não é Word (.docx) nem Excel (.xlsx).")
    for tabela in tabelas:
        linhas = _linhas_da_tabela(tabela)
        if linhas is not None:
            return linhas
    raise ErroEnvio(f"Nenhuma tabela com a coluna '{COL_CMI}' foi encontrada em '{caminho.name}'.")


def buscar(linhas: list[LinhaEnvio], codigo: str) -> LinhaEnvio | None:
    alvo = chave_codigo(codigo)
    return next((x for x in linhas if chave_codigo(x.cod_cmi) == alvo), None)


# Uma tabela é uma lista de linhas; cada célula, (texto, link ou "").
Celula = tuple[str, str]


def _linhas_da_tabela(tabela: list[list[Celula]]) -> list[LinhaEnvio] | None:
    alvo = normalizar_cabecalho(COL_CMI)
    for i, linha in enumerate(tabela):
        nomes = [normalizar_cabecalho(t) for t, _ in linha]
        if alvo not in nomes:
            continue

        def col(nome):
            n = normalizar_cabecalho(nome)
            return nomes.index(n) if n in nomes else None

        c_cmi, c_it, c_desc, c_rev = col(COL_CMI), col(COL_ITAIPU), col(COL_DESCRICAO), col(COL_REVISAO)
        c_link = col(COL_LINK)
        if c_link is None:   # o cabeçalho pode vir cortado ("LINK" na última coluna, às vezes "LINKS")
            c_link = next((j for j, n in enumerate(nomes) if n.startswith("LINK")), None)
        saida = []
        for outra in tabela[i + 1:]:
            def celula(j):
                return outra[j] if j is not None and j < len(outra) else ("", "")
            cmi = celula(c_cmi)[0].strip()
            if not cmi:
                continue
            texto_link, destino = celula(c_link)
            if not destino and texto_link.strip().lower().startswith("http"):
                destino = texto_link.strip()
            saida.append(LinhaEnvio(cmi, celula(c_it)[0].strip(), celula(c_desc)[0].strip(),
                                    celula(c_rev)[0].strip(), destino.strip()))
        return saida
    return None


def _tabelas_xlsx(caminho: Path) -> list[list[list[Celula]]]:
    import openpyxl

    try:
        wb = openpyxl.load_workbook(caminho, data_only=True)   # hiperlink só no modo normal
    except Exception as e:  # noqa: BLE001
        raise ErroEnvio(f"Não foi possível abrir '{caminho.name}': {e}") from e
    try:
        tabelas = []
        for ws in wb.worksheets:
            linhas = []
            for row in ws.iter_rows():
                linhas.append([("" if c.value is None else str(c.value),
                                (c.hyperlink.target or "") if c.hyperlink is not None else "")
                               for c in row])
            tabelas.append(linhas)
        return tabelas
    finally:
        wb.close()


def _tabelas_docx(caminho: Path) -> list[list[list[Celula]]]:
    try:
        with zipfile.ZipFile(caminho) as z:
            doc = ET.fromstring(z.read("word/document.xml"))
            rels_xml = z.read("word/_rels/document.xml.rels") if "word/_rels/document.xml.rels" in z.namelist() else b""
    except (zipfile.BadZipFile, KeyError, OSError, ET.ParseError) as e:
        raise ErroEnvio(f"Não foi possível abrir '{caminho.name}' como Word: {e}") from e
    rels = {}
    if rels_xml:
        for rel in ET.fromstring(rels_xml).findall(f"{_PKG}Relationship"):
            rels[rel.get("Id")] = rel.get("Target", "")
    tabelas = []
    for tbl in doc.iter(f"{_W}tbl"):
        linhas = []
        for tr in tbl.findall(f"{_W}tr"):
            linhas.append([_celula_docx(tc, rels) for tc in tr.findall(f"{_W}tc")])
        tabelas.append(linhas)
    return tabelas


def _celula_docx(tc, rels: dict[str, str]) -> Celula:
    paragrafos = []
    for p in tc.iter(f"{_W}p"):
        paragrafos.append("".join(t.text or "" for t in p.iter(f"{_W}t")))
    texto = " ".join(x for x in paragrafos if x)
    link = ""
    for h in tc.iter(f"{_W}hyperlink"):
        rid = h.get(f"{_R}id")
        if rid and rels.get(rid):
            link = rels[rid]
            break
    if not link:   # hiperlink como campo: { HYPERLINK "https://..." }
        instrucoes = [f.get(f"{_W}instr", "") for f in tc.iter(f"{_W}fldSimple")]
        instrucoes += [i.text or "" for i in tc.iter(f"{_W}instrText")]
        m = _RE_HYPERLINK_CAMPO.search(" ".join(instrucoes))
        if m:
            link = m.group(1)
    return texto, link
