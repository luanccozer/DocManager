"""Arquivo de envio do Upload → aprovação: Word ou Excel, com o link do Box como hiperlink."""
from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape

import openpyxl
import pytest

from docmanager.services import upload_envio as ue

CABECALHO = ["IDENTIFICAÇÃO DOCUMENTO CMI", "IDENTIFICAÇÃO DOCUMENTO ITAIPU",
             "ESPECIFICAÇÃO TÉCNICA (EQUIPAMENTO/SISTEMA)", "DESCRIÇÃO", "TIPO DE DOCUMENTO",
             "EMITIR REV. ITAIPÚ", "LINK"]
LINHAS = [
    ("0000CMI-AA01-01", "#XX00=EXEMPLO&AAA010", "UNIDADE", "-", "LISTA", "0",
     "https://exemplo.box.com/folder/111"),
    ("0000CMI-AA02-01", "#XX00=EXEMPLO&AAA020", "UNIDADE", "60Hz", "LISTA", "0E",
     "https://exemplo.box.com/folder/222"),
]


def _docx(caminho, *, como_campo=False):
    """Um .docx mínimo: frase + tabela, LINK como hiperlink (relação) ou como campo."""
    def celula(texto, link=None, rid=None):
        texto = escape(texto)
        if link and como_campo:
            corpo = (f'<w:p><w:fldSimple w:instr=" HYPERLINK &quot;{link}&quot; ">'
                     f"<w:r><w:t>{texto}</w:t></w:r></w:fldSimple></w:p>")
        elif link:
            corpo = f'<w:p><w:hyperlink r:id="{rid}"><w:r><w:t>{texto}</w:t></w:r></w:hyperlink></w:p>'
        else:
            corpo = f"<w:p><w:r><w:t>{texto}</w:t></w:r></w:p>"
        return f"<w:tc>{corpo}</w:tc>"

    linhas = ["<w:tr>" + "".join(celula(c) for c in CABECALHO) + "</w:tr>"]
    rels = []
    for i, dados in enumerate(LINHAS, 1):
        rid = f"rIdLink{i}"
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/'
                    f'2006/relationships/hyperlink" Target="{dados[-1]}" TargetMode="External"/>')
        linhas.append("<w:tr>" + "".join(celula(c) for c in dados[:-1])
                      + celula("R0 | Pov", dados[-1], rid) + "</w:tr>")
    doc = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
           'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>'
           '<w:p><w:r><w:t>Seguem documentos para envio via ACONEX análise de ITAIPU:</w:t></w:r></w:p>'
           f'<w:tbl>{"".join(linhas)}</w:tbl></w:body></w:document>')
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels",
                   '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                   f'package/2006/relationships">{"".join(rels)}</Relationships>')
    return caminho


def _xlsx(caminho):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "Seguem documentos para envio via ACONEX análise de ITAIPU:"
    ws.append([])
    ws.append(CABECALHO)
    for dados in LINHAS:
        ws.append(list(dados[:-1]) + ["R0 | Pov"])
        ws.cell(ws.max_row, len(CABECALHO)).hyperlink = dados[-1]
    wb.save(caminho)
    return caminho


@pytest.mark.parametrize("montar", [_docx, lambda c: _docx(c, como_campo=True), _xlsx],
                         ids=["word", "word-campo", "excel"])
def test_le_a_tabela_e_o_destino_do_hiperlink(tmp_path, montar):
    sufixo = ".xlsx" if montar is _xlsx else ".docx"
    linhas = ue.ler_envio(montar(tmp_path / f"envio{sufixo}"))
    assert [x.cod_cmi for x in linhas] == ["0000CMI-AA01-01", "0000CMI-AA02-01"]
    achada = ue.buscar(linhas, " 0000cmi-aa02-01 ")
    assert achada.cod_itaipu == "#XX00=EXEMPLO&AAA020"
    assert achada.revisao == "0E"
    assert achada.link == "https://exemplo.box.com/folder/222"   # o destino, não "R0 | Pov"


def test_codigo_que_nao_esta_na_tabela(tmp_path):
    assert ue.buscar(ue.ler_envio(_xlsx(tmp_path / "e.xlsx")), "OUTRO-01") is None


def test_formato_antigo_pede_para_salvar_de_novo(tmp_path):
    antigo = tmp_path / "envio.doc"
    antigo.write_bytes(b"x")
    with pytest.raises(ue.ErroEnvio, match="Salvar como"):
        ue.ler_envio(antigo)


def test_sem_a_tabela(tmp_path):
    caminho = tmp_path / "vazio.xlsx"
    openpyxl.Workbook().save(caminho)
    with pytest.raises(ue.ErroEnvio, match="IDENTIFICAÇÃO DOCUMENTO CMI"):
        ue.ler_envio(caminho)
