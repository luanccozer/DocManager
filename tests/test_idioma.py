"""A interface em espanhol, português ou inglês (`ui/idioma.py`), como a CMI
Suite e o SIG-FT: texto de tela em `t("...")`, tradução em
`ui/recursos/idiomas/es.json` e `en.json`."""
import ast
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


# Quem recebe texto de tela, e em que posição. `t("...")`/`marcar("...")` são
# chamadas, não literais: o que aparece aqui como literal escapou da tradução.
_TEXTO_NA_POSICAO = {
    "rotulo": 0, "botao": 0, "Card": 0, "RunBar": 0, "FileSelector": 0, "QPushButton": 0,
    "QLabel": 0, "QCheckBox": 0, "QRadioButton": 0, "setToolTip": 0, "setPlaceholderText": 0,
    "setWindowTitle": 0, "setText": 0, "desabilitar": 0, "legenda": 0, "addRow": 0,
    "info": 1, "aviso": 1, "erro": 1, "perguntar": 1, "tentar_de_novo": 0,
}
_TEXTO_EM_PALAVRA_CHAVE = {"dica", "placeholderText", "titulo"}


def _literais_de_tela(arvore):
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        nome = no.func.attr if isinstance(no.func, ast.Attribute) else getattr(no.func, "id", "")
        candidatos = []
        if nome in _TEXTO_NA_POSICAO:
            fim = _TEXTO_NA_POSICAO[nome] + 1
            candidatos += no.args[:fim] if nome in ("info", "aviso", "erro", "perguntar") else no.args[:1]
        if nome == "add" and isinstance(no.func, ast.Attribute) and "tabs" in ast.unparse(no.func):
            candidatos += no.args[:1]
        if nome == "Seletor" and no.args and isinstance(no.args[0], ast.List):
            candidatos += no.args[0].elts
        candidatos += [kw.value for kw in no.keywords if kw.arg in _TEXTO_EM_PALAVRA_CHAVE]
        for arg in candidatos:
            if isinstance(arg, ast.JoinedStr):   # f-string: conta o texto fixo dela
                texto = "".join(v.value for v in arg.values if isinstance(v, ast.Constant))
            elif isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                texto = arg.value
            else:
                continue
            if re.search(r"[A-Za-zÀ-ú]{3}", texto) and texto != "DocManager":
                yield no.lineno


def test_nenhum_texto_de_tela_fora_de_t():
    """Literal (ou f-string) passado a um widget ou a um helper de texto de
    tela escaparia da tradução: tem de ir em `t("...")`."""
    culpados = []
    for arquivo in sorted((Path(textos.PACOTE) / "ui").rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        culpados += [f"{arquivo.name}:{linha}" for linha in _literais_de_tela(arvore)]
    assert culpados == []


def test_texto_do_outro_usuario_e_o_mesmo_do_backend():
    """A tela marca o texto de `OUTRO_USUARIO` para traduzir; os dois têm de
    continuar iguais, ou a opção manual sai sem tradução."""
    from docmanager.aconex_backend import OUTRO_USUARIO
    from docmanager.ui.views.aconex_view import AconexView

    assert AconexView._ROTULO_OUTRO == OUTRO_USUARIO


def test_atalhos_do_periodo_estao_todos_marcados():
    from datetime import date

    from docmanager.core.doclist_periodo import janelas_padrao
    from docmanager.ui.views.periodo_dialog import _ATALHOS_NA_TELA

    assert {j.rotulo for j in janelas_padrao(date(2026, 10, 31))} == set(_ATALHOS_NA_TELA)


def test_tipos_da_sugestao_estao_marcados():
    from docmanager.services import sugestoes
    from docmanager.ui.views.sugestoes_view import _TIPOS_NA_TELA

    assert set(sugestoes.TIPOS) == set(_TIPOS_NA_TELA)


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


def test_a_guarda_pega_os_helpers_de_texto():
    """A guarda de verdade pega o que escapava da antiga (só QPushButton/QLabel)."""
    for codigo in ('botao("Exportar")', 'self.tabs.add("Planilha", "x")', 'Seletor(["Grupo", "Sistema"])',
                   'rotulo(f"Total: {n} documentos")', 'dialogos.aviso("Aviso", "Algo deu errado")'):
        assert list(_literais_de_tela(ast.parse(codigo))), codigo
    for codigo in ('botao(t("Exportar"))', 'rotulo(f"•  {it}")', 'self.tabs.add(marcar("Planilha"))'):
        assert not list(_literais_de_tela(ast.parse(codigo))), codigo


def test_idioma_do_windows_vem_da_interface_e_nao_do_formato_regional(monkeypatch):
    monkeypatch.setattr(idioma.locale, "getlocale", lambda: ("Portuguese_Brazil", "1252"))
    assert idioma.do_sistema(["en-US", "pt-BR"]) == "en"     # Windows em inglês, formato do Brasil
    assert idioma.do_sistema([]) == "pt"                      # sem o Qt: o formato regional
