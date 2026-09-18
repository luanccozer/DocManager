"""Leitura do CHANGELOG.md - a fonte das novidades da Home e do Release."""
from docmanager._build_info import VERSAO
from docmanager.services import novidades
from docmanager.services.novidades import analisar, bloco_de, ler

EXEMPLO = """# Histórico de versões

Texto de abertura que não é novidade nenhuma.

## 3.1.0 - 2026-09-18

- Atualização automática pelo GitHub.
- Credenciais cadastradas no app.

## v3.0.0 - 2026-08-02

* Doc List Mapping.
+ Home com módulos.
"""


def test_analisa_blocos_na_ordem():
    blocos = analisar(EXEMPLO)
    assert [b.versao for b in blocos] == ["3.1.0", "3.0.0"]
    assert blocos[0].data == "2026-09-18"
    assert len(blocos[0].itens) == 2


def test_aceita_os_tres_marcadores_de_lista():
    """`-`, `*` e `+` são todos Markdown válido; o parser não pode perder item
    só porque alguém digitou diferente."""
    assert len(analisar(EXEMPLO)[1].itens) == 2


def test_texto_fora_de_bloco_nao_vira_novidade():
    assert "Texto de abertura" not in " ".join(
        i for b in analisar(EXEMPLO) for i in b.itens)


def test_bloco_de_versao_ignora_o_v_da_tag():
    assert bloco_de(EXEMPLO, "3.0.0").versao == "3.0.0"
    assert bloco_de(EXEMPLO, "v3.0.0").versao == "3.0.0"
    assert bloco_de(EXEMPLO, "3.0.0-rc.1").versao == "3.0.0"
    assert bloco_de(EXEMPLO, "9.9.9") is None


def test_markdown_e_o_corpo_do_release():
    assert bloco_de(EXEMPLO, "3.1.0").markdown() == (
        "- Atualização automática pelo GitHub.\n- Credenciais cadastradas no app.")


def test_changelog_vazio_ou_estranho_nao_quebra():
    assert analisar("") == []
    assert analisar("só um texto solto, sem cabeçalho") == []
    assert bloco_de("", "3.0.0") is None


def test_changelog_do_projeto_cobre_a_versao_atual():
    """Guarda-costas do release: sem bloco da versão, o Release do GitHub sairia
    sem notas e a Home mostraria as novidades de outra versão."""
    bloco = bloco_de(open(novidades.caminho_changelog(), encoding="utf-8").read(), VERSAO)
    assert bloco is not None, f"CHANGELOG.md não tem bloco '## {VERSAO}'"
    assert bloco.itens


def test_ler_cai_para_o_mais_recente_em_build_de_desenvolvimento():
    assert ler("99.0.0").versao == analisar(
        open(novidades.caminho_changelog(), encoding="utf-8").read())[0].versao
