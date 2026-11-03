"""Upload de documentos → Para aprovação: a parte que não grava nada (Fase 1).

Confere o código CMI no arquivo de envio (link do Box) e no Controle de Documentos
(a última revisão emitida precisa ser 0C; senão, a pessoa decide se segue), acha o
documento no Aconex pela API (busca exata pelo código, a mesma da consulta rápida) e
devolve o resumo do que o robô vai fazer.

A gravação (Box, nova revisão, workflow, impressão) é a Fase 2 e depende do mapeamento
das telas (spec `.scratch/upload-aprovacao/spec.md`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .controle_docs import chave_codigo, ler_controle
from .upload_envio import ErroEnvio, LinhaEnvio, buscar, ler_envio

REVISAO_ESPERADA = "0C"
REVISAO_NOVA = "0"
STATUS_NOVO = "Para Aprovação"


@dataclass
class Preparacao:
    ok: bool
    mensagem: str
    codigo: str = ""
    envio: LinhaEnvio | None = None
    ultima_revisao: str = ""
    documento: dict = field(default_factory=dict)
    prazo_dias: int = 0

    def resumo(self) -> str:
        d = self.documento
        return "\n".join([
            f"Código CMI: {self.codigo}",
            f"Documento no Aconex: {d.get('No. do Documento', '?')} (revisão atual "
            f"{d.get('Revisão', '?')}, {d.get('Status da Revisão', '?')})",
            f"Título: {d.get('Título', '')}",
            f"Pasta do Box: {self.envio.link if self.envio else ''}",
            f"Vai subir: revisão {REVISAO_NOVA}, status \"{STATUS_NOVO}\", com o PDF e o editável "
            "da pasta do Box",
            "Workflow: o mesmo modelo do último fluxo do documento, prazo de "
            f"{self.prazo_dias} dia(s)",
            "No fim: imprimir a tela do workflow como PDF e subir na pasta do Box.",
        ])


def preparar_aprovacao(config, caminho_envio, caminho_controle, codigo: str, prazo_dias: int, *,
                       aba_controle=0, log_cb=print, perguntar_cb=None,
                       consultar=None) -> Preparacao:
    """Confere tudo o que dá para conferir sem gravar. `perguntar_cb(mensagem) -> bool`
    decide se segue quando a revisão não é 0C; `consultar` é a busca no Aconex
    (padrão: `aconex_backend.consultar_codigos`)."""
    codigo = (codigo or "").strip()
    if not codigo:
        return Preparacao(False, "Nenhum código CMI informado.")
    if not prazo_dias or prazo_dias <= 0:
        return Preparacao(False, "Informe o prazo do workflow em dias.")
    r = Preparacao(False, "", codigo=codigo, prazo_dias=prazo_dias)

    try:
        linha = buscar(ler_envio(caminho_envio), codigo)
    except ErroEnvio as e:
        r.mensagem = str(e)
        return r
    if linha is None:
        r.mensagem = f"O código {codigo} não está no arquivo de envio."
        return r
    if not linha.link:
        r.mensagem = f"O código {codigo} está no arquivo de envio, mas a coluna LINK não tem o link do Box."
        return r
    r.envio = linha
    log_cb(f"Arquivo de envio: {codigo} → {linha.cod_itaipu or '(sem código Itaipu)'}; link do Box ok.")

    controle = ler_controle(caminho_controle, aba_controle, log_cb=log_cb)
    linha_ctrl = controle.linha_por_codigo(codigo)
    r.ultima_revisao = linha_ctrl.ultima_revisao if linha_ctrl else ""
    if linha_ctrl is None:
        aviso = f"O código {codigo} não está no Controle de Documentos."
    elif chave_codigo(r.ultima_revisao) != REVISAO_ESPERADA:
        aviso = (f"No Controle de Documentos, a última revisão emitida de {codigo} é "
                 f"'{r.ultima_revisao or '(vazia)'}', e não {REVISAO_ESPERADA}.")
    else:
        aviso = ""
    if aviso:
        log_cb(aviso)
        if not (perguntar_cb and perguntar_cb(f"{aviso}\n\nContinuar mesmo assim?")):
            r.mensagem = f"{aviso} Envio cancelado."
            return r
        log_cb("Continuando por decisão do usuário.")
    else:
        log_cb(f"Controle de Documentos: {codigo} está em {REVISAO_ESPERADA}.")

    if consultar is None:
        from ..aconex_backend import consultar_codigos as consultar
    res = consultar(config, [codigo], log_cb=log_cb)
    if res.erros:
        r.mensagem = f"A busca no Aconex falhou: {res.erros[0][1]}"
        return r
    base = res.base
    if base is None or base.empty or "Controle do Emissor" not in base.columns:
        r.mensagem = f"O documento {codigo} não foi encontrado no Aconex."
        return r
    do_codigo = base[base["Controle do Emissor"].map(chave_codigo) == chave_codigo(codigo)]
    if do_codigo.empty:
        r.mensagem = f"Nenhum documento do Aconex tem {codigo} no Controle do Emissor."
        return r
    numeros = sorted(set(do_codigo["No. do Documento"]))
    if len(numeros) > 1:
        r.mensagem = (f"Mais de um documento do Aconex tem {codigo} no Controle do Emissor: "
                      f"{', '.join(numeros)}. Confira no Aconex antes de enviar.")
        return r
    atuais = do_codigo[do_codigo["Current"].astype(str).str.strip().str.lower() == "true"] \
        if "Current" in do_codigo.columns else do_codigo
    vigente = (atuais if not atuais.empty else do_codigo).iloc[-1]
    r.documento = {k: str(vigente.get(k, "")) for k in
                   ("No. do Documento", "Título", "Revisão", "Status da Revisão", "Versão")}
    log_cb(f"Aconex: {r.documento['No. do Documento']} na revisão {r.documento['Revisão']} "
           f"({r.documento['Status da Revisão']}).")
    r.ok = True
    r.mensagem = r.resumo()
    return r
