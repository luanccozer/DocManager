from __future__ import annotations

from .. import dialogos
from ..components import Card, FileSelector, RunBar, botao, linha, rotulo
from .base import BaseView


def ler_linha_cabecalho(caminho: str, aba, classe_planilha) -> int:
    """Linha do cabeçalho da planilha (Mapa ou Doc List), que o Delta precisa."""
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=True)
    try:
        ws = wb[aba] if aba and not isinstance(aba, int) else wb.active
        return classe_planilha(ws).row_header
    finally:
        wb.close()


class MapaView(BaseView):
    titulo_view = "Mapa dos Planos"
    subtitulo_view = "Atualiza status, hierarquia, KPIs e resumos da planilha de mapeamento"

    _COLS_CFG = {"doc": "N° ITAIPU", "grupo": "GRUPO", "sistema": "SISTEMA",
                 "nivel": "NÍVEL", "titulo": "DESCRIÇÃO DO DOCUMENTO", "predecessor": "PREDECESSOR"}

    def montar(self, body):
        cfg = self.ctx.config
        card = Card("Arquivos")
        self.sel_aconex = card.add(FileSelector("Base Aconex", cfg, "aconex", aba_padrao="Documentos"))
        self.sel_mapa = card.add(FileSelector("Mapeamento de Planos", cfg, "mapa"))
        self.sel_ctrl = card.add(FileSelector("Controle de Documentos (opcional)", cfg, "controle"))
        body.addWidget(card)

        self.lbl_vip = rotulo("", "suave")
        delta = botao("Analisar Mudanças por Período (Delta)", icone="history", ao_clicar=self._abrir_delta)
        body.addWidget(linha(self.lbl_vip, delta, esticar=0))
        self._atualizar_vip()

        self.run = RunBar("Iniciar Atualização", self._tarefa, self.log)
        body.addWidget(self.run)

    def _abrir_delta(self):
        if not self.sel_mapa.path:
            dialogos.aviso("Aviso", "Selecione a Planilha de Mapeamento primeiro.", self)
            return
        if not self.sel_aconex.path:
            dialogos.aviso("Aviso", "Selecione a Base Aconex para prosseguir.", self)
            return
        from ...mapa_backend import MappingSheet
        from .delta_dialog import DeltaDialog
        cfg = dict(self._COLS_CFG)
        try:
            cfg["header_row"] = ler_linha_cabecalho(self.sel_mapa.path, self.sel_mapa.sheet, MappingSheet)
        except Exception as e:  # noqa: BLE001
            dialogos.erro("Erro", f"Não foi possível ler o cabeçalho do mapeamento:\n{e}", self)
            return
        self._delta = DeltaDialog(self, config=self.ctx.config, path_map=self.sel_mapa.path,
                                  sheet_map=self.sel_mapa.sheet, path_hist=self.sel_aconex.path,
                                  sheet_hist=self.sel_aconex.sheet, cols_config=cfg,
                                  estrito=self.ctx.config.settings.regra_estrita_vip)
        self._delta.show()

    def _atualizar_vip(self):
        estado = "Ligada" if self.ctx.config.settings.regra_estrita_vip else "Desligada"
        self.lbl_vip.setText(f"Regra da Aprovação Intermediária: {estado}  (altere em Configurações)")

    def ao_exibir(self):
        self._atualizar_vip()   # o toggle mora nas Configurações

    def _tarefa(self, run: RunBar):
        if not self.sel_aconex.path or not self.sel_mapa.path:
            self.log.log("Selecione a base Aconex e o mapeamento.")
            return
        from ...controle_backend import ler_controle
        from ...mapa_backend import atualizar_mapeamento
        controle = (ler_controle(self.sel_ctrl.path, self.sel_ctrl.sheet, log_cb=self.log.log)
                    if self.sel_ctrl.path else None)
        r = atualizar_mapeamento(
            self.sel_aconex.path, self.sel_mapa.path,
            sheet_aconex=self.sel_aconex.sheet, sheet_mapping=self.sel_mapa.sheet,
            controle=controle, regra_estrita_vip=self.ctx.config.settings.regra_estrita_vip,
            log_cb=self.log.log, progress_cb=run.set_progress,
            retry_cb=lambda m: dialogos.tentar_de_novo("Salvar", m))
        self.log.log(r.mensagem)
        if r.ok:
            dialogos.info("Mapa dos Planos", r.mensagem)
