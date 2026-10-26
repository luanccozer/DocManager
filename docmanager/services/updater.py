"""Atualização automática a partir dos Releases do GitHub.

Como funciona, em uma frase: o app pergunta ao GitHub qual é o último Release,
compara com a versão do próprio binário (`_build_info.VERSAO`), e - se for mais
nova - baixa o instalador, confere o SHA256 e o executa; o app se fecha para que
o instalador possa substituir os arquivos.

═══ Os quatro erros que quebram um auto-update e como cada um foi tratado ═══

1. **Repositório PRIVADO + `browser_download_url`.** Em repo privado aquela URL
   só funciona para um NAVEGADOR LOGADO: um `requests.get` nela recebe uma
   página HTML de login, com status 200. O download "dá certo" e entrega um HTML
   de 4 KB renomeado para `.exe` - que não instala nada. O jeito certo é o
   endpoint de API do asset (`/releases/assets/{id}`) com
   `Accept: application/octet-stream` e o token. É o que `baixar()` usa.

2. **Zscaler/GlobalProtect.** Sem os certificados do Windows, todo HTTPS falha
   com `certificate verify failed` e o app simplesmente nunca avisa que há
   versão nova. Tudo aqui passa por `services.rede`, que injeta o truststore e
   varre proxy do sistema / variáveis de ambiente / conexão direta.

3. **Versão vinda do `.env`.** O `.env` é do usuário e sobrevive à atualização:
   o app novo continuaria se declarando na versão velha e baixaria a mesma
   atualização para sempre. Por isso a versão vem do BUILD (`_build_info.py`).

4. **Instalar por cima de si mesmo.** O Windows não deixa sobrescrever um `.exe`
   em execução, então o app dispara o instalador e se fecha. Até a v3.1.0 isso
   era uma CORRIDA: o Inno checa o `AppMutex` logo ao abrir e, em modo
   silencioso, responde "Cancelar" sozinho à caixa "feche o aplicativo" - se o
   app ainda estivesse saindo, a atualização abortava em meio segundo e a
   versão antiga ficava (reproduzido no Wine). Agora o instalador espera o app
   sair (`InitializeSetup` no .iss) e avisa quando está pronto (`/SINAL`); só
   então o app se fecha - ver `instalar()`.

═══ Atualização "só do que mudou" (a partir da 3.2.0) ═══
Cada Release publica, além do instalador completo, um instalador PEQUENO por
versão de origem, só com os arquivos que mudaram desde ela (gerado por
`tools/gerar_atualizacao.py`). O `latest.json` lista esses pacotes em
`atualizacoes`, cada um com o `de` (a versão de origem). Se existe uma entrada
com `de` igual à versão instalada, o app baixa o pequeno; senão, o completo.

O pequeno sai em dois formatos (`.zip` e `.exe`), porque na rede da empresa o
proxy cortava o fim de um formato e deixava passar outro. O app tenta zip → exe
→ completo: a cadeia está em `Atualizacao.reserva`, e `baixar()` desce por ela
quando um download falha.

═══ Sobre o token ═══
O repositório é privado, então a consulta exige autenticação. O token é embutido
no build pelo workflow (nunca fica no Git). **Ofuscação não é segurança**: quem
tiver o `.exe` consegue extraí-lo. Por isso ele deve ser um PAT *fine-grained*,
SOMENTE LEITURA (`Contents: Read-only`) e restrito a ESTE repositório - o pior
caso é alguém conseguir ler o código que essa pessoa já recebeu. Ver BUILD.md
(seção "Rotação do token") para trocá-lo.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from . import rede

REPO_OWNER = "luanccozer"
REPO_NOME = "DocManager"
API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NOME}"

# Nome do manifesto publicado junto do instalador (traz versão, SHA256 e notas).
ARQUIVO_MANIFESTO = "latest.json"

# Prefixos dos instaladores no Release - acordo com tools/gerar_atualizacao.py,
# com o .iss (OutputBaseFilename) e com o workflow. O completo é escolhido PELO
# NOME, e não mais como "o primeiro .exe": o pequeno também é um .exe.
PREFIXO_COMPLETO = "DocManager_Itaipu_Setup_"
PREFIXO_PEQUENO = "DocManager_Itaipu_Update_"

# O AppId do .iss já expandido (lá o "{{" inicial é o escape do Inno para "{").
# É o nome da chave de "Aplicativos instalados": `Uninstall\<AppId>_is1`.
APP_ID = "{7C3B2A10-DOCM-4ITA-IPU0-DOCMANAGER01}}"

# Abaixo disto o "instalador" é uma página de erro (HTML de login, JSON da API).
TAMANHO_MINIMO = 1_000_000

Log = Callable[[str], None]
Progresso = Callable[[float], None]


def _nada(_msg) -> None:
    """Log/progresso padrão: silencioso."""


# ─────────────────────────────── versões ────────────────────────────────────

def versao_em_partes(versao: str) -> tuple:
    """'v3.10.2-beta.1' → chave ordenável. Função pura (testada).

    Segue o essencial do SemVer: compara número a número e coloca a pré-versão
    ANTES da versão final (3.1.0-beta < 3.1.0). Entradas estranhas não explodem -
    o que não for número vira 0 , porque uma tag digitada errada no GitHub não
    pode derrubar o app de quem está usando.
    """
    texto = str(versao or "").strip().lstrip("vV")
    nucleo, _, pre = texto.partition("-")
    numeros = [int(p) if p.isdigit() else 0 for p in re.split(r"[.+]", nucleo) if p != ""]
    numeros = (numeros + [0, 0, 0])[:3]
    if not pre:
        return (tuple(numeros), (1,))       # sem pré-versão → vem depois
    partes = tuple((0, int(p), "") if p.isdigit() else (1, 0, p)
                   for p in re.split(r"[.+]", pre) if p != "")
    return (tuple(numeros), (0,) + partes)


def e_mais_nova(remota: str, atual: str) -> bool:
    """True se `remota` for estritamente mais nova que `atual`."""
    try:
        return versao_em_partes(remota) > versao_em_partes(atual)
    except Exception:  # noqa: BLE001 - nunca deixar a comparação derrubar o app
        return False


# ─────────────────────────────── o token ────────────────────────────────────

# O par ofuscar/desofuscar vive em `_ofuscacao.py`, compartilhado com o script de
# build - as duas pontas TÊM que usar o mesmo algoritmo (ver o módulo).
def caminho_token_externo() -> Path:
    """Arquivo opcional para trocar o token SEM refazer o build (ver BUILD.md).

    Fica na mesma pasta de dados do usuário que guarda a config e as credenciais
    (`Documentos\\DocManager_Itaipu` por padrão). Antes esse caminho era montado
    à mão aqui e ignorava o `DOCMANAGER_DADOS_DIR` - o que fazia a suíte de
    testes escrever um token na pasta Documentos DE VERDADE de quem rodasse os
    testes, e esse arquivo passaria a ter precedência sobre o token do build.
    """
    from .credenciais import pasta_dados

    return pasta_dados() / "update_token.txt"


def token() -> str:
    """Token de leitura do repositório, na ordem: variável de ambiente → arquivo
    em Documentos → embutido no build. Devolve '' se não houver nenhum."""
    if (env := os.getenv("DOCMANAGER_UPDATE_TOKEN", "").strip()):
        return env
    try:
        externo = caminho_token_externo()
        if externo.is_file() and (conteudo := externo.read_text(encoding="utf-8").strip()):
            return conteudo
    except Exception:  # noqa: BLE001
        pass
    try:
        from .._ofuscacao import desofuscar
        from .._update_auth import TOKEN_OFUSCADO   # gerado pelo CI (fora do Git)

        return desofuscar(TOKEN_OFUSCADO) if TOKEN_OFUSCADO else ""
    except Exception:  # noqa: BLE001 - build local não tem o módulo: sem update
        return ""


def _cabecalhos(aceitar: str = "application/vnd.github+json") -> dict:
    h = {"Accept": aceitar, "X-GitHub-Api-Version": "2022-11-28",
         "User-Agent": "DocManagerItaipu"}
    if (tok := token()):
        h["Authorization"] = f"Bearer {tok}"
    return h


# ────────────────────────── o que vem do GitHub ─────────────────────────────

@dataclass(frozen=True)
class Atualizacao:
    """Um arquivo a baixar, e o que fazer se ele falhar (`reserva`).

    Quando há instalador pequeno para a versão instalada, `checar` devolve o
    primeiro formato dele; `reserva` aponta o próximo formato e, no fim da
    cadeia, o completo do mesmo Release (que também fica em `completo`)."""
    versao: str
    notas: str
    nome_arquivo: str
    url_asset: str          # endpoint de API - o único que funciona em repo privado
    tamanho: int
    sha256: str             # '' quando o release não publicou o hash
    url_pagina: str
    publicado_em: str = ""
    incremental: bool = False
    formato: str = "completo"         # "zip" | "exe" | "completo"
    sha256_dentro: str = ""           # só no zip: o hash do .exe lá dentro
    tamanho_completo: int = 0
    prerelease: bool = False
    completo: Atualizacao | None = None
    reserva: Atualizacao | None = None

    @property
    def tamanho_mb(self) -> float:
        return round(self.tamanho / (1024 * 1024), 1) if self.tamanho else 0.0

    @property
    def tamanho_completo_mb(self) -> float:
        return round(self.tamanho_completo / (1024 * 1024), 1) if self.tamanho_completo else 0.0

    def tentativas(self) -> list[Atualizacao]:
        """Os arquivos na ordem em que `baixar()` tenta: este e as reservas."""
        saida, atual = [], self
        while atual is not None:
            saida.append(atual)
            atual = atual.reserva
        return saida


def _asset(release: dict, nome: str) -> dict | None:
    return next((a for a in release.get("assets", []) if a.get("name") == nome), None)


def _instalador(release: dict, manifesto: dict | None = None) -> dict | None:
    """O asset do instalador COMPLETO.

    Pelo prefixo do nome; senão o `arquivo` do latest.json; senão (Releases
    antigos, de nome diferente) o primeiro `.exe` que não seja um pequeno. O
    app até a 3.1.1 pegava "o primeiro .exe" e só: com o pequeno também sendo
    `.exe`, podia baixar o pacote errado.
    """
    exes = [a for a in release.get("assets", [])
            if str(a.get("name", "")).lower().endswith(".exe")]
    for asset in exes:
        if str(asset.get("name", "")).startswith(PREFIXO_COMPLETO):
            return asset
    if manifesto and (pelo_nome := _asset(release, str(manifesto.get("arquivo", "")))):
        return pelo_nome
    return next((a for a in exes if not str(a.get("name", "")).startswith(PREFIXO_PEQUENO)),
                None)


def _sha(texto) -> str:
    return str(texto or "").strip().lower()


def _entrada_para(manifesto: dict | None, versao_atual: str) -> dict | None:
    """A entrada de `atualizacoes` cujo `de` é a versão instalada."""
    alvo = str(versao_atual or "").strip().lstrip("vV")
    if not manifesto or not alvo:
        return None
    for entrada in manifesto.get("atualizacoes") or []:
        if isinstance(entrada, dict) and str(entrada.get("de", "")).strip().lstrip("vV") == alvo:
            return entrada
    return None


def interpretar_release(release: dict, manifesto: dict | None = None,
                        versao_atual: str = "") -> Atualizacao | None:
    """Monta a `Atualizacao` a partir do JSON do release. Pura - testada.

    O SHA256 do completo vem, em ordem: do `latest.json` publicado junto; senão
    do campo `digest` que a própria API do GitHub devolve; senão fica vazio (o
    download ainda acontece, mas `baixar()` avisa que não deu para conferir).

    Com `versao_atual` e uma entrada de `atualizacoes` para ela, devolve o
    pequeno (zip, com o exe e o completo de reserva). Pequeno sem SHA256 não é
    oferecido: um pacote parcial errado estraga a instalação.
    """
    asset = _instalador(release, manifesto)
    if asset is None:
        return None
    sha = ""
    if manifesto and str(manifesto.get("arquivo", asset.get("name"))) == asset.get("name"):
        sha = _sha(manifesto.get("sha256"))
    if not sha:
        digest = str(asset.get("digest", "") or "")
        if digest.lower().startswith("sha256:"):
            sha = _sha(digest.split(":", 1)[1])
    notas = (manifesto or {}).get("notas") or release.get("body") or ""
    tamanho = int(asset.get("size") or 0)
    completo = Atualizacao(
        versao=str(release.get("tag_name", "")).lstrip("vV"),
        notas=str(notas).strip(),
        nome_arquivo=str(asset.get("name", "")),
        url_asset=str(asset.get("url", "")),
        tamanho=tamanho,
        sha256=sha,
        url_pagina=str(release.get("html_url", "")),
        publicado_em=str(release.get("published_at", "") or "")[:10],
        tamanho_completo=tamanho,
        prerelease=bool(release.get("prerelease")),
    )

    entrada = _entrada_para(manifesto, versao_atual)
    if entrada is None:
        return completo
    atual = completo
    # Monta a cadeia de trás para a frente: exe → (reserva) completo, depois
    # zip → (reserva) exe. Quem chama recebe o zip.
    for formato, dados in (("exe", entrada), ("zip", entrada.get("zip"))):
        if not isinstance(dados, dict):
            continue
        pequeno = _asset(release, str(dados.get("arquivo", "")))
        sha_pequeno = _sha(dados.get("sha256"))
        if pequeno is None or not sha_pequeno:
            continue
        if formato == "zip" and not _sha(dados.get("sha256_dentro")):
            continue
        atual = replace(
            completo, nome_arquivo=str(pequeno.get("name", "")),
            url_asset=str(pequeno.get("url", "")),
            tamanho=int(pequeno.get("size") or dados.get("tamanho") or 0),
            sha256=sha_pequeno, incremental=True, formato=formato,
            sha256_dentro=_sha(dados.get("sha256_dentro")) if formato == "zip" else "",
            completo=completo, reserva=atual)
    return atual


class SemToken(RuntimeError):
    """O build não tem token - checar atualização é impossível neste repositório."""


def escolher_release(releases: list[dict]) -> dict | None:
    """Canal de testes: o Release de versão mais alta, pré-lançamento inclusive
    (rascunho não). Pura - testada."""
    validos = [r for r in releases or []
               if isinstance(r, dict) and not r.get("draft") and r.get("tag_name")]
    return max(validos, key=lambda r: versao_em_partes(r["tag_name"]), default=None)


def versao_registrada_no_windows() -> str:
    """A versão que o instalador gravou em "Aplicativos instalados" ('' se não
    der para ler). O pequeno confere a mesma coisa e desiste se não bater; aqui
    serve para nem oferecê-lo - senão a pessoa clicaria, o app fecharia e
    reabriria sem atualizar, toda vez."""
    if os.name != "nt":
        return ""
    try:
        import winreg

        chave = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1"
        locais = [(winreg.HKEY_CURRENT_USER, 0),
                  (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY),
                  (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY)]
        pasta = pasta_instalacao()
        for raiz, visao in locais:
            try:
                with winreg.OpenKey(raiz, chave, 0, winreg.KEY_READ | visao) as k:
                    local = str(winreg.QueryValueEx(k, "InstallLocation")[0] or "")
                    if pasta is not None and local and \
                            Path(local).resolve() != pasta.resolve():
                        continue   # outra instalação (a "para todos" e a "só para mim")
                    return str(winreg.QueryValueEx(k, "DisplayVersion")[0] or "")
            except OSError:
                continue
    except Exception:  # noqa: BLE001 - na dúvida, o próprio instalador confere
        pass
    return ""


def checar(versao_atual: str, *, canal_testes: bool = False,
           log_cb: Log = _nada) -> Atualizacao | None:
    """Devolve a `Atualizacao` se houver versão mais nova; `None` se já está em dia.

    `canal_testes` (as "Versões de teste" das Configurações) considera também os
    pré-lançamentos; desligado, vale só o `/releases/latest`, que o GitHub já
    devolve sem pré-lançamento.

    Levanta `SemToken` (build sem token, ou token recusado pelo GitHub) ou
    `rede.FalhaDeRede` (rede/Zscaler). Quem chama decide se mostra o erro ou
    engole - a checagem automática engole, o botão "Procurar atualizações" mostra.
    """
    if not token():
        raise SemToken(
            "Este build não tem token de atualização embutido (build local ou "
            "segredo ausente no workflow). Baixe a versão nova manualmente pela "
            "página de Releases do projeto.")

    log_cb("Procurando atualizações" + (" (com as versões de teste)..." if canal_testes else "..."))
    url = f"{API}/releases?per_page=20" if canal_testes else f"{API}/releases/latest"
    # 401/403/404 são respostas VÁLIDAS do GitHub, não falhas de rota: entram no
    # `status_ok` para virarem uma mensagem que diz o que fazer, em vez do
    # "nenhuma rota funcionou" genérico que a cascata devolveria.
    sessao, resp = rede.abrir(url, headers=_cabecalhos(), timeout=20, log_cb=log_cb,
                              status_ok=(200, 401, 403, 404))
    # Uma sessão só para a consulta E para o manifesto: a rota que funcionou já
    # foi descoberta, não faz sentido redescobri-la (e talvez cair em outra).
    try:
        try:
            if resp.status_code in (401, 403):
                raise SemToken(
                    "O GitHub recusou o token de atualização deste build "
                    f"(HTTP {resp.status_code}). Ele provavelmente expirou ou perdeu "
                    "o acesso ao repositório. Baixe a versão nova manualmente pela "
                    "página de Releases e avise o responsável pelo build.")
            if resp.status_code == 404:
                # Sem release publicado ainda, ou o token não enxerga o
                # repositório: num repo privado o GitHub responde 404, e não 403,
                # para quem não tem acesso - daí as duas hipóteses na mensagem.
                log_cb("Nenhum release publicado ainda (ou o token não tem acesso "
                       "ao repositório).")
                return None
            dados = resp.json()
        finally:
            resp.close()

        release = escolher_release(dados) if canal_testes else dados
        if not release:
            log_cb("O GitHub não devolveu nenhum release publicado.")
            return None
        versao_remota = str(release.get("tag_name", "")).lstrip("vV")
        if not versao_remota:
            log_cb("O GitHub não devolveu nenhum release publicado.")
            return None
        if not e_mais_nova(versao_remota, versao_atual):
            log_cb(f"Você já está na versão mais recente (v{versao_atual}).")
            return None

        # Manifesto é opcional: sem ele, o SHA256 vem do `digest` da própria API
        # e não há instalador pequeno.
        manifesto = None
        if (asset_manifesto := _asset(release, ARQUIVO_MANIFESTO)) is not None:
            try:
                r = sessao.get(asset_manifesto["url"],
                               headers=_cabecalhos("application/octet-stream"),
                               timeout=20)
                if r.status_code == 200:
                    manifesto = json.loads(r.content.decode("utf-8-sig"))  # tolera BOM
                r.close()
            except Exception as e:  # noqa: BLE001 - manifesto é um extra
                log_cb(f"(não foi possível ler o {ARQUIVO_MANIFESTO}: {e})")
    finally:
        sessao.close()

    base_pequeno = versao_atual
    if (registrada := versao_registrada_no_windows()) and registrada != versao_atual:
        log_cb(f"(o Windows registra a v{registrada} instalada, e este programa é a "
               f"v{versao_atual}: vai o instalador completo)")
        base_pequeno = ""
    info = interpretar_release(release, manifesto, base_pequeno)
    if info is None:
        log_cb(f"O release v{versao_remota} existe, mas não tem instalador (.exe) "
               f"publicado. Avise o responsável pelo build.")
        return None
    if info.incremental:
        log_cb(f"Nova versão disponível: v{info.versao} ({info.tamanho_mb} MB, só o que "
               f"mudou; o completo tem {info.tamanho_completo_mb} MB).")
    else:
        log_cb(f"Nova versão disponível: v{info.versao} ({info.tamanho_mb} MB).")
    return info


# ──────────────────────────── baixar e instalar ─────────────────────────────

def pasta_download() -> Path:
    p = Path(tempfile.gettempdir()) / "DocManager_Update"
    p.mkdir(parents=True, exist_ok=True)
    return p


class HashDivergente(RuntimeError):
    """O arquivo baixado não bate com o SHA256 publicado - não pode ser executado."""


class DownloadIncompleto(HashDivergente):
    """Veio menos que o anunciado: conexão (ou proxy) cortou o fim do arquivo."""


class PacoteInvalido(HashDivergente):
    """O `.zip` do pequeno não tem exatamente o instalador esperado dentro."""


def limpar_pasta_download() -> None:
    """Apaga instaladores de tentativas anteriores (o log fica, para diagnóstico)."""
    for arquivo in pasta_download().iterdir():
        if arquivo.suffix.lower() in (".exe", ".zip", ".part"):
            try:
                arquivo.unlink()
            except OSError:
                pass   # um instalador velho ainda aberto: fica para a próxima


def _vale_tentar_outro(erro: Exception) -> bool:
    """Falha do ARQUIVO (cortado, hash errado, rede) → tenta o próximo formato.
    Falha do DISCO (sem espaço, sem permissão) → o próximo falharia igual."""
    try:
        import requests

        if isinstance(erro, requests.RequestException):
            return True
    except ImportError:
        pass
    return isinstance(erro, (HashDivergente, rede.FalhaDeRede))


def baixar(info: Atualizacao, *, progresso_cb: Progresso = _nada, log_cb: Log = _nada,
           ao_cair_no_completo: Callable[[Atualizacao, Exception], None] | None = None) -> Path:
    """Baixa o instalador e confere o SHA256. Devolve o caminho do `.exe`.

    Se o pequeno falhar (download cortado, SHA errado, rede), tenta o formato
    reserva e, no fim, o completo - avisando por `ao_cair_no_completo`. Não
    tenta remendar o pedaço que faltou: começa o próximo arquivo do zero. Erro
    de disco não troca de arquivo.
    """
    limpar_pasta_download()
    atual = info
    while True:
        try:
            return _baixar_um(atual, progresso_cb=progresso_cb, log_cb=log_cb)
        except Exception as e:  # noqa: BLE001 - decide abaixo se vale insistir
            if atual.reserva is None or not _vale_tentar_outro(e):
                raise
            proximo = atual.reserva
            log_cb(f"O download de {atual.nome_arquivo} falhou ({e}). "
                   f"Tentando {proximo.nome_arquivo}...")
            if not proximo.incremental and ao_cair_no_completo is not None:
                ao_cair_no_completo(proximo, e)
            progresso_cb(0.0)
            atual = proximo


def _baixar_arquivo(info: Atualizacao, destino: Path, *, progresso_cb: Progresso,
                    log_cb: Log) -> str:
    """Grava `destino` (via `.part`) e devolve o SHA256 calculado no caminho.

    Usa o endpoint de API do asset (não o `browser_download_url`): em repositório
    privado só ele entrega o binário - ver o item 1 do cabeçalho do módulo.
    """
    log_cb(f"Baixando {info.nome_arquivo} ({info.tamanho_mb} MB)...")
    sessao, resp = rede.abrir(info.url_asset, headers=_cabecalhos("application/octet-stream"),
                              timeout=60, stream=True, log_cb=log_cb)
    parcial = destino.with_suffix(destino.suffix + ".part")
    try:
        total = int(resp.headers.get("Content-Length") or info.tamanho or 0)
        baixado = 0
        ultimo = -1
        digest = hashlib.sha256()
        with open(parcial, "wb") as f:
            for bloco in resp.iter_content(chunk_size=256 * 1024):
                if not bloco:
                    continue
                f.write(bloco)
                digest.update(bloco)
                baixado += len(bloco)
                # Só avisa quando o percentual muda: mil callbacks por segundo
                # entupiriam a fila da interface.
                if total and (pct := int(min(baixado / total, 1.0) * 100)) != ultimo:
                    ultimo = pct
                    progresso_cb(pct / 100)
    except BaseException:
        parcial.unlink(missing_ok=True)
        raise
    finally:
        resp.close()
        sessao.close()

    # Um HTML de login (repo privado acessado sem token) tem alguns KB - um
    # instalador tem MB. Barra o "download que deu certo" enganoso.
    if baixado < TAMANHO_MINIMO:
        parcial.unlink(missing_ok=True)
        raise HashDivergente(
            f"O arquivo baixado é pequeno demais para ser o instalador "
            f"({baixado} bytes). Isso costuma ser uma página de erro no "
            f"lugar do binário - token de atualização inválido ou expirado.")
    if total and baixado < total:
        parcial.unlink(missing_ok=True)
        raise DownloadIncompleto(
            f"O download de {info.nome_arquivo} parou em {baixado} de {total} bytes "
            f"(a conexão ou o proxy cortou o fim).")

    obtido = digest.hexdigest()
    if info.sha256:
        if obtido != info.sha256:
            parcial.unlink(missing_ok=True)
            raise HashDivergente(
                f"O arquivo baixado não confere com o publicado.\n"
                f"  esperado: {info.sha256}\n  obtido:   {obtido}\n"
                f"Baixe manualmente pela página do Release.")
        log_cb("Integridade conferida (SHA256 confere).")
    else:
        log_cb("⚠️ O release não publicou o SHA256 - não deu para conferir a "
               "integridade do arquivo.")
    destino.unlink(missing_ok=True)
    parcial.rename(destino)
    return obtido


def extrair_do_zip(zip_path: Path, sha256_dentro: str) -> Path:
    """O `.exe` de dentro do zip do pequeno, conferido. Pura o bastante para teste.

    Recusa zip corrompido, mais de um membro, nome com pasta (um `../` no nome
    escreveria fora da pasta de download) e hash que não bate."""
    import zipfile

    try:
        with zipfile.ZipFile(zip_path) as z:
            membros = z.infolist()
            if len(membros) != 1:
                raise PacoteInvalido(f"O pacote {zip_path.name} deveria ter 1 arquivo e tem "
                                     f"{len(membros)}.")
            nome = membros[0].filename
            if "/" in nome or "\\" in nome or ".." in nome or not nome.lower().endswith(".exe"):
                raise PacoteInvalido(f"Nome inesperado dentro de {zip_path.name}: {nome!r}.")
            destino = zip_path.parent / nome
            digest = hashlib.sha256()
            parcial = destino.with_suffix(".exe.part")
            with z.open(membros[0]) as origem, open(parcial, "wb") as f:
                for bloco in iter(lambda: origem.read(1024 * 1024), b""):
                    f.write(bloco)
                    digest.update(bloco)
    except zipfile.BadZipFile as e:
        raise PacoteInvalido(f"O pacote {zip_path.name} está corrompido ({e}).") from e
    if digest.hexdigest() != sha256_dentro:
        parcial.unlink(missing_ok=True)
        raise HashDivergente(f"O instalador de dentro de {zip_path.name} não confere com "
                             f"o publicado.")
    destino.unlink(missing_ok=True)
    parcial.rename(destino)
    zip_path.unlink(missing_ok=True)
    return destino


def _baixar_um(info: Atualizacao, *, progresso_cb: Progresso, log_cb: Log) -> Path:
    destino = pasta_download() / Path(info.nome_arquivo).name
    _baixar_arquivo(info, destino, progresso_cb=progresso_cb, log_cb=log_cb)
    if info.formato == "zip":
        destino = extrair_do_zip(destino, info.sha256_dentro)
    progresso_cb(1.0)
    log_cb(f"Download concluído: {destino}")
    return destino


def empacotado() -> bool:
    """True quando rodando como .exe do PyInstaller (fora disso não há o que instalar)."""
    return bool(getattr(sys, "frozen", False))


def pasta_instalacao() -> Path | None:
    return Path(sys.executable).parent if empacotado() else None


def precisa_elevacao() -> bool:
    """True se a pasta de instalação exigir administrador para ser sobrescrita.

    Serve só para AVISAR que o Windows vai pedir a permissão - quem a pede é o
    próprio instalador. Testa ESCREVENDO de verdade: no Windows,
    `os.access(..., W_OK)` mente para Program Files (devolve True mesmo sem
    permissão) por causa da virtualização de arquivos herdada do XP.
    """
    pasta = pasta_instalacao()
    if pasta is None:
        return False
    try:
        teste = pasta / ".docmanager_write_test"
        teste.touch()
        teste.unlink()
        return False
    except Exception:  # noqa: BLE001 - sem permissão (ou pasta somente leitura)
        return True


# /SILENT mostra só a barra de progresso. /CLOSEAPPLICATIONS deixa o Restart
# Manager fechar o que ainda estiver usando os arquivos. /REABRIR (do nosso .iss)
# reabre o DocManager no fim; /RESTARTAPPLICATIONS fica pelo mesmo motivo, é o
# sinal que o instalador entende vindo do app 3.1.0.
ARGS_INSTALADOR = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                   "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS", "/REABRIR"]

# Quanto esperar o instalador ficar pronto. Cobre o tempo de a pessoa ler e
# confirmar o pedido de permissão do Windows (UAC).
ESPERA_INSTALADOR_S = 15 * 60


class InstaladorNaoIniciou(RuntimeError):
    """O instalador terminou (ou não respondeu) antes de ficar pronto - a
    atualização não aconteceu e o app deve continuar aberto para avisar."""


def instalar(caminho: Path, *, log_cb: Log = _nada,
             espera_s: float = ESPERA_INSTALADOR_S) -> None:
    """Dispara o instalador e ESPERA ele ficar pronto; então quem chama FECHA o app.

    O instalador é disparado SEM elevação: quando a instalação é para todos os
    usuários, ele mesmo pede a permissão de administrador (o Inno é `asInvoker`
    e se reabre elevado). Isso deixa o app reaberto no fim rodar na conta de
    quem o usava - com "Executar como administrador" feito pelo app, a conta
    podia ser a do administrador que digitou a senha.

    "Pronto" é o instalador ter criado o arquivo passado em `/SINAL`: ele já
    passou pelo UAC e está esperando o DocManager sair para trocar os arquivos.
    Se o instalador terminar antes disso - permissão recusada, antivírus - ou
    não responder em `espera_s`, levanta `InstaladorNaoIniciou`, e o app segue
    aberto. Fechar o app ANTES de o instalador estar pronto era a corrida que
    abortava a atualização da v3.1.0.
    """
    caminho = Path(caminho)
    pasta = pasta_download()
    sinal = pasta / "instalador_pronto.txt"
    sinal.unlink(missing_ok=True)
    args = [str(caminho), *ARGS_INSTALADOR,
            f"/LOG={pasta / 'instalacao.log'}", f"/SINAL={sinal}"]
    flags = 0
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: o instalador sobrevive
        # ao fechamento do app.
        flags = 0x00000008 | 0x00000200
    if precisa_elevacao():
        log_cb("O Windows vai pedir permissão de administrador (o DocManager está "
               "instalado para todos os usuários). Confirme na janela dele.")
    try:
        processo = subprocess.Popen(args, close_fds=True, creationflags=flags)
    except OSError as e:
        raise InstaladorNaoIniciou(
            f"O Windows não deixou abrir o instalador ({e}). Rode manualmente: {caminho}") from e

    inicio = time.monotonic()
    while not sinal.exists():
        if (codigo := processo.poll()) is not None:
            raise InstaladorNaoIniciou(
                f"O instalador terminou antes de começar (código {codigo}). Se o "
                f"Windows pediu permissão de administrador, ela precisa ser "
                f"confirmada. Detalhes em {pasta / 'instalacao.log'}.")
        if time.monotonic() - inicio > espera_s:
            raise InstaladorNaoIniciou(
                "O instalador não respondeu a tempo. Se a janela de permissão do "
                "Windows ficou aberta, confirme-a e feche o DocManager.")
        time.sleep(0.2)
    log_cb("Instalador pronto. O DocManager vai fechar e abrir de novo já atualizado.")


# ─────────────────────── política: quando checar, o que pular ───────────────
#
# A checagem automática precisa ser DISCRETA: nunca atrasar a abertura do app,
# nunca insistir numa versão que a pessoa mandou pular e nunca bater no GitHub a
# cada duplo-clique. Estas funções guardam essas decisões em um lugar só, para a
# interface não ter que lembrar delas.

INTERVALO_PADRAO_HORAS = 6


def motivo_para_nao_verificar() -> str:
    """Por que ESTA cópia não se atualiza sozinha ('' = ela se atualiza).

    Só se atualiza o programa empacotado, instalado pelo instalador (há um
    `unins*.exe` ao lado do `.exe`) e com token. Numa pasta copiada, rodar o
    instalador criaria uma SEGUNDA instalação em outro lugar, e a cópia que a
    pessoa usa ficaria velha."""
    if not empacotado():
        return ("Esta cópia roda pelo código-fonte, não é o programa instalado. A "
                "atualização automática vale só para o DocManager instalado pelo "
                "instalador.")
    pasta = pasta_instalacao()
    if pasta is not None and not any(pasta.glob("unins*.exe")):
        return ("Esta cópia do DocManager não foi instalada pelo instalador (é uma "
                "pasta copiada): atualizar por aqui criaria uma segunda instalação. "
                "Instale pelo DocManager_Itaipu_Setup da página de Releases.")
    if not token():
        return ("Este build não tem token de atualização embutido (foi gerado "
                "localmente). Baixe as versões novas pela página de Releases.")
    return ""


def deve_verificar(config, *, intervalo_horas: int = INTERVALO_PADRAO_HORAS) -> bool:
    """True se é hora de perguntar ao GitHub (checagem AUTOMÁTICA).

    Desligada nas Configurações, cópia que não se atualiza
    (`motivo_para_nao_verificar`), ou consultada há menos de `intervalo_horas`
    → False. A abertura do app passa `intervalo_horas=0`: toda abertura
    pergunta, porque uma requisição por abertura fica muito abaixo do limite do
    token. O botão "Procurar atualizações" chama `checar()` direto.
    """
    from datetime import datetime, timedelta

    try:
        s = config.settings
    except Exception:  # noqa: BLE001
        return False
    if not s.verificar_atualizacoes or motivo_para_nao_verificar():
        return False
    if not s.ultima_verificacao or intervalo_horas <= 0:
        return True
    try:
        ultima = datetime.fromisoformat(s.ultima_verificacao)
    except ValueError:
        return True
    return datetime.now() - ultima >= timedelta(hours=intervalo_horas)


def canal_de_testes(config) -> bool:
    try:
        return bool(config.settings.versoes_de_teste)
    except Exception:  # noqa: BLE001
        return False


def registrar_verificacao(config) -> None:
    from datetime import datetime

    try:
        config.set_setting("ultima_verificacao", datetime.now().isoformat(timespec="seconds"))
    except Exception:  # noqa: BLE001 - não poder gravar não pode quebrar a checagem
        pass


def ignorar_versao(config, versao: str) -> None:
    """Silencia UMA versão. A próxima que sair volta a avisar - de propósito:
    'pular' não pode virar 'nunca mais me avise' sem a pessoa perceber."""
    try:
        config.set_setting("versao_ignorada", str(versao))
    except Exception:  # noqa: BLE001
        pass


def esta_ignorada(config, versao: str) -> bool:
    try:
        return config.settings.versao_ignorada.strip() == str(versao).strip()
    except Exception:  # noqa: BLE001
        return False


def verificar_em_segundo_plano(config, versao_atual: str, ao_encontrar,
                               *, log_cb: Log = _nada, forcar: bool = False,
                               intervalo_horas: int = INTERVALO_PADRAO_HORAS) -> None:
    """Dispara a checagem numa thread e chama `ao_encontrar(info)` se houver novidade.

    Nunca levanta exceção: numa checagem automática, rede indisponível ou build
    sem token são silêncio no log - o app segue como se nada fosse. Quem quer o
    erro na tela (botão "Procurar atualizações") usa `checar()` diretamente.

    `ao_encontrar` roda NA THREAD DE FUNDO: quem passa o callback é responsável
    por voltar para a thread da interface (`widget.after(0, ...)`).
    """
    import threading

    if not forcar and not deve_verificar(config, intervalo_horas=intervalo_horas):
        return

    def _trabalho():
        try:
            info = checar(versao_atual, canal_testes=canal_de_testes(config), log_cb=log_cb)
        except (SemToken, rede.FalhaDeRede) as e:
            log_cb(f"(verificação de atualização adiada: {e})")
            return
        except Exception as e:  # noqa: BLE001
            log_cb(f"(falha ao verificar atualizações: {e})")
            return
        registrar_verificacao(config)
        if info is None:
            return
        if not forcar and esta_ignorada(config, info.versao):
            log_cb(f"(v{info.versao} foi marcada como 'pular' - sem aviso)")
            return
        ao_encontrar(info)

    threading.Thread(target=_trabalho, daemon=True).start()
