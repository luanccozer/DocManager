"""Status Consolidado, regra estrita, emitido/não-emitido e "com quem está a bola".

Porta de `DataManager.calcula_status_consolidado` (L298), `..._estrito` (L325),
`calcular_emitido_nao_emitido` (L116) e `calcula_parado_com` (L340).

Mudança sancionada (§21.5): a regra morta `se == 'Em Processo' and
sr == 'Análise 1ª Emissão'` foi REMOVIDA - nenhum motor produz "Análise 1ª
Emissão" (provado pelo diferencial cartesiano). O bucket ERRO permanece como
sentinela de combinação não prevista (§21.4).

A regra estrita recebe `estrito`/é chamada explicitamente - o backend não lê
config; quem decide ligar o pente-fino é o orquestrador (toggle VIP).
"""
from __future__ import annotations

from .comissionamento import equivalente
from .constants import (
    CONS_APROVACAO_INTERMEDIARIA,
    CONS_APROVADO,
    CONS_CANCELADO,
    CONS_EM_PROCESSO,
    CONS_ERRO,
    CONS_NAO_APROVADO,
    CONS_NAO_EMITIDO,
    NAO_EMITIDO,
    STATUS_EM_INTEGRACAO,
)

_APROVADOS_CONS = ("Aprovado com Comentários", "Aprovado", "Para Assinatura", "Informativo", "Para Aprovação")
# O motor já entrega 'Cancelado' para toda anulação; os sinônimos ficam por
# segurança, para o consolidado calculado a partir de um status lido de planilha.
_CANCELAMENTO_UPPER = ("ANULADO", "CANCELADO", "ISSUED FOR ANNULMENT", "VOID")
_PARA_ANALISE_UPPER = ("PARA ANÁLISE", "PARA ANALISE")


def calcular_emitido_nao_emitido(status_consolidado) -> str:
    """Derivação trivial: vazio ou 'NÃO EMITIDO' → NÃO EMITIDO; senão EMITIDO."""
    st = str(status_consolidado).strip().upper()
    if not st or st == "NÃO EMITIDO":
        return NAO_EMITIDO
    return "EMITIDO"


def calcula_status_consolidado(status_real, status_emissao, emitido_nao_emitido) -> str:
    sr = status_real if status_real else ""
    # O bruto chega com o rótulo cru do Aconex. Numa planilha de comissionamento
    # o motor já traduziu 'Reviewed with No Comments' para 'Não Aprovado' no
    # status real; aqui o bruto recebe a mesma tradução, senão o par (Não
    # Aprovado, Reviewed with No Comments) cairia em ERRO. Dispensa o título:
    # o par só se forma quando o motor tratou o rótulo como reprovação, e aí
    # NÃO APROVADO é a leitura certa (core/comissionamento.py).
    se = equivalente(status_emissao) if status_emissao else ""
    ene = emitido_nao_emitido if emitido_nao_emitido else ""

    if sr in _APROVADOS_CONS:
        return CONS_APROVADO
    elif sr == "Não Aprovado" and se == "Não Aprovado":
        return CONS_NAO_APROVADO
    elif sr == "Não Aprovado" and (se in STATUS_EM_INTEGRACAO or str(se).strip().upper() in _PARA_ANALISE_UPPER):
        return CONS_NAO_APROVADO
    elif sr == "Não Aprovado" and se == "Em Processo":
        return CONS_EM_PROCESSO
    elif str(sr).strip().upper() in _CANCELAMENTO_UPPER:
        return CONS_CANCELADO
    elif sr == "NÃO EMITIDO":
        return CONS_NAO_EMITIDO
    elif (not sr) and (ene == "SATedms"):
        return "SATedms"
    elif sr == "Em Processo" and se == "Em Processo":
        return CONS_EM_PROCESSO
    else:
        return CONS_ERRO


def calcula_status_consolidado_estrito(status_real, status_consolidado_atual) -> str:
    """Regra estrita das planilhas VIP (KB §10). Só 'Aprovado' seco vira APROVADO;
    aprovações parciais viram APROVAÇÃO INTERMEDIÁRIA; o resto mantém o
    consolidado já calculado."""
    sr = status_real if status_real else ""
    if sr == "Aprovado":
        return CONS_APROVADO
    elif sr in ("Aprovado com Comentários", "Para Assinatura", "Informativo", "Para Aprovação"):
        return CONS_APROVACAO_INTERMEDIARIA
    return status_consolidado_atual


def calcula_parado_com(status_bruto) -> str:
    """COM ITAIPU: Em Processo → ITAIPU; qualquer outro → CMI (KB §9)."""
    if status_bruto == "Em Processo":
        return "ITAIPU"
    return "CMI"
