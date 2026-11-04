"""Capturar telas: o botão flutuante grava imagem, HTML da página e dos frames."""
from __future__ import annotations

import json
import os
import zipfile

import pytest

pytest.importorskip("playwright")

from docmanager.services import navegador  # noqa: E402

CHROMIUM = "/opt/pw-browsers/chromium"


def _executavel():
    if os.path.exists(CHROMIUM):
        return CHROMIUM
    pytest.skip("sem Chromium para o teste (o CI não tem navegador)")


def test_capturar_grava_tela_pagina_e_frames(tmp_path):
    pagina = tmp_path / "pagina.html"
    frame = tmp_path / "frame.html"
    frame.write_text("<html><body><button id='btn-atualizar'>Atualizar</button></body></html>")
    pagina.write_text(f"<html><head><title>Registro de Documentos</title></head><body>"
                      f"<h1>Aconex de mentira</h1><iframe name='principal' src='{frame.as_uri()}'></iframe>"
                      f"</body></html>")
    cliques = []

    def parar(contexto):
        p = contexto.pages[0]
        if not cliques:
            p.wait_for_selector(f"#{navegador.ID_BOTAO}")
            p.frame(name="principal").wait_for_selector("#btn-atualizar")
            p.click(f"#{navegador.ID_BOTAO}")
            cliques.append(1)
            return False
        cliques.append(1)
        texto = p.inner_text(f"#{navegador.ID_BOTAO}")
        return texto.startswith("Capturada") or len(cliques) > 40   # ~20 s no máximo

    destino = tmp_path / "capturas" / "sessao"
    arquivo = navegador.capturar_telas(log_cb=lambda _m: None, url_inicial=pagina.as_uri(),
                                       destino=destino, executavel=_executavel(),
                                       perfil=tmp_path / "perfil", headless=True, parar=parar)
    assert arquivo == destino.with_suffix(".zip") and arquivo.exists()
    tela = destino / "01-Registro de Documentos"
    assert (tela / "tela.png").stat().st_size > 0
    assert "Aconex de mentira" in (tela / "pagina.html").read_text(encoding="utf-8")
    assert "btn-atualizar" in (tela / "frame-1.html").read_text(encoding="utf-8")
    info = json.loads((tela / "info.json").read_text(encoding="utf-8"))
    assert info["titulo"] == "Registro de Documentos" and info["frames"][0]["nome"] == "principal"
    with zipfile.ZipFile(arquivo) as z:
        assert "sessao/01-Registro de Documentos/tela.png" in z.namelist()


def test_o_botao_nao_aparece_dentro_dos_frames(tmp_path):
    frame = tmp_path / "f.html"
    frame.write_text("<html><body>dentro</body></html>")
    pagina = tmp_path / "p.html"
    pagina.write_text(f"<html><body><iframe name='f' src='{frame.as_uri()}'></iframe></body></html>")
    vistos = {}

    def parar(contexto):
        p = contexto.pages[0]
        p.wait_for_selector(f"#{navegador.ID_BOTAO}")
        p.frame(name="f").wait_for_load_state()
        vistos["frame"] = p.frame(name="f").query_selector(f"#{navegador.ID_BOTAO}")
        return True

    assert navegador.capturar_telas(log_cb=lambda _m: None, url_inicial=pagina.as_uri(),
                                    destino=tmp_path / "c", executavel=_executavel(),
                                    perfil=tmp_path / "perfil", headless=True, parar=parar) is None
    assert vistos["frame"] is None


def test_sem_chrome_a_mensagem_diz_o_que_fazer(tmp_path):
    class _Chromium:
        def launch_persistent_context(self, *_a, **_k):
            raise Exception("Chromium distribution 'chrome' is not found at C:\\...")

    class _Pw:
        chromium = _Chromium()

    with pytest.raises(navegador.ErroNavegador, match="Google Chrome não foi encontrado"):
        navegador.abrir_chrome(_Pw(), perfil=tmp_path)


def test_f8_dentro_de_um_frame_captura_sem_o_mouse(tmp_path):
    """Mexer o mouse fecha menus do Aconex: a tecla captura, mesmo com o foco num frame."""
    frame = tmp_path / "f.html"
    frame.write_text("<html><body><input id='campo'></body></html>")
    pagina = tmp_path / "p.html"
    pagina.write_text(f"<html><head><title>Tela</title></head><body>"
                      f"<iframe name='f' src='{frame.as_uri()}'></iframe></body></html>")
    estado = {"apertou": False, "voltas": 0}

    def parar(contexto):
        p = contexto.pages[0]
        estado["voltas"] += 1
        if estado["voltas"] > 40:   # ~20 s: não trava a suíte se a tecla não capturar
            return True
        if not estado["apertou"]:
            p.wait_for_selector(f"#{navegador.ID_BOTAO}")
            alvo = p.frame(name="f")
            alvo.wait_for_selector("#campo")
            alvo.focus("#campo")
            p.keyboard.press(navegador.TECLA)
            estado["apertou"] = True
            return False
        return p.inner_text(f"#{navegador.ID_BOTAO}").startswith("Capturada")

    destino = tmp_path / "c"
    arquivo = navegador.capturar_telas(log_cb=lambda _m: None, url_inicial=pagina.as_uri(),
                                       destino=destino, executavel=_executavel(),
                                       perfil=tmp_path / "perfil", headless=True, parar=parar)
    assert arquivo is not None and (destino / "01-Tela" / "tela.png").exists()
