"""A atualização pequena: só os arquivos que mudaram entre duas versões.

Copiado do método da CMI Suite (`cmi_suite/core/pacote.py`), que funciona sem
instalador nenhum no meio. O mesmo módulo MONTA o pacote (no workflow de
Release, via `tools/gerar_atualizacao.py`) e o APLICA (na máquina de quem usa):
uma implementação só do formato - se as duas pontas tivessem cada uma a sua, a
primeira divergência viraria uma instalação quebrada.

Só biblioteca padrão: o gerador roda no runner do Release.

Formato
-------
`arquivos.json` (publicado em todo Release desde a 3.2.0):
    {"versao": "3.3.0", "arquivos": {"DocManager.exe": {"sha256": ..., "tamanho": ...}, ...}}
(o valor também pode ser só o SHA256, como no da CMI Suite).

`DocManager_Itaipu_Atualizacao_<de>_para_<para>.zip`:
    manifesto.json   {"de": ..., "para": ..., "alterados": [...], "removidos": [...]}
    arquivos/<caminho relativo>   (cada arquivo novo ou alterado)

Como aplicar com o programa ABERTO
----------------------------------
O Windows não deixa sobrescrever nem apagar um `.exe` ou uma DLL em uso, mas
deixa RENOMEAR. Então cada arquivo antigo vira `<nome>.dm-old` e o novo é
escrito no lugar; os `.dm-old` são apagados na próxima abertura
(`limpar_restos`). Se qualquer passo falhar, ou se o resultado não bater com o
`arquivos.json` da versão nova, tudo volta como estava (`aplicar` desfaz na
ordem inversa) e a janela da atualização cai para o instalador completo.

Até a 3.3.0 o "pequeno" era um instalador Inno à parte: passava pelo UAC, pela
espera do mutex e pela trava de versão do registro, e cada um desses passos
era um jeito de não atualizar. Aqui não há nenhum deles.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path, PurePath

__all__ = ["SUFIXO_ANTIGO", "nome_pacote", "sha_de", "diferenca", "montar", "aplicar",
           "limpar_restos", "dentro", "ErroPacote"]

SUFIXO_ANTIGO = ".dm-old"
_BLOCO = 1024 * 1024


class ErroPacote(RuntimeError):
    """O pacote não pôde ser aplicado - e a pasta ficou exatamente como estava."""


def nome_pacote(de: str, para: str) -> str:
    return f"DocManager_Itaipu_Atualizacao_{de}_para_{para}.zip"


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with Path(caminho).open("rb") as f:
        while bloco := f.read(_BLOCO):
            h.update(bloco)
    return h.hexdigest()


def sha_de(valor) -> str:
    """O SHA256 de uma entrada do `arquivos.json`: `{"sha256": ...}` ou o texto puro."""
    if isinstance(valor, dict):
        valor = valor.get("sha256")
    return str(valor or "").strip().lower()


def diferenca(antigo: dict, novo: dict) -> tuple[list[str], list[str]]:
    """(alterados ou novos, removidos), em ordem estável. Recebe os manifestos inteiros."""
    a, n = antigo["arquivos"], novo["arquivos"]
    alterados = sorted(rel for rel, v in n.items() if rel not in a or sha_de(a[rel]) != sha_de(v))
    removidos = sorted(rel for rel in a if rel not in n)
    return alterados, removidos


def montar(origens: dict[str, Path], antigo: dict, novo: dict, destino: Path) -> Path:
    """Grava o zip de `antigo` para `novo` em `destino`.

    `origens` é caminho instalado → arquivo no build: o CHANGELOG.md, por
    exemplo, é instalado na raiz mas não sai do `dist`."""
    alterados, removidos = diferenca(antigo, novo)
    for rel in alterados + removidos:
        dentro(PurePath("."), rel)   # o gerador recusa o que o app recusaria
    saida = Path(destino) / nome_pacote(antigo["versao"], novo["versao"])
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("manifesto.json", json.dumps({
            "de": antigo["versao"], "para": novo["versao"],
            "alterados": alterados, "removidos": removidos,
        }, ensure_ascii=False, indent=1))
        for rel in alterados:
            z.write(origens[rel], f"arquivos/{rel}")
    return saida


def dentro(base: PurePath, relativo: str) -> PurePath:
    """`base / relativo`, ou ErroPacote se `relativo` puder sair de `base` (zip-slip).

    As regras da CMI Suite, todas por RECUSA (nenhum nome legítimo as viola):
    só `/` como separador; nada de `\\` (separador no Windows), `:` (letra de
    unidade, fluxo alternativo do NTFS) nem NUL; nenhuma parte vazia, `.`, `..`
    ou terminada em ponto ou espaço (o Windows apaga esses finais e `.. ` vira
    `..`)."""
    if not relativo or "\\" in relativo or ":" in relativo or relativo.startswith("/"):
        raise ErroPacote(f"caminho inválido no pacote: {relativo!r}")
    partes = relativo.split("/")
    for parte in partes:
        if parte in ("", ".", "..") or parte != parte.rstrip(". ") or "\x00" in parte:
            raise ErroPacote(f"caminho inválido no pacote: {relativo!r}")
    return base.joinpath(*partes)


def _afastar(caminho: Path) -> Path:
    """Renomeia o arquivo (em uso ou não) para fora do caminho, e devolve o novo nome."""
    alvo = caminho.with_name(caminho.name + SUFIXO_ANTIGO)
    n = 1
    while alvo.exists():
        try:
            alvo.unlink()  # resto de uma atualização anterior
            break
        except OSError:  # ainda em uso: escolhe outro nome
            alvo = caminho.with_name(f"{caminho.name}.{n}{SUFIXO_ANTIGO}")
            n += 1
    caminho.rename(alvo)
    return alvo


def aplicar(arquivo_zip: Path, pasta: Path, novo: dict) -> list[str]:
    """Aplica o pacote sobre `pasta` e confere contra `novo` (o arquivos.json).

    Devolve os caminhos alterados. Em qualquer falha desfaz tudo e levanta
    ErroPacote: a pasta fica exatamente como estava.
    """
    pasta = Path(pasta)
    feitos: list[tuple[Path, Path | None]] = []
    try:
        with zipfile.ZipFile(arquivo_zip) as z:
            info = json.loads(z.read("manifesto.json"))
            if info.get("para") != novo.get("versao"):
                raise ErroPacote(f"o pacote leva à {info.get('para')}, "
                                 f"não à {novo.get('versao')}")
            for rel in info["alterados"]:
                destino = dentro(pasta, rel)
                destino.parent.mkdir(parents=True, exist_ok=True)
                antigo = _afastar(destino) if destino.exists() else None
                feitos.append((destino, antigo))
                with z.open(f"arquivos/{rel}") as origem, destino.open("wb") as saida:
                    shutil.copyfileobj(origem, saida, _BLOCO)
            for rel in info["removidos"]:
                destino = dentro(pasta, rel)
                if destino.exists():
                    feitos.append((destino, _afastar(destino)))

        for rel, valor in novo["arquivos"].items():
            caminho = dentro(pasta, rel)
            if not caminho.is_file() or sha256(caminho) != sha_de(valor):
                raise ErroPacote(f"{rel} não confere com a versão {novo['versao']}")
        return list(info["alterados"])
    except Exception as erro:
        _desfazer(feitos)
        if isinstance(erro, ErroPacote):
            raise
        raise ErroPacote(f"atualização pequena desfeita: {erro}") from erro


def _desfazer(feitos: list[tuple[Path, Path | None]]) -> None:
    for destino, antigo in reversed(feitos):
        try:
            if destino.exists():
                destino.unlink()
            if antigo is not None:
                antigo.rename(destino)
        except OSError:
            continue  # o que der para voltar, volta; o resto o completo conserta


def limpar_restos(pasta: Path) -> int:
    """Apaga os `.dm-old` que a última atualização deixou. Em uso? Fica para a próxima."""
    apagados = 0
    for resto in Path(pasta).rglob(f"*{SUFIXO_ANTIGO}"):
        try:
            resto.unlink()
            apagados += 1
        except OSError:
            continue
    return apagados
