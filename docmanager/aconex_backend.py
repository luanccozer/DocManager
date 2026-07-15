"""Extração da base Aconex via API REST (KB §18.2) — sem tkinter.

Porta fiel de `AconexView.executar_script_aconex` (legado L1919-2155): OAuth2
client_credentials, paginação de 500, parse XML, rename para colunas canônicas
(§5), datas dd/mm/yyyy. Log por callback; salvamento por caminho.

Segredos (KB §21.7): o CLIENT_SECRET vem do `.env` (`SECRET_<NOME>`); os
Client ID / User ID são identificadores públicos e ficam aqui como padrão.
Rede corporativa: `truststore` injeta os certificados do Windows (Zscaler);
fora dela, é inofensivo. Proxy: manual, autodetectado ou direto.
"""
from __future__ import annotations

import base64
import os
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:  # 'requests' é import tardio (só a extração ao vivo usa)
    import requests

PROJECT_ID = "1207975853"
ACONEX_INSTANCE = "https://us1.aconex.com"
AUTH_URL = "https://constructionandengineering.oraclecloud.com/auth/token"

CAMPOS_STRING = (
    "statusid,current,trackingId,title,docno,revision,"
    "versionnumber,reviewstatus,Especialidad_singleSelect,"
    "Subespecialidad_singleSelect,doctype,registered,Dcc_singleSelect,"
    "ControlDelEmisor_singleLineText,Idioma_singleSelect,reviewsource,"
    "Disciplina_singleSelect,"
    "TipoDeDocumentoDcc_singleSelect,ControlCmi_singleLineText,"
    # Comentários por revisão (KB §24.5): nº de anotações/markups do cliente na
    # versão + data da última. Confirmados HTTP 200 no schema real do projeto.
    # (markupdate/uploaddate existem no schema mas são REJEITADOS como campo.)
    "numberOfMarkups,markupLastModifiedDate"
)

# Usuários conhecidos: Client ID/User ID públicos; secret sempre do ambiente.
USUARIOS = {
    "Luan Cozer": {"client_id": "SCP_LUAN_COZER_ACONEX_client_APPID", "user_id": "1208560183", "env": "SECRET_LUAN"},
    "Rafhael Martins": {"client_id": "SCP_RAFHAEL_MARTINS_ACONEX_client_APPID", "user_id": "1208639621", "env": "SECRET_RAFHAEL"},
}

MAPA_COLUNAS = {
    "ControlDelEmisor_singleLineText": "Controle do Emissor",
    "DateModified": "Data de Alteração",
    "DocumentNumber": "No. do Documento",
    "Title": "Título",
    "Revision": "Revisão",
    "TrackingId": "Tracking ID",
    "DocumentStatus": "Status",
    "DocumentType": "Tipo do Documento",
    "ReviewSource": "Fonte",
    "ReviewStatus": "Status da Revisão",
    "NumberOfMarkups": "Qtd. de Comentários",
    "MarkupLastModifiedDate": "Data do Último Comentário",
    "VersionNumber": "Versão",
    "Idioma_singleSelect": "Idioma",
    "Subespecialidad_singleSelect": "Subespecialidade",
    "Especialidad_singleSelect": "Especialidade",
    "Dcc_singleSelect": "Subtipo DCC",
    "TipoDeDocumentoDcc_singleSelect": "Tipo do Documento DCC",
    "ControlCmi_singleLineText": "Control CMI",
    "Disciplina_singleSelect": "Disciplina (Modelo)",
}

ORDEM_COLUNAS = [
    "No. do Documento", "Controle do Emissor", "Tracking ID", "Revisão",
    "Data de Alteração", "Status", "Título", "Tipo do Documento",
    "Especialidade", "Subespecialidade", "Tipo do Documento DCC",
    "Subtipo DCC", "Fonte", "Tipo de Tramitação", "Status da Revisão",
    "Qtd. de Comentários", "Data do Último Comentário", "Versão",
    "Current", "Idioma", "Control CMI", "Disciplina (Modelo)",
]


