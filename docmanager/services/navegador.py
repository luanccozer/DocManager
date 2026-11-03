"""O Chrome do robô (Upload de documentos) e a ferramenta Capturar telas.

O robô usa o **Google Chrome instalado** na máquina, pelo Playwright
(`channel="chrome"`): nada de navegador empacotado no instalador. O perfil fica em
`pasta_dados()/navegador`, então o login do Box e do Aconex feito pela pessoa uma vez
continua valendo nas próximas (como no Chrome dela). Nenhuma senha passa pelo app.

Capturar telas existe porque daqui não se vê o Box nem a tela do Aconex: a pessoa
faz o processo à mão uma vez, aperta o botão "Capturar" (flutuante, só na página
principal) em cada tela, e o app grava a imagem, o HTML da página e de cada frame
(o Aconex é feito de frames - sem eles os botões não aparecem) e o endereço. O .zip
é o mapa da Fase 2. As capturas têm dados reais e nunca entram no repositório.
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

URL_ACONEX = "https://us1.aconex.com"
ID_BOTAO = "dm-capturar"

_SCRIPT_CAPTURADA = """(n) => {
  const b = document.getElementById('%(id)s');
  if (!b) return;
  b.style.visibility = 'visible';
  b.textContent = 'Capturada (' + n + ')';
  setTimeout(() => { b.disabled = false; b.textContent = 'Capturar'; }, 1500);
}""" % {"id": ID_BOTAO}

_SCRIPT_BOTAO = """
(() => {
  if (window.top !== window) return;   // só na página principal, não nos frames
  const montar = () => {
    if (document.getElementById('%(id)s')) return;
    const b = document.createElement('button');
    b.id = '%(id)s';
    b.textContent = 'Capturar';
    b.title = 'DocManager: grava esta tela para o mapeamento do robô';
    b.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;' +
      'padding:10px 18px;background:#1f6feb;color:#fff;border:0;border-radius:6px;' +
      'font:600 14px sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.35);cursor:pointer';
    b.onclick = async () => {
      // O app grava fora daqui (a gravação mexe na página) e depois avisa no botão.
      b.disabled = true; b.textContent = 'Capturando...';
      try { await window.dmCapturar(); }
      catch (e) { b.textContent = 'Erro ao capturar'; b.disabled = false; }
    };
    document.documentElement.appendChild(b);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', montar);
  else montar();
})();
""" % {"id": ID_BOTAO}


class ErroNavegador(RuntimeError):
    """O Chrome do robô não abriu; a mensagem é para a tela."""


def pasta_perfil() -> Path:
    from .credenciais import pasta_dados

    p = pasta_dados() / "navegador"
    p.mkdir(parents=True, exist_ok=True)
    return p


def abrir_chrome(pw, *, canal: str | None = "chrome", executavel: str | None = None,
                 perfil: Path | None = None, headless: bool = False):
    """Contexto persistente do Chrome do robô (perfil próprio, login guardado)."""
    opcoes = {"headless": headless, "accept_downloads": True, "no_viewport": True}
    if executavel:
        opcoes["executable_path"] = executavel
    elif canal:
        opcoes["channel"] = canal
    try:
        return pw.chromium.launch_persistent_context(str(perfil or pasta_perfil()), **opcoes)
    except Exception as e:  # noqa: BLE001 - o motivo vira mensagem para a pessoa
        texto = str(e)
        if "is not found" in texto or "not installed" in texto or "Executable doesn't exist" in texto:
            raise ErroNavegador("O Google Chrome não foi encontrado neste computador. O robô usa o "
                                "Chrome instalado; instale-o (ou peça à TI) e tente de novo.") from e
        if "ProcessSingleton" in texto or "user data directory is already in use" in texto.lower():
            raise ErroNavegador("O Chrome do robô já está aberto. Feche aquela janela e tente de novo.") from e
        raise ErroNavegador(f"O Chrome do robô não abriu: {texto.splitlines()[0]}") from e


def _nome_seguro(texto: str) -> str:
    return re.sub(r"[^\w\- ]+", "", texto or "").strip()[:40] or "tela"


def capturar_telas(*, log_cb=print, url_inicial: str = URL_ACONEX, destino: Path | None = None,
                   canal: str | None = "chrome", executavel: str | None = None,
                   perfil: Path | None = None, headless: bool = False, parar=None) -> Path | None:
    """Abre o Chrome do robô com o botão Capturar e espera a pessoa fechar o navegador.

    Devolve o .zip com as capturas (None se nenhuma foi feita). `parar(contexto)` é
    chamado a cada meio segundo e encerra a espera quando devolve True (testes)."""
    from playwright.sync_api import sync_playwright

    if destino is None:
        from .credenciais import pasta_dados

        destino = pasta_dados() / "capturas" / datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    feitas: list[Path] = []

    pendentes: list = []

    def pedir_captura(origem) -> None:
        # Só anota: mexer na página aqui dentro trava o Playwright (API síncrona).
        pendentes.append(origem["page"])

    def capturar(page) -> int:
        n = len(feitas) + 1
        try:
            titulo = page.title()
        except Exception:  # noqa: BLE001
            titulo = ""
        pasta = destino / f"{n:02d}-{_nome_seguro(titulo)}"
        pasta.mkdir(parents=True, exist_ok=True)
        page.evaluate(f"document.getElementById('{ID_BOTAO}').style.visibility='hidden'")
        page.screenshot(path=str(pasta / "tela.png"))
        (pasta / "pagina.html").write_text(page.content(), encoding="utf-8")
        frames = []
        for i, frame in enumerate(page.frames[1:], 1):
            info = {"n": i, "nome": frame.name, "url": frame.url}
            try:
                (pasta / f"frame-{i}.html").write_text(frame.content(), encoding="utf-8")
            except Exception as e:  # noqa: BLE001 - frame que sumiu no meio: anota e segue
                info["erro"] = str(e).splitlines()[0]
            frames.append(info)
        (pasta / "info.json").write_text(json.dumps(
            {"url": page.url, "titulo": titulo, "quando": datetime.now().isoformat(timespec="seconds"),
             "frames": frames}, ensure_ascii=False, indent=1), encoding="utf-8")
        feitas.append(pasta)
        page.evaluate(_SCRIPT_CAPTURADA, n)
        log_cb(f"Tela {n} capturada: {titulo or page.url}")
        return n

    def atender_pedidos() -> None:
        while pendentes:
            page = pendentes.pop(0)
            try:
                capturar(page)
            except Exception as e:  # noqa: BLE001 - a aba fechou no meio: segue
                log_cb(f"Não foi possível capturar esta tela: {str(e).splitlines()[0]}")

    with sync_playwright() as pw:
        contexto = abrir_chrome(pw, canal=canal, executavel=executavel, perfil=perfil, headless=headless)
        try:
            contexto.expose_binding("dmCapturar", pedir_captura)
            contexto.add_init_script(_SCRIPT_BOTAO)
            pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
            if url_inicial:
                try:
                    pagina.goto(url_inicial)
                except Exception as e:  # noqa: BLE001 - sem rede/VPN: a pessoa navega à mão
                    log_cb(f"Não abriu {url_inicial} ({str(e).splitlines()[0]}); navegue à mão.")
            log_cb("Chrome do robô aberto. Faça o processo à mão e aperte 'Capturar' em cada tela; "
                   "feche o Chrome para terminar.")
            while contexto.pages:
                try:
                    contexto.pages[0].wait_for_timeout(500)
                except Exception:  # noqa: BLE001 - a aba fechou entre uma volta e outra
                    continue
                atender_pedidos()
                if parar is not None and parar(contexto):
                    break
        finally:
            try:
                contexto.close()
            except Exception:  # noqa: BLE001
                pass

    if not feitas:
        log_cb("Nenhuma tela foi capturada.")
        return None
    arquivo = destino.with_suffix(".zip")
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(destino.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(destino.parent))
    log_cb(f"{len(feitas)} tela(s) capturada(s). Arquivo para mandar: {arquivo}")
    return arquivo
