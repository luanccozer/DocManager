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
                           incluir_fase=False, cabecalhos=None):
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
           "fase": "FASE DE PROJETO"}
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
    ws.append([cab[k] for k in chaves])
    for lin in linhas:
        ws.append([lin.get(k, "") for k in chaves])
    wb.save(path)
    return path
