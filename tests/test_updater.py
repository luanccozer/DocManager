"""Atualização automática: comparação de versões, leitura do release e política.

Nada aqui toca a rede. O que é testado é justamente a parte que decide se o
usuário vai ou não ser avisado - e que, errada, produz os dois piores defeitos
possíveis: nunca avisar, ou reoferecer a mesma versão para sempre.
"""
import dataclasses
import hashlib
import json

import pytest

from docmanager._ofuscacao import desofuscar, ofuscar
from docmanager.services import pacote, updater
from docmanager.services.config import ConfigManager


# --------------------------------------------------------------------------
# Comparação de versões
# --------------------------------------------------------------------------
@pytest.mark.parametrize("remota,atual,esperado", [
    ("3.1.0", "3.0.0", True),
    ("3.0.1", "3.0.0", True),
    ("3.10.0", "3.9.0", True),      # 10 > 9: comparação numérica, não de texto
    ("v3.1.0", "3.0.0", True),      # o 'v' da tag não atrapalha
    ("3.0.0", "3.0.0", False),      # em dia
    ("3.0.0", "3.1.0", False),      # nunca "atualizar" para trás
    ("3.1.0-beta.1", "3.1.0", False),   # pré-versão vem ANTES da final
    ("3.1.0", "3.1.0-beta.1", True),    # da pré-versão para a final, sim
    ("3.1", "3.0.9", True),         # tag encurtada ainda compara certo
])
def test_comparacao_de_versoes(remota, atual, esperado):
    assert updater.e_mais_nova(remota, atual) is esperado


def test_versao_estranha_nao_derruba_o_app():
    """Uma tag digitada errada no GitHub não pode virar exceção na abertura."""
    assert updater.e_mais_nova("versao-de-teste", "3.0.0") is False
    assert updater.e_mais_nova("", "3.0.0") is False
    assert updater.e_mais_nova(None, "3.0.0") is False


# --------------------------------------------------------------------------
# Leitura do release
# --------------------------------------------------------------------------
def _release(assets, tag="v3.2.0", body="- novidade"):
    return {"tag_name": tag, "body": body, "assets": assets,
            "html_url": "https://github.com/x/y/releases/tag/" + tag,
            "published_at": "2026-09-18T10:00:00Z"}


def test_interpretar_release_escolhe_o_instalador():
    r = _release([
        {"name": "latest.json", "url": "https://api/assets/1", "size": 300},
        {"name": "DocManager_Itaipu_Setup_3.2.0.exe", "url": "https://api/assets/2",
         "size": 40_000_000, "digest": "sha256:ABC123"},
    ])
    info = updater.interpretar_release(r)
    assert info.versao == "3.2.0"
    assert info.nome_arquivo.endswith(".exe")
    # A URL guardada é a da API, não a browser_download_url: em repositório
    # privado só a de API entrega o binário (a outra devolve uma página HTML).
    assert info.url_asset == "https://api/assets/2"
    assert info.sha256 == "abc123"          # normalizado para minúsculas
    assert info.tamanho_mb == 38.1


def test_manifesto_vence_o_digest_da_api():
    r = _release([{"name": "s.exe", "url": "u", "size": 1, "digest": "sha256:doapi"}])
    info = updater.interpretar_release(r, {"sha256": "DOMANIFESTO", "notas": "- do manifesto"})
    assert info.sha256 == "domanifesto"
    assert info.notas == "- do manifesto"


def test_sem_manifesto_usa_o_body_do_release():
    r = _release([{"name": "s.exe", "url": "u", "size": 1}], body="- veio do body")
    info = updater.interpretar_release(r)
    assert info.notas == "- veio do body"
    assert info.sha256 == ""        # sem hash: baixar() avisa que não conferiu


def test_release_sem_instalador_devolve_none():
    """Publicar só o latest.json (build que falhou no meio) não pode virar um
    aviso de atualização que não instala nada."""
    assert updater.interpretar_release(_release([{"name": "latest.json", "url": "u"}])) is None


