"""Atualizar a planilha de mapeamento de pendências direto do Aconex (KB §32).

A pessoa escolhe a planilha; o app busca as Questões do Campo e grava, sem
pergunta final:

- as pendências novas entram no TOPO da tabela, em ordem decrescente, com a
  formatação das outras (D2);
- nas que já estão, as colunas do Aconex são atualizadas; as manuais nunca (D1);
- valor que o Aconex perdeu só é apagado se a pessoa decidir, e o que ela
  mantém fica lembrado em `pendencias_mantidas.json` (D6, C10);
- impeditiva não fechada fica com a cor da legenda, e perde a cor quando deixa
  de ser - só o preenchimento muda, nunca fonte, borda ou altura (D5);
- tudo ou nada: qualquer falha (API, recusa, conferência) não grava (C2), e a
  troca do arquivo passa pela substituição segura, com cópia de segurança.

Nenhum número de estilo é fixo: o fill de destaque, os modelos de linha e de
célula saem dos dados da própria planilha (8.4 da spec).
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from ..core.normalize import normalizar_cabecalho
from . import gravacao
from . import xlsx_cirurgico as xc
from .credenciais import pasta_dados
from .sobrescricao import DecisaoSobrescricao

CHAVE = "Issue Number"
COLUNA_CLASSIFICACAO = "Clasificación de pendencia"
COLUNA_STATUS = "Status"
COLUNA_COMENTARIOS = "Comments"
IMPEDITIVA = "Impeditiva"
FECHADA = "Closed"
ARQUIVO_MANTIDAS = "pendencias_mantidas.json"
AZUL = "FF0070C0"       # o que a última atualização trouxe
VERMELHO = "FFFF0000"   # impeditiva não fechada
PRETO = "FF000000"
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class Apagamento:
    """Uma célula com valor na planilha que está vazia no Aconex (D6)."""
    linha: int
    numero: int
    col: int
    titulo_coluna: str
    valor_planilha: object
    descricao: str
    valor_novo: str = "(vazio)"

    @property
    def codigo(self) -> str:
        return str(self.numero)


@dataclass
class ResultadoPendencias:
    ok: bool
    mensagem: str
    novas: list[int] = field(default_factory=list)
    novas_destacadas: int = 0
    atualizadas: Counter = field(default_factory=Counter)
    preenchidas: int = 0
    apagadas: int = 0
    mantidas: int = 0
    ganharam_cor: int = 0
    perderam_cor: int = 0
    so_na_planilha: list[int] = field(default_factory=list)
    backup: str = ""
    gravou: bool = False


class _Recusa(Exception):
    def __init__(self, motivo: str, *, ja_no_log: bool = False):
        super().__init__(motivo)
        self.ja_no_log = ja_no_log


# --- Comparação ----------------------------------------------------------------------

def _numero(v) -> int | None:
    """O Issue Number como inteiro, esteja a célula como número (131 ou 131.0) ou
    como texto ("131") - a planilha real tem dos dois jeitos."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, int):
        return v
    texto = str(v).strip()
    return int(texto) if texto.isdigit() else None


def _texto(v) -> str:
    """O valor como texto comparável: vazio = None, espaços colapsados, data = AAAA-MM-DD."""
    if v is None:
        return ""
    if isinstance(v, datetime):
        v = v.date()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return re.sub(r"\s+", " ", str(v)).strip()


def _para_gravar(atual, novo):
    """Data segue a célula (C8): se a atual é data real, a nova também vai como data."""
    if isinstance(atual, date) and isinstance(novo, str) and _ISO.match(novo.strip()):
        return date.fromisoformat(novo.strip())
    return novo


def _destacada(valores: dict[int, object], col_classif: int, col_status: int) -> bool:
    return (_texto(valores.get(col_classif)) == IMPEDITIVA
            and _texto(valores.get(col_status)) != FECHADA)


# --- Memória das recusas (C10) ----------------------------------------------------------

def _arquivo_mantidas():
    return pasta_dados() / ARQUIVO_MANTIDAS


def _chave_mantida(numero: int, titulo: str, valor) -> tuple:
    return (int(numero), normalizar_cabecalho(titulo), _texto(valor))


