"""Dados do painel HTML da Unidade Geradora (spec: `.scratch/painel-ug-html/spec.md`).

O painel substitui o Power BI do Doc List Mapping. Quem diz QUAIS documentos entram é
o Doc List (as linhas de nível 2); o Aconex conta o passado de cada um. Toda regra
fica aqui, sobre as mesmas funções que atualizam a planilha: o HTML só filtra,
conta e desenha.

Para cada documento (um código conta uma vez, como no `DISTINCTCOUNT` do Power BI):

- o retrato de hoje: status real, consolidado, com quem está, 1ª emissão e as três
  situações (emissão, OTD, say-do), calculados como `doclist_update` calcula;
- a **linha do tempo**: o status real a cada dia em que o histórico mexeu (máquina do
  tempo, `snapshots.obter_snapshot_status`), só as mudanças. É dela que sai a
  evolução da carteira e o "o que mudou" do painel;
- o **histórico de revisões**, como no Histórico Consolidado: envio e retorno de cada
  revisão (`wide`), com Dias e Atraso da Itaipu e da CMI (`delays`), e o tipo do envio
  (1ª emissão, reemissão ou emissão final), que mede o esforço da engenharia.

As linhas da planilha (associações) ficam à parte: um código pode estar em mais de um
grupo ou sistema, e os filtros do painel olham para elas.
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

from .constants import COL_DATA, COL_REVISAO, COL_TRACKING, NAO_EMITIDO
from .delays import (
    COL_ATRASO_CMI,
    COL_ATRASO_ITAIPU,
    COL_DATA_PREVISTA_CTRL,
    COL_DIAS_CMI,
    COL_DIAS_ITAIPU,
    DelayPolicy,
    calcular_atrasos,
)
from .doclist import (
    LinhaDocList,
    calcular_dias_desvio_emissao,
    calcular_predecessores,
    classificar_situacao_emissao,
    classificar_situacao_say_do,
    e_backlog,
)
from .identity import AconexIndex
from .mapping import processar_documento
from .snapshots import obter_snapshot_status
from .wide import (
    COL_DATA_ENVIO,
    COL_DATA_RETORNO,
    COL_SLA,
    COL_STATUS_RETORNO,
    build_wide_table,
    gerar_dataset_dashboard,
)

ESCOPO_UG = "UG"
ESCOPO_18A = "18A"

TIPO_PRIMEIRA_EMISSAO = "1ª emissão"
TIPO_REEMISSAO = "Reemissão"
TIPO_EMISSAO_FINAL = "Emissão final"

_RE_18A = re.compile(r"18A\b", re.IGNORECASE)


def escopo_da_linha(sistema: str, codigo_grupo: str) -> str:
    """UG ou 18A. Os sistemas e os grupos da unidade 18A trazem '18A' no nome
    ('SDSC - UG 18A', 'eBOP - PRESS 18A FABR', 'MIG PLAN - 18A'); o resto é UG."""
    return ESCOPO_18A if _RE_18A.search(f"{sistema} {codigo_grupo}") else ESCOPO_UG


def chave_documento(cod_itaipu: str, cod_cmi: str) -> str:
    """Identidade do documento na planilha: o código Itaipu (o CMI, se faltar)."""
    return (str(cod_itaipu or "").strip() or str(cod_cmi or "").strip()).upper()


def tipo_de_envio(revisao: str, *, primeiro: bool) -> str:
    """O primeiro envio do documento é a 1ª emissão; revisão só com números (0, 1...)
    é a emissão final, para construção; o resto é reemissão depois de comentários ou
    reprovação."""
    if primeiro:
        return TIPO_PRIMEIRA_EMISSAO
    if str(revisao).strip().isdigit():
        return TIPO_EMISSAO_FINAL
    return TIPO_REEMISSAO


def _iso(d) -> str | None:
    # pd.NaT também é um `date`: o teste de vazio vem antes de qualquer conversão.
    if d is None or pd.isna(d):
        return None
    return pd.Timestamp(d).date().isoformat()


def _int(v) -> int | None:
    return None if v is None or pd.isna(v) else int(v)


def linha_do_tempo(df_tracking: pd.DataFrame) -> list[tuple[date, str]]:
    """Status real do documento em cada dia em que o histórico mexeu, só as mudanças.

    Antes do primeiro evento o documento não existe para a Itaipu (NÃO EMITIDO), e
    é dessa situação que a lista parte: um documento que nasce aprovado tem uma
    entrada só."""
    if df_tracking.empty:
        return []
    df = df_tracking.copy()
    df["Data_Obj"] = pd.to_datetime(df[COL_DATA], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["Data_Obj"])
    mudancas: list[tuple[date, str]] = []
    anterior = NAO_EMITIDO
    for dia in sorted(df["Data_Obj"].dt.normalize().unique()):
        corte = pd.Timestamp(dia) + pd.Timedelta(hours=23, minutes=59, seconds=59)
        _bruto, real, _rev, _data = obter_snapshot_status(df, corte)
        if real != anterior:
            mudancas.append((pd.Timestamp(dia).date(), real))
            anterior = real
    return mudancas


def _alinhar_com_o_status_de_hoje(tempo: list[tuple[date, str]], df_tracking: pd.DataFrame,
                                  status_real: str) -> list[tuple[date, str]]:
    """Faz a linha do tempo terminar no status real de hoje.

    O retrato de hoje sai da linha da verdade (a linha Current, KB §8.9); a máquina
    do tempo, da maior versão até a data. Em poucos documentos os dois discordam no
    último evento (na planilha real de 10/11/2026, 4 de 933), e o painel mostraria
    um número no retrato e outro na evolução. Vale o de hoje, no dia do último
    evento."""
    if df_tracking.empty or (tempo and tempo[-1][1] == status_real) or (not tempo and status_real == NAO_EMITIDO):
        return tempo
    datas = pd.to_datetime(df_tracking[COL_DATA], dayfirst=True, errors="coerce").dropna()
    if datas.empty:
        return tempo
    ultimo = datas.max().date()
    tempo = list(tempo)
    if tempo and tempo[-1][0] == ultimo:
        tempo.pop()
    if not tempo or tempo[-1][1] != status_real:
        tempo.append((ultimo, status_real))
    return tempo


def historico_de_revisoes(base: pd.DataFrame, data_ref: dict[str, date | None], *,
                          hoje: date) -> dict[str, list[dict]]:
    """Tracking → revisões, como no Histórico Consolidado (KB §24.11), só para os
    documentos pedidos (`data_ref` = data-alvo de cada Tracking, régua do atraso
    CMI da 1ª emissão).

    Cada revisão traz envio e retorno, o status do retorno, Dias e Atraso da Itaipu
    e da CMI e o tipo do envio."""
    if base.empty or not data_ref:
        return {}
    sub = base[base[COL_TRACKING].isin(set(data_ref))]
    wide = build_wide_table(gerar_dataset_dashboard(sub))
    if wide.empty:
        return {}
    wide[COL_DATA_PREVISTA_CTRL] = pd.to_datetime(wide[COL_TRACKING].map(data_ref), errors="coerce")
    wide = calcular_atrasos(wide, DelayPolicy(hoje=hoje))
    saida: dict[str, list[dict]] = {}
    for tracking, g in wide.groupby(COL_TRACKING, sort=False):
        revisoes = []
        primeiro_visto = False
        for _, r in g.iterrows():
            envio = r.get(COL_DATA_ENVIO)
            tem_envio = envio is not None and not pd.isna(envio)
            revisoes.append({
                "revisao": str(r.get(COL_REVISAO, "")).strip(),
                "tipo": tipo_de_envio(r.get(COL_REVISAO, ""), primeiro=not primeiro_visto) if tem_envio else None,
                "envio": _iso(envio) if tem_envio else None,
                "retorno": _iso(r.get(COL_DATA_RETORNO)),
                "status_retorno": None if pd.isna(r.get(COL_STATUS_RETORNO)) else str(r.get(COL_STATUS_RETORNO)),
                "dias_itaipu": _int(r.get(COL_DIAS_ITAIPU)),
                "atraso_itaipu": _int(r.get(COL_ATRASO_ITAIPU)),
                "dias_cmi": _int(r.get(COL_DIAS_CMI)),
                "atraso_cmi": _int(r.get(COL_ATRASO_CMI)),
                "sla": _int(r.get(COL_SLA)),
            })
            primeiro_visto = primeiro_visto or tem_envio
        saida[str(tracking)] = revisoes
    return saida


def montar_dados_painel(linhas: list[LinhaDocList], base: pd.DataFrame, *, hoje: date,
                        progresso=None) -> dict:
    """Tudo o que o painel mostra, pronto para virar JSON.

    `linhas` = as linhas do Doc List na ordem física (grupos e documentos); `base` =
    a extração do Aconex como sai de `carregar_base_aconex`. `progresso(f)` recebe a
    fração concluída (0 a 1)."""
    avancar = progresso or (lambda _f: None)
    predecessores = calcular_predecessores(linhas)
    idx = AconexIndex(base)

    grupos = []
    for ln in linhas:
        if ln.e_grupo:
            grupos.append({"codigo": ln.cod_itaipu, "grupo": ln.grupo, "sistema": ln.sistema,
                           "fase": ln.fase_projeto, "linha": ln.row,
                           "escopo": escopo_da_linha(ln.sistema, ln.cod_itaipu)})

    docs: list[dict] = []
    por_chave: dict[str, int] = {}
    associacoes = []
    primeira_linha: list[LinhaDocList] = []
    for ln in linhas:
        if ln.e_grupo:
            continue
        chave = chave_documento(ln.cod_itaipu, ln.cod_cmi)
        if not chave:
            continue
        if chave not in por_chave:
            por_chave[chave] = len(primeira_linha)
            primeira_linha.append(ln)
        grupo_codigo = predecessores.get(ln.row, "")
        associacoes.append({"doc": por_chave[chave], "grupo": ln.grupo, "sistema": ln.sistema,
                            "fase": ln.fase_projeto, "responsavel": ln.responsavel,
                            "escopo": escopo_da_linha(ln.sistema, grupo_codigo),
                            "codigo_grupo": grupo_codigo, "linha": ln.row})

    historicos: dict[int, pd.DataFrame] = {}
    data_ref: dict[str, date | None] = {}
    for i, ln in enumerate(primeira_linha):
        df_t = idx.localizar(ln.cod_itaipu, ln.cod_cmi)
        if not df_t.empty:
            historicos[i] = df_t
            data_ref[str(df_t[COL_TRACKING].iloc[0])] = ln.data_alvo
    revisoes = historico_de_revisoes(base, data_ref, hoje=hoje)
    avancar(0.15)

    total = max(len(primeira_linha), 1)
    for i, ln in enumerate(primeira_linha):
        df_t = historicos.get(i, pd.DataFrame())
        r = processar_documento(df_t, nivel="2", tag_etapa="", data_prevista=ln.data_alvo, hoje=hoje)
        e1 = r.data_primeira_emissao
        tracking = str(df_t[COL_TRACKING].iloc[0]) if not df_t.empty else ""
        tempo = _alinhar_com_o_status_de_hoje(linha_do_tempo(df_t), df_t, r.status_real)
        docs.append({
            "codigo": ln.cod_itaipu or ln.cod_cmi,
            "cmi": r.cod_cmi_atual or ln.cod_cmi,
            "codigo_atual": r.cod_itaipu_atual or "",
            "descricao": r.descricao_atual or ln.descricao,
            "prevista": _iso(ln.data_prevista),
            "reprogramada": _iso(ln.data_reprogramada),
            "alvo": _iso(ln.data_alvo),
            "primeira_emissao": _iso(e1),
            "ultima_emissao": _iso(pd.to_datetime(r.data_ultimo_status, dayfirst=True, errors="coerce"))
            if r.data_ultimo_status else None,
            "revisao": r.revisao or "",
            "status_real": r.status_real,
            "status_bruto": r.status_emissao or "",
            "consolidado": r.status_consolidado,
            "com": r.com_itaipu,
            "situacao_emissao": classificar_situacao_emissao(
                data_primeira_emissao=e1, data_alvo=ln.data_alvo,
                status_consolidado=r.status_consolidado, hoje=hoje),
            "situacao_otd": classificar_situacao_emissao(
                data_primeira_emissao=e1, data_alvo=ln.data_prevista,
                status_consolidado=r.status_consolidado, hoje=hoje),
            "situacao_say_do": classificar_situacao_say_do(
                data_prevista=ln.data_prevista, data_reprogramada=ln.data_reprogramada,
                data_primeira_emissao=e1, status_consolidado=r.status_consolidado, hoje=hoje),
            "backlog": e_backlog(data_prevista=ln.data_prevista, data_reprogramada=ln.data_reprogramada,
                                 data_primeira_emissao=e1),
            "desvio": calcular_dias_desvio_emissao(e1, ln.data_alvo),
            "no_aconex": not df_t.empty,
            "linha_do_tempo": [(d.isoformat(), s) for d, s in tempo],
            "revisoes": revisoes.get(tracking, []),
        })
        if i % 25 == 0:
            avancar(0.15 + 0.85 * i / total)
    avancar(1.0)

    ultimo_evento = pd.to_datetime(base[COL_DATA], dayfirst=True, errors="coerce").max() if not base.empty else None
    return {
        "hoje": hoje.isoformat(),
        "ultimo_evento_aconex": _iso(ultimo_evento),
        "documentos": docs,
        "associacoes": associacoes,
        "grupos": grupos,
    }
