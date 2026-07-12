"""Persistência de configuração e caminhos (KB §20).

Config em Documents/DocManager_Itaipu/config.json, schema 2 — coexiste com o app
legado (que ignora chaves novas). Guarda o toggle da regra estrita VIP e o
último diretório usado por tipo de arquivo.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def resource_path(rel: str) -> str:
    """Caminho de recurso empacotável (PyInstaller) ou em desenvolvimento."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def _pasta_config() -> Path:
    p = Path.home() / "Documents" / "DocManager_Itaipu"
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class AppSettings:
    regra_estrita_vip: bool = False
    dash_port: int = 8050


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

    # --- últimos caminhos por tipo ---
    def ultimo_dir(self, tipo: str) -> str:
        d = self._data.get("paths", {}).get(tipo, "")
        return d if d and os.path.isdir(d) else str(Path.home() / "Documents")

    def lembrar_dir(self, tipo: str, caminho: str) -> None:
        if caminho:
            self._data.setdefault("paths", {})[tipo] = os.path.dirname(caminho)
            self.salvar()

    # --- settings ---
    @property
    def settings(self) -> AppSettings:
        s = self._data.get("settings", {})
        return AppSettings(
            regra_estrita_vip=bool(s.get("regra_estrita_vip", False)),
            dash_port=int(s.get("dash_port", 8050)),
        )

    def set_setting(self, chave: str, valor) -> None:
        self._data.setdefault("settings", {})[chave] = valor
        self.salvar()