# --------------------------------------------------------------------------
# Token embutido
# --------------------------------------------------------------------------
def test_ofuscacao_ida_e_volta():
    token = "github_pat_11ABCDEF_umTokenQualquerComSímbolos-_=."
    assert desofuscar(ofuscar(token)) == token
    assert token not in ofuscar(token)   # não aparece num `strings` do .exe


def test_token_da_variavel_de_ambiente_vence(monkeypatch):
    monkeypatch.setenv("DOCMANAGER_UPDATE_TOKEN", "tok_do_ambiente")
    assert updater.token() == "tok_do_ambiente"


def test_token_do_arquivo_em_documentos(monkeypatch, tmp_path):
    """Trocar o token sem refazer o build (rotação de emergência)."""
    monkeypatch.delenv("DOCMANAGER_UPDATE_TOKEN", raising=False)
    arquivo = updater.caminho_token_externo()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("  tok_do_arquivo\n", encoding="utf-8")
    assert updater.token() == "tok_do_arquivo"


def test_sem_token_a_checagem_explica_em_vez_de_quebrar(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "")
    with pytest.raises(updater.SemToken):
        updater.checar("3.0.0")


# --------------------------------------------------------------------------
# Política: quando avisar
# --------------------------------------------------------------------------
def test_nao_verifica_sem_token(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "")
    assert updater.deve_verificar(ConfigManager()) is False


def test_verifica_na_primeira_vez_e_respeita_o_intervalo(monkeypatch):
    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: "")
    cfg = ConfigManager()
    assert updater.deve_verificar(cfg) is True      # nunca verificou
    updater.registrar_verificacao(cfg)
    assert updater.deve_verificar(cfg) is False     # acabou de verificar
    assert updater.deve_verificar(cfg, intervalo_horas=0) is True   # a abertura


def test_desligar_o_aviso_automatico_para_a_verificacao(monkeypatch):
    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: "")
    cfg = ConfigManager()
    cfg.set_setting("verificar_atualizacoes", False)
    assert updater.deve_verificar(cfg) is False


def test_data_invalida_na_config_nao_trava_a_verificacao(monkeypatch):
    monkeypatch.setattr(updater, "motivo_para_nao_verificar", lambda: "")
    cfg = ConfigManager()
    cfg.set_setting("ultima_verificacao", "ontem de manhã")
    assert updater.deve_verificar(cfg) is True


def test_pular_versao_silencia_so_aquela_versao():
    cfg = ConfigManager()
    updater.ignorar_versao(cfg, "3.2.0")
    assert updater.esta_ignorada(cfg, "3.2.0") is True
    assert updater.esta_ignorada(cfg, "3.3.0") is False   # a próxima volta a avisar


def test_manifesto_com_bom_ainda_e_lido():
    """O PowerShell pode gravar o latest.json com BOM; `utf-8-sig` cobre os dois."""
    bruto = b"\xef\xbb\xbf" + json.dumps({"sha256": "abc"}).encode("utf-8")
    assert json.loads(bruto.decode("utf-8-sig"))["sha256"] == "abc"


def test_release_publicado_de_verdade_e_entendido():
    """O JSON (resumido) que a API devolveu para o Release v3.1.0 publicado pelo
    workflow: é o formato que os apps instalados vão ler na próxima versão."""
    release = {
        "tag_name": "v3.1.0", "prerelease": False, "draft": False,
        "html_url": "https://github.com/luanccozer/DocManager/releases/tag/v3.1.0",
        "published_at": "2026-09-18T17:35:25Z", "body": "## O que mudou na v3.1.0 ...",
        "assets": [
            {"name": "DocManager_Itaipu_Setup_3.1.0.exe", "size": 54226345,
             "url": "https://api.github.com/repos/luanccozer/DocManager/releases/assets/573114368",
             "digest": "sha256:b675b74dc1dace0d54762173eaf0c1d250d31d3824d7a63c89e983c4e9eb3491"},
            {"name": "latest.json", "size": 1670,
             "url": "https://api.github.com/repos/luanccozer/DocManager/releases/assets/573114371"},
        ],
    }
    info = updater.interpretar_release(release)
    assert info.versao == "3.1.0"
    assert info.nome_arquivo == "DocManager_Itaipu_Setup_3.1.0.exe"
    assert info.url_asset.endswith("/releases/assets/573114368")   # a URL de API
    assert info.sha256 == "b675b74dc1dace0d54762173eaf0c1d250d31d3824d7a63c89e983c4e9eb3491"
    assert info.tamanho_mb == 51.7
    assert updater.e_mais_nova("3.1.1", "3.1.0")


