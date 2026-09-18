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
import re
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import pandas as pd

from .services import rede

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
    "TipoDeDocumentoDcc_singleSelect,ControlCmi_singleLineText"
)
# NOTA (KB §24.5/§24.9): 'numberOfMarkups' foi testado e DESCARTADO — conta
# ELEMENTOS de marcação, não as "Anotações" do site (v32: 344 vs 147; v93: 19 vs
# 10). Não há endpoint de markups (todos 404) nem outro campo no schema. Sem
# fonte confiável da contagem de anotações, a coluna foi removida (2026-07-15).

# Usuários conhecidos: Client ID/User ID públicos; secret sempre do ambiente.
USUARIOS = {
    "Luan Cozer": {"client_id": "SCP_LUAN_COZER_ACONEX_client_APPID", "user_id": "1208560183", "env": "SECRET_LUAN"},
    "Rafhael Martins": {"client_id": "SCP_RAFHAEL_MARTINS_ACONEX_client_APPID", "user_id": "1208639621", "env": "SECRET_RAFHAEL"},
}

# Rótulo da opção de entrada manual (usuário não previsto informa os dados dele).
OUTRO_USUARIO = "Outro (inserir manualmente)"


def _perfil_do_env(sufixo: str) -> dict | None:
    """Perfil de um usuário NOVO, descoberto só pelo .env. O Aconex exige os três
    dados, então além do SECRET_<NOME> é preciso CLIENTID_<NOME> e USERID_<NOME>
    (o secret sozinho não autentica). Sem eles → None (usa-se a opção manual)."""
    cid = os.getenv(f"CLIENTID_{sufixo}", "").strip()
    uid = os.getenv(f"USERID_{sufixo}", "").strip()
    return {"client_id": cid, "user_id": uid, "env": f"SECRET_{sufixo}"} if cid and uid else None


def _perfis_do_env() -> dict[str, dict]:
    """Usuários que ainda vêm do `.env` (formato legado, anterior à v3.1.0).

    Continua funcionando para quem já tinha um .env montado, mas o caminho
    normal hoje é o cadastro pela interface (`services.credenciais`)."""
    perfis: dict[str, dict] = {
        nome: dict(u) for nome, u in USUARIOS.items() if os.getenv(u["env"], "").strip()
    }
    ja_conhecidos = {u["env"] for u in USUARIOS.values()}
    for chave, valor in os.environ.items():
        if (not chave.startswith("SECRET_") or chave in ja_conhecidos
                or not str(valor).strip()):
            continue
        perfil = _perfil_do_env(chave[len("SECRET_"):])
        if perfil:
            perfis[chave[len("SECRET_"):].replace("_", " ").title()] = perfil
    return perfis


def _perfis_do_cofre() -> dict[str, dict]:
    """Usuários cadastrados pela interface (Documentos\\DocManager_Itaipu)."""
    from .services.credenciais import cofre

    perfis: dict[str, dict] = {}
    try:
        c = cofre()
        for nome in c.listar():
            cred = c.obter(nome)
            if cred and cred.completa():
                perfis[nome] = {"client_id": cred.client_id, "user_id": cred.user_id,
                                "env": "", "fonte": "cofre"}
    except Exception:  # noqa: BLE001 — cofre ilegível não pode esconder o .env
        pass
    return perfis


def perfis_disponiveis() -> dict[str, dict]:
    """{nome exibido → perfil} de todos os usuários utilizáveis.

    Duas fontes, nesta ordem de precedência:
      1. **Cofre do app** — cadastrado na própria interface (Extração →
         "Cadastrar usuário"), com o secret cifrado pela DPAPI do Windows. É o
         caminho normal desde a v3.1.0, em que o app passou a ser distribuído
         por instalador e ninguém mais recebe um `.env` pronto;
      2. **`.env`** — formato legado: SECRET_<NOME> para os usuários conhecidos
         (os IDs já estão em `USUARIOS`) ou SECRET_ + CLIENTID_ + USERID_ para um
         usuário novo. Quem já tinha um .env é migrado para o cofre no primeiro
         uso (`migrar_env_para_cofre`).

    Quem não tem credencial completa some da lista; a opção `OUTRO_USUARIO`
    (entrada manual, válida só para aquela execução) cobre o resto."""
    perfis = _perfis_do_env()
    perfis.update(_perfis_do_cofre())   # o cadastro no app vence o .env antigo
    return perfis


def usuarios_disponiveis() -> list[str]:
    """Nomes para o seletor da extração (ver `perfis_disponiveis`)."""
    return list(perfis_disponiveis())


