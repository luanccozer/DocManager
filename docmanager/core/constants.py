"""Fonte ÚNICA das constantes de domínio (KB §5, §8.1, §19, §21.3).

Regras de comparação:
- Vereditos do motor de status real comparam em UPPER + strip (listas *_UPPER).
- O consolidado legado compara alguns status em case ORIGINAL (STATUS_EM_INTEGRACAO)
  — preservado para não mudar comportamento (KB §9).
"""
from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Marco temporal — mudança de fluxo no Aconex (KB §7, §21.3)
# Regime NOVO (workflow) ⇔ data >= 19/08/2024. Ponto ÚNICO da regra.
# ---------------------------------------------------------------------------
DATA_CORTE_FLUXO = pd.Timestamp("2024-08-19")


def is_regime_novo(data) -> bool:
    """True se a data pertence ao regime novo (fluxo/workflow), inclusive 19/08/2024."""
    return pd.Timestamp(data) >= DATA_CORTE_FLUXO


# ---------------------------------------------------------------------------
# SLAs canônicos (KB §19)
# ---------------------------------------------------------------------------
SLA_ITAIPU_REV_0A = 30      # análise da primeira emissão (0A)
SLA_ITAIPU_DEMAIS = 15      # análise das demais revisões
SLA_CMI_REEMISSAO = 15      # retrabalho/reemissão após veredito

# ---------------------------------------------------------------------------
# Vereditos e trâmite — documentos comuns (KB §8.1; legado: data_manager L146-152)
# ---------------------------------------------------------------------------
STATUS_APROVACAO_UPPER = ("APROVADO", "APROVADO COM COMENTÁRIOS", "PARA ASSINATURA")
STATUS_REPROVACAO_UPPER = ("NÃO APROVADO",)
STATUS_INFORMATIVO_UPPER = ("INFORMATIVO", "PARA INFORMAÇÃO")
# Anulação: o Aconex usa vários rótulos para a MESMA coisa ('VOID' é o do
# sistema em inglês). Todos são sinônimos e o motor os unifica em
# `STATUS_CANCELADO` no status real (decisão do usuário, 2026-07-28).
STATUS_ANULACAO_UPPER = ("CANCELADO", "ANULADO", "ISSUED FOR ANNULMENT", "VOID")
# Rótulo CANÔNICO do status real de um documento anulado — um só, para o
# dashboard não ter que conhecer os sinônimos do Aconex.
STATUS_CANCELADO = "Cancelado"

# Fantasmas de integração/internos — case ORIGINAL (legado: data_manager L23-26).
# O consolidado legado faz `status in STATUS_EM_INTEGRACAO` sem normalizar.
STATUS_EM_INTEGRACAO = (
    "Em Integração", "Integrado", "Não Integrado", "Em Validação", "Validado",
    "Não Validado", "Aceito", "Não Aceito", "01 Aceito", "03 Nao Aceito",
    "Para Aprovação", "Para Integraçao",
)
STATUS_EM_INTEGRACAO_UPPER = tuple(s.strip().upper() for s in STATUS_EM_INTEGRACAO)

# "Para Análise" é fantasma somente no regime novo (>= corte) — ver status_engine.
PARA_ANALISE_UPPER = ("PARA ANÁLISE", "PARA ANALISE")

# ---------------------------------------------------------------------------
# Sucesso/falha/cancelamento dos KPIs (legado: data_manager L1835-1837)
# Inclui variantes em inglês e 'Apto para Firma' — universo mais largo que o
# do motor de status real, de propósito.
# ---------------------------------------------------------------------------
KPI_STATUS_SUCESSO_UPPER = (
    "APROVADO", "APROVADO COM COMENTÁRIOS", "PARA ASSINATURA",
    "APPROVED", "APPROVED WITH COMMENTS", "INFORMATIVO", "PARA INFORMAÇÃO",
    "APTO PARA FIRMA",
)
KPI_STATUS_FALHA_UPPER = ("NÃO APROVADO",)
KPI_STATUS_CANCELADO_UPPER = ("CANCELADO", "ANULADO", "ISSUED FOR ANNULMENT", "VOID")