# --------------------------------------------------------------------------
# Instalação: o app só fecha quando o instalador está PRONTO (2026-09-30)
# --------------------------------------------------------------------------
# Até a v3.1.0 o app disparava o instalador e fechava 400 ms depois. Em modo
# silencioso o Inno aborta se o app ainda estiver aberto na checagem do
# AppMutex - a atualização falhava em meio segundo (reproduzido no Wine).
# Agora o instalador cria o arquivo de /SINAL quando está pronto (e esperando
# o app sair), e `instalar` só volta nesse momento.
def _instalador_falso(tmp_path, corpo: str):
    """Script executável no lugar do Setup.exe; recebe os mesmos argumentos."""
    import stat
    import sys

    script = tmp_path / "Setup_falso.py"
    script.write_text(
        f"#!{sys.executable}\n"
        "import sys, time, pathlib\n"
        "args = sys.argv[1:]\n"
        "sinal = next((a.split('=', 1)[1] for a in args if a.startswith('/SINAL=')), '')\n"
        f"pathlib.Path({str(tmp_path / 'args.txt')!r}).write_text('\\n'.join(args))\n"
        + corpo, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


@pytest.fixture
def pasta_update(tmp_path, monkeypatch):
    pasta = tmp_path / "update"
    pasta.mkdir()
    monkeypatch.setattr(updater, "pasta_download", lambda: pasta)
    # O instalador falso continua rodando depois que `instalar` volta (como o de
    # verdade): encerra no fim do teste, senão sobra processo órfão da suíte.
    abertos = []
    popen = updater.subprocess.Popen

    def popen_registrando(*args, **kwargs):
        processo = popen(*args, **kwargs)
        abertos.append(processo)
        return processo

    monkeypatch.setattr(updater.subprocess, "Popen", popen_registrando)
    yield pasta
    for processo in abertos:
        processo.kill()
        processo.wait()


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_instalar_espera_o_instalador_ficar_pronto(tmp_path, pasta_update):
    inst = _instalador_falso(tmp_path, (
        "time.sleep(0.5)\n"
        "pathlib.Path(sinal).write_text('pronto')\n"
        "time.sleep(2)\n"))
    inicio = __import__("time").monotonic()
    updater.instalar(inst)
    assert __import__("time").monotonic() - inicio >= 0.5    # esperou o sinal
    args = (tmp_path / "args.txt").read_text().splitlines()
    for esperado in ("/SILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS",
                     "/RESTARTAPPLICATIONS", "/REABRIR"):
        assert esperado in args
    assert f"/SINAL={pasta_update / 'instalador_pronto.txt'}" in args
    assert f"/LOG={pasta_update / 'instalacao.log'}" in args


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_instalador_que_termina_sem_ficar_pronto_nao_fecha_o_app(tmp_path, pasta_update):
    """UAC recusado, antivírus...: o instalador sai sem criar o sinal. O app
    tem de continuar aberto e avisar - fechar seria perder a pessoa de vista."""
    inst = _instalador_falso(tmp_path, "sys.exit(2)\n")
    with pytest.raises(updater.InstaladorNaoIniciou, match="código 2"):
        updater.instalar(inst)


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_sinal_velho_nao_e_confundido_com_pronto(tmp_path, pasta_update):
    """Um sinal que sobrou de uma tentativa anterior não pode fechar o app."""
    (pasta_update / "instalador_pronto.txt").write_text("pronto")
    inst = _instalador_falso(tmp_path, "sys.exit(1)\n")
    with pytest.raises(updater.InstaladorNaoIniciou):
        updater.instalar(inst)


@pytest.mark.skipif(__import__("os").name == "nt", reason="instalador falso é script com shebang")
def test_instalador_que_nao_responde_desiste_sem_fechar_o_app(tmp_path, pasta_update):
    inst = _instalador_falso(tmp_path, "time.sleep(5)\n")
    with pytest.raises(updater.InstaladorNaoIniciou, match="não respondeu"):
        updater.instalar(inst, espera_s=0.5)


def test_instalador_que_nao_abre_vira_aviso(tmp_path, pasta_update):
    with pytest.raises(updater.InstaladorNaoIniciou, match="não deixou abrir"):
        updater.instalar(tmp_path / "nao_existe.exe")


# --------------------------------------------------------------------------
# Atualização pequena: o método da CMI Suite (a partir da 3.4.0)
# --------------------------------------------------------------------------
COMPLETO = "DocManager_Itaipu_Setup_3.4.0.exe"
ZIP = "DocManager_Itaipu_Atualizacao_3.3.0_para_3.4.0.zip"


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def _release_com_pequena(*, com_zip=True, com_arquivos=True, digest=True):
    def asset(nome, url, tamanho, sha):
        a = {"name": nome, "url": url, "size": tamanho}
        if digest:
            a["digest"] = f"sha256:{sha}"
        return a
    assets = [asset(COMPLETO, "api/completo", 56_000_000, "c" * 64),
              {"name": "latest.json", "url": "api/latest", "size": 900}]
    if com_zip:
        assets.append(asset(ZIP, "api/zip", 4_000_000, "a" * 64))
    if com_arquivos:
        assets.append(asset("arquivos.json", "api/arquivos", 90_000, "b" * 64))
    return _release(assets, tag="v3.4.0")


def test_oferece_a_pequena_quando_ha_zip_da_versao_instalada():
    info = updater.interpretar_release(_release_com_pequena(), None, "3.3.0")
    assert info.nome_arquivo == COMPLETO and info.sha256 == "c" * 64
    assert info.tem_pequena
    assert info.pequena == updater.Pacote(ZIP, "api/zip", 4_000_000, "a" * 64)
    assert info.arquivos == updater.Pacote("arquivos.json", "api/arquivos", 90_000, "b" * 64)


@pytest.mark.parametrize("versao_atual", ["3.2.0", "3.3.0-rc.1", ""])
def test_sem_zip_da_versao_instalada_vai_o_completo(versao_atual):
    info = updater.interpretar_release(_release_com_pequena(), None, versao_atual)
    assert not info.tem_pequena and info.nome_arquivo == COMPLETO


@pytest.mark.parametrize("kw", [{"com_zip": False}, {"com_arquivos": False}, {"digest": False}])
def test_pequena_incompleta_ou_sem_sha_nao_e_oferecida(kw):
    """Sem o zip, sem o arquivos.json ou sem SHA256 de algum deles: o completo."""
    assert not updater.interpretar_release(_release_com_pequena(**kw), None, "3.3.0").tem_pequena


def test_sha_do_latest_json_vence_o_digest():
    manifesto = {"pequenas": [{"de": "3.3.0", "arquivo": ZIP, "sha256": "D" * 64}],
                 "arquivos_json": {"sha256": "E" * 64}}
    info = updater.interpretar_release(_release_com_pequena(digest=False), manifesto, "3.3.0")
    assert info.pequena.sha256 == "d" * 64 and info.arquivos.sha256 == "e" * 64


def test_o_zip_de_um_app_3_3_0_nunca_e_o_completo():
    """O app 3.3.0 lê `atualizacoes`, que não é mais publicado; e o completo é
    escolhido pelo nome, qualquer que seja a ordem dos arquivos."""
    r = _release_com_pequena()
    r["assets"].reverse()
    assert updater.interpretar_release(r, {"pequenas": []}).nome_arquivo == COMPLETO
    nomes = sorted(a["name"] for a in r["assets"])
    assert next(n for n in nomes if n.endswith(".exe")) == COMPLETO


def test_completo_de_release_antigo_e_escolhido_pelo_nome():
    antigo = _release([{"name": "DocManager_Itaipu_Update_3.2.0_para_3.3.0.exe", "url": "u1", "size": 1},
                       {"name": "Instalador_antigo.exe", "url": "u2", "size": 1}])
    assert updater.interpretar_release(antigo).nome_arquivo == "Instalador_antigo.exe"


def test_pode_pequena_so_com_pasta_gravavel(tmp_path, monkeypatch):
    info = updater.interpretar_release(_release_com_pequena(), None, "3.3.0")
    assert updater.pode_pequena(info, tmp_path)
    monkeypatch.setattr(updater, "pasta_instalacao", lambda: None)
    assert not updater.pode_pequena(info)                          # código-fonte
    monkeypatch.setattr(updater, "_gravavel", lambda _p: False)
    assert not updater.pode_pequena(info, tmp_path)                # Program Files
    sem = updater.interpretar_release(_release_com_pequena(), None, "3.2.0")
    monkeypatch.setattr(updater, "_gravavel", lambda _p: True)
    assert not updater.pode_pequena(sem, tmp_path)


def test_canal_de_testes_fica_com_a_versao_mais_alta_menos_rascunho():
    releases = [{"tag_name": "v3.2.0", "prerelease": False},
                {"tag_name": "v3.3.0-rc.2", "prerelease": True},
                {"tag_name": "v3.3.0-rc.10", "prerelease": True},
                {"tag_name": "v9.9.9", "draft": True}]
    assert updater.escolher_release(releases)["tag_name"] == "v3.3.0-rc.10"
    assert updater.escolher_release([]) is None


class _Resp:
    """Resposta falsa do `requests` com `iter_content`."""

    def __init__(self, dados: bytes, anunciado: int | None = None):
        self._dados = dados
        self.headers = {"Content-Length": str(anunciado if anunciado is not None else len(dados))}
        self.status_code = 200

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._dados), chunk_size):
            yield self._dados[i:i + chunk_size]

    def close(self):
        pass


