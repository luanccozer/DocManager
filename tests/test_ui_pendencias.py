# ruff: noqa: F811 - as fixtures app e caixas vêm de test_ui_telas
"""O módulo Pendências na interface (spec, seção 10)."""
from __future__ import annotations

import pytest

from test_ui_telas import _quando_abrir, app, caixas  # noqa: F401 - fixtures

from docmanager import aconex_backend as ab
from docmanager.services import pendencias_update as pu


@pytest.fixture
def servico(monkeypatch):
    """O serviço simulado: anota cada chamada e devolve um resultado ok."""
    chamadas = []

    def atualizar(config, caminho, **kw):
        chamadas.append((config, caminho, kw))
        if "ao_chamar" in servico_estado:
            servico_estado["ao_chamar"](kw)
        return pu.ResultadoPendencias(True, "Planilha de pendências atualizada.")

    servico_estado: dict = {"chamadas": chamadas}
    monkeypatch.setattr(pu, "atualizar_pendencias", atualizar)
    monkeypatch.setattr(ab, "usuarios_disponiveis", lambda: ["FULANO"])
    monkeypatch.setattr(ab.AconexConfig, "para_usuario",
                        classmethod(lambda cls, nome, **_k: f"config de {nome}"))
    return servico_estado


def _tela(app):
    app.selecionar("pendencias")
    return app._views["pendencias"]


def test_modulo_na_barra_lateral_e_no_inicio(app):
    from docmanager.ui.main_app import VIEWS
    from docmanager.ui.views.home_view import MODULOS, _BlocoModulo

    assert any(v.key == "pendencias" and v.icone == "file-spreadsheet" for v in VIEWS)
    assert any(m[0] == "pendencias" for m in MODULOS)
    from PySide6.QtWidgets import QLabel

    app.selecionar("home")
    bloco = next(b for b in app._views["home"].findChildren(_BlocoModulo)
                 if any(lbl.text() == "Pendências" for lbl in b.findChildren(QLabel)))
    bloco._ao_abrir()
    assert app._key_ativa == "pendencias"


def test_escolher_a_planilha_dispara_a_atualizacao(app, qtbot, servico, caixas, tmp_path):
    tela = _tela(app)
    caminho = str(tmp_path / "pendencias.xlsx")
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.sel.definir(caminho)
    assert len(servico["chamadas"]) == 1
    config, usado, kw = servico["chamadas"][0]
    assert (config, usado) == ("config de FULANO", caminho)
    assert {"decidir_cb", "retry_cb", "log_cb", "progress_cb"} <= set(kw)
    assert caixas == [("info", "Pendências", "Planilha de pendências atualizada.")]

    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()                                  # rodar de novo sem escolher
    assert len(servico["chamadas"]) == 2


def test_sem_planilha_so_avisa(app, qtbot, servico):
    tela = _tela(app)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()
    assert servico["chamadas"] == []
    assert "Selecione a planilha de pendências" in tela.log.texto()


def test_sem_credencial_abre_o_cadastro_e_cancelar_nao_chama_o_servico(
        app, qtbot, servico, monkeypatch, tmp_path):
    from docmanager.ui.views import credenciais_dialog

    monkeypatch.setattr(ab, "usuarios_disponiveis", lambda: [])
    abertos = []
    monkeypatch.setattr(credenciais_dialog, "cadastrar", lambda parent=None, nome=None: abertos.append(1))
    tela = _tela(app)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.sel.definir(str(tmp_path / "p.xlsx"))
    assert abertos == [1]
    assert servico["chamadas"] == []
    assert "Sem usuário do Aconex" in tela.log.texto()


def test_decisao_e_nova_tentativa_vao_aos_dialogos_certos(app, qtbot, servico, monkeypatch,
                                                         caixas, tmp_path):
    from docmanager.ui import dialogos
    from docmanager.ui.views import pendencias_view

    recebidas = {}
    monkeypatch.setattr(pendencias_view, "decidir_sobrescricoes",
                        lambda itens, parent=None, textos=None: recebidas.update(itens=itens, textos=textos))
    monkeypatch.setattr(dialogos, "tentar_de_novo", lambda titulo, msg, *a, **k: recebidas.update(retry=msg))
    servico["ao_chamar"] = lambda kw: (kw["decidir_cb"](["item"]), kw["retry_cb"]("arquivo aberto"))
    tela = _tela(app)
    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.sel.definir(str(tmp_path / "p.xlsx"))
    assert recebidas["itens"] == ["item"]
    assert recebidas["textos"] is pendencias_view.TEXTOS_PENDENCIAS
    assert recebidas["retry"] == "arquivo aberto"
    assert [c[0] for c in caixas] == ["info"]                 # nenhuma pergunta "Gravar?"


def _apagamentos():
    return [pu.Apagamento(5, 6, 20, "¿Pasó a comisionamiento?", "#TAG DESLOCADO", "Pendência 6"),
            pu.Apagamento(5, 6, 17, "Fecha prevista para corrección", "2026-12-01", "Pendência 6")]


def test_tela_de_apagamentos_com_os_textos_das_pendencias(qtbot):
    from docmanager.services.sobrescricao import DecisaoSobrescricao
    from docmanager.ui.views.pendencias_view import TEXTOS_PENDENCIAS
    from docmanager.ui.views.sobrescricao_dialog import (
        CasoACasoDialog,
        EscolhaSobrescricao,
        decidir_sobrescricoes,
    )

    vistos = {}

    def caso(w):
        vistos["escolha"] = (w.windowTitle(), w.lbl_resumo.text(), w.btn_aceitar.text(),
                             w.btn_recusar.text())
        w.btn_caso.click()

    def marcar_primeira(w):
        vistos["colunas"] = [w.tree.headerItem().text(i) for i in range(w.tree.columnCount())]
        vistos["linha"] = [w.tree.topLevelItem(0).text(i) for i in range(5)]
        w.marcar(0, True)
        w.btn_trocar.click()

    _t1 = _quando_abrir(EscolhaSobrescricao, caso)
    _t2 = _quando_abrir(CasoACasoDialog, marcar_primeira)
    decisao = decidir_sobrescricoes(_apagamentos(), textos=TEXTOS_PENDENCIAS)
    assert decisao == DecisaoSobrescricao(aceitas=frozenset({0}), recusadas=frozenset({1}))
    assert vistos["escolha"] == ("Valores que o Aconex não tem mais",
                                 "2 células têm valor na planilha, mas estão vazias no Aconex.",
                                 "Apagar todas", "Manter todas")
    assert vistos["colunas"] == ["Pendência", "Descrição", "Coluna", "Na planilha", "No Aconex"]
    assert vistos["linha"] == ["6", "Pendência 6", "¿Pasó a comisionamiento?", "'#TAG DESLOCADO'", "(vazio)"]