def _ler_mantidas() -> set[tuple]:
    try:
        dados = json.loads(_arquivo_mantidas().read_text(encoding="utf-8"))
        return {_chave_mantida(d["numero"], d["coluna"], d["valor"]) for d in dados.get("mantidas", [])}
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def _gravar_mantidas(itens: list[Apagamento]) -> None:
    dados = {"mantidas": [{"numero": a.numero, "coluna": a.titulo_coluna, "valor": _texto(a.valor_planilha)}
                          for a in itens]}
    try:
        _arquivo_mantidas().write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass   # perder a memória só faz a pergunta voltar


# --- Estilos descobertos pelos dados (8.4) ---------------------------------------------------

@dataclass
class _Modelos:
    fill_destaque: str | None
    fill_normal: dict[int, str]
    abertura: dict[bool, str]
    s_linha: dict[bool, str | None]
    s_celula: dict[bool, dict[int, str | None]]


def _modelo_de_abertura(linhas: list[xc.Linha], s: str | None) -> str:
    sem_r = [re.sub(r'(\sr=")\d+(")', r"\g<1>0\g<2>", x.abertura, count=1) for x in linhas]
    abertura = xc.mais_comum(sem_r)
    if s is not None:
        abertura = xc._trocar_attr(abertura, "s", s)
    return abertura


def _descobrir_modelos(pasta: xc.Pasta, corpo: list[xc.Linha], destacadas: set[int], log) -> _Modelos:
    tb, est = pasta.tabela, pasta.estilos
    grupos = {True: [x for x in corpo if x.r in destacadas], False: [x for x in corpo if x.r not in destacadas]}
    cols = range(tb.col_ini, tb.col_fim + 1)
    fill_destaque = None
    if grupos[True]:
        fill_destaque = xc.mais_comum([est.fill(x.celulas[tb.col_ini].s) for x in grupos[True]
                                       if tb.col_ini in x.celulas])
    fill_normal = {c: xc.mais_comum([est.fill(x.celulas[c].s) for x in grupos[False] if c in x.celulas])
                   for c in cols}
    abertura, s_linha, s_celula = {}, {}, {}
    for g in (True, False):
        linhas = grupos[g] or grupos[not g]
        s_linha[g] = xc.mais_comum([x.s for x in linhas])
        abertura[g] = _modelo_de_abertura(linhas, s_linha[g])
        s_celula[g] = {c: xc.mais_comum([x.celulas[c].s for x in linhas if c in x.celulas]) for c in cols}
    if not grupos[False]:
        log("A planilha não tem nenhuma linha sem destaque: as novas usam o modelo das destacadas.")
    return _Modelos(fill_destaque, fill_normal, abertura, s_linha, s_celula)


# --- O serviço ----------------------------------------------------------------------------------

def atualizar_pendencias(config, caminho, *, log_cb=print, progress_cb=None, retry_cb=None,
                         decidir_cb=None) -> ResultadoPendencias:
    """Atualiza a planilha de pendências em `caminho` com as Questões do Aconex.

    `decidir_cb(apagamentos) -> DecisaoSobrescricao | None` é a tela do D6
    (aceitar = apagar; None = janela fechada: mantém tudo sem memorizar).
    `retry_cb(mensagem) -> bool` é o "Tentar de novo?" quando o Windows recusa
    a troca do arquivo.
    """
    log = log_cb or (lambda _m: None)
    progresso = progress_cb or (lambda _f: None)
    try:
        return _atualizar(config, caminho, log, progresso, retry_cb, decidir_cb)
    except _Recusa as e:
        if not e.ja_no_log:
            log(f"Nada foi gravado: {e}")
        return ResultadoPendencias(False, f"A planilha não foi alterada.\n{e}")


