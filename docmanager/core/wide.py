"""Histórico consolidado: dataset (long) + tabela wide ÚNICA (KB §18.5).

Funde os dois caminhos divergentes do legado (`gerar_dataset_dashboard` L938,
`gerar_excel_historico_formatado` L1032 e `preparar_tabela_wide` L1152) num só:

- `gerar_dataset_dashboard(df_bruto)` → df_limpo (long, 1 linha por evento),
  com a borda 19/08 PADRONIZADA (regime novo ⇔ data >= 19/08, §21.3):
  o legado usava `<=` para o passado, tratando 19/08 como regime antigo,
  divergindo do motor de status. Aqui `is_regime_novo` manda em todo lugar.
- `build_wide_table(df_limpo)` → df_wide (1 linha por Tracking+Revisão) com
  colunas internas `Data Envio`/`Data Retorno`, `Status Envio`/`Status Retorno`
  e `SLA_Itaipu`. Ordenação pela CANÔNICA do ciclo de vida (`normalizar_revisao`,
  ljust-'z'). A exportação Excel renomeia para `Data de Envio`/`Data de Retorno`.

Ciclo de vida das revisões (KB §3.1): a família começa nas internas de
integração 0AA/0AB (só alguns tipos), emite ao cliente na 0A, evolui 0B/0C… e
FECHA na aprovação de número seco (0). Se algo muda depois, nasce a próxima
família 1A/1B…→1, e assim por diante. A ordem correta é, portanto,
`0AA<0AB<0A<0B<0<1A<1B<1<…` — exatamente o que `normalizar_revisao` produz.

Divergências sancionadas: #2 (borda). O antigo #4 (ordenar o histórico pela
sort key de 3 níveis, herdada de data_manager L1192) foi um ERRO: aquela chave
joga TODOS os números secos (0,1,2 = aprovações) para o fim, depois das letras
de famílias posteriores — desalinhando a família e bagunçando a cadeia de
atraso CMI (que mede contra o retorno da revisão anterior). Corrigido aqui.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import (
    COL_DATA,
    COL_REVISAO,
    COL_STATUS,
    COL_TIPO_DOC,
    COL_TITULO,
    COL_TRACKING,
    COL_VERSAO,
    DATA_CORTE_FLUXO,
    HIST_STATUS_VALIDOS,
    HIST_TIPOS_VALIDOS,
    SLA_ITAIPU_DEMAIS,
    SLA_ITAIPU_REV_0A,
)
from .normalize import normalizar_revisao

# Colunas internas do wide (sem "de"); a exportação Excel renomeia.
COL_DATA_ENVIO = "Data Envio"
COL_STATUS_ENVIO = "Status Envio"
COL_DATA_RETORNO = "Data Retorno"
COL_STATUS_RETORNO = "Status Retorno"
COL_SLA = "SLA_Itaipu"

_COLS_META = ("Especialidade", "Subespecialidade", "Tipo do Documento DCC", "Subtipo DCC")
_COLS_ESTATICAS = (
    "No. do Documento", "Controle do Emissor", COL_TRACKING, COL_TITULO,
    COL_TIPO_DOC, "Especialidade", "Subespecialidade",
    "Tipo do Documento DCC", "Subtipo DCC", COL_VERSAO, "Current", COL_REVISAO,
)


def _ultimo_nao_vazio(s: pd.Series) -> str:
    """Último valor não-vazio da série (na ordem do grupo); '' se todos vazios."""
    nao_vazios = s[s != ""]
    return nao_vazios.iloc[-1] if len(nao_vazios) else ""


def gerar_dataset_dashboard(df_bruto: pd.DataFrame) -> pd.DataFrame:
    """Dataset long limpo (envios vs retornos), base do histórico e do dashboard."""
    if df_bruto.empty:
        return pd.DataFrame()

    df = df_bruto.copy()

    # 1. Filtros grossos: Terminated, status válidos, tipos válidos.
    if "Status da Revisão" in df.columns:
        df = df[df["Status da Revisão"].astype(str).str.strip() != "Terminated"]
    df = df[df[COL_STATUS].isin(HIST_STATUS_VALIDOS)]
    if COL_TIPO_DOC in df.columns:
        df = df[df[COL_TIPO_DOC].isin(HIST_TIPOS_VALIDOS)]

    # 2. Limpeza técnica de revisão e datas.
    df[COL_REVISAO] = df[COL_REVISAO].astype(str).str.upper().str.replace("R", "", regex=False).str.strip()
    df = df[df[COL_REVISAO].str.len() <= 2]
    df[COL_DATA] = pd.to_datetime(df[COL_DATA], errors="coerce", dayfirst=True)
    df = df.dropna(subset=[COL_DATA])
    df["Versão_Int"] = pd.to_numeric(df[COL_VERSAO], errors="coerce").fillna(0)

    # 3. Borda 19/08 PADRONIZADA: regime novo ⇔ data >= corte (§21.3).
    antigo = df[COL_DATA] < DATA_CORTE_FLUXO
    df.loc[antigo & (df[COL_STATUS] == "Em Processo"), COL_STATUS] = "Em Processo (CMI)"
    df.loc[antigo & (df[COL_STATUS] == "Para Análise"), COL_STATUS] = "Em Processo"
    df = df[~((~antigo) & (df[COL_STATUS] == "Para Análise"))]

    # Regras cirúrgicas do "Para Aprovação": comissionamento vira retorno
    # ("Para Assinatura"); o restante NÃO é mais exterminado aqui — segue no
    # frame até a etapa 5, onde serve de ENVIO-fallback (§24.7) e sai do fluxo.
    mask_para_aprov = df[COL_STATUS] == "Para Aprovação"
    mask_comiss = df[COL_TITULO].str.contains(r"PLANILHA[S]? DE COMISSIONAMENTO", case=False, na=False)
    df.loc[mask_para_aprov & mask_comiss, COL_STATUS] = "Para Assinatura"

    # 4. Ordenação para deduplicação.
    df = df.sort_values(
        by=[COL_TRACKING, COL_REVISAO, COL_DATA, "Versão_Int"],
        ascending=[True, True, False, False],
    )

    # 4.5. Backfill de metadados por Tracking (último valor não-vazio sobrescreve).
    # Evita `.replace(regex)` (deprecação de downcasting no pandas 2.3); opera
    # sobre a versão já "stripada" e pega o último não-vazio na ordem do grupo.
    cols_meta = [c for c in _COLS_META if c in df.columns]
    for col in cols_meta:
        stripped = df[col].astype(str).str.strip()
        df[col] = stripped.groupby(df[COL_TRACKING]).transform(_ultimo_nao_vazio)

    # 5. Seleção do ciclo por revisão — REGRA DO ÚLTIMO CICLO CONSISTENTE
    # (validada pelo usuário em 2026-07-14; KB §24.6). Por (Tracking, Revisão):
    #   - retorno = último retorno (como sempre);
    #   - envio   = último 'Em Processo' com data ≤ retorno (par consistente);
    #   - envio POSTERIOR ao último retorno da revisão:
    #       · é o último evento do documento (data+versão) → RELANÇAMENTO:
    #         ciclo novo em aberto (envio = ele; a revisão fica SEM retorno);
    #       · senão → subida com revisão errada, corrigida em seguida
    #         (ex.: "0C" de 24/07 que virou 0D no mesmo dia) → ignorada;
    #   - sem retorno → último envio (pendente, comportamento de sempre).
    # E o ENVIO-FALLBACK do "Para Aprovação" (§24.7, pedido do usuário): no
    # início do projeto a revisão definitiva ("0") subia como 'Para Aprovação';
    # quando a revisão NÃO tem 'Em Processo', o último PA ≤ retorno vira envio.
    # PA nunca vira retorno e nunca substitui envio real (só fallback).
    mask_pa_rest = df[COL_STATUS] == "Para Aprovação"
    pa_fallback = df[mask_pa_rest]
    df = df[~mask_pa_rest]                       # extermínio (agora aqui)

    asc = df.sort_values(by=[COL_DATA, "Versão_Int"])
    env = asc[asc[COL_STATUS] == "Em Processo"]
    ret = asc[~asc[COL_STATUS].str.contains("Em Processo", case=False, na=False)]
    ult = asc.groupby(COL_TRACKING).tail(1)
    ult_key = {t: (d, v) for t, d, v in zip(ult[COL_TRACKING], ult[COL_DATA], ult["Versão_Int"])}

    env_g = dict(iter(env.groupby([COL_TRACKING, COL_REVISAO], sort=False)))
    ret_g = dict(iter(ret.groupby([COL_TRACKING, COL_REVISAO], sort=False)))
    pa_g = dict(iter(pa_fallback.sort_values(by=[COL_DATA, "Versão_Int"])
                     .groupby([COL_TRACKING, COL_REVISAO], sort=False)))
    idx_env: list = []
    idx_ret: list = []
    idx_env_pa: list = []
    for chave in set(env_g) | set(ret_g):
        g_env = env_g.get(chave)
        g_ret = ret_g.get(chave)
        if g_env is None:                       # só retorno (sem envio na base)
            linha_ret = g_ret.iloc[-1]
            g_pa = pa_g.get(chave)
            if g_pa is not None:                # PA anterior ao retorno = envio
                cand = g_pa[g_pa[COL_DATA] <= linha_ret[COL_DATA]]
                if not cand.empty:
                    idx_env_pa.append(cand.index[-1])
            idx_ret.append(linha_ret.name)
            continue
        if g_ret is None:                       # pendente: último envio
            idx_env.append(g_env.index[-1])
            continue
        linha_ret = g_ret.iloc[-1]
        data_ret = linha_ret[COL_DATA]
        tardios = g_env[g_env[COL_DATA] > data_ret]
        if not tardios.empty:
            s = tardios.iloc[-1]
            if (s[COL_DATA], s["Versão_Int"]) == ult_key.get(chave[0]):
                idx_env.append(s.name)          # relançamento → em aberto
                continue
        consistentes = g_env[g_env[COL_DATA] <= data_ret]
        if not consistentes.empty:
            idx_env.append(consistentes.index[-1])
        idx_ret.append(linha_ret.name)

    df_envios = df.loc[idx_env]
    if idx_env_pa:
        # PA promovido a envio: rotulado 'Em Processo' (marcador canônico de
        # envio no wide, mesma convenção do 'Para Análise' pré-corte).
        extras = pa_fallback.loc[idx_env_pa].copy()
        extras[COL_STATUS] = "Em Processo"
        df_envios = pd.concat([df_envios, extras])
    df_retornos = df.loc[idx_ret]
    # Filtra partes vazias antes do concat: concatenar um frame vazio com
    # colunas datetime dispara DeprecationWarning de timedelta no pandas 2.3.
    partes = [p for p in (df_envios, df_retornos) if not p.empty]
    df_final = pd.concat(partes) if partes else df.iloc[0:0]
    df_final = df_final.sort_values(by=[COL_TRACKING, COL_REVISAO, COL_DATA])
    return df_final


def build_wide_table(df_limpo: pd.DataFrame) -> pd.DataFrame:
    """1 linha por (Tracking, Revisão) com Envio/Retorno + SLA_Itaipu.

    Builder ÚNICO consumido pelo Excel e pelo dashboard.
    """
    if df_limpo.empty:
        return pd.DataFrame()

    cols_existentes = [c for c in _COLS_ESTATICAS if c in df_limpo.columns]
    df_base = df_limpo.sort_values(by=[COL_DATA]).drop_duplicates(
        subset=[COL_TRACKING, COL_REVISAO], keep="last"
    )[cols_existentes].copy()

    df_envio = df_limpo[df_limpo[COL_STATUS] == "Em Processo"][
        [COL_TRACKING, COL_REVISAO, COL_DATA, COL_STATUS]
    ].rename(columns={COL_DATA: COL_DATA_ENVIO, COL_STATUS: COL_STATUS_ENVIO})

    df_retorno = df_limpo[df_limpo[COL_STATUS] != "Em Processo"][
        [COL_TRACKING, COL_REVISAO, COL_DATA, COL_STATUS]
    ].rename(columns={COL_DATA: COL_DATA_RETORNO, COL_STATUS: COL_STATUS_RETORNO})

    df_wide = pd.merge(df_base, df_envio, on=[COL_TRACKING, COL_REVISAO], how="left")
    df_wide = pd.merge(df_wide, df_retorno, on=[COL_TRACKING, COL_REVISAO], how="left")

    # Ordem canônica do ciclo de vida (família): 0AA<0AB<0A<0B<0<1A<1B<1<…
    df_wide["_sort"] = df_wide[COL_REVISAO].apply(normalizar_revisao)
    df_wide = df_wide.sort_values(by=[COL_TRACKING, "_sort"], kind="stable").drop(columns="_sort")

    df_wide[COL_SLA] = np.where(
        df_wide[COL_REVISAO].astype(str).str.strip().str.upper() == "0A",
        SLA_ITAIPU_REV_0A,
        SLA_ITAIPU_DEMAIS,
    )
    return df_wide.reset_index(drop=True)
