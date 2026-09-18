"""Linha da verdade ÚNICA (KB §3-Terminated, §8.9, §21.2, §21.8).

Substitui as 4 implementações divergentes do legado:
  1. MappingView.iniciar_atualizacao  (aconex_reviewer L587-632)
  2. StatusCheckView.iniciar_processo  (idem)
  3. DataManager.obter_snapshot_status  (Delta, data_manager L588-617)
  4. limiar de versão dos KPIs           (data_manager L1816-1823)

REGRA CANÔNICA (limiar de versão por revisão): o Terminated invalida apenas
as versões daquela revisão ATÉ a versão terminada. Sobrevive `Versão >
maior versão Terminated da revisão` - o que permite o "renascimento" de uma
revisão reenviada com versão maior. Esta é a única regra; o legado (exceto
KPIs) descartava a revisão terminada inteira, matando o renascimento
(divergência sancionada §21.8).

Passar `legado_exclui_revisao=True` reproduz o comportamento antigo (usado só
pelo harness de regressão).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .constants import COL_CURRENT, COL_REVISAO, COL_STATUS_REVISAO, COL_VERSAO
from .normalize import REV_LIMITE_0A, normalizar_revisao


@dataclass
class TruthLine:
    """Resultado da resolução da linha da verdade.

    - `linha_dinamica`: a linha que alimenta as colunas visuais (Revisão /
      Data Última Emissão / Status). `None` ⇒ NÃO EMITIDO (colunas limpas).
    - `df_para_calculo`: base já tratada que vai ao motor de status real.
      VAZIA ⇒ NÃO EMITIDO. Invariante: `linha_dinamica is None` ⟺ base vazia.
    - `revisao_atual`: revisão da linha dinâmica ('' quando None).
    """

    linha_dinamica: pd.Series | None
    df_para_calculo: pd.DataFrame
    revisao_atual: str

    @property
    def nao_emitido(self) -> bool:
        return self.linha_dinamica is None or self.df_para_calculo.empty


def _com_versao_int(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Versão_Int"] = pd.to_numeric(df[COL_VERSAO], errors="coerce").fillna(0)
    return df


def _rev_key(serie: pd.Series) -> pd.Series:
    return serie.astype(str).str.strip().str.upper()


def limpar_terminated_por_limiar(df: pd.DataFrame) -> pd.DataFrame:
    """Remove as versões mortas por um Terminated na MESMA revisão.

    Para cada revisão, calcula a maior versão Terminated; sobrevivem apenas as
    linhas com `Versão_Int` estritamente maior. Revisões sem Terminated
    mantêm tudo (limiar -1). Idempotente. Preserva colunas originais + Versão_Int.
    Porta fiel de data_manager L1816-1823, generalizada.
    """
    if df.empty:
        return df.copy()
    df = _com_versao_int(df)
    rev_key = _rev_key(df[COL_REVISAO])
    mask_term = df[COL_STATUS_REVISAO].astype(str).str.lower().str.contains("terminated", na=False)
    if mask_term.any():
        max_term = df.loc[mask_term].groupby(rev_key[mask_term])["Versão_Int"].max()
        limite = rev_key.map(max_term).fillna(-1)
        df = df[df["Versão_Int"] > limite]
    return df


def _linha_maior_versao(df: pd.DataFrame) -> pd.Series:
    """Linha de maior Versão_Int (desempate por Versão textual desc), como legado."""
    return df.sort_values(by=["Versão_Int", COL_VERSAO], ascending=False).iloc[0]


def resolver_linha_da_verdade(
    df_tracking: pd.DataFrame,
    *,
    legado_exclui_revisao: bool = False,
) -> TruthLine:
    """Resolve a linha dinâmica e a base de cálculo a partir do histórico completo.

    Fluxo (KB §8.9, unificado no limiar §21.8):
      1. Current existe e NÃO é Terminated → linha = Current; base = histórico
         com limiar aplicado (limpa outras revisões terminadas).
      2. Current é Terminated e a revisão renasceu (sobreviveu ao limiar) →
         linha = maior versão sobrevivente da revisão; base = limpa.
      3. Current é Terminated sem renascimento, revisão ≤ 0A → NÃO EMITIDO.
      4. Current é Terminated sem renascimento, revisão > 0A → linha = maior
         versão do restante limpo.
      5. Sem Current no histórico → linha = maior versão do histórico limpo.
    """
    vazio = df_tracking.iloc[0:0].copy() if len(df_tracking.columns) else df_tracking.copy()
    if df_tracking.empty:
        return TruthLine(None, vazio, "")

    df = _com_versao_int(df_tracking)
    current_rows = df[df[COL_CURRENT].astype(str).str.lower() == "true"]
    cand_current = current_rows.iloc[0] if not current_rows.empty else None

    # --- Sem Current: fallback pela maior versão do histórico limpo ---
    if cand_current is None:
        df_calc = limpar_terminated_por_limiar(df)
        if df_calc.empty:
            return TruthLine(None, vazio, "")
        linha = _linha_maior_versao(df_calc)
        return TruthLine(linha, df_calc, str(linha.get(COL_REVISAO, "")).strip())

    rev_current = str(cand_current.get(COL_REVISAO, "")).strip()
    current_terminated = "terminated" in str(cand_current.get(COL_STATUS_REVISAO, "")).lower()

    # --- Caso 1: Current vivo → é a linha dinâmica; base limpa ---
    if not current_terminated:
        df_calc = limpar_terminated_por_limiar(df)
        return TruthLine(cand_current, df_calc, rev_current)

    # --- Current é Terminated ---
    rev_norm = normalizar_revisao(rev_current)

    if legado_exclui_revisao:
        # Comportamento antigo: descarta a revisão terminada inteira (sem renascimento).
        if rev_norm <= REV_LIMITE_0A:
            return TruthLine(None, vazio, rev_current)
        restante = df[_rev_key(df[COL_REVISAO]) != rev_current.upper()]
        if restante.empty:
            return TruthLine(None, vazio, rev_current)
        linha = _linha_maior_versao(restante)
        return TruthLine(linha, restante, str(linha.get(COL_REVISAO, "")).strip())

    # Novo: limiar de versão (renascimento).
    df_calc = limpar_terminated_por_limiar(df)
    surv_rev = df_calc[_rev_key(df_calc[COL_REVISAO]) == rev_current.upper()]
    if not surv_rev.empty:
        # Caso 2: a revisão renasceu (reenvio com versão maior).
        linha = _linha_maior_versao(surv_rev)
        return TruthLine(linha, df_calc, rev_current)

    # Revisão terminada sem renascimento.
    if rev_norm <= REV_LIMITE_0A:
        # Caso 3: cancelou a primeira emissão da vida útil → NÃO EMITIDO.
        return TruthLine(None, vazio, rev_current)
    if df_calc.empty:
        return TruthLine(None, vazio, rev_current)
    # Caso 4: a revisão sai do jogo; vigente = maior versão do que sobrou.
    linha = _linha_maior_versao(df_calc)
    return TruthLine(linha, df_calc, str(linha.get(COL_REVISAO, "")).strip())
