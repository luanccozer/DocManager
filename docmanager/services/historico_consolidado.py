"""Orquestração do Histórico Consolidado turbinado (KB §18.5 + feature nova).

Pipeline:
  base Aconex bruta
    → gerar_dataset_dashboard (long, borda 19/08 corrigida)
    → build_wide_table (1 linha por Tracking+Revisão + SLA)
    → anexar_data_prevista (data_ref do Controle por Tracking)
    → injetar_linhas_sinteticas (docs previstos e não postados)
    → calcular_atrasos (4 colunas de atraso)
    → exportar Excel (renomeia Data Envio→Data de Envio, layout legado + novas)

Este módulo é a ponte core↔serviços: o core (wide/delays) permanece puro;
aqui ele se casa com o Controle de Documentos.
"""
from __future__ import annotations

import pandas as pd

from ..core.delays import (
    BASE_CMI_REPROGRAMACAO,
    COL_DATA_PREVISTA,
    COL_DATA_PREVISTA_CTRL,
    COL_REPROGRAMACAO,
    DelayPolicy,
    calcular_atrasos,
)
from ..core.identity import construir_indice_reverso, obter_codigos_historicos
from ..core.wide import (
    COL_STATUS_ENVIO,
    build_wide_table,
    gerar_dataset_dashboard,
)
from ..core.constants import COL_DOC_CMI, COL_DOC_ITAIPU, COL_TITULO, COL_TRACKING
from .controle_docs import ControleDocs, chave_codigo, partes_codigo

_SINTETICA_STATUS = "NÃO EMITIDO"


def _resolver_base(prevista, reprogramada, base_cmi_0a: str):
    """Base do atraso CMI 0A conforme a config: reprogramação (>prevista) ou prevista."""
    if base_cmi_0a == BASE_CMI_REPROGRAMACAO and reprogramada is not None:
        return reprogramada
    return prevista


def anexar_datas_controle(df_wide: pd.DataFrame, controle: ControleDocs | None,
                          df_base: pd.DataFrame, *,
                          base_cmi_0a: str = BASE_CMI_REPROGRAMACAO) -> pd.DataFrame:
    """Anexa por Tracking as datas do Controle:
      - 'Data Prevista' e 'Reprogramação' (exibição, brutas);
      - 'Data Prevista (Controle)' (base resolvida do atraso CMI 0A, interna)."""
    df = df_wide.copy()
    if controle is None or df.empty:
        for c in (COL_DATA_PREVISTA, COL_REPROGRAMACAO, COL_DATA_PREVISTA_CTRL):
            df[c] = pd.NaT
        return df
    prev_por, reprog_por, base_por = {}, {}, {}
    for tid, grp in df_base.groupby(COL_TRACKING, sort=False):
        codigos = obter_codigos_historicos(grp)
        prevista, reprogramada = controle.datas_por_codigos(codigos)
        prev_por[str(tid)] = prevista
        reprog_por[str(tid)] = reprogramada
        base_por[str(tid)] = _resolver_base(prevista, reprogramada, base_cmi_0a)
    chave = df[COL_TRACKING].astype(str)
    df[COL_DATA_PREVISTA] = pd.to_datetime(chave.map(prev_por), errors="coerce")
    df[COL_REPROGRAMACAO] = pd.to_datetime(chave.map(reprog_por), errors="coerce")
    df[COL_DATA_PREVISTA_CTRL] = pd.to_datetime(chave.map(base_por), errors="coerce")
    return df


# Compat: nome antigo mantido como alias.
anexar_data_prevista = anexar_datas_controle


def varredura_final_controle(df_wide: pd.DataFrame, controle: ControleDocs | None, *,
                             base_cmi_0a: str = BASE_CMI_REPROGRAMACAO,
                             ) -> tuple[pd.DataFrame, int, set[int]]:
    """Varredura FINAL (§24.8c, pedido do usuário): cada documento que ficou SEM
    data prevista procura os códigos DA PRÓPRIA LINHA direto no Controle —
    primeiro por igualdade (chave tolerante), depois por CONTÉM (como o Ctrl+F
    na mão). Retorna (df, nº de resgatados, ids das linhas do Controle usadas —
    para a injeção de sintéticas não duplicá-las)."""
    if controle is None or df_wide.empty or COL_DATA_PREVISTA_CTRL not in df_wide.columns:
        return df_wide, 0, set()
    df = df_wide
    sem_data = df[df[COL_DATA_PREVISTA_CTRL].isna()]
    if sem_data.empty:
        return df, 0, set()
    resgatados = 0
    usadas: set[int] = set()
    for tid, grp in sem_data.groupby(COL_TRACKING, sort=False):
        codigos: list[str] = []
        for col in (COL_DOC_ITAIPU, COL_DOC_CMI):
            if col in grp.columns:
                codigos.extend(str(v).strip() for v in grp[col].tolist() if str(v).strip())
        linha = None
        for c in dict.fromkeys(codigos):          # ordem estável, sem duplicatas
            r = controle.linha_por_codigo(c)
            if r is not None and r.tem_data:
                linha = r
                break
        if linha is None:
            for c in dict.fromkeys(codigos):
                r = controle.buscar_contendo(c)
                if r is not None and r.tem_data:
                    linha = r
                    break
        if linha is None:
            continue
        resgatados += 1
        usadas.add(id(linha))
        mask = df[COL_TRACKING] == tid
        prev = pd.Timestamp(linha.data_prevista) if linha.data_prevista else pd.NaT
        reprog = pd.Timestamp(linha.data_reprogramada) if linha.data_reprogramada else pd.NaT
        base = _resolver_base(linha.data_prevista, linha.data_reprogramada, base_cmi_0a)
        df.loc[mask, COL_DATA_PREVISTA] = prev
        df.loc[mask, COL_REPROGRAMACAO] = reprog
        df.loc[mask, COL_DATA_PREVISTA_CTRL] = pd.Timestamp(base) if base else pd.NaT
    return df, resgatados, usadas


