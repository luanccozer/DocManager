"""Textos da atualização - sem biblioteca gráfica, para dar para testar.

A janela (`views/update_dialog.py`) só monta widgets; o que ela ESCREVE sai
daqui. A lógica de rede fica no `services/updater.py`.
"""
from __future__ import annotations

TEXTO_REABRE = ("Ao atualizar, o DocManager fecha, instala e abre de novo sozinho. Suas "
                "preferências e credenciais continuam.")

TEXTO_UAC = ("O DocManager está instalado para todos os usuários (Program Files). Esta "
             "atualização o passa para \"somente para você\", como os outros: o Windows "
             "vai pedir permissão de administrador uma vez, para remover a instalação "
             "antiga. Depois disso as atualizações não pedem mais nada.")

TEXTO_CONFERIDO = "Download conferido. Abrindo o instalador..."

TEXTO_APLICADO = "Atualizado e conferido. O DocManager vai abrir de novo, já na versão nova."

PERGUNTA_TAREFA = ("Há uma tarefa em andamento. Para atualizar, o DocManager precisa "
                   "fechar, e ela seria interrompida.\n\nAtualizar mesmo assim?")


def _mb(tamanho: int) -> str:
    """12.345.678 bytes → '11,8 MB' (vírgula, como se escreve aqui)."""
    return f"{tamanho / (1024 * 1024):.1f} MB".replace(".", ",")


def _data(iso: str) -> str:
    """'2026-10-23' → '23/10/2026' (o que não parecer data volta igual)."""
    partes = (iso or "").split("-")
    if len(partes) == 3 and all(p.isdigit() for p in partes):
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    return iso or ""


def titulo(info) -> str:
    texto = f"Nova versão do DocManager: v{info.versao}"
    return texto + " (versão de teste)" if info.prerelease else texto


def tamanho_download(info, pequena: bool = False) -> str:
    """'12,3 MB: só o que mudou (o instalador completo tem 54,1 MB)'."""
    if pequena and info.pequena is not None and info.pequena.tamanho:
        texto = f"{_mb(info.pequena.tamanho)}: só o que mudou"
        if info.tamanho:
            texto += f" (o instalador completo tem {_mb(info.tamanho)})"
        return texto
    if not info.tamanho:
        return ""
    return f"{_mb(info.tamanho)}: instalador completo"


def resumo(info, versao_atual: str, pequena: bool = False) -> str:
    partes = [f"Você está na v{versao_atual}"]
    if info.publicado_em:
        partes.append(f"publicada em {_data(info.publicado_em)}")
    if (tam := tamanho_download(info, pequena)):
        partes.append(f"download de {tam}")
    return "   ·   ".join(partes)


def caiu_no_completo(info, erro) -> str:
    return (f"A atualização pequena não deu certo ({erro}), e nada foi alterado. "
            f"Baixando o instalador completo ({_mb(info.tamanho)}).")


def em_dia(versao_atual: str) -> str:
    return f"Você já está na versão mais recente (v{versao_atual})."
