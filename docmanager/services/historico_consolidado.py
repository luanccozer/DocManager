"""Orquestração do Histórico Consolidado — DIRIGIDO PELO CONTROLE (§24.11).

O Controle de Documentos (agora OBRIGATÓRIO) determina QUAIS documentos entram
no histórico; o extrato Aconex fornece o histórico (revisões, envios, retornos)
de cada um. Fluxo:

  Controle (aba selecionada) → para cada documento (com sua Fase de Projeto):
    busca no Aconex pela CASCATA dos demais módulos (AconexIndex.localizar:
    par Itaipu+CMI → CMI → Itaipu, desempate por data)
      • achou   → revisões do doc (build_wide_table) + Tracking ID + Fase de
                  Projeto + Data Prevista/Reprogramação do Controle
      • não achou → 1 linha NÃO EMITIDO (campos do Aconex em branco, Tracking em
                    branco; mantém Fase/códigos/datas do Controle)
    → calcular_atrasos (4 colunas: CMI antes de Itaipu) → Excel

O extrato ainda passa por gerar_dataset_dashboard (limpeza, borda 19/08, ciclo
consistente, PA-fallback, retorno representativo) e build_wide_table; a novidade
é que a SELEÇÃO dos documentos vem do Controle, não mais do Aconex. Documentos
que estão no Aconex mas NÃO no Controle não aparecem. Se o Controle marca um doc
como EMITIDO mas a busca não acha tracking, isso é sinalizado no log.
"""
from __future__ import annotations

import pandas as pd

from ..core.constants import (
    COL_DATA,
    COL_DOC_CMI,
    COL_DOC_ITAIPU,
    COL_REVISAO,
    COL_TITULO,
    COL_TRACKING,
    NAO_EMITIDO,
)
from ..core.delays import (
    BASE_CMI_REPROGRAMACAO,
    COL_DATA_PREVISTA,
    COL_DATA_PREVISTA_CTRL,
    COL_REPROGRAMACAO,
    DelayPolicy,
    calcular_atrasos,
)
from ..core.identity import AconexIndex
from ..core.wide import (
    COL_DATA_ENVIO,
    COL_DATA_RETORNO,
    COL_STATUS_ENVIO,
    build_wide_table,
    gerar_dataset_dashboard,
)
from .controle_docs import ControleDocs, chave_codigo, partes_codigo

# Coluna nova pedida pelo usuário (§24.11): a fase de projeto do Controle.
COL_FASE = "Fase de Projeto"


def _resolver_base(prevista, reprogramada, base_cmi_0a: str):
    """Base do atraso CMI 0A: reprogramação (>prevista) ou prevista, conforme config."""
    if base_cmi_0a == BASE_CMI_REPROGRAMACAO and reprogramada is not None:
        return reprogramada
    return prevista


def _indice_chave(df_bruto: pd.DataFrame) -> dict:
    """{chave_codigo(código) → Tracking ID} sobre a base bruta, tolerante a
    espaços/invisíveis internos (§24.8b). Fallback da busca quando a cascata
    exata falha. Colisão: vence o Tracking de Data de Alteração mais recente."""
    if df_bruto.empty:
        return {}
    datas = pd.to_datetime(df_bruto[COL_DATA], dayfirst=True, errors="coerce")
    docs = df_bruto[COL_DOC_ITAIPU].astype(str)
    cmis = df_bruto[COL_DOC_CMI].astype(str)
    tids = df_bruto[COL_TRACKING].astype(str)
    melhor: dict[str, tuple] = {}
    for pos in range(len(df_bruto)):
        tid = tids.iat[pos].strip()
        if not tid:
            continue
        data = datas.iat[pos]
        for cod in (chave_codigo(docs.iat[pos]), chave_codigo(cmis.iat[pos])):
            if not cod:
                continue
            atual = melhor.get(cod)
            if atual is None or (pd.notna(data) and (pd.isna(atual[0]) or data > atual[0])):
                melhor[cod] = (data, tid)
    return {c: t for c, (_, t) in melhor.items()}


