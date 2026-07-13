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

from ..core.constants import COLS_STRIP_CARGA, MAPA_ANCORA_ITAIPU
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
# Data Prevista (Controle) é interna (só para cálculo dos atrasos), não vai ao Excel.
_COLUNAS_NOVAS = [COL_DIAS_ITAIPU, COL_ATRASO_ITAIPU, COL_DIAS_CMI, COL_ATRASO_CMI]

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


def carregar_base_aconex(caminho, aba=0) -> pd.DataFrame:
    """Carrega a base Aconex como o backend espera: dtype=str, sem NaN, strip
    nas colunas-chave (porta de DataManager.carregar_aconex)."""
    df = pd.read_excel(caminho, sheet_name=aba, dtype=str).fillna("")
    for col in COLS_STRIP_CARGA:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


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

    def set_reprogramada_etapa1(self, row: int, valor) -> bool:
        """Escreve a REPROGRAMAÇÃO na coluna DATA REPROGRAMADA da ETAPA 1.

        §21.1: há 4 colunas 'DATA REPROGRAMADA' (não endereçáveis por nome). A da
        etapa 1 é, por posição, a imediatamente à direita de 'DATA PREVISTA
        EMISSÃO ETAPA 1'. Só escreve se o cabeçalho vizinho de fato normalizar
        para REPROGRAMADA — senão devolve False sem tocar em nada."""
        from ..core.normalize import remover_acentos
        col_prev = self.headers.get(COLUNAS_MAPA["data_previsao_etapa_1"])
        if not col_prev:
            return False
        col_reprog = col_prev + 1
        hdr = self.ws.cell(row=self.row_header, column=col_reprog).value
        if hdr and "REPROGRAMADA" in remover_acentos(str(hdr)).upper():
            self.ws.cell(row=row, column=col_reprog).value = valor
            return True
        return False

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


def exportar_dataframe(df: pd.DataFrame, caminho_saida, sheet_name="Relatório",
                       larguras: dict | None = None) -> tuple[bool, str]:
    """Exportação genérica com o mesmo cabeçalho profissional (slate + zebra)."""
    if df is None or df.empty:
        return False, "Nada a exportar."
    try:
        with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]
            ws.freeze_panes = "A2"
            ws.row_dimensions[1].height = 26
            for c, nome in enumerate(df.columns, 1):
                cell = ws.cell(1, c)
                cell.fill = _FILL_HEADER
                cell.font = _FONT_HEADER
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                cell.border = _BORDER
                ws.column_dimensions[get_column_letter(c)].width = (larguras or {}).get(nome, 22)
            for r in range(2, len(df) + 2):
                banda = _FILL_BANDA if r % 2 == 0 else None
                for c in range(1, len(df.columns) + 1):
                    cell = ws.cell(r, c)
                    cell.font = _FONT_DADO
                    cell.border = _BORDER
                    cell.alignment = Alignment(wrap_text=True, vertical="center")
                    if banda is not None:
                        cell.fill = banda
            ws.auto_filter.ref = ws.dimensions
        return True, f"Arquivo gerado: {caminho_saida}"
    except Exception as e:  # noqa: BLE001
        return False, f"Erro ao salvar Excel: {e}"


