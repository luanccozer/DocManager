"""Sugestões, erros e dúvidas de quem usa o app, enviadas por e-mail.

A tela "Sugestões" monta um RASCUNHO no programa de e-mail padrão do Windows
(um link `mailto:`): a pessoa revê e envia, nada sai sozinho. O destinatário
vem das Configurações (`email_sugestoes`); vazio, o rascunho abre sem
destinatário para a pessoa completar - nenhum endereço fica escrito no código.

O `mailto:` tem limite de tamanho (o Windows corta links longos), então texto
grande vai pela área de transferência: o rascunho abre com um aviso para colar
(Ctrl+V) e a tela copia o texto inteiro antes.

Sem biblioteca gráfica: quem abre o link e mexe na área de transferência é a
tela (`ui/views/sugestoes_view.py`).
"""
from __future__ import annotations

import platform
from dataclasses import dataclass
from urllib.parse import quote

TIPOS = ("Sugestão", "Erro", "Dúvida")

# Abaixo do limite de link do Windows (~2000 caracteres), com folga.
LIMITE_LINK = 1800

AVISO_COLAR = ("(O texto completo foi copiado: cole aqui com Ctrl+V.)")


@dataclass(frozen=True)
class Rascunho:
    link: str
    texto: str            # assunto + corpo, para copiar
    cortado: bool         # o corpo não coube no link: vai pela área de transferência


def sistema() -> str:
    """'Windows-10-10.0.19045-SP0' - ajuda a reproduzir um erro."""
    try:
        return platform.platform()
    except Exception:  # noqa: BLE001
        return ""


def assunto(tipo: str, texto: str) -> str:
    """'[DocManager] Sugestão: primeira linha do texto' (até 60 caracteres)."""
    primeira = next((linha.strip() for linha in texto.splitlines() if linha.strip()), "")
    if len(primeira) > 60:
        primeira = primeira[:57].rstrip() + "..."
    return f"[DocManager] {tipo}: {primeira}" if primeira else f"[DocManager] {tipo}"


def corpo(tipo: str, texto: str, versao: str, sistema_op: str = "", diario: str = "") -> str:
    linhas = [texto.strip(), "", "---", f"Tipo: {tipo}", f"DocManager v{versao}"]
    if sistema_op:
        linhas.append(f"Sistema: {sistema_op}")
    if diario.strip():
        # O que o app registrou por último: num erro, poupa pedir o diario.log.
        linhas += ["", "--- Diário do app (últimas linhas) ---", diario.strip()]
    return "\n".join(linhas)


def _mailto(destino: str, assunto_: str, corpo_: str) -> str:
    # quote com safe="" : "&", "?" e "#" do texto não podem quebrar o link.
    # O "\n" vira %0A, que os programas de e-mail entendem como quebra de linha.
    return (f"mailto:{quote(destino.strip(), safe='@.+-_')}"
            f"?subject={quote(assunto_, safe='')}&body={quote(corpo_, safe='')}")


def montar(tipo: str, texto: str, versao: str, destino: str = "",
           sistema_op: str | None = None, diario: str = "") -> Rascunho:
    """O rascunho do e-mail. Levanta ValueError sem texto ou com tipo desconhecido."""
    if not texto.strip():
        raise ValueError("Escreva a sugestão antes de enviar.")
    if tipo not in TIPOS:
        raise ValueError(f"Tipo desconhecido: {tipo!r}")
    sistema_op = sistema() if sistema_op is None else sistema_op
    a = assunto(tipo, texto)
    c = corpo(tipo, texto, versao, sistema_op, diario)
    link = _mailto(destino, a, c)
    cortado = len(link) > LIMITE_LINK
    if cortado:
        link = _mailto(destino, a, AVISO_COLAR)
    return Rascunho(link=link, texto=f"{a}\n\n{c}", cortado=cortado)