def _buscar_tracking(r, idx: AconexIndex, idx_chave: dict) -> str:
    """Tracking do documento do Controle no Aconex: cascata EXATA (par Itaipu+CMI
    → CMI → Itaipu, como o módulo de Status) e, se falhar, fallback tolerante por
    `chave_codigo` (cobre sujeira de Excel e célula multi-código)."""
    df_t = idx.localizar(r.cod_itaipu, r.cod_cmi)
    if not df_t.empty:
        return str(df_t[COL_TRACKING].iloc[0]).strip()
    for cod_bruto in (r.cod_itaipu, r.cod_cmi):
        for parte in partes_codigo(cod_bruto):
            tid = idx_chave.get(chave_codigo(parte))
            if tid:
                return str(tid).strip()
    return ""


def _ts(d):
    return pd.Timestamp(d) if d else pd.NaT


def _anexar_controle(d: dict, r, base_cmi_0a: str) -> None:
    """Anexa a uma linha (do wide ou sintética) as infos do Controle."""
    d[COL_FASE] = r.fase
    d[COL_DATA_PREVISTA] = _ts(r.data_prevista)
    d[COL_REPROGRAMACAO] = _ts(r.data_reprogramada)
    d[COL_DATA_PREVISTA_CTRL] = _ts(_resolver_base(r.data_prevista, r.data_reprogramada, base_cmi_0a))


def _linha_nao_emitido(r, base_cmi_0a: str) -> dict:
    """Documento do Controle sem tracking no Aconex → 1 linha NÃO EMITIDO. Recebe
    um Tracking interno único (para o atraso agrupar corretamente) que é APAGADO
    na saída — o usuário quer o Tracking em branco para os não emitidos."""
    chave = chave_codigo(r.cod_itaipu) or chave_codigo(r.cod_cmi) or r.titulo
    d = {
        COL_DOC_ITAIPU: r.cod_itaipu,
        COL_DOC_CMI: r.cod_cmi,
        COL_TRACKING: f"NE::{chave}",
        COL_TITULO: r.titulo,
        COL_REVISAO: "",
        COL_STATUS_ENVIO: NAO_EMITIDO,
        # Metadados do Controle preenchem o vazio do Aconex (pedido do usuário).
        # Nomes idênticos aos do wide (core/wide.py::_COLS_META) p/ casar as colunas.
        "Especialidade": r.especialidade,
        "Subespecialidade": r.subespecialidade,
        "Tipo do Documento DCC": r.tipo_documento,
        "Subtipo DCC": r.subtipo,
    }
    _anexar_controle(d, r, base_cmi_0a)
    return d


def _chaves_exclusao(codigos) -> dict[str, str]:
    """{chave_codigo → texto original} da lista MANUAL de remoção (pedido do
    usuário): documentos que o usuário cola na interface para NÃO entrarem no
    histórico. Tolerante à sujeira de Excel e à célula multi-código, como o resto
    do módulo (§24.8b)."""
    mapa: dict[str, str] = {}
    for bruto in codigos or ():
        for parte in partes_codigo(bruto):
            ch = chave_codigo(parte)
            if ch:
                mapa.setdefault(ch, str(parte).strip())
    return mapa


def _chaves_da_linha(r) -> set[str]:
    """Chaves de código (Itaipu e CMI, célula multi-código) de uma linha do
    Controle — para casar contra a lista manual de remoção."""
    chaves: set[str] = set()
    for cod_bruto in (r.cod_itaipu, r.cod_cmi):
        for parte in partes_codigo(cod_bruto):
            ch = chave_codigo(parte)
            if ch:
                chaves.add(ch)
    return chaves