def _atualizar(config, caminho, log, progresso, retry_cb, decidir_cb) -> ResultadoPendencias:
    from .. import field_backend as fb

    progresso(0.02)
    try:
        assinatura = gravacao.assinatura_de(caminho)
        pasta = xc.ler(caminho, CHAVE)
    except OSError as e:
        raise _Recusa(f"Não foi possível abrir a planilha ({e}).") from e
    except xc.ErroXlsx as e:
        raise _Recusa(f"A planilha não serve para a atualização: {e}") from e
    if (problemas := xc.recusas(pasta, CHAVE)):
        raise _Recusa("Para não arriscar a planilha, nada foi gravado. Encontrado:\n- "
                      + "\n- ".join(problemas))
    tb = pasta.tabela
    log(f"Tabela '{tb.nome}' na aba '{pasta.aba_nome}' ({tb.ref}): "
        f"{tb.ultima - tb.cabecalho} pendências na planilha.")

    col_comentarios = tb.coluna(COLUNA_COMENTARIOS)
    try:
        ext = fb.extrair_questoes(config, log_cb=log, com_comentarios=col_comentarios is not None,
                                  progress_cb=lambda f: progresso(0.05 + 0.75 * f))
    except Exception as e:  # noqa: BLE001 - tudo ou nada: qualquer falha da API não grava
        raise _Recusa(f"A busca no Aconex não terminou ({e}).") from e

    # Colunas do Aconex × manuais (C7), pelo nome.
    rotulos = fb.rotulos_dos_campos_das_questoes(ext.tipos, ext.questoes)
    do_aconex = {normalizar_cabecalho(n) for n in (*fb.COLUNAS_PADRAO, *rotulos)}
    sem_fonte = {normalizar_cabecalho(n) for n in fb.COLUNAS_SEM_FONTE}
    titulos = {tb.col_ini + i: n for i, n in enumerate(tb.colunas)}
    cols_aconex = {c: normalizar_cabecalho(n) for c, n in titulos.items()
                   if normalizar_cabecalho(n) in do_aconex and normalizar_cabecalho(n) not in sem_fonte}
    repetidas = [n for n, q in Counter(cols_aconex.values()).items() if q > 1]
    if repetidas:
        raise _Recusa(f"A coluna do Aconex '{repetidas[0]}' aparece mais de uma vez na tabela.")
    col_chave = tb.coluna(CHAVE)
    col_classif, col_status = tb.coluna(COLUNA_CLASSIFICACAO), tb.coluna(COLUNA_STATUS)

    # Valores do Aconex por pendência, já pela coluna da planilha.
    avisos: list[str] = []
    defs = fb.definicoes_por_chave(ext.definicoes)
    api: dict[int, dict[int, object]] = {}
    sem_coluna: set[str] = set()
    for q in ext.questoes:
        comentarios = None
        if col_comentarios is not None:
            comentarios = fb.formatar_comentarios(ext.comentarios_por_issue.get(str(q.get("issue_id")), []))
        valores = fb.valores_da_questao(q, defs, comentarios, avisar=avisos.append)
        numero = valores.get(CHAVE)
        if not isinstance(numero, int) or numero <= 0:
            log(f"Questão sem número válido ignorada: {q.get('issue_id')}")
            continue
        por_nome = {normalizar_cabecalho(k): v for k, v in valores.items()}
        sem_coluna |= {k for k in valores if normalizar_cabecalho(k) in
                       {normalizar_cabecalho(r) for r in rotulos} - set(cols_aconex.values())}
        api[numero] = {c: (xc.limpar_texto(v, avisos.append) if isinstance(v, str) else v)
                       for c, nome in cols_aconex.items() for v in [por_nome.get(nome, "")]}
    for aviso in dict.fromkeys(avisos):
        log(f"Atenção: {aviso}")
    if sem_coluna:
        log(f"Campos do Aconex sem coluna na planilha (ignorados): {', '.join(sorted(sem_coluna))}.")

    corpo = pasta.corpo()
    planilha = {_numero(x.celulas[col_chave].valor): x for x in corpo}
    novas = sorted(set(api) - set(planilha), reverse=True)
    so_na_planilha = sorted(set(planilha) - set(api), reverse=True)
    r = ResultadoPendencias(True, "", novas=novas, so_na_planilha=so_na_planilha)
    if so_na_planilha:
        log(f"{len(so_na_planilha)} pendência(s) da planilha não existem mais no Aconex e ficaram "
            f"como estão: {', '.join(map(str, so_na_planilha[:20]))}"
            + (" …" if len(so_na_planilha) > 20 else ""))

    # 8.3: trocas, preenchimentos e apagamentos nas existentes.
    edicao = xc.Edicao()
    finais: dict[int, dict[int, object]] = {}       # linha → coluna → valor final (texto)
    apagamentos: list[Apagamento] = []
    for numero, linha in planilha.items():
        atuais = {c: (linha.celulas[c].valor if c in linha.celulas else None) for c in titulos}
        finais[linha.r] = dict(atuais)
        if numero not in api:
            continue
        for c in cols_aconex:
            if c == col_chave:
                continue
            atual, novo = atuais[c], api[numero][c]
            if _texto(atual) == _texto(novo):
                continue
            if _texto(novo):
                s = linha.celulas[c].s if c in linha.celulas else linha.s
                edicao.celulas[(linha.r, c)] = (_para_gravar(atual, novo), s)
                finais[linha.r][c] = novo
                if _texto(atual):
                    r.atualizadas[titulos[c]] += 1
                else:
                    r.preenchidas += 1
            else:
                descricao = _texto(atuais.get(tb.coluna("Issue Description")))
                apagamentos.append(Apagamento(linha.r, numero, c, titulos[c], atual, descricao))

    # D6: o que o Aconex perdeu só se apaga com decisão.
    memoria = _ler_mantidas()
    ja_mantidas = [a for a in apagamentos if _chave_mantida(a.numero, a.titulo_coluna, a.valor_planilha) in memoria]
    pendentes = [a for a in apagamentos if a not in ja_mantidas]
    apagar: list[Apagamento] = []
    manter_e_lembrar: list[Apagamento] = list(ja_mantidas)
    r.mantidas = len(ja_mantidas)
    if ja_mantidas:
        log(f"{len(ja_mantidas)} valor(es) que o Aconex não tem mais ficaram, como decidido antes.")
    if pendentes:
        decisao = decidir_cb(pendentes) if decidir_cb else None
        if decisao is None:
            log(f"{len(pendentes)} valor(es) que o Aconex não tem mais ficaram como estão (sem decisão).")
            decisao = DecisaoSobrescricao()
        for i, a in enumerate(pendentes):
            if i in decisao.aceitas:
                apagar.append(a)
            else:
                r.mantidas += 1
                if i in decisao.recusadas:
                    manter_e_lembrar.append(a)
    for a in apagar:
        s = planilha[a.numero].celulas[a.col].s
        edicao.celulas[(a.linha, a.col)] = ("", s)
        finais[a.linha][a.col] = ""
    r.apagadas = len(apagar)

    # Cores (pedido da equipe, 2026-11-02): o texto é que leva a cor, sem preenchimento.
    # - impeditiva não fechada: o texto da linha inteira em VERMELHO (D5);
    # - o que ESTA atualização trouxe (linha nova, célula trocada ou preenchida): AZUL;
    # - o azul (e o vermelho que deixou de valer) das execuções anteriores volta a PRETO.
    # O vermelho prevalece sobre o azul. O preenchimento laranja de antes sai das
    # linhas que o tinham e da legenda.
    regra = col_classif is not None and col_status is not None
    if not regra:
        log(f"A tabela não tem as colunas '{COLUNA_CLASSIFICACAO}' e '{COLUNA_STATUS}': "
            "o vermelho das impeditivas não foi aplicado.")
    destacadas_hoje_regra = {x.r for x in corpo if regra and _destacada(
        {c: (x.celulas[c].valor if c in x.celulas else None) for c in titulos}, col_classif, col_status)}
    modelos = _descobrir_modelos(pasta, corpo, destacadas_hoje_regra, log)
    est = pasta.estilos
    fill_antigo = modelos.fill_destaque
    if fill_antigo is not None and fill_antigo == modelos.fill_normal.get(tb.col_ini):
        fill_antigo = None   # já não há preenchimento de destaque para tirar
    mudadas = {k for k, (v, _s) in edicao.celulas.items() if _texto(v)}
    ha_novidade = bool(novas or mudadas)

    def fill_normal(c):
        f = modelos.fill_normal.get(c)
        return "0" if f is None or f == fill_antigo else f

    for x in corpo:
        depois = regra and _destacada(finais[x.r], col_classif, col_status)
        cel_a = x.celulas.get(tb.col_ini)
        tinha_fill = fill_antigo is not None and cel_a is not None and est.fill(cel_a.s) == fill_antigo
        era_vermelha = tinha_fill or (cel_a is not None and est.cor_do_texto(cel_a.s) == VERMELHO)
        for c, cel in x.celulas.items():
            if c not in titulos:
                continue
            fill = fill_normal(c) if tinha_fill and est.fill(cel.s) == fill_antigo else None
            atual = est.cor_do_texto(cel.s)
            if depois:
                cor = VERMELHO
            elif (x.r, c) in mudadas:
                cor = AZUL
            elif atual == VERMELHO or (ha_novidade and atual == AZUL):
                cor = PRETO   # o azul só sai quando há um lote novo para marcar
            else:
                cor = None
            novo_s = est.com(cel.s, fill=fill, cor_texto=cor)
            if novo_s != (cel.s or "0"):
                valor, _s = edicao.celulas.get((x.r, c), (xc.MANTER, cel.s))
                edicao.celulas[(x.r, c)] = (valor, novo_s)
        if tinha_fill and est.fill(x.s) == fill_antigo and modelos.s_linha[False] is not None:
            edicao.estilo_linha[x.r] = (modelos.s_linha[False]
                                        if est.fill(modelos.s_linha[False]) != fill_antigo
                                        else est.com(x.s, fill=fill_normal(tb.col_ini)))
        if depois and not era_vermelha:
            r.ganharam_cor += 1
        elif era_vermelha and not depois:
            r.perderam_cor += 1

    # A legenda (acima da tabela): o quadrado laranja perde o preenchimento e o texto
    # ao lado dele fica vermelho, como as linhas que ele explica.
    if fill_antigo is not None:
        for linha in pasta.linhas:
            if linha.r >= tb.cabecalho:
                continue
            for c, cel in sorted(linha.celulas.items()):
                if est.fill(cel.s) != fill_antigo:
                    continue
                edicao.celulas[(linha.r, c)] = (xc.MANTER, est.com(cel.s, fill="0"))
                texto = next((t for cc, t in sorted(linha.celulas.items()) if cc > c and _texto(t.valor)), None)
                if texto is not None:
                    edicao.celulas[(linha.r, texto.col)] = (xc.MANTER, est.com(texto.s, cor_texto=VERMELHO))

    # Novas no topo (D2), com o modelo das linhas normais; o texto em azul (ou vermelho).
    for numero in novas:
        valores = api[numero]
        destacada = regra and _destacada(valores, col_classif, col_status)
        r.novas_destacadas += destacada
        linha_nova = []
        for c in titulos:
            v = valores.get(c, "") if c in cols_aconex else ""
            s_modelo = modelos.s_celula[False].get(c)
            fill = fill_normal(c) if fill_antigo is not None and est.fill(s_modelo) == fill_antigo else None
            cor = VERMELHO if destacada else (AZUL if _texto(v) else None)
            s_final = est.com(s_modelo, fill=fill, cor_texto=cor) if (fill or cor) else s_modelo
            linha_nova.append((v, s_final))
        abertura = modelos.abertura[False]
        if fill_antigo is not None and est.fill(xc._attrs(abertura).get("s")) == fill_antigo:
            abertura = xc._trocar_attr(abertura, "s", est.com(xc._attrs(abertura).get("s"),
                                                               fill=fill_normal(tb.col_ini)))
        edicao.novas.append(xc.LinhaNova(abertura, linha_nova))

    progresso(0.85)
    if not (edicao.novas or edicao.celulas or edicao.estilo_linha):
        _gravar_mantidas(manter_e_lembrar)
        r.mensagem = "A planilha já está atualizada; nada foi gravado."
        log(r.mensagem)
        progresso(1.0)
        return r

    alteradas = xc.aplicar(pasta, edicao, avisar=log)
    esperado = _Esperado(pasta, edicao, novas, finais, cols_aconex, titulos, set(planilha))
    info: dict = {}
    erro = gravacao.substituir_com_seguranca(
        caminho, lambda tmp: xc.gravar_zip(pasta, alteradas, tmp),
        validar=lambda tmp: validar(tmp, pasta, alteradas, esperado),
        assinatura=assinatura, retry_cb=retry_cb, log_cb=log, info=info)
    if erro is not None:
        raise _Recusa(erro, ja_no_log=True)   # a substituição segura já o escreveu
    _gravar_mantidas(manter_e_lembrar)
    r.gravou = True
    r.backup = str(info.get("backup") or "")
    r.mensagem = _mensagem(r)
    log(r.mensagem)
    progresso(1.0)
    return r


