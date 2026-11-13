"""Página HTML do painel da Unidade Geradora (spec: `.scratch/painel-ug-html/spec.md`).

Um arquivo só, que abre com dois cliques em qualquer navegador, sem internet: o modelo
(`recursos/painel_ug.html`), as bibliotecas de gráfico (Chart.js e o plugin de rótulos,
licença MIT, cabeçalhos preservados) e os dados vão embutidos. Pode ser guardado no Box
e reaberto depois, ou enviado a quem não tem o DocManager.

Toda regra já vem calculada em `core/painel_ug.py`; aqui os dados só ganham a forma
compacta (listas em vez de dicionários) que o JavaScript do modelo lê. Os recursos ficam
ao lado deste módulo e entram no executável pelo `.spec` (`docmanager/dashboard/recursos`).
"""
from __future__ import annotations

import json
from pathlib import Path

RECURSOS = Path(__file__).resolve().parent / "recursos"
MODELO = "painel_ug.html"
BIBLIOTECAS = {"/*__CHARTJS__*/": "chart.umd.js", "/*__DATALABELS__*/": "chartjs-plugin-datalabels.min.js"}
_MARCADOR_DADOS = "/*__DADOS__*/"


def _sem_fim_de_script(texto: str) -> str:
    """"</script" dentro do conteúdo fecharia o <script> antes da hora."""
    return texto.replace("</script", "<\\/script").replace("</SCRIPT", "<\\/SCRIPT")


def compactar(dados: dict, meta: dict) -> dict:
    """Dados de `montar_dados_painel` na forma que o modelo lê (a ordem das listas é o
    contrato com o JavaScript: ver a leitura de `D.docs` em `painel_ug.html`)."""
    docs = []
    for d in dados["documentos"]:
        docs.append([
            d["codigo"], d["cmi"], d["codigo_atual"], d["descricao"], d["prevista"], d["reprogramada"],
            d["alvo"], d["primeira_emissao"], d["ultima_emissao"], d["revisao"], d["status_real"],
            d["status_bruto"], d["consolidado"], d["com"], d["situacao_emissao"], d["situacao_otd"],
            d["situacao_say_do"], int(bool(d["backlog"])), d["desvio"], int(bool(d["no_aconex"])),
            [list(x) for x in d["linha_do_tempo"]],
            [[r["revisao"], r["tipo"], r["envio"], r["retorno"], r["status_retorno"], r["dias_itaipu"],
              r["atraso_itaipu"], r["dias_cmi"], r["atraso_cmi"], r["sla"]] for r in d["revisoes"]],
            d["tracking"], d["achado_por"], int(d["ambiguo"]), int(d["codigo_vigente"]),
            int(d["aconex_sem_cmi"]), int(d["datas_divergentes"]),
            d["etapa_interna"], d["etapa_interna_desde"], [list(x) for x in d["fluxo_interno"]],
        ])
    assoc = [[a["doc"], a["grupo"], a["sistema"], a["fase"], a["responsavel"], a["escopo"],
              a["codigo_grupo"], a["linha"]] for a in dados["associacoes"]]
    grupos = [[g["codigo"], g["grupo"], g["sistema"], g["fase"], g["linha"], g["escopo"]] for g in dados["grupos"]]
    meta = {**meta, "hoje": dados["hoje"], "ultimoEvento": dados["ultimo_evento_aconex"]}
    return {"meta": meta, "docs": docs, "assoc": assoc, "grupos": grupos}


def renderizar(dados: dict, *, base: str, doc_list: str, aba: str, gerado_em: str, versao: str) -> str:
    """HTML completo do painel. `base`, `doc_list` e `aba` só identificam as fontes no
    cabeçalho da página; `gerado_em` já vem formatado (dd/mm/aaaa hh:mm)."""
    html = (RECURSOS / MODELO).read_text(encoding="utf-8")
    for marcador, arquivo in BIBLIOTECAS.items():
        html = html.replace(marcador, _sem_fim_de_script((RECURSOS / arquivo).read_text(encoding="utf-8")), 1)
    meta = {"base": base, "docList": doc_list, "aba": aba, "geradoEm": gerado_em, "versao": versao}
    payload = json.dumps(compactar(dados, meta), ensure_ascii=False, separators=(",", ":"))
    return html.replace(_MARCADOR_DADOS, _sem_fim_de_script(payload), 1)
