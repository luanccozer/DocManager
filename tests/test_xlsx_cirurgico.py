"""Escrita cirúrgica no .xlsx: só o XML que precisa mudar, o resto byte a byte (ADR 0002)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

import openpyxl
import pytest

from builders import escrever_planilha_pendencias, linha_pendencia
from docmanager.services import xlsx_cirurgico as xc

CHAVE = "Issue Number"
IMPEDITIVA = {"Clasificación de pendencia": "Impeditiva"}


@pytest.fixture
def planilha(tmp_path):
    caminho = tmp_path / "pendencias.xlsx"
    escrever_planilha_pendencias(caminho, [
        linha_pendencia(9, **IMPEDITIVA),
        linha_pendencia(8),
        linha_pendencia(7, **{"Captured On": date(2026, 10, 2)}),
    ], fonte_azul=(8,))
    return caminho


def _partes(caminho):
    with zipfile.ZipFile(caminho) as z:
        return [(i.filename, z.read(i)) for i in z.infolist()]


def _aplicar(pasta, edicao, destino):
    alteradas = xc.aplicar(pasta, edicao)
    xc.gravar_zip(pasta, alteradas, destino)
    return alteradas


# --- Leitura --------------------------------------------------------------------

def test_le_a_tabela_pela_coluna_chave(planilha):
    p = xc.ler(planilha, CHAVE)
    assert p.aba_nome == "PENDÊNCIAS"
    assert p.tabela.nome == "tbRegistros" and p.tabela.ref == "A4:V7"
    assert (p.tabela.cabecalho, p.tabela.primeira, p.tabela.ultima) == (4, 5, 7)
    assert p.tabela.coluna("clasificacion de PENDENCIA") == 15
    corpo = p.corpo()
    assert [x.celulas[1].valor for x in corpo] == [9, 8, 7]
    assert corpo[0].celulas[2].valor == "05. Pendencia de Comisionamiento"   # texto compartilhado
    assert corpo[2].celulas[6].valor == date(2026, 10, 2)                     # data real
    assert corpo[1].celulas[6].valor == "2026-10-01"                          # data como texto
    assert xc.recusas(p, CHAVE) == []


def test_sem_tabela_recusa(tmp_path):
    caminho = tmp_path / "x.xlsx"
    wb = openpyxl.Workbook()
    wb.active["A1"] = "Issue Number"
    wb.save(caminho)
    with pytest.raises(xc.ErroXlsx, match="Tabela do Excel"):
        xc.ler(caminho, CHAVE)


def test_arquivo_que_nao_e_xlsx(tmp_path):
    caminho = tmp_path / "x.xlsx"
    caminho.write_bytes(b"texto")
    with pytest.raises(xc.ErroXlsx):
        xc.ler(caminho, CHAVE)


# --- Escrita --------------------------------------------------------------------

def test_linhas_novas_no_topo_e_existentes_renumeradas(planilha, tmp_path):
    p = xc.ler(planilha, CHAVE)
    modelo = p.corpo()[1]
    nova = xc.LinhaNova(modelo.abertura, [(11, modelo.celulas[1].s)] +
                        [("nova & <11>", modelo.celulas[c].s) for c in range(2, 23)])
    nova2 = xc.LinhaNova(modelo.abertura, [(10, modelo.celulas[1].s)] +
                         [("", modelo.celulas[c].s) for c in range(2, 23)])
    destino = tmp_path / "saida.xlsx"
    alteradas = _aplicar(p, xc.Edicao(novas=[nova, nova2]), destino)
    assert set(alteradas) == {p.aba_parte, p.tabela.parte}

    ws = openpyxl.load_workbook(destino)["PENDÊNCIAS"]
    assert [ws.cell(r, 1).value for r in range(5, 10)] == [11, 10, 9, 8, 7]
    assert ws["B5"].value == "nova & <11>"
    assert ws["B6"].value is None
    assert ws["B2"].value == 'IMPEDITIVAS SITUAÇÃO "OPEN"'      # acima do corpo: intacto
    assert ws.tables["tbRegistros"].ref == "A4:V9"
    aba = dict(_partes(destino))[p.aba_parte].decode()
    assert '<dimension ref="A2:V9"/>' in aba
    tabela = dict(_partes(destino))[p.tabela.parte].decode()
    assert 'ref="A4:V9"' in tabela and '<autoFilter ref="A4:V9"/>' in tabela


def test_partes_nao_alteradas_saem_byte_a_byte_e_na_mesma_ordem(planilha, tmp_path):
    antes = _partes(planilha)
    p = xc.ler(planilha, CHAVE)
    modelo = p.corpo()[0]
    nova = xc.LinhaNova(modelo.abertura, [(10, modelo.celulas[c].s) if c == 1 else ("x", None)
                                          for c in range(1, 23)])
    destino = tmp_path / "saida.xlsx"
    alteradas = _aplicar(p, xc.Edicao(novas=[nova]), destino)
    depois = _partes(destino)
    assert [n for n, _ in antes] == [n for n, _ in depois]
    for (nome, a), (_n, d) in zip(antes, depois):
        if nome not in alteradas:
            assert a == d, nome
    assert "xl/charts/chart1.xml" in dict(depois) and "customXml/item1.xml" in dict(depois)


def test_raiz_e_partes_fora_do_sheetData_ficam_iguais(planilha, tmp_path):
    p = xc.ler(planilha, CHAVE)
    destino = tmp_path / "saida.xlsx"
    _aplicar(p, xc.Edicao(celulas={(6, 5): ("texto trocado", "1")}), destino)
    antes = p.aba_xml
    depois = dict(_partes(destino))[p.aba_parte].decode()
    raiz = re.compile(r"^.*?<sheetData>", re.S)
    assert raiz.match(antes).group(0) == raiz.match(depois).group(0)   # raiz, cols, pane...
    assert antes.split("</sheetData>")[1] == depois.split("</sheetData>")[1]
    assert 'mc:Ignorable="x14ac"' in depois
    ET.fromstring(depois)
    ws = openpyxl.load_workbook(destino)["PENDÊNCIAS"]
    assert ws.column_dimensions["M"].hidden
    assert ws.freeze_panes == "C5"


def test_troca_preenche_e_apaga_celulas_mantendo_o_estilo(planilha, tmp_path):
    p = xc.ler(planilha, CHAVE)
    linha = p.corpo()[1]           # r=6
    s_e, s_n = linha.celulas[5].s, linha.celulas[14].s
    destino = tmp_path / "saida.xlsx"
    _aplicar(p, xc.Edicao(celulas={(6, 5): ("nova descrição", s_e), (6, 14): ("", s_n),
                                   (6, 6): (date(2026, 1, 3), linha.celulas[6].s)}), destino)
    q = xc.ler(destino, CHAVE)
    nova = q.linha(6)
    assert nova.celulas[5].valor == "nova descrição" and nova.celulas[5].s == s_e
    assert nova.celulas[14].valor is None and nova.celulas[14].s == s_n
    assert '<v>46025</v>' in nova.celulas[6].xml          # data real vira serial
    assert nova.celulas[10].xml == linha.celulas[10].xml  # manual intacta
    assert q.linha(5).xml == p.linha(5).xml               # outra linha intacta


def test_celula_ausente_e_inserida_na_ordem_das_colunas(tmp_path):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)])
    p = xc.ler(caminho, CHAVE)
    # tira a célula P5 (Documentos de referencia) e grava, como se o Excel não a tivesse escrito
    sem = p.aba_xml.replace(re.search(r'<c r="P5"[^>]*?(?:/>|>.*?</c>)', p.aba_xml).group(0), "")
    p.aba_xml = sem
    p.linhas, p.antes, p.depois, p.entre = xc._ler_linhas(sem, p.estilos, [])
    assert 16 not in p.linha(5).celulas
    destino = tmp_path / "saida.xlsx"
    _aplicar(p, xc.Edicao(celulas={(5, 16): ("DOC-1", None)}), destino)
    aba = dict(_partes(destino))[p.aba_parte].decode()
    linha = re.search(r'<row r="5".*?</row>', aba, re.S).group(0)
    refs = re.findall(r'<c r="([A-Z]+)5"', linha)
    assert refs == sorted(refs, key=xc.numero_coluna)
    assert openpyxl.load_workbook(destino)["PENDÊNCIAS"]["P5"].value == "DOC-1"


def test_estilo_novo_e_acrescentado_no_fim_e_reaproveitado(planilha, tmp_path):
    p = xc.ler(planilha, CHAVE)
    n_xfs = len(p.estilos.xfs)
    normal = p.corpo()[1].celulas[5].s
    fill_destaque = p.estilos.fill(p.corpo()[0].celulas[1].s)
    novo = p.estilos.com_fill(normal, fill_destaque)
    assert p.estilos.com_fill(normal, fill_destaque) == novo     # não duplica
    destino = tmp_path / "saida.xlsx"
    _aplicar(p, xc.Edicao(celulas={(6, 5): (xc.MANTER, novo)}), destino)
    estilos = dict(_partes(destino))["xl/styles.xml"].decode()
    original = p.estilos.xml
    assert re.search(r'<cellXfs count="(\d+)"', estilos).group(1) == str(int(novo) + 1)
    bloco = lambda x: re.search(r"<cellXfs[^>]*>(.*?)</cellXfs>", x, re.S).group(1)  # noqa: E731
    assert bloco(estilos).startswith(bloco(original))                 # índices antigos intactos
    assert int(novo) >= n_xfs or p.estilos.fill(novo) == fill_destaque
    ws = openpyxl.load_workbook(destino)["PENDÊNCIAS"]
    assert ws["E6"].fill.fgColor.rgb == "FFF4B183"
    assert ws["E6"].value == "Pendência fictícia 8"                    # valor mantido
    assert ws["E6"].border.bottom.style == "thin"                     # borda mantida


def test_estilo_existente_igual_e_reaproveitado(planilha):
    p = xc.ler(planilha, CHAVE)
    destacada, normal = p.corpo()[0], p.corpo()[2]   # a [1] tem fonte azul
    alvo = p.estilos.fill(destacada.celulas[5].s)
    # E das destacadas = E das normais com outro fill: já existe, nada é acrescentado
    assert p.estilos.com_fill(normal.celulas[5].s, alvo) == destacada.celulas[5].s
    assert p.estilos.novos == []


def test_estilo_de_linha_troca_so_o_s_do_row(planilha, tmp_path):
    p = xc.ler(planilha, CHAVE)
    abertura = p.linha(6).abertura
    destino = tmp_path / "saida.xlsx"
    _aplicar(p, xc.Edicao(estilo_linha={6: p.linha(5).s}), destino)
    nova = xc.ler(destino, CHAVE).linha(6)
    assert nova.s == p.linha(5).s
    assert {k: v for k, v in nova.attrs.items() if k != "s"} == \
        {k: v for k, v in xc._attrs(abertura).items() if k != "s"}


@pytest.mark.parametrize("texto", [
    "  espaço no início e no fim  ", "linha 1\nlinha 2", "=SOMA(A1:A2)", "a & b < c > d",
    "acentuação ÇÃÕ ¿¡",
])
def test_textos_dificeis_voltam_iguais(planilha, tmp_path, texto):
    p = xc.ler(planilha, CHAVE)
    destino = tmp_path / "saida.xlsx"
    _aplicar(p, xc.Edicao(celulas={(5, 5): (texto, "1")}), destino)
    assert xc.ler(destino, CHAVE).linha(5).celulas[5].valor == texto
    assert openpyxl.load_workbook(destino)["PENDÊNCIAS"]["E5"].value == texto
    assert openpyxl.load_workbook(destino)["PENDÊNCIAS"]["E5"].data_type == "s"


def test_caractere_de_controle_sai_e_texto_longo_e_cortado(planilha, tmp_path):
    avisos = []
    p = xc.ler(planilha, CHAVE)
    destino = tmp_path / "saida.xlsx"
    xc.gravar_zip(p, xc.aplicar(p, xc.Edicao(celulas={
        (5, 5): ("a\x01b\x0bc", "1"), (6, 5): ("x" * 40000, "1")}), avisos.append), destino)
    q = xc.ler(destino, CHAVE)
    assert q.linha(5).celulas[5].valor == "abc"
    longo = q.linha(6).celulas[5].valor
    assert len(longo) == xc.LIMITE_TEXTO and longo.endswith(xc.MARCA_CORTE)
    assert avisos


# --- Recusas --------------------------------------------------------------------

def _com(planilha, troca):
    """A planilha com a aba da tabela mexida por `troca(texto) -> texto`."""
    partes = _partes(planilha)
    with zipfile.ZipFile(planilha, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, dados in partes:
            if nome == "xl/worksheets/sheet1.xml":
                dados = troca(dados.decode()).encode()
            z.writestr(nome, dados)
    return xc.recusas(xc.ler(planilha, CHAVE), CHAVE)


@pytest.mark.parametrize("trecho, palavra", [
    ('<mergeCells count="1"><mergeCell ref="B2:C2"/></mergeCells>', "mescladas"),
    ('<conditionalFormatting sqref="A5"><cfRule type="expression" priority="1"><formula>1</formula>'
     "</cfRule></conditionalFormatting>", "condicional"),
    ('<dataValidations count="1"><dataValidation sqref="A5"/></dataValidations>', "validação"),
    ('<hyperlinks><hyperlink ref="A5" location="A1"/></hyperlinks>', "hyperlink"),
    ('<rowBreaks count="1"><brk id="5"/></rowBreaks>', "quebra de página"),
    ('<sheetProtection sheet="1"/>', "protegida"),
    ('<legacyDrawing r:id="rId9"/>', "comentário"),
    ('<drawing r:id="rId9"/>', "gráfico ou imagem"),
    ('<extLst><ext uri="{X}"><x14:sparklineGroups/></ext></extLst>', "avançados"),
])
def test_recusa_o_que_nao_da_para_deslocar(planilha, trecho, palavra):
    problemas = _com(planilha, lambda x: x.replace("</sheetData>", "</sheetData>" + trecho, 1))
    assert any(palavra in m for m in problemas), problemas


def test_recusa_formula_na_aba(planilha):
    problemas = _com(planilha, lambda x: x.replace('<c r="B2" ', '<c r="C2"><f>1+1</f><v>2</v></c><c r="B2" ', 1))
    assert any("fórmula" in m for m in problemas)


def test_recusa_dado_abaixo_e_ao_lado_da_tabela(planilha):
    problemas = _com(planilha, lambda x: x.replace(
        "</sheetData>", '<row r="20"><c r="A20" t="inlineStr"><is><t>solto</t></is></c></row></sheetData>'))
    assert any("abaixo da tabela" in m for m in problemas)


def test_recusa_chave_ausente_ou_repetida(tmp_path):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), linha_pendencia(3)])
    assert any("mais de uma vez" in m for m in xc.recusas(xc.ler(caminho, CHAVE), CHAVE))
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), linha_pendencia(2, **{CHAVE: None})])
    assert any("não tem 'Issue Number'" in m for m in xc.recusas(xc.ler(caminho, CHAVE), CHAVE))


def test_formula_de_outra_aba_que_aponta_para_o_corpo_recusa(tmp_path):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)])
    wb = openpyxl.load_workbook(caminho)   # só para montar o caso de teste
    wb.create_sheet("Resumo")["A1"] = "='PENDÊNCIAS'!A5"
    wb.create_sheet("Cabeçalho")["A1"] = "=PENDÊNCIAS!B2"   # acima do corpo: pode
    wb.save(caminho)
    problemas = xc.recusas(xc.ler(caminho, CHAVE), CHAVE)
    assert len([m for m in problemas if "outra aba" in m]) == 1


def test_nome_do_arquivo_com_o_nome_da_aba_nao_e_referencia():
    """O <c:pivotSource> cita o NOME DO ARQUIVO, que contém o nome da aba."""
    rx = xc._ref_aba("PENDÊNCIAS")
    assert xc._linhas_citadas("[ACONEX - MAPEAMENTO PENDÊNCIAS_x.xlsx]GRÁFICO SITUAÇÃO!Tabela dinâmica3", rx) == []
    assert xc._linhas_citadas("'PENDÊNCIAS'!$A$5:$B$9", rx) == [5, 9]
    assert xc._linhas_citadas("PENDÊNCIAS!3:4", rx) == [3, 4]


def test_cache_dinamico_por_intervalo_fixo_recusa_e_por_nome_da_tabela_nao(tmp_path):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)])
    partes = _partes(caminho)

    def com_cache(fonte):
        with zipfile.ZipFile(caminho, "w") as z:
            for nome, dados in partes:
                z.writestr(nome, dados)
            z.writestr("xl/pivotCache/pivotCacheDefinition1.xml",
                       f'<pivotCacheDefinition refreshOnLoad="1"><cacheSource type="worksheet">'
                       f"{fonte}</cacheSource></pivotCacheDefinition>")
        return xc.recusas(xc.ler(caminho, CHAVE), CHAVE)

    assert com_cache('<worksheetSource name="tbRegistros"/>') == []
    assert any("tabela dinâmica" in m
               for m in com_cache('<worksheetSource ref="A4:V5" sheet="PENDÊNCIAS"/>'))
