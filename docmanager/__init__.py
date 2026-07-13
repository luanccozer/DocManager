"""DocManager Itaipu — gestão de documentação de engenharia (CMI ↔ Itaipu via Aconex)."""
import os

# A versão é encapsulada no .env (VERSAO). Em desenvolvimento, o load_dotenv()
# procura o .env na pasta atual/pais; empacotado, o __main__ carrega o externo.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 — dotenv ausente não deve quebrar o import
    pass

__version__ = os.getenv("VERSAO", "3.0.0")
