"""Gravar a planilha de volta no lugar e, quando o Windows recusa, dizer por quê.

"Permission denied" ao salvar cobre causas diferentes, e a mensagem antiga
("arquivo aberto?") acertava só uma: na 3.6.1-rc.1 o usuário não estava com o
arquivo aberto e não tinha como saber o que fazer. Antes de desistir, o app
tenta de novo por alguns segundos (o Box sincronizando ou o antivírus lendo o
arquivo soltam logo) e depois pergunta ao próprio Windows:

- o arquivo está marcado como Somente leitura?
- algum programa o tem aberto, e qual (pelo Restart Manager, o mesmo serviço que
  o instalador usa para fechar programas)?
- a pasta aceita um arquivo novo deste programa? Se nem isso, é proteção do
  Windows (Acesso controlado a pastas) ou permissão da pasta no Box.

Fora do Windows não há Restart Manager: a lista de programas sai vazia.
"""
from __future__ import annotations

import os
import stat
import tempfile
import time
from pathlib import Path


def salvar_planilha(wb, caminho, *, retry_cb=None, log_cb=None, tentativas: int = 3,
                    espera_s: float = 2.0) -> str | None:
    """Salva `wb` em `caminho`. Devolve None se salvou, ou a mensagem de por que não.

    `retry_cb(mensagem) -> bool` é a pergunta "Tentar de novo?" da tela: recebe o
    motivo e, se a pessoa resolver e confirmar, o app tenta outra vez.
    """
    log = log_cb or (lambda _m: None)
    while True:
        erro = _tentar_salvar(wb, caminho, tentativas, espera_s, log)
        if erro is None:
            return None
        motivo = motivo_da_recusa(caminho, erro)
        log(f"Não foi possível salvar: {motivo}")
        if retry_cb and retry_cb(f"{motivo}\n\nResolva isso e tente de novo."):
            continue
        return f"Não foi possível salvar a planilha. {motivo}"


def _tentar_salvar(wb, caminho, tentativas: int, espera_s: float, log) -> PermissionError | None:
    for i in range(tentativas):
        try:
            wb.save(caminho)
            return None
        except PermissionError as e:
            erro = e
            if i + 1 < tentativas:
                log(f"O Windows recusou salvar ({e.strerror or e}); tentando de novo em {espera_s:g} s.")
                time.sleep(espera_s)
    return erro


def motivo_da_recusa(caminho, erro: OSError) -> str:
    """O que impede gravar `caminho`, em palavras de quem vai resolver."""
    nome = Path(caminho).name
    if _somente_leitura(caminho):
        return (f"O arquivo '{nome}' está marcado como Somente leitura. No Explorador de Arquivos: "
                "botão direito no arquivo → Propriedades → desmarque Somente leitura → OK.")
    programas = _programas_com_o_arquivo(caminho)
    if programas:
        return (f"O arquivo '{nome}' está aberto em: {', '.join(programas)}. "
                "Feche-o nesse programa.")
    if not _pasta_aceita_arquivo_novo(Path(caminho).parent):
        return (f"O Windows não deixa o DocManager gravar na pasta de '{nome}', nem um arquivo "
                "novo. Costuma ser a proteção contra ransomware da Segurança do Windows (Acesso "
                "controlado a pastas) ou a permissão da pasta no Box. "
                f"Erro do Windows: {erro}")
    return (f"O Windows recusou gravar '{nome}' ({erro}), e nenhum programa aparece com o "
            "arquivo aberto. Confira se você tem permissão de edição nesse arquivo (no Box, o "
            "seu papel na pasta).")


def _somente_leitura(caminho) -> bool:
    """No Windows, o atributo Somente leitura aparece como falta de permissão de escrita."""
    try:
        return not os.stat(caminho).st_mode & stat.S_IWUSR
    except OSError:
        return False


def _pasta_aceita_arquivo_novo(pasta) -> bool:
    """Cria e apaga um arquivo vazio na pasta. O "~$" é o prefixo dos arquivos de
    trabalho do Office, que o Box não sincroniza."""
    try:
        fd, nome = tempfile.mkstemp(prefix="~$docmanager-", suffix=".tmp", dir=pasta)
    except OSError:
        return False
    os.close(fd)
    try:
        os.unlink(nome)
    except OSError:
        pass
    return True


def _programas_com_o_arquivo(caminho) -> list[str]:
    """Nomes dos programas que têm o arquivo aberto, fora o próprio DocManager.
    Vazio fora do Windows ou se o Restart Manager não responder."""
    if os.name != "nt":
        return []
    try:
        return _perguntar_ao_restart_manager(str(caminho))
    except Exception:  # noqa: BLE001 - diagnóstico: na falha, só não aponta ninguém
        return []


def _perguntar_ao_restart_manager(caminho: str) -> list[str]:
    import ctypes
    from ctypes import wintypes

    class _ProcessoUnico(ctypes.Structure):  # RM_UNIQUE_PROCESS
        _fields_ = [("dwProcessId", wintypes.DWORD), ("ProcessStartTime", wintypes.FILETIME)]

    class _InfoProcesso(ctypes.Structure):  # RM_PROCESS_INFO
        _fields_ = [("Process", _ProcessoUnico),
                    ("strAppName", wintypes.WCHAR * 256),
                    ("strServiceShortName", wintypes.WCHAR * 64),
                    ("ApplicationType", ctypes.c_int),
                    ("AppStatus", wintypes.ULONG),
                    ("TSSessionId", wintypes.DWORD),
                    ("bRestartable", wintypes.BOOL)]

    rm = ctypes.WinDLL("rstrtmgr")
    rm.RmStartSession.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.LPWSTR]
    rm.RmRegisterResources.argtypes = [wintypes.DWORD, wintypes.UINT, ctypes.POINTER(wintypes.LPCWSTR),
                                       wintypes.UINT, ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p]
    rm.RmGetList.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT),
                             ctypes.POINTER(_InfoProcesso), ctypes.POINTER(wintypes.DWORD)]
    rm.RmEndSession.argtypes = [wintypes.DWORD]
    for funcao in (rm.RmStartSession, rm.RmRegisterResources, rm.RmGetList, rm.RmEndSession):
        funcao.restype = wintypes.DWORD

    sessao = wintypes.DWORD()
    chave = ctypes.create_unicode_buffer(33)  # CCH_RM_SESSION_KEY + 1
    if rm.RmStartSession(ctypes.byref(sessao), 0, chave):
        return []
    try:
        arquivos = (wintypes.LPCWSTR * 1)(caminho)
        if rm.RmRegisterResources(sessao, 1, arquivos, 0, None, 0, None):
            return []
        precisa, quantos, motivo = wintypes.UINT(0), wintypes.UINT(0), wintypes.DWORD(0)
        r = rm.RmGetList(sessao, ctypes.byref(precisa), ctypes.byref(quantos), None,
                         ctypes.byref(motivo))
        if r not in (0, 234) or not precisa.value:  # 234 = ERROR_MORE_DATA
            return []
        infos = (_InfoProcesso * precisa.value)()
        quantos = wintypes.UINT(precisa.value)
        if rm.RmGetList(sessao, ctypes.byref(precisa), ctypes.byref(quantos), infos,
                        ctypes.byref(motivo)):
            return []
        nomes: list[str] = []
        for info in infos[:quantos.value]:
            if info.Process.dwProcessId == os.getpid():
                continue  # o que o próprio app segura não impede o app de salvar
            nome = info.strAppName.strip() or f"processo {info.Process.dwProcessId}"
            if nome not in nomes:
                nomes.append(nome)
        return nomes
    finally:
        rm.RmEndSession(sessao)
