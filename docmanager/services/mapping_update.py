"""Orquestração da atualização do Mapa dos Planos (ex-`iniciar_atualizacao`).

Amarra, na MESMA ordem do legado (aconex_reviewer L401-814): carga da base →
loop por documento (injeção da data prevista + cálculo) → hierarquia →
pente-fino VIP (se o toggle estiver ligado) → resumo de quantidades → salvar.

O core faz o cálculo puro; aqui cuida do I/O da planilha e dos callbacks de
progresso/log/retry (a UI pluga os seus; a CLI usa print).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import openpyxl

from ..core.hierarchy import (
    aplicar_regra_estrita,
    calcular_hierarquia,
    calcular_resumo_quantidades,
    identificar_planilhas_vip,
)
from ..core.identity import AconexIndex, obter_codigos_historicos
from ..core.mapping import processar_documento, resolver_data_prevista
from .controle_docs import ControleDocs
from .excel_io import MappingSheet, carregar_base_aconex


@dataclass
class ResultadoMapa:
    ok: bool
    mensagem: str
    linhas_processadas: int = 0


def _fmt_data(valor) -> str:
    """Formata data para dd/mm/yyyy quando possível (senão devolve string)."""
    try:
        return valor.strftime("%d/%m/%Y")
    except Exception:
        return str(valor) if valor is not None else ""


def _escrever_resultado(ms: MappingSheet, row: int, r) -> None:
    # Visuais (None → limpa a célula / mata zumbi)
    ms.set_val("revisao", row, r.revisao)
    ms.set_val("data_ultimo_status", row, _fmt_data(r.data_ultimo_status) if r.data_ultimo_status else None)
    ms.set_val("status_emissao", row, r.status_emissao)
    if r.cod_itaipu_atual:
        ms.set_val("codigo_itaipu", row, r.cod_itaipu_atual)
    if r.cod_cmi_atual:
        ms.set_val("codigo_cmi", row, r.cod_cmi_atual)
    if r.descricao_atual:
        ms.set_val("descricao", row, r.descricao_atual)
    # Calculadas
    ms.set_val("status_real", row, r.status_real)
    ms.set_val("emitido_nao_emitido", row, r.emitido_nao_emitido)
    ms.set_val("status_consolidado", row, r.status_consolidado)
    ms.set_val("com_itaipu", row, r.com_itaipu)
    # KPIs
    for chave, k in (("dias_status", "dias_status"), ("situacao_prazo", "situacao_prazo"),
                     ("dias_atraso", "dias_atraso"), ("total_ciclos", "total_ciclos"),
                     ("ciclos_aprovar", "ciclos_aprovar"), ("downgrade", "downgrade")):
        ms.set_val(chave, row, r.kpis.get(k))
    ms.set_val("atraso_acum_ib", row, r.atrasos.get("atraso_acumulado_itaipu"))
    ms.set_val("atraso_acum_cmi", row, r.atrasos.get("atraso_acumulado_cmi"))


def atualizar_mapeamento(
    path_aconex, path_mapping, *, sheet_aconex=0, sheet_mapping=None,
    controle: ControleDocs | None = None, regra_estrita_vip: bool = False,
    hoje: date | None = None, log_cb=print, progress_cb=None, retry_cb=None,
) -> ResultadoMapa:
    log_cb("Lendo base Aconex...")
    base = carregar_base_aconex(path_aconex, sheet_aconex)
    idx = AconexIndex(base)
    log_cb(f"Base carregada: {len(base)} linhas. Abrindo mapeamento...")

    wb = openpyxl.load_workbook(path_mapping)
    ws = wb[sheet_mapping] if sheet_mapping else wb.active
    ms = MappingSheet(ws)

    log_cb(f"Toggle regra estrita VIP: {'LIGADO' if regra_estrita_vip else 'desligado'}.")
    log_cb(f"Processando linhas {ms.start_row} a {ms.max_row}...")

    total = ms.max_row - ms.start_row + 1
    processadas = 0
    for i, row in enumerate(range(ms.start_row, ms.max_row + 1)):
        if progress_cb and total > 0 and i % 10 == 0:
            progress_cb(i / total)
        c_itaipu = ms.get_val("codigo_itaipu", row)
        c_cmi = ms.get_val("codigo_cmi", row)
        if not c_itaipu and not c_cmi:
            continue
        processadas += 1
        df_tracking = idx.localizar(c_itaipu, c_cmi)

        # Injeção da data prevista (§13): mata zumbi, resolve, escreve se vazio.
        ms.matar_zumbi("data_previsao_etapa_1", row)
        if controle is not None and not df_tracking.empty:
            valor = ms.get_val("data_previsao_etapa_1", row)
            data_inj = resolver_data_prevista(
                valor or None, obter_codigos_historicos(df_tracking), c_itaipu, c_cmi, controle)
            if data_inj is not None:
                ms.set_val("data_previsao_etapa_1", row, data_inj)
        data_prevista = ms.get_val("data_previsao_etapa_1", row) or None

        nivel = ms.get_val("nivel", row)
        tag_etapa = ms.get_val("filtro_etapa", row)
        resultado = processar_documento(
            df_tracking, nivel=nivel, tag_etapa=tag_etapa, data_prevista=data_prevista, hoje=hoje)
        _escrever_resultado(ms, row, resultado)

    # Hierarquia (posicional) — relê os códigos já atualizados.
    log_cb("Calculando predecessores e planos de execução...")
    linhas = ms.ler_linhas()
    hierarquia = calcular_hierarquia(linhas)
    for ln in linhas:
        pred, plano = hierarquia[ln.row]
        ms.set_val("predecessor", ln.row, pred)
        ms.set_val("plano_de_execucao", ln.row, plano)

    # Pente-fino VIP (só com o toggle ligado).
    if regra_estrita_vip:
        log_cb("Aplicando regra estrita das planilhas VIP...")
        linhas = ms.ler_linhas()  # relê com predecessores
        vips = identificar_planilhas_vip(linhas)
        for row_r, novo_cons in aplicar_regra_estrita(linhas, hierarquia, vips).items():
            ms.set_val("status_consolidado", row_r, novo_cons)

    # Resumo de quantidades.
    log_cb("Calculando resumo de quantidades...")
    linhas = ms.ler_linhas()
    for row_r, texto in calcular_resumo_quantidades(linhas, hierarquia, estrito=regra_estrita_vip).items():
        ms.set_val("resumo_quantidades", row_r, texto)

    # Salvar (com retry opcional em PermissionError).
    log_cb("Salvando...")
    while True:
        try:
            wb.save(path_mapping)
            break
        except PermissionError as e:
            if retry_cb and retry_cb(f"Arquivo aberto/bloqueado: {e}. Feche e tente de novo."):
                continue
            return ResultadoMapa(False, f"Não foi possível salvar (arquivo aberto?): {e}", processadas)

    if progress_cb:
        progress_cb(1.0)
    return ResultadoMapa(True, f"Mapeamento atualizado: {processadas} documentos.", processadas)
