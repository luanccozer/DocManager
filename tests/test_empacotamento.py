"""Invariantes entre o app, o instalador e o build.

São acordos entre arquivos DIFERENTES, que nenhum teste de unidade pegaria e que
nada no dia a dia lembra de conferir: quebram calados e só aparecem quando a
atualização falha na máquina de alguém. Ler texto com regex, em vez de importar,
é de propósito — o `ui/main_app.py` precisa de tkinter, que não existe no CI.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _ler(rel: str) -> str:
    return (RAIZ / rel).read_text(encoding="utf-8")


def test_mutex_do_app_bate_com_o_do_instalador():
    """O Inno Setup acha o app aberto pelo AppMutex para fechá-lo antes de trocar
    os arquivos. Nomes diferentes = atualização falha com 'arquivo em uso'."""
    do_app = re.search(r'^NOME_MUTEX = "(.+?)"', _ler("docmanager/ui/main_app.py"), re.M)
    do_iss = re.search(r"^AppMutex=(.+)$", _ler("installer/docmanager.iss"), re.M)
    assert do_app and do_iss, "NOME_MUTEX ou AppMutex sumiram"
    assert do_app.group(1) == do_iss.group(1).strip()


def test_changelog_vai_para_dentro_do_executavel():
    """Sem estar nos `datas` do .spec, a seção 'O que há de novo' some no .exe."""
    assert '("CHANGELOG.md", ".")' in _ler("docmanager.spec")


def test_token_de_atualizacao_esta_no_gitignore():
    """O arquivo gerado com o token NUNCA pode ser commitado."""
    assert "docmanager/_update_auth.py" in _ler(".gitignore")


def test_o_token_nao_esta_versionado():
    assert not (RAIZ / "docmanager" / "_update_auth.py").exists() or \
        "docmanager/_update_auth.py" in _ler(".gitignore")


def test_preparar_build_consegue_reescrever_o_build_info():
    """O script do CI substitui essas linhas por regex; se alguém reformatar o
    `_build_info.py`, o build passaria batido e publicaria a versão errada."""
    texto = _ler("docmanager/_build_info.py")
    for chave in ("VERSAO", "COMMIT", "DATA_BUILD", "ORIGEM"):
        assert re.search(rf'^{chave} = ".*"$', texto, re.M), \
            f"{chave} não está no formato que tools/preparar_build.py espera"


def test_versao_do_build_e_semver():
    from docmanager._build_info import VERSAO

    assert re.match(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$", VERSAO), VERSAO


def test_o_repositorio_do_updater_bate_com_o_remoto_documentado():
    """Um fork ou uma renomeação do repo deixaria o updater apontando para o
    lugar errado — e ninguém receberia atualização nunca mais."""
    from docmanager.services.updater import REPO_NOME, REPO_OWNER

    assert f"{REPO_OWNER}/{REPO_NOME}" == "luanccozer/DocManager"
    assert f"github.com/{REPO_OWNER}/{REPO_NOME}" in _ler("installer/docmanager.iss")


# ─────────────── versão de pré-lançamento vs. versão binária ────────────────
# O Inno abortou a publicação da 3.1.0-rc.1 com
#   Value of [Setup] section directive "VersionInfoVersion" is invalid
# porque esse campo é o número de versão BINÁRIO do Windows e só aceita
# dígitos — o sufixo "-rc.1" não entra. São duas versões diferentes, e as duas
# pontas (o .iss e o workflow) têm que continuar concordando sobre isso.

def test_versioninfo_nao_usa_a_versao_com_sufixo():
    iss = _ler("installer/docmanager.iss")
    assert "VersionInfoVersion={#MyVersionInfo}" in iss, \
        "VersionInfoVersion tem que usar MyVersionInfo (só dígitos), não MyAppVersion"
    assert "#ifndef MyVersionInfo" in iss, "falta o padrão de MyVersionInfo para build local"


def test_workflow_passa_a_versao_numerica_para_o_inno():
    wf = _ler(".github/workflows/release.yml")
    assert "/DMyVersionInfo=" in wf, "o workflow não está passando a versão numérica ao ISCC"
    assert "numerica=" in wf, "o workflow não calcula a versão sem o sufixo"


def test_corte_do_sufixo_do_workflow_produz_versao_numerica():
    """Roda a EXPRESSÃO que está no YAML, não uma cópia dela."""
    import re
    import subprocess

    wf = _ler(".github/workflows/release.yml")
    m = re.search(r'^\s*(numerica="\$\{versao%%.*\}")\s*$', wf, re.M)
    assert m, "não achei a linha que calcula a versão numérica no workflow"
    expressao = m.group(1)

    for entrada, esperado in [("3.1.0", "3.1.0"), ("3.1.0-rc.1", "3.1.0"),
                              ("3.2.0-beta.2", "3.2.0"), ("10.0.1", "10.0.1")]:
        r = subprocess.run(["bash", "-c", f'versao="{entrada}"; {expressao}; echo "$numerica"'],
                           capture_output=True, text=True)
        obtido = r.stdout.strip()
        assert obtido == esperado, f"{entrada} virou {obtido}, esperado {esperado}"
        assert all(p.isdigit() for p in obtido.split(".")), \
            f"'{obtido}' tem parte não numérica — o Inno recusaria"
