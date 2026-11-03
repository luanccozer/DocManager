"""Builders de histórico Aconex sintético para os testes.

Produzem DataFrames com as colunas canônicas (§5) e no MESMO formato que
`carregar_aconex` entrega ao backend: tudo string, sem NaN. Assim os testes
exercitam exatamente o que os motores recebem em produção.
"""
from __future__ import annotations

import pandas as pd

COLUNAS_ACONEX = [
    "No. do Documento", "Controle do Emissor", "Tracking ID", "Título",
    "Tipo do Documento", "Especialidade", "Subespecialidade",
    "Tipo do Documento DCC", "Subtipo DCC",
    "Revisão", "Versão", "Status", "Status da Revisão",
    "Data de Alteração", "Current",
]


class HistoricoBuilder:
    """Constrói o histórico (várias linhas por revisão/versão) de UM documento."""

    def __init__(self, tracking, doc, cmi, titulo="DOCUMENTO GENERICO",
                 tipo="Documento Técnico"):
        self.tracking = tracking
        self.doc = doc
        self.cmi = cmi
        self.titulo = titulo
        self.tipo = tipo
        self._eventos: list[dict] = []

    def evento(self, rev, versao, status, data, *, current=False,
               terminated=False, doc=None, cmi=None, titulo=None, tipo=None):
        """Adiciona uma linha (um evento/versão). `data` = 'dd/mm/yyyy'."""
        self._eventos.append({
            "No. do Documento": doc if doc is not None else self.doc,
            "Controle do Emissor": cmi if cmi is not None else self.cmi,
            "Tracking ID": self.tracking,
            "Título": titulo if titulo is not None else self.titulo,
            "Tipo do Documento": tipo if tipo is not None else self.tipo,
            "Especialidade": "", "Subespecialidade": "",
            "Tipo do Documento DCC": "", "Subtipo DCC": "",
            "Revisão": rev,
            "Versão": str(versao),
            "Status": status,
            "Status da Revisão": "Terminated" if terminated else "",
            "Data de Alteração": data,
            "Current": "true" if current else "false",
        })
        return self

    def build(self) -> pd.DataFrame:
        return base(self)


def base(*builders: HistoricoBuilder) -> pd.DataFrame:
    """Concatena históricos num único DataFrame no formato da carga Aconex."""
    linhas = [ev for b in builders for ev in b._eventos]
    df = pd.DataFrame(linhas, columns=COLUNAS_ACONEX)
    return df.astype(str).fillna("")


def escrever_controle_xlsx(path, linhas, *, incluir_reprogramacao=True,
                           incluir_fase=False, cabecalhos=None, incluir_ultima=False):
    """Escreve um Controle de Documentos sintético (cabeçalho na linha 4).

    `linhas`: list[dict] com chaves itaipu, cmi, titulo, prevista, reprog, fase.
    Códigos podem ser float (ex.: 12345.0) para exercitar o '.0' fantasma.
    `cabecalhos`: sobrescreve os textos do cabeçalho (dict por chave: itaipu,
    cmi, prevista, reprog, fase) - para exercitar cabeçalhos quebrados em duas
    linhas, com espaços a mais, etc.
    """
    from openpyxl import Workbook

    from docmanager.core.constants import (
        CTRL_COL_CMI,
        CTRL_COL_DATA_PREVISTA,
        CTRL_COL_ITAIPU,
    )

    cab = {"itaipu": CTRL_COL_ITAIPU, "cmi": CTRL_COL_CMI, "titulo": "DESCRIÇÃO",
           "prevista": CTRL_COL_DATA_PREVISTA, "reprog": "REPROGRAMAÇÃO",
           "fase": "FASE DE PROJETO", "ultima": "ÚLTIMA REVISÃO EMITIDA"}
    cab.update(cabecalhos or {})

    wb = Workbook()
    ws = wb.active
    ws.append(["Controle de Documentos"])
    ws.append([])
    ws.append([])
    chaves = ["itaipu", "cmi", "titulo", "prevista"]
    if incluir_reprogramacao:
        chaves.append("reprog")
    if incluir_fase:
        chaves.append("fase")
    if incluir_ultima:
        chaves.append("ultima")
    ws.append([cab[k] for k in chaves])
    for lin in linhas:
        ws.append([lin.get(k, "") for k in chaves])
    wb.save(path)
    return path


