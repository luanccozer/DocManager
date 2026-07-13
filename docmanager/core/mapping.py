"""Pipeline de cálculo por documento do Mapa dos Planos (KB §8.9, §11-14).

Funções puras que o serviço de atualização do mapeamento consome. Um documento
passa por: filtro TAG ETAPA (níveis 1/2) → linha da verdade → status real →
consolidação → KPIs → atrasos acumulados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from .constants import COL_STATUS, COL_TITULO, NAO_EMITIDO
from .consolidation import (
    calcula_parado_com,
    calcula_status_consolidado,
    calcular_emitido_nao_emitido,
)
from .identity import obter_codigos_historicos
from .kpis import analisar_kpis_documento, calcular_atrasos_acumulados
from .normalize import remover_acentos
from .status_engine import calcular_status_real
from .truth_line import resolver_linha_da_verdade


@dataclass
class ResultadoDocumento:
    # Colunas visuais (None → limpar a célula: documento não emitido)
    revisao: str | None = None
    data_ultimo_status: str | None = None
    status_emissao: str | None = None          # status bruto da linha dinâmica
    cod_itaipu_atual: str | None = None
    cod_cmi_atual: str | None = None
    descricao_atual: str | None = None
    # Calculadas
    status_real: str = NAO_EMITIDO
    emitido_nao_emitido: str = NAO_EMITIDO
    status_consolidado: str = NAO_EMITIDO
    com_itaipu: str = "CMI"
    kpis: dict = field(default_factory=dict)
    atrasos: dict = field(default_factory=dict)


def filtrar_historico_por_titulo(df_historico: pd.DataFrame, texto_filtro) -> pd.DataFrame:
    """Mantém só as linhas cujo Título contém o filtro (sem acento, upper). §12."""
    if df_historico.empty or not texto_filtro:
        return df_historico
    termo = remover_acentos(texto_filtro).upper().strip()
    mask = df_historico[COL_TITULO].apply(lambda x: termo in remover_acentos(x).upper().strip())
    return df_historico[mask].copy()


def resolver_data_prevista(valor_celula, codigos_historicos, cod_itaipu_atual,
                           cod_cmi_atual, controle) -> date | None:
    """Data a INJETAR na célula DATA PREVISTA EMISSÃO ETAPA 1, ou None (§13).

    Só injeta se a célula está vazia. Desempate de datas conflitantes: código
    Itaipu atual → CMI atual → data mais nova. Candidata = data_ref do Controle
    (REPROGRAMAÇÃO > DATA PREVISTA). Mantida por compatibilidade; o Mapa novo usa
    `resolver_datas_controle`, que separa prevista e reprogramada.
    """
    if controle is None:
        return None
    if valor_celula is not None and str(valor_celula).strip() != "":
        return None  # nunca sobrescreve data existente
    encontradas = {}
    for cod in codigos_historicos:
        linha = controle.linha_por_codigo(cod)
        if linha is not None and linha.data_ref is not None:
            encontradas[cod] = linha.data_ref
    datas = set(encontradas.values())
    if not datas:
        return None
    if len(datas) == 1:
        return next(iter(datas))
    # Conflito: confia no código atual do mapeamento; senão, a mais nova.
    if cod_itaipu_atual in encontradas:
        return encontradas[cod_itaipu_atual]
    if cod_cmi_atual in encontradas:
        return encontradas[cod_cmi_atual]
    return max(datas)


@dataclass(frozen=True)
class DatasControle:
    """Resultado da resolução das datas do Controle para um documento do Mapa.

    - `prevista_para_celula`: DATA PREVISTA a escrever na célula ETAPA 1 — só
      quando a célula está vazia (nunca sobrescreve input existente).
    - `reprogramada`: REPROGRAMAÇÃO a escrever na coluna DATA REPROGRAMADA.
    - `data_ref`: REPROGRAMAÇÃO > PREVISTA — usada para o cálculo de atraso.
    """
    prevista_para_celula: date | None = None
    reprogramada: date | None = None
    data_ref: date | None = None


def resolver_datas_controle(valor_celula_prevista, codigos_historicos, cod_itaipu_atual,
                            cod_cmi_atual, controle) -> DatasControle:
    """Separa PREVISTA (célula, só se vazia) de REPROGRAMAÇÃO (coluna própria) e
    entrega a `data_ref` para o atraso. Regra do usuário (§24)."""
    if controle is None:
        return DatasControle()
    linha = controle.resolver_para_codigos(codigos_historicos, cod_itaipu_atual, cod_cmi_atual)
    if linha is None:
        return DatasControle()
    celula_vazia = not (valor_celula_prevista and str(valor_celula_prevista).strip())
    prevista = linha.data_prevista if (celula_vazia and linha.data_prevista is not None) else None
    return DatasControle(prevista_para_celula=prevista, reprogramada=linha.data_reprogramada,
                         data_ref=linha.data_ref)


def processar_documento(df_tracking: pd.DataFrame, *, nivel: str, tag_etapa: str = "",
                        data_prevista=None, hoje: date | None = None) -> ResultadoDocumento:
    """Calcula tudo de um documento a partir do seu histórico completo."""
    # Filtro TAG ETAPA (níveis 1/2): revisões de etapas anteriores somem.
    if nivel in ("1", "2") and tag_etapa:
        df_tracking = filtrar_historico_por_titulo(df_tracking, tag_etapa)

    if df_tracking.empty:
        # Não encontrado / filtrado a zero → NÃO EMITIDO, mas ainda cobra a data prevista.
        return ResultadoDocumento(
            status_real=NAO_EMITIDO, emitido_nao_emitido=NAO_EMITIDO,
            status_consolidado=NAO_EMITIDO, com_itaipu="CMI",
            kpis=analisar_kpis_documento(df_tracking, NAO_EMITIDO, "", data_prevista, hoje=hoje),
            atrasos=calcular_atrasos_acumulados(df_tracking, NAO_EMITIDO, data_prevista, hoje=hoje),
        )

    # Dados estáticos da linha Current (código/descrição atuais).
    current = df_tracking[df_tracking["Current"].astype(str).str.lower() == "true"]
    linha_estatica = current.iloc[0] if not current.empty else None

    tl = resolver_linha_da_verdade(df_tracking)
    if tl.nao_emitido:
        status_real, bruto, rev = NAO_EMITIDO, "", ""
        rev_visual = data_visual = status_visual = None
    else:
        rev = tl.revisao_atual
        status_real = calcular_status_real(tl.df_para_calculo, rev)
        ld = tl.linha_dinamica
        bruto = str(ld.get(COL_STATUS, "")).strip()
        rev_visual = str(ld.get("Revisão", "")).strip()
        data_visual = ld.get("Data de Alteração")
        status_visual = ld.get(COL_STATUS)

    emitido = calcular_emitido_nao_emitido(status_real)
    consolidado = calcula_status_consolidado(status_real, bruto, emitido)
    com = calcula_parado_com(bruto)
    kpis = analisar_kpis_documento(df_tracking, status_real, rev, data_prevista, hoje=hoje)
    atrasos = calcular_atrasos_acumulados(df_tracking, status_real, data_prevista, hoje=hoje)

    return ResultadoDocumento(
        revisao=rev_visual, data_ultimo_status=data_visual, status_emissao=status_visual,
        cod_itaipu_atual=str(linha_estatica.get("No. do Documento")) if linha_estatica is not None else None,
        cod_cmi_atual=str(linha_estatica.get("Controle do Emissor")) if linha_estatica is not None else None,
        descricao_atual=str(linha_estatica.get("Título")) if linha_estatica is not None else None,
        status_real=status_real, emitido_nao_emitido=emitido,
        status_consolidado=consolidado, com_itaipu=com, kpis=kpis, atrasos=atrasos,
    )
