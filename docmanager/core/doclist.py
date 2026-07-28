"""Núcleo puro do módulo **Doc List Mapping** (KB §27).

O Doc List Mapping nasceu do Mapa dos Planos: a equipe gostou do follow-up
semanal de uma documentação já definida e passou a usar a planilha de
mapeamento para acompanhar OUTRO tipo de documentação, forçando regras que não
se aplicavam. Este módulo formaliza aquela adaptação — mesma espinha dorsal
(status real → consolidado → hierarquia → resumo), com três diferenças:

1. **Dois níveis apenas.** Nível 1 deixou de ser documento: é um AGRUPAMENTO,
   um por escopo das Unidades Geradoras. Nível 2 são os documentos.
2. **Uma coluna de hierarquia.** `PLANO DE EXECUÇÃO` e `PREDECESSOR` viravam
   sempre o mesmo valor com só dois níveis — restou `PREDECESSOR`.
3. **Planejamento dirigido pelo Controle de Documentos**: `DATA PREVISTA EMISSÃO`
   e `DATA REPROGRAMADA` vêm de lá, e a coluna `DATA-ALVO EMISSÃO` (ex-`TROCAR`)
   consolida a data que vale para o dashboard — REPROGRAMADA quando houver,
   senão PREVISTA. `FASE DE PROJETO` é **input manual** (§27.3).

O **STATUS CONSOLIDADO é o mesmo do Mapa** (`calcula_status_consolidado`): os
três status de aprovação caem todos em `APROVADO`. Chegou a separá-los (§27),
mas o usuário reverteu em 2026-07-28 — discretizar aqui só replicaria a coluna
STATUS REAL, e quem quiser o detalhe no dashboard troca de coluna.

Tudo aqui é função pura; o I/O da planilha vive em `services/doclist_io.py` e a
orquestração em `services/doclist_update.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .constants import (
    CONS_APROVADO,
    CONS_CANCELADO,
    CONS_EM_PROCESSO,
    CONS_NAO_APROVADO,
    CONS_NAO_EMITIDO,
)
from .planejamento import reconciliar_datas

# ---------------------------------------------------------------------------
# Colunas (chave lógica → texto do cabeçalho), NA ORDEM do layout acordado.
# A âncora de localização do cabeçalho é 'N° ITAIPU' — atenção ao codepoint:
# 'N° ITAIPU' usa U+00B0 (GRAU) e 'Nº CMI' usa U+00BA (ORDINAL), igual ao Mapa.
# ---------------------------------------------------------------------------
COLUNAS_DOCLIST: dict[str, str] = {
    "grupo": "GRUPO",
    "sistema": "SISTEMA",
    "fase_projeto": "FASE DE PROJETO",
    "codigo_cmi": "Nº CMI",
    "codigo_itaipu": "N° ITAIPU",
    "descricao": "DESCRIÇÃO DO DOCUMENTO",
    "data_prevista": "DATA PREVISTA EMISSÃO",
    "data_reprogramada": "DATA REPROGRAMADA",
    "data_alvo": "DATA-ALVO EMISSÃO",
    "emitido_nao_emitido": "EMITIDO / NÃO EMITIDO",
    "data_ultimo_status": "DATA ÚLTIMA EMISSÃO",
    "revisao": "ÚLTIMA REV. EMITIDA",
    "status_real": "STATUS REAL",
    "status_emissao": "STATUS",
    "responsavel": "RESPONSIBLE (COE/VENDOR)",
    "nivel": "NÍVEL",
    "status_consolidado": "STATUS CONSOLIDADO",
    "com_itaipu": "COM ITAIPU",
    "predecessor": "PREDECESSOR",
    "observacao": "OBSERVAÇÕES",
    "resumo_quantidades": "RESUMO QUANTIDADES",
}

# A coluna DATA-ALVO EMISSÃO ocupa o lugar da antiga 'TROCAR'. Cabeçalhos
# antigos são reconhecidos e renomeados na abertura da planilha.
CABECALHOS_LEGADOS: dict[str, tuple[str, ...]] = {
    "data_alvo": ("TROCAR",),
    "data_prevista": ("DATA PREVISTA EMISSÃO ETAPA 1", "DATA PREVISTA DE EMISSÃO"),
    "responsavel": ("RESPONSÁVEL",),
    "observacao": ("OBSERVAÇÃO",),
}

ANCORA_DOCLIST = COLUNAS_DOCLIST["codigo_itaipu"]

NIVEL_GRUPO = "1"
NIVEL_DOCUMENTO = "2"

# Colunas que o app calcula e sobrescreve a cada atualização (as demais são
# input manual e nunca são tocadas).
COLUNAS_CALCULADAS = (
    "data_alvo", "emitido_nao_emitido", "data_ultimo_status", "revisao",
    "status_real", "status_emissao", "status_consolidado", "com_itaipu",
    "predecessor", "resumo_quantidades",
)


# ---------------------------------------------------------------------------
# Linha da planilha
# ---------------------------------------------------------------------------
@dataclass
class LinhaDocList:
    """Uma linha do Doc List Mapping, na ordem física (row = nº da linha)."""
    row: int
    cod_itaipu: str = ""
    cod_cmi: str = ""
    nivel: str = ""
    grupo: str = ""
    sistema: str = ""
    fase_projeto: str = ""
    descricao: str = ""
    responsavel: str = ""
    status_real: str = ""
    status_consolidado: str = ""
    emitido_nao_emitido: str = ""
    data_prevista: date | None = None
    data_reprogramada: date | None = None
    predecessor: str = ""

    @property
    def e_grupo(self) -> bool:
        """Nível 1 = agrupamento por escopo, não é documento."""
        return str(self.nivel).strip() == NIVEL_GRUPO

    @property
    def data_alvo(self) -> date | None:
        """Data que vale para o planejamento: REPROGRAMADA > PREVISTA."""
        return self.data_reprogramada if self.data_reprogramada is not None else self.data_prevista

    @property
    def esta_emitido(self) -> bool:
        return str(self.emitido_nao_emitido).strip().upper() not in ("", CONS_NAO_EMITIDO)


# ---------------------------------------------------------------------------
# Hierarquia — só dois níveis, uma coluna
# ---------------------------------------------------------------------------
def calcular_predecessores(linhas: list[LinhaDocList]) -> dict[int, str]:
    """row → PREDECESSOR.

    Nível 1 (grupo) → o próprio código (decisão do usuário: mantém a regra do
    Mapa, onde o pai aponta para si mesmo e os filhos apontam para ele, que é o
    que faz o RESUMO QUANTIDADES fechar).
    Demais níveis → código do grupo (nível 1) imediatamente ACIMA na ordem
    física. Um nível fora de {1, 2} continua sendo tratado como filho, para que
    uma linha esquecida não fique órfã do seu grupo.
    """
    resultado: dict[int, str] = {}
    grupo_atual = ""
    for ln in linhas:
        if ln.e_grupo:
            grupo_atual = ln.cod_itaipu
            resultado[ln.row] = ln.cod_itaipu
        else:
            resultado[ln.row] = grupo_atual
    return resultado


def niveis_fora_do_padrao(linhas: list[LinhaDocList]) -> list[int]:
    """Linhas cujo NÍVEL não é 1 nem 2 (só para avisar no log)."""
    return [ln.row for ln in linhas
            if str(ln.nivel).strip() not in (NIVEL_GRUPO, NIVEL_DOCUMENTO)]


# ---------------------------------------------------------------------------
# Resumo de quantidades
# ---------------------------------------------------------------------------
# Rótulo exibido → status consolidado correspondente. A ordem é a do texto.
_BUCKETS_RESUMO: tuple[tuple[str, str], ...] = (
    ("Aprovados", CONS_APROVADO),
    ("Em Processo", CONS_EM_PROCESSO),
    ("Não Aprovados", CONS_NAO_APROVADO),
    ("Não Emitidos", CONS_NAO_EMITIDO),
)
# Baldes raros: só entram no texto quando existem, para não poluir a célula.
_BUCKETS_OPCIONAIS: tuple[tuple[str, str], ...] = (("Cancelados", CONS_CANCELADO),)


def calcular_resumo_quantidades(linhas: list[LinhaDocList],
                                predecessores: dict[int, str]) -> dict[int, str]:
    """row (nível 1) → texto do RESUMO QUANTIDADES.

    Conta os filhos diretos do grupo (predecessor == código do grupo). O total
    SEMPRE fecha com a soma dos baldes: um consolidado inesperado cai numa linha
    'Outros', em vez de sumir silenciosamente.
    """
    resumo: dict[int, str] = {}
    for pai in linhas:
        if not pai.e_grupo or not pai.cod_itaipu:
            continue
        contagem: dict[str, int] = {}
        qtd = 0
        for filho in linhas:
            if filho.row == pai.row or not filho.cod_itaipu:
                continue
            if predecessores.get(filho.row) != pai.cod_itaipu:
                continue
            qtd += 1
            s = str(filho.status_consolidado).strip().upper()
            contagem[s] = contagem.get(s, 0) + 1
        if qtd == 0:
            continue
        partes = [f"Total: {qtd}"]
        contados = 0
        for rotulo, chave in _BUCKETS_RESUMO:
            n = contagem.get(chave, 0)
            contados += n
            partes.append(f"{rotulo}: {n}")
        for rotulo, chave in _BUCKETS_OPCIONAIS:
            n = contagem.get(chave, 0)
            if n:
                contados += n
                partes.append(f"{rotulo}: {n}")
        if qtd - contados > 0:
            partes.append(f"Outros: {qtd - contados}")
        resumo[pai.row] = "\n".join(partes)
    return resumo


# ---------------------------------------------------------------------------
# Datas de planejamento (vindas do Controle de Documentos)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DatasDocList:
    """O que gravar nas colunas de planejamento de uma linha.

    `None` em `prevista`/`reprogramada` significa "não mexer na célula".
    `data_alvo` é sempre recalculada a partir do que ficará nas células.
    """
    prevista: date | None = None
    reprogramada: date | None = None
    data_alvo: date | None = None
    via: str = ""            # como o doc foi achado no Controle (diagnóstico)
    prevista_atualizada: bool = False   # o Controle trouxe data MAIS RECENTE
    titulo_controle: str = ""           # DESCRIÇÃO do Controle (fallback do Aconex)


def resolver_datas_doclist(*, prevista_atual: date | None, reprogramada_atual: date | None,
                           codigos, cod_itaipu_atual: str, cod_cmi_atual: str,
                           controle) -> DatasDocList:
    """Aplica as regras de planejamento do Doc List (§27).

    - **DATA PREVISTA EMISSÃO** — vem do Controle; havendo divergência com a
      planilha, vence a data MAIS RECENTE.
    - **DATA REPROGRAMADA** — vem do Controle, mas NUNCA sobrescreve: a coluna
      também aceita input manual, que tem a palavra final.
    - **DATA-ALVO EMISSÃO** — sempre recalculada: reprogramada > prevista.

    A regra é a mesma do Mapa dos Planos (`core/planejamento.py`, §24.13).
    **FASE DE PROJETO não entra aqui**: é input manual (§27.3).
    """
    linha = None
    via = ""
    if controle is not None:
        m = controle.resolver(codigos, cod_itaipu_atual, cod_cmi_atual)
        linha, via = m.linha, m.via

    d = reconciliar_datas(
        prevista_planilha=prevista_atual, reprogramada_planilha=reprogramada_atual,
        prevista_controle=linha.data_prevista if linha else None,
        reprogramada_controle=linha.data_reprogramada if linha else None)
    return DatasDocList(prevista=d.prevista, reprogramada=d.reprogramada,
                        data_alvo=d.data_ref, via=via,
                        prevista_atualizada=d.prevista_atualizada,
                        titulo_controle=str(linha.titulo).strip() if linha else "")
