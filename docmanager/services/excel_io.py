"""I/O de Excel: exportação do Histórico Consolidado (e, adiante, MappingSheet).

A exportação preserva o layout legado (`gerar_excel_historico_formatado`
L1032-1150): mesmas larguras, wrap, autofilter, e os nomes de coluna COM "de"
(`Data de Envio`/`Data de Retorno`). As colunas novas de atraso são anexadas
ao FIM, sem perturbar quem já lê o arquivo.
"""
from __future__ import annotations

import pandas as pd
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..core.constants import MAPA_ANCORA_ITAIPU
from ..core.hierarchy import LinhaPlano
from ..core.delays import (
    COL_ATRASO_CMI,
    COL_ATRASO_ITAIPU,
    COL_DATA_PREVISTA_CTRL,
    COL_DIAS_CMI,
    COL_DIAS_ITAIPU,
)
from ..core.wide import COL_DATA_ENVIO, COL_DATA_RETORNO, COL_STATUS_ENVIO, COL_STATUS_RETORNO

# Ordem final das colunas do Excel (layout legado + novas ao fim).
_COLUNAS_LEGADO = [
    "No. do Documento", "Controle do Emissor", "Tracking ID", "Título",
    "Tipo do Documento", "Especialidade", "Subespecialidade",
    "Tipo do Documento DCC", "Subtipo DCC", "Versão", "Current", "Revisão",
    "Data de Envio", "Status Envio", "Data de Retorno", "Status Retorno",
]
_COLUNAS_NOVAS = [
    COL_DIAS_ITAIPU, COL_ATRASO_ITAIPU, COL_DIAS_CMI, COL_ATRASO_CMI, COL_DATA_PREVISTA_CTRL,
]

_LARGURAS = {
    "No. do Documento": 27, "Controle do Emissor": 27, "Tracking ID": 27,
    "Título": 60, "Tipo do Documento": 20, "Especialidade": 27,
    "Subespecialidade": 33, "Tipo do Documento DCC": 25, "Subtipo DCC": 25,
    "Versão": 8, "Current": 8, "Revisão": 10,
    "Data de Envio": 15, "Status Envio": 25, "Data de Retorno": 15, "Status Retorno": 25,
    COL_DIAS_ITAIPU: 12, COL_ATRASO_ITAIPU: 14, COL_DIAS_CMI: 12,
    COL_ATRASO_CMI: 14, COL_DATA_PREVISTA_CTRL: 20,
}

_RENOMEAR_SAIDA = {COL_DATA_ENVIO: "Data de Envio", COL_DATA_RETORNO: "Data de Retorno"}


