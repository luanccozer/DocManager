"""Gravar a planilha de volta e, quando o Windows recusa, dizer por quê (3.6.1).

Na 3.6.1-rc.1 o usuário via "arquivo aberto?" sem estar com o arquivo aberto. A
recusa do Windows ("Permission denied") cobre causas diferentes, e o app agora
pergunta ao Windows qual é a da vez.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys

import openpyxl
import pytest

from docmanager.services import gravacao


def _planilha(tmp_path):
    caminho = tmp_path / "Doc List Mapping.xlsx"
    openpyxl.Workbook().save(caminho)
    return caminho


def _recusa(*_):
    raise PermissionError(13, "Permission denied")


def _sem_motivo_conhecido(monkeypatch):
    monkeypatch.setattr(gravacao, "_somente_leitura", lambda c: False)
    monkeypatch.setattr(gravacao, "_programas_com_o_arquivo", lambda c: [])
    monkeypatch.setattr(gravacao, "_pasta_aceita_arquivo_novo", lambda p: True)


def test_salva_normalmente(tmp_path):
    caminho = _planilha(tmp_path)
    wb = openpyxl.load_workbook(caminho)
    wb.active["A1"] = "novo"
    assert gravacao.salvar_planilha(wb, caminho) is None
    assert openpyxl.load_workbook(caminho).active["A1"].value == "novo"


def test_recusa_passageira_e_tentada_de_novo_sem_perguntar(tmp_path, monkeypatch):
    """Box sincronizando ou antivírus lendo o arquivo: a recusa some em segundos."""
    caminho = _planilha(tmp_path)
    wb = openpyxl.load_workbook(caminho)
    wb.active["A1"] = "novo"
    salvar_de_verdade = wb.save
    recusas = [PermissionError(13, "Permission denied")] * 2

    def save(c):
        if recusas:
            raise recusas.pop()
        salvar_de_verdade(c)

    monkeypatch.setattr(wb, "save", save)
    perguntas = []
    assert gravacao.salvar_planilha(wb, caminho, retry_cb=perguntas.append, espera_s=0) is None
    assert perguntas == []
    assert openpyxl.load_workbook(caminho).active["A1"].value == "novo"


def test_recusa_que_fica_pergunta_com_o_programa_que_esta_com_o_arquivo(tmp_path, monkeypatch):
    caminho = _planilha(tmp_path)
    wb = openpyxl.load_workbook(caminho)
    monkeypatch.setattr(wb, "save", _recusa)
    _sem_motivo_conhecido(monkeypatch)
    monkeypatch.setattr(gravacao, "_programas_com_o_arquivo", lambda c: ["Microsoft Excel"])
    perguntas = []

    def desistir(msg):
        perguntas.append(msg)
        return False

    msg = gravacao.salvar_planilha(wb, caminho, retry_cb=desistir, espera_s=0)
    assert len(perguntas) == 1
    assert "Microsoft Excel" in perguntas[0]
    assert "Microsoft Excel" in msg
    assert "arquivo aberto?" not in msg


def test_tentar_de_novo_depois_de_fechar_o_programa_salva(tmp_path, monkeypatch):
    caminho = _planilha(tmp_path)
    wb = openpyxl.load_workbook(caminho)
    wb.active["A1"] = "novo"
    salvar_de_verdade = wb.save
    aberto = {"excel": True}

    def save(c):
        if aberto["excel"]:
            raise PermissionError(13, "Permission denied")
        salvar_de_verdade(c)

    def fechar_e_tentar(msg):
        aberto["excel"] = False
        return True

    monkeypatch.setattr(wb, "save", save)
    _sem_motivo_conhecido(monkeypatch)
    assert gravacao.salvar_planilha(wb, caminho, retry_cb=fechar_e_tentar, espera_s=0) is None
    assert openpyxl.load_workbook(caminho).active["A1"].value == "novo"


def test_motivo_somente_leitura(tmp_path, monkeypatch):
    caminho = _planilha(tmp_path)
    os.chmod(caminho, stat.S_IREAD)
    try:
        assert gravacao._somente_leitura(caminho)
        msg = gravacao.motivo_da_recusa(caminho, PermissionError(13, "Permission denied"))
    finally:
        os.chmod(caminho, stat.S_IREAD | stat.S_IWRITE)
    assert not gravacao._somente_leitura(caminho)
    assert "Somente leitura" in msg
    assert "Propriedades" in msg


def test_motivo_pasta_que_nao_aceita_gravacao(tmp_path, monkeypatch):
    caminho = _planilha(tmp_path)
    _sem_motivo_conhecido(monkeypatch)
    monkeypatch.setattr(gravacao, "_pasta_aceita_arquivo_novo", lambda p: False)
    msg = gravacao.motivo_da_recusa(caminho, PermissionError(13, "Permission denied"))
    assert "pasta" in msg
    assert "Acesso controlado a pastas" in msg


def test_motivo_sem_causa_aparente_mostra_o_erro_do_windows(tmp_path, monkeypatch):
    caminho = _planilha(tmp_path)
    _sem_motivo_conhecido(monkeypatch)
    msg = gravacao.motivo_da_recusa(caminho, PermissionError(13, "Permission denied"))
    assert "Permission denied" in msg
    assert "nenhum programa" in msg


def test_a_pasta_aceita_arquivo_novo_nao_deixa_lixo(tmp_path):
    assert gravacao._pasta_aceita_arquivo_novo(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_fora_do_windows_nao_lista_programas(tmp_path):
    if os.name == "nt":
        pytest.skip("fora do Windows")
    assert gravacao._programas_com_o_arquivo(_planilha(tmp_path)) == []


# Outro processo abre o arquivo sem compartilhar nada, como o Excel faz com a
# planilha aberta, e espera a entrada fechar.
_SEGURA_O_ARQUIVO = r"""
import ctypes, sys
from ctypes import wintypes
k = ctypes.WinDLL("kernel32", use_last_error=True)
k.CreateFileW.restype = wintypes.HANDLE
k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                          wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
h = k.CreateFileW(sys.argv[1], 0x80000000 | 0x40000000, 0, None, 3, 0x80, None)
print("pronto" if h and h != ctypes.c_void_p(-1).value else "falhou", flush=True)
sys.stdin.read()
"""


@pytest.mark.skipif(os.name != "nt", reason="trava de arquivo do Windows")
def test_no_windows_diz_qual_programa_esta_com_o_arquivo(tmp_path):
    caminho = _planilha(tmp_path)
    wb = openpyxl.load_workbook(caminho)
    outro = subprocess.Popen([sys.executable, "-c", _SEGURA_O_ARQUIVO, str(caminho)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert outro.stdout.readline().strip() == "pronto"
        programas = gravacao._programas_com_o_arquivo(caminho)
        assert programas, "o Restart Manager devia apontar o processo que segura o arquivo"
        msg = gravacao.salvar_planilha(wb, caminho, espera_s=0)
        assert msg is not None
        assert programas[0] in msg
    finally:
        outro.stdin.close()
        outro.wait(timeout=30)