# --- Planilha de mapeamento de pendências (estrutura da real, dados fictícios) -----

COLUNAS_PENDENCIAS = [
    "Issue Number", "Issue Type", "Area", "Location Detail", "Issue Description",
    "Captured On", "Captured by", "Status", "Departamento Responsável", "Responsável",
    "Acompanhamento da Ação", "Respondida Aconex", "Due Date", "TAG RDS-PP",
    "Clasificación de pendencia", "Documentos de referencia", "Fecha prevista para corrección",
    "Cierre", "Área del Solicitante", "¿Pasó a comisionamiento?", "Área responsable SM.DT",
    "Comments",
]
MANUAIS_PENDENCIAS = ("Departamento Responsável", "Responsável", "Acompanhamento da Ação",
                      "Respondida Aconex")


def linha_pendencia(numero, **valores) -> dict:
    """Uma linha da planilha: os campos do Aconex com valores fictícios coerentes."""
    base = {
        "Issue Number": numero,
        "Issue Type": "05. Pendencia de Comisionamiento",
        "Area": "PROJETO EXEMPLO > GRUPO EXEMPLO",
        "Location Detail": f"PAINEL-{numero}",
        "Issue Description": f"Pendência fictícia {numero}",
        "Captured On": "2026-10-01",
        "Captured by": "FULANO DE TAL",
        "Status": "Open",
        "Due Date": "2026-11-05",
        "TAG RDS-PP": f"#XX00=Z{numero:03d}: EQUIPAMENTO",
        "Clasificación de pendencia": "No impeditiva",
        "Área del Solicitante": "AREA X",
        "¿Pasó a comisionamiento?": "Não",
        "Área responsable SM.DT": "SM.DT X",
    }
    base.update(valores)
    return base


def escrever_planilha_pendencias(path, linhas: list[dict], *, com_destaque: bool = True,
                                 fonte_azul: tuple = (), parte_extra: bool = True,
                                 colunas: list[str] | None = None) -> None:
    """Imita a "ACONEX - MAPEAMENTO PENDÊNCIAS.xlsx" (spec, seção 3).

    Aba PENDÊNCIAS com a legenda na linha 2; Tabela tbRegistros a partir de A4
    com as 22 colunas; linhas normais (H cinza, I-L em tom claro) e destacadas
    (Impeditiva e não Closed: a linha inteira na cor da legenda); coluna M
    oculta; painel congelado em C5; alturas personalizadas; uma segunda aba com
    gráfico; e, depois de salvo, uma parte extra no zip para provar que o que o
    app não conhece passa byte a byte.
    """

    import openpyxl
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Border, Font, PatternFill, Side
    from openpyxl.worksheet.table import Table, TableStyleInfo

    destaque = PatternFill("solid", fgColor="FFF4B183")
    cinza = PatternFill("solid", fgColor="FFD9D9D9")
    claro = PatternFill("solid", fgColor="FFDDEBF7")
    borda = Border(bottom=Side(style="thin"))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PENDÊNCIAS"
    ws["A2"].fill = destaque
    ws["B2"] = 'IMPEDITIVAS SITUAÇÃO "OPEN"'
    colunas = colunas or COLUNAS_PENDENCIAS
    for i, nome in enumerate(colunas, 1):
        ws.cell(4, i, nome)
    for r, dados in enumerate(linhas, 5):
        destacada = com_destaque and (dados.get("Clasificación de pendencia") == "Impeditiva"
                                      and dados.get("Status") != "Closed")
        for i, nome in enumerate(colunas, 1):
            c = ws.cell(r, i, dados.get(nome))
            c.border = borda
            if destacada:
                c.fill = destaque
            elif nome == "Status":
                c.fill = cinza
            elif i in (9, 10, 11, 12):   # I-L, as manuais
                c.fill = claro
            if dados.get("Issue Number") in fonte_azul:
                c.font = Font(color="FF0070C0")
        ws.row_dimensions[r].height = 25.5 if r % 2 else 50.15
    ultima = 4 + len(linhas)
    tabela = Table(displayName="tbRegistros", ref=f"A4:{chr(64 + len(colunas))}{ultima}")
    tabela.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=False)
    ws.add_table(tabela)
    ws.column_dimensions["M"].hidden = True
    ws.freeze_panes = "C5"

    graf = wb.create_sheet("GRÁFICO SITUAÇÃO")
    graf.append(["Status", "Quantidade"])
    graf.append(["Open", 3])
    graf.append(["Closed", 1])
    barra = BarChart()
    barra.add_data(Reference(graf, min_col=2, min_row=1, max_row=3), titles_from_data=True)
    graf.add_chart(barra, "D2")
    wb.save(path)

    _como_o_excel(path, parte_extra)


