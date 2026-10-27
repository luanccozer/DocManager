from __future__ import annotations

from datetime import datetime

from .. import dialogos
from ..components import Card, FileSelector, RunBar
from .base import BaseView


class ReportsView(BaseView):
    titulo_view = "Relatórios"
    subtitulo_view = ("Avanço (prazos de devolução), Auditoria de Integração (0AA) "
                      "e Fluxos em Andamento (onde está e com quem)")

    def montar(self, body):
        card = Card("Base Aconex")
        self.sel = card.add(FileSelector("Base Aconex", self.ctx.config, "aconex", aba_padrao="Documentos"))
        card.add(RunBar("Relatório de Avanço", self._avanco, self.log))
        card.add(RunBar("Auditoria de Integração", self._integracao, self.log))
        body.addWidget(card)

        # Fluxos vêm de OUTRA base (a Workflows API), com seletor próprio - juntar
        # os dois seletores num só faria o usuário apontar o arquivo errado.
        card_wf = Card("Base de Fluxos de Trabalho (extraída na aba Extração Aconex)")
        self.sel_wf = card_wf.add(FileSelector("Base de Fluxos", self.ctx.config, "fluxos",
                                               aba_padrao="Fluxos"))
        card_wf.add(RunBar("Fluxos em Andamento", self._fluxos, self.log))
        body.addWidget(card_wf)

    def _carregar(self):
        from ...common import carregar_base_aconex
        if not self.sel.path:
            self.log.log("Selecione a base Aconex.")
            return None
        self.log.log("Lendo base Aconex...")
        return carregar_base_aconex(self.sel.path, self.sel.sheet)

    def _exportar(self, ok, obj, nome, sheet, run):
        from ...common import exportar_dataframe
        if not ok:
            self.log.log(f"ERRO: {obj}")
            return
        if obj is None or obj.empty:
            self.log.log("Nenhuma linha no relatório.")
            return
        saida = dialogos.pedir_salvar(self.ctx.config, "saida", nome)
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok2, msg = exportar_dataframe(obj, saida, sheet_name=sheet)
        run.set_progress(1.0)
        self.log.log(msg)
        if ok2:
            dialogos.info("Relatórios", f"{len(obj)} linhas geradas.")

    def _avanco(self, run: RunBar):
        base = self._carregar()
        if base is None:
            return
        from ...relatorios_backend import gerar_relatorio_avanco
        run.set_progress(0.6)
        ok, obj = gerar_relatorio_avanco(base)
        nome = f"Relatorio_Avanco_{datetime.now().strftime('%d%m%y')}.xlsx"
        self._exportar(ok, obj, nome, "Avanço", run)

    def _integracao(self, run: RunBar):
        base = self._carregar()
        if base is None:
            return
        from ...relatorios_backend import auditar_fluxo_integracao
        run.set_progress(0.6)
        df = auditar_fluxo_integracao(base)
        nome = f"Auditoria_Integracao_{datetime.now().strftime('%d%m%y')}.xlsx"
        self._exportar(True, df, nome, "Integração", run)

    def _fluxos(self, run: RunBar):
        """Fluxos em Andamento: onde cada documento está e com quem (KB §24.12)."""
        import pandas as pd

        from ...relatorios_backend import analisar_fluxos_em_andamento, resumir_por_responsavel
        from ...services.excel_io import exportar_fluxos_andamento
        if not self.sel_wf.path:
            self.log.log("Selecione a base de Fluxos (extraia na aba 'Extração Aconex').")
            return
        self.log.log("Lendo base de fluxos...")
        df = pd.read_excel(self.sel_wf.path, sheet_name=self.sel_wf.sheet, dtype=str).fillna("")
        run.set_progress(0.5)
        try:
            detalhe = analisar_fluxos_em_andamento(df)
        except KeyError as e:
            self.log.log(f"ERRO: {e}")
            return
        if detalhe.empty:
            self.log.log("Nenhum fluxo em andamento com etapa aberta na base selecionada.")
            return
        por_pessoa = resumir_por_responsavel(detalhe, por="pessoa")
        por_org = resumir_por_responsavel(detalhe, por="organizacao")
        atrasados = int((pd.to_numeric(detalhe["Dias de Atraso"], errors="coerce") > 0).sum())
        self.log.log(f"{len(detalhe)} etapas em aberto - {atrasados} atrasadas; "
                     f"{len(por_pessoa)} responsáveis, {len(por_org)} organizações.")
        run.set_progress(0.8)

        nome = f"Fluxos_Andamento_{datetime.now().strftime('%d%m%y')}.xlsx"
        saida = dialogos.pedir_salvar(self.ctx.config, "saida", nome)
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        ok, msg = exportar_fluxos_andamento(detalhe, por_pessoa, por_org, saida)
        run.set_progress(1.0)
        self.log.log(msg)
        if ok:
            dialogos.info("Fluxos em Andamento", f"{len(detalhe)} etapas em aberto ({atrasados} atrasadas).")
