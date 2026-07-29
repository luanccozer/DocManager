"""Sonda a Mail API do Aconex para o "Transmitido em" — foco em CUSTO de tempo.

Read-only. Responde: (1) qual `mail_box` é válido; (2) quantos transmittals
existem (define o custo da paginação); (3) se o registro de cada mail já traz os
documentos anexados INLINE (barato) ou exige um GET por mail (caro). Isso decide
se dá para enriquecer a extração sem aumentar o tempo.
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
    auth = {"Authorization": f"Bearer {token}", "Accept": "application/xml"}
    mail = f"{config.instance}/api/projects/{config.project_id}/mail"

    print("\n=== 1) SCHEMA da Mail API (return_fields e mail types) ===")
    r = session.get(f"{mail}/schema", headers=auth, timeout=60)
    print(f"GET {mail}/schema -> HTTP {r.status_code}")
    if r.status_code == 200:
        root = ET.fromstring(r.content)
        ids = [_local(e.tag) + "=" + (e.text or "") for e in root.iter()
               if _local(e.tag) in ("Identifier", "FieldName")]
        print("  campos:", ", ".join(ids[:80]))
        # procura algo de "attached documents" / docs
        susp = [x for x in ids if any(k in x.lower() for k in ("doc", "attach", "anex"))]
        print("  suspeitos (documentos/anexos):", susp or "NENHUM no schema de criação")

    print("\n=== 2) mail_box válido + TotalResults (custo de paginação) ===")
    rf = "subject,docno,sentdate,attachedDocumentCount,hasAttachments,corrtypeid"
    caixa_ok = None
    for box in ("SENTBOX", "INBOX"):
        params = {"mail_box": box, "search_query": "", "search_type": "PAGED",
                  "page_size": 25, "page_number": 1, "return_fields": rf}
        rr = session.get(mail, headers=auth, params=params, timeout=45)
        code = rr.status_code
        if code == 200:
            total = ET.fromstring(rr.content).attrib.get("TotalResults", "?")
            if caixa_ok is None and box == "SENTBOX":
                caixa_ok = box
            print(f"  mail_box={box:8} -> HTTP 200, TotalResults={total}")
        else:
            print(f"  mail_box={box:8} -> HTTP {code}  {rr.text[:140]}")

    if not caixa_ok:
        print("\nNenhuma caixa válida encontrada. Fim.")
        return

    print(f"\n=== 3) 1ª página de {caixa_ok}: campos de UM mail (tem docnos inline?) ===")
    params = {"mail_box": caixa_ok, "search_query": "", "search_type": "PAGED",
              "page_size": 25, "page_number": 1, "return_fields": rf}
    rr = session.get(mail, headers=auth, params=params, timeout=60)
    root = ET.fromstring(rr.content)
    mails = [e for e in root.iter() if _local(e.tag) == "Mail"]
    print(f"  mails na página: {len(mails)}")
    if mails:
        m = mails[0]
        mail_id = m.attrib.get("MailId") or m.attrib.get("mailId") or dict(m.attrib)
        print(f"  1º mail attrs: {dict(m.attrib)}")
        for c in m:
            print(f"    <{_local(c.tag)}> = {(c.text or '')[:80]!r}"
                  + (f"  [filhos: {[_local(x.tag) for x in c][:6]}]" if len(list(c)) else ""))
        # 4) detalhe do mail: lista documentos anexados?
        mid = m.attrib.get("MailId") or m.attrib.get("mailId")
        if mid:
            print(f"\n=== 4) GET /mail/{mid} — lista documentos anexados? ===")
            rd = session.get(f"{mail}/{mid}", headers=auth, timeout=60)
            print(f"  HTTP {rd.status_code}")
            if rd.status_code == 200:
                rootd = ET.fromstring(rd.content)
                tags = {}
                for e in rootd.iter():
                    tags[_local(e.tag)] = tags.get(_local(e.tag), 0) + 1
                print("  tags no detalhe:", dict(sorted(tags.items())))
                docs = [e for e in rootd.iter() if _local(e.tag) in ("Document", "RegisteredDocument")]
                print(f"  documentos anexados encontrados: {len(docs)}")
                if docs:
                    d0 = docs[0]
                    print(f"    ex.: attrs={dict(d0.attrib)}  filhos={[(_local(c.tag), (c.text or '')[:40]) for c in d0][:6]}")
    print("\nFim.")


if __name__ == "__main__":
    main()