class _Sessao:
    def close(self):
        pass


@pytest.fixture
def servidor(tmp_path, monkeypatch):
    """`rede.abrir` falso: devolve o que estiver em `arquivos[url]`."""
    pasta = tmp_path / "dl"
    pasta.mkdir()
    monkeypatch.setattr(updater, "pasta_download", lambda: pasta)
    arquivos: dict = {}
    pedidos: list = []

    def abrir(url, **_k):
        pedidos.append(url)
        resp = arquivos[url]
        if isinstance(resp, Exception):
            raise resp
        return _Sessao(), resp

    monkeypatch.setattr(updater.rede, "abrir", abrir)
    return arquivos, pedidos, pasta


COMPLETO_BYTES = b"C" * 1_500_000
V1 = {"DocManager.exe": b"exe v1", "_internal/lib.dll": b"lib" * 1000, "_internal/a.pyc": b"v1"}
V2 = {"DocManager.exe": b"exe v2", "_internal/lib.dll": b"lib" * 1000, "_internal/a.pyc": b"v2"}


def _instalacao(pasta, arquivos):
    for rel, dados in arquivos.items():
        (pasta / rel).parent.mkdir(parents=True, exist_ok=True)
        (pasta / rel).write_bytes(dados)
    return pasta


def _retrato(arquivos, versao):
    return {"versao": versao, "arquivos": {rel: {"sha256": _sha(d), "tamanho": len(d)}
                                           for rel, d in arquivos.items()}}


