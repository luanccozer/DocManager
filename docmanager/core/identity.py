"""Identidade do documento: Tracking ID acima de tudo (KB §6).

Um documento pode trocar de código (Itaipu e/ou CMI) entre revisões; a única
chave imutável é o Tracking ID. Este módulo concentra:

- `AconexIndex` — busca em cascata ouro/prata/bronze com semântica IDÊNTICA a
  `DataManager.localiza_doc_historico` (legado L71-111), mas com dicionários
  O(1) em vez de varreduras booleanas da base inteira por documento.
- `construir_indice_reverso` — todos os códigos que cada documento já teve
  (normalizados) → Tracking ID. Usado no matching com o Controle de Documentos.
- `obter_codigos_historicos` — porta fiel do legado (L345-368).
"""
from __future__ import annotations

import pandas as pd

from .constants import COL_DATA, COL_DOC_CMI, COL_DOC_ITAIPU, COL_TRACKING
from .normalize import normalizar_codigo


def obter_codigos_historicos(df_tracking: pd.DataFrame) -> list:
    """Todos os códigos (Itaipu + CMI) únicos que o documento já possuiu."""
    codigos_unicos = set()
    if not df_tracking.empty:
        if COL_DOC_ITAIPU in df_tracking.columns:
            codigos_unicos.update(
                df_tracking[COL_DOC_ITAIPU].dropna().astype(str).str.strip().tolist()
            )
        if COL_DOC_CMI in df_tracking.columns:
            codigos_unicos.update(
                df_tracking[COL_DOC_CMI].dropna().astype(str).str.strip().tolist()
            )
    codigos_unicos.discard("")
    codigos_unicos.discard("nan")
    codigos_unicos.discard("None")
    return list(codigos_unicos)


