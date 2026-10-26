"""Guardas do sistema visual (sem abrir janela) - as mesmas do SIG-FT.

* nenhuma cor escrita fora de `ui/tokens.py` e `ui/estilo.py`: assim a troca de
  tema alcança tudo;
* todo par de texto que a folha pinta tem contraste de pelo menos 4,5:1;
* a pasta de ícones tem exatamente os usados (e a licença);
* nada da interface antiga (tkinter/CustomTkinter) voltou.
"""
import re
from pathlib import Path

import pytest

from docmanager.ui import tokens

PASTA_UI = Path(__file__).resolve().parent.parent / "docmanager" / "ui"
COR = re.compile(r"#[0-9A-Fa-f]{6}\b")
PODEM_TER_COR = {"tokens.py", "estilo.py"}


def _fontes_da_ui():
    return sorted(p for p in PASTA_UI.rglob("*.py") if "__pycache__" not in p.parts)


def test_nenhuma_cor_escrita_fora_dos_tokens_e_da_folha():
    achadas = [f"{p.relative_to(PASTA_UI)}: {m}" for p in _fontes_da_ui() if p.name not in PODEM_TER_COR
               for m in COR.findall(p.read_text(encoding="utf-8"))]
    # theme.py só reexporta os tokens (para o gerar_splash), sem escrever cor.
    assert not achadas, achadas


def test_interface_antiga_nao_voltou():
    for p in _fontes_da_ui():
        texto = p.read_text(encoding="utf-8")
        assert "import customtkinter" not in texto and "import tkinter" not in texto, p
        assert "from tkinter" not in texto, p


@pytest.mark.parametrize("tema", ["escuro", "claro"])
@pytest.mark.parametrize("texto,fundo", [
    ("texto", "fundo"), ("texto", "superficie"), ("texto", "superficie_alta"),
    ("texto_suave", "fundo"), ("texto_suave", "superficie"),
    ("primaria", "fundo"), ("primaria", "superficie"),
    ("texto_sobre_primaria", "primaria"), ("perigo", "fundo"), ("perigo", "superficie"),
    ("aviso", "superficie"), ("console_texto", "console_fundo"),
])
def test_contraste_dos_pares_da_folha(tema, texto, fundo):
    p = tokens.paleta(tema)
    assert tokens.contraste(p[texto], p[fundo]) >= 4.5, (tema, texto, fundo)


def test_os_dois_temas_tem_os_mesmos_papeis():
    assert set(tokens.ESCURO) == set(tokens.CLARO)


def test_pasta_de_icones_tem_exatamente_os_usados():
    pytest.importorskip("PySide6")
    from docmanager.ui import icones

    arquivos = {p.stem for p in icones.PASTA.glob("*.svg")}
    assert arquivos == set(icones.NOMES)
    assert (icones.PASTA / "LICENSE").exists()


def test_folha_de_estilo_dos_dois_temas_monta():
    from docmanager.ui import estilo

    for tema in ("escuro", "claro"):
        folha = estilo.folha_de_estilo(tema)
        assert tokens.paleta(tema)["fundo"] in folha
        assert folha.count("{") == folha.count("}")
