"""I/O de Excel: exportação do Histórico Consolidado (e, adiante, MappingSheet).

A exportação preserva o layout legado (`gerar_excel_historico_formatado`
L1032-1150): mesmas larguras, wrap, autofilter, e os nomes de coluna COM "de"
(`Data de Envio`/`Data de Retorno`). As colunas novas de atraso são anexadas
ao FIM, sem perturbar quem já lê o arquivo.
"""
from __future__ import annotations

import pandas as pd
from openpyxl.styles import Alignment

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


def exportar_historico(df_wide: pd.DataFrame, caminho_saida) -> tuple[bool, str]:
    if df_wide is None or df_wide.empty:
        return False, "DataFrame vazio."
    df = preparar_para_exportar(df_wide)
    try:
        with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Histórico")
            ws = writer.sheets["Histórico"]
            for column_cells in ws.columns:
                header = column_cells[0].value
                if header in _LARGURAS:
                    ws.column_dimensions[column_cells[0].column_letter].width = _LARGURAS[header]
                for cell in column_cells:
                    cell.alignment = Alignment(wrap_text=True, vertical="center")
            ws.auto_filter.ref = ws.dimensions
        return True, f"Arquivo gerado com sucesso: {caminho_saida}"
    except Exception as e:  # noqa: BLE001 — reportado ao chamador
        return False, f"Erro ao salvar Excel: {e}"
