"""Extração das Questões do módulo Campo (Field) do Aconex - as "pendências de
comissionamento" (KB §32).

Espelha `workflows_backend` (mesma sessão, mesmo token, mesma retentativa),
mas ataca OUTRO serviço, com outras regras - todas medidas ao vivo em 11/2026:

- a base é `/field-management/api/projects/{id}`, não o `/api/projects/...`
  do register;
- a resposta é JSON (`Accept: application/json`); a V2 só acrescenta
  `permissions`, que não serve aqui;
- no máximo 5 req/s e 10 simultâneas POR ORGANIZAÇÃO (todas as integrações da
  CMI dividem a cota): pausa de 250 ms entre chamadas, uma por vez;
- as questões se pedem a partir da área RAIZ (`include_child_areas`,
  `include_shared`), 200 por página no máximo;
- o bloco `conversations` da listagem vem com `comments: []` mesmo quando há
  comentários: o texto de Comments sai de `/issues/{id}/conversations/all`, e
  só com `supportPublicConversation=true` vêm os "With Everyone";
- campo customizado se casa pelo `family_id` antes do `id` (o `id` muda a cada
  versão da definição do campo).

Só GET. Tudo ou nada: falha definitiva levanta `ErroField`, e quem chama não
grava nada.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from . import aconex_backend as ab

ACCEPT_FIELD = "application/json"
PAGE_SIZE_QUESTOES = 200
PAUSA_ENTRE_CHAMADAS_S = 0.25      # no máximo 4 chamadas por segundo, somando todas
CONVERSAS_EM_PARALELO = 4          # a cota é 10 simultâneas por organização


class ErroField(RuntimeError):
    """A extração das questões não terminou; nada deve ser gravado."""


@dataclass
class ExtracaoQuestoes:
    questoes: list[dict]
    definicoes: list[dict]                  # /customfields
    tipos: list[dict]                       # /issue_types
    comentarios_por_issue: dict[str, list[dict]] = field(default_factory=dict)  # conversas cruas


def _base(config) -> str:
    return f"{config.instance}/field-management/api/projects/{config.project_id}"


class _Cliente:
    """Uma sessão autenticada, uma chamada por vez, com a pausa da cota."""

    def __init__(self, config, log_cb):
        self.config, self.log = config, log_cb
        self.session, token = ab._estabelecer_sessao(config, log_cb)
        self.headers = {"Authorization": f"Bearer {token}", "Accept": ACCEPT_FIELD,
                        "Accept-Encoding": "gzip, deflate"}
        self.chamadas = 0
        self._trava = threading.Lock()
        self._proxima = 0.0

    def _esperar_a_vez(self) -> None:
        """Espaça o INÍCIO das chamadas em `PAUSA_ENTRE_CHAMADAS_S`, venham de uma
        thread ou de várias: é o que mantém a cota de chamadas por segundo."""
        with self._trava:
            agora = time.monotonic()
            espera = self._proxima - agora
            self._proxima = max(agora, self._proxima) + PAUSA_ENTRE_CHAMADAS_S
            self.chamadas += 1
        if espera > 0:
            time.sleep(espera)

    def get(self, rota: str, params: dict | None = None) -> dict:
        self._esperar_a_vez()

        def interpretar(r):
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError as e:
                    raise ab.FalhaRetentavel(f"resposta inválida em {rota}: {e}") from e
            raise ab.FalhaRetentavel(f"HTTP {r.status_code} em {rota}")

        url = f"{_base(self.config)}/{rota}"
        dados, erro, self.session = ab._get_resiliente(
            self.session, self.config, url, self.headers, dict(params or {}), self.log, interpretar)
        if erro:
            raise ErroField(f"o Aconex não respondeu a {rota} após "
                            f"{ab.TENTATIVAS_POR_PAGINA} tentativas ({erro})")
        return dados or {}

    def fechar(self):
        try:
            self.session.close()
        except Exception:  # noqa: BLE001
            pass


def extrair_questoes(config, *, log_cb=print, progress_cb=None,
                     com_comentarios: bool = True) -> ExtracaoQuestoes:
    """Todas as questões do projeto, com as definições dos campos e, se pedido,
    as conversas de cada uma (uma chamada por questão - só peça se a planilha
    tiver a coluna Comments)."""
    progresso = progress_cb or (lambda _f: None)
    cliente = _Cliente(config, log_cb)
    try:
        log_cb(f"Buscando as questões do Campo no projeto {config.project_id}...")
        raizes = [a for a in (cliente.get("areas").get("areas") or []) if a.get("id")]
        if not raizes:
            raise ErroField("o Aconex não devolveu nenhuma área do Campo neste projeto")
        definicoes = cliente.get("customfields").get("custom_fields") or []
        tipos = cliente.get("issue_types").get("issue_types") or []
        progresso(0.05)

        questoes: list[dict] = []
        vistas: set[str] = set()
        for raiz in raizes:
            pagina = 1
            while True:
                dados = cliente.get(f"areas/{raiz['id']}/issues", {
                    "include_child_areas": "true", "include_shared": "true",
                    "page_size": PAGE_SIZE_QUESTOES, "page_number": pagina,
                    "sort_by": "issue_number", "sort_order": "desc"})
                for q in dados.get("issues") or []:
                    chave = str(q.get("issue_id") or "")
                    if chave and chave not in vistas:
                        vistas.add(chave)
                        questoes.append(q)
                total_paginas = int(dados.get("total_pages") or 0)
                if pagina >= total_paginas or not dados.get("issues"):
                    break
                pagina += 1
        log_cb(f"{len(questoes)} questões encontradas.")
        progresso(0.15)

        comentarios: dict[str, list[dict]] = {}
        if com_comentarios and questoes:
            comentarios = _baixar_conversas(cliente, questoes, log_cb, progresso)
        progresso(0.9)
        return ExtracaoQuestoes(questoes, definicoes, tipos, comentarios)
    finally:
        cliente.fechar()


def _baixar_conversas(cliente: _Cliente, questoes: list[dict], log_cb, progresso) -> dict[str, list[dict]]:
    """As conversas de cada questão, várias ao mesmo tempo (uma chamada por questão
    era ~85 s para 150 questões; em paralelo, ~40 s). A cota continua respeitada
    pelo `_esperar_a_vez`. Uma falha definitiva cancela o resto e sobe (tudo ou nada)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def uma(q):
        dados = cliente.get(f"issues/{q['issue_id']}/conversations/all",
                            {"supportPublicConversation": "true"})
        return str(q["issue_id"]), list((dados.get("_embedded") or {}).get("conversations") or [])

    resultado: dict[str, list[dict]] = {}
    total = len(questoes)
    with ThreadPoolExecutor(max_workers=CONVERSAS_EM_PARALELO) as pool:
        futuros = [pool.submit(uma, q) for q in questoes]
        try:
            for i, futuro in enumerate(as_completed(futuros), 1):
                chave, conversas = futuro.result()
                resultado[chave] = conversas
                progresso(0.15 + 0.75 * i / total)
                if i % 25 == 0 or i == total:
                    log_cb(f"Comentários: {i}/{total}")
        except BaseException:
            for f in futuros:
                f.cancel()
            raise
    return resultado


