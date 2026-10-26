"""Persistência de configuração e caminhos (KB §20).

Config em Documents/DocManager_Itaipu/config.json, schema 2 - coexiste com o app
legado (que ignora chaves novas). Guarda o toggle da regra estrita VIP e o
último diretório usado por tipo de arquivo.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


def resource_path(rel: str) -> str:
    """Caminho de recurso empacotável (PyInstaller) ou em desenvolvimento."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _pasta_config() -> Path:
    """Mesma pasta do cofre de credenciais (respeita DOCMANAGER_DADOS_DIR)."""
    from .credenciais import pasta_dados

    return pasta_dados()


@dataclass
class AppSettings:
    regra_estrita_vip: bool = False
    dash_port: int = 8050
    # Base do atraso CMI na 0A: "reprogramacao" (quando houver) ou "prevista".
    base_atraso_cmi_0a: str = "reprogramacao"
    # --- atualização automática ---
    verificar_atualizacoes: bool = True
    # Versão que a pessoa mandou pular ("" = nenhuma). Não silencia as seguintes.
    versao_ignorada: str = ""
    # ISO da última consulta ao GitHub - evita bater no servidor a cada abertura.
    ultima_verificacao: str = ""
    # Canal de testes: também oferece pré-lançamentos (rc). Desligado por padrão.
    versoes_de_teste: bool = False


class ConfigManager:
    def __init__(self):
        self.caminho = _pasta_config() / "config.json"
        self._data = self._carregar()

    def _carregar(self) -> dict:
        if self.caminho.exists():
            try:
                return json.loads(self.caminho.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"schema": 2, "paths": {}, "settings": {}}

    def salvar(self) -> None:
        self._data["schema"] = 2
        try:
            self.caminho.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # --- últimos caminhos por tipo (com memória global "onde cliquei por último") ---
    def ultimo_dir(self, tipo: str) -> str:
        """Diretório inicial para o diálogo: o último do próprio `tipo`; se ainda
        não houver, o último de QUALQUER diálogo (`_ultimo`); senão Documentos."""
        paths = self._data.get("paths", {})
        for chave in (tipo, "_ultimo"):
            d = paths.get(chave, "")
            if d and os.path.isdir(d):
                return d
        return str(Path.home() / "Documents")

    def lembrar_dir(self, tipo: str, caminho: str) -> None:
        """Guarda o diretório do `caminho` para o `tipo` E na memória global
        `_ultimo` - assim abrir/salvar em qualquer módulo lembra o último local."""
        if caminho:
            d = os.path.dirname(caminho)
            paths = self._data.setdefault("paths", {})
            paths[tipo] = d
            paths["_ultimo"] = d
            self.salvar()

    # --- settings ---
    @property
    def settings(self) -> AppSettings:
        s = self._data.get("settings", {})
        return AppSettings(
            regra_estrita_vip=bool(s.get("regra_estrita_vip", False)),
            dash_port=int(s.get("dash_port", 8050)),
            base_atraso_cmi_0a=str(s.get("base_atraso_cmi_0a", "reprogramacao")),
            verificar_atualizacoes=bool(s.get("verificar_atualizacoes", True)),
            versao_ignorada=str(s.get("versao_ignorada", "")),
            ultima_verificacao=str(s.get("ultima_verificacao", "")),
            versoes_de_teste=bool(s.get("versoes_de_teste", False)),
        )

    def set_setting(self, chave: str, valor) -> None:
        self._data.setdefault("settings", {})[chave] = valor
        self.salvar()