def migrar_env_para_cofre(log_cb=None) -> list[str]:
    """Importa para o cofre os usuários que ainda só existem no `.env`.

    Chamada uma vez na abertura do app: quem vem da v3.0.0 (com .env na máquina)
    não precisa recadastrar nada — os dados aparecem já cadastrados na Extração.
    Devolve os nomes importados (lista vazia quando não há nada a fazer)."""
    from .services.credenciais import cofre

    try:
        importados = cofre().importar_do_env(USUARIOS)
    except Exception as e:  # noqa: BLE001 — migração nunca pode impedir a abertura
        if log_cb:
            log_cb(f"(não foi possível importar as credenciais do .env: {e})")
        return []
    if importados and log_cb:
        log_cb(f"Credenciais do .env importadas para o app: {', '.join(importados)}.")
    return importados

def _secret_de(nome: str, perfil: dict) -> str:
    """Client Secret do usuário: primeiro o cofre do app, depois o `.env`."""
    from .services.credenciais import cofre

    try:
        cred = cofre().obter(nome)
        if cred and cred.secret:
            return cred.secret
    except Exception:  # noqa: BLE001
        pass
    return os.getenv(perfil.get("env") or "", "").strip()


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
    "Subtipo DCC", "Fonte", "Tipo de Tramitação", "Status da Revisão", "Versão",
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
        """Config de um usuário do .env (conhecido ou descoberto por SECRET_<NOME>)."""
        # Cai no USUARIOS mesmo sem secret, para o erro ser "secret vazio"
        # (acionável) em vez de "usuário desconhecido".
        u = perfis_disponiveis().get(nome) or USUARIOS.get(nome)
        if u is None:
            raise KeyError(f"Usuário '{nome}' desconhecido. Cadastrados: "
                           f"{usuarios_disponiveis() or '(nenhum)'}")
        seg = secret if secret is not None else _secret_de(nome, u)
        if not seg:
            onde = (f"Defina {u['env']} no .env" if u.get("env")
                    else "Cadastre o Client Secret dele na tela de Extração")
            raise ValueError(f"Secret vazio para '{nome}'. {onde} ou use a opção "
                             f"'{OUTRO_USUARIO}'.")
        return cls(client_id=u["client_id"], client_secret=seg, user_id=u["user_id"], proxy=proxy)


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


