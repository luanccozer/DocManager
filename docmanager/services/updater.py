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

═══ Atualização pequena: o método da CMI Suite (a partir da 3.4.0) ═══
Cada Release publica, além do instalador completo, o `arquivos.json` (cada
arquivo instalado com o SHA256) e um zip por versão de origem,
`DocManager_Itaipu_Atualizacao_<de>_para_<para>.zip`, só com o que mudou desde
ela. Se existe o zip saindo EXATAMENTE da versão instalada e a pasta do
programa aceita escrita (instalação "só para mim"), o app o aplica COM ELE
ABERTO - ver `services/pacote.py` -, confere cada arquivo contra o
`arquivos.json` novo e se reabre. Sem instalador, sem UAC, sem corrida com o
mutex. Qualquer falha desfaz tudo e a janela cai para o instalador completo.

Até a 3.3.0 o pequeno era um instalador Inno à parte (zip → exe → completo,
listado em `atualizacoes` no latest.json). Os zips novos vão em `pequenas`, e
`atualizacoes` não é mais publicado: um app 3.3.0 que lesse um zip novo ali o
rodaria como instalador. Sem a lista, ele baixa o completo, como sempre.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import pacote, rede

REPO_OWNER = "luanccozer"
REPO_NOME = "DocManager"
API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NOME}"

# Nome do manifesto publicado junto do instalador (traz versão, SHA256 e notas).
ARQUIVO_MANIFESTO = "latest.json"

# O retrato de cada versão (ver services/pacote.py), publicado em todo Release.
ARQUIVO_ARQUIVOS = "arquivos.json"

# Prefixo do instalador completo no Release - acordo com o workflow. O completo
# é escolhido PELO NOME. O PEQUENO é o prefixo dos instaladores pequenos Inno
# da 3.2.0-3.3.0: um Release antigo ainda os tem, e eles nunca são o completo.
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
class Pacote:
    """Um arquivo da atualização pequena no Release (o zip ou o arquivos.json)."""
    nome: str
    url: str                # endpoint de API - o único que funciona em repo privado
    tamanho: int
    sha256: str             # nunca vazio: pequena sem SHA256 não é oferecida


@dataclass(frozen=True)
class Atualizacao:
    """O instalador completo do Release e, quando há, a atualização pequena
    saindo da versão instalada (`pequena` + `arquivos`)."""
    versao: str
    notas: str
    nome_arquivo: str
    url_asset: str          # endpoint de API - o único que funciona em repo privado
    tamanho: int
    sha256: str             # '' quando o release não publicou o hash
    url_pagina: str
    publicado_em: str = ""
    prerelease: bool = False
    pequena: Pacote | None = None
    arquivos: Pacote | None = None

    @property
    def tamanho_mb(self) -> float:
        return round(self.tamanho / (1024 * 1024), 1) if self.tamanho else 0.0

    @property
    def tem_pequena(self) -> bool:
        return self.pequena is not None and self.arquivos is not None


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


def _sha_do_asset(asset: dict) -> str:
    """O SHA256 que a própria API do GitHub devolve no campo `digest`."""
    digest = str(asset.get("digest", "") or "")
    return _sha(digest.split(":", 1)[1]) if digest.lower().startswith("sha256:") else ""


def _pacote(release: dict, nome: str, sha_publicado: str = "") -> Pacote | None:
    """O asset `nome` com o SHA256 (o do latest.json, senão o `digest`). None
    se não existe ou não tem SHA256: nunca se aplica o que não deu para conferir."""
    asset = _asset(release, nome)
    if asset is None:
        return None
    sha = _sha(sha_publicado) or _sha_do_asset(asset)
    if not sha:
        return None
    return Pacote(nome=nome, url=str(asset.get("url", "")),
                  tamanho=int(asset.get("size") or 0), sha256=sha)


def _pequena(release: dict, manifesto: dict | None, de: str, para: str):
    """(zip, arquivos.json) da atualização pequena de `de` para `para`, ou (None, None)."""
    de = str(de or "").strip().lstrip("vV")
    if not de:
        return None, None
    nome = pacote.nome_pacote(de, para)
    entrada = next((e for e in (manifesto or {}).get("pequenas") or []
                    if isinstance(e, dict) and e.get("arquivo") == nome), {})
    sha_arquivos = ((manifesto or {}).get("arquivos_json") or {})
    zip_ = _pacote(release, nome, entrada.get("sha256", ""))
    arquivos = _pacote(release, ARQUIVO_ARQUIVOS,
                       sha_arquivos.get("sha256", "") if isinstance(sha_arquivos, dict) else "")
    if zip_ is None or arquivos is None:
        return None, None
    return zip_, arquivos


