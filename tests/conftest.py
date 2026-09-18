"""Isolamento dos dados do usuário durante os testes.

Config e credenciais moram em `Documentos\\DocManager_Itaipu`. Sem isolar, a
suíte leria (e escreveria!) o cofre real de quem está rodando os testes — e o
resultado mudaria de máquina para máquina. `DOCMANAGER_DADOS_DIR` redireciona a
pasta inteira para um diretório temporário por teste.
"""
import pytest

from docmanager.services import credenciais


@pytest.fixture(autouse=True)
def dados_isolados(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCMANAGER_DADOS_DIR", str(tmp_path / "dados"))
    # O cofre é um singleton em memória: zera para o teste pegar a pasta nova.
    monkeypatch.setattr(credenciais, "_cofre", None, raising=False)
    yield
    credenciais._cofre = None
