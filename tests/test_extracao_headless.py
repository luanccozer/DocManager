"""`DocManager.exe --extrair-aconex`: a extração sem janela que a CMI Suite dispara."""
import pandas as pd

from docmanager import aconex_backend as ab
from docmanager import extracao_headless as eh


def _resultado(completa=True, linhas=2):
    return ab.ResultadoExtracao(df=pd.DataFrame({"No. do Documento": [f"D{i}" for i in range(linhas)]}),
                                completa=completa, registros=linhas, motivo="" if completa else "rede caiu")


def _preparar(monkeypatch, resultado, usuarios=("Ana",)):
    monkeypatch.setattr(ab, "migrar_env_para_cofre", lambda log_cb=None: [])
    monkeypatch.setattr(ab, "usuarios_disponiveis", lambda: list(usuarios))
    usados = []
    monkeypatch.setattr(ab.AconexConfig, "para_usuario",
                        classmethod(lambda cls, nome, **k: usados.append(nome) or cls("c", "s", "u")))
    monkeypatch.setattr(ab, "extrair_base", lambda config, **k: resultado)
    limpos = []
    monkeypatch.setattr(ab, "limpar_checkpoint", lambda config: limpos.append(1))
    monkeypatch.setattr(ab, "salvar_excel", lambda df, caminho: pd.DataFrame(df).to_csv(caminho))
    return usados, limpos


def test_completa_grava_a_saida_com_o_primeiro_usuario_e_limpa_o_checkpoint(tmp_path, monkeypatch):
    usados, limpos = _preparar(monkeypatch, _resultado())
    saida, log = tmp_path / "pasta" / "base.xlsx", tmp_path / "log.txt"
    assert eh.main(["--saida", str(saida), "--log", str(log)]) == eh.OK
    assert saida.is_file() and not list(saida.parent.glob("*.parcial.*"))
    assert usados == ["Ana"] and limpos == [1]
    assert "2 linhas" in log.read_text(encoding="utf-8")


def test_incompleta_nao_grava_e_guarda_o_checkpoint(tmp_path, monkeypatch):
    _usados, limpos = _preparar(monkeypatch, _resultado(completa=False))
    saida = tmp_path / "base.xlsx"
    assert eh.main(["--saida", str(saida)]) == eh.INCOMPLETA
    assert not saida.exists() and limpos == []


def test_sem_usuario_cadastrado(tmp_path, monkeypatch):
    _preparar(monkeypatch, _resultado(), usuarios=())
    assert eh.main(["--saida", str(tmp_path / "b.xlsx")]) == eh.SEM_CREDENCIAL


def test_erro_inesperado_vai_para_o_log(tmp_path, monkeypatch):
    _preparar(monkeypatch, _resultado())

    def explode(config, **k):
        raise ConnectionError("sem rota")
    monkeypatch.setattr(ab, "extrair_base", explode)
    log = tmp_path / "log.txt"
    assert eh.main(["--saida", str(tmp_path / "b.xlsx"), "--log", str(log)]) == eh.FALHOU
    assert "sem rota" in log.read_text(encoding="utf-8")


def test_o_exe_despacha_sem_abrir_a_interface(tmp_path, monkeypatch):
    import sys

    import pytest

    from docmanager import __main__ as entrada
    chamadas = []
    monkeypatch.setattr(eh, "main", lambda argv: chamadas.append(argv) or 0)
    sys.modules.pop("docmanager.ui.main_app", None)
    with pytest.raises(SystemExit) as saiu:
        entrada.main(["--extrair-aconex", "--saida", "x.xlsx"])
    assert saiu.value.code == 0 and chamadas == [["--saida", "x.xlsx"]]
    assert "docmanager.ui.main_app" not in sys.modules
