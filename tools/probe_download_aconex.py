"""Sonda: é possível BAIXAR o arquivo de um documento pela API do Aconex?

Read-only. Pega um documento real da página 1 do register (com o atributo
DocumentId e o filename) e testa os endpoints candidatos de download do arquivo
nativo/rendição, imprimindo status, content-type, tamanho e "magic bytes".
Precisa de rede corporativa + SECRET no .env. Não altera nada.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from docmanager.aconex_backend import AconexConfig, _estabelecer_sessao


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def main():
    load_dotenv()
    usuario = sys.argv[1] if len(sys.argv) > 1 else "Luan Cozer"
    config = AconexConfig.para_usuario(usuario)
    session, token = _estabelecer_sessao(config, print)
    auth = {"Authorization": f"Bearer {token}"}
    base = f"{config.instance}/api/projects/{config.project_id}/register"

    print("\n=== 1) varre páginas até achar códigos Itaipu reais (#... current) ===")
    docs = []
    reais = []
    for page in range(1, 6):
        params = {"search_query": "", "return_fields": "docno,current,filename,fileType,versionnumber",
                  "search_type": "PAGED", "page_size": 500, "page_number": page,
                  "sort_field": "docno", "sort_direction": "ASC"}
        r = session.get(base, headers={**auth, "Accept": "application/xml"}, params=params, timeout=90)
        root = ET.fromstring(r.content)
        for d in root.iter():
            if _local(d.tag) == "Document":
                did = d.attrib.get("DocumentId") or d.attrib.get("documentId")
                info = {_local(c.tag): (c.text or "") for c in d}
                if did:
                    docs.append((did, info))
                    dn = (info.get("DocumentNumber") or "").strip()
                    if dn.startswith("#") and (info.get("Current", "").lower() == "true"):
                        reais.append((did, info))
        print(f"  página {page}: acumulado {len(docs)} docs, {len(reais)} com '#...' current")
        if len(reais) >= 3:
            break
    if not docs:
        print("Nenhum documento. Amostra:\n", r.text[:800])
        return

    alvo = next((x for x in docs if x[1].get("Filename")), docs[0])
    did, info = alvo
    print(f"\nalvo p/ download -> DocumentId={did}  docno={info.get('DocumentNumber')!r}  "
          f"filename={info.get('Filename')!r}")

    print("\n=== 2) códigos Itaipu reais achados ===")
    for d, i in reais[:5]:
        print(f"  DocumentId={d}  docno={i.get('DocumentNumber')!r}  current={i.get('Current')!r}")
    docno_teste = (reais[0][1].get("DocumentNumber") if reais else "").strip() or "#ST00=B01MSE00&ED010"

    print(f"\n=== 3) variantes de search_query para o docno {docno_teste!r} ===")
    variantes = [
        ("cru", docno_teste),
        ("docno:", f"docno:{docno_teste}"),
        ("aspas", f'"{docno_teste}"'),
        ("docno:aspas", f'docno:"{docno_teste}"'),
    ]
    for nome, q in variantes:
        params = {"search_query": q, "return_fields": "docno,current", "search_type": "PAGED",
                  "page_size": 25, "page_number": 1}
        try:
            rr = session.get(base, headers={**auth, "Accept": "application/xml"}, params=params, timeout=60)
            root2 = ET.fromstring(rr.content)
            total = root2.attrib.get("TotalResults", "?")
            print(f"  [{nome:12}] q={q!r} -> HTTP {rr.status_code}, TotalResults={total}")
        except Exception as e:  # noqa: BLE001
            print(f"  [{nome:12}] ERRO: {e}")
    print("\nFim.")


if __name__ == "__main__":
    main()
