"""Hierarquia posicional, planilhas VIP e resumo de quantidades (KB §11, §10).

Porta de `MappingView.iniciar_atualizacao` (legado L694-803). A hierarquia é
POSICIONAL: PREDECESSOR/PLANO DE EXECUÇÃO derivam da ordem física das linhas
(§11.1/§21.6). Estas funções são puras: recebem a lista de linhas na ordem da
planilha e devolvem dicionários por número de linha.

Regra estrita VIP (§10) é condicionada ao toggle: `estrito=False` (padrão) não
rebaixa nada e o resumo do nível 3 sai SEM a linha 'Aprovação Intermediária'.
"""
from __future__ import annotations

from dataclasses import dataclass

from .consolidation import calcula_status_consolidado_estrito
from .constants import (
    CONS_APROVACAO_INTERMEDIARIA,
    CONS_APROVADO,
    CONS_EM_PROCESSO,
    CONS_NAO_APROVADO,
    CONS_NAO_EMITIDO,
)


@dataclass
class LinhaPlano:
    """Uma linha da planilha de mapeamento, na ordem física (row = nº da linha)."""
    row: int
    cod_itaipu: str = ""
    cod_cmi: str = ""
    nivel: str = ""
    descricao: str = ""
    status_real: str = ""
    status_consolidado: str = ""


def calcular_hierarquia(linhas: list[LinhaPlano]) -> dict[int, tuple[str, str]]:
    """row → (predecessor, plano_execução). Réplica de L694-724.

    Nível 1 → predecessor = plano = próprio código. Demais → varre as linhas
    ACIMA (ordem física): primeiro código de nível menor vira predecessor;
    primeiro código de nível 1 vira plano de execução. Linhas com nível não
    numérico são puladas.
    """
    resultado: dict[int, tuple[str, str]] = {}
    for i, ln in enumerate(linhas):
        nivel_atual = ln.nivel
        plano_exec, predecessor = "", ""
        if nivel_atual == "1":
            plano_exec = predecessor = ln.cod_itaipu
        else:
            for j in range(i - 1, -1, -1):
                aux = linhas[j]
                if not aux.nivel.isdigit() or not nivel_atual.isdigit():
                    continue
                if predecessor == "" and int(aux.nivel) < int(nivel_atual):
                    predecessor = aux.cod_itaipu
                if plano_exec == "" and aux.nivel == "1":
                    plano_exec = aux.cod_itaipu
                if plano_exec and predecessor:
                    break
        resultado[ln.row] = (predecessor, plano_exec)
    return resultado


def identificar_planilhas_vip(linhas: list[LinhaPlano]) -> set[str]:
    """Códigos Itaipu das planilhas VIP: nível 3 com 'PLANILHA' na descrição (L731-741)."""
    vips: set[str] = set()
    for ln in linhas:
        if ln.nivel == "3" and "PLANILHA" in str(ln.descricao).upper() and ln.cod_itaipu:
            vips.add(ln.cod_itaipu)
    return vips


# Descrições dos PLANOS de (des)comissionamento (nível 2) — pai das planilhas VIP.
_DESC_PLANO_COMISS = ("PLANO DE COMISSIONAMENTO", "PLANO DE DESCOMISSIONAMENTO")


def identificar_planos_comissionamento(linhas: list[LinhaPlano]) -> set[str]:
    """Códigos Itaipu dos PLANOS de (des)comissionamento: nível 2 cuja DESCRIÇÃO
    contém 'PLANO DE COMISSIONAMENTO'/'PLANO DE DESCOMISSIONAMENTO' (pedido do
    usuário). As planilhas de nível 3 SOB eles recebem a regra estrita — mesma
    ideia dos documentos de nível 4 sob planilhas VIP (nível 3), um nível acima."""
    planos: set[str] = set()
    for ln in linhas:
        desc = str(ln.descricao).upper()
        if ln.nivel == "2" and ln.cod_itaipu and any(t in desc for t in _DESC_PLANO_COMISS):
            planos.add(ln.cod_itaipu)
    return planos


