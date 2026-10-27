"""Atualização "só do que mudou": manifesto, bases e pacotes pequenos.

Entre duas versões quase tudo é igual (Python, bibliotecas, DLLs). Por isso cada
Release publica, além do instalador completo:

  • `arquivos.json` - cada arquivo instalado, com SHA256 e tamanho. É a BASE da
    diferença da versão seguinte, e o que o app confere depois de aplicar;
  • um zip PEQUENO por versão de origem, só com o que mudou desde ela
    (`DocManager_Itaipu_Atualizacao_<de>_para_<para>.zip`). O formato e quem o
    aplica moram em `docmanager/services/pacote.py` - o método da CMI Suite;
  • a lista `pequenas` e o `arquivos_json` no `latest.json`, com os SHA256.

Não há diff binário: o arquivo que mudou vai inteiro. É mais simples, e o ganho
já vem do resto da pasta, que não muda.

Subcomandos:

    manifesto       percorre dist\\DocManager (+ extras) e grava o arquivos.json
    escolher-bases  a partir do JSON de GET /releases, as versões de origem
    pacotes         um zip por base + latest.json
    conteudo-exe    lista o que vai dentro do DocManager.exe (diagnóstico)

Pular um pacote NUNCA derruba o Release: sai um `::warning::` e quem estiver
naquela versão recebe o completo, como antes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from docmanager.services import pacote  # noqa: E402 - o formato mora num lugar só

ARQUIVO_MANIFESTO = "arquivos.json"
ARQUIVO_CONTEUDO_EXE = "conteudo_exe.json"
# Acordo com o app (services/updater.py) e com o workflow.
PREFIXO_COMPLETO = "DocManager_Itaipu_Setup_"

# Se o pequeno copiaria mais que isto do total, não compensa: o completo,
# comprimido inteiro, sai quase do mesmo tamanho.
LIMITE_FRACAO = 0.60
# De quantas versões anteriores (pré-lançamentos inclusive) sai um pequeno,
# além da última versão normal, que entra sempre.
BASES_RECENTES = 3


def _aviso(msg: str) -> None:
    # Só ASCII no log do runner (pode estar em cp1252).
    print(f"::warning::{msg}".encode("ascii", "replace").decode("ascii"))


def sha256_arquivo(caminho: Path) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _gravar_json(destino: Path, dados) -> None:
    # UTF-8 sem BOM: é o que o app e o próprio script releem.
    destino.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────── versões ────────────────────────────────────
# Mesma regra do `services/updater.versao_em_partes` (há teste conferindo que os
# dois concordam). Copiada porque este script não pode importar o app: o
# updater puxa `requests`, e aqui só vale a biblioteca padrão.

def versao_em_partes(versao: str) -> tuple:
    texto = str(versao or "").strip().lstrip("vV")
    nucleo, _, pre = texto.partition("-")
    numeros = [int(p) if p.isdigit() else 0 for p in re.split(r"[.+]", nucleo) if p != ""]
    numeros = (numeros + [0, 0, 0])[:3]
    if not pre:
        return (tuple(numeros), (1,))
    partes = tuple((0, int(p), "") if p.isdigit() else (1, 0, p)
                   for p in re.split(r"[.+]", pre) if p != "")
    return (tuple(numeros), (0,) + partes)


# ─────────────────────────────── manifesto ──────────────────────────────────

def _extras(itens: list[str] | None) -> dict[str, Path]:
    """`destino=origem` → {"destino": Path(origem)}. Ex.: CHANGELOG.md=CHANGELOG.md
    (o .iss instala o CHANGELOG na raiz de {app}, fora do dist)."""
    saida: dict[str, Path] = {}
    for item in itens or []:
        destino, sep, origem = item.partition("=")
        if not sep:
            origem = destino
        saida[destino.replace("\\", "/").strip("/")] = Path(origem)
    return saida


def fontes(dist: Path, extras: dict[str, Path]) -> dict[str, Path]:
    """Caminho relativo instalado (com '/') → arquivo de origem no build."""
    saida = {p.relative_to(dist).as_posix(): p
             for p in sorted(dist.rglob("*")) if p.is_file()}
    saida.update(extras)
    return saida


def montar_manifesto(versao: str, dist: Path, extras: dict[str, Path]) -> dict:
    arquivos = {}
    for rel, origem in sorted(fontes(dist, extras).items()):
        arquivos[rel] = {"sha256": sha256_arquivo(origem), "tamanho": origem.stat().st_size}
    return {"versao": versao, "arquivos": arquivos}


# ──────────────────────────────── bases ─────────────────────────────────────

def _tem_manifesto(release: dict) -> bool:
    return any(a.get("name") == ARQUIVO_MANIFESTO for a in release.get("assets", []))


def escolher_bases(releases: list[dict], versao_nova: str) -> list[str]:
    """Tags de onde sai um pequeno: as `BASES_RECENTES` versões mais novas que
    publicaram `arquivos.json` (pré-lançamentos inclusive) e, SEMPRE, a última
    versão normal - é nela que está quase todo mundo.

    Rascunho não conta, e só entra versão ANTERIOR à nova (um re-run de uma tag
    velha não gera "atualização" de uma versão mais nova para ela)."""
    chave_nova = versao_em_partes(versao_nova)
    candidatas = [r for r in releases
                  if not r.get("draft") and _tem_manifesto(r)
                  and versao_em_partes(r.get("tag_name", "")) < chave_nova]
    candidatas.sort(key=lambda r: versao_em_partes(r.get("tag_name", "")), reverse=True)
    tags = [r["tag_name"] for r in candidatas[:BASES_RECENTES]]
    normal = next((r for r in candidatas if not r.get("prerelease")), None)
    if normal is not None and normal["tag_name"] not in tags:
        tags.append(normal["tag_name"])
    return tags


# ─────────────────────────────── pacotes ────────────────────────────────────

def fracao_copiada(alterados: list[str], nova: dict) -> float:
    """Quanto do total o pacote leva. `nova` é o campo "arquivos" do manifesto."""
    total = sum(int(i.get("tamanho", 0)) for i in nova.values())
    copiado = sum(int(nova[rel].get("tamanho", 0)) for rel in alterados)
    return copiado / total if total else 0.0


def _info(caminho: Path) -> dict:
    return {"arquivo": caminho.name, "sha256": sha256_arquivo(caminho),
            "tamanho": caminho.stat().st_size}


def gerar_pacote(*, base: dict, nova: dict, origens: dict[str, Path],
                 pasta_saida: Path) -> dict | None:
    """O zip de `base` para `nova`. Devolve a entrada de `pequenas` do
    latest.json, ou None quando o pacote é pulado (com o motivo no log)."""
    de, versao = base["versao"], nova["versao"]
    alterados, removidos = pacote.diferenca(base, nova)
    if not (alterados or removidos):
        _aviso(f"{de} -> {versao}: nenhum arquivo mudou; sem atualizacao pequena.")
        return None
    fracao = fracao_copiada(alterados, nova["arquivos"])
    print(f"{de} -> {versao}: copiar {len(alterados)}, remover {len(removidos)} "
          f"arquivo(s); {fracao:.0%} do total.")
    for rel in alterados[:40]:
        print(f"    + {rel}")
    if fracao > LIMITE_FRACAO:
        _aviso(f"{de} -> {versao}: o pequeno levaria {fracao:.0%} do total (limite "
               f"{LIMITE_FRACAO:.0%}); quem estiver na {de} recebe o completo.")
        return None
    try:
        zip_ = pacote.montar(origens, base, nova, pasta_saida)
    except (OSError, KeyError, pacote.ErroPacote) as e:
        _aviso(f"{de} -> {versao}: o pacote nao saiu ({e}); quem estiver na {de} "
               f"recebe o completo.")
        return None
    return {"de": de, **_info(zip_)}


# ─────────────────────────── conteúdo do .exe ───────────────────────────────

def conteudo_exe(exe: Path) -> dict:
    """{entrada: sha256} do que vai dentro do DocManager.exe (PKG e PYZ).

    Diagnóstico: o `.exe` muda inteiro se UMA coisa lá dentro mudar. Comparar
    esta lista com a da versão anterior diz qual foi (ordem de um set,
    timestamp, uma biblioteca que o pip atualizou...)."""
    from PyInstaller.archive.readers import CArchiveReader  # só no runner de build

    pkg = CArchiveReader(str(exe))
    saida = {"__exe__": sha256_arquivo(exe)}
    for nome, meta in sorted(pkg.toc.items()):
        tipo = meta[-1] if isinstance(meta, (tuple, list)) else ""
        if tipo == "z":   # o PYZ: abre e lista módulo por módulo
            pyz = pkg.open_embedded_archive(nome)
            for mod in sorted(pyz.toc):
                bruto = pyz.extract(mod, raw=True)
                saida[f"{nome}:{mod}"] = hashlib.sha256(bruto or b"").hexdigest()
            continue
        saida[nome] = hashlib.sha256(pkg.extract(nome) or b"").hexdigest()
    return saida


def comparar_conteudo(anterior: dict, atual: dict) -> list[str]:
    linhas = []
    for nome in sorted(set(anterior) | set(atual)):
        if nome not in anterior:
            linhas.append(f"  novo    {nome}")
        elif nome not in atual:
            linhas.append(f"  sumiu   {nome}")
        elif anterior[nome] != atual[nome]:
            linhas.append(f"  mudou   {nome}")
    return linhas


# ──────────────────────────────── CLI ───────────────────────────────────────

def _cmd_manifesto(args) -> None:
    dados = montar_manifesto(args.versao, args.dist, _extras(args.extra))
    _gravar_json(args.saida, dados)
    total = sum(i["tamanho"] for i in dados["arquivos"].values())
    print(f"{args.saida}: {len(dados['arquivos'])} arquivos, {total} bytes")


def _cmd_escolher_bases(args) -> None:
    releases = json.loads(args.releases.read_text(encoding="utf-8-sig"))
    tags = escolher_bases(releases, args.versao)
    # Bytes com "\n", NUNCA "\r\n": no runner Windows o `\r` grudava na tag
    # dentro do $(...) do bash, e todas as bases menos a última davam
    # "release not found". O stdout em modo texto do Windows faria a troca.
    sys.stdout.buffer.write("".join(f"{t}\n" for t in tags).encode("ascii"))
    sys.stdout.flush()


def _cmd_pacotes(args) -> None:
    nova = json.loads(args.manifesto.read_text(encoding="utf-8-sig"))
    origens = fontes(args.dist, _extras(args.extra))
    latest = json.loads(args.latest.read_text(encoding="utf-8-sig"))
    args.saida.mkdir(parents=True, exist_ok=True)
    entradas = []
    for arq in sorted(args.bases.glob("*.json")):
        try:
            base = json.loads(arq.read_text(encoding="utf-8-sig"))
            base["versao"] = str(base.get("versao") or arq.stem).lstrip("vV")
            base["arquivos"]
        except (OSError, ValueError, KeyError, TypeError) as e:
            _aviso(f"{arq.name}: manifesto da base ilegivel ({e}); pulado.")
            continue
        entrada = gerar_pacote(base=base, nova=nova, origens=origens, pasta_saida=args.saida)
        if entrada is None:
            continue
        entradas.append(entrada)
        print(f"  -> {entrada['arquivo']}: {entrada['tamanho']} bytes")
    # `pequenas`, e NÃO `atualizacoes`: o app 3.2.0-3.3.0 lê `atualizacoes` e
    # rodaria o zip novo como se fosse o instalador pequeno dele. Sem a lista,
    # ele baixa o completo.
    latest.pop("atualizacoes", None)
    latest["pequenas"] = entradas
    latest["arquivos_json"] = {k: v for k, v in _info(args.manifesto).items() if k != "arquivo"}
    _gravar_json(args.latest, latest)
    # Lista para o passo que publica, um caminho por linha, com "\n" puro.
    gerados = [args.saida / e["arquivo"] for e in entradas]
    args.lista.write_bytes("".join(f"{p.as_posix()}\n" for p in gerados).encode("utf-8"))
    print(f"{len(entradas)} pacote(s) pequeno(s); latest.json atualizado.")


def _cmd_conteudo_exe(args) -> None:
    try:
        atual = conteudo_exe(args.exe)
    except Exception as e:  # noqa: BLE001 - diagnóstico nunca derruba o Release
        _aviso(f"nao foi possivel listar o conteudo do .exe: {e}")
        return
    _gravar_json(args.saida, atual)
    print(f"{args.saida}: {len(atual)} entradas")
    if args.anterior and args.anterior.is_file():
        anterior = json.loads(args.anterior.read_text(encoding="utf-8-sig"))
        if anterior.get("__exe__") == atual["__exe__"]:
            print("O .exe e identico ao da versao anterior.")
            return
        diferencas = [d for d in comparar_conteudo(anterior, atual) if "__exe__" not in d]
        print(f"O .exe mudou em relacao a versao anterior ({len(diferencas)} entrada(s)):")
        for linha in diferencas[:80]:
            print(linha)
        if not diferencas:
            print("  nenhuma entrada mudou: a diferenca esta no cabecalho do .exe "
                  "(timestamp do PE? confira o SOURCE_DATE_EPOCH).")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("manifesto")
    m.add_argument("--dist", type=Path, required=True)
    m.add_argument("--extra", action="append", help="destino=origem (repetível)")
    m.add_argument("--versao", required=True)
    m.add_argument("--saida", type=Path, default=Path(ARQUIVO_MANIFESTO))
    m.set_defaults(func=_cmd_manifesto)

    b = sub.add_parser("escolher-bases")
    b.add_argument("--releases", type=Path, required=True, help="JSON de GET /releases")
    b.add_argument("--versao", required=True)
    b.set_defaults(func=_cmd_escolher_bases)

    p = sub.add_parser("pacotes")
    p.add_argument("--manifesto", type=Path, required=True)
    p.add_argument("--bases", type=Path, required=True, help="pasta com <tag>.json")
    p.add_argument("--dist", type=Path, required=True)
    p.add_argument("--extra", action="append")
    p.add_argument("--saida", type=Path, default=RAIZ / "installer" / "Output")
    p.add_argument("--latest", type=Path, default=Path("latest.json"))
    p.add_argument("--lista", type=Path, default=Path("pacotes.txt"))
    p.set_defaults(func=_cmd_pacotes)

    c = sub.add_parser("conteudo-exe")
    c.add_argument("--exe", type=Path, required=True)
    c.add_argument("--saida", type=Path, default=Path(ARQUIVO_CONTEUDO_EXE))
    c.add_argument("--anterior", type=Path)
    c.set_defaults(func=_cmd_conteudo_exe)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