# --- Questão → colunas da exportação (validado: 4.263/4.263 células) ---------

FUSO_LOCAL = timezone(timedelta(hours=-3))   # Brasil/Paraguai, sem horário de verão
STATUS_ROTULO = {"Open": "Open", "InDispute": "In dispute",
                 "ReadyToInspect": "Ready to inspect",   # rótulo NÃO verificado
                 "WorkDone": "Work Done", "Closed": "Closed"}
BOOLEANO_ROTULO = {"Yes": "Sim", "No": "Não"}
TIPOS_VERIFICADOS = {"single_select", "single_line_text", "multi_line_text", "date", "boolean"}
PARTICIPANTE_PUBLICO = "-1"   # "Everyone"
_DIAS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MESES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# As colunas da exportação que não são campo customizado (seção 7 da spec).
COLUNAS_PADRAO = (
    "Issue Number", "Issue Type", "Area", "Location Detail", "Issue Description",
    "Captured On", "Captured by", "Status", "Due Date", "Assigned On", "Assigned to",
    "Assigned By", "Closed On", "Closed By User", "Closed By Organization", "Listed In",
    "Comments",
)
# Sem fonte validada: se a planilha as tiver, as células existentes não são tocadas.
COLUNAS_SEM_FONTE = ("Pinned To DocNumber", "Doc Title", "Source")


def _instante(iso) -> datetime:
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))


def _data(iso, *, converter_fuso: bool = True) -> str:
    """'2026-10-30T13:05:00.000Z' → '2026-10-30', no fuso local (como a exportação)."""
    if not iso:
        return ""
    try:
        dt = _instante(iso)
    except ValueError:
        return str(iso)
    if dt.tzinfo is not None and converter_fuso:
        dt = dt.astimezone(FUSO_LOCAL)
    return dt.date().isoformat()


def _pessoa(u) -> str:
    u = u or {}
    return " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x).strip()


def _organizacao(u) -> str:
    """Nome fantasia ('CMI'), não a razão social - é o que a exportação mostra."""
    org = (u or {}).get("organization") or {}
    return org.get("trading_name") or org.get("name") or ""


def _caminho_area(area) -> str:
    area = area or {}
    nomes = [x.get("name", "") for x in area.get("path") or []]
    if not nomes or nomes[-1] != area.get("name"):
        nomes.append(area.get("name", ""))
    return " > ".join(n for n in nomes if n)


def definicoes_por_chave(definicoes: list[dict]) -> dict[str, dict]:
    """family_id PRIMEIRO: o id muda a cada versão da definição do campo."""
    mapa: dict[str, dict] = {}
    for d in definicoes:
        for chave in (d.get("family_id"), d.get("id")):
            if chave:
                mapa.setdefault(str(chave), d)
    return mapa


