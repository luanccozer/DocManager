"""Invariantes entre o app, o instalador e o build.

São acordos entre arquivos DIFERENTES, que nenhum teste de unidade pegaria e que
nada no dia a dia lembra de conferir: quebram calados e só aparecem quando a
atualização falha na máquina de alguém. Ler texto com regex, em vez de importar,
é de propósito - importar o `ui/main_app.py` carregaria o Qt inteiro só para ler
uma constante.
"""
import functools
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _ler(rel: str) -> str:
    return (RAIZ / rel).read_text(encoding="utf-8")


def _mutex_do_instalador() -> str:
    """O nome do AppMutex no .iss, resolvendo o `#define` que ele usa."""
    iss = _ler("installer/docmanager.iss")
    valor = re.search(r"^AppMutex=(.+)$", iss, re.M)
    assert valor, "AppMutex sumiu do .iss"
    valor = valor.group(1).strip()
    if (ref := re.fullmatch(r"\{#(\w+)\}", valor)):
        define = re.search(rf'^#define {ref.group(1)} "(.+?)"', iss, re.M)
        assert define, f"#define {ref.group(1)} sumiu do .iss"
        valor = define.group(1)
    return valor


def test_mutex_do_app_bate_com_o_do_instalador():
    """O Inno Setup acha o app aberto pelo AppMutex (e a atualização espera ele
    sumir). Nomes diferentes = o instalador troca arquivos com o app aberto."""
    do_app = re.search(r'^NOME_MUTEX = "(.+?)"', _ler("docmanager/ui/main_app.py"), re.M)
    assert do_app, "NOME_MUTEX sumiu"
    assert do_app.group(1) == _mutex_do_instalador()


def _code_do_iss() -> str:
    iss = _ler("installer/docmanager.iss")
    assert "[Code]" in iss, "o [Code] do instalador sumiu"
    return iss.split("[Code]", 1)[1]


def test_atualizacao_silenciosa_espera_o_app_sair():
    """Em modo silencioso o Inno ABORTA se o mutex do app existir na checagem do
    AppMutex - e o app leva segundos para sair depois de disparar o instalador.
    A espera tem de estar no InitializeSetup, que roda ANTES da checagem."""
    code = _code_do_iss()
    inicio = code.index("function InitializeSetup")
    corpo = code[inicio:code.index("\nend;", inicio)]
    assert "CheckForMutexes('{#AppMutexName}')" in corpo
    assert "Sleep(" in corpo and "WizardSilent" in corpo


def test_instalador_entende_os_parametros_que_o_app_passa():
    """/SINAL e /REABRIR não são do Inno: são do nosso [Code]. Se um lado mudar
    sem o outro, o app espera um sinal que nunca vem (ou o app não reabre)."""
    from docmanager.services import updater

    code = _code_do_iss()
    assert "{param:SINAL|}" in code
    assert "/REABRIR" in updater.ARGS_INSTALADOR and "'/REABRIR'" in code
    # O app 3.1.0 só passa /RESTARTAPPLICATIONS: o instalador tem de entendê-lo.
    assert "/RESTARTAPPLICATIONS" in updater.ARGS_INSTALADOR
    assert "'/RESTARTAPPLICATIONS'" in code


