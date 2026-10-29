"""Orquestração da atualização do Mapa dos Planos (ex-`iniciar_atualizacao`).

Amarra, na MESMA ordem do legado (aconex_reviewer L401-814): carga da base →
loop por documento (injeção da data prevista + cálculo) → hierarquia →
pente-fino VIP (se o toggle estiver ligado) → resumo de quantidades → salvar.

O core faz o cálculo puro; aqui cuida do I/O da planilha e dos callbacks de
progresso/log/retry (a UI pluga os seus; a CLI usa print).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import openpyxl

from ..core.hierarchy import (
    aplicar_regra_estrita,
    calcular_hierarquia,
    calcular_resumo_quantidades,
    identificar_planilhas_vip,
    identificar_planos_comissionamento,
)
from ..core.identity import AconexIndex, obter_codigos_historicos
from ..core.mapping import processar_documento, resolver_datas_controle
from ..core.planejamento import COLUNA_PREVISTA
from .controle_docs import ControleDocs, ControleMemo
from .excel_io import COLUNAS_MAPA, MappingSheet, aviso_datas_com_texto, carregar_base_aconex
from .sobrescricao import IncidenciaDoc, linhas_log_nao_trocadas

TITULO_REPROGRAMADA_ETAPA1 = "DATA REPROGRAMADA (etapa 1)"


@dataclass
class ResultadoMapa:
    ok: bool
    mensagem: str
    linhas_processadas: int = 0


@dataclass
class DiagnosticoControle:
    """Placar do casamento Mapa ↔ Controle de Documentos.

    Existe porque a falha antiga era SILENCIOSA: sem data, o mapeamento saía
    igualzinho a um mapeamento sem Controle. Agora o log diz quantos casaram,
    por qual via, e nomeia os que ficaram de fora."""
    previstas: int = 0
    reprogramadas: int = 0
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
        msgs = [f"Controle ↔ Mapa: {self.casados} documentos casaram ({vias}); "
                f"{self.previstas} datas previstas e {self.reprogramadas} reprogramações escritas."]
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


@dataclass
class _Linha:
    """Uma linha com código, guardada entre as duas passadas."""
    row: int
    cod_itaipu: str
    cod_cmi: str
    df_tracking: object = None
    codigos: list = field(default_factory=list)


def _resolver_datas(ms: MappingSheet, ln: _Linha, controle, aceitas=frozenset()):
    return resolver_datas_controle(
        ms.get_bruto("data_previsao_etapa_1", ln.row), ln.codigos, ln.cod_itaipu, ln.cod_cmi,
        controle, valor_celula_reprogramada=ms.get_reprogramada_etapa1_bruto(ln.row),
        aceitas=aceitas)


def _incidencias_da_linha(ms: MappingSheet, ln: _Linha, datas) -> list[IncidenciaDoc]:
    return [IncidenciaDoc(
        row=ln.row, cod_itaipu=ln.cod_itaipu, cod_cmi=ln.cod_cmi,
        descricao=ms.get_val("descricao", ln.row), coluna=inc.coluna,
        titulo_coluna=(COLUNAS_MAPA["data_previsao_etapa_1"] if inc.coluna == COLUNA_PREVISTA
                       else TITULO_REPROGRAMADA_ETAPA1),
        valor_planilha=inc.valor_planilha, data_controle=inc.data_controle)
        for inc in datas.incidencias]


def _escrever_resultado(ms: MappingSheet, row: int, r) -> None:
    # Visuais (None → limpa a célula / mata zumbi)
    ms.set_val("revisao", row, r.revisao)
    # DATA ÚLTIMA EMISSÃO como data nativa, igual ao Doc List. Até a v3.1.0 ia
    # como TEXTO 'dd/mm/aaaa', que o Power BI não agrupa por período.
    ms.set_data_ou_texto("data_ultimo_status", row, r.data_ultimo_status)
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

    total = max(ms.max_row - ms.start_row + 1, 1)
    controle = ControleMemo(controle) if controle is not None else None
    diag = DiagnosticoControle()
    datas_com_texto: list[str] = []

    # Passada 1: datas da etapa 1 viram DATA do Excel, cada documento é
    # localizado no Aconex e as incidências com o Controle são levantadas
    # (ADR 0001: data preenchida não é trocada sem aceite).
    linhas_doc: list[_Linha] = []
    incidencias: list[IncidenciaDoc] = []
    for i, row in enumerate(range(ms.start_row, ms.max_row + 1)):
        if progress_cb and i % 10 == 0:
            progress_cb(min(0.3 * i / total, 0.3))
        c_itaipu = ms.get_val("codigo_itaipu", row)
        c_cmi = ms.get_val("codigo_cmi", row)
        if not c_itaipu and not c_cmi:
            continue

        # As datas da etapa 1 que a equipe digita (e que o app também preenche
        # pelo Controle) viram DATA do Excel - texto '15/10/2026', formato
        # personalizado... -, para o Power BI ler a coluna como data (§27.6).
        for rotulo, texto in (
                (COLUNAS_MAPA["data_previsao_etapa_1"], ms.normalizar_data("data_previsao_etapa_1", row)),
                (TITULO_REPROGRAMADA_ETAPA1, ms.normalizar_reprogramada_etapa1(row))):
            if texto is not None:
                datas_com_texto.append(f"{rotulo} linha {row}: '{texto}'")

        ln = _Linha(row, c_itaipu, c_cmi, df_tracking=idx.localizar(c_itaipu, c_cmi))
        linhas_doc.append(ln)
        # A busca no Controle roda MESMO com o documento ausente do Aconex
        # (§24.12): é justamente o NÃO EMITIDO que mais precisa da data planejada.
        if controle is not None:
            ln.codigos = obter_codigos_historicos(ln.df_tracking) if not ln.df_tracking.empty else []
            incidencias += _incidencias_da_linha(ms, ln, _resolver_datas(ms, ln, controle))

    for linha_log in linhas_log_nao_trocadas(incidencias):
        log_cb(linha_log)

    # Passada 2: grava datas, status, KPIs e atrasos.
    for i, ln in enumerate(linhas_doc):
        if progress_cb and i % 10 == 0:
            progress_cb(min(0.3 + 0.65 * i / max(len(linhas_doc), 1), 0.95))
        row = ln.row
        data_ref, datas = None, None
        if controle is not None:
            datas = _resolver_datas(ms, ln, controle)
            if datas.prevista_para_celula is not None:
                ms.set_data("data_previsao_etapa_1", row, datas.prevista_para_celula)
                diag.previstas += 1
            if datas.reprogramada is not None:
                if ms.set_reprogramada_etapa1(row, datas.reprogramada):
                    diag.reprogramadas += 1
            diag.registrar(datas.via, ln.cod_itaipu or ln.cod_cmi)
            data_ref = datas.data_ref
        # Atraso usa a data_ref (já com o que ficou nas células); sem Controle,
        # cai na data que está na planilha.
        data_prevista = data_ref if data_ref is not None else ms.get_data("data_previsao_etapa_1", row)

        nivel = ms.get_val("nivel", row)
        tag_etapa = ms.get_val("filtro_etapa", row)
        resultado = processar_documento(
            ln.df_tracking, nivel=nivel, tag_etapa=tag_etapa, data_prevista=data_prevista, hoje=hoje)
        _escrever_resultado(ms, row, resultado)

        # Descrição - cadeia de prioridade Aconex > Controle > planilha (§27.3).
        # Quem está no Aconex já teve a descrição escrita acima. Para o resto,
        # o título do Controle SOBRESCREVE o que estiver na célula: descrição
        # digitada à mão costuma ser genérica, e a do Controle é a boa.
        if ln.df_tracking.empty and datas is not None and datas.titulo_controle \
                and ms.get_val("descricao", row) != datas.titulo_controle:
            ms.set_val("descricao", row, datas.titulo_controle)
            diag.titulos += 1
    processadas = len(linhas_doc)

    if controle is not None:
        for linha_log in diag.linhas_log():
            log_cb(linha_log)
    if (aviso := aviso_datas_com_texto(datas_com_texto)):
        log_cb(aviso)

    # Hierarquia (posicional) - relê os códigos já atualizados.
    log_cb("Calculando predecessores e planos de execução...")
    linhas = ms.ler_linhas()
    hierarquia = calcular_hierarquia(linhas)
    for ln in linhas:
        pred, plano = hierarquia[ln.row]
        ms.set_val("predecessor", ln.row, pred)
        ms.set_val("plano_de_execucao", ln.row, plano)

    # Pente-fino VIP (só com o toggle ligado): planilhas VIP (nível 3) rebaixam
    # seus documentos de nível 4; planos de (des)comissionamento (nível 2)
    # rebaixam suas planilhas de nível 3 (pedido do usuário).
    if regra_estrita_vip:
        log_cb("Aplicando regra estrita (planilhas VIP e planos de comissionamento)...")
        linhas = ms.ler_linhas()  # relê com predecessores
        vips = identificar_planilhas_vip(linhas)
        planos_comiss = identificar_planos_comissionamento(linhas)
        for row_r, novo_cons in aplicar_regra_estrita(linhas, hierarquia, vips, planos_comiss).items():
            ms.set_val("status_consolidado", row_r, novo_cons)

    # Resumo de quantidades.
    log_cb("Calculando resumo de quantidades...")
    linhas = ms.ler_linhas()
    planos_comiss = identificar_planos_comissionamento(linhas)
    for row_r, texto in calcular_resumo_quantidades(
            linhas, hierarquia, estrito=regra_estrita_vip, planos_comiss=planos_comiss).items():
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