def _conteudo(pasta):
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in pasta.rglob("*") if p.is_file()}


@pytest.fixture
def pequena(tmp_path, servidor):
    """Uma instalação 3.3.0, o zip para a 3.4.0 e o arquivos.json no 'GitHub'."""
    arquivos, pedidos, _ = servidor
    instalada = _instalacao(tmp_path / "instalada", V1)
    v2 = _instalacao(tmp_path / "v2", V2)
    m1, m2 = _retrato(V1, "3.3.0"), _retrato(V2, "3.4.0")
    zip_ = pacote.montar({rel: v2 / rel for rel in V2}, m1, m2, tmp_path)
    zip_bytes, json_bytes = zip_.read_bytes(), json.dumps(m2).encode()
    arquivos["api/zip"] = _Resp(zip_bytes)
    arquivos["api/arquivos"] = _Resp(json_bytes)
    info = updater.Atualizacao(
        "3.4.0", "", COMPLETO, "api/completo", len(COMPLETO_BYTES), _sha(COMPLETO_BYTES), "pag",
        pequena=updater.Pacote(ZIP, "api/zip", len(zip_bytes), _sha(zip_bytes)),
        arquivos=updater.Pacote("arquivos.json", "api/arquivos", len(json_bytes), _sha(json_bytes)))
    return info, instalada, arquivos, pedidos