def preparar_para_exportar(df_wide: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas internas → nomes do Excel, formata datas e ordena colunas."""
    df = df_wide.rename(columns=_RENOMEAR_SAIDA).copy()
    for col in ("Data de Envio", "Data de Retorno", COL_DATA_PREVISTA_CTRL):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y")
    ordem = [c for c in (_COLUNAS_LEGADO + _COLUNAS_NOVAS) if c in df.columns]
    # Preserva Status Envio/Retorno mesmo que a lista mude no futuro
    for c in (COL_STATUS_ENVIO, COL_STATUS_RETORNO):
        if c in df.columns and c not in ordem:
            ordem.append(c)
    return df[ordem]


# ===========================================================================
# MappingSheet — I/O da planilha de Mapeamento de Planos (KB §4, §21.1)
# ===========================================================================

# Chave lógica → texto do cabeçalho (porta do dict legado L188-233).
COLUNAS_MAPA = {
    "grupo": "GRUPO", "sistema": "SISTEMA", "oep": "OEP",
    "etapa_1": "ETAPA 1", "etapa_2": "ETAPA 2", "etapa_3": "ETAPA 3", "etapa_4": "ETAPA 4",
    "codigo_cmi": "Nº CMI", "codigo_itaipu": MAPA_ANCORA_ITAIPU,
    "descricao": "DESCRIÇÃO DO DOCUMENTO", "mes_referencia": "MÊS DE REFERÊNCIA",
    "data_previsao_etapa_1": "DATA PREVISTA EMISSÃO ETAPA 1",
    "emitido_nao_emitido": "EMITIDO / NÃO EMITIDO",
    "data_ultimo_status": "DATA ÚLTIMA EMISSÃO", "revisao": "ÚLTIMA REV. EMITIDA",
    "responsavel": "RESPONSÁVEL", "status_real": "STATUS REAL", "status_emissao": "STATUS",
    "observacao": "OBSERVAÇÃO", "nivel": "NÍVEL",
    "status_consolidado": "STATUS CONSOLIDADO", "com_itaipu": "COM ITAIPU",
    "plano_de_execucao": "PLANO DE EXECUÇÃO", "predecessor": "PREDECESSOR",
    "resumo_quantidades": "RESUMO QUANTIDADES", "filtro_etapa": "TAG ETAPA",
    "dias_status": "DIAS NO STATUS ATUAL", "situacao_prazo": "SITUAÇÃO DO PRAZO",
    "dias_atraso": "DIAS DE ATRASO", "total_ciclos": "TOTAL DE CICLOS",
    "ciclos_aprovar": "CICLOS PARA APROVAR", "downgrade": "DOWNGRADE",
    "atraso_acum_ib": "ATRASO ACUMULADO IB", "atraso_acum_cmi": "ATRASO ACUMULADO CMI",
}
# §21.1: DATA REPROGRAMADA nunca é endereçável por nome de cabeçalho (4 colunas
# com o mesmo texto). Bloqueado explicitamente em get_val/set_val.
CHAVES_PROIBIDAS = {"reprogramada_etapa_1", "reprogramada_etapa_2", "reprogramada_etapa_3", "reprogramada_etapa_4"}


class MappingSheet:
    """Encapsula a planilha de Mapeamento: localização do cabeçalho, leitura em
    LinhaPlano e escrita por chave lógica (com matador de zumbis)."""

    def __init__(self, ws):
        self.ws = ws
        self.headers, self.row_header = self._find_headers(ws)
        if not self.headers:
            raise ValueError(f"Cabeçalho não encontrado (âncora '{MAPA_ANCORA_ITAIPU}' nas 5 primeiras linhas).")
        self.start_row = self.row_header + 2

    @staticmethod
    def _find_headers(ws):
        for r in range(1, 6):
            headers = {}
            for cell in ws[r]:
                if cell.value is not None and str(cell.value).strip():
                    headers[str(cell.value).strip()] = cell.column
            if MAPA_ANCORA_ITAIPU in headers:
                return headers, r
        return {}, 0

    def _col(self, chave: str):
        if chave in CHAVES_PROIBIDAS:
            raise KeyError(f"Chave '{chave}' (DATA REPROGRAMADA) não é endereçável por nome (§21.1).")
        return self.headers.get(COLUNAS_MAPA.get(chave))

    def get_val(self, chave: str, row: int) -> str:
        col = self._col(chave)
        if col:
            v = self.ws.cell(row=row, column=col).value
            return str(v).strip() if v is not None else ""
        return ""

    def set_val(self, chave: str, row: int, valor) -> None:
        col = self._col(chave)
        if col:
            self.ws.cell(row=row, column=col).value = valor

    def matar_zumbi(self, chave: str, row: int) -> None:
        """Converte string vazia '' em None (célula zumbi → nula de verdade)."""
        col = self._col(chave)
        if col:
            cell = self.ws.cell(row=row, column=col)
            if cell.value is not None and str(cell.value).strip() == "":
                cell.value = None

    @property
    def max_row(self) -> int:
        return self.ws.max_row

    def ler_linhas(self) -> list[LinhaPlano]:
        """Lê todas as linhas de dados (ordem física preservada = hierarquia)."""
        linhas = []
        for row in range(self.start_row, self.max_row + 1):
            cod_it = self.get_val("codigo_itaipu", row)
            cod_cmi = self.get_val("codigo_cmi", row)
            if not cod_it and not cod_cmi:
                continue
            linhas.append(LinhaPlano(
                row=row, cod_itaipu=cod_it, cod_cmi=cod_cmi,
                nivel=self.get_val("nivel", row),
                descricao=self.get_val("descricao", row),
                status_real=self.get_val("status_real", row),
                status_consolidado=self.get_val("status_consolidado", row),
            ))
        return linhas


# Paleta (alinhada ao tema do app: slate #2C3E50).
_FILL_HEADER = PatternFill("solid", fgColor="2C3E50")        # cabeçalho legado
_FILL_HEADER_NOVO = PatternFill("solid", fgColor="1F6F5C")   # cabeçalho colunas novas (teal)
_FILL_BANDA = PatternFill("solid", fgColor="F4F6F7")         # linha ímpar (zebra)
_FONT_HEADER = Font(color="FFFFFF", bold=True, size=10, name="Segoe UI")
_FONT_DADO = Font(size=10, name="Segoe UI")
_BORDA_FINA = Side(style="thin", color="D5DBDB")
_BORDER = Border(left=_BORDA_FINA, right=_BORDA_FINA, top=_BORDA_FINA, bottom=_BORDA_FINA)
_COLS_NOVAS_SET = set(_COLUNAS_NOVAS)
_COLS_NUM = {COL_DIAS_ITAIPU, COL_ATRASO_ITAIPU, COL_DIAS_CMI, COL_ATRASO_CMI}
_COLS_CENTRO = {"Versão", "Current", "Revisão", *_COLS_NUM,
                "Data de Envio", "Data de Retorno", COL_DATA_PREVISTA_CTRL}


def _estilizar_historico(ws, df: pd.DataFrame) -> None:
    n_rows, n_cols = len(df), len(df.columns)
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30
    col_por_nome = {c: i + 1 for i, c in enumerate(df.columns)}

    # Cabeçalho
    for c, nome in enumerate(df.columns, 1):
        cell = ws.cell(1, c)
        cell.fill = _FILL_HEADER_NOVO if nome in _COLS_NOVAS_SET else _FILL_HEADER
        cell.font = _FONT_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
        ws.column_dimensions[get_column_letter(c)].width = _LARGURAS.get(nome, 16)

    # Corpo: fonte, borda, zebra, alinhamento, formato numérico
    for r in range(2, n_rows + 2):
        banda = _FILL_BANDA if (r % 2 == 0) else None
        for c in range(1, n_cols + 1):
            cell = ws.cell(r, c)
            cell.font = _FONT_DADO
            cell.border = _BORDER
            nome = df.columns[c - 1]
            centro = nome in _COLS_CENTRO
            cell.alignment = Alignment(wrap_text=True, vertical="center",
                                       horizontal="center" if centro else "left")
            if nome in _COLS_NUM:
                cell.number_format = "0"
            if banda is not None:
                cell.fill = banda

    # Escala de cores nos atrasos (verde → amarelo → vermelho)
    if n_rows:
        rule = ColorScaleRule(start_type="num", start_value=0, start_color="63BE7B",
                              mid_type="num", mid_value=15, mid_color="FFEB84",
                              end_type="percentile", end_value=90, end_color="F8696B")
        for nome in (COL_ATRASO_ITAIPU, COL_ATRASO_CMI):
            if nome in col_por_nome:
                letra = get_column_letter(col_por_nome[nome])
                ws.conditional_formatting.add(f"{letra}2:{letra}{n_rows + 1}", rule)

    ws.auto_filter.ref = ws.dimensions


def exportar_historico(df_wide: pd.DataFrame, caminho_saida) -> tuple[bool, str]:
    if df_wide is None or df_wide.empty:
        return False, "DataFrame vazio."
    df = preparar_para_exportar(df_wide)
    try:
        with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Histórico")
            _estilizar_historico(writer.sheets["Histórico"], df)
        return True, f"Arquivo gerado com sucesso: {caminho_saida}"
    except Exception as e:  # noqa: BLE001 — reportado ao chamador
        return False, f"Erro ao salvar Excel: {e}"
