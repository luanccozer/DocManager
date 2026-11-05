"""Upload de documentos: Documento novo, Para revisão e Para aprovação.

Agora só Para aprovação, e na Fase 1 (spec `.scratch/upload-aprovacao/spec.md`): a tela
faz um documento da tabela colada de cada vez: confere o código no Controle, acha o documento no Aconex e mostra
o que o robô vai fazer - sem gravar nada. A ferramenta Capturar telas grava as telas do
Box e do Aconex que a Fase 2 precisa (daqui não se vê nenhuma das duas).
"""
from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QSpinBox

from .. import dialogos
from ..components import LARGURA_ROTULO, Abas, Card, FileSelector, RunBar, linha, rotulo
from ..idioma import marcar, t
from ..ponte import na_ui_e_esperar
from .base import BaseView

_TAB_NOVO = marcar("Documento novo")
_TAB_REVISAO = marcar("Para revisão")
_TAB_APROVACAO = marcar("Para aprovação")


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
        lay.addWidget(rotulo(t("Tabela de envio (copie do e-mail e cole aqui, com ou sem o cabeçalho):")))
        self.tabela = QPlainTextEdit()
        self.tabela.setPlaceholderText(t("IDENTIFICAÇÃO DOCUMENTO CMI   IDENTIFICAÇÃO DOCUMENTO ITAIPU   …   "
                                         "REVISÃO   LINK GE BOX"))
        self.tabela.setMinimumHeight(110)
        self.tabela.textChanged.connect(self._contar)
        lay.addWidget(self.tabela)
        self.lbl_reconhecidos = rotulo("", "legenda", quebra=True)
        lay.addWidget(self.lbl_reconhecidos)
        self.sel_controle = FileSelector(t("ITAIPU Controle de Documentos"), cfg, "controle")
        lay.addWidget(self.sel_controle)
        nome_prazo = rotulo(t("Prazo do workflow (dias)"))
        nome_prazo.setMinimumWidth(LARGURA_ROTULO)
        self.prazo = QSpinBox()
        self.prazo.setRange(1, 365)
        self.prazo.setValue(10)
        lay.addWidget(linha(nome_prazo, self.prazo, esticar=None))
        lay.addWidget(rotulo(t("O robô faz um documento da tabela de cada vez, na ordem dela: confere o código no "
                               "Controle (precisa estar em 0C), acha o documento no Aconex e mostra o que vai "
                               "fazer. Nesta versão nada é enviado: a subida no Aconex e no Box chega depois do "
                               "mapeamento das telas."), "suave", quebra=True))
        self.run = RunBar(t("Iniciar"), self._tarefa, self.log)
        lay.addWidget(self.run)
        self._contar()

        mapa = Card(t("Mapear telas para o robô"))
        mapa.add(rotulo(t("Abre o Chrome do robô. Faça o envio à mão uma vez, com um documento de teste, e em "
                          "cada tela do Box e do Aconex aperte F8 (ou o botão Capturar, no canto): a tecla não "
                          "fecha menus abertos como o mouse. Ao fechar o Chrome, o DocManager junta tudo num "
                          ".zip para mandar: é com ele que o robô aprende os botões."), "suave", quebra=True))
        self.run_captura = RunBar(t("Capturar telas"), self._capturar, self.log)
        mapa.add(self.run_captura)
        lay.addWidget(mapa)
        lay.addStretch(1)

    # --- Para aprovação --------------------------------------------------------------

    def _documentos(self):
        from ...services.upload_envio import ler_tabela

        return ler_tabela(self.tabela.toPlainText())

    def _contar(self) -> None:
        docs = self._documentos()
        if not self.tabela.toPlainText().strip():
            self.lbl_reconhecidos.setText("")
        elif not docs:
            self.lbl_reconhecidos.setText(t("Nenhum documento reconhecido na tabela colada."))
        else:
            self.lbl_reconhecidos.setText(t("{n} documento(s) reconhecido(s): {codigos}", n=len(docs),
                                            codigos=", ".join(d.cod_cmi for d in docs)))

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
        documentos = na_ui_e_esperar(self._documentos)
        if not documentos:
            self.log.log("Cole a tabela de envio: nenhum documento foi reconhecido.")
            return
        if not self.sel_controle.path:
            self.log.log("Escolha o Controle de Documentos.")
            return
        config = self._config()
        if config is None:
            return
        from ...services.controle_docs import ler_controle
        from ...services.upload_aprovacao import preparar_aprovacao

        prazo = na_ui_e_esperar(self.prazo.value)   # widget: lido na thread da interface
        controle = ler_controle(self.sel_controle.path, self.sel_controle.sheet, log_cb=self.log.log)
        resultados = []
        for i, doc in enumerate(documentos, 1):
            self.log.log(f"--- Documento {i} de {len(documentos)}: {doc.cod_cmi} ---")
            r = preparar_aprovacao(config, doc, controle, prazo, log_cb=self.log.log,
                                   perguntar_cb=self._perguntar)
            resultados.append(r)
            run.set_progress(i / len(documentos))
        self.log.log("Ensaio concluído: nada foi enviado.")
        prontos = [r for r in resultados if r.ok]
        partes = [t("{ok} de {n} documento(s) prontos para o envio.", ok=len(prontos), n=len(resultados))]
        partes += [f"\n{r.resumo()}" for r in prontos]
        partes += [f"\n{r.codigo}: {r.mensagem}" for r in resultados if not r.ok]
        partes.append("\n" + t("Nesta versão nada foi enviado: a subida chega depois do mapeamento das telas."))
        caixa = dialogos.info if prontos else dialogos.aviso
        caixa(t("Upload para aprovação"), "\n".join(partes), self)

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
