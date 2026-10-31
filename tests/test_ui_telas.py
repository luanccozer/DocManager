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


def test_procurar_atualizacao_na_engrenagem_responde_uma_vez(app, qtbot, monkeypatch, caixas):
    """Mora nas Configurações (a engrenagem) e no Ctrl+K; clique duplo não
    abre duas consultas, e sempre responde."""
    from docmanager.services import updater

    consultas = []
    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: "")
    monkeypatch.setattr(updater, "checar", lambda _v, **_k: consultas.append(1))
    assert not hasattr(app, "_btn_procurar")                   # saiu da barra lateral

    app.selecionar("config")
    app._views["config"]._procurar()
    app.verificar_atualizacao(True)                            # o 2º clique, ainda procurando
    qtbot.waitUntil(lambda: bool(caixas), timeout=5000)
    assert caixas[0][:2] == ("info", "Tudo em dia")
    assert len(consultas) == 1


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

    return updater.Atualizacao(versao="9.9.9-rc.1", notas="- teste",
                               nome_arquivo="DocManager_Itaipu_Setup_9.9.9-rc.1.exe",
                               url_asset="https://api/c", tamanho=56_000_000, sha256="c",
                               url_pagina="https://github.com/x", publicado_em="2026-10-23",
                               prerelease=True,
                               pequena=updater.Pacote("p.zip", "https://api/z", 12_900_000, "z"),
                               arquivos=updater.Pacote("arquivos.json", "https://api/a", 9_000, "a"))


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
    monkeypatch.setattr(updater, "pode_pequena", lambda info: True)
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


def test_pequena_aplicada_reabre_o_exe_novo_e_fecha(app, qtbot, monkeypatch, tmp_path):
    """O método da CMI Suite: sem instalador - aplica, abre o .exe novo, sai."""
    from docmanager.services import updater

    reabertos, fechou = [], []
    monkeypatch.setattr(updater, "pode_pequena", lambda info: True)
    monkeypatch.setattr(updater, "atualizar_pequena", lambda info, **_k: tmp_path / "DocManager.exe")
    monkeypatch.setattr(updater, "reabrir", reabertos.append)
    monkeypatch.setattr(updater, "baixar", lambda *a, **k: pytest.fail("não devia baixar o completo"))
    dlg = _dialogo(app, _info_pequena(), "9.9.8", fechar_app=lambda: fechou.append(1))
    assert "só o que mudou" in dlg.lbl_resumo.text()
    dlg._atualizar()
    qtbot.waitUntil(lambda: bool(fechou), timeout=5000)
    assert reabertos == [str(tmp_path / "DocManager.exe")]


