"""Atualização "só do que mudou": manifesto, bases e instaladores pequenos.

Entre duas versões quase tudo é igual (Python, bibliotecas, DLLs). Por isso cada
Release publica, além do instalador completo:

  • `arquivos.json` - cada arquivo instalado, com SHA256 e tamanho. É a BASE da
    diferença da versão seguinte;
  • um instalador PEQUENO por versão de origem, só com o que mudou desde ela
    (em dois formatos, `.zip` e `.exe` - ver `pacotes`);
  • a lista `atualizacoes` no `latest.json`, que diz qual pequeno serve para
    qual versão instalada. O app instalado procura a entrada com `de` igual à
    própria versão; sem ela, baixa o completo.

Não há diff binário: o arquivo que mudou vai inteiro. É mais simples, e o ganho
já vem do resto da pasta, que não muda.

Só biblioteca padrão (roda no runner antes de qualquer coisa ser instalada, e o
`conteudo-exe` importa o PyInstaller só se ele existir). Subcomandos:

    manifesto       percorre dist\\DocManager (+ extras) e grava o arquivos.json
    escolher-bases  a partir do JSON de GET /releases, as versões de origem
    pacotes         diferença + includes do Inno + ISCC + zip + latest.json
    conteudo-exe    lista o que vai dentro do DocManager.exe (diagnóstico)

Pular um pacote NUNCA derruba o Release: sai um `::warning::` e quem estiver
naquela versão recebe o completo, como antes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ARQUIVO_MANIFESTO = "arquivos.json"
ARQUIVO_CONTEUDO_EXE = "conteudo_exe.json"
# Os dois prefixos são um ACORDO com o app (services/updater.py) e com o .iss
# (OutputBaseFilename). "Setup" vem antes de "Update" na ordem alfabética: o app
# 3.1.x, que pega "o primeiro .exe do Release", continua pegando o completo.
PREFIXO_COMPLETO = "DocManager_Itaipu_Setup_"
PREFIXO_PEQUENO = "DocManager_Itaipu_Update_"

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


# ────────────────────────────── diferença ───────────────────────────────────

@dataclass
class Diferenca:
    copiar: list[str] = field(default_factory=list)          # novos ou com SHA diferente
    remover: list[str] = field(default_factory=list)         # sumiram
    pastas_remover: list[str] = field(default_factory=list)  # deixaram de existir

    @property
    def vazia(self) -> bool:
        return not (self.copiar or self.remover)


def _pastas(caminhos) -> set[str]:
    pastas = set()
    for c in caminhos:
        partes = c.split("/")[:-1]
        for i in range(1, len(partes) + 1):
            pastas.add("/".join(partes[:i]))
    return pastas


def diferenca(base: dict, nova: dict) -> Diferenca:
    """`base` e `nova` são o campo "arquivos" de dois manifestos."""
    copiar = sorted(rel for rel, info in nova.items()
                    if rel not in base or base[rel].get("sha256") != info.get("sha256"))
    remover = sorted(rel for rel in base if rel not in nova)
    sumidas = _pastas(base) - _pastas(nova)
    # Da mais funda para a mais rasa: o dirifempty só apaga pasta vazia.
    pastas = sorted(sumidas, key=lambda p: (-p.count("/"), p))
    return Diferenca(copiar, remover, pastas)


def fracao_copiada(dif: Diferenca, nova: dict) -> float:
    total = sum(int(i.get("tamanho", 0)) for i in nova.values())
    copiado = sum(int(nova[rel].get("tamanho", 0)) for rel in dif.copiar)
    return copiado / total if total else 0.0


# ─────────────────────────── includes do Inno ───────────────────────────────

def escapar_inno(texto: str) -> str:
    """'{' abre constante no Inno e '"' fecha o valor entre aspas."""
    return texto.replace("{", "{{").replace('"', '""')


def _win(rel: str) -> str:
    return rel.replace("/", "\\")


def linhas_arquivos(dif: Diferenca, origens: dict[str, Path], pasta_iss: Path) -> list[str]:
    linhas = []
    for rel in dif.copiar:
        origem = Path(os.path.relpath(Path(origens[rel]).resolve(), pasta_iss.resolve()))
        sub = rel.rsplit("/", 1)[0] if "/" in rel else ""
        destino = "{app}" + ("\\" + escapar_inno(_win(sub)) if sub else "")
        linhas.append(f'Source: "{escapar_inno(_win(origem.as_posix()))}"; '
                      f'DestDir: "{destino}"; Flags: ignoreversion')
    return linhas


def linhas_remover(dif: Diferenca) -> list[str]:
    linhas = [f'Type: files; Name: "{{app}}\\{escapar_inno(_win(rel))}"' for rel in dif.remover]
    linhas += [f'Type: dirifempty; Name: "{{app}}\\{escapar_inno(_win(p))}"'
               for p in dif.pastas_remover]
    return linhas


def gravar_include(destino: Path, linhas: list[str], titulo: str) -> None:
    # UTF-8 COM BOM: é assim que o Inno reconhece um include em UTF-8 (sem o
    # BOM ele lê na code page do Windows e um nome com acento sai trocado).
    cabecalho = [f"; {titulo} - GERADO por tools/gerar_atualizacao.py, nao edite."]
    destino.write_text("\n".join(cabecalho + linhas) + "\n", encoding="utf-8-sig")


# ─────────────────────────────── pacotes ────────────────────────────────────

def nome_pequeno(de: str, para: str) -> str:
    return f"{PREFIXO_PEQUENO}{de}_para_{para}"


def _info(caminho: Path) -> dict:
    return {"arquivo": caminho.name, "sha256": sha256_arquivo(caminho),
            "tamanho": caminho.stat().st_size}


def zipar(exe: Path) -> Path:
    """Um `.zip` sem compressão e sem senha, com o `.exe` sozinho dentro.

    Não é para esconder nada do proxy: é outro formato para a mesma coisa. Na
    rede da empresa o proxy cortava o fim de um formato e deixava passar outro,
    então o app tenta zip → exe → completo."""
    destino = exe.with_suffix(".zip")
    destino.unlink(missing_ok=True)
    with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_STORED) as z:
        z.write(exe, arcname=exe.name)
    return destino


def entrada_latest(de: str, exe: Path, zip_: Path) -> dict:
    return {"de": de, **_info(exe),
            "zip": {**_info(zip_), "sha256_dentro": sha256_arquivo(exe)}}


def gerar_pacote(*, de: str, base: dict, nova: dict, origens: dict[str, Path],
                 iss: Path, iscc: str, versao: str, versao_info: str,
                 pasta_saida: Path) -> dict | None:
    """Gera o pequeno de `de` para `versao`. Devolve a entrada do latest.json,
    ou None quando o pacote é pulado (com o motivo no log)."""
    dif = diferenca(base.get("arquivos", {}), nova["arquivos"])
    if dif.vazia:
        _aviso(f"{de} -> {versao}: nenhum arquivo mudou; sem instalador pequeno.")
        return None
    fracao = fracao_copiada(dif, nova["arquivos"])
    print(f"{de} -> {versao}: copiar {len(dif.copiar)}, remover {len(dif.remover)} "
          f"arquivo(s) e {len(dif.pastas_remover)} pasta(s); {fracao:.0%} do total.")
    for rel in dif.copiar[:40]:
        print(f"    + {rel}")
    if fracao > LIMITE_FRACAO:
        _aviso(f"{de} -> {versao}: o pequeno levaria {fracao:.0%} do total (limite "
               f"{LIMITE_FRACAO:.0%}); quem estiver na {de} recebe o completo.")
        return None

    pasta_iss = iss.parent
    gravar_include(pasta_iss / "atualizacao_arquivos.iss",
                   linhas_arquivos(dif, origens, pasta_iss), f"Arquivos de {de} para {versao}")
    gravar_include(pasta_iss / "atualizacao_remover.iss",
                   linhas_remover(dif), f"Remocoes de {de} para {versao}")

    cmd = [iscc, "/DAtualizacao=1", f"/DVersaoDe={de}", f"/DMyAppVersion={versao}",
           f"/DMyVersionInfo={versao_info}", str(iss)]
    r = subprocess.run(cmd)
    exe = pasta_saida / f"{nome_pequeno(de, versao)}.exe"
    if r.returncode != 0 or not exe.is_file():
        _aviso(f"{de} -> {versao}: o ISCC falhou (codigo {r.returncode}); "
               f"quem estiver na {de} recebe o completo.")
        return None
    return entrada_latest(de, exe, zipar(exe))


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
    entradas, gerados = [], []
    for arq in sorted(args.bases.glob("*.json")):
        try:
            base = json.loads(arq.read_text(encoding="utf-8-sig"))
            de = str(base.get("versao") or arq.stem).lstrip("vV")
        except (OSError, ValueError) as e:
            _aviso(f"{arq.name}: manifesto da base ilegivel ({e}); pulado.")
            continue
        entrada = gerar_pacote(de=de, base=base, nova=nova, origens=origens, iss=args.iss,
                               iscc=args.iscc, versao=args.versao,
                               versao_info=args.versao_info or args.versao.split("-")[0],
                               pasta_saida=args.saida)
        if entrada is None:
            continue
        entradas.append(entrada)
        gerados += [args.saida / entrada["zip"]["arquivo"], args.saida / entrada["arquivo"]]
        print(f"  -> {entrada['arquivo']}: {entrada['tamanho']} bytes")
    latest["atualizacoes"] = entradas
    _gravar_json(args.latest, latest)
    # Lista para o passo que publica, um caminho por linha, com "\n" puro.
    args.lista.write_bytes("".join(f"{p.as_posix()}\n" for p in gerados).encode("utf-8"))
    print(f"{len(entradas)} instalador(es) pequeno(s); latest.json atualizado.")


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
    p.add_argument("--versao", required=True)
    p.add_argument("--versao-info", default="")
    p.add_argument("--iss", type=Path, default=RAIZ / "installer" / "docmanager.iss")
    p.add_argument("--iscc", required=True)
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