def _como_o_excel(path, parte_extra: bool) -> None:
    """Deixa o XML com o jeito do que o Excel grava e o openpyxl não: raiz com
    `mc:Ignorable="x14ac"`, `<row s=.. customFormat="1" x14ac:dyDescent=..>` e a
    coluna Issue Type em textos compartilhados (sharedStrings)."""
    import re
    import zipfile

    with zipfile.ZipFile(path) as z:
        partes = [(i, z.read(i)) for i in z.infolist()]
    textos: list[str] = []

    def compartilhar(m):
        texto = m.group(2)
        if texto not in textos:
            textos.append(texto)
        return f'{m.group(1)} t="s"><v>{textos.index(texto)}</v></c>'

    def linha(m):
        r = int(m.group(1))
        if r < 5:
            return m.group(0)
        s_a = re.search(rf'<c r="A{r}" s="(\d+)"', m.string)
        extra = f' s="{s_a.group(1)}" customFormat="1"' if s_a else ""
        return m.group(0).replace(f'<row r="{r}"', f'<row r="{r}"{extra}', 1).replace(
            ">", ' x14ac:dyDescent="0.35">', 1)

    novas = []
    for info, dados in partes:
        if info.filename == "xl/worksheets/sheet1.xml":
            x = dados.decode("utf-8")
            x = x.replace(
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
                'mc:Ignorable="x14ac" '
                'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac">', 1)
            x = re.sub(r'<row r="(\d+)"[^>]*>', linha, x)
            x = re.sub(r'(<c r="B(?:[5-9]|\d\d+)" s="\d+") t="inlineStr"><is><t>([^<]*)</t></is></c>',
                       compartilhar, x)
            dados = x.encode("utf-8")
        elif info.filename == "[Content_Types].xml":
            extra = (b'<Override PartName="/xl/sharedStrings.xml" ContentType="application/'
                     b'vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>')
            if parte_extra:
                extra += b'<Override PartName="/customXml/item1.xml" ContentType="application/xml"/>'
            dados = dados.replace(b"</Types>", extra + b"</Types>")
        elif info.filename == "xl/_rels/workbook.xml.rels":
            dados = dados.replace(
                b"</Relationships>",
                b'<Relationship Id="rIdSst" Target="sharedStrings.xml" Type="http://schemas.'
                b'openxmlformats.org/officeDocument/2006/relationships/sharedStrings"/>'
                b"</Relationships>")
        novas.append((info, dados))
    sst = "".join(f"<si><t>{t}</t></si>" for t in textos)
    novas.append((zipfile.ZipInfo("xl/sharedStrings.xml"), (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(textos)}" uniqueCount="{len(textos)}">{sst}</sst>').encode("utf-8")))
    if parte_extra:
        novas.append((zipfile.ZipInfo("customXml/item1.xml"),
                      b'<?xml version="1.0"?><dados x="1">extra</dados>'))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for info, dados in novas:
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, dados)
