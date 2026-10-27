"""Transpasse de Fase: o quadro de cores por dia da Planilha1, desenhado a
partir das datas das planilhas de acompanhamento.

A equipe pintava à mão, numa grade de dias, a passagem de cada grupo de
equipamentos pelos marcos convocação IB → inspeção IB → emissão do CCMLC →
transpasse de fase (CCMLC emitido via Unifier) → início do comissionamento. As
regras da pintura saíram dessa planilha e valem aqui igual:

- vermelho, laranja e azul vão da data do seu marco até a véspera do próximo
  marco que tiver data, sem pintar sábado e domingo (o dia do próprio marco é
  pintado mesmo se cair no fim de semana). Sem próximo marco, a etapa ainda
  está em andamento e vai até hoje - na Planilha1 ela aparecia só no dia da
  convocação, e o tempo parado não se via;
- verde (transpasse) e preto (início do comissionamento) ocupam um dia só;
- marcos no mesmo dia: vale a cor do marco mais adiantado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median_low

from .normalize import remover_acentos

UM_DIA = timedelta(days=1)
# Data mais de um ano antes das demais é ano digitado errado (ex.: 2020 num
# quadro de 2026). Sem esse corte, uma convocação assim esticaria o quadro por anos.
MARGEM_IMPROVAVEL = timedelta(days=365)

MARCOS = ("conv", "insp", "ccmlc", "transp", "inicio")
NOME = {"conv": "Convocação", "insp": "Inspeção IB", "ccmlc": "Emissão CCMLC",
        "transp": "Transpasse de fase", "inicio": "Início do comissionamento"}
# Marco → letra da cor na legenda da Planilha1.
COR = {"conv": "R", "insp": "O", "ccmlc": "B", "transp": "G", "inicio": "K"}
_CORRIDAS = ("conv", "insp", "ccmlc")   # as cores que se estendem até o próximo marco


@dataclass
class GrupoLido:
    """Um grupo de equipamentos como veio de UMA das planilhas."""
    id: str
    sala: str
    nome: str = ""
    datas: dict = field(default_factory=dict)        # marco → date
    avisos: list = field(default_factory=list)       # o que a leitura achou estranho (vai para o card)


@dataclass
class GrupoPainel:
    """Um grupo pronto para o quadro: só as datas que entram nele, as células
    pintadas e o que o card mostra ao passar o mouse."""
    id: str
    sala: str
    nome: str
    datas: dict
    celulas: dict
    dias: int | None         # coluna "Dias": convocação → início, contando os dois dias
    intervalos: dict         # marco → dias desde o marco anterior que tem data
    rodape: str              # a última linha do card
    avisos: list = field(default_factory=list)

    @property
    def pendente(self) -> bool:
        """Ainda sem convocação: o código do grupo fica amarelo, como na Planilha1."""
        return self.datas.get("conv") is None


@dataclass
class Quadro:
    """Os grupos do quadro e o período da grade (do 1º dia do mês da data mais
    antiga ao último dia do mês da mais recente, hoje incluído)."""
    grupos: list
    inicio: date
    fim: date


def montar_quadro(principal: list[GrupoLido], complementar: list[GrupoLido] | None,
                  hoje: date) -> Quadro:
    """Junta as duas planilhas grupo a grupo. A principal manda na lista de
    grupos (código, sala e nome); a complementar completa as datas que faltam
    nela e acrescenta os grupos que a principal não tem, na sala equivalente
    (o '60HZ' dela é a 'SALA SEGURA 60 Hz' da principal)."""
    complementar = complementar or []
    sobras = {g.id: g for g in complementar}
    todas = [d for g in (*principal, *complementar) for d in g.datas.values() if d]
    piso = date.fromordinal(median_low(d.toordinal() for d in todas)) - MARGEM_IMPROVAVEL if todas else None
    salas = {}
    for g in principal:
        salas.setdefault(_chave_sala(g.sala), g.sala)

    blocos: dict[str, list] = {}   # sala → grupos, na ordem em que as salas aparecem
    for g in principal:
        c = sobras.pop(g.id, None)
        fontes = [("principal", g)] + ([("complementar", c)] if c else [])
        divergencia = [aviso] if c and (aviso := _divergencia(g, c)) else []
        blocos.setdefault(g.sala, []).append(_montar(g.id, g.sala, g.nome, fontes, divergencia, hoje, piso))
    for c in sobras.values():
        sala = salas.get(_chave_sala(c.sala), c.sala)
        blocos.setdefault(sala, []).append(_montar(c.id, sala, c.nome, [("complementar", c)], [], hoje, piso))
    # Sala sem nenhuma convocação ainda (ex.: a de testes) entra quando tiver.
    grupos = [g for lista in blocos.values() if any(not g.pendente for g in lista) for g in lista]

    usadas = [d for g in grupos for d in g.datas.values() if d] + [hoje]
    ultima = max(usadas)
    proximo_mes = date(ultima.year + ultima.month // 12, ultima.month % 12 + 1, 1)
    return Quadro(grupos, min(usadas).replace(day=1), proximo_mes - UM_DIA)


def _montar(ident, sala, nome, fontes, avisos, hoje, piso) -> GrupoPainel:
    datas, avisos_datas = _juntar(fontes, hoje, piso)
    dias = (datas["inicio"] - datas["conv"]).days + 1 if datas["inicio"] and datas["conv"] else None
    da_leitura = [aviso for _, g in fontes for aviso in g.avisos]
    return GrupoPainel(ident, sala, nome, datas, pintar(datas, hoje), dias, _intervalos(datas),
                       _rodape(datas, dias, hoje), avisos + da_leitura + avisos_datas)


def _intervalos(datas: dict) -> dict:
    intervalos, anterior = {}, None
    for marco in MARCOS:
        intervalos[marco] = (datas[marco] - anterior).days if datas[marco] and anterior else None
        anterior = datas[marco] or anterior
    return intervalos


# Último marco com data → o que o grupo está esperando.
AGUARDANDO = {"conv": "a inspeção", "insp": "a emissão do CCMLC", "ccmlc": "o transpasse",
              "transp": "o início do comissionamento"}


def _rodape(datas: dict, dias: int | None, hoje: date) -> str:
    if dias is not None:
        return f"Dias (convocação → início): {dias}"
    if not datas["conv"]:
        return "Sem data de convocação" if any(datas.values()) else "Ainda não convocado"
    ultimo = next(m for m in ("transp", "ccmlc", "insp", "conv") if datas[m])
    n = (hoje - datas[ultimo]).days
    return f"Aguardando {AGUARDANDO[ultimo]} há {n} dia{'' if n == 1 else 's'}"


def _juntar(fontes: list[tuple[str, GrupoLido]], hoje: date, piso: date | None) -> tuple[dict, list[str]]:
    """Datas do grupo, marco a marco: a da primeira fonte (a principal); sem
    ela, ou se ela tiver problema, a da seguinte. Toda data que fica de fora
    vai para o card, com o motivo quando há um."""
    datas, avisos = {}, []
    anterior = None   # (marco, data) do último marco que entrou no quadro
    for marco in MARCOS:
        candidatas = [(origem, g.datas[marco]) for origem, g in fontes if g.datas.get(marco)]
        escolhida = None
        for origem, data in candidatas:
            problema = _problema(data, anterior, hoje, piso)
            if escolhida is None and problema is None:
                escolhida = data
            elif data != escolhida:
                avisos.append(f"Na planilha {origem}: {NOME[marco]} = {data:%d/%m/%Y}"
                              + (f" ({problema})" if problema else ""))
        datas[marco] = escolhida
        if escolhida:
            anterior = (marco, escolhida)
    return datas, avisos


def _problema(data: date, anterior: tuple | None, hoje: date, piso: date | None) -> str | None:
    """Por que a data não pode entrar no quadro (None = pode). Todos os marcos
    são de coisas que já aconteceram: data depois de hoje é erro."""
    if data > hoje:
        return "data no futuro"
    if piso and data < piso:
        return "data improvável: mais de um ano antes das demais"
    if anterior and data < anterior[1]:
        return f"fora de ordem: antes de {NOME[anterior[0]]}, {anterior[1]:%d/%m/%Y}"
    return None


def _divergencia(g: GrupoLido, c: GrupoLido) -> str | None:
    """A complementar só tem o NÚMERO do grupo. Se o nome ou a sala dela
    contam outra história, as datas que vieram dela podem ser de outro grupo."""
    partes = []
    nome_g, nome_c = _sem_simbolos(g.nome), _sem_simbolos(c.nome)
    if nome_g and nome_c and nome_g not in nome_c and nome_c not in nome_g:
        partes.append(f"é “{c.nome}”")
    if _chave_sala(g.sala) != _chave_sala(c.sala):
        partes.append(f"está na sala {c.sala}")
    if not partes:
        return None
    aviso = f"Na planilha complementar, este número {' e '.join(partes)}"
    return aviso + " - confira se as datas são deste grupo" if c.datas else aviso


def _sem_simbolos(texto) -> str:
    """Só letras e números, sem acento e em maiúsculas: compara nomes escritos
    com caixa, pontuação ou quebras de linha diferentes."""
    return re.sub(r"[^A-Z0-9]", "", remover_acentos(texto).upper())


def _chave_sala(sala) -> str:
    """'SALA SEGURA 60 Hz' e '60HZ' são a mesma sala: compara pela frequência."""
    texto = remover_acentos(sala).upper()
    achou = re.search(r"(\d+)\s*HZ", texto)
    return achou.group(1) if achou else _sem_simbolos(texto)


def pintar(datas: dict, hoje: date) -> dict[date, str]:
    """Dia → letra da cor, para as datas (já validadas) de um grupo."""
    celulas: dict[date, str] = {}
    for i, marco in enumerate(_CORRIDAS):
        inicio = datas.get(marco)
        if not inicio:
            continue
        proximos = [datas[m] for m in (*_CORRIDAS[i + 1:], "transp") if datas.get(m)]
        fim = proximos[0] if proximos else hoje + UM_DIA
        celulas[inicio] = COR[marco]
        dia = inicio + UM_DIA
        while dia < fim:
            if dia.weekday() < 5:
                celulas[dia] = COR[marco]
            dia += UM_DIA
    for marco in ("transp", "inicio"):
        if datas.get(marco):
            celulas[datas[marco]] = COR[marco]
    return celulas
