"""A tabela de envio do Upload → aprovação, COLADA na tela (pedido de 2026-11-04).

Não há arquivo: a lista chega por e-mail e a pessoa copia e cola a tabela inteira (do
Outlook, do Word ou do Excel - os três colam como texto separado por TAB). Cada linha é
um documento, e o robô faz um de cada vez, na ordem da tabela.

Colunas (as da lista real): IDENTIFICAÇÃO DOCUMENTO CMI, IDENTIFICAÇÃO DOCUMENTO ITAIPU,
ESPECIFICAÇÃO TÉCNICA, CAPÍTULO ESPECIFICAÇÃO TÉCNICA, DESCRIÇÃO, TIPO DE DOCUMENTO,
SUBTIPO DE DOCUMENTO, REVISÃO, LINK GE BOX. Com o cabeçalho colado, as colunas são achadas
pelo nome; sem ele, vale esta ordem. O link do Box é o endereço escrito na célula.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from ..core.normalize import normalizar_cabecalho
from .controle_docs import chave_codigo

COL_CMI = "IDENTIFICAÇÃO DOCUMENTO CMI"
COL_ITAIPU = "IDENTIFICAÇÃO DOCUMENTO ITAIPU"
COL_DESCRICAO = "DESCRIÇÃO"
COL_REVISAO = "REVISÃO"
COL_LINK = "LINK GE BOX"
# A ordem das colunas na lista, para quando o cabeçalho não vem junto.
ORDEM = (COL_CMI, COL_ITAIPU, "ESPECIFICAÇÃO TÉCNICA (EQUIPAMENTO/SISTEMA)",
         "CAPÍTULO ESPECIFICAÇÃO TÉCNICA (EQUIPAMENTO/SISTEMA)", COL_DESCRICAO,
         "TIPO DE DOCUMENTO", "SUBTIPO DE DOCUMENTO", COL_REVISAO, COL_LINK)


class ErroEnvio(ValueError):
    """A tabela colada não pôde ser lida; a mensagem é para a tela."""


@dataclass(frozen=True)
class LinhaEnvio:
    cod_cmi: str
    cod_itaipu: str = ""
    descricao: str = ""
    revisao: str = ""
    link: str = ""


def _linhas_do_texto(texto: str) -> list[list[str]]:
    # O Excel põe entre aspas a célula com quebra de linha; o csv desfaz isso.
    leitor = csv.reader(io.StringIO(texto.replace("\r\n", "\n")), delimiter="\t", quotechar='"')
    return [[c.strip() for c in linha] for linha in leitor if any(c.strip() for c in linha)]


def ler_tabela(texto: str) -> list[LinhaEnvio]:
    """Os documentos da tabela colada, na ordem dela. Linhas sem código CMI ficam de fora."""
    linhas = _linhas_do_texto(texto or "")
    if not linhas:
        return []
    alvo = normalizar_cabecalho(COL_CMI)
    i_cab = next((i for i, lin in enumerate(linhas)
                  if alvo in [normalizar_cabecalho(c) for c in lin]), None)
    if i_cab is None:
        nomes, corpo = [normalizar_cabecalho(c) for c in ORDEM], linhas
    else:
        nomes, corpo = [normalizar_cabecalho(c) for c in linhas[i_cab]], linhas[i_cab + 1:]

    def col(nome):
        n = normalizar_cabecalho(nome)
        return nomes.index(n) if n in nomes else None

    c_cmi, c_it, c_desc, c_rev = col(COL_CMI), col(COL_ITAIPU), col(COL_DESCRICAO), col(COL_REVISAO)
    c_link = col(COL_LINK)
    if c_link is None:
        c_link = next((j for j, n in enumerate(nomes) if n.startswith("LINK")), None)

    saida = []
    for lin in corpo:
        def cel(j):
            return lin[j] if j is not None and j < len(lin) else ""
        cmi = cel(c_cmi)
        # Uma linha de tabela tem colunas: a frase "Seguem documentos..." colada junto não conta.
        if len(lin) < 2 or not cmi or normalizar_cabecalho(cmi) == alvo:
            continue
        link = cel(c_link)
        if not link.lower().startswith("http"):   # coluna fora do lugar: o endereço onde estiver
            link = next((c for c in lin if c.lower().startswith("http")), "")
        saida.append(LinhaEnvio(cmi, cel(c_it), cel(c_desc), cel(c_rev), link))
    return saida


def buscar(linhas: list[LinhaEnvio], codigo: str) -> LinhaEnvio | None:
    alvo = chave_codigo(codigo)
    return next((x for x in linhas if chave_codigo(x.cod_cmi) == alvo), None)