def test_pequena_de_ponta_a_ponta(pequena):
    info, instalada, _arquivos, pedidos = pequena
    exe = updater.atualizar_pequena(info, pasta=instalada)
    assert exe == instalada / "DocManager.exe"
    assert pedidos == ["api/arquivos", "api/zip"]
    pacote.limpar_restos(instalada)
    assert _conteudo(instalada) == V2


def test_zip_adulterado_nao_toca_na_instalacao(pequena):
    info, instalada, arquivos, _ = pequena
    arquivos["api/zip"] = _Resp(b"x" * info.pequena.tamanho)
    with pytest.raises(updater.HashDivergente, match="não confere"):
        updater.atualizar_pequena(info, pasta=instalada)
    assert _conteudo(instalada) == V1


def test_arquivos_json_de_outra_versao_e_recusado(pequena):
    info, instalada, arquivos, _ = pequena
    outro = json.dumps(_retrato(V2, "3.5.0")).encode()
    arquivos["api/arquivos"] = _Resp(outro)
    info = dataclasses.replace(info, arquivos=updater.Pacote("arquivos.json", "api/arquivos",
                                                         len(outro), _sha(outro)))
    with pytest.raises(pacote.ErroPacote, match="3.5.0"):
        updater.atualizar_pequena(info, pasta=instalada)
    assert _conteudo(instalada) == V1


def test_instalacao_mexida_desfaz_e_levanta(pequena):
    info, instalada, _, _ = pequena
    (instalada / "_internal/lib.dll").write_bytes(b"outra")
    antes = _conteudo(instalada)
    with pytest.raises(pacote.ErroPacote):
        updater.atualizar_pequena(info, pasta=instalada)
    assert _conteudo(instalada) == antes


def test_download_cortado_da_pequena_nao_toca_na_instalacao(pequena):
    info, instalada, arquivos, _ = pequena
    arquivos["api/zip"] = _Resp(b"PK", anunciado=info.pequena.tamanho)
    with pytest.raises(updater.DownloadIncompleto):
        updater.atualizar_pequena(info, pasta=instalada)
    assert _conteudo(instalada) == V1


def test_sem_pequena_nem_tenta(tmp_path):
    info = updater.Atualizacao("3.4.0", "", COMPLETO, "api/completo", 1, "", "pag")
    with pytest.raises(pacote.ErroPacote, match="indisponível"):
        updater.atualizar_pequena(info, pasta=tmp_path)


def test_limpar_restos_na_abertura(tmp_path, monkeypatch):
    (tmp_path / "DocManager.exe.dm-old").write_bytes(b"velho")
    monkeypatch.setattr(updater, "pasta_instalacao", lambda: tmp_path)
    assert updater.limpar_restos() == 1 and not list(tmp_path.iterdir())
    monkeypatch.setattr(updater, "pasta_instalacao", lambda: None)
    assert updater.limpar_restos() == 0


def test_reabrir_abre_o_exe_novo_desligado(monkeypatch, tmp_path):
    chamadas = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **k: chamadas.append((a, k)))
    updater.reabrir(tmp_path / "DocManager.exe")
    (args,), kw = chamadas[0]
    assert args == [str(tmp_path / "DocManager.exe")] and kw["cwd"] == str(tmp_path)


