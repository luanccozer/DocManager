"""A interface em espanhol, português ou inglês (`ui/idioma.py`), como a CMI
Suite e o SIG-FT: texto de tela em `t("...")`, tradução em
`ui/recursos/idiomas/es.json` e `en.json`."""
import json
import re
import string
from pathlib import Path

import pytest

from docmanager.ui import idioma
from tools import textos_da_interface as textos


@pytest.fixture(autouse=True)
def _volta_ao_portugues():
    yield
    idioma.definir("pt")


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_todo_texto_de_tela_tem_traducao(codigo):
    assert textos.faltando(codigo) == []


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_traducao_mantem_os_mesmos_campos(codigo):
    """"{versao}" no português tem de existir na tradução, senão o texto sai sem o número."""
    catalogo = json.loads((textos.IDIOMAS / f"{codigo}.json").read_text(encoding="utf-8"))
    campos = lambda s: sorted(c for _, c, _, _ in string.Formatter().parse(s) if c)  # noqa: E731
    for original, traducao in catalogo.items():
        assert campos(original) == campos(traducao), original


@pytest.mark.parametrize("codigo", ["es", "en"])
def test_catalogo_sem_texto_que_ja_nao_existe(codigo):
    catalogo = json.loads((textos.IDIOMAS / f"{codigo}.json").read_text(encoding="utf-8"))
    sobrando = set(catalogo) - set(textos.textos())
    assert sobrando == set(), "remova do catálogo o que saiu da interface"


def test_traduz_e_formata():
    idioma.definir("es")
    assert idioma.t("Configurações") == "Configuración"
    assert idioma.t("Pular a v{versao}", versao="3.6.4") == "Saltar la v3.6.4"
    idioma.definir("en")
    assert idioma.t("Configurações") == "Settings"
    idioma.definir("pt")
    assert idioma.t("Configurações") == "Configurações"
    assert idioma.t("texto que ninguém traduziu") == "texto que ninguém traduziu"


def test_idioma_desconhecido_cai_no_portugues():
    idioma.definir("fr")
    assert idioma.atual() == "pt"


def test_escolha_vazia_segue_o_windows(monkeypatch):
    monkeypatch.setattr(idioma.locale, "getlocale", lambda: ("Spanish_Paraguay", "1252"))
    assert idioma.efetivo("") == "es"
    monkeypatch.setattr(idioma.locale, "getlocale", lambda: ("de_DE", "UTF-8"))
    assert idioma.efetivo("") == "pt"
    assert idioma.efetivo("en") == "en"


def test_nenhum_texto_de_tela_fora_de_t():
    """QPushButton("...")/QLabel("...")/QCheckBox("...") com português cru
    escapariam da tradução."""
    cru = re.compile(r'Q(?:PushButton|Label|CheckBox|RadioButton)\(\s*"[^"]*[a-zà-ú]{3}')
    culpados = []
    for arquivo in (Path(textos.PACOTE) / "ui").rglob("*.py"):
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if cru.search(linha):
                culpados.append(f"{arquivo.name}:{n}")
    assert culpados == []


def test_a_janela_inteira_abre_em_espanhol_e_em_ingles(qtbot, monkeypatch):
    """Monta todas as telas nos dois idiomas: um `t()` com campo errado
    levantaria aqui, e o título da Home sai traduzido."""
    pytest.importorskip("PySide6")
    from docmanager.services import updater
    from docmanager.ui import main_app

    monkeypatch.setattr(updater, "verificar_em_segundo_plano", lambda *a, **k: None)
    main_app.criar_app()
    for codigo, inicio in (("es", "Inicio"), ("en", "Home")):
        idioma.definir(codigo)
        janela = main_app.MainApp()
        qtbot.addWidget(janela)
        for spec in main_app.VIEWS:
            janela.selecionar(spec.key)
        assert janela._botoes["home"].text() == inicio
        janela._saindo_para_atualizar = True