@dataclass
class AconexConfig:
    client_id: str
    client_secret: str
    user_id: str
    project_id: str = PROJECT_ID
    instance: str = ACONEX_INSTANCE
    auth_url: str = AUTH_URL
    campos: str = CAMPOS_STRING
    proxy: str | None = None  # None → autodetecta; "" → força direto

    @classmethod
    def para_usuario(cls, nome: str, *, secret: str | None = None, proxy: str | None = None) -> "AconexConfig":
        if nome not in USUARIOS:
            raise KeyError(f"Usuário '{nome}' desconhecido. Conhecidos: {list(USUARIOS)}")
        u = USUARIOS[nome]
        seg = secret if secret is not None else os.getenv(u["env"], "")
        if not seg:
            raise ValueError(f"Secret vazio. Defina {u['env']} no .env ou passe --secret.")
        return cls(client_id=u["client_id"], client_secret=seg, user_id=u["user_id"], proxy=proxy)


def _proxies(config: AconexConfig, log) -> dict | None:
    if config.proxy:
        return {"http": config.proxy, "https": config.proxy}
    if config.proxy == "":
        return None
    try:
        p = urllib.request.getproxies()
        if p:
            log("Proxy do sistema detectado.")
            return p
    except Exception:
        pass
    log("Nenhum proxy detectado. Conexão direta.")
    return None