def injetar_linhas_sinteticas(df_wide: pd.DataFrame, controle: ControleDocs | None,
                              indice_reverso: dict,
                              ignorar_ids: set[int] | None = None) -> pd.DataFrame:
    """Adiciona linhas NÃO EMITIDO para docs do Controle sem representação no
    wide (não resolvem no índice reverso, ou resolvem para um Tracking que foi
    filtrado — ex.: preso em integração/0AA). `ignorar_ids`: linhas do Controle
    já casadas pela varredura final (§24.8c) — não podem virar sintética."""
    if controle is None:
        return df_wide
    ignorar_ids = ignorar_ids or set()
    trackings_no_wide = set(df_wide[COL_TRACKING].astype(str)) if not df_wide.empty else set()
    novas: list[dict] = []
    ja_incluido: set[str] = set()
    for r in controle.rows:
        if id(r) in ignorar_ids:
            continue  # já casou com um doc do wide pela varredura final
        # Célula multi-código e sujeira de Excel: mesma chave tolerante do match
        # (senão um doc já postado viraria sintética duplicada) — §24.8b.
        codigos = [chave_codigo(p) for cod in (r.cod_itaipu, r.cod_cmi) for p in partes_codigo(cod)]
        codigos = [c for c in codigos if c]
        if not codigos:
            continue
        tid = next((indice_reverso[c] for c in codigos if c in indice_reverso), None)
        if tid is not None and str(tid) in trackings_no_wide:
            continue  # já está no wide
        chave = codigos[0]
        if chave in ja_incluido:
            continue
        ja_incluido.add(chave)
        prevista = pd.Timestamp(r.data_prevista) if r.data_prevista else pd.NaT
        reprog = pd.Timestamp(r.data_reprogramada) if r.data_reprogramada else pd.NaT
        base = pd.Timestamp(r.data_ref) if r.data_ref else pd.NaT
        novas.append({
            COL_DOC_ITAIPU: r.cod_itaipu,
            COL_DOC_CMI: r.cod_cmi,
            COL_TRACKING: f"SINT::{chave}",
            COL_TITULO: r.titulo,
            "Revisão": "",
            COL_STATUS_ENVIO: _SINTETICA_STATUS,
            COL_DATA_PREVISTA: prevista,
            COL_REPROGRAMACAO: reprog,
            COL_DATA_PREVISTA_CTRL: base,
        })
    if not novas:
        return df_wide
    df_novas = pd.DataFrame(novas).reindex(columns=df_wide.columns if not df_wide.empty else None)
    # Alinha dtypes de data (o reindex deixa NaN float; concatenar com datetime64
    # dispara DeprecationWarning de timedelta no pandas 2.3).
    from ..core.wide import COL_DATA_ENVIO, COL_DATA_RETORNO
    for col in (COL_DATA_ENVIO, COL_DATA_RETORNO, COL_DATA_PREVISTA,
                COL_REPROGRAMACAO, COL_DATA_PREVISTA_CTRL):
        if col in df_novas.columns:
            df_novas[col] = pd.to_datetime(df_novas[col], errors="coerce")
    return pd.concat([df_wide, df_novas], ignore_index=True)


def gerar_historico(df_bruto: pd.DataFrame, controle: ControleDocs | None = None,
                    policy: DelayPolicy | None = None, *, log_cb=None) -> pd.DataFrame:
    """Do bruto ao wide final com atrasos e sintéticas (tudo em memória)."""
    policy = policy or DelayPolicy()
    df_limpo = gerar_dataset_dashboard(df_bruto)
    df_wide = build_wide_table(df_limpo)
    df_wide = anexar_datas_controle(df_wide, controle, df_limpo, base_cmi_0a=policy.base_cmi_0a)
    # Varredura final (§24.8c): quem ficou sem data procura direto no Controle
    # pelos códigos da própria linha (igualdade tolerante e depois CONTÉM).
    df_wide, resgatados, usadas = varredura_final_controle(
        df_wide, controle, base_cmi_0a=policy.base_cmi_0a)
    if controle is not None and log_cb is not None and not df_wide.empty:
        # Diagnóstico do casamento com o Controle (§24.8b): quantos documentos
        # do histórico receberam data — permite ver na hora se o match falhou.
        por_doc = df_wide.groupby(COL_TRACKING)[COL_DATA_PREVISTA_CTRL].max()
        log_cb(f"Controle ↔ histórico: {int(por_doc.notna().sum())} de {len(por_doc)} "
               f"documentos com data prevista/reprogramação"
               f" ({resgatados} pela varredura final).")
    indice_reverso = construir_indice_reverso(df_bruto) if controle is not None else {}
    df_wide = injetar_linhas_sinteticas(df_wide, controle, indice_reverso, ignorar_ids=usadas)
    df_wide = calcular_atrasos(df_wide, policy)
    return df_wide
