"""Análise por período do Doc List Mapping (KB §27.2) - funções puras.

Responde à pergunta de planejamento do usuário: *quais documentos estão
previstos para emitir nos próximos tempos?*

A data que vale é a **DATA-ALVO EMISSÃO** (`REPROGRAMADA` quando existe, senão
`DATA PREVISTA EMISSÃO`) - a mesma que o módulo grava na planilha para o
dashboard ler. Cada item carrega a `origem` dessa data, para o leitor saber se
o prazo já foi reprogramado.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .doclist import LinhaDocList

ORIGEM_REPROGRAMADA = "Reprogramada"
ORIGEM_PREVISTA = "Prevista"


@dataclass(frozen=True)
class Janela:
    """Intervalo fechado [inicio, fim]. `None` em qualquer ponta = sem limite."""
    rotulo: str
    inicio: date | None
    fim: date | None

    def contem(self, d: date) -> bool:
        if self.inicio is not None and d < self.inicio:
            return False
        if self.fim is not None and d > self.fim:
            return False
        return True


def _fim_do_mes(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def janelas_padrao(hoje: date) -> list[Janela]:
    """Atalhos de período oferecidos na interface."""
    inicio_mes_que_vem = _fim_do_mes(hoje) + timedelta(days=1)
    return [
        Janela("Vencidos (não emitidos)", None, hoje - timedelta(days=1)),
        Janela("Próximos 7 dias", hoje, hoje + timedelta(days=7)),
        Janela("Próximos 30 dias", hoje, hoje + timedelta(days=30)),
        Janela("Próximos 90 dias", hoje, hoje + timedelta(days=90)),
        Janela("Restante deste mês", hoje, _fim_do_mes(hoje)),
        Janela("Mês que vem", inicio_mes_que_vem, _fim_do_mes(inicio_mes_que_vem)),
        Janela("Este ano", date(hoje.year, 1, 1), date(hoje.year, 12, 31)),
    ]


@dataclass(frozen=True)
class ItemPeriodo:
    """Um documento previsto para emissão dentro da janela analisada."""
    grupo: str
    sistema: str
    fase_projeto: str
    cod_itaipu: str
    cod_cmi: str
    descricao: str
    responsavel: str
    predecessor: str
    data_alvo: date
    origem: str                  # 'Prevista' ou 'Reprogramada'
    dias: int                    # data_alvo − hoje (negativo = vencido)
    status_consolidado: str
    emitido: bool

    @property
    def situacao(self) -> str:
        if self.emitido:
            return "Emitido"
        return "Vencido" if self.dias < 0 else "A emitir"

    @property
    def mes(self) -> str:
        return f"{self.data_alvo.year:04d}-{self.data_alvo.month:02d}"


def _item(ln: LinhaDocList, hoje: date) -> ItemPeriodo | None:
    alvo = ln.data_alvo
    if alvo is None:
        return None
    origem = ORIGEM_REPROGRAMADA if ln.data_reprogramada is not None else ORIGEM_PREVISTA
    return ItemPeriodo(
        grupo=ln.grupo, sistema=ln.sistema, fase_projeto=ln.fase_projeto,
        cod_itaipu=ln.cod_itaipu, cod_cmi=ln.cod_cmi, descricao=ln.descricao,
        responsavel=ln.responsavel, predecessor=ln.predecessor,
        data_alvo=alvo, origem=origem, dias=(alvo - hoje).days,
        status_consolidado=ln.status_consolidado, emitido=ln.esta_emitido,
    )


def analisar_periodo(linhas: list[LinhaDocList], *, inicio: date | None, fim: date | None,
                     hoje: date, incluir_emitidos: bool = False) -> list[ItemPeriodo]:
    """Documentos cuja DATA-ALVO cai na janela, ordenados por data.

    As linhas de NÍVEL 1 são agrupamentos, não documentos - ficam de fora.
    Por padrão os já emitidos também saem: a pergunta é "o que falta emitir".
    """
    janela = Janela("", inicio, fim)
    itens: list[ItemPeriodo] = []
    for ln in linhas:
        if ln.e_grupo or not (ln.cod_itaipu or ln.cod_cmi):
            continue
        it = _item(ln, hoje)
        if it is None or not janela.contem(it.data_alvo):
            continue
        if it.emitido and not incluir_emitidos:
            continue
        itens.append(it)
    itens.sort(key=lambda x: (x.data_alvo, x.grupo, x.cod_itaipu))
    return itens


def listar_sem_data(linhas: list[LinhaDocList], *, incluir_emitidos: bool = False) -> list[LinhaDocList]:
    """Documentos sem NENHUMA data de planejamento - o furo que a análise por
    período não enxerga e que o usuário precisa fechar no Controle."""
    saida = []
    for ln in linhas:
        if ln.e_grupo or not (ln.cod_itaipu or ln.cod_cmi):
            continue
        if ln.data_alvo is not None:
            continue
        if ln.esta_emitido and not incluir_emitidos:
            continue
        saida.append(ln)
    return saida


def agrupar_por_mes(itens: list[ItemPeriodo]) -> dict[str, list[ItemPeriodo]]:
    """{'AAAA-MM': [itens]} em ordem cronológica."""
    saida: dict[str, list[ItemPeriodo]] = {}
    for it in sorted(itens, key=lambda x: x.data_alvo):
        saida.setdefault(it.mes, []).append(it)
    return saida


def agrupar_por(itens: list[ItemPeriodo], chave: str) -> dict[str, list[ItemPeriodo]]:
    """Agrupa por um atributo do item ('grupo', 'sistema', 'fase_projeto', ...)."""
    saida: dict[str, list[ItemPeriodo]] = {}
    for it in itens:
        saida.setdefault(str(getattr(it, chave, "") or "(sem valor)"), []).append(it)
    return dict(sorted(saida.items()))


def resumo(itens: list[ItemPeriodo]) -> dict:
    """Números de cabeçalho do relatório."""
    vencidos = sum(1 for i in itens if not i.emitido and i.dias < 0)
    reprogramados = sum(1 for i in itens if i.origem == ORIGEM_REPROGRAMADA)
    datas = [i.data_alvo for i in itens]
    return {
        "total": len(itens),
        "vencidos": vencidos,
        "a_emitir": len(itens) - vencidos,
        "reprogramados": reprogramados,
        "primeira_data": min(datas) if datas else None,
        "ultima_data": max(datas) if datas else None,
        "por_mes": {m: len(v) for m, v in agrupar_por_mes(itens).items()},
    }
