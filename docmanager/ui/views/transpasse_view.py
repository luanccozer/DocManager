"""Transpasse de Fase: a Planilha1 da equipe (o quadro de cores por dia de cada
grupo de equipamentos), desenhada a partir das planilhas de acompanhamento e
aberta no navegador. Regras em `core/transpasse.py`."""
from __future__ import annotations

import webbrowser
from datetime import datetime
from pathlib import Path

from .. import dialogos
from ..components import Card, FileSelector, RunBar, rotulo
from .base import BaseView


class TranspasseView(BaseView):
    titulo_view = "Transpasse de Fase"
    subtitulo_view = ("Quadro dia a dia de cada grupo de equipamentos: convocação, inspeção IB, emissão do CCMLC, "
                      "transpasse de fase e início do comissionamento")

    def montar(self, body):
        cfg = self.ctx.config
        card = Card("Planilhas")
        self.sel_principal = card.add(FileSelector("Acompanhamento do transpasse", cfg, "transpasse",
                                                   escolher_aba=False))
        self.sel_complementar = card.add(FileSelector("Planilha complementar (opcional)", cfg,
                                                      "transpasse_complementar", escolher_aba=False))
        card.add(rotulo("A complementar é a de controle do início do comissionamento: traz a data em que a "
                        "manutenção começou (o preto do quadro) e, com ela, a coluna Dias. Também completa as "
                        "datas que faltarem na principal.", "suave", quebra=True))
        body.addWidget(card)

        self.run = RunBar("Gerar e Abrir Painel", self._tarefa, self.log)
        body.addWidget(self.run)

    def _tarefa(self, run: RunBar):
        if not self.sel_principal.path:
            self.log.log("Selecione a planilha de acompanhamento do transpasse.")
            return
        saida = dialogos.pedir_salvar(self.ctx.config, "transpasse_saida",
                                      f"Transpasse_de_Fase_{datetime.now():%d%m%y}.html",
                                      filtro="Página HTML (*.html)")
        if not saida:
            self.log.log("Salvamento cancelado.")
            return
        from ...transpasse_backend import gerar_painel_transpasse
        run.set_progress(0.3)
        r = gerar_painel_transpasse(self.sel_principal.path, saida, self.sel_complementar.path,
                                    log_cb=self.log.log)
        run.set_progress(1.0)
        self.log.log(r.mensagem)
        if r.ok:
            webbrowser.open(Path(saida).as_uri())
        else:
            dialogos.aviso("Transpasse de Fase", r.mensagem)
