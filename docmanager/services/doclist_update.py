"""Orquestração da atualização do **Doc List Mapping** (KB §27).

Mesma espinha do Mapa dos Planos (`mapping_update`), com as regras próprias do
módulo: dois níveis, uma coluna de hierarquia e as colunas de planejamento
(PREVISTA / REPROGRAMADA / DATA-ALVO) dirigidas pelo Controle de Documentos.
FASE DE PROJETO é input manual (§27.3); o STATUS CONSOLIDADO é o mesmo do Mapa
(§27.4).

Ordem: carga da base → loop por linha (grupo ou documento) → hierarquia →
resumo de quantidades → salvar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import openpyxl

from ..core.doclist import (
    NIVEL_GRUPO,
    calcular_dias_desvio_emissao,
    calcular_predecessores,
    calcular_resumo_quantidades,
    classificar_situacao_emissao,
    niveis_fora_do_padrao,
    resolver_datas_doclist,
)
from ..core.identity import AconexIndex, obter_codigos_historicos
from ..core.mapping import processar_documento
from .controle_docs import ControleDocs
from .doclist_io import DocListSheet
from .excel_io import carregar_base_aconex


@dataclass
class ResultadoDocList:
    ok: bool
    mensagem: str
    linhas_processadas: int = 0
    grupos: int = 0


@dataclass
class DiagnosticoDocList:
    """Placar do casamento Doc List ↔ Controle, para o log não ser mudo."""
    previstas: int = 0
    previstas_atualizadas: int = 0
    reprogramadas: int = 0
    alvos: int = 0
    titulos: int = 0
    por_via: dict = field(default_factory=dict)
    sem_match: list = field(default_factory=list)

    LIMITE_AMOSTRA = 15

    def registrar(self, via: str, codigo: str) -> None:
        if via:
            self.por_via[via] = self.por_via.get(via, 0) + 1
        else:
            self.sem_match.append(codigo)

    @property
    def casados(self) -> int:
        return sum(self.por_via.values())

    def linhas_log(self) -> list[str]:
        vias = ", ".join(f"{k}: {v}" for k, v in sorted(self.por_via.items())) or "nenhum"
        msgs = [
            f"Controle ↔ Doc List: {self.casados} documentos casaram ({vias}).",
            f"Planejamento gravado: {self.previstas} datas previstas "
            f"({self.previstas_atualizadas} atualizadas por serem mais recentes), "
            f"{self.reprogramadas} reprogramações, {self.alvos} datas-alvo.",
        ]
        if self.titulos:
            msgs.append(f"{self.titulos} descrições vindas do título do Controle "
                        f"(documentos que o Aconex ainda não conhece).")
        if self.sem_match:
            amostra = ", ".join(self.sem_match[:self.LIMITE_AMOSTRA])
            resto = "" if len(self.sem_match) <= self.LIMITE_AMOSTRA else \
                f" (+{len(self.sem_match) - self.LIMITE_AMOSTRA} outros)"
            msgs.append(f"{len(self.sem_match)} documentos SEM correspondência no Controle: "
                        f"{amostra}{resto}")
            msgs.append("Se algum deles existe no Controle, confira se a ABA selecionada é a certa.")
        return msgs


def _escrever_data_emissao(ds: DocListSheet, row: int, valor) -> None:
    """Grava DATA ÚLTIMA EMISSÃO como data NATIVA do Excel.

    O Mapa dos Planos escreve essa célula como texto 'dd/mm/aaaa'; aqui não
    serve, porque o Doc List alimenta um dashboard que precisa agrupar por
    período. Valor irreconhecível cai como texto, para não sumir informação.
    """
    if not valor:
        ds.set_val("data_ultimo_status", row, None)
        return
    from .doclist_io import _para_date
    d = _para_date(valor)
    if d is not None:
        ds.set_data("data_ultimo_status", row, d)
    else:
        ds.set_val("data_ultimo_status", row, str(valor))


def _escrever_grupo(ds: DocListSheet, row: int) -> None:
    """Linha de NÍVEL 1: agrupamento por escopo, não é documento.

    Não é procurada no Aconex nem no Controle; recebe o bloco NÃO EMITIDO (como
    na planilha que a equipe já usa) e, mais adiante, o RESUMO QUANTIDADES.
    """
    from ..core.constants import CONS_NAO_EMITIDO, NAO_EMITIDO

    ds.set_val("emitido_nao_emitido", row, NAO_EMITIDO)
    ds.set_val("status_real", row, NAO_EMITIDO)
    ds.set_val("status_consolidado", row, CONS_NAO_EMITIDO)
    ds.set_val("com_itaipu", row, "CMI")
    # Agrupamento não tem DATA-ALVO nem emissão: o bloco de aderência fica
    # VAZIO de propósito, para não inventar um balde e poluir a legenda do
    # dashboard com linhas que não são documento.
    for chave in ("revisao", "data_ultimo_status", "status_emissao",
                  "data_primeira_emissao", "situacao_emissao", "dias_desvio_emissao"):
        ds.set_val(chave, row, None)


def _escrever_situacao_emissao(ds: DocListSheet, row: int, r, data_alvo, hoje: date) -> None:
    """Grava o bloco de aderência ao planejamento (KB §27.5).

    `DATA 1ª EMISSÃO` vai como data NATIVA - o dashboard precisa dela agrupável,
    igual à DATA-ALVO. `DIAS DESVIO EMISSÃO` vai como número (negativo =
    adiantado), não como texto, para o Power BI conseguir somar/mediar.
    """
    ds.set_data("data_primeira_emissao", row, r.data_primeira_emissao)
    ds.set_val("situacao_emissao", row, classificar_situacao_emissao(
        data_primeira_emissao=r.data_primeira_emissao, data_alvo=data_alvo,
        status_consolidado=r.status_consolidado, hoje=hoje))
    ds.set_val("dias_desvio_emissao", row,
               calcular_dias_desvio_emissao(r.data_primeira_emissao, data_alvo))


def _escrever_documento(ds: DocListSheet, row: int, r) -> None:
    ds.set_val("revisao", row, r.revisao)
    _escrever_data_emissao(ds, row, r.data_ultimo_status)
    ds.set_val("status_emissao", row, r.status_emissao)
    if r.cod_itaipu_atual:
        ds.set_val("codigo_itaipu", row, r.cod_itaipu_atual)
    if r.cod_cmi_atual:
        ds.set_val("codigo_cmi", row, r.cod_cmi_atual)
    if r.descricao_atual:
        ds.set_val("descricao", row, r.descricao_atual)
    ds.set_val("status_real", row, r.status_real)
    ds.set_val("emitido_nao_emitido", row, r.emitido_nao_emitido)
    ds.set_val("com_itaipu", row, r.com_itaipu)
    # Consolidado IGUAL ao do Mapa: os três status de aprovação caem em APROVADO
    # (§27.4). `processar_documento` já o calculou assim.
    ds.set_val("status_consolidado", row, r.status_consolidado)


def atualizar_doclist(
    path_aconex, path_doclist, *, sheet_aconex=0, sheet_doclist=None,
    controle: ControleDocs | None = None, hoje: date | None = None,
    log_cb=print, progress_cb=None, retry_cb=None,
) -> ResultadoDocList:
    """Atualiza a planilha do Doc List Mapping a partir da base Aconex (+
    Controle de Documentos, opcional)."""
    log_cb("Lendo base Aconex...")
    base = carregar_base_aconex(path_aconex, sheet_aconex)
    idx = AconexIndex(base)
    log_cb(f"Base carregada: {len(base)} linhas. Abrindo Doc List Mapping...")

    wb = openpyxl.load_workbook(path_doclist)
    ws = wb[sheet_doclist] if sheet_doclist and not isinstance(sheet_doclist, int) else wb.active
    ds = DocListSheet(ws)

    trocas = ds.renomear_cabecalhos_legados()
    for antigo, novo in trocas:
        log_cb(f"Cabeçalho atualizado: '{antigo}' → '{novo}'.")
    if ds.colunas_ausentes:
        log_cb(f"Aviso: colunas não encontradas na planilha (serão ignoradas): "
               f"{', '.join(ds.colunas_ausentes)}")

    log_cb(f"Processando linhas {ds.start_row} a {ds.max_row}...")
    hoje_ref = hoje or date.today()   # régua do PENDENTE NO PRAZO / VENCIDO
    total = max(ds.max_row - ds.start_row + 1, 1)
    processadas = grupos = 0
    diag = DiagnosticoDocList()

    for i, row in enumerate(range(ds.start_row, ds.max_row + 1)):
        if progress_cb and i % 10 == 0:
            progress_cb(min(i / total, 0.95))
        c_itaipu = ds.get_val("codigo_itaipu", row)
        c_cmi = ds.get_val("codigo_cmi", row)
        if not c_itaipu and not c_cmi:
            continue
        processadas += 1

        if ds.get_val("nivel", row).strip() == NIVEL_GRUPO:
            grupos += 1
            _escrever_grupo(ds, row)
            continue

        df_tracking = idx.localizar(c_itaipu, c_cmi)

        # Planejamento vindo do Controle (roda mesmo sem o doc no Aconex - é
        # justamente o não emitido que precisa da data prevista).
        for chave in ("data_prevista", "data_reprogramada", "data_alvo"):
            ds.matar_zumbi(chave, row)
        datas = resolver_datas_doclist(
            prevista_atual=ds.get_data("data_prevista", row),
            reprogramada_atual=ds.get_data("data_reprogramada", row),
            codigos=obter_codigos_historicos(df_tracking) if not df_tracking.empty else [],
            cod_itaipu_atual=c_itaipu, cod_cmi_atual=c_cmi, controle=controle)
        if datas.prevista is not None and ds.set_data("data_prevista", row, datas.prevista):
            diag.previstas += 1
            diag.previstas_atualizadas += int(datas.prevista_atualizada)
        if datas.reprogramada is not None and ds.set_data("data_reprogramada", row, datas.reprogramada):
            diag.reprogramadas += 1
        # DATA-ALVO é sempre reescrita (inclusive apagada, se não há mais data).
        if ds.set_data("data_alvo", row, datas.data_alvo) and datas.data_alvo is not None:
            diag.alvos += 1
        if controle is not None:
            diag.registrar(datas.via, c_itaipu or c_cmi)

        resultado = processar_documento(
            df_tracking, nivel=ds.get_val("nivel", row), tag_etapa="",
            data_prevista=datas.data_alvo, hoje=hoje)
        _escrever_documento(ds, row, resultado)
        _escrever_situacao_emissao(ds, row, resultado, datas.data_alvo, hoje_ref)

        # Descrição - cadeia de prioridade Aconex > Controle > planilha (§27.3).
        # Quem está no Aconex já teve a descrição escrita acima. Para o resto,
        # o título do Controle SOBRESCREVE o que estiver na célula: descrição
        # digitada à mão costuma ser genérica, e a do Controle é a boa.
        if df_tracking.empty and datas.titulo_controle \
                and ds.get_val("descricao", row) != datas.titulo_controle:
            ds.set_val("descricao", row, datas.titulo_controle)
            diag.titulos += 1

    if controle is not None:
        for linha_log in diag.linhas_log():
            log_cb(linha_log)

    # Hierarquia: uma coluna só (PREDECESSOR), dois níveis.
    log_cb("Calculando predecessores...")
    linhas = ds.ler_linhas()
    fora = niveis_fora_do_padrao(linhas)
    if fora:
        log_cb(f"Aviso: {len(fora)} linha(s) com NÍVEL fora de 1/2 "
               f"(linhas {', '.join(str(r) for r in fora[:10])}) - tratadas como documento.")
    predecessores = calcular_predecessores(linhas)
    for ln in linhas:
        ds.set_val("predecessor", ln.row, predecessores[ln.row])

    # Resumo de quantidades nos grupos (relê o consolidado já gravado).
    log_cb("Calculando resumo de quantidades...")
    linhas = ds.ler_linhas()
    for ln in linhas:
        ln.predecessor = predecessores.get(ln.row, "")
    for row_r, texto in calcular_resumo_quantidades(linhas, predecessores).items():
        ds.set_val("resumo_quantidades", row_r, texto)

    log_cb("Salvando...")
    while True:
        try:
            wb.save(path_doclist)
            break
        except PermissionError as e:
            if retry_cb and retry_cb(f"Arquivo aberto/bloqueado: {e}. Feche e tente de novo."):
                continue
            return ResultadoDocList(False, f"Não foi possível salvar (arquivo aberto?): {e}",
                                    processadas, grupos)

    if progress_cb:
        progress_cb(1.0)
    return ResultadoDocList(
        True, f"Doc List Mapping atualizado: {processadas - grupos} documentos em {grupos} grupos.",
        processadas, grupos)
