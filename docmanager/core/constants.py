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
STATUS_ANULACAO_UPPER = ("CANCELADO", "ANULADO", "ISSUED FOR ANNULMENT")

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
KPI_STATUS_CANCELADO_UPPER = ("CANCELADO", "ANULADO", "ISSUED FOR ANNULMENT")

# ---------------------------------------------------------------------------
# Dataset do histórico consolidado / dashboard (legado: data_manager L941-948)
# ---------------------------------------------------------------------------
HIST_STATUS_VALIDOS = (
    "Anulado", "Aprovado", "Aprovado com Comentários", "Cancelado",
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
# Doc List Mapping (§27): o consolidado separa os três sabores de aprovação, em
# vez de fundir tudo em APROVADO como faz o Mapa dos Planos.
CONS_APROVADO_COM_COMENTARIOS = "APROVADO COM COMENTÁRIOS"
CONS_PARA_ASSINATURA = "PARA ASSINATURA"
CONS_NAO_APROVADO = "NÃO APROVADO"
CONS_EM_PROCESSO = "EM PROCESSO"
CONS_CANCELADO = "CANCELADO"
CONS_NAO_EMITIDO = "NÃO EMITIDO"
CONS_ERRO = "ERRO"  # sentinela intencional de combinação não mapeada (KB §21.4)

NAO_EMITIDO = "NÃO EMITIDO"