def test_arquivo_pequeno_demais_e_recusado(servidor):
    arquivos, _, pasta = servidor
    info = updater.Atualizacao("3.4.0", "", COMPLETO, "api/completo", 0, "", "pag")
    arquivos["api/completo"] = _Resp(b"<html>login</html>")
    with pytest.raises(updater.HashDivergente, match="pequeno demais"):
        updater.baixar(info)
    assert not list(pasta.iterdir())


def test_completo_cortado_e_recusado(servidor):
    arquivos, _, _ = servidor
    info = updater.Atualizacao("3.4.0", "", COMPLETO, "api/completo", 0, _sha(COMPLETO_BYTES), "pag")
    arquivos["api/completo"] = _Resp(COMPLETO_BYTES[:1_200_000], anunciado=len(COMPLETO_BYTES))
    with pytest.raises(updater.DownloadIncompleto):
        updater.baixar(info)


def test_sha_errado_no_completo_e_erro_final(servidor):
    arquivos, _, _ = servidor
    info = updater.Atualizacao("3.4.0", "", COMPLETO, "api/completo", 0, "0" * 64, "pag")
    arquivos["api/completo"] = _Resp(COMPLETO_BYTES)
    with pytest.raises(updater.HashDivergente, match="não confere"):
        updater.baixar(info)


def test_baixar_apaga_downloads_velhos(servidor):
    arquivos, _, pasta = servidor
    (pasta / "DocManager_Itaipu_Setup_3.1.0.exe").write_bytes(b"velho")
    (pasta / "x.zip.part").write_bytes(b"velho")
    (pasta / "arquivos_3.3.0.json").write_bytes(b"velho")
    (pasta / "instalacao.log").write_text("log")
    arquivos["api/completo"] = _Resp(COMPLETO_BYTES)
    updater.baixar(updater.Atualizacao("3.4.0", "", COMPLETO, "api/completo", 0, "", "pag"))
    assert sorted(p.name for p in pasta.iterdir()) == [COMPLETO, "instalacao.log"]


# --------------------------------------------------------------------------
# Quando verificar
# --------------------------------------------------------------------------
def test_codigo_fonte_nao_se_atualiza(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "tok")
    assert "código-fonte" in updater.motivo_para_nao_verificar()


def test_copia_solta_nao_se_atualiza(monkeypatch, tmp_path):
    """Sem `unins*.exe` ao lado do .exe, o instalador criaria outra instalação."""
    monkeypatch.setattr(updater, "token", lambda: "tok")
    monkeypatch.setattr(updater, "empacotado", lambda: True)
    monkeypatch.setattr(updater, "pasta_instalacao", lambda: tmp_path)
    assert "não foi instalada" in updater.motivo_para_nao_verificar()
    (tmp_path / "unins000.exe").write_bytes(b"")
    assert updater.motivo_para_nao_verificar() == ""
    monkeypatch.setattr(updater, "token", lambda: "")
    assert "token" in updater.motivo_para_nao_verificar()


def test_canal_de_testes_desligado_por_padrao():
    cfg = ConfigManager()
    assert updater.canal_de_testes(cfg) is False
    cfg.set_setting("versoes_de_teste", True)
    assert updater.canal_de_testes(ConfigManager()) is True


def test_checar_no_canal_de_testes_consulta_a_lista(monkeypatch):
    monkeypatch.setattr(updater, "token", lambda: "tok")
    pedidos = []

    class R:
        status_code = 200

        def json(self):
            return [{"tag_name": "v3.3.0-rc.1", "prerelease": True,
                     "assets": [{"name": COMPLETO, "url": "u", "size": 5}]}]

        def close(self):
            pass

    monkeypatch.setattr(updater.rede, "abrir",
                        lambda url, **_k: (pedidos.append(url), (_Sessao(), R()))[1])
    info = updater.checar("3.2.0", canal_testes=True)
    assert pedidos == [f"{updater.API}/releases?per_page=20"]
    assert info.versao == "3.3.0-rc.1" and info.prerelease