def _get_token(session: requests.Session, config: AconexConfig, log) -> str | None:
    creds = base64.b64encode(f"{config.client_id}:{config.client_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    data = {"grant_type": "client_credentials", "user_id": config.user_id, "user_site": config.instance}
    try:
        resp = session.post(config.auth_url, headers=headers, data=data, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("access_token")
        log(f"Erro autenticação: {resp.status_code} - {resp.text[:200]}")
    except Exception as e:  # noqa: BLE001
        log(f"Erro conexão auth: {e}")
    return None


def _parse_pagina(conteudo: bytes) -> list[dict]:
    root = ET.fromstring(conteudo)
    docs = []
    for d in root.iter():
        if "Document" in d.tag and "Documents" not in d.tag:
            item = {}
            for field_el in d:
                tag = field_el.tag.split("}")[-1] if "}" in field_el.tag else field_el.tag
                if field_el.text is not None:
                    item[tag] = field_el.text
            if item:
                docs.append(item)
    return docs


def classificar_fonte(fonte) -> str:
    """Mecanismo de tramitação a partir da Fonte (ReviewSource) — KB §24.1:
      - 'WF-…'  → 'Fluxo'           (Workflow: ciclo de revisão pós-19/08/2024)
      - numérico → 'Transmissão'     (Transmittal)
      - 'SD-…'  → 'Docs. Fornecedor' (Supplier Docs)
      - 'Nenhum'/vazio → ''          (linha fora de qualquer ciclo)

    NÃO diz ONDE (qual etapa/organização) — isso exige a Workflows API. Só
    torna legível, na própria base, o TIPO de trâmite que a Fonte já carrega."""
    s = str(fonte or "").strip()
    if not s or s.upper() == "NENHUM":
        return ""
    up = s.upper()
    if up.startswith("WF"):
        return "Fluxo"
    if up.startswith("SD"):
        return "Docs. Fornecedor"
    if s.replace("-", "").isdigit():
        return "Transmissão"
    return "Outro"


def montar_dataframe(registros: list[dict]) -> pd.DataFrame:
    """Monta o DataFrame canônico a partir dos dicts brutos do XML (função pura,
    sem rede — testável): rename (§5) → coluna derivada 'Tipo de Tramitação' →
    ordem de colunas → datas dd/mm/yyyy. Colunas novas do Aconex que não estejam
    no `ORDEM_COLUNAS` vão para o fim (nunca somem)."""
    if not registros:
        return pd.DataFrame()
    df = pd.DataFrame(registros).dropna(how="all")
    df = df.rename(columns=MAPA_COLUNAS)
    # Fluxo: a Fonte já traz o WF/Transmittal; deriva o tipo legível ao lado.
    if "Fonte" in df.columns:
        df["Tipo de Tramitação"] = df["Fonte"].map(classificar_fonte)
    existentes = [c for c in ORDEM_COLUNAS if c in df.columns]
    extras = [c for c in df.columns if c not in existentes]
    df = df[existentes + extras]
    for col in ("Data de Alteração", "Data do Último Comentário", "registered",
                "FechaDeInicio_date", "FechaFin_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    return df


def extrair_base(config: AconexConfig, *, log_cb=print) -> pd.DataFrame:
    """Extrai o histórico completo do projeto e devolve o DataFrame canônico.

    Operação longa (paginação sobre todo o registro; ~30 min em produção).
    """
    import time

    import requests  # só a extração ao vivo precisa; import tardio deixa o
    #                  parser/monta-DF (funções puras) usáveis sem a lib.

    try:
        import truststore  # certificados do Windows (Zscaler); opcional fora do corporativo
        truststore.inject_into_ssl()
    except Exception as e:  # noqa: BLE001
        log_cb(f"(truststore indisponível: {e} — seguindo sem injeção de certificados)")

    session = requests.Session()
    proxies = _proxies(config, log_cb)
    if proxies:
        session.proxies.update(proxies)

    token = _get_token(session, config, log_cb)
    if not token:
        raise RuntimeError("Falha na autenticação Aconex.")

    base_url = f"{config.instance}/api/projects/{config.project_id}/register"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/xml", "Accept-Encoding": "gzip, deflate"}

    all_data: list[dict] = []
    page, total = 1, 0
    log_cb(f"Iniciando extração do projeto {config.project_id}...")
    while True:
        params = {
            "search_query": "", "return_fields": config.campos, "search_type": "PAGED",
            "page_size": 500, "page_number": page, "show_document_history": "true",
            "sort_field": "docno", "sort_direction": "ASC",
        }
        r, sucesso = None, False
        for tentativa in range(3):
            try:
                r = session.get(base_url, headers=headers, params=params, timeout=60)
                if r.status_code == 200:
                    sucesso = True
                    break
                if r.status_code == 400:
                    break
                if r.status_code == 401:
                    log_cb("Token expirado. Renovando...")
                    token = _get_token(session, config, log_cb)
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    continue
                log_cb(f" [Erro {r.status_code}] tentativa {tentativa + 1}...")
                time.sleep(5)
            except Exception as e:  # noqa: BLE001
                log_cb(f" [Erro conexão] {e}")
                time.sleep(5)
        if not sucesso or (r is not None and r.status_code == 400):
            log_cb(f"Fim da paginação ou erro na página {page}.")
            break
        try:
            docs = _parse_pagina(r.content)
        except Exception as e:  # noqa: BLE001
            log_cb(f"Erro XML página {page}: {e}")
            break
        if not docs:
            break
        all_data.extend(docs)
        total += len(docs)
        log_cb(f"Página {page}: +{len(docs)} docs (total {total})")
        if len(docs) < 500:
            log_cb("Última página atingida.")
            break
        page += 1

    if not all_data:
        log_cb("Nenhum dado extraído.")
        return pd.DataFrame()

    df = montar_dataframe(all_data)
    log_cb(f"Extração concluída: {len(df)} linhas.")
    return df


def nome_arquivo_padrao() -> str:
    return f"Aconex_Historico_{datetime.now().strftime('%d.%m.%y_%Hh%Mm')}.xlsx"


def salvar_excel(df: pd.DataFrame, caminho) -> None:
    """Salva com formatação (xlsxwriter): wrap, larguras, freeze, autofilter."""
    with pd.ExcelWriter(caminho, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Documentos")
        wb, ws = writer.book, writer.sheets["Documentos"]
        fmt = wb.add_format({"text_wrap": True, "valign": "top"})
        fmt_hdr = wb.add_format({"bold": True, "text_wrap": True, "valign": "top", "bottom": 1})
        larguras = {
            "No. do Documento": 26.27, "Controle do Emissor": 24.09, "Revisão": 10.18,
            "Data de Alteração": 19.18, "Status": 17, "Status da Revisão": 17,
            "Título": 76, "Current": 8.09, "Tipo do Documento": 23.27,
            "Tipo de Tramitação": 16, "Qtd. de Comentários": 16,
            "Data do Último Comentário": 21,
        }
        for i, col in enumerate(df.columns):
            ws.set_column(i, i, larguras.get(col, 18), fmt)
            ws.write(0, i, col, fmt_hdr)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, len(df), len(df.columns) - 1)
