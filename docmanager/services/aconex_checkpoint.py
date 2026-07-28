"""Checkpoint retomável da extração Aconex (KB §28).

A extração completa do projeto leva ~30 min de paginação. Quando a conexão caía
no meio, todo o tempo ia embora: o código parava a paginação e devolvia o que
tinha em memória — **sem avisar que estava truncado**. Este módulo persiste as
páginas já baixadas para que a próxima tentativa continue de onde parou.

Formato (dois arquivos por extração):
  - `<base>.jsonl`  — um registro bruto do XML por linha, anexado a cada página;
  - `<base>.meta.json` — `{pagina, total, offset, ...}` do último ponto ÍNTEGRO.

O `offset` (tamanho do .jsonl no fim da última página confirmada) é o que torna
a retomada exata: se o processo morre no meio da escrita de uma página, o
arquivo é TRUNCADO de volta ao offset antes de continuar. Sem isso, uma página
pela metade viraria registro duplicado ou JSON quebrado.

A chave do checkpoint inclui projeto + campos + paginação: mudou a consulta,
mudou o checkpoint — nunca se retoma uma extração com parâmetros diferentes.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

VERSAO_FORMATO = 1


def pasta_padrao() -> Path:
    """`Documents/DocManager_Itaipu/extracoes` — ao lado da config do app."""
    p = Path.home() / "Documents" / "DocManager_Itaipu" / "extracoes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def chave_extracao(*, project_id: str, campos: str, page_size: int,
                   sort_field: str, sort_direction: str) -> str:
    """Identidade da consulta: mudou qualquer parâmetro, é outra extração."""
    crua = f"{project_id}|{campos}|{page_size}|{sort_field}|{sort_direction}"
    return f"{project_id}_{hashlib.sha1(crua.encode()).hexdigest()[:10]}"


@dataclass
class EstadoCheckpoint:
    pagina: int = 0          # última página BAIXADA E CONFIRMADA
    total: int = 0           # registros confirmados
    offset: int = 0          # bytes íntegros do .jsonl
    atualizado_em: str = ""

    @property
    def proxima_pagina(self) -> int:
        return self.pagina + 1


class CheckpointExtracao:
    """Diário de bordo da paginação. Use como context manager ou chame
    `abrir()`/`fechar()` — `registrar_pagina` é o único ponto de commit."""

    def __init__(self, chave: str, pasta: Path | str | None = None):
        self.pasta = Path(pasta) if pasta is not None else pasta_padrao()
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.chave = chave
        self.path_dados = self.pasta / f"{chave}.jsonl"
        self.path_meta = self.pasta / f"{chave}.meta.json"
        self.path_meta_tmp = self.pasta / f"{chave}.meta.json.tmp"
        self.estado = EstadoCheckpoint()
        self._fh = None

    # ------------------------------------------------------------------
    def existe(self) -> bool:
        return self.path_meta.exists() and self.path_dados.exists()

    def ler_meta(self) -> EstadoCheckpoint | None:
        try:
            dados = json.loads(self.path_meta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — checkpoint corrompido = sem checkpoint
            return None
        if dados.get("versao") != VERSAO_FORMATO or dados.get("chave") != self.chave:
            return None
        return EstadoCheckpoint(
            pagina=int(dados.get("pagina", 0)), total=int(dados.get("total", 0)),
            offset=int(dados.get("offset", 0)), atualizado_em=str(dados.get("atualizado_em", "")))

    def carregar(self) -> list[dict]:
        """Registros já baixados, truncando qualquer página incompleta.

        Devolve `[]` (e zera o estado) se o checkpoint não for utilizável.
        """
        estado = self.ler_meta() if self.existe() else None
        if estado is None:
            self.estado = EstadoCheckpoint()
            return []
        # Corta o rabo de uma página interrompida no meio da escrita.
        try:
            if self.path_dados.stat().st_size > estado.offset:
                with open(self.path_dados, "r+b") as fh:
                    fh.truncate(estado.offset)
        except OSError:
            self.estado = EstadoCheckpoint()
            return []
        registros: list[dict] = []
        try:
            with open(self.path_dados, encoding="utf-8") as fh:
                for linha in fh:
                    linha = linha.strip()
                    if linha:
                        registros.append(json.loads(linha))
        except (OSError, json.JSONDecodeError):
            self.estado = EstadoCheckpoint()
            return []
        self.estado = estado
        return registros

    # ------------------------------------------------------------------
    def abrir(self) -> None:
        """Abre o .jsonl em append BINÁRIO.

        Binário de propósito: em modo texto o `tell()` devolve um cookie opaco,
        que não serve como offset de `truncate()`. Em binário ele é o byte exato
        — que é justamente o que torna a retomada precisa.
        """
        if self._fh is None:
            self._fh = open(self.path_dados, "ab")

    def registrar_pagina(self, pagina: int, registros: list[dict]) -> None:
        """Commit de UMA página: grava as linhas, força para o disco e só então
        atualiza o meta. Nessa ordem, um crash nunca deixa o meta apontando
        para dados que não chegaram ao disco."""
        self.abrir()
        for r in registros:
            self._fh.write((json.dumps(r, ensure_ascii=False) + "\n").encode("utf-8"))
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self.estado = EstadoCheckpoint(
            pagina=pagina, total=self.estado.total + len(registros),
            offset=self._fh.tell(), atualizado_em=datetime.now().isoformat(timespec="seconds"))
        self._gravar_meta()

    def _gravar_meta(self) -> None:
        payload = {
            "versao": VERSAO_FORMATO, "chave": self.chave,
            "pagina": self.estado.pagina, "total": self.estado.total,
            "offset": self.estado.offset, "atualizado_em": self.estado.atualizado_em,
        }
        self.path_meta_tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        os.replace(self.path_meta_tmp, self.path_meta)   # troca atômica

    def fechar(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            finally:
                self._fh = None

    def limpar(self) -> None:
        """Apaga o checkpoint — chamar só depois que a base foi SALVA."""
        self.fechar()
        for p in (self.path_dados, self.path_meta, self.path_meta_tmp):
            try:
                p.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.fechar()
        return False


def limpar_antigos(pasta: Path | str | None = None, *, dias: int = 30) -> int:
    """Remove checkpoints esquecidos há mais de `dias`. Devolve quantos saíram."""
    base = Path(pasta) if pasta is not None else pasta_padrao()
    if not base.exists():
        return 0
    limite = datetime.now().timestamp() - dias * 86400
    removidos = 0
    for p in base.glob("*.meta.json"):
        try:
            if p.stat().st_mtime >= limite:
                continue
            chave = p.name[: -len(".meta.json")]
            p.unlink()
            (base / f"{chave}.jsonl").unlink(missing_ok=True)
            removidos += 1
        except OSError:
            continue
    return removidos