def _tentar_token(session, config: AconexConfig) -> str:
    """Autentica DEIXANDO as exceções de rede/SSL propagarem (para a cascata
    distinguir a via que funciona). Retorna o token no 200; levanta
    PermissionError se a API recusar as credenciais (trocar de proxy não ajuda)."""
    creds = base64.b64encode(f"{config.client_id}:{config.client_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}",
               "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    data = {"grant_type": "client_credentials", "user_id": config.user_id, "user_site": config.instance}
    resp = session.post(config.auth_url, headers=headers, data=data, timeout=30)
    if resp.status_code == 200:
        tok = resp.json().get("access_token")
        if tok:
            return tok
        raise PermissionError("resposta 200 sem access_token")
    raise PermissionError(f"HTTP {resp.status_code}: {resp.text[:160]}")


def _estrategias_conexao(config: AconexConfig) -> list:
    """Vias de conexão a tentar, em ordem (item 3 — robustez VPN/Zscaler). Cada
    item: (nome, proxies|None, trust_env). proxies=None → deixa o requests usar
    o ambiente; {} → força SEM proxy."""
    if config.proxy:
        return [("proxy informado", {"http": config.proxy, "https": config.proxy}, False)]
    estr: list = []
    try:
        sistema = urllib.request.getproxies()
    except Exception:  # noqa: BLE001
        sistema = {}
    if sistema:
        estr.append(("proxy do sistema", sistema, False))
    if any(os.getenv(v) for v in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy")):
        estr.append(("variáveis de ambiente", None, True))
    estr.append(("conexão direta", {}, False))
    return estr


def _estabelecer_sessao(config: AconexConfig, log_cb):
    """Tenta autenticar por várias vias (proxy do sistema, ambiente, direta) e —
    só se houver falha de CERTIFICADO — repete SEM verificação SSL (último
    recurso, com aviso). Devolve (session, token) ou levanta RuntimeError com
    diagnóstico. Não prejudica quem já funciona: a via boa vem primeiro."""
    import requests

    estrategias = _estrategias_conexao(config)
    houve_ssl = False
    for verify in (True, False):
        if not verify:
            if not houve_ssl:
                break   # nenhuma falha foi de SSL → não desabilita verificação
            log_cb("⚠️ Último recurso: tentando SEM verificação de certificado SSL "
                   "(o certificado do Zscaler/GlobalProtect não está no sistema). "
                   "Só use em rede corporativa confiável.")
            try:
                import urllib3
                urllib3.disable_warnings()
            except Exception:  # noqa: BLE001
                pass
        for nome, proxies, trust_env in estrategias:
            session = requests.Session()
            session.trust_env = trust_env
            if proxies is not None:
                session.proxies = dict(proxies)
            session.verify = verify
            try:
                token = _tentar_token(session, config)
            except requests.exceptions.SSLError as e:
                houve_ssl = True
                log_cb(f"  [{nome}] certificado SSL não confiável — {rede.resumo_erro(e)}")
                continue
            except PermissionError as e:
                # Conectou, mas as credenciais foram recusadas — proxy não muda isso.
                raise RuntimeError(f"Conectou, mas o Aconex recusou as credenciais "
                                   f"({e}). Verifique o secret/usuário.") from e
            except requests.exceptions.RequestException as e:
                # A causa RAIZ, não o embrulho do requests: "Max retries
                # exceeded" é idêntico para timeout, DNS e conexão recusada.
                log_cb(f"  [{nome}] sem conexão — {rede.resumo_erro(e)}")
                continue
            via = nome + ("" if verify else " · SSL NÃO verificado")
            log_cb(f"Conectado ao Aconex via {via}.")
            return session, token
    # Nenhuma rota funcionou: em vez de mandar "verifique a rede", despejar o
    # estado real (proxy do Windows, PAC, DNS, porta 443) no log — é a diferença
    # entre diagnosticar e ficar trocando a VPN no escuro.
    for linha in rede.diagnostico(urlparse(config.auth_url).hostname or ""):
        log_cb(linha)
    raise RuntimeError("Não foi possível conectar ao Aconex por nenhuma via "
                       "(proxy do sistema, variáveis de ambiente, conexão direta, "
                       "SSL). O diagnóstico de rede acima diz onde está travando.")


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
    for col in ("Data de Alteração", "registered",
                "FechaDeInicio_date", "FechaFin_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    return df


PAGE_SIZE = 500          # o register só aceita 25/50/…/500 (KB §24)
SORT_FIELD = "docno"
SORT_DIRECTION = "ASC"
TENTATIVAS_POR_PAGINA = 5
ESPERAS_BACKOFF = (5, 15, 30, 60)   # segundos entre tentativas


@dataclass
class ResultadoExtracao:
    """Desfecho de uma extração — inclusive quando ela NÃO terminou.

    Antes `extrair_base` devolvia um DataFrame e pronto: uma queda de conexão no
    meio da paginação produzia uma base truncada indistinguível de uma completa,
    que ia direto para o Excel e para os demais módulos. Agora `completa` diz a
    verdade e `checkpoint` aponta de onde a próxima tentativa continua.
    """
    df: pd.DataFrame
    completa: bool
    paginas: int = 0
    registros: int = 0
    motivo: str = ""          # por que parou, quando incompleta
    checkpoint: str = ""      # arquivo de retomada (vazio = sem retomada)
    retomada: bool = False    # esta execução continuou uma anterior

    @property
    def ok(self) -> bool:
        return self.completa and not self.df.empty


def _chave_checkpoint(config: AconexConfig) -> str:
    from .services.aconex_checkpoint import chave_extracao
    return chave_extracao(project_id=config.project_id, campos=config.campos,
                          page_size=PAGE_SIZE, sort_field=SORT_FIELD,
                          sort_direction=SORT_DIRECTION)


def _baixar_pagina(session, config, base_url, headers, page, log_cb):
    """Baixa UMA página com retentativas e backoff progressivo.

    Devolve `(docs, fim_da_paginacao, erro, session)` — a sessão volta junto
    porque uma reconexão a SUBSTITUI, e o laço de paginação precisa seguir com a
    nova (a antiga está morta). Renovar o token (401) não gasta tentativa:
    expirar depois de meia hora de paginação é o esperado, não uma falha.
    """
    import time

    params = {
        "search_query": "", "return_fields": config.campos, "search_type": "PAGED",
        "page_size": PAGE_SIZE, "page_number": page, "show_document_history": "true",
        "sort_field": SORT_FIELD, "sort_direction": SORT_DIRECTION,
    }
    ultimo_erro = ""
    renovacoes = 0
    tentativa = 0
    while tentativa < TENTATIVAS_POR_PAGINA:
        try:
            r = session.get(base_url, headers=headers, params=params, timeout=60)
            if r.status_code == 200:
                try:
                    return _parse_pagina(r.content), False, "", session
                except Exception as e:  # noqa: BLE001 — XML truncado: vale retentar
                    ultimo_erro = f"XML inválido na página {page}: {e}"
                    log_cb(f" [{ultimo_erro}] tentativa {tentativa + 1}/{TENTATIVAS_POR_PAGINA}...")
            elif r.status_code == 400:
                return [], True, "", session          # fim normal da paginação
            elif r.status_code == 401 and renovacoes < 3:
                renovacoes += 1
                log_cb("Token expirado. Renovando...")
                novo = _get_token(session, config, log_cb)
                if novo:
                    headers["Authorization"] = f"Bearer {novo}"
                    continue                 # não consome tentativa
                ultimo_erro = "não foi possível renovar o token"
            else:
                ultimo_erro = f"HTTP {r.status_code}"
                log_cb(f" [Erro {r.status_code}] tentativa {tentativa + 1}/{TENTATIVAS_POR_PAGINA}...")
        except Exception as e:  # noqa: BLE001 — rede/SSL/timeout
            ultimo_erro = f"conexão: {e}"
            log_cb(f" [Erro de conexão] {str(e)[:120]} — tentativa "
                   f"{tentativa + 1}/{TENTATIVAS_POR_PAGINA}...")
            if tentativa >= 1:
                try:
                    log_cb(" Reconectando (nova sessão e novo token)...")
                    nova_sessao, novo_token = _estabelecer_sessao(config, log_cb)
                    session.close()
                    session = nova_sessao
                    headers["Authorization"] = f"Bearer {novo_token}"
                except Exception as e2:  # noqa: BLE001
                    log_cb(f" Reconexão falhou: {str(e2)[:120]}")
        tentativa += 1
        if tentativa < TENTATIVAS_POR_PAGINA:
            espera = ESPERAS_BACKOFF[min(tentativa - 1, len(ESPERAS_BACKOFF) - 1)]
            log_cb(f" Aguardando {espera}s antes de tentar de novo...")
            time.sleep(espera)
    return None, False, ultimo_erro or "falha desconhecida", session


def extrair_base(config: AconexConfig, *, log_cb=print, usar_checkpoint: bool = True,
                 pasta_checkpoint=None, progress_cb=None,
                 cancelado_cb=None) -> ResultadoExtracao:
    """Extrai o histórico completo do projeto (paginação sobre todo o registro,
    ~30 min em produção) e devolve um `ResultadoExtracao`.

    Com `usar_checkpoint` (padrão), cada página baixada é persistida em disco:
    se a conexão cair — ou o app for fechado — a próxima execução **retoma da
    página seguinte** em vez de recomeçar do zero. O checkpoint só é apagado
    depois que o chamador confirma o salvamento (`limpar_checkpoint`).

    `cancelado_cb()` → True interrompe a extração no fim da página corrente,
    preservando o checkpoint.
    """
    from .services.aconex_checkpoint import CheckpointExtracao

    try:
        import truststore  # injeta os certificados do Windows (inclui o do Zscaler
        truststore.inject_into_ssl()  # nas máquinas gerenciadas) na verificação SSL.
        log_cb("Certificados do Windows carregados (truststore).")
    except Exception as e:  # noqa: BLE001
        log_cb(f"(truststore indisponível: {e} — se o Zscaler/GlobalProtect inspecionar "
               f"o SSL, a conexão pode cair no modo sem verificação de certificado)")

    ck = CheckpointExtracao(_chave_checkpoint(config), pasta_checkpoint) if usar_checkpoint else None
    all_data: list[dict] = []
    page = 1
    retomada = False
    if ck is not None:
        all_data = ck.carregar()
        if all_data:
            retomada = True
            page = ck.estado.proxima_pagina
            log_cb(f"Retomando extração interrompida em {ck.estado.atualizado_em}: "
                   f"{len(all_data)} registros já baixados — continuando da página {page}.")
        else:
            ck.limpar()   # meta órfão/corrompido não atrapalha a execução nova

    # Cascata de conexão robusta a VPN/Zscaler (item 3): tenta várias vias.
    session, token = _estabelecer_sessao(config, log_cb)

    base_url = f"{config.instance}/api/projects/{config.project_id}/register"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/xml",
               "Accept-Encoding": "gzip, deflate"}

    total = len(all_data)
    completa, motivo = False, ""
    log_cb(f"Iniciando extração do projeto {config.project_id}...")
    try:
        while True:
            if cancelado_cb is not None and cancelado_cb():
                motivo = "cancelado pelo usuário"
                log_cb("Extração cancelada. O progresso ficou salvo para retomar depois.")
                break
            docs, fim, erro, session = _baixar_pagina(
                session, config, base_url, headers, page, log_cb)
            if erro:
                motivo = f"falha na página {page} após {TENTATIVAS_POR_PAGINA} tentativas ({erro})"
                log_cb(f"INTERROMPIDO: {motivo}.")
                break
            if fim or not docs:
                completa = True
                log_cb("Fim da paginação.")
                break
            all_data.extend(docs)
            total += len(docs)
            if ck is not None:
                ck.registrar_pagina(page, docs)
            log_cb(f"Página {page}: +{len(docs)} docs (total {total})")
            if progress_cb:
                progress_cb(min(0.05 + page * 0.02, 0.95))
            if len(docs) < PAGE_SIZE:
                completa = True
                log_cb("Última página atingida.")
                break
            page += 1
    finally:
        if ck is not None:
            ck.fechar()

    if not all_data:
        log_cb("Nenhum dado extraído.")
        return ResultadoExtracao(pd.DataFrame(), completa, page - 1, 0, motivo,
                                 str(ck.path_meta) if (ck and not completa) else "", retomada)

    df = montar_dataframe(all_data)
    if completa:
        log_cb(f"Extração concluída: {len(df)} linhas.")
    else:
        log_cb(f"Extração INCOMPLETA: {len(df)} linhas baixadas até a página {page - 1}. "
               f"Rode de novo para continuar de onde parou.")
    return ResultadoExtracao(df, completa, page - 1, total, motivo,
                             str(ck.path_meta) if (ck and not completa) else "", retomada)


def limpar_checkpoint(config: AconexConfig, pasta_checkpoint=None) -> None:
    """Descarta o checkpoint da extração — chamar depois que a base foi SALVA."""
    from .services.aconex_checkpoint import CheckpointExtracao
    CheckpointExtracao(_chave_checkpoint(config), pasta_checkpoint).limpar()


def checkpoint_pendente(config: AconexConfig, pasta_checkpoint=None):
    """Estado do checkpoint desta consulta, ou None se não houver retomada."""
    from .services.aconex_checkpoint import CheckpointExtracao
    ck = CheckpointExtracao(_chave_checkpoint(config), pasta_checkpoint)
    return ck.ler_meta() if ck.existe() else None


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
            "Tipo de Tramitação": 16,
        }
        for i, col in enumerate(df.columns):
            ws.set_column(i, i, larguras.get(col, 18), fmt)
            ws.write(0, i, col, fmt_hdr)
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, len(df), len(df.columns) - 1)


