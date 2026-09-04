"""Identidade do documento: Tracking ID acima de tudo (KB §6).

Um documento pode trocar de código (Itaipu e/ou CMI) entre revisões; a única
chave imutável é o Tracking ID. Este módulo concentra:

- `AconexIndex` — busca em cascata ouro/prata/bronze com semântica IDÊNTICA a
  `DataManager.localiza_doc_historico` (legado L71-111), mas com dicionários
  O(1) em vez de varreduras booleanas da base inteira por documento. `resolver`
  devolve, além do histórico, COMO o documento foi achado (`Resolucao`).
- `construir_indice_reverso` — todos os códigos que cada documento já teve
  (normalizados) → Tracking ID. Usado no matching com o Controle de Documentos.
- `obter_codigos_historicos` — porta fiel do legado (L345-368).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .constants import COL_CURRENT, COL_DATA, COL_DOC_CMI, COL_DOC_ITAIPU, COL_TRACKING
from .normalize import normalizar_codigo


@dataclass(frozen=True)
class Resolucao:
    """Resultado da cascata: o histórico eleito MAIS como se chegou nele.

    - `df` — histórico completo do Tracking eleito (vazio ⇒ não encontrado).
    - `via` ∈ {'', 'par', 'itaipu', 'cmi'} — qual código resolveu o documento.
    - `vigente` — o código casou com a identidade ATUAL do documento (linha
      `Current`); `False` ⇒ casou só com uma revisão antiga (código trocado).
    - `candidatos` — Tracking IDs que o match considerou ANTES do desempate por
      data. Mais de um ⇒ o código é compartilhado e a eleição foi um chute
      informado: quem consome deve sinalizar (`ambiguo`).
    """

    df: pd.DataFrame
    via: str
    vigente: bool
    candidatos: tuple

    @property
    def ambiguo(self) -> bool:
        return len(self.candidatos) > 1


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
        # Camadas "vigentes": só as linhas cujo código é o código ATUAL do
        # Tracking (o da linha `Current`). Ver `localizar(preferir_vigente=)`.
        self._rows_par_vig: dict[tuple, list] = {}
        self._rows_cmi_vig: dict[str, list] = {}
        self._rows_doc_vig: dict[str, list] = {}
        self._codigos_norm: set | None = None   # preguiçoso (só quem usa paga)

        docs = df_aconex[COL_DOC_ITAIPU].astype(str) if COL_DOC_ITAIPU in df_aconex.columns else None
        cmis = df_aconex[COL_DOC_CMI].astype(str) if COL_DOC_CMI in df_aconex.columns else None
        tids = df_aconex[COL_TRACKING].astype(str) if COL_TRACKING in df_aconex.columns else None
        vig_doc, vig_cmi = self._codigos_vigentes(df_aconex, docs, cmis, tids)
        for pos in range(len(df_aconex)):
            doc = docs.iat[pos] if docs is not None else ""
            cmi = cmis.iat[pos] if cmis is not None else ""
            tid = tids.iat[pos] if tids is not None else ""
            # Tracking sem linha `Current` (base incompleta) → nada a comparar:
            # todas as suas linhas contam como vigentes, para não perder matches.
            vd, vc = vig_doc.get(tid), vig_cmi.get(tid)
            ok_doc, ok_cmi = vd is None or doc in vd, vc is None or cmi in vc
            if doc and cmi:
                self._rows_par.setdefault((doc, cmi), []).append(pos)
                if ok_doc and ok_cmi:
                    self._rows_par_vig.setdefault((doc, cmi), []).append(pos)
            if cmi:
                self._rows_cmi.setdefault(cmi, []).append(pos)
                if ok_cmi:
                    self._rows_cmi_vig.setdefault(cmi, []).append(pos)
            if doc:
                self._rows_doc.setdefault(doc, []).append(pos)
                if ok_doc:
                    self._rows_doc_vig.setdefault(doc, []).append(pos)
            self._pos_tracking.setdefault(tid, []).append(pos)

    @staticmethod
    def _codigos_vigentes(df_aconex, docs, cmis, tids) -> tuple[dict, dict]:
        """{Tracking → códigos da(s) linha(s) `Current`}, por Itaipu e por CMI."""
        vig_doc: dict[str, set] = {}
        vig_cmi: dict[str, set] = {}
        if tids is None or COL_CURRENT not in df_aconex.columns:
            return vig_doc, vig_cmi
        cur = df_aconex[COL_CURRENT].astype(str).str.strip().str.lower() == "true"
        for pos in cur.to_numpy().nonzero()[0]:
            tid = tids.iat[pos]
            if docs is not None:
                vig_doc.setdefault(tid, set()).add(docs.iat[pos])
            if cmis is not None:
                vig_cmi.setdefault(tid, set()).add(cmis.iat[pos])
        return vig_doc, vig_cmi

    # ------------------------------------------------------------------
    def conhece_codigo(self, codigo) -> bool:
        """True se o código (normalizado) aparece em QUALQUER linha da base —
        de qualquer documento, de qualquer época.

        Distingue "esse código é de OUTRO documento" (erro de digitação/troca na
        lista) de "esse código não existe no Aconex" (documento provavelmente
        ainda não emitido/registrado) — ver `_classificar_codigo_busca`.
        """
        if self._codigos_norm is None:
            cods: set[str] = set()
            for col in (COL_DOC_ITAIPU, COL_DOC_CMI):
                if col in self._df.columns:
                    cods.update(normalizar_codigo(c) for c in self._df[col].astype(str).unique())
            cods.discard("")
            self._codigos_norm = cods
        c = normalizar_codigo(codigo)
        return bool(c) and c in self._codigos_norm

    # ------------------------------------------------------------------
    def historico(self, tracking_id) -> pd.DataFrame:
        """Histórico completo do Tracking ID (ordem original da base), como cópia."""
        pos = self._pos_tracking.get(str(tracking_id), [])
        if not pos:
            return pd.DataFrame(columns=self._df.columns)
        return self._df.iloc[pos].copy()

    # ------------------------------------------------------------------
    def localizar(self, codigo_itaipu, codigo_cmi, *, preferir_itaipu: bool = False,
                  preferir_vigente: bool = False) -> pd.DataFrame:
        """Histórico do Tracking eleito pela cascata — ver `resolver`."""
        return self.resolver(codigo_itaipu, codigo_cmi, preferir_itaipu=preferir_itaipu,
                             preferir_vigente=preferir_vigente).df

    # ------------------------------------------------------------------
    def resolver(self, codigo_itaipu, codigo_cmi, *, preferir_itaipu: bool = False,
                 preferir_vigente: bool = False) -> Resolucao:
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

        `preferir_vigente=True` insere uma camada ANTES do passo 4: o código só
        casa, de início, com quem o usa HOJE (linha `Current`); as ocorrências
        históricas viram último recurso. Sem isso, um código compartilhado entre
        documentos (o CMI renumera e reaproveita) pode eleger, pelo desempate de
        data, justamente o documento que JÁ ABANDONOU aquele código — "match
        fantasma": o mais recente a mexer no código não é o dono dele. Foi o que
        levou `08934100BUA20-FS00FE-02` ao workstatement errado (2026-09-04). O
        último recurso preserva o recurso do "código atualizado (azul)": quem
        busca pelo código ANTIGO de um documento renomeado continua achando-o.
        """
        it = str(codigo_itaipu).strip() if codigo_itaipu else ""
        cmi = str(codigo_cmi).strip() if codigo_cmi else ""

        par = (self._rows_par, self._rows_par_vig, (it, cmi), "par")
        doc = (self._rows_doc, self._rows_doc_vig, it, "itaipu")
        cm = (self._rows_cmi, self._rows_cmi_vig, cmi, "cmi")
        # Passos 2 e 3, na ordem escolhida (CMI-primeiro é o padrão do legado).
        secundarios = [doc, cm] if preferir_itaipu else [cm, doc]

        ordem: list[tuple] = []
        if len(it) > 3 and len(cmi) > 3:
            ordem += [(par, True), (par, False)] if preferir_vigente else [(par, False)]
        if preferir_vigente:
            ordem += [(s, True) for s in secundarios]
        ordem += [(s, False) for s in secundarios]

        for (tabela, tabela_vig, chave, via), so_vigentes in ordem:
            if via != "par" and len(chave) <= 3:
                continue
            pos = (tabela_vig if so_vigentes else tabela).get(chave)
            if pos:
                return self._eleger(pos, via, chave in tabela_vig)
        return Resolucao(pd.DataFrame(), "", False, ())

    # ------------------------------------------------------------------
    def _eleger(self, pos: list, via: str, vigente: bool) -> Resolucao:
        """Desempate por Data de Alteração entre as linhas do match (passos 4 e 5)."""
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
            return Resolucao(self.historico(tracking_eleito), via, vigente, tuple(unique_ids))
        return Resolucao(pd.DataFrame(), "", False, ())


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
