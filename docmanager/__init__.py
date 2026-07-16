"""DocManager Itaipu — gestão de documentação de engenharia (CMI ↔ Itaipu via Aconex)."""
import os
import sys

# A versão e os segredos vêm do .env (VERSAO, SECRET_*). Carregado já no import
# para que __version__ e as credenciais estejam prontos em qualquer módulo.
#   • Empacotado (PyInstaller): o .env fica AO LADO do .exe (externo, nunca
#     embutido) — procura em dirname(sys.executable).
#   • Desenvolvimento: procura o .env na pasta atual e nas pais.
try:
    from dotenv import find_dotenv, load_dotenv

    if getattr(sys, "frozen", False):
        # Procura o .env ao lado do .exe (precisa de admin em Program Files) OU
        # em Documents\DocManager_Itaipu (editável sem admin). O 1º encontrado vence.
        _candidatos = [
            os.path.join(os.path.dirname(sys.executable), ".env"),
            os.path.join(os.path.expanduser("~"), "Documents", "DocManager_Itaipu", ".env"),
        ]
        load_dotenv(next((c for c in _candidatos if os.path.isfile(c)), _candidatos[0]))
    else:
        load_dotenv(find_dotenv(usecwd=True))
except Exception:  # noqa: BLE001 — dotenv ausente não deve quebrar o import
    pass

__version__ = os.getenv("VERSAO", "3.0.0")