# ==========================================================================
# Download de arquivos por lista de códigos (versão CURRENT) — KB Feature
# ==========================================================================
# Comprovado ao vivo (2026-07-29): a busca EXATA por código usa search_query com
# o código ENTRE ASPAS ('"<codigo>"'); o arquivo da versão vigente sai de
# GET /register/{DocumentId}/markedup (application/octet-stream, ex.: %PDF).
DOWNLOAD_TIMEOUT = 180
_RESERVADOS_ARQ = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _tag_local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _nome_seguro(nome: str) -> str:
    """Nome de arquivo válido no Windows (troca os reservados por '_')."""
    limpo = _RESERVADOS_ARQ.sub("_", str(nome)).strip().strip(".")
    return limpo or "documento"


def _caminho_unico(caminho: str) -> str:
    """Evita sobrescrever: se já existir, acrescenta ' (2)', ' (3)'…"""
    if not os.path.exists(caminho):
        return caminho
    raiz, ext = os.path.splitext(caminho)
    i = 2
    while os.path.exists(f"{raiz} ({i}){ext}"):
        i += 1
    return f"{raiz} ({i}){ext}"


@dataclass
class ResultadoDownload:
    """Desfecho do download por lista."""
    total: int = 0
    baixados: int = 0
    pasta: str = ""
    nao_encontrados: list = field(default_factory=list)
    sem_arquivo: list = field(default_factory=list)
    erros: list = field(default_factory=list)   # (codigo, motivo)


