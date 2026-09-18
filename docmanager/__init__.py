"""DocManager Itaipu — gestão de documentação de engenharia (CMI ↔ Itaipu via Aconex)."""
import os
import sys

from ._build_info import VERSAO as _VERSAO_BUILD

# --- Versão -----------------------------------------------------------------
# Vem do BUILD (`_build_info.py`, escrito pelo CI a partir da tag), não do .env:
# o .env é do usuário e sobrevive à atualização — se a versão viesse de lá, o app
# atualizado continuaria se declarando na versão antiga e rebaixaria para sempre.
# `DOCMANAGER_VERSAO` existe só para testar o aviso de atualização em
# desenvolvimento (ex.: fingir que se está numa versão velha).
__version__ = os.getenv("DOCMANAGER_VERSAO", "").strip() or _VERSAO_BUILD

# --- .env (legado, ainda aceito) --------------------------------------------
# As credenciais do Aconex agora ficam no cofre do app (services/credenciais.py),
# cadastradas pela própria interface. O .env continua sendo lido para quem já
# tinha um: na primeira execução ele é IMPORTADO para o cofre e depois não faz
# mais falta. Carregado já no import para que as variáveis estejam disponíveis
# em qualquer módulo.
#   • Empacotado (PyInstaller): procura ao lado do .exe e em Documentos.
#   • Desenvolvimento: procura na pasta atual e nas pais.
try:
    from dotenv import find_dotenv, load_dotenv

    if getattr(sys, "frozen", False):
        _candidatos = [
            os.path.join(os.path.dirname(sys.executable), ".env"),
            os.path.join(os.path.expanduser("~"), "Documents", "DocManager_Itaipu", ".env"),
        ]
        load_dotenv(next((c for c in _candidatos if os.path.isfile(c)), _candidatos[0]))
    else:
        load_dotenv(find_dotenv(usecwd=True))
except Exception:  # noqa: BLE001 — dotenv ausente não deve quebrar o import
    pass