def aplicar_regra_estrita(linhas: list[LinhaPlano], predecessores: dict[int, tuple[str, str]],
                          vips: set[str], planos_comiss: set[str] | None = None) -> dict[int, str]:
    """row → novo status consolidado. Só faz sentido com o toggle LIGADO. Rebaixa
    por `calcula_status_consolidado_estrito`:
      - documentos de **nível 4** cujo PREDECESSOR é uma planilha VIP (nível 3);
      - planilhas de **nível 3** cujo PREDECESSOR é um PLANO de (des)comissionamento
        de nível 2 — mesma regra, um nível acima (pedido do usuário)."""
    planos_comiss = planos_comiss or set()
    novos: dict[int, str] = {}
    if not vips and not planos_comiss:
        return novos
    for ln in linhas:
        pred = predecessores.get(ln.row, ("", ""))[0]
        if ln.nivel == "4" and pred in vips:
            novos[ln.row] = calcula_status_consolidado_estrito(ln.status_real, ln.status_consolidado)
        elif ln.nivel == "3" and pred in planos_comiss:
            novos[ln.row] = calcula_status_consolidado_estrito(ln.status_real, ln.status_consolidado)
    return novos


def calcular_resumo_quantidades(linhas: list[LinhaPlano], predecessores: dict[int, tuple[str, str]],
                                *, estrito: bool = False,
                                planos_comiss: set[str] | None = None) -> dict[int, str]:
    """row → texto do RESUMO QUANTIDADES para níveis 1/2/3 (L757-803).

    Conta apenas filhos DIRETOS (predecessor == código do pai). Nível 1/2 já
    APROVADO → 'Plano Aprovado'. A quebra de Aprovação Intermediária aparece,
    quando `estrito=True`, no nível 3 (suas planilhas) e nos PLANOS de
    (des)comissionamento de nível 2 (contando as planilhas de nível 3 sob eles —
    pedido do usuário); esses planos NÃO caem no atalho 'Plano Aprovado'.
    """
    planos_comiss = planos_comiss or set()
    pred_por_row = {ln.row: predecessores.get(ln.row, ("", ""))[0] for ln in linhas}
    resumo: dict[int, str] = {}
    for pai in linhas:
        if pai.nivel not in ("1", "2", "3"):
            continue
        # Plano de (des)comissionamento (nível 2) com o toggle ligado: mostra a
        # quebra da Aprovação Intermediária das planilhas de nível 3 sob ele.
        comiss_estrito = estrito and pai.nivel == "2" and pai.cod_itaipu in planos_comiss
        cons_pai = str(pai.status_consolidado).strip().upper()
        if pai.nivel in ("1", "2") and cons_pai == CONS_APROVADO and not comiss_estrito:
            resumo[pai.row] = "Plano Aprovado"
            continue
        cod_pai = pai.cod_itaipu
        if not cod_pai:
            continue
        qtd = aprov = aprov_int = proc = nao_aprov = nao_emit = 0
        for filho in linhas:
            if filho.row == pai.row or pred_por_row.get(filho.row) != cod_pai or not filho.cod_itaipu:
                continue
            qtd += 1
            s = str(filho.status_consolidado).strip().upper()
            if s == CONS_APROVADO:
                aprov += 1
            elif s == CONS_APROVACAO_INTERMEDIARIA:
                aprov_int += 1
            elif s == CONS_NAO_APROVADO:
                nao_aprov += 1
            elif s == CONS_NAO_EMITIDO:
                nao_emit += 1
            elif s == CONS_EM_PROCESSO:
                proc += 1
        if qtd == 0:
            continue
        if (pai.nivel == "3" and estrito) or comiss_estrito:
            resumo[pai.row] = (f"Total: {qtd}\nAprovados: {aprov}\nAprovação Intermediária: {aprov_int}"
                               f"\nEm Processo: {proc}\nNão Aprovados: {nao_aprov}\nNão Emitidos: {nao_emit}")
        else:
            resumo[pai.row] = (f"Total: {qtd}\nAprovados: {aprov}\nEm Processo: {proc}"
                               f"\nNão Aprovados: {nao_aprov}\nNão Emitidos: {nao_emit}")
    return resumo