def rotulos_dos_campos_das_questoes(tipos: list[dict], questoes: list[dict]) -> set[str]:
    """Os rótulos dos campos customizados dos tipos de questão EM USO.

    Nunca todos os de `/customfields`: eles incluem campos de outros módulos
    ("Especialidad", "Idioma"...), e uma coluna manual com um desses nomes seria
    tomada por coluna do Aconex e esvaziada."""
    em_uso = {str((q.get("issue_type") or {}).get("id")) for q in questoes}
    return {str(cf.get("label")) for t in tipos if str(t.get("id")) in em_uso
            for cf in t.get("custom_fields") or [] if cf.get("label")}


def valores_da_questao(q: dict, defs: dict[str, dict], comentarios: str | None = None,
                       avisar=None) -> dict:
    """Título da coluna da exportação → valor, para uma questão.

    `Issue Number` volta como número. `avisar(texto)` recebe o que não foi
    verificado contra o Aconex real (status desconhecido, tipo de campo novo).
    """
    avisar = avisar or (lambda _m: None)
    md = q.get("meta_data") or {}
    status = q.get("status") or ""
    if status and status not in STATUS_ROTULO:
        avisar(f"Status desconhecido '{status}' na pendência {q.get('issue_number')}: gravado como veio.")
    try:
        numero = int(str(q.get("issue_number")).strip())
    except (TypeError, ValueError):
        numero = q.get("issue_number") or ""
    v = {
        "Issue Number": numero,
        "Issue Type": (q.get("issue_type") or {}).get("name") or "",
        "Area": _caminho_area(q.get("area")),
        "Location Detail": q.get("location_detail") or "",
        "Issue Description": q.get("description") or "",
        "Captured On": _data(md.get("created_at")),
        "Captured by": _pessoa(md.get("created_by")),
        "Status": STATUS_ROTULO.get(status, status),
        "Due Date": _data(q.get("due_date"), converter_fuso=False),   # prazo é dia, não instante
        "Assigned On": _data(q.get("assigned_at")),
        "Assigned to": _organizacao(q.get("assigned_to")),
        "Assigned By": _organizacao(q.get("assigned_by")),
        "Closed On": _data(q.get("closed_at")),
        "Closed By User": _pessoa(q.get("closed_by")),
        "Closed By Organization": _organizacao(q.get("closed_by")),
        "Listed In": "; ".join(x.get("title", "") for x in q.get("issue_listings") or []),
    }
    for cf in q.get("custom_fields") or []:
        d = defs.get(str(cf.get("family_id"))) or defs.get(str(cf.get("id")))
        if not d or not d.get("label"):
            continue
        valor = cf.get("value")
        valor = "" if valor is None else valor
        tipo = str((d.get("type") or {}).get("name") or "").lower()
        if tipo == "date":
            valor = _data(valor, converter_fuso=False)
        elif tipo == "boolean":
            valor = BOOLEANO_ROTULO.get(valor, valor)
        elif tipo not in TIPOS_VERIFICADOS and valor != "":
            avisar(f"Campo '{d['label']}' é do tipo '{tipo}', ainda não visto no Aconex real: "
                   "gravado o texto como veio.")
        if not isinstance(valor, str):
            valor = str(valor)
        v[d["label"]] = valor
    if comentarios is not None:
        v["Comments"] = comentarios
    return v


def _quando(iso) -> str:
    """'2026-09-30T11:23:10.953Z' → 'Wed, Sep 30, 2026, 8:23:10 am' (UTC−3, inglês, 12 h)."""
    dt = _instante(iso).astimezone(FUSO_LOCAL)
    return (f"{_DIAS[dt.weekday()]}, {_MESES[dt.month - 1]} {dt.day}, {dt.year}, "
            f"{dt.hour % 12 or 12}:{dt:%M:%S} {'am' if dt.hour < 12 else 'pm'}")


def formatar_comentarios(conversas: list[dict]) -> str:
    """Texto da coluna Comments: 'Everyone' primeiro, blocos separados por linha em branco."""
    blocos = []
    publico_primeiro = sorted(
        conversas, key=lambda c: str((c.get("participant") or {}).get("id")) != PARTICIPANTE_PUBLICO)
    for conv in publico_primeiro:
        coms = sorted(conv.get("comments") or [], key=lambda c: _instante(c["client_captured_at"]))
        if not coms:
            continue
        part = conv.get("participant") or {}
        linhas = [f"With {part.get('trading_name') or part.get('name')}:"]
        for c in coms:
            a = c.get("author") or {}
            org = a.get("organization") or {}
            linhas.append(f'"{c.get("content")}" submitted by {a.get("first_name")} '
                          f'{a.get("last_name")} ({org.get("trading_name") or org.get("name")}) '
                          f'on {_quando(c["client_captured_at"])}')
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)
