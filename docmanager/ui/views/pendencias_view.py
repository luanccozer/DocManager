"""Pendências: a planilha de mapeamento de pendências de comissionamento,
atualizada direto do Aconex (Campo → Questões). Regras em
`services/pendencias_update.py` (KB §32).

A tela faz só isto: escolher a planilha JÁ dispara a atualização, que grava sem
pergunta final (a segurança vem da conferência, da cópia de segurança e da troca
atômica). A única pergunta possível é a dos valores que o Aconex não tem mais.
"""
from __future__ import annotations

from .. import dialogos
from ..components import Card, FileSelector, RunBar, rotulo
from ..idioma import marcar, t
from ..ponte import na_ui_e_esperar
from .base import BaseView
from .sobrescricao_dialog import TextosSobrescricao, decidir_sobrescricoes


def _resumo_apagamentos(pendentes) -> str:
    n = len(pendentes)
    if n == 1:
        return t("1 célula tem valor na planilha, mas está vazia no Aconex.")
    return t("{n} células têm valor na planilha, mas estão vazias no Aconex.", n=n)


def _vazio(_item) -> str:
    return t("(vazio)")


TEXTOS_PENDENCIAS = TextosSobrescricao(
    titulo=marcar("Valores que o Aconex não tem mais"),
    resumo=_resumo_apagamentos,
    aviso=marcar("O que você mantiver não é perguntado de novo enquanto o valor for o mesmo."),
    colunas=((marcar("Pendência"), 90), (marcar("Descrição"), 380), (marcar("Coluna"), 220),
             (marcar("Na planilha"), 200), (marcar("No Aconex"), 100)),
    aceitar=marcar("Apagar todas"),
    recusar=marcar("Manter todas"),
    caso_a_caso=marcar("Ver caso a caso"),
    titulo_caso=marcar("Escolher quais valores apagar"),
    instrucao_caso=marcar("Marque os valores que devem ser apagados, como no Aconex. Os desmarcados "
                          "ficam na planilha e não são perguntados de novo enquanto o valor for o mesmo."),
    confirmar_caso=marcar("Apagar os marcados"),
    valor_novo=_vazio,
)


class PendenciasView(BaseView):
    titulo_view = marcar("Pendências")
    subtitulo_view = marcar("Planilha de mapeamento de pendências de comissionamento, atualizada direto do "
                            "Aconex (Campo → Questões)")

    def montar(self, body):
        card = Card(t("Planilha"))
        self.sel = card.add(FileSelector(t("Planilha de pendências"), self.ctx.config, "pendencias",
                                         filtro=dialogos.FILTRO_XLSX, escolher_aba=False,
                                         on_change=self._ao_escolher))
        card.add(rotulo(t("Ao escolher a planilha, o DocManager busca as pendências no Aconex e já grava: "
                          "as novas entram no topo, as colunas do Aconex das que já estão na planilha "
                          "são atualizadas e as colunas preenchidas à mão não são tocadas. Impeditivas "
                          "não fechadas ficam em vermelho, e o que a atualização trouxe fica em azul. "
                          "Antes de trocar o arquivo, o app "
                          "confere o resultado e guarda uma cópia de segurança. Abra no Excel para as "
                          "tabelas dinâmicas e os gráficos se atualizarem."), "suave", quebra=True))
        body.addWidget(card)

        self.run = RunBar(t("Atualizar Pendências"), self._tarefa, self.log)
        body.addWidget(self.run)

    def _ao_escolher(self, _caminho: str) -> None:
        self.run.btn.click()

    def _config(self):
        """O usuário do Aconex já cadastrado, o primeiro da lista (a regra da extração
        sem janela); sem nenhum, abre o cadastro. None se não houver como seguir."""
        from ...aconex_backend import AconexConfig, usuarios_disponiveis
        from .credenciais_dialog import cadastrar

        nomes = usuarios_disponiveis()
        if not nomes:
            self.log.log("Nenhum usuário do Aconex cadastrado: abrindo o cadastro.")
            na_ui_e_esperar(self._cadastrar, cadastrar)
            nomes = usuarios_disponiveis()
            if not nomes:
                self.log.log("Sem usuário do Aconex cadastrado, não há como buscar as pendências.")
                return None
        try:
            return AconexConfig.para_usuario(nomes[0])
        except (KeyError, ValueError) as e:
            self.log.log(f"Credencial do Aconex: {e}")
            return None

    def _cadastrar(self, cadastrar):
        return cadastrar(self.window())

    def _decidir(self, itens):
        return decidir_sobrescricoes(itens, self, textos=TEXTOS_PENDENCIAS)

    def _tarefa(self, run: RunBar):
        if not self.sel.path:
            self.log.log("Selecione a planilha de pendências.")
            return
        config = self._config()
        if config is None:
            return
        from ...services.pendencias_update import atualizar_pendencias

        r = atualizar_pendencias(config, self.sel.path, log_cb=self.log.log,
                                 progress_cb=run.set_progress,
                                 retry_cb=lambda m: dialogos.tentar_de_novo(t("Salvar"), m),
                                 decidir_cb=self._decidir)
        if r.ok:
            dialogos.info(t("Pendências"), r.mensagem, self)
        else:
            dialogos.erro(t("Pendências"), r.mensagem, self)
