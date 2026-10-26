"""Telas de verdade (Qt/PySide6), para o que só aparece com a janela aberta.

Rodam sem monitor (`QT_QPA_PLATFORM=offscreen`, posto no conftest) - no CI do
Linux e no Release do Windows. Sem o PySide6 instalado, são puladas.
"""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from docmanager.services.credenciais import cofre  # noqa: E402

CAIXAS = ("info", "aviso", "erro", "perguntar", "tentar_de_novo")


@pytest.fixture
def caixas(monkeypatch):
    """Nenhuma caixa de mensagem de verdade: modal, ela travaria a suíte
    esperando um clique. Cada chamada fica anotada (nome, título, texto)."""
    from docmanager.ui import dialogos

    anotadas = []
    for nome in CAIXAS:
        monkeypatch.setattr(dialogos, nome,
                            lambda titulo="", msg="", *a, _n=nome, **_k: anotadas.append((_n, titulo, msg)))
    return anotadas


@pytest.fixture
def app(qtbot, monkeypatch, caixas):
    for k in list(__import__("os").environ):
        if k.startswith(("SECRET_", "CLIENTID_", "USERID_")):
            monkeypatch.delenv(k, raising=False)
    from docmanager.services import updater
    from docmanager.ui import main_app

    # A checagem da abertura iria ao GitHub: aqui não pergunta nada.
    monkeypatch.setattr(updater, "verificar_em_segundo_plano", lambda *a, **k: None)
    main_app.criar_app()
    janela = main_app.MainApp()
    qtbot.addWidget(janela)
    janela.show()
    yield janela
    janela._saindo_para_atualizar = True   # não pergunta nada ao fechar


def test_todas_as_telas_abrem_nos_dois_temas(app, qtbot):
    from PySide6.QtWidgets import QApplication

    from docmanager.ui import main_app, tema

    for escolha in ("claro", "escuro"):
        tema.aplicar(QApplication.instance(), escolha)
        for spec in main_app.VIEWS:
            app.selecionar(spec.key)
            assert app._pilha.currentWidget() is app._views[spec.key]


def test_cadastro_nas_configuracoes_aparece_na_extracao(app):
    """O defeito relatado: cadastrar nas Configurações não chegava na Extração,
    porque a tela dela já estava criada e não relia a lista."""
    app.selecionar("aconex")
    extracao = app._views["aconex"]
    assert extracao.opt_user.get() == extracao._OUTRO          # ninguém cadastrado

    app.selecionar("config")
    cofre().salvar("Fulano Teste", "SCP_FULANO_client_APPID", "1234567890", "segredo")
    app.selecionar("aconex")

    assert "Fulano Teste" in extracao.usuarios_na_lista()
    assert extracao.opt_user.get() == "Fulano Teste"
    assert not extracao.manual_visivel()                        # campos manuais somem
    cfg = extracao._montar_config()
    assert (cfg.client_id, cfg.user_id, cfg.client_secret) == \
        ("SCP_FULANO_client_APPID", "1234567890", "segredo")


def test_cadastro_na_extracao_aparece_nas_configuracoes(app):
    app.selecionar("config")
    config = app._views["config"]
    app.selecionar("aconex")
    cofre().salvar("Ciclano", "SCP_C_client_APPID", "42", "s")
    app.selecionar("config")
    assert "Ciclano" in config._lista_cred.text()
    assert config._opt_cred.get() == "Ciclano"


def test_trocar_o_tema_nas_configuracoes_grava_e_repinta(app):
    from docmanager.ui import estilo

    app.selecionar("config")
    config = app._views["config"]
    config.seletor_tema.botoes["claro"].click()
    assert estilo.TEMA_ATUAL == "claro"
    assert app.ctx.config.settings.tema == "claro"
    assert config.seletor_tema.escolhido() == "claro"
    config.seletor_tema.botoes["escuro"].click()
    assert estilo.TEMA_ATUAL == "escuro"


def test_botao_de_procurar_atualizacao_na_barra_lateral(app, qtbot, monkeypatch, caixas):
    """Visível em qualquer tela; não aceita clique duplo e sempre responde."""
    from docmanager.services import updater

    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: "")
    monkeypatch.setattr(updater, "checar", lambda _v, **_k: None)
    assert app._btn_procurar.text() == app.TEXTO_PROCURAR

    app._btn_procurar.click()
    assert not app._btn_procurar.isEnabled()                   # não aceita clique duplo
    qtbot.waitUntil(lambda: bool(caixas), timeout=5000)
    assert caixas[0][:2] == ("info", "Tudo em dia")
    assert app._btn_procurar.isEnabled()


