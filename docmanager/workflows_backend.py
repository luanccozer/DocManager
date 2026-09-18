"""Extração dos Fluxos de Trabalho via Workflows API do Aconex (KB §24.12).

Espelha `aconex_backend` (mesma sessão, mesmo token, mesmo backoff, mesmo
checkpoint), mas ataca outro serviço - e é ele que traz o que o register NUNCA
teve: **a quem cada etapa está atribuída, o prazo e o atraso**.

ARMADILHA CENTRAL (custou uma investigação inteira, 2026-09-04): o Aconex roteia
por *media type versionado*. Com `Accept: application/xml` - o header da extração
de documentos - TODA rota de workflow responde **404 `URL_UNKNOWN`**, como se o
serviço não existisse neste tenant. O serviço existe; o header é que precisa ser
`application/vnd.aconex.workflow.v1+xml`. Nunca copiar o Accept do register.

Outras diferenças verificadas ao vivo contra o projeto real:
- `page_size` aceita até **1000** (o guia diz "mínimo e múltiplo de 25, padrão
  25"); com 1000 o projeto inteiro sai em ~96 páginas.
- `updated_after`/`updated_before` (RFC3339) permitem extração INCREMENTAL -
  7 dias ≈ 2.700 registros contra ~96.000 do total.
- Os valores vêm **localizados em português** (`Em Andamento`, `Concluído`,
  `Em Atraso`, `Previsão`), não em inglês como o guia documenta. Comparar com as
  constantes deste módulo, nunca com os rótulos do PDF.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

import pandas as pd

from .aconex_backend import (
    ESPERAS_BACKOFF,
    TENTATIVAS_POR_PAGINA,
    AconexConfig,
    ResultadoExtracao,
    _estabelecer_sessao,
    _get_token,
)

# O header que faz a API existir (ver docstring do módulo).
ACCEPT_WORKFLOWS = "application/vnd.aconex.workflow.v1+xml"
PAGE_SIZE_WF = 1000

# Rotas do serviço (todas confirmadas 200 no projeto real). A busca por status
# tem rota própria no guia, mas nenhuma grafia testada respondeu - filtra-se no
# cliente, que é barato porque o status vem em toda linha.
ROTAS = {
    "todos": "workflows",
    "iniciados_por_nos": "workflows/initiated-by/us",
    "iniciados_por_outros": "workflows/initiated-by/others",
    "atribuidos_a_nos": "workflows/assigned-to/us",
    "atribuidos_a_outros": "workflows/assigned-to/others",
}

# Os valores REAIS (em português, com espaço à direita) moram na fonte única de
# constantes de domínio - ver `core/constants.py`, seção "Fluxos de Trabalho".

# Grupos de pessoa no XML: viram duas colunas (nome e organização).
_PESSOAS = {"Initiator": "Iniciador", "Reviewer": "Revisor"}

MAPA_COLUNAS_WF = {
    "WorkflowNumber": "Nº do Fluxo",
    "WorkflowName": "Nome do Fluxo",
    "WorkflowTemplate": "Modelo do Fluxo",
    "WorkflowStatus": "Status do Fluxo",
    "StepName": "Etapa",
    "StepStatus": "Status da Etapa",
    "StepOutcome": "Resultado da Etapa",
    # Nomes IDÊNTICOS aos da base de documentos - é o que permite juntar os dois
    # mundos sem tradução (Tracking ID é a identidade canônica, KB §6).
    "DocumentNumber": "No. do Documento",
    "DocumentRevision": "Revisão",
    "DocumentTitle": "Título",
    "DocumentTrackingId": "Tracking ID",
    "DocumentVersion": "Versão",
    "DateIn": "Data de Recebimento",
    "DateDue": "Data de Vencimento",
    "OriginalDueDate": "Vencimento Original",
    "DateCompleted": "Data de Conclusão",
    "DaysLate": "Dias em Atraso",
    "Duration": "Duração (dias)",
    "ReasonForIssue": "Motivo da Emissão",
    "Comments": "Comentários",
    "FileName": "Arquivo",
    "FileSize": "Tamanho (bytes)",
    "ParentWorkflowId": "Fluxo Pai",
    "RelatedSupplierDocumentPackage": "Pacote do Fornecedor",
}

ORDEM_COLUNAS_WF = [
    "Nº do Fluxo", "Nome do Fluxo", "Status do Fluxo",
    "No. do Documento", "Revisão", "Versão", "Título",
    "Etapa", "Status da Etapa", "Resultado da Etapa",
    "Atribuído a", "Organização Atribuída", "Qtd. Atribuídos",
    "Data de Recebimento", "Data de Vencimento", "Vencimento Original",
    "Data de Conclusão", "Dias em Atraso", "Duração (dias)",
    "Iniciador", "Organização Iniciador", "Revisor", "Organização Revisor",
    "Motivo da Emissão", "Comentários", "Modelo do Fluxo",
    "Tracking ID", "Workflow ID", "Fluxo Pai", "Pacote do Fornecedor",
    "Arquivo", "Tamanho (bytes)", "Organizações (por atribuído)",
]

_COLS_DATA_WF = ("Data de Recebimento", "Data de Vencimento", "Vencimento Original",
                 "Data de Conclusão")


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _texto(el, nome: str) -> str:
    for filho in el:
        if _local(filho.tag) == nome:
            return (filho.text or "").strip()
    return ""


def parse_pagina_workflows(conteudo: bytes) -> list[dict]:
    """XML de uma página → lista de dicts achatados (função pura, sem rede).

    Cada `<Workflow>` é UMA linha (fluxo × documento × etapa) - o mesmo grão da
    aba Fluxos de Trabalho do site. `Assignees` é 1..n: vira nome/organização
    concatenados, porque a linha precisa caber numa planilha.
    """
    root = ET.fromstring(conteudo)
    linhas: list[dict] = []
    for wf in root.iter():
        if _local(wf.tag) != "Workflow":
            continue
        item: dict = {"Workflow ID": wf.attrib.get("WorkflowId", "")}
        for filho in wf:
            nome = _local(filho.tag)
            if nome == "Assignees":
                nomes, orgs, pareadas = [], [], []
                for a in filho:
                    if _local(a.tag) != "Assignee":
                        continue
                    n, o = _texto(a, "Name"), _texto(a, "OrganizationName")
                    if n:
                        nomes.append(n)
                        # PAREADA (1 por pessoa, com repetição): sem isso não dá
                        # para saber de qual organização é CADA atribuído, e um
                        # revisor que participa de etapas mistas aparece
                        # fragmentado no resumo por responsável.
                        pareadas.append(o)
                    if o and o not in orgs:
                        orgs.append(o)
                item["Atribuído a"] = "; ".join(nomes)
                item["Organização Atribuída"] = "; ".join(orgs)   # distintas: leitura
                item["Organizações (por atribuído)"] = "; ".join(pareadas)
                item["Qtd. Atribuídos"] = len(nomes)
            elif nome in _PESSOAS:
                rot = _PESSOAS[nome]
                item[rot] = _texto(filho, "Name")
                item[f"Organização {rot}"] = _texto(filho, "OrganizationName")
            elif filho.text is not None:
                # strip OBRIGATÓRIO: o Aconex devolve vários valores com espaço à
                # direita ('Concluído ') - sem isso toda comparação exata falha.
                item[nome] = filho.text.strip()
        if len(item) > 1:
            linhas.append(item)
    return linhas


def montar_dataframe_workflows(registros: list[dict]) -> pd.DataFrame:
    """Dicts brutos → DataFrame canônico (pura): rename, ordem, datas dd/mm/yyyy.

    Colunas novas que o Aconex venha a acrescentar vão para o fim - nunca somem.
    """
    if not registros:
        return pd.DataFrame()
    df = pd.DataFrame(registros).dropna(how="all").rename(columns=MAPA_COLUNAS_WF)
    for col in _COLS_DATA_WF:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed",
                                     utc=True).dt.strftime("%d/%m/%Y").fillna("")
    existentes = [c for c in ORDEM_COLUNAS_WF if c in df.columns]
    extras = [c for c in df.columns if c not in existentes]
    return df[existentes + extras]


def _chave_checkpoint_wf(config: AconexConfig, rota: str, updated_after: str) -> str:
    from .services.aconex_checkpoint import chave_extracao
    return chave_extracao(project_id=config.project_id,
                          campos=f"workflows|{rota}|{updated_after}",
                          page_size=PAGE_SIZE_WF, sort_field="-", sort_direction="-")


def _baixar_pagina_wf(session, config, url, headers, params, page, log_cb):
    """Uma página com retentativas/backoff - mesma política da extração de docs.

    Devolve `(linhas, fim, erro, session)`; a sessão volta junto porque uma
    reconexão a SUBSTITUI.
    """
    import time

    p = dict(params, page_number=page)
    ultimo_erro, renovacoes, tentativa = "", 0, 0
    while tentativa < TENTATIVAS_POR_PAGINA:
        try:
            r = session.get(url, headers=headers, params=p, timeout=120)
            if r.status_code == 200:
                try:
                    return parse_pagina_workflows(r.content), False, "", session
                except Exception as e:  # noqa: BLE001 - XML truncado: vale retentar
                    ultimo_erro = f"XML inválido na página {page}: {e}"
            elif r.status_code == 400:
                # Fim normal da paginação (page_number além do total).
                return [], True, "", session
            elif r.status_code == 401 and renovacoes < 3:
                renovacoes += 1
                log_cb("Token expirado. Renovando...")
                novo = _get_token(session, config, log_cb)
                if novo:
                    headers["Authorization"] = f"Bearer {novo}"
                    continue
                ultimo_erro = "não foi possível renovar o token"
            else:
                ultimo_erro = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            ultimo_erro = f"{type(e).__name__}: {e}"
        tentativa += 1
        if tentativa < TENTATIVAS_POR_PAGINA:
            espera = ESPERAS_BACKOFF[min(tentativa - 1, len(ESPERAS_BACKOFF) - 1)]
            log_cb(f" [{ultimo_erro}] tentativa {tentativa + 1}/{TENTATIVAS_POR_PAGINA} "
                   f"em {espera}s...")
            time.sleep(espera)
            if tentativa >= 2:
                try:
                    session, token = _estabelecer_sessao(config, log_cb)
                    headers["Authorization"] = f"Bearer {token}"
                except Exception as e:  # noqa: BLE001
                    log_cb(f" (falha ao reconectar: {e})")
    return [], False, ultimo_erro, session


def extrair_workflows(config: AconexConfig, *, log_cb=print, rota: str = "todos",
                      updated_after: str = "", updated_before: str = "",
                      usar_checkpoint: bool = True, pasta_checkpoint=None,
                      progress_cb=None, cancelado_cb=None) -> ResultadoExtracao:
    """Extrai os Fluxos de Trabalho do projeto (~96 páginas de 1000, ~20 min).

    `updated_after`/`updated_before`: RFC3339 (`2026-08-01T00:00:00Z`) - com o
    primeiro a extração vira INCREMENTAL e cai para segundos. `rota`: chave de
    `ROTAS`. Retomada por checkpoint igual à extração de documentos.
    """
    from .services.aconex_checkpoint import CheckpointExtracao

    try:
        import truststore   # certificados do Windows (Zscaler) - ver aconex_backend
        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001
        pass

    if rota not in ROTAS:
        raise KeyError(f"Rota '{rota}' desconhecida. Use uma de: {list(ROTAS)}")

    ck = (CheckpointExtracao(_chave_checkpoint_wf(config, rota, updated_after), pasta_checkpoint)
          if usar_checkpoint else None)
    todos: list[dict] = []
    page, retomada = 1, False
    if ck is not None:
        todos = ck.carregar()
        if todos:
            retomada = True
            page = ck.estado.proxima_pagina
            log_cb(f"Retomando extração de fluxos em {ck.estado.atualizado_em}: "
                   f"{len(todos)} registros - continuando da página {page}.")
        else:
            ck.limpar()

    session, token = _estabelecer_sessao(config, log_cb)
    url = f"{config.instance}/api/projects/{config.project_id}/{ROTAS[rota]}"
    headers = {"Authorization": f"Bearer {token}", "Accept": ACCEPT_WORKFLOWS,
               "Accept-Encoding": "gzip, deflate"}
    params = {"page_size": PAGE_SIZE_WF}
    if updated_after:
        params["updated_after"] = updated_after
    if updated_before:
        params["updated_before"] = updated_before

    total = len(todos)
    completa, motivo = False, ""
    log_cb(f"Extraindo fluxos de trabalho ({rota}) do projeto {config.project_id}...")
    try:
        while True:
            if cancelado_cb is not None and cancelado_cb():
                motivo = "cancelado pelo usuário"
                log_cb("Extração cancelada. O progresso ficou salvo para retomar depois.")
                break
            linhas, fim, erro, session = _baixar_pagina_wf(
                session, config, url, headers, params, page, log_cb)
            if erro:
                motivo = (f"falha na página {page} após {TENTATIVAS_POR_PAGINA} "
                          f"tentativas ({erro})")
                log_cb(f"INTERROMPIDO: {motivo}.")
                break
            if fim or not linhas:
                completa = True
                log_cb("Fim da paginação.")
                break
            todos.extend(linhas)
            total += len(linhas)
            if ck is not None:
                ck.registrar_pagina(page, linhas)
            log_cb(f"Página {page}: +{len(linhas)} fluxos (total {total})")
            if progress_cb:
                progress_cb(min(0.05 + page * 0.01, 0.95))
            if len(linhas) < PAGE_SIZE_WF:
                completa = True
                log_cb("Última página atingida.")
                break
            page += 1
    finally:
        if ck is not None:
            ck.fechar()

    if not todos:
        log_cb("Nenhum fluxo extraído.")
        return ResultadoExtracao(pd.DataFrame(), completa, page - 1, 0, motivo,
                                 str(ck.path_meta) if (ck and not completa) else "", retomada)

    df = montar_dataframe_workflows(todos)
    if completa:
        log_cb(f"Extração de fluxos concluída: {len(df)} linhas.")
    else:
        log_cb(f"Extração INCOMPLETA: {len(df)} linhas até a página {page - 1}. "
               f"Rode de novo para continuar de onde parou.")
    return ResultadoExtracao(df, completa, page - 1, total, motivo,
                             str(ck.path_meta) if (ck and not completa) else "", retomada)


def limpar_checkpoint_wf(config: AconexConfig, *, rota: str = "todos",
                         updated_after: str = "", pasta_checkpoint=None) -> None:
    """Descarta o checkpoint - chamar depois que a base de fluxos foi SALVA."""
    from .services.aconex_checkpoint import CheckpointExtracao
    CheckpointExtracao(_chave_checkpoint_wf(config, rota, updated_after),
                       pasta_checkpoint).limpar()


# Larguras do Excel de fluxos (coluna → caracteres).
_LARGURAS_WF = {
    "Nº do Fluxo": 14, "Nome do Fluxo": 38, "Status do Fluxo": 16,
    "No. do Documento": 26, "Revisão": 9, "Versão": 8, "Título": 70,
    "Etapa": 26, "Status da Etapa": 16, "Resultado da Etapa": 20,
    "Atribuído a": 42, "Organização Atribuída": 30, "Qtd. Atribuídos": 10,
    "Data de Recebimento": 17, "Data de Vencimento": 17,
    "Vencimento Original": 17, "Data de Conclusão": 16,
    "Dias em Atraso": 12, "Duração (dias)": 12, "Comentários": 46,
    "Iniciador": 24, "Organização Iniciador": 28, "Revisor": 24,
    "Organização Revisor": 28, "Motivo da Emissão": 22, "Modelo do Fluxo": 34,
    "Tracking ID": 22, "Workflow ID": 22, "Arquivo": 34,
}


def nome_arquivo_padrao_wf() -> str:
    """Convenção do projeto: `Aconex_Workflows_<dd.mm.yy_HHhMMm>.xlsx`."""
    return f"Aconex_Workflows_{datetime.now().strftime('%d.%m.%y_%Hh%Mm')}.xlsx"


def salvar_excel_workflows(df: pd.DataFrame, caminho) -> None:
    """Salva a base de fluxos com o mesmo acabamento da base de documentos."""
    with pd.ExcelWriter(caminho, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Fluxos")
        wb, ws = writer.book, writer.sheets["Fluxos"]
        fmt = wb.add_format({"text_wrap": True, "valign": "top"})
        fmt_hdr = wb.add_format({"bold": True, "text_wrap": True, "valign": "top", "bottom": 1})
        for i, col in enumerate(df.columns):
            ws.set_column(i, i, _LARGURAS_WF.get(col, 18), fmt)
            ws.write(0, i, col, fmt_hdr)
        ws.freeze_panes(1, 0)
        if len(df):
            ws.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))
