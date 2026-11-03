"""Upload de documentos: Documento novo, Para revisão e Para aprovação.

Agora só Para aprovação, e na Fase 1 (spec `.scratch/upload-aprovacao/spec.md`): a tela
confere o código no arquivo de envio e no Controle, acha o documento no Aconex e mostra
o que o robô vai fazer - sem gravar nada. A ferramenta Capturar telas grava as telas do
Box e do Aconex que a Fase 2 precisa (daqui não se vê nenhuma das duas).
"""
from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QSpinBox

from .. import dialogos
from ..components import LARGURA_ROTULO, Abas, Card, FileSelector, RunBar, linha, rotulo
from ..idioma import marcar, t
from ..ponte import na_ui_e_esperar
from .base import BaseView

_TAB_NOVO = marcar("Documento novo")
_TAB_REVISAO = marcar("Para revisão")
_TAB_APROVACAO = marcar("Para aprovação")
FILTRO_ENVIO = "Word ou Excel (*.docx *.xlsx);;Word (*.docx);;Excel (*.xlsx)"


class UploadView(BaseView):
    titulo_view = marcar("Upload de documentos")
    subtitulo_view = marcar("O robô sobe documentos no Aconex a partir da pasta do Box: documento novo, "
                            "para revisão ou para aprovação")

    def montar(self, body):
        card = Card()
        self.tabs = Abas()
        for nome, icone in ((_TAB_NOVO, "file"), (_TAB_REVISAO, "pencil")):
            aba = self.tabs.add(nome, icone)
            aba.layout().addWidget(rotulo(t("Em breve: por enquanto o robô faz só o envio para aprovação."),
                                          "suave", quebra=True))
            aba.layout().addStretch(1)
        self._montar_aprovacao(self.tabs.add(_TAB_APROVACAO, "check"))
        self.tabs.set(_TAB_APROVACAO)
        card.add(self.tabs)
        body.addWidget(card)

    def _montar_aprovacao(self, aba):
        lay = aba.layout()
        cfg = self.ctx.config
        self.sel_envio = FileSelector(t("Arquivo de envio (código CMI e link do Box)"), cfg, "upload_envio",
                                      filtro=FILTRO_ENVIO, escolher_aba=False)
        self.sel_controle = FileSelector(t("ITAIPU Controle de Documentos"), cfg, "controle")
        lay.addWidget(self.sel_envio)
        lay.addWidget(self.sel_controle)
        nome_prazo = rotulo(t("Prazo do workflow (dias)"))
        nome_prazo.setMinimumWidth(LARGURA_ROTULO)
        self.prazo = QSpinBox()
        self.prazo.setRange(1, 365)
        self.prazo.setValue(10)
        lay.addWidget(linha(nome_prazo, self.prazo, esticar=None))
        lay.addWidget(rotulo(t("Ao iniciar, cole o código CMI do documento. O robô confere o código no "
                               "arquivo de envio e no Controle (precisa estar em 0C), acha o documento no "
                               "Aconex e mostra o que vai fazer. Nesta versão nada é enviado: a subida no "
                               "Aconex e no Box chega depois do mapeamento das telas."), "suave", quebra=True))
        self.run = RunBar(t("Iniciar"), self._tarefa, self.log)
        lay.addWidget(self.run)

        mapa = Card(t("Mapear telas para o robô"))
        mapa.add(rotulo(t("Abre o Chrome do robô com um botão 'Capturar'. Faça o envio à mão uma vez, com um "
                          "documento de teste, e aperte Capturar em cada tela do Box e do Aconex. Ao fechar "
                          "o Chrome, o DocManager junta tudo num .zip para mandar: é com ele que o robô "
                          "aprende os botões."), "suave", quebra=True))
        self.run_captura = RunBar(t("Capturar telas"), self._capturar, self.log)
        mapa.add(self.run_captura)
        lay.addWidget(mapa)
        lay.addStretch(1)

    # --- Para aprovação --------------------------------------------------------------

    def _pedir_codigo(self) -> str:
        texto, ok = QInputDialog.getText(self.window(), t("Código CMI"),
                                         t("Cole o código CMI do documento:"))
        return texto.strip() if ok else ""

    def _perguntar(self, mensagem: str) -> bool:
        return dialogos.perguntar(t("Upload para aprovação"), mensagem, padrao_nao=True, parent=self)

    def _config(self):
        """O usuário do Aconex já cadastrado, o primeiro (a regra da extração sem janela)."""
        from ...aconex_backend import AconexConfig, usuarios_disponiveis

        nomes = usuarios_disponiveis()
        if not nomes:
            self.log.log("Nenhum usuário do Aconex cadastrado: cadastre em Configurações → Credenciais.")
            return None
        try:
            return AconexConfig.para_usuario(nomes[0])
        except (KeyError, ValueError) as e:
            self.log.log(f"Credencial do Aconex: {e}")
            return None

    def _tarefa(self, run: RunBar):
        if not self.sel_envio.path or not self.sel_controle.path:
            self.log.log("Escolha o arquivo de envio e o Controle de Documentos.")
            return
        codigo = na_ui_e_esperar(self._pedir_codigo)
        if not codigo:
            self.log.log("Nenhum código informado.")
            return
        config = self._config()
        if config is None:
            return
        from ...services.upload_aprovacao import preparar_aprovacao

        prazo = na_ui_e_esperar(self.prazo.value)   # widget: lido na thread da interface
        run.set_progress(0.2)
        r = preparar_aprovacao(config, self.sel_envio.path, self.sel_controle.path, codigo,
                               prazo, aba_controle=self.sel_controle.sheet,
                               log_cb=self.log.log, perguntar_cb=self._perguntar)
        run.set_progress(1.0)
        if not r.ok:
            dialogos.aviso(t("Upload para aprovação"), r.mensagem, self)
            return
        self.log.log("Ensaio concluído: nada foi enviado.")
        dialogos.info(t("Upload para aprovação"),
                      t("Tudo conferido. O robô faria isto:\n\n{resumo}\n\nNesta versão nada foi enviado: "
                        "a subida chega depois do mapeamento das telas.", resumo=r.resumo()), self)

    # --- Capturar telas --------------------------------------------------------------

    def _capturar(self, run: RunBar):
        from ...services.navegador import ErroNavegador, capturar_telas

        try:
            arquivo = capturar_telas(log_cb=self.log.log)
        except ErroNavegador as e:
            dialogos.aviso(t("Capturar telas"), str(e), self)
            return
        if arquivo is not None:
            dialogos.info(t("Capturar telas"),
                          t("As telas foram guardadas em:\n{arquivo}\n\nMande esse arquivo para quem está "
                            "programando o robô.", arquivo=str(arquivo)), self)
