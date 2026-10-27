"""Leitura das planilhas do Transpasse de Fase.

As colunas são achadas pelo TÍTULO, não pela letra: as planilhas são mantidas à
mão, e uma coluna inserida no meio não pode desalinhar as datas. Os títulos são
comparados sem acento, em maiúsculas e com os espaços normalizados ('DATA
PREVISTA  INSPEÇÃO ' e 'DATA PREVISTA INSPEÇÃO' são o mesmo título).
"""
from __future__ import annotations

import openpyxl

from ..core.normalize import celula_para_date, remover_acentos
from ..core.transpasse import NOME, GrupoLido

# Até que linha procurar o cabeçalho (há título e linhas em branco antes dele).
_LINHAS_CABECALHO = 30

# Planilha principal (acompanhamento do transpasse): coluna → como reconhecer o título.
_PRINCIPAL = {
    "id": lambda t: t == "ID GRUPO EQUIPAMENTOS",
    "sala": lambda t: t == "CAPITULO",
    "nome": lambda t: t == "GRUPO EQUIPAMENTOS",
    "conv": lambda t: t.startswith("CONVOCACAO"),
    "insp": lambda t: "INSPECAO REALIZADA" in t,
    "ccmlc": lambda t: t == "DATA EMISSAO CCMLC",
    "transp": lambda t: "TRANSPASSE" in t,
    "inicio": lambda t: "INICIO" in t and "COMISSIONAMENTO" in t,
}
_MARCOS_PRINCIPAL = ("conv", "insp", "ccmlc", "transp", "inicio")
# Sem estas o quadro sairia faltando cores sem ninguém perceber (o início do
# comissionamento é opcional: costuma vir da planilha complementar).
_OBRIGATORIAS_PRINCIPAL = {"sala": "CAPÍTULO", "conv": "CONVOCAÇÃO CONJUNTA REALIZADA EM",
                           "insp": "DATA INSPEÇÃO REALIZADA CMI/ITAIPU", "ccmlc": "DATA EMISSÃO CCMLC",
                           "transp": "DATA TRANSPASSE FASE"}


# Planilha complementar (controle do início do comissionamento): um par de
# linhas por grupo, "Prevista" e "Realizada"; só a realizada é lida. Os títulos
# trazem o prazo da etapa ("Inspeção IB \n1 dia") e grafias que variam de uma
# aba para a outra ("InicIo"/"Inico do Comissionamento").
_COMPLEMENTAR = {
    "sala": lambda t: t == "SALA",
    "grupo": lambda t: t == "GRUPO",
    "nome": lambda t: t.startswith("DESCRICAO"),
    "execucao": lambda t: t.startswith("EXECUCAO"),
    "conv": lambda t: t.startswith("CONVOCACAO"),
    "insp": lambda t: t.startswith("INSPECAO"),
    "ccmlc": lambda t: t.startswith("EMISSAO CCMLC"),
    "transp": lambda t: t.startswith("TRANSPASSE"),
    "inicio": lambda t: t.startswith("INIC") and "COMISSIONAMENTO" in t,
}
_OBRIGATORIAS_COMPLEMENTAR = {"conv": "Convocação Inspeção IB", "insp": "Inspeção IB", "ccmlc": "Emissão CCMLC",
                              "transp": "Transpasse de fase", "inicio": "Início do Comissionamento"}
# A complementar numera os grupos 1, 2, 3...: o grupo N é o GEQ-001-NNN da principal.
PREFIXO_COMPLEMENTAR = "GEQ-001-"


def _titulo(valor) -> str:
    return " ".join(remover_acentos(valor).upper().split()) if valor is not None else ""


def _texto(valor) -> str:
    """Texto de célula limpo: o Excel grava a quebra de linha do Windows como
    '_x000D_' e o nome do grupo às vezes vem quebrado em várias linhas."""
    return " ".join(str(valor).replace("_x000D_", " ").split()) if valor is not None else ""


def _ler_datas(ws, linha: int, col: dict, marcos, planilha: str) -> tuple[dict, list[str]]:
    """Datas dos `marcos` na `linha`. Texto que não é data (ex.: '14/1O/2026',
    com a letra O) vira aviso: senão a data sumiria do quadro sem explicação.
    Vazio, '[Data Início]', '-' e fórmula (previsão) são ignorados calados."""
    datas, avisos = {}, []
    for marco in marcos:
        if marco not in col:
            continue
        valor = ws.cell(linha, col[marco]).value
        if data := celula_para_date(valor):
            datas[marco] = data
        elif isinstance(valor, str) and (texto := valor.strip()) and texto != "-" \
                and not texto.startswith("=") and not (texto.startswith("[") and texto.endswith("]")):
            avisos.append(f"Na planilha {planilha}: {NOME[marco]} “{texto}” não é uma data")
    return datas, avisos