def gerar_historico(df_bruto: pd.DataFrame, controle: ControleDocs | None,
                    policy: DelayPolicy | None = None, *,
                    excluir_codigos=None, log_cb=None) -> pd.DataFrame:
    """Histórico dirigido pelo Controle (obrigatório). Ver docstring do módulo.

    `excluir_codigos`: lista MANUAL de códigos (Itaipu ou CMI) colada na interface
    para remover documentos do histórico — casada de forma tolerante contra o
    código Itaipu E o CMI de cada linha do Controle."""
    policy = policy or DelayPolicy()

    def log(msg):
        if log_cb:
            log_cb(msg)

    if controle is None:
        raise ValueError(
            "Controle de Documentos é obrigatório: ele determina os documentos "
            "do histórico (nova estrutura §24.11).")

    df_limpo = gerar_dataset_dashboard(df_bruto)
    df_wide_all = build_wide_table(df_limpo)
    idx = AconexIndex(df_bruto)
    idx_chave = _indice_chave(df_bruto)
    wide_por_tracking = ({str(tid): g for tid, g in df_wide_all.groupby(COL_TRACKING, sort=False)}
                         if not df_wide_all.empty else {})

    excluir = _chaves_exclusao(excluir_codigos)   # {chave → texto original}
    excluir_set = set(excluir)
    usados_excluir: set[str] = set()

    linhas: list[dict] = []
    vistos: set[str] = set()
    n_ach = n_ne = n_rem = 0
    emitido_sem_tracking: list = []
    for r in controle.rows:
        if excluir_set:
            atinge = _chaves_da_linha(r) & excluir_set
            if atinge:
                usados_excluir |= atinge
                n_rem += 1
                continue  # documento na lista MANUAL de remoção (pedido do usuário)
        tracking = _buscar_tracking(r, idx, idx_chave)
        revs = wide_por_tracking.get(tracking) if tracking else None
        if revs is not None and not revs.empty:
            if tracking in vistos:
                continue  # doc já incluído por outra linha do Controle (código histórico)
            vistos.add(tracking)
            n_ach += 1
            for _, rev in revs.iterrows():
                d = rev.to_dict()
                _anexar_controle(d, r, policy.base_cmi_0a)
                linhas.append(d)
        else:
            n_ne += 1
            linhas.append(_linha_nao_emitido(r, policy.base_cmi_0a))
            # Sinaliza: Controle diz EMITIDO mas a busca NÃO achou tracking algum
            # (pedido do usuário). Se achou tracking mas sem revisão válida
            # (fantasma filtrado), não é "sem tracking" — não entra aqui.
            if r.esta_emitido and not tracking:
                emitido_sem_tracking.append(r)

    if excluir:
        log(f"Remoção manual: {n_rem} documento(s) retirado(s) do histórico "
            f"({len(excluir)} código(s) na lista).")
        nao_achados = [txt for ch, txt in excluir.items() if ch not in usados_excluir]
        if nao_achados:
            amostra = ", ".join(nao_achados[:30])
            resto = f" (+{len(nao_achados) - 30} outros)" if len(nao_achados) > 30 else ""
            log(f"⚠️ {len(nao_achados)} código(s) da lista NÃO encontrado(s) no "
                f"Controle: {amostra}{resto}")

    if not linhas:
        log("Controle → histórico: nenhum documento (Controle vazio na aba selecionada?).")
        return pd.DataFrame()

    df = pd.DataFrame(linhas)
    for col in (COL_DATA_ENVIO, COL_DATA_RETORNO, COL_DATA_PREVISTA,
                COL_REPROGRAMACAO, COL_DATA_PREVISTA_CTRL):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df = calcular_atrasos(df, policy)
    # Tracking em branco na SAÍDA para os não emitidos (pedido do usuário).
    df.loc[df[COL_STATUS_ENVIO].astype(str) == NAO_EMITIDO, COL_TRACKING] = ""

    log(f"Controle → histórico: {n_ach} documentos encontrados no Aconex, "
        f"{n_ne} não emitidos (de {len(controle.rows)} no Controle).")
    if emitido_sem_tracking:
        log(f"⚠️ {len(emitido_sem_tracking)} documento(s) marcado(s) EMITIDO no "
            f"Controle mas SEM tracking no Aconex (verificar códigos):")
        for r in emitido_sem_tracking[:30]:
            log(f"    {r.cod_itaipu} | {r.cod_cmi}")
        if len(emitido_sem_tracking) > 30:
            log(f"    … (+{len(emitido_sem_tracking) - 30} outros)")
    return df