def test_procurar_explica_por_que_esta_copia_nao_se_atualiza(app, monkeypatch, caixas):
    from docmanager.services import updater

    monkeypatch.setattr(updater, "checar", lambda *a, **k: pytest.fail("não devia consultar"))
    app.verificar_atualizacao(True)                 # código-fonte: não está instalado
    assert caixas and "código-fonte" in caixas[0][2]


def _info_falsa():
    from docmanager.services import updater

    return updater.Atualizacao(versao="9.9.9", notas="- teste", nome_arquivo="Setup.exe",
                               url_asset="https://api/x", tamanho=60_000_000, sha256="",
                               url_pagina="https://github.com/x")


def _info_pequena():
    from docmanager.services import updater

    completo = updater.Atualizacao(versao="9.9.9-rc.1", notas="- teste",
                                   nome_arquivo="DocManager_Itaipu_Setup_9.9.9-rc.1.exe",
                                   url_asset="https://api/c", tamanho=56_000_000, sha256="c",
                                   url_pagina="https://github.com/x", publicado_em="2026-10-23",
                                   tamanho_completo=56_000_000, prerelease=True)
    return updater.replace(completo, nome_arquivo="DocManager_Itaipu_Update_x.zip",
                           url_asset="https://api/z", tamanho=12_900_000, sha256="z",
                           incremental=True, formato="zip", completo=completo, reserva=completo)


def _dialogo(app, info, versao="3.1.0", **kw):
    from docmanager.ui.views.update_dialog import AtualizacaoDialog

    dlg = AtualizacaoDialog(app, info, versao, **kw)
    dlg.PAUSA_ANTES_DE_FECHAR_MS = 10
    dlg.show()
    return dlg