def exportar_delta_arvore(arvore, caminho_saida, *, agrupador="Grupo", visao="Efetiva",
                          ocultar_aprovados=False) -> tuple[bool, str]:
    """Exporta a árvore de mudanças do Delta (porta de DeltaView.exportar_excel).

    Cabeçalhos dinâmicos por visão; datas da Bruta viram data nativa do Excel.
    """
    import openpyxl
    from datetime import datetime as _dt

    aprovados = {"Aprovado", "Aprovado com Comentários", "Para Assinatura"}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mudanças do Período"
    if visao == "Efetiva":
        headers = [agrupador, "Nível", "Documento", "Título",
                   "Status Aconex (Antes)", "Status Efetivo (Antes)",
                   "Status Aconex (Depois)", "Status Efetivo (Depois)"]
    else:
        headers = [agrupador, "Nível", "Documento", "Título",
                   "Revisão (Antes)", "Data (Antes)", "Status Aconex (Antes)", "Status Efetivo (Antes)",
                   "Revisão (Depois)", "Data (Depois)", "Status Aconex (Depois)", "Status Efetivo (Depois)"]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = _FILL_HEADER
        cell.font = _FONT_HEADER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER

    def _data_excel(s):
        if s and s != "-":
            try:
                return _dt.strptime(s, "%d/%m/%y").date()
            except Exception:  # noqa: BLE001
                return s
        return "-"

    row_idx = 2
    for grupo in sorted(arvore.keys()):
        for nivel, docs in arvore[grupo].items():
            for d in docs:
                if ocultar_aprovados and str(d["real_antes"]).strip() in aprovados:
                    continue
                if visao == "Efetiva":
                    linha = [grupo, nivel, d["doc"], d["titulo"], d["raw_antes"], d["real_antes"],
                             d["raw_depois"], d["real_depois"]]
                else:
                    linha = [grupo, nivel, d["doc"], d["titulo"],
                             d.get("rev_antes", "-"), _data_excel(d.get("data_antes", "-")),
                             d["raw_antes"], d["real_antes"],
                             d.get("rev_depois", "-"), _data_excel(d.get("data_depois", "-")),
                             d["raw_depois"], d["real_depois"]]
                ws.append(linha)
                if visao == "Bruta":
                    if linha[5] != "-":
                        ws.cell(row=row_idx, column=6).number_format = "dd/mm/yyyy"
                    if linha[9] != "-":
                        ws.cell(row=row_idx, column=10).number_format = "dd/mm/yyyy"
                banda = _FILL_BANDA if row_idx % 2 == 0 else None
                for cell in ws[row_idx]:
                    cell.border = _BORDER
                    cell.font = _FONT_DADO
                    cell.alignment = Alignment(vertical="center", wrap_text=True)
                    if banda is not None:
                        cell.fill = banda
                row_idx += 1

    for col in ws.columns:
        largura = max((len(str(c.value)) for c in col if c.value is not None), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(largura + 2, 60)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    try:
        wb.save(caminho_saida)
        return True, f"Relatório salvo em:\n{caminho_saida}"
    except PermissionError:
        return False, "O arquivo parece estar aberto no Excel. Feche-o e tente novamente."
    except Exception as e:  # noqa: BLE001
        return False, f"Não foi possível salvar: {e}"


# Cores do gráfico de status (porta do legado: VERDE/AZUL/VERMELHO/CINZA).
_STATUS_ORDEM = ["Aprovado", "Para Assinatura", "Para Aprovação", "Aprovado com Comentários",
                 "Em Processo", "Não Aprovado", "NÃO EMITIDO"]
_STATUS_ORDEM_MODELO = [
    "Aprovado - LOD 350", "Aprovado - LOD 300", "Aprovado - Fase Preliminar",
    "Em Análise - LOD 350", "Em Análise - LOD 300", "Em Análise - Fase Preliminar",
    "Emissão Inicial - LOD 350", "Emissão Inicial - LOD 300", "Emissão Inicial - Fase Preliminar",
    "Não Aprovado - LOD 350", "Não Aprovado - LOD 300", "Não Aprovado - Fase Preliminar",
]


def _cor_status(status: str) -> str:
    st = status.upper()
    if st in ("APROVADO", "APROVADO COM COMENTÁRIOS", "PARA ASSINATURA", "PARA APROVAÇÃO") or st.startswith("APROVADO -"):
        return "16B63C"          # verde
    if "NÃO" in st or "NAO" in st:
        return "C00000"          # vermelho
    if st == "EM PROCESSO" or st.startswith("EM ANÁLISE -") or st.startswith("EMISSÃO INICIAL -"):
        return "0070C0"          # azul
    return "808080"              # cinza


def exportar_status_documentos(linhas: list[dict], contador, caminho_saida, *,
                               tem_modelos=False) -> tuple[bool, str]:
    """Excel de Status de Documentos com o gráfico de barras (porta do legado).

    `linhas`: dicts com Código Itaipu/CMI, Título, Revisão, Data, Status Aconex,
    Status Real. `contador`: dict {status: qtd}.
    """
    import openpyxl
    from openpyxl.chart import BarChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.chart.marker import DataPoint

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Status Documentos"
    larguras = [25, 25, 60, 10, 15, 25, 25]
    for i, w in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    headers = ["Código Itaipu", "Código CMI", "Título", "Revisão", "Data", "Status Aconex", "Status Real"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="366092")
        cell.alignment = Alignment(horizontal="center")
    ws.freeze_panes = "A2"

    for r, d in enumerate(linhas, 2):
        ws.cell(r, 1, d.get("Código Itaipu", ""))
        ws.cell(r, 2, d.get("Código CMI", ""))
        ws.cell(r, 3, d.get("Título", ""))
        ws.cell(r, 4, d.get("Revisão", "")).alignment = Alignment(horizontal="center")
        ws.cell(r, 5, d.get("Data", "")).alignment = Alignment(horizontal="center")
        ws.cell(r, 6, d.get("Status Aconex", ""))
        cell = ws.cell(r, 7, d.get("Status Real", ""))
        cell.alignment = Alignment(horizontal="center", vertical="center")
        s = str(d.get("Status Real", ""))
        if s in ("Aprovado", "Aprovado com Comentários", "Para Assinatura") or s.startswith("Aprovado -"):
            cell.font = Font(color="006100")
            cell.fill = PatternFill("solid", fgColor="C6EFCE")
        elif s == "Em Processo" or s.startswith("Em Análise -") or s.startswith("Emissão Inicial -"):
            cell.font = Font(color="0000FF")
        elif s in ("Não Aprovado", "NÃO EMITIDO") or s.startswith("Não Aprovado -"):
            cell.font = Font(color="9C0006")
            cell.fill = PatternFill("solid", fgColor="FFC7CE")
    ws.auto_filter.ref = f"A1:G{len(linhas) + 1}"

    # Tabela auxiliar + gráfico
    col_chart = 10
    ws.cell(1, col_chart, "Status")
    ws.cell(1, col_chart + 1, "Qtd")
    ordem = list(_STATUS_ORDEM) + (list(_STATUS_ORDEM_MODELO) if tem_modelos else [])
    row_aux = 2
    cores = []
    vistos = set()
    for st in ordem:
        val = contador.get(st, 0)
        if val > 0:
            ws.cell(row_aux, col_chart, st)
            ws.cell(row_aux, col_chart + 1, val)
            cores.append(_cor_status(st))
            vistos.add(st)
            row_aux += 1
    for st, val in contador.items():
        if st not in vistos and val > 0:
            ws.cell(row_aux, col_chart, st)
            ws.cell(row_aux, col_chart + 1, val)
            cores.append(_cor_status(st))
            row_aux += 1
    try:
        chart = BarChart()
        chart.type = "bar"
        chart.title = "Situação da documentação analisada"
        chart.legend = None
        chart.height, chart.width = 10, 20
        data = Reference(ws, min_col=col_chart + 1, min_row=1, max_row=row_aux - 1)
        cats = Reference(ws, min_col=col_chart, min_row=2, max_row=row_aux - 1)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.y_axis.delete = False
        chart.x_axis.delete = False
        series = chart.series[0]
        for i, cor in enumerate(cores):
            pt = DataPoint(idx=i)
            pt.graphicalProperties.solidFill = cor
            series.dPt.append(pt)
        series.dLbls = DataLabelList()
        series.dLbls.showVal = True
        ws.add_chart(chart, "J5")
    except Exception:  # noqa: BLE001 — gráfico é acessório; nunca derruba a exportação
        pass

    try:
        wb.save(caminho_saida)
        return True, f"Relatório gerado: {caminho_saida}"
    except PermissionError:
        return False, "O arquivo parece estar aberto no Excel. Feche-o e tente novamente."
    except Exception as e:  # noqa: BLE001
        return False, f"Não foi possível salvar: {e}"


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