def test_instalador_reabre_o_app_depois_da_atualizacao():
    """O Restart Manager não reabre o app (ele sai sozinho antes): quem reabre
    é a entrada do [Run] - na conta de quem usava o app, não na do admin."""
    run = _ler("installer/docmanager.iss").split("[Run]", 1)[1].split("\n[", 1)[0]
    reabrir = [ln for ln in run.splitlines() if "ReabrirAposAtualizar" in ln]
    assert reabrir and "runasoriginaluser" in reabrir[0] and "nowait" in reabrir[0]
    assert "function ReabrirAposAtualizar" in _code_do_iss()


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
    lugar errado - e ninguém receberia atualização nunca mais."""
    from docmanager.services.updater import REPO_NOME, REPO_OWNER

    assert f"{REPO_OWNER}/{REPO_NOME}" == "luanccozer/DocManager"
    assert f"github.com/{REPO_OWNER}/{REPO_NOME}" in _ler("installer/docmanager.iss")


# ─────────────── versão de pré-lançamento vs. versão binária ────────────────
# O Inno abortou a publicação da 3.1.0-rc.1 com
#   Value of [Setup] section directive "VersionInfoVersion" is invalid
# porque esse campo é o número de versão BINÁRIO do Windows e só aceita
# dígitos - o sufixo "-rc.1" não entra. São duas versões diferentes, e as duas
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


@functools.lru_cache(maxsize=1)
def _bash_posix_disponivel() -> bool:
    """Há um `bash` POSIX utilizável nesta máquina?

    No Windows o `bash` do PATH costuma ser o do WSL: sem distro instalada, ele
    responde "Windows Subsystem for Linux has no installed distributions" - em
    UTF-16 - com código de saída 1. Sem esta checagem, o teste abaixo comparava
    essa mensagem com a versão e reprovava o build inteiro. Ironia registrada:
    um teste feito para pegar defeitos do Windows, ele mesmo só rodava em Linux.

    A CI de cada commit (ci.yml) roda em Ubuntu, então a expressão continua
    sendo exercitada de verdade a cada push; no job de Release, que é Windows,
    este teste é pulado.
    """
    try:
        r = subprocess.run(["bash", "-c", "echo pronto"], capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.strip() == "pronto"


@pytest.mark.skipif(not _bash_posix_disponivel(),
                    reason="sem bash POSIX (Windows/WSL sem distro)")
def test_corte_do_sufixo_do_workflow_produz_versao_numerica():
    """Roda a EXPRESSÃO que está no YAML, não uma cópia dela."""
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
            f"'{obtido}' tem parte não numérica - o Inno recusaria"


# ─────────────── atualização pequena (o método da CMI Suite) ─────────────────

def test_instalador_nao_tem_mais_o_modo_pequeno():
    """Desde a 3.4.0 o pequeno é um zip que o app aplica (services/pacote.py):
    o .iss é só o completo, que limpa o _internal antes de copiar."""
    iss = _ler("installer/docmanager.iss")
    assert "#ifdef Atualizacao" not in iss and "VersaoDe" not in iss
    assert "OutputBaseFilename=DocManager_Itaipu_Setup\n" in iss
    assert 'Type: filesandordirs; Name: "{app}\\_internal"' in iss


def test_appid_do_app_bate_com_o_do_instalador():
    """A pequena atualiza a versão de "Aplicativos instalados" na chave do Inno."""
    from docmanager.services.updater import APP_ID

    appid = re.search(r"^AppId=(.+)$", _ler("installer/docmanager.iss"), re.M).group(1).strip()
    assert appid.startswith("{{")
    assert APP_ID == appid[1:]      # "{{" é o escape do Inno para "{"


def test_nomes_dos_pacotes_sao_os_mesmos_no_gerador_e_no_app():
    from docmanager.services import pacote, updater
    from tools import gerar_atualizacao as g

    assert pacote.nome_pacote("3.3.0", "3.4.0") == "DocManager_Itaipu_Atualizacao_3.3.0_para_3.4.0.zip"
    assert g.pacote is pacote
    assert g.ARQUIVO_MANIFESTO == updater.ARQUIVO_ARQUIVOS
    assert g.PREFIXO_COMPLETO == updater.PREFIXO_COMPLETO
    wf = _ler(".github/workflows/release.yml")
    assert "DocManager_Itaipu_Setup_${{ steps.versao.outputs.versao }}.exe" in wf
    assert "--iscc" not in wf.split("Montar as atualizações pequenas", 1)[1].split("- name:", 1)[0]


def test_reabrir_tem_o_mesmo_nome_dos_dois_lados():
    """O app passa /REABRIR (sem valor) e o [Code] procura exatamente isso."""
    from docmanager.services import updater

    assert "/REABRIR" in updater.ARGS_INSTALADOR
    assert not any(a.startswith("/REABRIR=") for a in updater.ARGS_INSTALADOR)
    assert "TemParametro('/REABRIR')" in _code_do_iss()


def test_build_reprodutivel_no_workflow():
    """Sem estes dois, o .exe e o base_library.zip mudam a cada build e o pequeno
    leva tudo de novo."""
    wf = _ler(".github/workflows/release.yml")
    passo = wf.split("name: Gerar o executável (PyInstaller)", 1)[1].split("- name:", 1)[0]
    assert 'PYTHONHASHSEED: "0"' in passo
    epoch = re.search(r'SOURCE_DATE_EPOCH: "(\d+)"', passo)
    assert epoch, "SOURCE_DATE_EPOCH tem de ser um valor FIXO (não a data do commit)"
    assert "-c constraints-build.txt" in wf


def test_nosso_codigo_fica_fora_do_exe():
    """Com o código dentro do .exe, ele muda inteiro a cada versão (~30 MB)."""
    assert 'module_collection_mode={"docmanager": "pyc"}' in _ler("docmanager.spec")