def _mensagem(r: ResultadoPendencias) -> str:
    linhas = ["Planilha de pendências atualizada."]
    if r.novas:
        faixa = f"nº {r.novas[-1]} a {r.novas[0]}" if len(r.novas) > 1 else f"nº {r.novas[0]}"
        linhas.append(f"{len(r.novas)} pendência(s) nova(s) no topo ({faixa})"
                      + (f"; {r.novas_destacadas} delas impeditivas abertas, com a cor da legenda."
                         if r.novas_destacadas else "."))
    else:
        linhas.append("Nenhuma pendência nova.")
    detalhe = "; ".join(f"{k}: {v}" for k, v in r.atualizadas.most_common())
    total = sum(r.atualizadas.values())
    linhas.append(f"Atualizadas: {total} célula(s)" + (f" ({detalhe})" if detalhe else "")
                  + f". Preenchidas: {r.preenchidas}. Apagadas: {r.apagadas}. Mantidas: {r.mantidas}.")
    if r.ganharam_cor:
        linhas.append(f"{r.ganharam_cor} linha(s) ganharam a cor (ficaram impeditivas abertas).")
    if r.perderam_cor:
        linhas.append(f"{r.perderam_cor} linha(s) perderam a cor (fecharam ou deixaram de ser impeditivas).")
    if r.so_na_planilha:
        linhas.append(f"{len(r.so_na_planilha)} pendência(s) da planilha não estão mais no Aconex "
                      "e ficaram como estavam.")
    else:
        linhas.append("Nenhuma pendência da planilha sumiu do Aconex.")
    if r.backup:
        linhas.append(f"Cópia de segurança: {r.backup}")
    linhas.append("Abra no Excel para as tabelas dinâmicas e os gráficos se atualizarem.")
    return "\n".join(linhas)


