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
   em execução. Por isso o instalador é disparado com `/CLOSEAPPLICATIONS` (o
   Inno acha o app pelo `AppMutex` do .iss) e o app se encerra logo em seguida.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import rede

REPO_OWNER = "luanccozer"
REPO_NOME = "DocManager"
API = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NOME}"

# Nome do manifesto publicado junto do instalador (traz versão, SHA256 e notas).
ARQUIVO_MANIFESTO = "latest.json"

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
    versao: str
    notas: str
    nome_arquivo: str
    url_asset: str          # endpoint de API - o único que funciona em repo privado
    tamanho: int
    sha256: str             # '' quando o release não publicou o hash
    url_pagina: str
    publicado_em: str = ""

    @property
    def tamanho_mb(self) -> float:
        return round(self.tamanho / (1024 * 1024), 1) if self.tamanho else 0.0


def _asset(release: dict, nome: str) -> dict | None:
    return next((a for a in release.get("assets", []) if a.get("name") == nome), None)


def _instalador(release: dict) -> dict | None:
    """O asset do instalador: o primeiro `.exe` do release."""
    return next((a for a in release.get("assets", [])
                 if str(a.get("name", "")).lower().endswith(".exe")), None)


def interpretar_release(release: dict, manifesto: dict | None = None) -> Atualizacao | None:
    """Monta a `Atualizacao` a partir do JSON do release. Pura - testada.

    O SHA256 vem, em ordem: do `latest.json` publicado junto; senão do campo
    `digest` que a própria API do GitHub devolve; senão fica vazio (o download
    ainda acontece, mas `baixar()` avisa que não deu para conferir).
    """
    asset = _instalador(release)
    if asset is None:
        return None
    sha = ""
    if manifesto:
        sha = str(manifesto.get("sha256", "")).strip().lower()
    if not sha:
        digest = str(asset.get("digest", "") or "")
        if digest.lower().startswith("sha256:"):
            sha = digest.split(":", 1)[1].strip().lower()
    notas = (manifesto or {}).get("notas") or release.get("body") or ""
    return Atualizacao(
        versao=str(release.get("tag_name", "")).lstrip("vV"),
        notas=str(notas).strip(),
        nome_arquivo=str(asset.get("name", "")),
        url_asset=str(asset.get("url", "")),
        tamanho=int(asset.get("size") or 0),
        sha256=sha,
        url_pagina=str(release.get("html_url", "")),
        publicado_em=str(release.get("published_at", "") or "")[:10],
    )


class SemToken(RuntimeError):
    """O build não tem token - checar atualização é impossível neste repositório."""