# ---------------------------------------------------------------------------
# Dataset do histórico consolidado / dashboard (legado: data_manager L941-948)
# ---------------------------------------------------------------------------
# Filtro de linhas do dataset (compara o Status BRUTO do Aconex) — por isso
# lista os sinônimos de anulação em vez do rótulo canônico.
HIST_STATUS_VALIDOS = (
    "Anulado", "Aprovado", "Aprovado com Comentários", "Cancelado", "VOID",
    "Em Processo", "Informativo", "Não Aprovado", "Para Análise",
    "Para Aprovação", "Para Assinatura", "Para Informação",
)
HIST_TIPOS_VALIDOS = ("Documento Técnico", "Management Document")

# ---------------------------------------------------------------------------
# Motor de modelos BIM (KB §16; legado: data_manager L30-54)
# ---------------------------------------------------------------------------
MOD_APROV_PRE = ("P0 - Modelo Aprovado", "P1 - Modelo Aprovado")
MOD_APROV_300 = ("S1 - LOD 300 - Sem Incidentes", "S1 - LOD 300 - Finalizado")
MOD_APROV_350 = ("S3 - LOD 350 - Aprovado", "S4 - LOD 350 - Aprovado")

MOD_REPROV_PRE = ("Não Aprovado", "P0 - Modelo Não Aprovado", "P1 - Modelo Não Aprovado")
MOD_REPROV_300 = ("S1 - LOD 300 - Com Incidentes",)
MOD_REPROV_350 = ("S3 - LOD 350 - Com Incidentes", "S3 - LOD 350 - Não Aprovado")

MOD_ANALISE_PRE = ("P0 - Validação do Modelo", "P1 - Validação do Modelo BIM", "Para Análise", "Para Aprovação")
MOD_ANALISE_300 = ("S1 - LOD 300 - Revisão de Modelo",)
MOD_ANALISE_350 = ("S3 - LOD 350 - Revisão de Modelo",)

MOD_INICIAL_PRE = ("Em Processo", "P0 - Emissão Inicial", "P1 - Emissão Inicial")
MOD_INICIAL_300 = ("S0 - Initial Status", "S0 - LOD 300 - Inicial")
MOD_INICIAL_350 = ("S2 - LOD 350 - Inicial",)

MOD_INFO = ("Para Informação",)

# ---------------------------------------------------------------------------
# Colunas canônicas da base Aconex (KB §5)
# ---------------------------------------------------------------------------
COL_DOC_ITAIPU = "No. do Documento"
COL_DOC_CMI = "Controle do Emissor"
COL_TRACKING = "Tracking ID"
COL_REVISAO = "Revisão"
COL_VERSAO = "Versão"
COL_STATUS = "Status"
COL_STATUS_REVISAO = "Status da Revisão"   # onde aparece 'Terminated'
COL_DATA = "Data de Alteração"
COL_CURRENT = "Current"
COL_TITULO = "Título"
COL_TIPO_DOC = "Tipo do Documento"

COLS_STRIP_CARGA = (
    COL_DOC_ITAIPU, COL_DOC_CMI, COL_TRACKING, COL_CURRENT,
    COL_STATUS_REVISAO, COL_REVISAO, COL_STATUS, COL_VERSAO,
)

# ---------------------------------------------------------------------------
# Planilha de Mapeamento — âncoras (KB §4). ATENÇÃO aos codepoints:
#   'N° ITAIPU' usa U+00B0 (SINAL DE GRAU);  'Nº CMI' usa U+00BA (ORDINAL).
# Trocar um pelo outro faz o find_headers falhar silenciosamente.
# ---------------------------------------------------------------------------
MAPA_ANCORA_ITAIPU = "N° ITAIPU"
MAPA_COL_CMI = "Nº CMI"