def test_app_so_fecha_quando_o_instalador_fica_pronto(app, qtbot, monkeypatch, tmp_path):
    from docmanager.services import updater

    fechou = []
    monkeypatch.setattr(updater, "baixar", lambda info, **_k: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", lambda caminho, **_k: None)
    dlg = _dialogo(app, _info_falsa(), fechar_app=lambda: fechou.append(1))
    dlg._atualizar()
    qtbot.waitUntil(lambda: bool(fechou), timeout=5000)


def test_app_continua_aberto_se_o_instalador_nao_ficar_pronto(app, qtbot, monkeypatch, tmp_path, caixas):
    """UAC recusado: a atualização não aconteceu, então o app não pode sumir."""
    from docmanager.services import updater

    fechou = []

    def instalar_recusado(caminho, **_k):
        raise updater.InstaladorNaoIniciou("O instalador terminou antes de começar (código 1).")

    monkeypatch.setattr(updater, "baixar", lambda info, **_k: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", instalar_recusado)
    dlg = _dialogo(app, _info_falsa(), fechar_app=lambda: fechou.append(1))
    dlg._atualizar()
    qtbot.waitUntil(lambda: any(c[0] == "erro" for c in caixas), timeout=5000)
    erro = next(c for c in caixas if c[0] == "erro")
    assert "código 1" in erro[2]
    assert not fechou
    assert dlg.btn_atualizar.text() == "Tentar de novo"


def test_fechar_para_instalar_marca_a_saida_do_processo(app):
    """O main() encerra o processo na hora quando a saída é para atualizar."""
    app._saindo_para_atualizar = False
    app._fechar_para_instalar()
    assert app._saindo_para_atualizar is True


def test_checagem_roda_na_abertura_e_abre_o_aviso(qtbot, monkeypatch, caixas):
    """Monta a janela principal DE VERDADE: a abertura pergunta ao GitHub (sem
    intervalo mínimo) e, havendo versão nova, o aviso abre sozinho."""
    from docmanager.services import updater
    from docmanager.services.config import ConfigManager
    from docmanager.ui import main_app

    perguntas = []
    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: "")
    monkeypatch.setattr(updater, "checar",
                        lambda v, **k: (perguntas.append(k.get("canal_testes")), _info_pequena())[1])
    monkeypatch.setattr(main_app.MainApp, "CHECAR_APOS_MS", 10)
    monkeypatch.setattr(main_app.MainApp, "AVISO_APOS_MS", 10)
    # Verificou há 1 minuto: com o intervalo de 6 h, não perguntaria.
    updater.registrar_verificacao(ConfigManager())
    main_app.criar_app()
    janela = main_app.MainApp()
    qtbot.addWidget(janela)
    try:
        qtbot.waitUntil(lambda: janela._dialogo_atualizacao is not None, timeout=10000)
        assert perguntas == [False]                  # canal de testes desligado
        dlg = janela._dialogo_atualizacao
        assert "só o que mudou" in dlg.lbl_resumo.text()
        assert "12,3 MB" in dlg.lbl_resumo.text()
        # Um segundo pedido (botão manual respondendo junto) não abre outro aviso.
        assert janela.abrir_atualizacao() is None
        assert janela._dialogo_atualizacao is dlg
        # A Home e o rodapé da barra também avisam.
        assert janela._views["home"].faixa_visivel()
        assert "9.9.9-rc.1" in janela._rodape.text()
    finally:
        janela._saindo_para_atualizar = True


def test_atualizar_com_tarefa_em_andamento_pergunta_antes(app, monkeypatch, caixas):
    from docmanager.services import updater

    baixou = []
    monkeypatch.setattr(updater, "baixar", lambda *a, **k: baixou.append(1))
    dlg = _dialogo(app, _info_pequena(), "9.9.8", tarefa_em_andamento=lambda: True)
    dlg._atualizar()
    assert [c[0] for c in caixas] == ["perguntar"]   # perguntou (e a resposta foi não)
    assert not baixou and dlg.btn_atualizar.isEnabled()


def test_durante_o_download_x_e_esc_nao_fecham(app, monkeypatch):
    import threading

    from docmanager.services import updater

    liberar = threading.Event()
    monkeypatch.setattr(updater, "baixar", lambda *a, **k: (liberar.wait(5), 1 / 0))
    dlg = _dialogo(app, _info_pequena(), "9.9.8")
    dlg._atualizar()
    dlg.reject()          # o que o Esc faz
    dlg.close()           # o "X"
    assert dlg.isVisible()
    liberar.set()


def test_caiu_no_completo_aparece_na_janela(app, qtbot, monkeypatch, tmp_path):
    from docmanager.services import updater

    info = _info_pequena()

    def baixar(i, *, ao_cair_no_completo=None, **_k):
        ao_cair_no_completo(i.completo, RuntimeError("cortado"))
        return tmp_path / "Setup.exe"

    fechou = []
    monkeypatch.setattr(updater, "baixar", baixar)
    monkeypatch.setattr(updater, "instalar", lambda caminho, **_k: None)
    dlg = _dialogo(app, info, "9.9.8", fechar_app=lambda: fechou.append(1))
    dlg._atualizar()
    qtbot.waitUntil(lambda: "completo" in dlg.lbl_resumo.text(), timeout=5000)
    qtbot.waitUntil(lambda: bool(fechou), timeout=5000)


# ─────────────────────────── componentes ────────────────────────────────────

def test_runbar_roda_em_thread_e_volta_ao_normal(qtbot):
    from docmanager.ui.components import LogConsole, RunBar

    log = LogConsole()
    feito = []

    def tarefa(run):
        run.set_progress(0.5)
        log.log("trabalhando")
        feito.append(1)

    rb = RunBar("Rodar", tarefa, log)
    qtbot.addWidget(rb)
    with qtbot.waitSignal(rb.terminou, timeout=5000):
        rb.btn.click()
    assert feito and rb.btn.isEnabled() and rb.btn.text() == "Rodar"
    assert not RunBar.em_andamento
    qtbot.waitUntil(lambda: "trabalhando" in log.texto(), timeout=2000)


def test_runbar_manda_o_erro_para_o_log(qtbot):
    from docmanager.ui.components import LogConsole, RunBar

    log = LogConsole()
    rb = RunBar("Rodar", lambda run: 1 / 0, log)
    qtbot.addWidget(rb)
    with qtbot.waitSignal(rb.terminou, timeout=5000):
        rb.btn.click()
    qtbot.waitUntil(lambda: "ERRO: division by zero" in log.texto(), timeout=2000)


def test_tarefa_em_thread_pergunta_e_recebe_a_resposta(qtbot, monkeypatch):
    """A ponte: um diálogo pedido de outra thread abre na da interface e a
    resposta volta para a tarefa (o "Salvar como" no meio da extração)."""
    import threading

    from docmanager.ui import ponte

    respostas = []
    thread_da_resposta = []

    def perguntar():
        thread_da_resposta.append(threading.current_thread() is threading.main_thread())
        return "ok"

    t = threading.Thread(target=lambda: respostas.append(ponte.na_ui_e_esperar(perguntar)))
    t.start()
    qtbot.waitUntil(lambda: bool(respostas), timeout=5000)
    t.join()
    assert respostas == ["ok"] and thread_da_resposta == [True]


def test_seletor_ignora_a_roda_sem_foco(qtbot):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    from docmanager.ui.components import Seletor

    s = Seletor(["A", "B", "C"])
    qtbot.addWidget(s)
    evento = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120),
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                         Qt.ScrollPhase.NoScrollPhase, False)
    s.wheelEvent(evento)
    assert s.get() == "A"


