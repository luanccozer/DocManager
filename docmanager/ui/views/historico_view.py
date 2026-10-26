from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QPlainTextEdit

from .. import dialogos
from ..components import Abas, Card, FileSelector, RunBar, rotulo
from ..ponte import na_ui_e_esperar
from .base import BaseView


class HistoricoView(BaseView):
    titulo_view = "Histórico Consolidado"
    subtitulo_view = "Gera a planilha detalhada ou o dashboard executivo, a partir da mesma base"

    def __init__(self, ctx, parent=None):
        self._server = None
        super().__init__(ctx, parent)

    def montar(self, body):
        cfg = self.ctx.config
        card = Card("Arquivos")
        self.sel_aconex = card.add(FileSelector("Base Aconex", cfg, "aconex", aba_padrao="Documentos"))
        self.sel_ctrl = card.add(FileSelector("Controle de Documentos (obrigatório)", cfg, "controle"))
        body.addWidget(card)

        rem = Card("Remover documentos (opcional)")
        rem.add(rotulo("Cole os códigos Itaipu dos documentos que não devem entrar no histórico, um por "
                       "linha (copie do Excel). Também aceita código CMI. Vale para a Planilha e o Dashboard.",
                       "suave", quebra=True))
        self.txt_excluir = QPlainTextEdit()
        self.txt_excluir.setObjectName("caixa_texto")
        self.txt_excluir.setFixedHeight(96)
        rem.add(self.txt_excluir)
        body.addWidget(rem)

        abas_card = Card()
        self.tabs = Abas()
        aba_plan = self.tabs.add("Planilha", "file-spreadsheet")
        aba_dash = self.tabs.add("Dashboard", "chart-column")
        abas_card.add(self.tabs)
        body.addWidget(abas_card)

        aba_plan.layout().addWidget(rotulo(
            "Excel com 1 linha por revisão + colunas de atraso (Itaipu e CMI).", "suave", quebra=True))
        aba_plan.layout().addWidget(RunBar("Gerar Planilha", self._gerar_planilha, self.log))

        aba_dash.layout().addWidget(rotulo(
            "Dashboard web: First Time Right, ciclo de aprovação, status vigente, fluxo de envios/retornos, "
            "evolução do atraso no tempo e gargalos por especialidade.\nEm desenvolvimento. Será liberado "
            "em breve.", "suave", quebra=True))
        run_dash = RunBar("Gerar e Abrir Dashboard", self._abrir_dashboard, self.log)
        run_dash.desabilitar("Dashboard (em desenvolvimento)")
        aba_dash.layout().addWidget(run_dash)

    def _base(self, run):
        from ...common import carregar_base_aconex
        from ...controle_backend import ler_controle
        if not self.sel_aconex.path:
            self.log.log("Selecione a base Aconex.")
            return None, None
        if not self.sel_ctrl.path:
            self.log.log("Selecione o Controle de Documentos: ele define quais documentos "
                         "entram no histórico (agora é obrigatório).")
            return None, None
        self.log.log("Lendo base Aconex...")
        run.set_progress(0.3)
        base = carregar_base_aconex(self.sel_aconex.path, self.sel_aconex.sheet)
        controle = ler_controle(self.sel_ctrl.path, self.sel_ctrl.sheet, log_cb=self.log.log)
        return base, controle

    def _policy(self):
        from ...historico_backend import DelayPolicy
        return DelayPolicy(base_cmi_0a=self.ctx.config.settings.base_atraso_cmi_0a)

    def _codigos_excluir(self):
        """Códigos colados para remoção manual (um por linha), como a Via Lista Rápida."""
        return [c.strip() for c in self.txt_excluir.toPlainText().splitlines() if c.strip()]

    def _gerar_planilha(self, run: RunBar):
        base, controle = self._base(run)
        if base is None:
            return
        from ...historico_backend import exportar_historico, gerar_historico
        wide = gerar_historico(base, controle, self._policy(),
                               excluir_codigos=na_ui_e_esperar(self._codigos_excluir), log_cb=self.log.log)
        nome = f"Historico_Consolidado_{datetime.now().strftime('%d.%m.%y_%Hh%Mm')}.xlsx"
        saida = dialogos.pedir_salvar(self.ctx.config, "saida", nome)
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok, msg = exportar_historico(wide, saida)
        run.set_progress(1.0)
        self.log.log(msg)
        if ok:
            dialogos.info("Histórico", f"{len(wide)} revisões geradas.")

    def _abrir_dashboard(self, run: RunBar):
        base, controle = self._base(run)
        if base is None:
            return
        from ...historico_backend import DashboardServer, gerar_historico
        self.log.log("Consolidando...")
        run.set_progress(0.7)
        wide = gerar_historico(base, controle, self._policy(),
                               excluir_codigos=na_ui_e_esperar(self._codigos_excluir), log_cb=self.log.log)
        if self._server is None:
            self._server = DashboardServer(porta=self.ctx.config.settings.dash_port)
        url = self._server.iniciar(wide)
        run.set_progress(1.0)
        self.log.log(f"Dashboard disponível em {url}")
