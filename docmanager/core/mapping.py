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
from .kpis import analisar_kpis_documento, calcular_atrasos_acumulados
from .normalize import celula_para_date as _como_date
from .normalize import remover_acentos
from .planejamento import reconciliar_datas
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

    - `prevista_para_celula`: DATA PREVISTA a escrever na célula ETAPA 1 —
      `None` significa "não mexer".
    - `reprogramada`: REPROGRAMAÇÃO a escrever — `None` significa "não mexer".
    - `data_ref`: REPROGRAMAÇÃO > PREVISTA **já considerando o que ficará nas
      células**, não só o que veio do Controle. É a data que o atraso usa.
    - `via`: como o documento foi localizado no Controle ('exato' | 'frouxo' |
      'contido' | '' quando não achou). Só para diagnóstico/log.
    - `prevista_atualizada`: a célula já tinha data e o Controle trouxe uma mais
      recente (para o log distinguir preenchimento de atualização).
    - `titulo_controle`: DESCRIÇÃO do Controle. Serve de **fallback** para a
      descrição do documento quando o Aconex não o conhece (§27.3) — sem isso o
      não emitido fica só com o código na planilha.
    """
    prevista_para_celula: date | None = None
    reprogramada: date | None = None
    data_ref: date | None = None
    via: str = ""
    prevista_atualizada: bool = False
    titulo_controle: str = ""

    @property
    def achou(self) -> bool:
        return bool(self.via)


def resolver_datas_controle(valor_celula_prevista, codigos_historicos, cod_itaipu_atual,
                            cod_cmi_atual, controle, *,
                            valor_celula_reprogramada: date | None = None) -> DatasControle:
    """Resolve PREVISTA e REPROGRAMAÇÃO da etapa 1 e entrega a `data_ref` do atraso.

    Regras (unificadas com o Doc List Mapping a pedido do usuário, §24.13 —
    "a lógica dele é melhor"):

    - **DATA PREVISTA** — vence a data **mais recente** entre a planilha e o
      Controle. Antes o Mapa só escrevia na célula vazia, então uma reprogramação
      de calendário registrada no Controle nunca chegava ao mapeamento.
    - **DATA REPROGRAMADA** — só preenche o **vazio**: a coluna aceita input
      manual, e antes o Mapa a sobrescrevia a cada rodada, apagando o que a
      equipe tinha digitado.
    - **`data_ref`** — REPROGRAMAÇÃO > PREVISTA sobre os valores FINAIS (os que
      ficam nas células). Antes vinha só do Controle, então o atraso ignorava uma
      data mais recente que estivesse na planilha.

    A busca no Controle é a cascata de `ControleDocs.resolver` (exato → frouxo →
    'contém'), que inclui o equivalente ao Ctrl+F manual (§24.12).
    """
    prevista_atual = _como_date(valor_celula_prevista)
    reprogramada_atual = _como_date(valor_celula_reprogramada)
    linha = None
    via = ""
    if controle is not None:
        m = controle.resolver(codigos_historicos, cod_itaipu_atual, cod_cmi_atual)
        linha, via = m.linha, m.via

    d = reconciliar_datas(
        prevista_planilha=prevista_atual, reprogramada_planilha=reprogramada_atual,
        prevista_controle=linha.data_prevista if linha else None,
        reprogramada_controle=linha.data_reprogramada if linha else None)
    return DatasControle(prevista_para_celula=d.prevista, reprogramada=d.reprogramada,
                         data_ref=d.data_ref, via=via,
                         prevista_atualizada=d.prevista_atualizada,
                         titulo_controle=str(linha.titulo).strip() if linha else "")


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