# ---------------------------------------------------------------------------
# Planilha Controle de Documentos (KB §13; cabeçalho na linha 4 → header=3)
# ---------------------------------------------------------------------------
CTRL_HEADER_ROW = 3  # base 0 do pandas
CTRL_COL_ITAIPU = "CODIFICAÇÃO ITAIPÚ (ACONEX)"
CTRL_COL_CMI = "NÚMERO INTERNO"
CTRL_COL_DATA_PREVISTA = "DATA PREVISTA DE EMISSÃO ACONEX"
# Nome exato a confirmar no Controle real; matching tolerante por 'contains'.
CTRL_COL_REPROGRAMACAO_HINT = "REPROGRAMA"

# ---------------------------------------------------------------------------
# Buckets do status consolidado (KB §9/§10)
# ---------------------------------------------------------------------------
CONS_APROVADO = "APROVADO"
CONS_APROVACAO_INTERMEDIARIA = "APROVAÇÃO INTERMEDIÁRIA"
CONS_NAO_APROVADO = "NÃO APROVADO"
CONS_EM_PROCESSO = "EM PROCESSO"
CONS_CANCELADO = "CANCELADO"
CONS_NAO_EMITIDO = "NÃO EMITIDO"
CONS_ERRO = "ERRO"  # sentinela intencional de combinação não mapeada (KB §21.4)

NAO_EMITIDO = "NÃO EMITIDO"

# ---------------------------------------------------------------------------
# Fluxos de Trabalho — Workflows API (KB §24.12)
# ---------------------------------------------------------------------------
# ATENÇÃO: a API devolve estes valores LOCALIZADOS EM PORTUGUÊS, e vários com
# espaço à direita ('Concluído '). O guia oficial documenta os rótulos em inglês
# ('In Progress', 'Completed') — que NÃO aparecem na resposta. Comparar sempre
# com estas constantes, após strip (feito na carga).
WF_STATUS_ANDAMENTO = "Em Andamento"
WF_STATUS_CONCLUIDO = "Concluído"
WF_STATUS_ENCERRADO = "Encerrado"

# Status da ETAPA. 'Atual' e 'Em Atraso' são as etapas EM ABERTO — é nelas que
# mora a resposta "com quem o documento está agora".
WF_ETAPA_ATUAL = "Atual"
WF_ETAPA_ATRASADA = "Em Atraso"
WF_ETAPAS_EM_ABERTO = (WF_ETAPA_ATUAL, WF_ETAPA_ATRASADA)
WF_ETAPA_PREVISAO = "Previsão"
WF_ETAPA_CONCLUIDA = "Concluído"
WF_ETAPA_ENCERRADA = "Encerrado"

# Colunas canônicas da base de fluxos (as de documento repetem os nomes da base
# do register de propósito — é o que permite juntar sem tradução).
WF_COL_NUMERO = "Nº do Fluxo"
WF_COL_STATUS = "Status do Fluxo"
WF_COL_ETAPA = "Etapa"
WF_COL_ETAPA_STATUS = "Status da Etapa"
WF_COL_ATRIBUIDO = "Atribuído a"
WF_COL_ORG_ATRIBUIDA = "Organização Atribuída"
WF_COL_RECEBIMENTO = "Data de Recebimento"
WF_COL_VENCIMENTO = "Data de Vencimento"

# Situação do prazo, no relatório de fluxos em andamento.
WF_SIT_ATRASADO = "Atrasado"
WF_SIT_VENCE_HOJE = "Vence hoje"
WF_SIT_NO_PRAZO = "No prazo"
WF_SIT_SEM_PRAZO = "Sem prazo"
# Organização de CADA atribuído, pareada 1-a-1 com `Atribuído a` (com repetição).
# `WF_COL_ORG_ATRIBUIDA` traz as DISTINTAS (leitura); esta traz o pareamento, sem
# o qual um revisor de etapas mistas se fragmenta no resumo por responsável.
WF_COL_ORG_PAREADA = "Organizações (por atribuído)"
