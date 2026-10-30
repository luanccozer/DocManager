from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QLineEdit, QPlainTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .. import dialogos
from ..components import Abas, Card, RunBar, Seletor, botao, linha, rotulo
from ..ponte import na_ui, na_ui_e_esperar
from .base import BaseView
from ..idioma import marcar, t


class AconexView(BaseView):
    titulo_view = marcar("Extração Aconex (API)")
    subtitulo_view = marcar("Baixa o histórico completo do projeto direto da API do Aconex")

    # Períodos da extração incremental de fluxos: rótulo → dias (None = tudo).
    PERIODOS_FLUXO = {
        marcar("Tudo (~20 min)"): None,
        marcar("Últimos 7 dias"): 7,
        marcar("Últimos 30 dias"): 30,
        marcar("Últimos 12 meses"): 365,
    }

    # Qual arquivo a "Baixar por Lista" traz: rótulo → modo do backend.
    MODOS_DOWNLOAD = {
        marcar("Com os comentários do Aconex (versão vigente)"): "marcado",
        marcar("Original, sem comentários (como o emitente subiu)"): "original",
    }
    # Chaves do resultado da consulta; o cabeçalho da tabela mostra `t(...)`.
    COLUNAS_CONSULTA = (marcar("Código Itaipu"), marcar("Código CMI"), marcar("Título"), marcar("Revisão"),
                        marcar("Data"), marcar("Status Aconex"), marcar("Status Real"))

    def montar(self, body):
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import OUTRO_USUARIO, usuarios_disponiveis
        self._OUTRO = OUTRO_USUARIO
        self._pasta_download: str | None = None

        card = Card(t("Credenciais (valem para todas as abas)"))
        # A lista sai do CADASTRO feito no app (antes vinha do .env, que ninguém
        # mais recebe: desde a v3.1.0 o app é instalado, não descompactado).
        disponiveis = usuarios_disponiveis()
        self._usuarios_conhecidos = list(disponiveis)
        self.opt_user = Seletor(disponiveis + [OUTRO_USUARIO])
        self.opt_user.setMinimumWidth(260)
        self.opt_user.setCurrentText(disponiveis[0] if disponiveis else OUTRO_USUARIO)
        self.opt_user.currentTextChanged.connect(self._on_user)
        usuario = rotulo(t("Usuário"))
        usuario.setFixedWidth(120)
        card.add(linha(usuario, self.opt_user,
                       botao(t("Cadastrar usuário"), variante="primario", icone="user-plus",
                             ao_clicar=self._cadastrar),
                       botao(t("Editar"), icone="pencil", ao_clicar=self._editar)))

        # Chamada para quem ainda não cadastrou nada: sem ela a tela fica com um
        # seletor vazio e nenhuma pista do que fazer.
        self._aviso_cadastro = card.add(rotulo("", "aviso", quebra=True))

        # Entrada manual (visível só quando "Outro" é escolhido) - não é salva.
        self._manual = QWidget()
        ml = QVBoxLayout(self._manual)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(6)
        self.entry_client = QLineEdit(placeholderText=t("Client ID (APP ID) do Aconex"))
        self.entry_userid = QLineEdit(placeholderText=t("User ID (numérico) do Aconex"))
        self.entry_secret = QLineEdit(placeholderText=t("Client Secret"))
        self.entry_secret.setEchoMode(QLineEdit.EchoMode.Password)
        for w in (self.entry_client, self.entry_userid, self.entry_secret):
            ml.addWidget(w)
        card.add(self._manual)

        self.entry_proxy = card.add(QLineEdit(
            placeholderText=t("Proxy (opcional). Em branco, o app detecta sozinho.")))
        self._dica = card.add(rotulo("", "legenda", quebra=True))
        body.addWidget(card)

        # Guias do módulo: extração completa, fluxos de trabalho e download por lista.
        abas_card = Card()
        self.tabs = Abas()
        self._montar_aba_consulta(self.tabs.add(marcar("Consulta Rápida"), "search"))
        self._montar_aba_extracao(self.tabs.add(marcar("Extração Completa"), "download"))
        self._montar_aba_fluxos(self.tabs.add(marcar("Fluxos de Trabalho"), "workflow"))
        self._montar_aba_download(self.tabs.add(marcar("Baixar por Lista"), "file"))
        abas_card.add(self.tabs)
        body.addWidget(abas_card)
        self._on_user(self.opt_user.get())   # visibilidade, dica e aviso iniciais

    def _montar_aba_consulta(self, aba):
        """Status e histórico de uma lista de códigos em segundos, direto da API
        - sem baixar a base completa (melhoria trazida do Corella Suite)."""
        lay = aba.layout()
        lay.addWidget(rotulo(
            t("Cole os códigos (Itaipu ou CMI), um por linha. O app consulta só esses documentos na API, "
            "com o histórico, e mostra o status real - sem baixar a base completa. Para relatórios "
            "oficiais, use a base completa: se um documento trocou de código, as versões com o código "
            "antigo não entram na consulta."), "suave", quebra=True))
        self.txt_consulta = QPlainTextEdit()
        self.txt_consulta.setObjectName("caixa_texto")
        self.txt_consulta.setFixedHeight(110)
        lay.addWidget(self.txt_consulta)
        lay.addWidget(RunBar(t("Consultar"), self._tarefa_consulta, self.log))
        self.tabela_consulta = QTreeWidget()
        self.tabela_consulta.setRootIsDecorated(False)
        self.tabela_consulta.setAlternatingRowColors(True)
        self.tabela_consulta.setHeaderLabels([t(c) for c in self.COLUNAS_CONSULTA])
        self.tabela_consulta.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, largura in enumerate((200, 200, 260, 70, 90, 160)):
            self.tabela_consulta.setColumnWidth(i, largura)
        self.tabela_consulta.setMinimumHeight(220)
        self.tabela_consulta.hide()
        lay.addWidget(self.tabela_consulta)
        self.btn_exportar_consulta = botao(t("Exportar Excel"), icone="file-spreadsheet",
                                           ao_clicar=self._exportar_consulta)
        self.btn_exportar_consulta.setEnabled(False)
        lay.addWidget(linha(self.btn_exportar_consulta))
        self._consulta = None   # (linhas, contador, tem_modelos) da última consulta

    def _montar_aba_extracao(self, aba):
        aba.layout().addWidget(rotulo(
            t("Baixa o histórico completo do projeto (todas as revisões, com Tracking ID) para um Excel. "
            "Leva vários minutos e retoma de onde parou se a conexão cair."), "suave", quebra=True))
        self.run = RunBar(t("Iniciar Extração"), self._tarefa, self.log)
        aba.layout().addWidget(self.run)

    def _montar_aba_fluxos(self, aba):
        lay = aba.layout()
        lay.addWidget(rotulo(
            t("Baixa os FLUXOS DE TRABALHO (a aba 'Fluxos de Trabalho' do Aconex): etapa, prazo e a quem "
            "cada documento está atribuído. Um período curto atualiza rápido, porque baixa só o que "
            "mudou desde então."), "suave", quebra=True))
        self.opt_periodo_fluxo = Seletor([t(k) for k in self.PERIODOS_FLUXO])
        self.opt_periodo_fluxo.setMinimumWidth(200)
        periodo = rotulo(t("Período"))
        periodo.setFixedWidth(120)
        lay.addWidget(linha(periodo, self.opt_periodo_fluxo))
        lay.addWidget(RunBar(t("Extrair Fluxos de Trabalho"), self._tarefa_fluxos, self.log))

    def _montar_aba_download(self, aba):
        lay = aba.layout()
        lay.addWidget(rotulo(t("Cole os códigos Itaipu, um por linha. Baixa um arquivo de cada documento "
                             "para a pasta escolhida."), "suave", quebra=True))
        self.txt_codigos = QPlainTextEdit()
        self.txt_codigos.setObjectName("caixa_texto")
        self.txt_codigos.setFixedHeight(140)
        lay.addWidget(self.txt_codigos)
        self.opt_modo_download = Seletor([t(k) for k in self.MODOS_DOWNLOAD])
        self.opt_modo_download.setMinimumWidth(380)
        arquivo = rotulo(t("Arquivo"))
        arquivo.setFixedWidth(120)
        lay.addWidget(linha(arquivo, self.opt_modo_download))
        lay.addWidget(rotulo(
            t("Com comentários: a versão vigente, com as marcações da análise aplicadas (o de sempre). "
            "Original: a última revisão na versão que o emitente enviou, sem as marcações - quando a "
            "revisão só tem versão comentada, vem a vigente sem as marcações, e o log avisa."),
            "legenda", quebra=True))
        self.lbl_pasta = rotulo(t("Nenhuma pasta escolhida"), "suave")
        lay.addWidget(linha(botao(t("Escolher pasta"), icone="folder-open", ao_clicar=self._escolher_pasta),
                            self.lbl_pasta, esticar=1))
        lay.addWidget(RunBar(t("Baixar Documentos"), self._tarefa_download, self.log))

    def _escolher_pasta(self):
        pasta = dialogos.escolher_pasta(self.ctx.config, "download",
                                        t("Pasta para salvar os documentos"), parent=self)
        if pasta:
            self._pasta_download = pasta
            self.lbl_pasta.setText(pasta)

    # ------------------------------------------------------------------ estado
    def _estado(self) -> dict:
        """Foto da tela, lida na thread da interface (as tarefas rodam em outra)."""
        return {"usuario": self.opt_user.get(), "proxy": self.entry_proxy.text().strip(),
                "client_id": self.entry_client.text().strip(), "user_id": self.entry_userid.text().strip(),
                "secret": self.entry_secret.text().strip(), "periodo": self.opt_periodo_fluxo.get(),
                "codigos": self.txt_codigos.toPlainText(),
                "modo_download": {t(k): v for k, v in self.MODOS_DOWNLOAD.items()}[self.opt_modo_download.get()],
                "consulta": self.txt_consulta.toPlainText()}

    def _on_user(self, escolha: str):
        """Mostra os campos manuais só na opção 'Outro'; ajusta a dica."""
        if escolha == self._OUTRO:
            self._manual.show()
            self._dica.setText(t("Entrada manual: informe os 3 dados do usuário do Aconex. Valem só para "
                               "esta extração e não são salvos. Para guardar de vez, use 'Cadastrar usuário'."))
        else:
            self._manual.hide()
            self._dica.setText(t("O Client Secret está guardado nesta máquina, cifrado pelo Windows. "
                               "Para trocá-lo, use 'Editar'."))
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
            t("Nenhum usuário cadastrado ainda. Clique em CADASTRAR USUÁRIO e informe o Client ID "
            "(APP ID), o User ID e o Client Secret que o administrador do Aconex passou para você. "
            "É uma vez só: fica guardado nesta máquina e continua valendo depois das atualizações."))
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
                raise ValueError(t("Preencha Client ID, User ID e Secret para o usuário manual."))
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
        dias = {t(k): v for k, v in self.PERIODOS_FLUXO.items()}.get(estado["periodo"])
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
                    t("Extração incompleta"),
                    t('A extração parou antes do fim ({motivo}).\n\n{n_df} linhas ficaram salvas para retomada - rode de novo que ela continua da página {valor}.\n\nQuer salvar agora um Excel com o que já veio (base PARCIAL)?', motivo=r.motivo, n_df=len(r.df), valor=r.paginas + 1)):
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
            dialogos.info(t("Fluxos de Trabalho"), t('{n_df} linhas de fluxo salvas.', n_df=len(r.df)))

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
        res = baixar_documentos(config, codigos, self._pasta_download, modo=estado["modo_download"],
                                log_cb=self.log.log, progress_cb=run.set_progress)
        run.set_progress(1.0)
        resumo = t("{baixados}/{total} documento(s) baixado(s) em:\n{pasta}",
                   baixados=res.baixados, total=res.total, pasta=res.pasta)
        if res.nao_encontrados:
            resumo += "\n\n" + t("{n} não encontrado(s).", n=len(res.nao_encontrados))
        if res.sem_arquivo or res.erros:
            resumo += "\n" + t("{sem} sem arquivo, {erros} com erro.", sem=len(res.sem_arquivo),
                                erros=len(res.erros))
        dialogos.info(t("Download Aconex"), resumo)

    def _tarefa_consulta(self, run: RunBar):
        if (prep := self._preparar()) is None:
            return
        estado, config = prep
        from ...aconex_backend import consultar_codigos, pares_da_consulta
        from ...status_backend import analisar_status_pares
        codigos = [c.strip() for c in estado["consulta"].splitlines() if c.strip()]
        if not codigos:
            self.log.log("Cole ao menos um código na aba 'Consulta Rápida'.")
            return
        run.set_progress(0.05)
        r = consultar_codigos(config, codigos, log_cb=self.log.log, progress_cb=run.set_progress)
        if r.base.empty:
            self.log.log("Nenhum dos códigos foi encontrado no Aconex.")
            na_ui(self._mostrar_consulta, None)
            return
        linhas, contador, tem_modelos = analisar_status_pares(r.base, pares_da_consulta(r.base, codigos))
        for st, n in contador.most_common():
            self.log.log(f"  {st}: {n}")
        self.log.log(f"Consulta concluída: {len(linhas)} documento(s).")
        na_ui(self._mostrar_consulta, (linhas, contador, tem_modelos))

    def _mostrar_consulta(self, resultado):
        self._consulta = resultado
        self.tabela_consulta.clear()
        self.btn_exportar_consulta.setEnabled(bool(resultado))
        if not resultado:
            self.tabela_consulta.hide()
            return
        for d in resultado[0]:
            self.tabela_consulta.addTopLevelItem(
                QTreeWidgetItem([str(d.get(c, "")) for c in self.COLUNAS_CONSULTA]))
        self.tabela_consulta.show()

    def linhas_da_consulta(self) -> list[list[str]]:
        t = self.tabela_consulta
        return [[t.topLevelItem(i).text(c) for c in range(t.columnCount())]
                for i in range(t.topLevelItemCount())]

    def _exportar_consulta(self):
        if not self._consulta:
            return
        from datetime import datetime

        from ...status_backend import exportar_status_documentos
        linhas, contador, tem_modelos = self._consulta
        saida = dialogos.pedir_salvar(self.ctx.config, "saida",
                                      f"Consulta_Aconex_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                      parent=self)
        if not saida:
            return
        ok, msg = exportar_status_documentos(linhas, contador, saida, tem_modelos=tem_modelos)
        self.log.log(msg)
        (dialogos.info if ok else dialogos.erro)(t("Consulta Rápida"), msg, self)

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
                dialogos.aviso(t("Extração Aconex"), t('A extração não foi concluída ({motivo}).\n\nRode de novo para continuar de onde parou.', motivo=r.motivo))
            return
        if not r.completa:
            self.log.log(f"ATENÇÃO: base PARCIAL ({r.motivo}).")
            if not dialogos.perguntar(
                    t("Extração incompleta"),
                    t('A extração parou antes do fim ({motivo}).\n\n{n_df} linhas foram baixadas e ficaram salvas para retomada - basta rodar de novo que ela continua da página {valor}.\n\nQuer salvar agora um Excel com o que já veio (base PARCIAL)?', motivo=r.motivo, n_df=len(r.df), valor=r.paginas + 1)):
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
            dialogos.info(t("Extração Aconex"), t('{n_df} linhas extraídas.', n_df=len(r.df)))
        else:
            self.log.log(f"Excel PARCIAL salvo com {len(r.df)} linhas. "
                         f"Rode a extração de novo para completar.")