def _colunas(ws, linha: int, regras: dict) -> dict[str, int]:
    """Título → número da coluna, para as regras que casarem na `linha`."""
    achadas = {}
    for celula in ws[linha]:
        titulo = _titulo(celula.value)
        for chave, casa in regras.items():
            if titulo and chave not in achadas and casa(titulo):
                achadas[chave] = celula.column
    return achadas


def ler_planilha_principal(caminho) -> list[GrupoLido]:
    """Grupos da planilha de acompanhamento do transpasse, na ordem da planilha.
    A aba é a que tem a coluna 'ID GRUPO EQUIPAMENTOS'."""
    wb = openpyxl.load_workbook(caminho)
    for ws in wb.worksheets:
        for linha in ws.iter_rows(max_row=_LINHAS_CABECALHO):
            if any(_titulo(c.value) == "ID GRUPO EQUIPAMENTOS" for c in linha):
                return _ler_grupos_principal(ws, linha[0].row)
    raise ValueError("Não encontrei a coluna 'ID GRUPO EQUIPAMENTOS' em nenhuma aba. "
                     "Esta é a planilha de acompanhamento do transpasse?")


def _ler_grupos_principal(ws, linha_cabecalho: int) -> list[GrupoLido]:
    col = _colunas(ws, linha_cabecalho, _PRINCIPAL)
    if faltam := [titulo for chave, titulo in _OBRIGATORIAS_PRINCIPAL.items() if chave not in col]:
        raise ValueError(f"Faltam colunas na planilha de acompanhamento (aba '{ws.title}'): {', '.join(faltam)}")
    grupos = []
    for linha in range(linha_cabecalho + 1, ws.max_row + 1):
        ident = _texto(ws.cell(linha, col["id"]).value)
        if not ident:
            continue
        datas, avisos = _ler_datas(ws, linha, col, _MARCOS_PRINCIPAL, "principal")
        grupos.append(GrupoLido(ident, _texto(ws.cell(linha, col["sala"]).value),
                                _texto(ws.cell(linha, col["nome"]).value) if "nome" in col else "", datas, avisos))
    return grupos


def ler_planilha_complementar(caminho) -> list[GrupoLido]:
    """Grupos da planilha de controle do início do comissionamento, aba por aba
    (uma por sala). Abas sem o cabeçalho 'Grupo' + 'Transpasse de fase' são
    ignoradas."""
    wb = openpyxl.load_workbook(caminho)
    grupos, achou = [], False
    for ws in wb.worksheets:
        for linha in ws.iter_rows(max_row=_LINHAS_CABECALHO):
            titulos = [_titulo(c.value) for c in linha]
            if "GRUPO" in titulos and any(t.startswith("TRANSPASSE") for t in titulos):
                grupos += _ler_grupos_complementar(ws, linha[0].row)
                achou = True
                break
    if not achou:
        raise ValueError("Não encontrei as colunas 'Grupo' e 'Transpasse de fase' em nenhuma aba. Esta é a "
                         "planilha complementar (controle do início do comissionamento)?")
    return grupos


def _ler_grupos_complementar(ws, linha_cabecalho: int) -> list[GrupoLido]:
    col = _colunas(ws, linha_cabecalho, _COMPLEMENTAR)
    if faltam := [titulo for chave, titulo in _OBRIGATORIAS_COMPLEMENTAR.items() if chave not in col]:
        raise ValueError(f"Faltam colunas na planilha complementar (aba '{ws.title}'): {', '.join(faltam)}")
    grupos = []
    for linha in range(linha_cabecalho + 1, ws.max_row + 1):
        numero = _numero(ws.cell(linha, col["grupo"]).value)
        if numero is None:
            continue
        realizada = _linha_realizada(ws, linha, col.get("execucao"))
        datas, avisos = _ler_datas(ws, realizada, col, _OBRIGATORIAS_COMPLEMENTAR, "complementar")
        sala = _texto(ws.cell(linha, col["sala"]).value) if "sala" in col else ""
        nome = _texto(ws.cell(linha, col["nome"]).value) if "nome" in col else ""
        grupos.append(GrupoLido(f"{PREFIXO_COMPLEMENTAR}{numero:03d}", sala or ws.title, nome, datas, avisos))
    return grupos


def _numero(valor) -> int | None:
    """Número do grupo (a célula mesclada só tem valor na 1ª linha do par)."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor)
    return None


def _linha_realizada(ws, linha: int, col_execucao: int | None) -> int:
    """A linha "Realizada" do par que começa em `linha`. Sem o rótulo (há par
    com as duas linhas escritas "Prevista"), é a segunda do par."""
    if col_execucao is None:
        return linha
    for candidata in (linha, linha + 1):
        if _titulo(ws.cell(candidata, col_execucao).value) == "REALIZADA":
            return candidata
    return linha + 1
