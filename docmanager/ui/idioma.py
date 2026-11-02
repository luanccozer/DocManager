"""A interface em espanhol, português ou inglês.

Como no SIG-FT (`sigft/app/idioma.py`) e na CMI Suite (`core/idioma.py`): o
texto de tela se escreve em português dentro de `t("...")`, e a tradução vem
de `ui/recursos/idiomas/es.json` e `en.json`, com o próprio texto em
português como chave. Texto sem tradução aparece em português (nunca uma
chave crua), e `tests/test_idioma.py` reprova `t("...")` sem tradução nos
dois arquivos.

O que NÃO se traduz, de propósito: o registro de execução (os logs), as
mensagens de erro que vêm dos serviços, da rede e do Aconex (são para
diagnóstico) e os nomes das colunas e abas das planilhas, que são da equipe.

Sem biblioteca gráfica: dá para testar e para os textos puros
(`ui/atualizacao_textos.py`) usarem.
"""
from __future__ import annotations

import json
import locale
from pathlib import Path

__all__ = ["t", "marcar", "definir", "atual", "NOMES", "IDIOMAS", "do_sistema", "efetivo"]

NOMES = {"es": "Español", "pt": "Português", "en": "English"}
IDIOMAS = tuple(NOMES)
PASTA = Path(__file__).resolve().parent / "recursos" / "idiomas"
_atual = "pt"
_catalogo: dict[str, str] = {}


def _carregar(codigo: str) -> dict[str, str]:
    if codigo == "pt":
        return {}
    try:
        return json.loads((PASTA / f"{codigo}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def definir(codigo: str) -> None:
    global _atual, _catalogo
    _atual = codigo if codigo in NOMES else "pt"
    _catalogo = _carregar(_atual)


def atual() -> str:
    return _atual


def t(texto: str, **valores) -> str:
    traduzido = _catalogo.get(texto, texto)
    try:
        return traduzido.format(**valores) if valores else traduzido
    except (KeyError, IndexError, ValueError):
        return texto.format(**valores)


def marcar(texto: str) -> str:
    """Marca um texto de tela que é constante de módulo: ele é lido ANTES de o
    idioma ser escolhido, então quem o mostra chama `t()` na hora. A marca é
    só para `tools/textos_da_interface.py` achá-lo (como no SIG-FT)."""
    return texto


def _do_codigo(codigo: str) -> str | None:
    codigo = (codigo or "").lower()
    for idioma in IDIOMAS:
        nome = {"es": "spanish", "pt": "portuguese", "en": "english"}[idioma]
        if codigo.startswith(idioma) or codigo.startswith(nome):
            return idioma
    return None


def do_sistema(idiomas_da_interface=()) -> str:
    """O idioma do Windows, se for um dos três; senão português (o da equipe).

    `idiomas_da_interface` é o `QLocale.system().uiLanguages()` (quem tem o Qt
    passa): o idioma em que o Windows MOSTRA as coisas. Sem ele, o
    `locale.getlocale()`, que é o formato regional (data, número) - um
    Windows em inglês com formato do Brasil diria português."""
    for codigo in idiomas_da_interface or ():
        if (achado := _do_codigo(codigo)):
            return achado
    try:
        codigo = locale.getlocale()[0] or ""
    except (ValueError, TypeError):
        codigo = ""
    return _do_codigo(codigo) or "pt"


def efetivo(escolha: str, idiomas_da_interface=()) -> str:
    """A escolha das Configurações; vazia ("ainda não escolhido"), a do Windows."""
    return escolha if escolha in IDIOMAS else do_sistema(idiomas_da_interface)
