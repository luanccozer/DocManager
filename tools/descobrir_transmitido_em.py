"""Descoberta: o "Transmitido em" existe como campo do register do Aconex?

Read-only. Responde de forma definitiva a pergunta da seção 7 de
`docs/atualizacao_controle_documentos.md`:

  1) faz o dump do schema do register (`/register/schema`) — lista TODOS os campos
     disponíveis, para ver se há algum de transmittal;
  2) consulta o documento de teste e imprime TODOS os campos que voltam para cada
     revisão, destacando quem for igual ao transmittal esperado.

Precisa de rede corporativa (VPN/Zscaler) e do SECRET_<USUARIO> no .env. Não
altera nada no Aconex nem no repositório. Uso:

    python tools/descobrir_transmitido_em.py                 # usuário "Luan Cozer"
    python tools/descobrir_transmitido_em.py "Rafhael Martins"
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Ferramenta standalone: garante a raiz do repo no sys.path para achar 'docmanager'.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

# Reusa a autenticação/cascata de conexão já testadas do backend.
from docmanager.aconex_backend import AconexConfig, _estabelecer_sessao

DOC_TESTE = "#BA00=B04BMA10UC013-UC901&ELD020"
TRANSMITTAL_ESPERADO = "ITAIPU-WTR-023502"


def _log(msg=""):
    print(msg, flush=True)


def _tags_e_valores(elem) -> list[tuple[str, str]]:
    """(tag_local, texto) de todos os descendentes com texto — genérico, serve
    tanto para o schema quanto para o documento (não assumimos a forma do XML)."""
    out = []
    for e in elem.iter():
        tag = e.tag.split("}")[-1] if "}" in e.tag else e.tag
        txt = (e.text or "").strip()
        attrs = " ".join(f'{k.split("}")[-1]}={v!r}' for k, v in e.attrib.items())
        if txt or attrs:
            out.append((tag, txt or f"<attrs {attrs}>"))
    return out


def dump_schema(session, headers, base_url):
    _log("\n" + "=" * 72)
    _log("1) SCHEMA DO REGISTER  (/register/schema) — campos disponíveis")
    _log("=" * 72)
    url = f"{base_url}/schema"
    r = session.get(url, headers=headers, timeout=60)
    _log(f"GET {url}  ->  HTTP {r.status_code}")
    if r.status_code != 200:
        _log(r.text[:800])
        return
    root = ET.fromstring(r.content)
    campos = _tags_e_valores(root)
    _log(f"\n{len(campos)} elementos com conteúdo no schema:\n")
    for tag, val in campos:
        _log(f"  {tag:<34} {val}")
    # Pista rápida: algo com cara de transmittal/transmissão?
    suspeitos = [(t, v) for t, v in campos
                 if any(k in (t + v).lower() for k in ("transmit", "transmis", "mail", "wtr"))]
    _log("\n--- possíveis campos de transmittal no schema: "
         + (", ".join(f"{t}={v}" for t, v in suspeitos) if suspeitos else "NENHUM") + " ---")


def consultar_doc(session, headers, base_url):
    _log("\n" + "=" * 72)
    _log(f"2) DOCUMENTO DE TESTE  ({DOC_TESTE})  — todos os campos por revisão")
    _log(f"   transmittal esperado: {TRANSMITTAL_ESPERADO} (na revisão 0)")
    _log("=" * 72)
    # Pede um superset largo de campos (o register ignora/erra os inexistentes;
    # se algum trouxer o transmittal, aparece aqui). Sem restringir, tenta todos.
    params = {
        "search_query": DOC_TESTE, "search_type": "PAGED",
        "page_size": 50, "page_number": 1, "show_document_history": "true",
    }
    r = session.get(base_url, headers=headers, params=params, timeout=60)
    _log(f"GET {base_url}  (search_query={DOC_TESTE!r})  ->  HTTP {r.status_code}")
    if r.status_code != 200:
        _log(r.text[:800])
        return
    root = ET.fromstring(r.content)
    achou = False
    for d in root.iter():
        if "Document" in d.tag and "Documents" not in d.tag:
            campos = _tags_e_valores(d)
            if not campos:
                continue
            achou = True
            _log("\n--- documento ---")
            for tag, val in campos:
                marca = "   <<< TRANSMITTAL" if TRANSMITTAL_ESPERADO.lower() in val.lower() else ""
                _log(f"  {tag:<26} {val}{marca}")
    if not achou:
        _log("\n(nenhum documento retornou — a search_query pode não filtrar por "
             "docno; nesse caso rode a extração completa e filtre pelo código.)")
        _log("Amostra do XML devolvido:\n" + r.text[:600])


def probe_mail(session, headers, config):
    """Sondagem MÍNIMA da Mail API: a fonte real do 'Transmitido em' (transmittals)
    segundo a KB §24.5. Só verifica se o endpoint responde neste projeto e mostra a
    forma da resposta — não tenta ainda mapear doc→transmittal."""
    _log("\n" + "=" * 72)
    _log("3) SONDAGEM DA MAIL API  (fonte real do 'Transmitido em')")
    _log("=" * 72)
    inst, pid = config.instance, config.project_id
    tentativas = [
        ("mail schema", f"{inst}/api/projects/{pid}/mail/schema", {}),
        ("mail sent (25)", f"{inst}/api/projects/{pid}/mail",
         {"mail_box": "sent", "search_query": "", "search_type": "PAGED",
          "page_size": 25, "page_number": 1, "return_fields": "subject,sentDate,docno,transmittalNumber"}),
    ]
    for nome, url, params in tentativas:
        try:
            r = session.get(url, headers=headers, params=params, timeout=45)
            _log(f"\n[{nome}] GET {url}\n  params={params}\n  -> HTTP {r.status_code}")
            _log("  " + r.text[:700].replace("\n", "\n  "))
        except Exception as e:  # noqa: BLE001
            _log(f"\n[{nome}] ERRO: {e}")


def main():
    load_dotenv()
    usuario = sys.argv[1] if len(sys.argv) > 1 else "Luan Cozer"
    _log(f"Usuário: {usuario}")
    config = AconexConfig.para_usuario(usuario)
    session, token = _estabelecer_sessao(config, _log)
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/xml",
               "Accept-Encoding": "gzip, deflate"}
    base_url = f"{config.instance}/api/projects/{config.project_id}/register"
    dump_schema(session, headers, base_url)
    consultar_doc(session, headers, base_url)
    probe_mail(session, headers, config)
    _log("\nFim.")


if __name__ == "__main__":
    main()