def interpretar_release(release: dict, manifesto: dict | None = None,
                        versao_atual: str = "") -> Atualizacao | None:
    """Monta a `Atualizacao` a partir do JSON do release. Pura - testada.

    O SHA256 do completo vem, em ordem: do `latest.json` publicado junto; senão
    do campo `digest` que a própria API do GitHub devolve; senão fica vazio (o
    download ainda acontece, mas `baixar()` avisa que não deu para conferir).

    Com `versao_atual`, procura também a atualização pequena saindo dela (o zip
    e o arquivos.json, os dois com SHA256).
    """
    asset = _instalador(release, manifesto)
    if asset is None:
        return None
    sha = ""
    if manifesto and str(manifesto.get("arquivo", asset.get("name"))) == asset.get("name"):
        sha = _sha(manifesto.get("sha256"))
    sha = sha or _sha_do_asset(asset)
    notas = (manifesto or {}).get("notas") or release.get("body") or ""
    versao = str(release.get("tag_name", "")).lstrip("vV")
    pequena, arquivos = _pequena(release, manifesto, versao_atual, versao)
    return Atualizacao(
        versao=versao,
        notas=str(notas).strip(),
        nome_arquivo=str(asset.get("name", "")),
        url_asset=str(asset.get("url", "")),
        tamanho=int(asset.get("size") or 0),
        sha256=sha,
        url_pagina=str(release.get("html_url", "")),
        publicado_em=str(release.get("published_at", "") or "")[:10],
        prerelease=bool(release.get("prerelease")),
        pequena=pequena,
        arquivos=arquivos,
    )


class SemToken(RuntimeError):
    """O build não tem token - checar atualização é impossível neste repositório."""


def escolher_release(releases: list[dict]) -> dict | None:
    """Canal de testes: o Release de versão mais alta, pré-lançamento inclusive
    (rascunho não). Pura - testada."""
    validos = [r for r in releases or []
               if isinstance(r, dict) and not r.get("draft") and r.get("tag_name")]
    return max(validos, key=lambda r: versao_em_partes(r["tag_name"]), default=None)


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

        # Manifesto é opcional: sem ele, os SHA256 vêm do `digest` da própria API.
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

    info = interpretar_release(release, manifesto, versao_atual)
    if info is None:
        log_cb(f"O release v{versao_remota} existe, mas não tem instalador (.exe) "
               f"publicado. Avise o responsável pelo build.")
        return None
    pequena = f"; atualização pequena: {_mb(info.pequena.tamanho)} MB" if info.tem_pequena else ""
    log_cb(f"Nova versão disponível: v{info.versao} (instalador completo: "
           f"{info.tamanho_mb} MB{pequena}).")
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


def limpar_pasta_download() -> None:
    """Apaga downloads de tentativas anteriores (o log fica, para diagnóstico)."""
    for arquivo in pasta_download().iterdir():
        if arquivo.suffix.lower() in (".exe", ".zip", ".json", ".part"):
            try:
                arquivo.unlink()
            except OSError:
                pass   # um instalador velho ainda aberto: fica para a próxima


def _mb(tamanho: int) -> float:
    return round(tamanho / (1024 * 1024), 1) if tamanho else 0.0


def baixar(info: Atualizacao, *, progresso_cb: Progresso = _nada, log_cb: Log = _nada) -> Path:
    """Baixa o instalador COMPLETO e confere o SHA256. Devolve o caminho do `.exe`."""
    limpar_pasta_download()
    destino = pasta_download() / Path(info.nome_arquivo).name
    _baixar_arquivo(info.nome_arquivo, info.url_asset, info.tamanho, info.sha256, destino,
                    progresso_cb=progresso_cb, log_cb=log_cb)
    progresso_cb(1.0)
    log_cb(f"Download concluído: {destino}")
    return destino


def _baixar_arquivo(nome: str, url: str, tamanho: int, sha256: str, destino: Path, *,
                    progresso_cb: Progresso, log_cb: Log,
                    minimo: int = TAMANHO_MINIMO) -> str:
    """Grava `destino` (via `.part`) e devolve o SHA256 calculado no caminho.

    Usa o endpoint de API do asset (não o `browser_download_url`): em repositório
    privado só ele entrega o binário - ver o item 1 do cabeçalho do módulo.
    `minimo` barra a página de erro no lugar do instalador; o arquivos.json e o
    zip pequeno não precisam dele, porque o SHA256 deles é obrigatório.
    """
    log_cb(f"Baixando {nome} ({_mb(tamanho)} MB)...")
    sessao, resp = rede.abrir(url, headers=_cabecalhos("application/octet-stream"),
                              timeout=60, stream=True, log_cb=log_cb)
    parcial = destino.with_suffix(destino.suffix + ".part")
    try:
        total = int(resp.headers.get("Content-Length") or tamanho or 0)
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
    if baixado < minimo:
        parcial.unlink(missing_ok=True)
        raise HashDivergente(
            f"O arquivo baixado é pequeno demais para ser o instalador "
            f"({baixado} bytes). Isso costuma ser uma página de erro no "
            f"lugar do binário - token de atualização inválido ou expirado.")
    if total and baixado < total:
        parcial.unlink(missing_ok=True)
        raise DownloadIncompleto(
            f"O download de {nome} parou em {baixado} de {total} bytes "
            f"(a conexão ou o proxy cortou o fim).")

    obtido = digest.hexdigest()
    if sha256:
        if obtido != sha256:
            parcial.unlink(missing_ok=True)
            raise HashDivergente(
                f"O arquivo baixado não confere com o publicado.\n"
                f"  esperado: {sha256}\n  obtido:   {obtido}\n"
                f"Baixe manualmente pela página do Release.")
        log_cb("Integridade conferida (SHA256 confere).")
    else:
        log_cb("⚠️ O release não publicou o SHA256 - não deu para conferir a "
               "integridade do arquivo.")
    destino.unlink(missing_ok=True)
    parcial.rename(destino)
    return obtido