def _buscar_doc_atual(session, base_url, headers, codigo: str):
    """(DocumentId, filename, revisão) da versão vigente do código, ou None.

    Busca EXATA: `search_query='"<codigo>"'` (as aspas fazem o casamento exato —
    sem elas o register devolve 0). Sem `show_document_history`, o register já
    devolve só a versão corrente."""
    params = {"search_query": f'"{codigo}"',
              "return_fields": "docno,current,filename,revision,versionnumber",
              "search_type": "PAGED", "page_size": 25, "page_number": 1}
    r = session.get(base_url, headers=headers, params=params, timeout=60)
    if r.status_code != 200:
        return None
    root = ET.fromstring(r.content)
    melhor = None
    for d in root.iter():
        if _tag_local(d.tag) != "Document":
            continue
        did = d.attrib.get("DocumentId") or d.attrib.get("documentId")
        if not did:
            continue
        campos = {_tag_local(c.tag): (c.text or "") for c in d}
        item = (did, campos.get("Filename", "").strip(), campos.get("Revision", "").strip())
        if str(campos.get("Current", "")).lower() == "true":
            return item
        if melhor is None:
            melhor = item
    return melhor


def baixar_documentos(config: AconexConfig, codigos, pasta_destino, *,
                      log_cb=print, progress_cb=None, cancelado_cb=None) -> ResultadoDownload:
    """Baixa a versão VIGENTE (current) de cada código numa pasta (pedido do
    usuário). Para cada código: busca exata → DocumentId → GET .../markedup →
    grava com o nome de arquivo do Aconex (sem sobrescrever)."""
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception as e:  # noqa: BLE001
        log_cb(f"(truststore indisponível: {e})")

    lista = [str(c).strip() for c in codigos if str(c).strip()]
    res = ResultadoDownload(total=len(lista), pasta=str(pasta_destino))
    if not lista:
        log_cb("Nenhum código informado.")
        return res
    os.makedirs(pasta_destino, exist_ok=True)

    session, token = _estabelecer_sessao(config, log_cb)
    base_url = f"{config.instance}/api/projects/{config.project_id}/register"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/xml"}
    log_cb(f"Baixando {len(lista)} documento(s) para {pasta_destino}...")

    for i, cod in enumerate(lista):
        if cancelado_cb is not None and cancelado_cb():
            log_cb("Download cancelado pelo usuário.")
            break
        if progress_cb and res.total:
            progress_cb(min(0.05 + i / res.total * 0.9, 0.95))
        try:
            info = _buscar_doc_atual(session, base_url, headers, cod)
        except Exception as e:  # noqa: BLE001
            res.erros.append((cod, f"busca: {e}"))
            log_cb(f"  ✗ {cod}: erro na busca ({e})")
            continue
        if info is None:
            res.nao_encontrados.append(cod)
            log_cb(f"  ✗ {cod}: não encontrado")
            continue
        did, filename, _rev = info
        if not filename:
            res.sem_arquivo.append(cod)
            log_cb(f"  ✗ {cod}: documento sem arquivo")
            continue
        try:
            r = session.get(f"{base_url}/{did}/markedup",
                            headers={"Authorization": headers["Authorization"]},
                            timeout=DOWNLOAD_TIMEOUT)
            if r.status_code != 200 or not r.content:
                res.erros.append((cod, f"download HTTP {r.status_code}"))
                log_cb(f"  ✗ {cod}: download falhou (HTTP {r.status_code})")
                continue
            destino = _caminho_unico(os.path.join(pasta_destino, _nome_seguro(filename)))
            with open(destino, "wb") as f:
                f.write(r.content)
            res.baixados += 1
            log_cb(f"  ✓ {cod} → {os.path.basename(destino)}")
        except Exception as e:  # noqa: BLE001
            res.erros.append((cod, str(e)))
            log_cb(f"  ✗ {cod}: erro ao baixar ({e})")

    if progress_cb:
        progress_cb(1.0)
    log_cb(f"Concluído: {res.baixados}/{res.total} baixados em {pasta_destino}.")
    if res.nao_encontrados:
        log_cb(f"  {len(res.nao_encontrados)} não encontrado(s): "
               + ", ".join(res.nao_encontrados[:20])
               + (" …" if len(res.nao_encontrados) > 20 else ""))
    if res.sem_arquivo:
        log_cb(f"  {len(res.sem_arquivo)} sem arquivo: " + ", ".join(res.sem_arquivo[:20]))
    if res.erros:
        log_cb(f"  {len(res.erros)} com erro: "
               + ", ".join(f"{c} ({m})" for c, m in res.erros[:10]))
    return res
