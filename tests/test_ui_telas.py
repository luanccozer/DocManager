"""Telas de verdade (CustomTkinter), para o que só aparece com a janela aberta.

Precisa de tela: roda no Windows de quem desenvolve e em Linux com Xvfb
(`xvfb-run -a pytest`); sem display, os testes são pulados.
"""
import pytest

from docmanager.services.credenciais import cofre


@pytest.fixture
def app(monkeypatch):
    for k in list(__import__("os").environ):
        if k.startswith(("SECRET_", "CLIENTID_", "USERID_")):
            monkeypatch.delenv(k, raising=False)
    tk = pytest.importorskip("tkinter")
    try:
        from docmanager.ui.main_app import MainApp
        janela = MainApp()
    except (tk.TclError, ImportError) as e:
        pytest.skip(f"sem display para abrir a janela: {e}")
    janela.update()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:
        pass   # o teste já fechou a janela (ex.: saída para atualizar)


def test_cadastro_nas_configuracoes_aparece_na_extracao(app):
    """O defeito relatado: cadastrar nas Configurações não chegava na Extração,
    porque a tela dela já estava criada e não relia a lista."""
    app.selecionar("aconex")
    extracao = app._views["aconex"]
    assert extracao.opt_user.get() == extracao._OUTRO          # ninguém cadastrado

    app.selecionar("config")
    cofre().salvar("Fulano Teste", "SCP_FULANO_client_APPID", "1234567890", "segredo")
    app.selecionar("aconex")
    app.update()

    assert "Fulano Teste" in extracao.opt_user.cget("values")
    assert extracao.opt_user.get() == "Fulano Teste"
    assert not extracao._manual.winfo_ismapped()               # campos manuais somem
    cfg = extracao._montar_config()
    assert (cfg.client_id, cfg.user_id, cfg.client_secret) == \
        ("SCP_FULANO_client_APPID", "1234567890", "segredo")


def test_cadastro_na_extracao_aparece_nas_configuracoes(app):
    app.selecionar("config")
    config = app._views["config"]
    app.selecionar("aconex")
    cofre().salvar("Ciclano", "SCP_C_client_APPID", "42", "s")
    app.selecionar("config")
    assert "Ciclano" in config._lista_cred.cget("text")
    assert config._opt_cred.get() == "Ciclano"


def _esperar(app, condicao, segundos=10.0):
    """Roda o mainloop até `condicao()` ou o tempo acabar.

    Tem de ser o mainloop de verdade (e não `update()` em laço): as threads de
    trabalho falam com a interface por `after`, e o Tk só aceita isso de outra
    thread com o mainloop rodando - como no app."""
    import time

    limite = time.monotonic() + segundos

    def checar():
        if condicao() or time.monotonic() > limite:
            app.quit()
        else:
            app.after(20, checar)

    app.after(20, checar)
    app.mainloop()
    return condicao()


def test_botao_de_procurar_atualizacao_na_barra_lateral(app, monkeypatch):
    """Visível em qualquer tela (antes só existia dentro das Configurações)."""
    from tkinter import messagebox

    from docmanager.services import updater

    avisos = []
    monkeypatch.setattr(updater, "checar", lambda _v, **_k: None)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **_k: avisos.append(a))
    assert app._btn_procurar.cget("text") == app.TEXTO_PROCURAR

    app._btn_procurar.invoke()
    assert app._btn_procurar.cget("state") == "disabled"      # não aceita clique duplo
    assert _esperar(app, lambda: avisos)
    assert avisos[0][0] == "Tudo em dia"
    assert app._btn_procurar.cget("state") == "normal"


def _info_falsa():
    from docmanager.services import updater

    return updater.Atualizacao(versao="9.9.9", notas="- teste", nome_arquivo="Setup.exe",
                               url_asset="https://api/x", tamanho=60_000_000, sha256="",
                               url_pagina="https://github.com/x")


def test_app_so_fecha_quando_o_instalador_fica_pronto(app, monkeypatch, tmp_path):
    from docmanager.services import updater
    from docmanager.ui.views.update_dialog import AtualizacaoDialog

    fechou = []
    monkeypatch.setattr(updater, "baixar", lambda info, **_k: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", lambda caminho, **_k: None)
    dlg = AtualizacaoDialog(app, _info_falsa(), "3.1.0", fechar_app=lambda: fechou.append(1))
    dlg._atualizar()
    assert _esperar(app, lambda: fechou)


def test_app_continua_aberto_se_o_instalador_nao_ficar_pronto(app, monkeypatch, tmp_path):
    """UAC recusado: a atualização não aconteceu, então o app não pode sumir."""
    from tkinter import messagebox

    from docmanager.services import updater
    from docmanager.ui.views.update_dialog import AtualizacaoDialog

    fechou, erros = [], []

    def instalar_recusado(caminho, **_k):
        raise updater.InstaladorNaoIniciou("O instalador terminou antes de começar (código 1).")

    monkeypatch.setattr(updater, "baixar", lambda info, **_k: tmp_path / "Setup.exe")
    monkeypatch.setattr(updater, "instalar", instalar_recusado)
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **_k: erros.append(a))
    dlg = AtualizacaoDialog(app, _info_falsa(), "3.1.0", fechar_app=lambda: fechou.append(1))
    dlg._atualizar()
    assert _esperar(app, lambda: erros)
    assert "código 1" in erros[0][1]
    assert not fechou
    assert dlg.btn_atualizar.cget("text") == "Tentar de novo"


def test_fechar_para_instalar_marca_a_saida_do_processo(app):
    """O main() encerra o processo na hora quando a saída é para atualizar."""
    assert app._saindo_para_atualizar is False
    app._fechar_para_instalar()
    assert app._saindo_para_atualizar is True