def test_pequena_que_falha_cai_no_completo(app, qtbot, monkeypatch, tmp_path):
    from docmanager.services import updater

    def falha(info, **_k):
        raise updater.pacote.ErroPacote("cortado")

    fechou = []
    monkeypatch.setattr(updater, "pode_pequena", lambda info: True)
    monkeypatch.setattr(updater, "atualizar_pequena", falha)
    monkeypatch.setattr(updater, "reabrir", lambda exe: pytest.fail("não devia reabrir"))
    monkeypatch.setattr(updater, "baixar", lambda info, **_k: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", lambda caminho, **_k: None)
    dlg = _dialogo(app, _info_pequena(), "9.9.8", fechar_app=lambda: fechou.append(1))
    dlg._atualizar()
    qtbot.waitUntil(lambda: "nada foi alterado" in dlg.lbl_resumo.text(), timeout=5000)
    assert "cortado" in dlg.lbl_resumo.text()
    qtbot.waitUntil(lambda: bool(fechou), timeout=5000)


def test_pequena_aplicada_que_nao_reabre_avisa_e_nao_fecha(app, qtbot, monkeypatch, tmp_path):
    from docmanager.services import updater
    from docmanager.ui import dialogos

    erros, fechou = [], []

    def nao_abre(exe):
        raise OSError("bloqueado")

    monkeypatch.setattr(updater, "pode_pequena", lambda info: True)
    monkeypatch.setattr(updater, "atualizar_pequena", lambda info, **_k: tmp_path / "DocManager.exe")
    monkeypatch.setattr(updater, "reabrir", nao_abre)
    monkeypatch.setattr(dialogos, "erro", lambda titulo, msg, parent=None: erros.append(msg))
    dlg = _dialogo(app, _info_pequena(), "9.9.8", fechar_app=lambda: fechou.append(1))
    dlg._atualizar()
    qtbot.waitUntil(lambda: bool(erros), timeout=5000)
    assert "Feche o DocManager e abra de novo" in erros[0] and not fechou


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


def _ainda_aberto(caminho) -> bool:
    """O próprio processo ainda segura o arquivo? No Linux, pela lista de
    descritores; no Windows, um arquivo aberto não pode ser renomeado."""
    import os
    from pathlib import Path

    alvo = os.path.realpath(caminho)
    descritores = Path("/proc/self/fd")
    if descritores.is_dir():
        for fd in descritores.iterdir():
            try:
                if os.path.realpath(os.readlink(fd)) == alvo:
                    return True
            except OSError:
                pass
        return False
    if os.name == "nt":
        try:
            os.replace(caminho, f"{caminho}.tmp")
            os.replace(f"{caminho}.tmp", caminho)
            return False
        except PermissionError:
            return True
    pytest.skip("sem como listar os arquivos abertos neste sistema")


def test_seletor_de_arquivo_nao_deixa_a_planilha_aberta(qtbot, tmp_path):
    """Listar as abas não pode prender o arquivo: preso pelo próprio app, o Windows
    recusava salvar a planilha depois ("permissão negada", 3.6.1-rc.1)."""
    import gc

    import openpyxl

    from docmanager.ui.components import FileSelector

    caminho = tmp_path / "Doc List Mapping.xlsx"
    openpyxl.Workbook().save(caminho)
    sel = FileSelector("Doc List Mapping")
    qtbot.addWidget(sel)
    gc.disable()  # sem o coletor de lixo fechando o arquivo por acaso no meio do teste
    try:
        sel.definir(str(caminho))
        assert sel.sheet == "Sheet"
        assert not _ainda_aberto(str(caminho))
    finally:
        gc.enable()
        # Coleta já, na thread da interface: deixado para depois, o lixo acumulado
        # (com objetos do Qt) podia ser coletado na thread de outro teste, e o Qt
        # derruba o processo quando um objeto dele morre fora da thread da interface.
        gc.collect()


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


def test_transpasse_gera_o_painel_e_abre_no_navegador(app, qtbot, monkeypatch, tmp_path):
    """Seleciona as duas planilhas, gera e abre - a complementar é opcional."""
    import webbrowser

    from docmanager.ui import dialogos
    from test_transpasse import GRUPO_002, complementar_com_inicio, planilha_principal

    saida = tmp_path / "painel.html"
    monkeypatch.setattr(dialogos, "pedir_salvar", lambda *a, **k: str(saida))
    abertos = []
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: abertos.append(url))
    app.selecionar("transpasse")
    tela = app._views["transpasse"]
    tela.sel_principal.definir(str(planilha_principal(tmp_path / "a.xlsx", [GRUPO_002])))
    tela.sel_complementar.definir(str(complementar_com_inicio(tmp_path / "c.xlsx")))

    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()

    assert abertos == [saida.as_uri()]
    assert "Painel gerado" in tela.log.texto()


def test_transpasse_sem_a_planilha_principal_so_avisa(app, qtbot, monkeypatch):
    from docmanager.ui import dialogos

    pediu = []
    monkeypatch.setattr(dialogos, "pedir_salvar", lambda *a, **k: pediu.append(a) or "")
    app.selecionar("transpasse")
    tela = app._views["transpasse"]

    with qtbot.waitSignal(tela.run.terminou, timeout=10000):
        tela.run.btn.click()

    assert not pediu
    assert "Selecione a planilha de acompanhamento" in tela.log.texto()


def test_download_oferece_o_original_sem_comentarios(app):
    app.selecionar("aconex")
    tela = app._views["aconex"]
    assert set(tela.MODOS_DOWNLOAD.values()) == {"marcado", "original"}
    assert tela._estado()["modo_download"] == "marcado"     # o padrão de sempre
    tela.opt_modo_download.setCurrentIndex(1)
    assert tela._estado()["modo_download"] == "original"


# ─────────────────────────── abertura ───────────────────────────────────────