# ───────────────────────── a atualização pequena ────────────────────────────

def pode_pequena(info: Atualizacao, pasta: Path | None = None) -> bool:
    """A pequena vale quando o Release tem o zip saindo da versão instalada e a
    pasta do programa aceita escrita (instalação "só para mim"). Para todos os
    usuários (Program Files) só o instalador, que pede a permissão, consegue."""
    pasta = pasta if pasta is not None else pasta_instalacao()
    return info.tem_pequena and pasta is not None and _gravavel(pasta)


def _gravavel(pasta: Path) -> bool:
    """Testa ESCREVENDO de verdade: no Windows, `os.access(..., W_OK)` mente para
    Program Files (a virtualização de arquivos herdada do XP)."""
    try:
        with tempfile.TemporaryFile(dir=pasta):
            return True
    except OSError:
        return False


def atualizar_pequena(info: Atualizacao, *, pasta: Path | None = None,
                      progresso_cb: Progresso = _nada, log_cb: Log = _nada) -> Path:
    """Baixa o arquivos.json e o zip, confere os dois e aplica com o app aberto.

    Devolve o `.exe` a reabrir. Levanta em qualquer falha - e então a pasta
    está exatamente como antes (`pacote.aplicar` desfaz) e quem chama cai para
    o instalador completo.
    """
    pasta = pasta if pasta is not None else pasta_instalacao()
    if pasta is None or not info.tem_pequena:
        raise pacote.ErroPacote("atualização pequena indisponível")
    limpar_pasta_download()
    destino = pasta_download()
    # o arquivos.json de todas as versões tem o mesmo nome: leva a versão no nome local
    retrato = destino / f"arquivos_{info.versao}.json"
    _baixar_arquivo(info.arquivos.nome, info.arquivos.url, info.arquivos.tamanho,
                    info.arquivos.sha256, retrato, progresso_cb=_nada, log_cb=log_cb, minimo=0)
    try:
        manifesto_novo = json.loads(retrato.read_text(encoding="utf-8-sig"))
    finally:
        retrato.unlink(missing_ok=True)
    if str(manifesto_novo.get("versao", "")).lstrip("vV") != info.versao:
        raise pacote.ErroPacote(f"o {ARQUIVO_ARQUIVOS} publicado é da versão "
                                f"{manifesto_novo.get('versao')}, não da {info.versao}")
    zip_ = destino / info.pequena.nome
    _baixar_arquivo(info.pequena.nome, info.pequena.url, info.pequena.tamanho,
                    info.pequena.sha256, zip_, progresso_cb=progresso_cb, log_cb=log_cb,
                    minimo=0)
    try:
        alterados = pacote.aplicar(zip_, pasta, manifesto_novo)
    finally:
        zip_.unlink(missing_ok=True)
    progresso_cb(1.0)
    log_cb(f"Atualização aplicada: {len(alterados)} arquivo(s) trocado(s), todos conferidos.")
    _registrar_versao(info.versao, pasta)
    return pasta / "DocManager.exe"


def _registrar_versao(versao: str, pasta: Path) -> None:
    """Atualiza a versão em "Aplicativos instalados" depois da pequena.

    Melhor esforço, e só na instalação "só para mim" (HKCU) - é a única que a
    pequena atualiza. O app se guia pela própria versão do build; isto é para a
    tela do Windows não mostrar a versão velha."""
    if os.name != "nt":
        return
    try:
        import winreg

        chave = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1"
        acesso = winreg.KEY_READ | winreg.KEY_SET_VALUE
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave, 0, acesso) as k:
            local = str(winreg.QueryValueEx(k, "InstallLocation")[0] or "")
            if local and Path(local).resolve() != Path(pasta).resolve():
                return   # a chave é de outra instalação
            winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, versao)
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, f"DocManager Itaipu {versao}")
    except OSError:
        pass


def limpar_restos() -> int:
    """Apaga os arquivos antigos que a última atualização pequena deixou de lado
    (em uso enquanto ela rodava). Chamada na abertura; nunca levanta."""
    pasta = pasta_instalacao()
    if pasta is None:
        return 0
    try:
        return pacote.limpar_restos(pasta)
    except OSError:
        return 0


def reabrir(exe: Path) -> None:
    """Abre o `.exe` novo, desligado deste processo (que vai sair em seguida)."""
    flags = 0
    if os.name == "nt":
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: sobrevive à saída do app.
        flags = 0x00000008 | 0x00000200
    subprocess.Popen([str(exe)], cwd=str(Path(exe).parent), close_fds=True, creationflags=flags)


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