class AconexIndex:
    """Índice da base Aconex completa (como sai de `carregar_aconex`: dtype str,
    fillna(''), strip nas colunas-chave).

    O matching da cascata é EXATO e case-sensitive, como no legado — a
    normalização agressiva (upper/'.0') existe só no índice reverso, que é
    recurso novo. Não normalizar às cegas aqui: mudaria eleições de Tracking.
    """

    def __init__(self, df_aconex: pd.DataFrame):
        self._df = df_aconex
        self._rows_par: dict[tuple, list] = {}
        self._rows_cmi: dict[str, list] = {}
        self._rows_doc: dict[str, list] = {}
        self._pos_tracking: dict[str, list] = {}

        docs = df_aconex[COL_DOC_ITAIPU].astype(str) if COL_DOC_ITAIPU in df_aconex.columns else None
        cmis = df_aconex[COL_DOC_CMI].astype(str) if COL_DOC_CMI in df_aconex.columns else None
        tids = df_aconex[COL_TRACKING].astype(str) if COL_TRACKING in df_aconex.columns else None
        for pos in range(len(df_aconex)):
            doc = docs.iat[pos] if docs is not None else ""
            cmi = cmis.iat[pos] if cmis is not None else ""
            tid = tids.iat[pos] if tids is not None else ""
            if doc and cmi:
                self._rows_par.setdefault((doc, cmi), []).append(pos)
            if cmi:
                self._rows_cmi.setdefault(cmi, []).append(pos)
            if doc:
                self._rows_doc.setdefault(doc, []).append(pos)
            self._pos_tracking.setdefault(tid, []).append(pos)

    # ------------------------------------------------------------------
    def historico(self, tracking_id) -> pd.DataFrame:
        """Histórico completo do Tracking ID (ordem original da base), como cópia."""
        pos = self._pos_tracking.get(str(tracking_id), [])
        if not pos:
            return pd.DataFrame(columns=self._df.columns)
        return self._df.iloc[pos].copy()

    # ------------------------------------------------------------------
    def localizar(self, codigo_itaipu, codigo_cmi, *, preferir_itaipu: bool = False) -> pd.DataFrame:
        """Cascata ouro/prata/bronze + desempate por data (legado L71-111).

        1. Ouro: match exato simultâneo Itaipu+CMI (ambos com len > 3).
        2/3. Prata → Bronze: só CMI (mais estável), depois só Itaipu — a ordem do
           legado, usada por Histórico/Mapa/Doc List. Com `preferir_itaipu=True`
           a ordem INVERTE para Itaipu → CMI: é o que o Status Documentos (leitura
           via Excel) usa, porque o Itaipu é a âncora de local/sistema/tipo e um
           CMI (número interno) errado na lista deve ser sinalizado por
           cor/comentário, não guiar a busca ao documento errado (pedido do usuário).
        4. Múltiplos Tracking IDs → desempate pela Data de Alteração mais
           recente ENTRE AS LINHAS DO MATCH (NaT por último).
        5. Retorna o histórico COMPLETO do Tracking eleito.
        """
        it = str(codigo_itaipu).strip() if codigo_itaipu else ""
        cmi = str(codigo_cmi).strip() if codigo_cmi else ""

        pos: list = []
        if len(it) > 3 and len(cmi) > 3:
            pos = self._rows_par.get((it, cmi), [])
        # Passos 2 e 3, na ordem escolhida (CMI-primeiro é o padrão do legado).
        secundarios = ((self._rows_doc, it), (self._rows_cmi, cmi)) if preferir_itaipu \
            else ((self._rows_cmi, cmi), (self._rows_doc, it))
        for tabela, chave in secundarios:
            if not pos and len(chave) > 3:
                pos = tabela.get(chave, [])
        if not pos:
            return pd.DataFrame()

        matches = self._df.iloc[pos]
        unique_ids = matches[COL_TRACKING].unique()
        if len(unique_ids) == 1:
            tracking_eleito = unique_ids[0]
        else:
            try:
                candidatos = matches.copy()
                candidatos["Data_Obj"] = pd.to_datetime(
                    candidatos[COL_DATA], dayfirst=True, errors="coerce"
                )
                candidatos = candidatos.sort_values(by="Data_Obj", ascending=False, na_position="last")
                tracking_eleito = candidatos.iloc[0][COL_TRACKING]
            except Exception:
                tracking_eleito = unique_ids[0]

        if tracking_eleito:
            return self.historico(tracking_eleito)
        return pd.DataFrame()


def construir_indice_reverso(df_aconex: pd.DataFrame) -> dict:
    """{código normalizado (Itaipu OU CMI, qualquer época) → Tracking ID}.

    Recurso NOVO (matching Controle de Documentos ↔ base Aconex). Construído
    sobre a BASE BRUTA COMPLETA — nunca sobre um dataset filtrado, para que
    "não está no índice" signifique "nunca existiu no Aconex".
    Colisão (mesmo código em Trackings diferentes): vence o de Data de
    Alteração mais recente, coerente com o desempate da cascata.
    """
    if df_aconex.empty:
        return {}
    datas = pd.to_datetime(df_aconex[COL_DATA], dayfirst=True, errors="coerce")
    melhor: dict[str, tuple] = {}
    docs = df_aconex[COL_DOC_ITAIPU].astype(str)
    cmis = df_aconex[COL_DOC_CMI].astype(str)
    tids = df_aconex[COL_TRACKING].astype(str)
    for pos in range(len(df_aconex)):
        tid = tids.iat[pos].strip()
        if not tid:
            continue
        data = datas.iat[pos]
        for cod in (normalizar_codigo(docs.iat[pos]), normalizar_codigo(cmis.iat[pos])):
            if not cod:
                continue
            atual = melhor.get(cod)
            if atual is None:
                melhor[cod] = (data, tid)
            elif pd.notna(data) and (pd.isna(atual[0]) or data > atual[0]):
                melhor[cod] = (data, tid)
    return {cod: tid for cod, (_, tid) in melhor.items()}