def test_splash_mostra_a_mesma_imagem_da_nativa(qtbot):
    """Uma tela só na abertura: a splash do Qt é a imagem que o bootloader do
    .exe mostra (`assets/splash.png`, a do Splash no docmanager.spec)."""
    from PySide6.QtGui import QImage

    from docmanager.ui import main_app, splash

    main_app.criar_app()
    caminho = splash.caminho_da_imagem()
    assert caminho.replace("\\", "/").endswith("assets/splash.png")
    tela = splash.mostrar_splash()
    assert tela is not None
    qtbot.addWidget(tela)
    assert tela.pixmap().toImage().convertToFormat(QImage.Format.Format_RGB32) == \
        QImage(caminho).convertToFormat(QImage.Format.Format_RGB32)
    assert '"assets/splash.png"' in open(
        splash.os.path.join(splash.os.path.dirname(caminho), "..", "docmanager.spec"),
        encoding="utf-8").read()


def test_splash_sem_imagem_nao_impede_a_abertura(monkeypatch):
    from docmanager.ui import main_app, splash

    main_app.criar_app()
    monkeypatch.setattr(splash, "caminho_da_imagem", lambda: "")
    assert splash.mostrar_splash() is None


def test_janela_abre_maximizada_e_a_splash_sai(qtbot, monkeypatch, caixas):
    from docmanager.services import updater
    from docmanager.ui import main_app, splash

    monkeypatch.setattr(updater, "verificar_em_segundo_plano", lambda *a, **k: None)
    abertas = []
    original = splash.mostrar_splash
    monkeypatch.setattr(splash, "mostrar_splash", lambda: abertas.append(original()) or abertas[-1])
    app = main_app.criar_app()
    janela = main_app.abrir(app)
    qtbot.addWidget(janela)
    try:
        assert janela.isMaximized()
        qtbot.waitUntil(lambda: not abertas[0].isVisible(), timeout=5000)
    finally:
        janela._saindo_para_atualizar = True


# ---------------------------------------------------------------------------
# Tela de sobrescrição (ADR 0001): o Controle trocaria datas já preenchidas
# ---------------------------------------------------------------------------
def _incidencias_exemplo():
    from datetime import date

    from docmanager.services.sobrescricao import IncidenciaDoc

    return [IncidenciaDoc(row=2, cod_itaipu="#IT-1", cod_cmi="CMI-1", descricao="DOC 1",
                          coluna="prevista", titulo_coluna="DATA PREVISTA EMISSÃO",
                          valor_planilha=date(2026, 3, 1), data_controle=date(2026, 9, 1)),
            IncidenciaDoc(row=3, cod_itaipu="#IT-2", cod_cmi="CMI-2", descricao="DOC 2",
                          coluna="reprogramada", titulo_coluna="DATA REPROGRAMADA",
                          valor_planilha="A DEFINIR", data_controle=date(2026, 12, 15))]


