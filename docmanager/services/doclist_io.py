"""I/O da planilha **Doc List Mapping** (KB §27.1).

Duas responsabilidades:
  - `DocListSheet` — abre a planilha, localiza o cabeçalho e lê/escreve por
    chave lógica, tratando datas como DATA NATIVA do Excel (e não texto), que é
    o que o dashboard precisa para agrupar por período;
  - `exportar_analise_periodo` — o Excel do relatório "próximos a emitir".
"""
from __future__ import annotations

from datetime import date

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..core.doclist import (
    ANCORA_DOCLIST,
    CABECALHOS_LEGADOS,
    COLUNAS_DOCLIST,
    LinhaDocList,
)
from ..core.normalize import remover_acentos
from .excel_io import celula_para_date

FORMATO_DATA = "DD/MM/YYYY"


def _norm_cabecalho(v) -> str:
    """Cabeçalho comparável: sem acento, MAIÚSCULAS, espaços colapsados.

    O colapso cobre as quebras de linha que o Excel esconde dentro da célula —
    a mesma armadilha que escondia as colunas do Controle de Documentos.
    """
    import re
    s = remover_acentos(str(v)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip().upper()


# Leitura de célula de data: implementação única, compartilhada com o Mapa.
_para_date = celula_para_date


class DocListSheet:
    """Planilha do Doc List Mapping: cabeçalho localizado por âncora, acesso por
    chave lógica e reconhecimento dos cabeçalhos LEGADOS (a planilha que a
    equipe montou em cima do mapeamento ainda chama a coluna de 'TROCAR')."""

    def __init__(self, ws):
        self.ws = ws
        self.headers, self.row_header = self._find_headers(ws)
        if not self.headers:
            raise ValueError(
                f"Cabeçalho do Doc List não encontrado (âncora '{ANCORA_DOCLIST}' "
                f"nas 10 primeiras linhas).")
        self.start_row = self.row_header + 1
        self._col_por_chave = self._mapear_colunas()

    # ------------------------------------------------------------------
    @staticmethod
    def _find_headers(ws):
        alvo = _norm_cabecalho(ANCORA_DOCLIST)
        for r in range(1, 11):
            headers = {}
            for cell in ws[r]:
                if cell.value is not None and str(cell.value).strip():
                    headers[_norm_cabecalho(cell.value)] = cell.column
            if alvo in headers:
                return headers, r
        return {}, 0

    def _mapear_colunas(self) -> dict[str, int]:
        """chave lógica → índice da coluna, aceitando o nome oficial ou legado."""
        mapa: dict[str, int] = {}
        for chave, titulo in COLUNAS_DOCLIST.items():
            nomes = (titulo, *CABECALHOS_LEGADOS.get(chave, ()))
            for nome in nomes:
                col = self.headers.get(_norm_cabecalho(nome))
                if col:
                    mapa[chave] = col
                    break
        return mapa

    @property
    def colunas_ausentes(self) -> list[str]:
        return [t for c, t in COLUNAS_DOCLIST.items() if c not in self._col_por_chave]

    @property
    def max_row(self) -> int:
        return self.ws.max_row

    # ------------------------------------------------------------------
    def get_val(self, chave: str, row: int) -> str:
        col = self._col_por_chave.get(chave)
        if not col:
            return ""
        v = self.ws.cell(row=row, column=col).value
        return str(v).strip() if v is not None else ""

    def set_val(self, chave: str, row: int, valor) -> bool:
        col = self._col_por_chave.get(chave)
        if not col:
            return False
        self.ws.cell(row=row, column=col).value = valor
        return True

    def get_data(self, chave: str, row: int) -> date | None:
        col = self._col_por_chave.get(chave)
        if not col:
            return None
        return _para_date(self.ws.cell(row=row, column=col).value)

    def set_data(self, chave: str, row: int, valor: date | None) -> bool:
        """Grava DATA NATIVA (com formato dd/mm/aaaa) — nunca texto, senão o
        dashboard não consegue agrupar por período."""
        col = self._col_por_chave.get(chave)
        if not col:
            return False
        cell = self.ws.cell(row=row, column=col)
        cell.value = valor
        if valor is not None:
            cell.number_format = FORMATO_DATA
        return True

    def renomear_cabecalhos_legados(self) -> list[tuple[str, str]]:
        """Atualiza no arquivo os cabeçalhos antigos para o nome oficial
        (`TROCAR` → `DATA-ALVO EMISSÃO`, etc.). Devolve os pares trocados."""
        trocas: list[tuple[str, str]] = []
        for chave, titulo in COLUNAS_DOCLIST.items():
            col = self._col_por_chave.get(chave)
            if not col:
                continue
            cell = self.ws.cell(row=self.row_header, column=col)
            atual = str(cell.value or "").strip()
            if _norm_cabecalho(atual) != _norm_cabecalho(titulo):
                cell.value = titulo
                trocas.append((atual, titulo))
        if trocas:
            self.headers, _ = self._find_headers(self.ws)
            self._col_por_chave = self._mapear_colunas()
        return trocas

    def matar_zumbi(self, chave: str, row: int) -> None:
        """String vazia → None (célula zumbi vira nula de verdade)."""
        col = self._col_por_chave.get(chave)
        if not col:
            return
        cell = self.ws.cell(row=row, column=col)
        if cell.value is not None and str(cell.value).strip() == "":
            cell.value = None

    # ------------------------------------------------------------------
    def ler_linhas(self) -> list[LinhaDocList]:
        """Lê as linhas de dados na ordem física (que É a hierarquia)."""
        linhas: list[LinhaDocList] = []
        for row in range(self.start_row, self.max_row + 1):
            cod_it = self.get_val("codigo_itaipu", row)
            cod_cmi = self.get_val("codigo_cmi", row)
            if not cod_it and not cod_cmi:
                continue
            linhas.append(LinhaDocList(
                row=row, cod_itaipu=cod_it, cod_cmi=cod_cmi,
                nivel=self.get_val("nivel", row),
                grupo=self.get_val("grupo", row),
                sistema=self.get_val("sistema", row),
                fase_projeto=self.get_val("fase_projeto", row),
                descricao=self.get_val("descricao", row),
                responsavel=self.get_val("responsavel", row),
                status_real=self.get_val("status_real", row),
                status_consolidado=self.get_val("status_consolidado", row),
                emitido_nao_emitido=self.get_val("emitido_nao_emitido", row),
                data_prevista=self.get_data("data_prevista", row),
                data_reprogramada=self.get_data("data_reprogramada", row),
                predecessor=self.get_val("predecessor", row),
            ))
        return linhas


def ler_linhas_doclist(caminho, sheet=None) -> list[LinhaDocList]:
    """Atalho de leitura (a Análise por Período não precisa escrever nada)."""
    import openpyxl
    wb = openpyxl.load_workbook(caminho, data_only=True)
    try:
        ws = wb[sheet] if (sheet and not isinstance(sheet, int)) else wb.active
        return DocListSheet(ws).ler_linhas()
    finally:
        wb.close()


# ===========================================================================
# Estilo (mesma paleta dos demais Excel do app: slate #2C3E50 + zebra)
# ===========================================================================
_FILL_HEADER = PatternFill("solid", fgColor="2C3E50")
_FILL_BANDA = PatternFill("solid", fgColor="F4F6F7")
_FILL_DESTAQUE = PatternFill("solid", fgColor="FDEBD0")     # linha de subtotal
_FONT_HEADER = Font(color="FFFFFF", bold=True, size=10, name="Segoe UI")
_FONT_DADO = Font(size=10, name="Segoe UI")
_FONT_VENCIDO = Font(color="9C0006", size=10, name="Segoe UI", bold=True)
_FONT_TITULO = Font(size=13, bold=True, name="Segoe UI", color="2C3E50")
_BORDA_FINA = Side(style="thin", color="D5DBDB")
_BORDER = Border(left=_BORDA_FINA, right=_BORDA_FINA, top=_BORDA_FINA, bottom=_BORDA_FINA)



_COLS_RELATORIO = [
    ("Data-Alvo", "data_alvo", 13), ("Origem", "origem", 13), ("Dias", "dias", 8),
    ("Situação", "situacao", 12), ("Grupo", "grupo", 14), ("Sistema", "sistema", 18),
    ("Fase de Projeto", "fase_projeto", 18), ("Nº CMI", "cod_cmi", 26),
    ("N° Itaipu", "cod_itaipu", 28), ("Descrição do Documento", "descricao", 70),
    ("Responsible", "responsavel", 16), ("Status Consolidado", "status_consolidado", 22),
    ("Predecessor", "predecessor", 26),
]


def exportar_analise_periodo(itens, resumo_dados, caminho_saida, *, titulo_janela: str,
                             hoje: date, sem_data=()) -> tuple[bool, str]:
    """Excel da análise por período: cabeçalho executivo, quadro por mês, o
    detalhe dos documentos e — quando houver — os que estão sem planejamento."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Previstos no Período"

    ws["A1"] = "Doc List Mapping — Documentos previstos para emissão"
    ws["A1"].font = _FONT_TITULO
    ws["A2"] = (f"Período: {titulo_janela}   |   Gerado em {hoje.strftime('%d/%m/%Y')}   |   "
                f"{resumo_dados['total']} documento(s): {resumo_dados['vencidos']} vencido(s), "
                f"{resumo_dados['a_emitir']} a emitir, {resumo_dados['reprogramados']} com data reprogramada")
    ws["A2"].font = Font(size=10, name="Segoe UI", color="566573")

    linha = 4
    por_mes = resumo_dados.get("por_mes") or {}
    if por_mes:
        ws.cell(linha, 1, "Quantidade por mês").font = Font(size=11, bold=True, name="Segoe UI")
        linha += 1
        for c, nome in enumerate(("Mês", "Documentos"), 1):
            cell = ws.cell(linha, c, nome)
            cell.fill = _FILL_HEADER
            cell.font = _FONT_HEADER
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = _BORDER
        linha += 1
        for mes, qtd in por_mes.items():
            ws.cell(linha, 1, mes).font = _FONT_DADO
            ws.cell(linha, 2, qtd).font = _FONT_DADO
            for c in (1, 2):
                ws.cell(linha, c).border = _BORDER
                ws.cell(linha, c).fill = _FILL_DESTAQUE
            linha += 1
        linha += 1

    cab_row = linha
    for c, (nome, _attr, largura) in enumerate(_COLS_RELATORIO, 1):
        cell = ws.cell(cab_row, c, nome)
        cell.fill = _FILL_HEADER
        cell.font = _FONT_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
        ws.column_dimensions[get_column_letter(c)].width = largura
    ws.row_dimensions[cab_row].height = 26

    centro = {"Data-Alvo", "Origem", "Dias", "Situação", "Nível"}
    r = cab_row + 1
    for it in itens:
        banda = _FILL_BANDA if (r - cab_row) % 2 == 0 else None
        vencido = (not it.emitido) and it.dias < 0
        for c, (nome, attr, _l) in enumerate(_COLS_RELATORIO, 1):
            cell = ws.cell(r, c, getattr(it, attr))
            cell.font = _FONT_VENCIDO if vencido else _FONT_DADO
            cell.border = _BORDER
            cell.alignment = Alignment(wrap_text=True, vertical="center",
                                       horizontal="center" if nome in centro else "left")
            if nome == "Data-Alvo":
                cell.number_format = FORMATO_DATA
            if banda is not None:
                cell.fill = banda
        r += 1
    ws.freeze_panes = ws.cell(cab_row + 1, 1).coordinate
    if itens:
        ws.auto_filter.ref = f"A{cab_row}:{get_column_letter(len(_COLS_RELATORIO))}{r - 1}"

    if sem_data:
        ws2 = wb.create_sheet("Sem Planejamento")
        cabs = ["Grupo", "Sistema", "Fase de Projeto", "Nº CMI", "N° Itaipu",
                "Descrição do Documento", "Status Consolidado"]
        larguras = [14, 18, 18, 26, 28, 70, 22]
        ws2.append(cabs)
        for c, (nome, larg) in enumerate(zip(cabs, larguras), 1):
            cell = ws2.cell(1, c)
            cell.fill = _FILL_HEADER
            cell.font = _FONT_HEADER
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = _BORDER
            ws2.column_dimensions[get_column_letter(c)].width = larg
        for i, ln in enumerate(sem_data, start=2):
            valores = [ln.grupo, ln.sistema, ln.fase_projeto, ln.cod_cmi,
                       ln.cod_itaipu, ln.descricao, ln.status_consolidado]
            for c, v in enumerate(valores, 1):
                cell = ws2.cell(i, c, v)
                cell.font = _FONT_DADO
                cell.border = _BORDER
                cell.alignment = Alignment(wrap_text=True, vertical="center")
                if i % 2 == 0:
                    cell.fill = _FILL_BANDA
        ws2.freeze_panes = "A2"
        ws2.auto_filter.ref = ws2.dimensions

    try:
        wb.save(caminho_saida)
        return True, f"Relatório salvo em:\n{caminho_saida}"
    except PermissionError:
        return False, "O arquivo parece estar aberto no Excel. Feche-o e tente novamente."
    except Exception as e:  # noqa: BLE001
        return False, f"Não foi possível salvar: {e}"
