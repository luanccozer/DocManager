"""Tela Sugestões: o rascunho de e-mail (`services/sugestoes.py`)."""
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from docmanager.services import sugestoes


def _partes(link: str):
    u = urlsplit(link)
    q = parse_qs(u.query)
    return unquote(u.path), q["subject"][0], q["body"][0]


def test_rascunho_tem_destino_assunto_corpo_e_versao():
    r = sugestoes.montar("Erro", "O Mapa travou ao salvar.\nAconteceu duas vezes.", "3.6.1",
                         "pessoa@empresa.com", sistema_op="Windows-11")
    destino, assunto, corpo = _partes(r.link)
    assert r.link.startswith("mailto:")
    assert destino == "pessoa@empresa.com"
    assert assunto == "[DocManager] Erro: O Mapa travou ao salvar."
    assert corpo.startswith("O Mapa travou ao salvar.\nAconteceu duas vezes.")
    assert "Tipo: Erro" in corpo and "DocManager v3.6.1" in corpo and "Sistema: Windows-11" in corpo
    assert not r.cortado and r.texto.startswith(assunto)


def test_sem_destinatario_abre_rascunho_em_branco():
    destino, _, _ = _partes(sugestoes.montar("Dúvida", "Como uso o Delta?", "3.6.1", "", sistema_op="").link)
    assert destino == ""


def test_caracteres_especiais_nao_quebram_o_link():
    texto = "Usar & e ? e # e % no texto = ok"
    _, assunto, corpo = _partes(sugestoes.montar("Sugestão", texto, "1", "", sistema_op="").link)
    assert texto in assunto and corpo.startswith(texto)


def test_texto_longo_vai_pela_area_de_transferencia():
    texto = "linha longa " * 400
    r = sugestoes.montar("Sugestão", texto, "3.6.1", "a@b.com", sistema_op="")
    assert r.cortado and len(r.link) <= sugestoes.LIMITE_LINK
    _, _, corpo = _partes(r.link)
    assert corpo == sugestoes.AVISO_COLAR
    assert texto.strip() in r.texto          # o texto inteiro vai para a cópia


def test_assunto_curto_mesmo_com_primeira_linha_longa():
    assert len(sugestoes.assunto("Sugestão", "x" * 200)) <= len("[DocManager] Sugestão: ") + 60


@pytest.mark.parametrize("tipo,texto", [("Sugestão", "   \n "), ("Outro", "texto")])
def test_texto_vazio_ou_tipo_desconhecido_e_recusado(tipo, texto):
    with pytest.raises(ValueError):
        sugestoes.montar(tipo, texto, "3.6.1")


def test_erro_leva_as_ultimas_linhas_do_diario():
    r = sugestoes.montar("Erro", "Travou ao salvar.", "3.6.4", "", sistema_op="",
                         diario="2026-10-31 10:00:00 ABERTO 3.6.4\n2026-10-31 10:01:00 erro X")
    _, _, corpo = _partes(r.link)
    assert "--- Diário do app (últimas linhas) ---" in corpo and "erro X" in corpo


def test_ultimas_linhas_do_diario(tmp_path, monkeypatch):
    from docmanager.services import diario

    assert diario.ultimas_linhas() == ""                     # sem diário: vazio, sem erro
    for i in range(50):
        diario.registrar(f"evento {i}")
    linhas = diario.ultimas_linhas(5).splitlines()
    assert len(linhas) == 5 and linhas[-1].endswith("evento 49")
