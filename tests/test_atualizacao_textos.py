"""Textos da janela de atualização - testáveis sem abrir janela nenhuma."""
from docmanager.services import updater
from docmanager.ui import atualizacao_textos as txt


def _info(**k):
    base = dict(versao="3.3.0", notas="", nome_arquivo="x", url_asset="u",
                tamanho=12_900_000, sha256="", url_pagina="p", publicado_em="2026-10-23",
                tamanho_completo=56_700_000)
    base.update(k)
    return updater.Atualizacao(**base)


def test_titulo_marca_a_versao_de_teste():
    assert txt.titulo(_info()) == "Nova versão do DocManager: v3.3.0"
    assert txt.titulo(_info(prerelease=True)).endswith("(versão de teste)")


def test_resumo_do_pequeno_compara_com_o_completo():
    r = txt.resumo(_info(incremental=True), "3.2.0")
    assert "Você está na v3.2.0" in r and "publicada em 23/10/2026" in r
    assert "12,3 MB: só o que mudou (o instalador completo tem 54,1 MB)" in r


def test_resumo_do_completo():
    assert "12,3 MB: instalador completo" in txt.resumo(_info(), "3.1.1")


def test_textos_nao_dependem_de_biblioteca_grafica():
    fonte = open(txt.__file__, encoding="utf-8").read()
    assert "import tkinter" not in fonte and "customtkinter" not in fonte
