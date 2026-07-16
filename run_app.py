"""Ponto de entrada do EXECUTÁVEL (PyInstaller).

O app roda normalmente com `python -m docmanager`; o PyInstaller, porém, precisa
de um script (não de `-m`). Este arquivo só importa o pacote e chama o main —
mantendo os imports relativos do pacote funcionando.
"""
from docmanager.__main__ import main

if __name__ == "__main__":
    main()