def test_seletor_de_arquivo_lista_as_abas(qtbot, tmp_path):
    import openpyxl

    from docmanager.ui.components import FileSelector

    caminho = tmp_path / "base.xlsx"
    wb = openpyxl.Workbook()
    wb.active.title = "Outra"
    wb.create_sheet("Documentos")
    wb.save(caminho)
    sel = FileSelector("Base Aconex", aba_padrao="Documentos")
    qtbot.addWidget(sel)
    sel.definir(str(caminho))
    assert sel.path == str(caminho)
    assert sel.sheet == "Documentos"
    sel.opt_aba.setCurrentText("Outra")
    assert sel.sheet == "Outra"


def test_dialogos_de_arvore_abrem_e_mostram_documentos(app, qtbot):
    from docmanager.ui.views.delta_dialog import DeltaDialog

    dlg = DeltaDialog(app, path_map="x", sheet_map="a", path_hist="y", sheet_hist="b", cols_config={})
    qtbot.addWidget(dlg)
    doc = {"doc": "IT-1", "raw_antes": "Em Processo", "real_antes": "Em Processo",
           "raw_depois": "Aprovado", "real_depois": "Aprovado", "repetido_grupos": True}
    dlg._concluir((True, {"G1": {"2": [doc]}}, 1))
    grupo = dlg.tree.topLevelItem(0)
    assert grupo.text(0) == "G1 (1)"
    item = grupo.child(0).child(0)
    assert item.text(0) == "IT-1" and item.text(7) == "Aprovado"
    assert dlg.btn_exportar.isEnabled()
    assert dlg.tree.isColumnHidden(1)                 # visão Efetiva: sem Rev/Data
    dlg.opt_visao.setCurrentText("Bruta")
    assert not dlg.tree.isColumnHidden(1)


def test_consulta_rapida_mostra_o_status_na_tela(app, qtbot, monkeypatch):
    """Cola os códigos, consulta (API falsa) e a tabela mostra o status real."""
    from docmanager import aconex_backend as ab
    from test_aconex_consulta import HISTORICO_IT1, _Sessao

    sessao = _Sessao({"IT-1": HISTORICO_IT1})
    monkeypatch.setattr(ab, "_estabelecer_sessao", lambda cfg, log=None: (sessao, "tok"))
    monkeypatch.setattr(ab, "_injetar_certificados", lambda log=None: None)
    cofre().salvar("Fulano", "SCP_F_client_APPID", "123", "segredo")
    app.selecionar("aconex")
    tela = app._views["aconex"]
    assert tela.tabs.get() == "Consulta Rápida"          # a primeira aba
    tela.txt_consulta.setPlainText("IT-1\nNADA")
    run = tela.tabs._pilha.currentWidget().findChild(__import__(
        "docmanager.ui.components", fromlist=["RunBar"]).RunBar)
    with qtbot.waitSignal(run.terminou, timeout=10000):
        run.btn.click()
    qtbot.waitUntil(lambda: bool(tela.linhas_da_consulta()), timeout=5000)
    linhas = tela.linhas_da_consulta()
    assert linhas[0][0] == "IT-1" and linhas[0][-1] == "Aprovado"
    assert linhas[1][-1] == "NÃO EMITIDO"
    assert tela.btn_exportar_consulta.isEnabled()


def test_download_oferece_o_original_sem_comentarios(app):
    app.selecionar("aconex")
    tela = app._views["aconex"]
    assert set(tela.MODOS_DOWNLOAD.values()) == {"marcado", "original"}
    assert tela._estado()["modo_download"] == "marcado"     # o padrão de sempre
    tela.opt_modo_download.setCurrentIndex(1)
    assert tela._estado()["modo_download"] == "original"
