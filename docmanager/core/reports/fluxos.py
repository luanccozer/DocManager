"""Fluxos em Andamento — onde cada documento está e com quem (KB §24.12).

Responde a pergunta que a base do register NUNCA respondeu: *este documento está
parado com quem, desde quando e vence quando?* A aba "Fluxos de Trabalho" do
Aconex mostra isso na tela; aqui vira relatório, ordenável por atraso e
agregável por responsável.

Funções PURAS (sem rede, sem I/O) sobre a base de fluxos que
`workflows_backend.extrair_workflows` produz.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from ..constants import (
    WF_COL_ATRIBUIDO,
    WF_COL_ETAPA_STATUS,
    WF_COL_ORG_ATRIBUIDA,
    WF_COL_ORG_PAREADA,
    WF_COL_RECEBIMENTO,
    WF_COL_STATUS,
    WF_COL_VENCIMENTO,
    WF_ETAPAS_EM_ABERTO,
    WF_SIT_ATRASADO,
    WF_SIT_NO_PRAZO,
    WF_SIT_SEM_PRAZO,
    WF_SIT_VENCE_HOJE,
    WF_STATUS_ANDAMENTO,
)
from ..normalize import celula_para_date

COLUNAS_DETALHE = [
    "Nº do Fluxo", "Nome do Fluxo", "No. do Documento", "Revisão", "Título",
    "Etapa", "Status da Etapa", "Atribuído a", "Organização Atribuída",
    "Qtd. Atribuídos", "Data de Recebimento", "Data de Vencimento",
    "Dias em Aberto", "Dias de Atraso", "Situação",
    "Iniciador", "Organização Iniciador", "Motivo da Emissão", "Tracking ID",
    # Pareada com `Atribuído a` — necessária ao resumo por pessoa e útil na
    # leitura de etapas mistas (quem é de qual organização).
    "Organizações (por atribuído)",
]

COLUNAS_RESUMO = ["Responsável", "Organização", "Fluxos", "Atrasados",
                  "% Atrasados", "Atraso Médio (dias)", "Atraso Máx. (dias)",
                  "Mais Antigo (dias em aberto)"]


def _dias(de: date | None, ate: date) -> str | int:
    return "" if de is None else (ate - de).days


def _situacao(venc: date | None, hoje: date) -> str:
    if venc is None:
        return WF_SIT_SEM_PRAZO
    if venc < hoje:
        return WF_SIT_ATRASADO
    return WF_SIT_VENCE_HOJE if venc == hoje else WF_SIT_NO_PRAZO


def analisar_fluxos_em_andamento(df_wf: pd.DataFrame, *, hoje: date | None = None) -> pd.DataFrame:
    """Uma linha por etapa EM ABERTO de fluxo em andamento — o "onde está agora".

    Filtra `Status do Fluxo == 'Em Andamento'` e `Status da Etapa` em
    {'Atual', 'Em Atraso'}: as etapas já concluídas são passado e as de
    'Previsão' ainda não começaram — nenhuma das duas responde "com quem está".

    `Dias em Aberto` conta do recebimento da etapa até hoje; `Dias de Atraso` só
    existe depois do vencimento (0 quando no prazo). NÃO se usa o `Dias em
    Atraso` que a API manda: ele é o atraso histórico daquela etapa e vem
    preenchido até em etapa concluída.
    """
    if df_wf.empty:
        return pd.DataFrame(columns=COLUNAS_DETALHE)
    hoje = hoje or date.today()
    falta = {WF_COL_STATUS, WF_COL_ETAPA_STATUS} - set(df_wf.columns)
    if falta:
        raise KeyError(f"Base de fluxos sem as colunas {sorted(falta)} — "
                       f"selecione o Excel de Fluxos (aba 'Fluxos'), não a base de documentos.")

    st = df_wf[WF_COL_STATUS].astype(str).str.strip()
    et = df_wf[WF_COL_ETAPA_STATUS].astype(str).str.strip()
    df = df_wf[(st == WF_STATUS_ANDAMENTO) & (et.isin(WF_ETAPAS_EM_ABERTO))].copy()
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_DETALHE)

    receb = df.get(WF_COL_RECEBIMENTO, pd.Series("", index=df.index)).map(celula_para_date)
    venc = df.get(WF_COL_VENCIMENTO, pd.Series("", index=df.index)).map(celula_para_date)
    df["Dias em Aberto"] = [_dias(d, hoje) for d in receb]
    df["Dias de Atraso"] = [0 if (v is None or v >= hoje) else (hoje - v).days for v in venc]
    df["Situação"] = [_situacao(v, hoje) for v in venc]

    for col in COLUNAS_DETALHE:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUNAS_DETALHE]
    # Mais atrasado primeiro; empate desempata por quem está esperando há mais tempo.
    return df.sort_values(
        by=["Dias de Atraso", "Dias em Aberto"], ascending=False,
        key=lambda s: pd.to_numeric(s, errors="coerce").fillna(-1),
    ).reset_index(drop=True)


def resumir_por_responsavel(df_detalhe: pd.DataFrame, *, por: str = "pessoa") -> pd.DataFrame:
    """Agrega o detalhe por responsável — a leitura "quem está segurando o quê".

    `por='pessoa'` EXPLODE a lista de atribuídos (uma etapa com 10 revisores
    conta 1 para cada um: a pergunta é "o que está na mão de fulano", e a soma da
    coluna passa do total de fluxos de propósito). `por='organizacao'` agrega
    pela organização, sem explodir pessoas.

    Cada pessoa entra com a organização DELA (coluna pareada), não com a lista de
    organizações da etapa — senão quem atua em etapas mistas se fragmenta em
    várias linhas. A chave é (nome, organização), não o UserId: no diretório
    real 58 nomes têm contas em organizações diferentes (ex.: 'BIANCA SANTOS'
    tem 1 conta no CMI e 2 na GE), e separá-los por organização é o desejado;
    contas homônimas DENTRO da mesma organização somam — quase sempre a mesma
    pessoa com duas contas, e pelo nome não há como distinguir mesmo.
    """
    if df_detalhe.empty:
        return pd.DataFrame(columns=COLUNAS_RESUMO)

    linhas = []
    for _, r in df_detalhe.iterrows():
        atraso = pd.to_numeric(r.get("Dias de Atraso"), errors="coerce")
        aberto = pd.to_numeric(r.get("Dias em Aberto"), errors="coerce")
        orgs = [o.strip() for o in str(r.get(WF_COL_ORG_ATRIBUIDA, "")).split(";") if o.strip()]
        if por == "organizacao":
            chaves = [(o, o) for o in orgs] or [("(sem atribuição)", "")]
        else:
            pessoas = [p.strip() for p in str(r.get(WF_COL_ATRIBUIDO, "")).split(";") if p.strip()]
            # A organização de CADA pessoa vem pareada (mesma ordem/cardinalidade).
            # Usar a lista de organizações da ETAPA aqui fragmentaria quem
            # participa de etapas mistas em várias linhas do resumo.
            pares = [o.strip() for o in str(r.get(WF_COL_ORG_PAREADA, "")).split(";")]
            chaves = [(nome, pares[i] if i < len(pares) and pares[i] else "; ".join(orgs))
                      for i, nome in enumerate(pessoas)]
            if not chaves:
                chaves = [("(sem atribuição)", "; ".join(orgs))]
        for nome, org in chaves:
            linhas.append({"Responsável": nome, "Organização": org,
                           "_atraso": 0 if pd.isna(atraso) else int(atraso),
                           "_aberto": 0 if pd.isna(aberto) else int(aberto)})

    d = pd.DataFrame(linhas)
    g = d.groupby(["Responsável", "Organização"], as_index=False).agg(
        Fluxos=("_atraso", "size"),
        Atrasados=("_atraso", lambda s: int((s > 0).sum())),
        **{"Atraso Médio (dias)": ("_atraso", lambda s: round(float(s[s > 0].mean()), 1) if (s > 0).any() else 0)},
        **{"Atraso Máx. (dias)": ("_atraso", "max")},
        **{"Mais Antigo (dias em aberto)": ("_aberto", "max")},
    )
    g["% Atrasados"] = (g["Atrasados"] / g["Fluxos"] * 100).round(1)
    return g[COLUNAS_RESUMO].sort_values(
        by=["Atrasados", "Fluxos"], ascending=False).reset_index(drop=True)