# --- Validador (seção 13 da spec) ---------------------------------------------------------------

@dataclass
class _Esperado:
    pasta: xc.Pasta
    edicao: xc.Edicao
    novas: list[int]
    finais: dict[int, dict[int, object]]
    cols_aconex: dict[int, str]
    titulos: dict[int, str]
    existentes: set[int]


def _declaracao_e_raiz(texto: str) -> tuple:
    """A declaração XML, o nome da raiz e os namespaces dela (com o `mc:Ignorable`).

    É o que o ElementTree estragaria ao reserializar; o `ref` da raiz da tabela
    muda de propósito e fica de fora."""
    m = re.match(r"\s*(<\?xml[^>]*\?>)?\s*<([^\s!?/>]+)([^>]*)>", texto)
    if not m:
        return ()
    ns = sorted(re.findall(r'\s((?:xmlns(?::[\w.-]+)?|mc:Ignorable)="[^"]*")', m.group(3)))
    return m.group(1) or "", m.group(2), tuple(ns)


def validar(tmp, pasta: xc.Pasta, alteradas: dict[str, bytes], esp: _Esperado) -> list[str]:
    """Confere o arquivo novo contra o original e o plano. Lista vazia = ok."""
    problemas: list[str] = []
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:
            return ["o zip novo está corrompido"]
        nomes = [i.filename for i in z.infolist()]
        if nomes != [i.filename for i in pasta.infos]:
            return ["as partes do arquivo novo não são as mesmas do original"]
        for nome in nomes:
            novo = z.read(nome)
            if nome not in alteradas:
                if novo != pasta.partes[nome]:
                    problemas.append(f"a parte {nome} mudou sem dever")
                continue
            try:
                ET.fromstring(novo)
            except ET.ParseError as e:
                problemas.append(f"a parte {nome} não é XML válido ({e})")
                continue
            if _declaracao_e_raiz(novo.decode("utf-8")) != _declaracao_e_raiz(pasta.partes[nome].decode("utf-8")):
                problemas.append(f"a declaração ou a raiz de {nome} mudou")
    if problemas:
        return problemas

    tb = pasta.tabela
    k = len(esp.novas)
    try:
        nova = xc.ler(tmp, CHAVE)
    except xc.ErroXlsx as e:
        return [f"o arquivo novo não pôde ser relido ({e})"]
    if nova.tabela.ref != xc._ref_intervalo(tb.col_ini, tb.cabecalho, tb.col_fim, tb.ultima + k):
        problemas.append(f"a tabela ficou em {nova.tabela.ref}")
    for linha in pasta.linhas:
        planejada_acima = any(r == linha.r for r, _c in esp.edicao.celulas)
        if linha.r < tb.primeira and not planejada_acima and (
                nova.linha(linha.r) is None or nova.linha(linha.r).xml != linha.xml):
            problemas.append(f"a linha {linha.r}, acima da tabela, mudou")
    col_chave = tb.coluna(CHAVE)
    ordem_antiga = [_numero(x.celulas[col_chave].valor) for x in pasta.corpo()]
    ordem_nova = [_numero(x.celulas[col_chave].valor) if col_chave in x.celulas else None
                  for x in nova.corpo()]
    planejada = esp.novas + ordem_antiga
    if ordem_nova != planejada:
        i = next((i for i, (a, b) in enumerate(zip(ordem_nova, planejada)) if a != b),
                 min(len(ordem_nova), len(planejada)))
        problemas.append(f"a ordem das pendências não é a planejada (linha {tb.primeira + i}: "
                         f"{ordem_nova[i] if i < len(ordem_nova) else 'nada'} no lugar de "
                         f"{planejada[i] if i < len(planejada) else 'nada'})")
        return problemas
    for i, plano in enumerate(esp.edicao.novas):
        linha = nova.linha(tb.primeira + i)
        for j, (valor, _s) in enumerate(plano.valores):
            cel = linha.celulas.get(tb.col_ini + j)
            if _texto(cel.valor if cel else None) != _texto(valor):
                problemas.append(f"a pendência nova {esp.novas[i]} não ficou como planejado")
                break
    for antiga in pasta.corpo():
        depois = nova.linha(antiga.r + k)
        if {a: v for a, v in depois.attrs.items() if a not in ("r", "s")} != \
                {a: v for a, v in antiga.attrs.items() if a not in ("r", "s")}:
            problemas.append(f"os atributos da linha {antiga.r} mudaram")
        if depois.s != antiga.s and antiga.r not in esp.edicao.estilo_linha:
            problemas.append(f"o estilo da linha {antiga.r} mudou sem dever")
        for c in esp.titulos:
            a_cel, d_cel = antiga.celulas.get(c), depois.celulas.get(c)
            a_s = a_cel.s if a_cel else None
            d_s = d_cel.s if d_cel else None
            planejada = esp.edicao.celulas.get((antiga.r, c))
            if planejada is None and a_s != d_s:
                problemas.append(f"o estilo de {xc.letra(c)}{antiga.r} mudou sem dever")
            d_valor = d_cel.valor if d_cel else None
            if c in esp.cols_aconex:
                if _texto(d_valor) != _texto(esp.finais[antiga.r][c]):
                    problemas.append(f"{esp.titulos[c]} da pendência na linha {antiga.r} não ficou como planejado")
            elif _texto(d_valor) != _texto(a_cel.valor if a_cel else None):
                problemas.append(f"a coluna manual {esp.titulos[c]} da linha {antiga.r} mudou")
        if len(problemas) > 10:
            break

    try:
        import pandas as pd

        df = pd.read_excel(tmp, sheet_name=pasta.aba_nome, header=tb.cabecalho - 1, dtype=str,
                           keep_default_na=False)
        if len(df) < tb.ultima - tb.primeira + 1 + k:
            problemas.append(f"o pandas leu {len(df)} linhas, menos que as {tb.ultima - tb.primeira + 1 + k} da tabela")
    except Exception as e:  # noqa: BLE001
        problemas.append(f"o pandas não leu a aba ({e})")
    return problemas
