from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from .. import dialogos
from ..components import Abas, Card, RunBar, Seletor, botao, linha, rotulo
from ..ponte import na_ui, na_ui_e_esperar
from .base import BaseView


class AconexView(BaseView):
    titulo_view = "Extração Aconex (API)"
    subtitulo_view = "Baixa o histórico completo do projeto direto da API do Aconex"

    # Períodos da extração incremental de fluxos: rótulo → dias (None = tudo).
    PERIODOS_FLUXO = {
        "Tudo (~20 min)": None,
        "Últimos 7 dias": 7,
        "Últimos 30 dias": 30,
        "Últimos 12 meses": 365,
    }

    def montar(self, body):
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import OUTRO_USUARIO, usuarios_disponiveis
        self._OUTRO = OUTRO_USUARIO
        self._pasta_download: str | None = None

        card = Card("Credenciais (valem para as três abas)")
        # A lista sai do CADASTRO feito no app (antes vinha do .env, que ninguém
        # mais recebe: desde a v3.1.0 o app é instalado, não descompactado).
        disponiveis = usuarios_disponiveis()
        self._usuarios_conhecidos = list(disponiveis)
        self.opt_user = Seletor(disponiveis + [OUTRO_USUARIO])
        self.opt_user.setMinimumWidth(260)
        self.opt_user.setCurrentText(disponiveis[0] if disponiveis else OUTRO_USUARIO)
        self.opt_user.currentTextChanged.connect(self._on_user)
        usuario = rotulo("Usuário")
        usuario.setFixedWidth(120)
        card.add(linha(usuario, self.opt_user,
                       botao("Cadastrar usuário", variante="primario", icone="user-plus",
                             ao_clicar=self._cadastrar),
                       botao("Editar", icone="pencil", ao_clicar=self._editar)))

        # Chamada para quem ainda não cadastrou nada: sem ela a tela fica com um
        # seletor vazio e nenhuma pista do que fazer.
        self._aviso_cadastro = card.add(rotulo("", "aviso", quebra=True))

        # Entrada manual (visível só quando "Outro" é escolhido) - não é salva.
        self._manual = QWidget()
        ml = QVBoxLayout(self._manual)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(6)
        self.entry_client = QLineEdit(placeholderText="Client ID (APP ID) do Aconex")
        self.entry_userid = QLineEdit(placeholderText="User ID (numérico) do Aconex")
        self.entry_secret = QLineEdit(placeholderText="Client Secret")
        self.entry_secret.setEchoMode(QLineEdit.EchoMode.Password)
        for w in (self.entry_client, self.entry_userid, self.entry_secret):
            ml.addWidget(w)
        card.add(self._manual)

        self.entry_proxy = card.add(QLineEdit(
            placeholderText="Proxy (opcional). Em branco, o app detecta sozinho."))
        self._dica = card.add(rotulo("", "legenda", quebra=True))
        body.addWidget(card)

        # Guias do módulo: extração completa, fluxos de trabalho e download por lista.
        abas_card = Card()
        self.tabs = Abas()
        self._montar_aba_extracao(self.tabs.add("Extração Completa", "download"))
        self._montar_aba_fluxos(self.tabs.add("Fluxos de Trabalho", "workflow"))
        self._montar_aba_download(self.tabs.add("Baixar por Lista", "file"))
        abas_card.add(self.tabs)
        body.addWidget(abas_card)
        self._on_user(self.opt_user.get())   # visibilidade, dica e aviso iniciais

    def _montar_aba_extracao(self, aba):
        aba.layout().addWidget(rotulo(
            "Baixa o histórico completo do projeto (todas as revisões, com Tracking ID) para um Excel. "
            "Leva vários minutos e retoma de onde parou se a conexão cair.", "suave", quebra=True))
        self.run = RunBar("Iniciar Extração", self._tarefa, self.log)
        aba.layout().addWidget(self.run)

    def _montar_aba_fluxos(self, aba):
        lay = aba.layout()
        lay.addWidget(rotulo(
            "Baixa os FLUXOS DE TRABALHO (a aba 'Fluxos de Trabalho' do Aconex): etapa, prazo e a quem "
            "cada documento está atribuído. Um período curto atualiza rápido, porque baixa só o que "
            "mudou desde então.", "suave", quebra=True))
        self.opt_periodo_fluxo = Seletor(list(self.PERIODOS_FLUXO))
        self.opt_periodo_fluxo.setMinimumWidth(200)
        periodo = rotulo("Período")
        periodo.setFixedWidth(120)
        lay.addWidget(linha(periodo, self.opt_periodo_fluxo))
        lay.addWidget(RunBar("Extrair Fluxos de Trabalho", self._tarefa_fluxos, self.log))

    def _montar_aba_download(self, aba):
        lay = aba.layout()
        lay.addWidget(rotulo("Cole os códigos Itaipu, um por linha. Baixa a versão atual (current) de "
                             "cada documento para a pasta escolhida.", "suave", quebra=True))
        self.txt_codigos = QPlainTextEdit()
        self.txt_codigos.setObjectName("caixa_texto")
        self.txt_codigos.setFixedHeight(140)
        lay.addWidget(self.txt_codigos)
        self.lbl_pasta = rotulo("Nenhuma pasta escolhida", "suave")
        lay.addWidget(linha(botao("Escolher pasta", icone="folder-open", ao_clicar=self._escolher_pasta),
                            self.lbl_pasta, esticar=1))
        lay.addWidget(RunBar("Baixar Documentos", self._tarefa_download, self.log))

    def _escolher_pasta(self):
        pasta = dialogos.escolher_pasta(self.ctx.config, "download",
                                        "Pasta para salvar os documentos", parent=self)
        if pasta:
            self._pasta_download = pasta
            self.lbl_pasta.setText(pasta)

    # ------------------------------------------------------------------ estado
    def _estado(self) -> dict:
        """Foto da tela, lida na thread da interface (as tarefas rodam em outra)."""
        return {"usuario": self.opt_user.get(), "proxy": self.entry_proxy.text().strip(),
                "client_id": self.entry_client.text().strip(), "user_id": self.entry_userid.text().strip(),
                "secret": self.entry_secret.text().strip(), "periodo": self.opt_periodo_fluxo.get(),
                "codigos": self.txt_codigos.toPlainText()}

    def _on_user(self, escolha: str):
        """Mostra os campos manuais só na opção 'Outro'; ajusta a dica."""
        if escolha == self._OUTRO:
            self._manual.show()
            self._dica.setText("Entrada manual: informe os 3 dados do usuário do Aconex. Valem só para "
                               "esta extração e não são salvos. Para guardar de vez, use 'Cadastrar usuário'.")
        else:
            self._manual.hide()
            self._dica.setText("O Client Secret está guardado nesta máquina, cifrado pelo Windows. "
                               "Para trocá-lo, use 'Editar'.")
        self._atualizar_aviso()

    def manual_visivel(self) -> bool:
        return not self._manual.isHidden()

    def _atualizar_aviso(self):
        """Texto de chamada quando ainda não há nenhum usuário cadastrado."""
        from ...aconex_backend import usuarios_disponiveis

        if usuarios_disponiveis():
            self._aviso_cadastro.hide()
            return
        self._aviso_cadastro.setText(
            "Nenhum usuário cadastrado ainda. Clique em CADASTRAR USUÁRIO e informe o Client ID "
            "(APP ID), o User ID e o Client Secret que o administrador do Aconex passou para você. "
            "É uma vez só: fica guardado nesta máquina e continua valendo depois das atualizações.")
        self._aviso_cadastro.show()

    # --- cadastro das credenciais -------------------------------------------
    def ao_exibir(self):
        # O cadastro também é feito nas Configurações, com esta tela já criada:
        # sem reler aqui, o usuário novo não aparecia na lista da Extração.
        self._recarregar_usuarios()

    def _manual_preenchido(self) -> bool:
        return any(w.text().strip() for w in (self.entry_client, self.entry_userid, self.entry_secret))

    def _recarregar_usuarios(self, selecionar: str | None = None):
        from ...aconex_backend import escolher_usuario, usuarios_disponiveis

        disponiveis = usuarios_disponiveis()
        alvo = escolher_usuario(disponiveis, atual=selecionar or self.opt_user.get(),
                                conhecidos=self._usuarios_conhecidos,
                                manual_preenchido=self._manual_preenchido())
        self._usuarios_conhecidos = list(disponiveis)
        self.opt_user.definir_itens(disponiveis + [self._OUTRO], alvo)
        self._on_user(alvo)

    def usuarios_na_lista(self) -> list[str]:
        return [self.opt_user.itemText(i) for i in range(self.opt_user.count())]

    def _cadastrar(self, nome: str | None = None):
        """Abre o cadastro. Só pode ser chamado na thread da interface."""
        from .credenciais_dialog import cadastrar

        salvo = cadastrar(self.window(), nome)
        if salvo:
            self._recarregar_usuarios(salvo)
            self.log.log(f"Credenciais de '{salvo}' salvas nesta máquina.")
        return salvo

    def _editar(self):
        escolha = self.opt_user.get()
        self._cadastrar(None if escolha == self._OUTRO else escolha)

    def _garantir_credenciais(self, estado) -> bool:
        """Checa, ANTES de gastar tempo, se há com o que autenticar. Roda na
        thread da tarefa: o cadastro abre na thread da interface."""
        from ...aconex_backend import usuarios_disponiveis

        if usuarios_disponiveis() or estado["usuario"] == self._OUTRO:
            return True
        self.log.log("Nenhum usuário do Aconex cadastrado - abrindo o cadastro.")
        na_ui(self._cadastrar)
        return False

    def _montar_config(self, estado: dict | None = None):
        """Monta a AconexConfig conforme a escolha (conhecido ou manual)."""
        from ...aconex_backend import AconexConfig
        estado = estado or self._estado()
        proxy = estado["proxy"] or None
        if estado["usuario"] == self._OUTRO:
            if not (estado["client_id"] and estado["user_id"] and estado["secret"]):
                raise ValueError("Preencha Client ID, User ID e Secret para o usuário manual.")
            return AconexConfig(client_id=estado["client_id"], client_secret=estado["secret"],
                                user_id=estado["user_id"], proxy=proxy)
        return AconexConfig.para_usuario(estado["usuario"], proxy=proxy)

    def _preparar(self):
        """(estado, config) para uma tarefa, ou None se faltar credencial."""
        estado = na_ui_e_esperar(self._estado)
        if not self._garantir_credenciais(estado):
            return None
        from dotenv import load_dotenv
        load_dotenv()
        try:
            return estado, self._montar_config(estado)
        except (KeyError, ValueError) as e:
            self.log.log(f"ERRO: {e}")
            return None

    # ------------------------------------------------------------------ tarefas
    def _tarefa_fluxos(self, run: RunBar):
        if (prep := self._preparar()) is None:
            return
        estado, config = prep
        from datetime import datetime, timedelta, timezone

        from ...workflows_backend import (
            extrair_workflows,
            limpar_checkpoint_wf,
            nome_arquivo_padrao_wf,
            salvar_excel_workflows,
        )
        dias = self.PERIODOS_FLUXO.get(estado["periodo"])
        updated_after = ""
        if dias:
            updated_after = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.log.log(f"Extração incremental: fluxos alterados nos últimos {dias} dias.")
        run.set_progress(0.05)
        r = extrair_workflows(config, log_cb=self.log.log, updated_after=updated_after,
                              progress_cb=run.set_progress)
        if r.df.empty:
            self.log.log("Nenhum fluxo retornado.")
            return
        if not r.completa:
            self.log.log(f"ATENÇÃO: base PARCIAL ({r.motivo}).")
            if not dialogos.perguntar(
                    "Extração incompleta",
                    f"A extração parou antes do fim ({r.motivo}).\n\n"
                    f"{len(r.df)} linhas ficaram salvas para retomada - rode de novo que ela "
                    f"continua da página {r.paginas + 1}.\n\n"
                    "Quer salvar agora um Excel com o que já veio (base PARCIAL)?"):
                self.log.log("Excel parcial não gerado. O progresso segue guardado para retomar.")
                return
        saida = dialogos.pedir_salvar(self.ctx.config, "saida", nome_arquivo_padrao_wf())
        if not saida:
            self.log.log("Salvamento cancelado. O progresso da extração continua guardado.")
            return
        salvar_excel_workflows(r.df, saida)
        run.set_progress(1.0)
        if r.completa:
            limpar_checkpoint_wf(config, updated_after=updated_after)
            self.log.log(f"Concluído: {len(r.df)} fluxos salvos.")
            dialogos.info("Fluxos de Trabalho", f"{len(r.df)} linhas de fluxo salvas.")

    def _tarefa_download(self, run: RunBar):
        if (prep := self._preparar()) is None:
            return
        estado, config = prep
        from ...aconex_backend import baixar_documentos
        codigos = [c.strip() for c in estado["codigos"].splitlines() if c.strip()]
        if not codigos:
            self.log.log("Cole ao menos um código na aba 'Baixar por Lista'.")
            return
        if not self._pasta_download:
            self.log.log("Escolha a pasta de destino.")
            return
        run.set_progress(0.05)
        res = baixar_documentos(config, codigos, self._pasta_download,
                                log_cb=self.log.log, progress_cb=run.set_progress)
        run.set_progress(1.0)
        resumo = f"{res.baixados}/{res.total} documento(s) baixado(s) em:\n{res.pasta}"
        if res.nao_encontrados:
            resumo += f"\n\n{len(res.nao_encontrados)} não encontrado(s)."
        if res.sem_arquivo or res.erros:
            resumo += f"\n{len(res.sem_arquivo)} sem arquivo, {len(res.erros)} com erro."
        dialogos.info("Download Aconex", resumo)

    def _tarefa(self, run: RunBar):
        if (prep := self._preparar()) is None:
            return
        _estado, config = prep
        from ...aconex_backend import (
            checkpoint_pendente,
            extrair_base,
            limpar_checkpoint,
            nome_arquivo_padrao,
            salvar_excel,
        )
        pendente = checkpoint_pendente(config)
        if pendente is not None:
            self.log.log(f"Há uma extração interrompida em {pendente.atualizado_em} com "
                         f"{pendente.total} registros - será retomada da página {pendente.proxima_pagina}.")
        run.set_progress(0.05)
        self.log.log("Extração iniciada (pode levar vários minutos)...")
        r = extrair_base(config, log_cb=self.log.log, progress_cb=run.set_progress)

        if r.df.empty:
            self.log.log("Nenhum dado retornado.")
            if not r.completa:
                dialogos.aviso("Extração Aconex", f"A extração não foi concluída ({r.motivo}).\n\n"
                               "Rode de novo para continuar de onde parou.")
            return
        if not r.completa:
            self.log.log(f"ATENÇÃO: base PARCIAL ({r.motivo}).")
            if not dialogos.perguntar(
                    "Extração incompleta",
                    f"A extração parou antes do fim ({r.motivo}).\n\n"
                    f"{len(r.df)} linhas foram baixadas e ficaram salvas para retomada - basta rodar de "
                    f"novo que ela continua da página {r.paginas + 1}.\n\n"
                    "Quer salvar agora um Excel com o que já veio (base PARCIAL)?"):
                self.log.log("Excel parcial não gerado. O progresso segue guardado para retomar.")
                return
        saida = dialogos.pedir_salvar(self.ctx.config, "saida", nome_arquivo_padrao())
        if not saida:
            self.log.log("Salvamento cancelado. O progresso da extração continua guardado.")
            return
        salvar_excel(r.df, saida)
        run.set_progress(1.0)
        if r.completa:
            # Só descarta o checkpoint depois que o Excel está em disco.
            limpar_checkpoint(config)
            self.log.log(f"Concluído: {len(r.df)} linhas salvas.")
            dialogos.info("Extração Aconex", f"{len(r.df)} linhas extraídas.")
        else:
            self.log.log(f"Excel PARCIAL salvo com {len(r.df)} linhas. "
                         f"Rode a extração de novo para completar.")