def _quando_abrir(classe, acao):
    """Age na janela modal assim que ela abrir. Ela roda o próprio laço de
    eventos (exec), então quem age é um timer, que dispara dentro dele."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    timer = QTimer()
    timer.setInterval(20)

    def _tick():
        janela = QApplication.activeModalWidget()
        if isinstance(janela, classe):
            timer.stop()
            acao(janela)

    timer.timeout.connect(_tick)
    timer.start()
    return timer


def test_sobrescricao_apaga_as_janelas_depois_de_respondidas(qtbot):
    """Sem dono, a janela respondida ficava para o coletor de lixo, que pode rodar
    numa thread de trabalho - e o Qt derruba o processo quando um objeto dele
    morre fora da thread da interface. Com dono (a tela), ficava escondida para
    sempre, uma a mais a cada atualização."""
    import shiboken6
    from PySide6.QtCore import QCoreApplication, QEvent

    from docmanager.ui.views.sobrescricao_dialog import (
        CasoACasoDialog,
        EscolhaSobrescricao,
        decidir_sobrescricoes,
    )

    janelas = []

    def guardar_e(acao):
        def agir(w):
            janelas.append(w)
            acao(w)
        return agir

    _t1 = _quando_abrir(EscolhaSobrescricao, guardar_e(lambda w: w.btn_caso.click()))
    _t2 = _quando_abrir(CasoACasoDialog, guardar_e(lambda w: w.btn_trocar.click()))
    assert decidir_sobrescricoes(_incidencias_exemplo()) is not None
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(janelas) == 2
    assert not any(shiboken6.isValid(w) for w in janelas)


def test_sobrescricao_aceitar_todas(qtbot):
    from docmanager.services.sobrescricao import DecisaoSobrescricao
    from docmanager.ui.views.sobrescricao_dialog import EscolhaSobrescricao, decidir_sobrescricoes

    _t = _quando_abrir(EscolhaSobrescricao, lambda w: w.btn_aceitar.click())
    assert decidir_sobrescricoes(_incidencias_exemplo()) == DecisaoSobrescricao.aceitar_todas(2)


def test_sobrescricao_nao_sobrescrever(qtbot):
    from docmanager.services.sobrescricao import DecisaoSobrescricao
    from docmanager.ui.views.sobrescricao_dialog import EscolhaSobrescricao, decidir_sobrescricoes

    _t = _quando_abrir(EscolhaSobrescricao, lambda w: w.btn_recusar.click())
    assert decidir_sobrescricoes(_incidencias_exemplo()) == DecisaoSobrescricao.recusar_todas(2)


def test_fechar_a_tela_de_sobrescricao_e_decidir_depois(qtbot):
    from docmanager.ui.views.sobrescricao_dialog import EscolhaSobrescricao, decidir_sobrescricoes

    _t = _quando_abrir(EscolhaSobrescricao, lambda w: w.reject())
    assert decidir_sobrescricoes(_incidencias_exemplo()) is None


def test_sobrescricao_avisa_que_a_data_prevista_e_a_baseline(qtbot):
    from docmanager.ui.views.sobrescricao_dialog import EscolhaSobrescricao

    tela = EscolhaSobrescricao(_incidencias_exemplo())
    qtbot.addWidget(tela)
    assert "2 datas" in tela.lbl_resumo.text()
    assert "baseline" in tela.lbl_aviso.text()


def test_caso_a_caso_troca_as_marcadas_e_recusa_as_outras(qtbot):
    from docmanager.services.sobrescricao import DecisaoSobrescricao
    from docmanager.ui.views.sobrescricao_dialog import (
        CasoACasoDialog,
        EscolhaSobrescricao,
        decidir_sobrescricoes,
    )

    vistas = []

    def marcar_a_segunda(w):
        vistas.extend([w.tree.topLevelItem(i).text(3) for i in range(w.tree.topLevelItemCount())])
        w.marcar(1, True)
        w.btn_trocar.click()

    _t1 = _quando_abrir(EscolhaSobrescricao, lambda w: w.btn_caso.click())
    _t2 = _quando_abrir(CasoACasoDialog, marcar_a_segunda)
    decisao = decidir_sobrescricoes(_incidencias_exemplo())
    assert decisao == DecisaoSobrescricao(aceitas=frozenset({1}), recusadas=frozenset({0}))
    assert vistas == ["01/03/2026", "'A DEFINIR'"]       # o que a planilha tem hoje


def test_caso_a_caso_marcar_todas_e_cancelar(qtbot):
    from docmanager.ui.views.sobrescricao_dialog import CasoACasoDialog

    tela = CasoACasoDialog(_incidencias_exemplo())
    qtbot.addWidget(tela)
    assert tela.decisao().aceitas == frozenset()          # começa tudo desmarcado
    tela.btn_marcar.click()
    assert tela.decisao().aceitas == frozenset({0, 1})
    tela.btn_desmarcar.click()
    assert tela.decisao().recusadas == frozenset({0, 1})


def test_doclist_pergunta_antes_de_trocar_uma_data_preenchida(app, qtbot, tmp_path):
    """A tela de verdade: a atualização roda em thread e a pergunta abre na
    janela; aceitar troca a data na planilha."""
    from datetime import date

    import openpyxl
    from builders import escrever_controle_xlsx
    from test_doclist import _preparar_planilha

    from docmanager.ui.views.sobrescricao_dialog import EscolhaSobrescricao

    path_base, path_dl = _preparar_planilha(tmp_path)
    path_ctrl = escrever_controle_xlsx(tmp_path / "ctrl.xlsx",
                                       [{"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "01-09-2026"}])
    app.selecionar("doclist")
    tela = app._views["doclist"]
    tela.sel_aconex.definir(str(path_base))
    tela.sel_doclist.definir(str(path_dl))
    tela.sel_ctrl.definir(str(path_ctrl))

    _t = _quando_abrir(EscolhaSobrescricao, lambda w: w.btn_aceitar.click())
    with qtbot.waitSignal(tela.run.terminou, timeout=20000):
        tela.run.btn.click()

    ws = openpyxl.load_workbook(path_dl).active
    col = {str(c.value): c.column for c in ws[1]}
    assert ws.cell(2, col["DATA PREVISTA EMISSÃO"]).value.date() == date(2026, 9, 1)
    assert "Sobrescrição aceita" in tela.log.texto()


def test_mapa_pergunta_antes_de_trocar_uma_data_preenchida(app, qtbot, tmp_path):
    from datetime import date

    import openpyxl
    from builders import HistoricoBuilder, base, escrever_controle_xlsx
    from test_controle_docs import _COLS_MAPA

    from docmanager.services.sobrescricao import ABA_RECUSAS
    from docmanager.ui.views.sobrescricao_dialog import EscolhaSobrescricao

    path_base = tmp_path / "base.xlsx"
    base(HistoricoBuilder("T1", "#IT-1", "CMI-1", "DOC")
         .evento("0A", 1, "Em Processo", "01/09/2025", current=True)).to_excel(path_base, index=False)
    path_mapa = tmp_path / "mapa.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    for c, nome in enumerate(_COLS_MAPA, 1):
        ws.cell(1, c, nome)
    ws.cell(3, 1, "SALAS"), ws.cell(3, 2, "CMI-1"), ws.cell(3, 3, "#IT-1"), ws.cell(3, 5, "4")
    ws.cell(3, _COLS_MAPA.index("DATA PREVISTA EMISSÃO ETAPA 1") + 1, date(2026, 1, 1))
    wb.save(path_mapa)
    path_ctrl = escrever_controle_xlsx(tmp_path / "ctrl.xlsx",
                                       [{"itaipu": "#IT-1", "cmi": "CMI-1", "prevista": "30-06-2026"}])
    app.selecionar("mapa")
    tela = app._views["mapa"]
    tela.sel_aconex.definir(str(path_base))
    tela.sel_mapa.definir(str(path_mapa))
    tela.sel_ctrl.definir(str(path_ctrl))

    _t = _quando_abrir(EscolhaSobrescricao, lambda w: w.btn_recusar.click())
    with qtbot.waitSignal(tela.run.terminou, timeout=20000):
        tela.run.btn.click()

    wb2 = openpyxl.load_workbook(path_mapa)
    assert str(wb2.active.cell(3, _COLS_MAPA.index("DATA PREVISTA EMISSÃO ETAPA 1") + 1).value) \
        .startswith("2026-01-01")
    assert ABA_RECUSAS in wb2.sheetnames


# ─────────────────────────────── sugestões ──────────────────────────────────

def test_sugestao_abre_rascunho_para_o_email_configurado(app, monkeypatch, caixas):
    from PySide6.QtGui import QDesktopServices

    abertos = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: (abertos.append(url.toString()), True)[1])
    app.selecionar("config")
    config = app._views["config"]
    config.email_sugestoes.setText("quem.cuida@empresa.com")
    config._salvar_email_sugestoes()
    app.selecionar("sugestoes")
    tela = app._views["sugestoes"]
    assert "quem.cuida@empresa.com" in tela.lbl_destino.text()
    tela.sel_tipo.setCurrentText("Erro")
    tela.texto.setPlainText("O Doc List não salvou.")
    tela.btn_email.click()
    assert len(abertos) == 1 and abertos[0].startswith("mailto:quem.cuida@empresa.com?")
    assert not caixas


def test_sugestao_vazia_avisa_e_nao_abre_nada(app, monkeypatch, caixas):
    from PySide6.QtGui import QDesktopServices

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: pytest.fail("não devia abrir"))
    app.selecionar("sugestoes")
    app._views["sugestoes"].btn_email.click()
    assert caixas and caixas[0][1] == "Sugestões"


def test_sem_programa_de_email_copia_o_texto(app, monkeypatch, caixas):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QApplication

    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: False)
    app.selecionar("sugestoes")
    tela = app._views["sugestoes"]
    tela.texto.setPlainText("Ideia: exportar em PDF.")
    tela.btn_email.click()
    assert "Ideia: exportar em PDF." in QApplication.clipboard().text()
    assert caixas and "copiado" in caixas[0][2]


def test_email_invalido_nas_configuracoes_nao_e_salvo(app, caixas):
    app.selecionar("config")
    config = app._views["config"]
    antes = app.ctx.config.settings.email_sugestoes
    config.email_sugestoes.setText("isto não é e-mail")
    config._salvar_email_sugestoes()
    assert app.ctx.config.settings.email_sugestoes == antes
    assert caixas and caixas[0][1] == "Sugestões"


def test_lampada_e_engrenagem_no_alto_como_na_cmi_suite(app):
    """Lâmpada e engrenagem lado a lado no alto, fora da barra lateral."""
    from PySide6.QtWidgets import QFrame

    lampada, engrenagem = app._botoes["sugestoes"], app._botoes["config"]
    assert lampada.parentWidget() is engrenagem.parentWidget()   # mesma faixa
    barra = app.findChild(QFrame, "sidebar")
    assert not barra.isAncestorOf(lampada) and not barra.isAncestorOf(engrenagem)
    assert lampada.text() == engrenagem.text() == ""
    assert "Sugestões" in lampada.toolTip() and "Configurações" in engrenagem.toolTip()
    lampada.click()
    assert app._pilha.currentWidget() is app._views["sugestoes"]
    engrenagem.click()
    assert app._pilha.currentWidget() is app._views["config"]


# ─────────────────── "O que mudou na vX" (igual ao da CMI Suite) ─────────────

def _home(qtbot, versao_vista=None):
    from docmanager.services.config import ConfigManager
    from docmanager.ui.app_context import AppContext
    from docmanager.ui.views.home_view import HomeView

    if versao_vista is not None:
        ConfigManager().set_setting("versao_vista", versao_vista)   # cria o config.json
    ctx = AppContext(config=ConfigManager(), versao="3.6.1")
    home = HomeView(ctx)
    qtbot.addWidget(home)
    return home, ctx


def test_novidades_aparecem_uma_vez_depois_de_atualizar(qtbot):
    home, ctx = _home(qtbot, versao_vista="3.6.0")
    assert home.novidades_visiveis()
    home.btn_entendi.click()
    assert not home.novidades_visiveis()
    assert ctx.config.settings.versao_vista == "3.6.1"
    home2, _ = _home(qtbot)                       # a abertura seguinte: não aparece mais
    assert not home2.novidades_visiveis()


def test_primeira_instalacao_nao_mostra_novidades(qtbot):
    home, ctx = _home(qtbot)
    assert not home.novidades_visiveis()
    assert ctx.config.settings.versao_vista == "3.6.1"   # anota para a próxima


def test_quem_vem_de_antes_da_versao_vista_tambem_ve(qtbot):
    """Até a 3.6.1 não se gravava a versão vista; quem já tinha config vê."""
    from docmanager.services.config import ConfigManager

    ConfigManager().set_setting("tema", "escuro")              # já usava o app
    home, _ = _home(qtbot)
    assert home.novidades_visiveis()


# ──────────────────────────── letra grande ──────────────────────────────────

def test_letra_grande_aumenta_a_folha_na_hora_e_fica_gravada(app):
    from PySide6.QtWidgets import QApplication

    from docmanager.ui import estilo, tema

    normal = estilo.fontes()["corpo"]
    try:
        app.selecionar("config")
        app._views["config"].seletor_letra.botoes["grande"].click()
        assert estilo.LETRA_ATUAL == "grande"
        assert estilo.fontes()["corpo"] == normal + 2
        assert f"font-size: {normal + 2}px" in QApplication.instance().styleSheet()
        assert app.ctx.config.settings.letra == "grande"
    finally:
        tema.aplicar_letra(QApplication.instance(), "normal")


def test_trocar_o_idioma_grava_e_avisa_que_vale_ao_reabrir(app):
    app.selecionar("config")
    config = app._views["config"]
    config.seletor_idioma.botoes["en"].click()
    assert app.ctx.config.settings.idioma == "en"
    assert not config._aviso_idioma.isHidden()


def test_seletor_guarda_a_chave_atras_do_texto_traduzido(qtbot):
    from docmanager.ui.components import Seletor

    s = Seletor(opcoes=[("Last 7 days", "Últimos 7 dias"), ("Everything", "Tudo (~20 min)")])
    qtbot.addWidget(s)
    assert s.chave() == "Últimos 7 dias"
    s.definir_opcoes([("A", "a"), ("B", "b")], "b")
    assert (s.get(), s.chave()) == ("B", "b")
    sem_chave = Seletor(["Aba 1"])
    qtbot.addWidget(sem_chave)
    assert sem_chave.chave() == "Aba 1"          # item sem chave: o próprio texto