def checar(versao_atual: str, *, log_cb: Log = _nada) -> Atualizacao | None:
    """Devolve a `Atualizacao` se houver versão mais nova; `None` se já está em dia.

    Levanta `SemToken` (build sem token, ou token recusado pelo GitHub) ou
    `rede.FalhaDeRede` (rede/Zscaler). Quem chama decide se mostra o erro ou
    engole - a checagem automática engole, o botão das Configurações mostra.
    """
    if not token():
        raise SemToken(
            "Este build não tem token de atualização embutido (build local ou "
            "segredo ausente no workflow). Baixe a versão nova manualmente pela "
            "página de Releases do projeto.")

    log_cb("Procurando atualizações...")
    # 401/403/404 são respostas VÁLIDAS do GitHub, não falhas de rota: entram no
    # `status_ok` para virarem uma mensagem que diz o que fazer, em vez do
    # "nenhuma rota funcionou" genérico que a cascata devolveria.
    sessao, resp = rede.abrir(f"{API}/releases/latest", headers=_cabecalhos(),
                              timeout=20, log_cb=log_cb,
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
            release = resp.json()
        finally:
            resp.close()

        versao_remota = str(release.get("tag_name", "")).lstrip("vV")
        if not versao_remota:
            log_cb("O GitHub não devolveu nenhum release publicado.")
            return None
        if not e_mais_nova(versao_remota, versao_atual):
            log_cb(f"Você já está na versão mais recente (v{versao_atual}).")
            return None

        # Manifesto é opcional: sem ele, o SHA256 vem do `digest` da própria API.
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

    info = interpretar_release(release, manifesto)
    if info is None:
        log_cb(f"O release v{versao_remota} existe, mas não tem instalador (.exe) "
               f"publicado. Avise o responsável pelo build.")
        return None
    log_cb(f"Nova versão disponível: v{info.versao} ({info.tamanho_mb} MB).")
    return info


# ──────────────────────────── baixar e instalar ─────────────────────────────

def pasta_download() -> Path:
    p = Path(tempfile.gettempdir()) / "DocManager_Update"
    p.mkdir(parents=True, exist_ok=True)
    return p


class HashDivergente(RuntimeError):
    """O arquivo baixado não bate com o SHA256 publicado - não pode ser executado."""


def baixar(info: Atualizacao, *, progresso_cb: Progresso = _nada,
           log_cb: Log = _nada) -> Path:
    """Baixa o instalador e confere o SHA256. Devolve o caminho do arquivo.

    Usa o endpoint de API do asset (não o `browser_download_url`): em repositório
    privado só ele entrega o binário - ver o item 1 do cabeçalho do módulo.
    """
    destino = pasta_download() / info.nome_arquivo
    log_cb(f"Baixando {info.nome_arquivo} ({info.tamanho_mb} MB)...")

    sessao, resp = rede.abrir(info.url_asset, headers=_cabecalhos("application/octet-stream"),
                              timeout=60, stream=True, log_cb=log_cb)
    parcial = destino.with_suffix(destino.suffix + ".part")
    try:
        total = int(resp.headers.get("Content-Length") or info.tamanho or 0)
        baixado = 0
        digest = hashlib.sha256()
        with open(parcial, "wb") as f:
            for bloco in resp.iter_content(chunk_size=256 * 1024):
                if not bloco:
                    continue
                f.write(bloco)
                digest.update(bloco)
                baixado += len(bloco)
                if total:
                    progresso_cb(min(baixado / total, 1.0))
    finally:
        resp.close()
        sessao.close()

    # Um HTML de login (repo privado acessado sem token) tem alguns KB - um
    # instalador tem dezenas de MB. Barra o "download que deu certo" enganoso.
    tamanho_baixado = parcial.stat().st_size
    if tamanho_baixado < 1_000_000:
        parcial.unlink(missing_ok=True)
        raise HashDivergente(
            f"O arquivo baixado é pequeno demais para ser o instalador "
            f"({tamanho_baixado} bytes). Isso costuma ser uma página de erro no "
            f"lugar do binário - token de atualização inválido ou expirado.")

    obtido = digest.hexdigest()
    if info.sha256:
        if obtido != info.sha256:
            parcial.unlink(missing_ok=True)
            raise HashDivergente(
                f"O instalador baixado não confere com o publicado.\n"
                f"  esperado: {info.sha256}\n  obtido:   {obtido}\n"
                f"Baixe manualmente pela página do Release.")
        log_cb("Integridade conferida (SHA256 confere).")
    else:
        log_cb("⚠️ O release não publicou o SHA256 - não deu para conferir a "
               "integridade do arquivo.")

    destino.unlink(missing_ok=True)
    parcial.rename(destino)
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

    Testa ESCREVENDO de verdade: no Windows, `os.access(..., W_OK)` mente para
    Program Files (devolve True mesmo sem permissão) por causa da virtualização
    de arquivos herdada do XP.
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


# /SILENT mostra só a barra de progresso; /CLOSEAPPLICATIONS faz o Inno fechar o
# app pelo AppMutex e /RESTARTAPPLICATIONS reabre o DocManager já atualizado.
ARGS_INSTALADOR = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                   "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]


def instalar(caminho: Path, *, log_cb: Log = _nada) -> None:
    """Dispara o instalador e volta - quem chama deve FECHAR o app em seguida.

    Com elevação (instalação em Program Files) usa `ShellExecuteW` com o verbo
    `runas`, que é o único jeito de fazer o Windows mostrar o UAC: um
    `subprocess` comum simplesmente falharia com "acesso negado".
    """
    caminho = Path(caminho)
    log_inst = pasta_download() / "instalacao.log"
    args = [*ARGS_INSTALADOR, f'/LOG={log_inst}']

    if precisa_elevacao():
        log_cb("A instalação vai pedir permissão de administrador (o app está em "
               "Program Files). Confirme na janela do Windows.")
        import ctypes
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", str(caminho), subprocess.list2cmdline(args), None, 1)
        if rc <= 32:   # <=32 é erro em ShellExecute; 5 = o usuário recusou o UAC
            raise RuntimeError(
                "Não foi possível iniciar o instalador com privilégios de "
                f"administrador (código {rc}). "
                + ("Você recusou o pedido do Windows." if rc == 5 else
                   f"Rode manualmente: {caminho}"))
    else:
        flags = 0
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: o instalador sobrevive
            # ao fechamento do app, que acontece logo depois desta chamada.
            flags = 0x00000008 | 0x00000200
        subprocess.Popen([str(caminho), *args], close_fds=True, creationflags=flags)
    log_cb("Instalador iniciado. O DocManager vai fechar e reabrir atualizado.")


# ─────────────────────── política: quando checar, o que pular ───────────────
#
# A checagem automática precisa ser DISCRETA: nunca atrasar a abertura do app,
# nunca insistir numa versão que a pessoa mandou pular e nunca bater no GitHub a
# cada duplo-clique. Estas funções guardam essas decisões em um lugar só, para a
# interface não ter que lembrar delas.

INTERVALO_PADRAO_HORAS = 6


def deve_verificar(config, *, intervalo_horas: int = INTERVALO_PADRAO_HORAS) -> bool:
    """True se é hora de perguntar ao GitHub (checagem AUTOMÁTICA).

    Desligada nas Configurações, sem token embutido, ou consultada há menos de
    `intervalo_horas` → False. O botão "Procurar atualizações" ignora tudo isto
    e chama `checar()` direto: pedido explícito sempre vale.
    """
    from datetime import datetime, timedelta

    try:
        s = config.settings
    except Exception:  # noqa: BLE001
        return False
    if not s.verificar_atualizacoes or not token():
        return False
    if not s.ultima_verificacao:
        return True
    try:
        ultima = datetime.fromisoformat(s.ultima_verificacao)
    except ValueError:
        return True
    return datetime.now() - ultima >= timedelta(hours=intervalo_horas)


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
                               *, log_cb: Log = _nada, forcar: bool = False) -> None:
    """Dispara a checagem numa thread e chama `ao_encontrar(info)` se houver novidade.

    Nunca levanta exceção: numa checagem automática, rede indisponível ou build
    sem token são silêncio no log - o app segue como se nada fosse. Quem quer o
    erro na tela (botão "Procurar atualizações") usa `checar()` diretamente.

    `ao_encontrar` roda NA THREAD DE FUNDO: quem passa o callback é responsável
    por voltar para a thread da interface (`widget.after(0, ...)`).
    """
    import threading

    if not forcar and not deve_verificar(config):
        return

    def _trabalho():
        try:
            info = checar(versao_atual, log_cb=log_cb)
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
