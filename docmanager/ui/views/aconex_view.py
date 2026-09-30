from __future__ import annotations

import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import theme as t
from ..components import Card, RunBar, pedir_salvar
from .base import BaseView


class AconexView(BaseView):
    titulo_view = "Extração Aconex (API)"
    subtitulo_view = "Baixa o histórico completo do projeto direto da API do Aconex"

    def montar(self, body):
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import OUTRO_USUARIO, usuarios_disponiveis
        self._OUTRO = OUTRO_USUARIO
        self._pasta_download: str | None = None

        card = Card(body, "Credenciais (valem para as duas abas)")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))

        # A lista sai do CADASTRO feito no app (antes vinha do .env, que ninguém
        # mais recebe: desde a v3.1.0 o app é instalado, não descompactado).
        disponiveis = usuarios_disponiveis()
        self._usuarios_conhecidos = list(disponiveis)
        linha = ctk.CTkFrame(card, fg_color="transparent")
        ctk.CTkLabel(linha, text="Usuário", width=170, anchor="w", font=t.corpo(12),
                     text_color=t.TEXTO).grid(row=0, column=0, sticky="w")
        self.opt_user = ctk.CTkOptionMenu(linha, values=disponiveis + [OUTRO_USUARIO],
                                          command=self._on_user,
                                          fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO,
                                          font=t.corpo(12))
        self.opt_user.set(disponiveis[0] if disponiveis else OUTRO_USUARIO)
        self.opt_user.grid(row=0, column=1, sticky="w", padx=(0, 8))
        ctk.CTkButton(linha, text="Cadastrar usuário", width=150, font=t.corpo(12),
                      fg_color=t.ACENTO, hover_color=t.ACENTO_HOVER,
                      command=self._cadastrar).grid(row=0, column=2, sticky="e")
        ctk.CTkButton(linha, text="Editar", width=80, font=t.corpo(12),
                      fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._editar).grid(row=0, column=3, sticky="e", padx=(8, 0))
        linha.grid_columnconfigure(1, weight=1)
        card.add(linha)

        # Chamada para quem ainda não cadastrou nada: sem ela a tela fica com um
        # seletor vazio e nenhuma pista do que fazer.
        self._aviso_cadastro = ctk.CTkLabel(
            card, text="", font=t.corpo(12), text_color=t.TEXTO, justify="left",
            wraplength=680, anchor="w")
        card.add(self._aviso_cadastro, pady=(0, 4))

        # Entrada manual (visível só quando "Outro" é escolhido) - não é salva.
        self._manual = ctk.CTkFrame(card, fg_color="transparent")
        self.entry_client = ctk.CTkEntry(self._manual, placeholder_text="Client ID (APP ID) do Aconex",
                                         font=t.corpo(12))
        self.entry_userid = ctk.CTkEntry(self._manual, placeholder_text="User ID (numérico) do Aconex",
                                         font=t.corpo(12))
        self.entry_secret = ctk.CTkEntry(self._manual, placeholder_text="Client Secret", show="*",
                                         font=t.corpo(12))
        for w in (self.entry_client, self.entry_userid, self.entry_secret):
            w.pack(fill="x", pady=3)
        card.add(self._manual)

        self.entry_proxy = ctk.CTkEntry(card, placeholder_text="Proxy (opcional). Em branco, o app detecta sozinho.",
                                        font=t.corpo(12))
        card.add(self.entry_proxy)
        self._dica = ctk.CTkLabel(card, text="", font=t.corpo(11), text_color=t.TEXTO_FRACO, anchor="w")
        self._dica.grid(row=card._linha, column=0, sticky="w", padx=16, pady=(0, 12))

        # Guias do módulo: extração completa, fluxos de trabalho e download por lista.
        self.tabs = ctk.CTkTabview(body, fg_color=t.CARD, segmented_button_selected_color=t.ACENTO,
                                   segmented_button_selected_hover_color=t.ACENTO_HOVER)
        self.tabs.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self._montar_aba_extracao(self.tabs.add("📦 Extração Completa"))
        self._montar_aba_fluxos(self.tabs.add("🔀 Fluxos de Trabalho"))
        self._montar_aba_download(self.tabs.add("⬇️ Baixar por Lista"))
        self._on_user(self.opt_user.get())   # visibilidade, dica e aviso iniciais

    def _montar_aba_extracao(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(aba, text="Baixa o histórico completo do projeto (todas as revisões, com "
                     "Tracking ID) para um Excel. Leva vários minutos e retoma de onde parou "
                     "se a conexão cair.",
                     font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=720).grid(
            row=0, column=0, sticky="w", padx=6, pady=(8, 2))
        self.run = RunBar(aba, "Iniciar Extração", self._tarefa, self.log)
        self.run.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))

    # Períodos da extração incremental: rótulo → dias (None = tudo).
    PERIODOS_FLUXO = {
        "Tudo (~20 min)": None,
        "Últimos 7 dias": 7,
        "Últimos 30 dias": 30,
        "Últimos 12 meses": 365,
    }

    def _montar_aba_fluxos(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(aba, text="Baixa os FLUXOS DE TRABALHO (a aba 'Fluxos de Trabalho' do Aconex): "
                     "etapa, prazo e a quem cada documento está atribuído. Um período curto "
                     "atualiza rápido, porque baixa só o que mudou desde então.",
                     font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=720).grid(
            row=0, column=0, sticky="w", padx=6, pady=(8, 2))

        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        ctk.CTkLabel(linha, text="Período", width=170, anchor="w", font=t.corpo(12),
                     text_color=t.TEXTO).grid(row=0, column=0, sticky="w")
        self.opt_periodo_fluxo = ctk.CTkOptionMenu(
            linha, values=list(self.PERIODOS_FLUXO), font=t.corpo(12),
            fg_color=t.SIDEBAR_HOVER, button_color=t.SIDEBAR_ATIVO)
        self.opt_periodo_fluxo.set("Tudo (~20 min)")
        self.opt_periodo_fluxo.grid(row=0, column=1, sticky="w")
        linha.grid_columnconfigure(1, weight=1)

        RunBar(aba, "Extrair Fluxos de Trabalho", self._tarefa_fluxos, self.log).grid(
            row=2, column=0, sticky="ew", padx=6, pady=(0, 8))

    def _tarefa_fluxos(self, run: RunBar):
        if not self._garantir_credenciais():
            return
        from datetime import datetime, timedelta, timezone

        from dotenv import load_dotenv
        load_dotenv()
        from ...workflows_backend import (
            extrair_workflows,
            limpar_checkpoint_wf,
            nome_arquivo_padrao_wf,
            salvar_excel_workflows,
        )
        try:
            config = self._montar_config()
        except (KeyError, ValueError) as e:
            self.log.log(f"ERRO: {e}")
            return

        dias = self.PERIODOS_FLUXO.get(self.opt_periodo_fluxo.get())
        updated_after = ""
        if dias:
            updated_after = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            self.log.log(f"Extração incremental: fluxos alterados nos últimos {dias} dias.")
        run.set_progress(0.05)
        r = extrair_workflows(config, log_cb=self.log.log, updated_after=updated_after,
                              progress_cb=run.set_progress)

        if r.df.empty:
            self.log.log("Nenhum fluxo retornado.")
            return
        if not r.completa:
            self.log.log(f"ATENÇÃO: base PARCIAL ({r.motivo}).")
            if not messagebox.askyesno(
                    "Extração incompleta",
                    f"A extração parou antes do fim ({r.motivo}).\n\n"
                    f"{len(r.df)} linhas ficaram salvas para retomada - rode de novo que ela "
                    f"continua da página {r.paginas + 1}.\n\n"
                    "Quer salvar agora um Excel com o que já veio (base PARCIAL)?"):
                self.log.log("Excel parcial não gerado. O progresso segue guardado para retomar.")
                return

        saida = pedir_salvar(self.ctx.config, "saida", nome_arquivo_padrao_wf())
        if not saida:
            self.log.log("Salvamento cancelado. O progresso da extração continua guardado.")
            return
        salvar_excel_workflows(r.df, saida)
        run.set_progress(1.0)
        if r.completa:
            limpar_checkpoint_wf(config, updated_after=updated_after)
            self.log.log(f"Concluído: {len(r.df)} fluxos salvos.")
            self.after(0, lambda: messagebox.showinfo(
                "Fluxos de Trabalho", f"{len(r.df)} linhas de fluxo salvas."))

    def _montar_aba_download(self, aba):
        aba.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(aba, text="Cole os códigos Itaipu, um por linha. Baixa a versão atual "
                     "(current) de cada documento para a pasta escolhida.",
                     font=t.corpo(12), text_color=t.TEXTO_FRACO, justify="left", wraplength=720).grid(
            row=0, column=0, sticky="w", padx=6, pady=(8, 2))
        self.txt_codigos = ctk.CTkTextbox(aba, height=140, font=t.mono(11), fg_color="#0B1119")
        self.txt_codigos.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 6))
        linha.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(linha, text="Escolher pasta", width=130, font=t.corpo(12),
                      fg_color=t.SIDEBAR_HOVER, hover_color=t.SIDEBAR_ATIVO,
                      command=self._escolher_pasta).grid(row=0, column=0, sticky="w")
        self.lbl_pasta = ctk.CTkLabel(linha, text="Nenhuma pasta escolhida", anchor="w",
                                      font=t.corpo(11), text_color=t.TEXTO_FRACO)
        self.lbl_pasta.grid(row=0, column=1, sticky="ew", padx=10)

        RunBar(aba, "Baixar Documentos", self._tarefa_download, self.log).grid(
            row=3, column=0, sticky="ew", padx=6, pady=(0, 8))

    def _escolher_pasta(self):
        inicial = self.ctx.config.ultimo_dir("download") if self.ctx.config else None
        pasta = filedialog.askdirectory(title="Pasta para salvar os documentos", initialdir=inicial)
        if not pasta:
            return
        self._pasta_download = pasta
        self.lbl_pasta.configure(text=pasta, text_color=t.TEXTO)
        if self.ctx.config:
            # lembrar_dir guarda o DIRNAME do caminho; passa um filho para
            # memorizar a própria pasta escolhida.
            self.ctx.config.lembrar_dir("download", os.path.join(pasta, "_"))

    def _tarefa_download(self, run: RunBar):
        if not self._garantir_credenciais():
            return
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import baixar_documentos
        try:
            config = self._montar_config()
        except (KeyError, ValueError) as e:
            self.log.log(f"ERRO: {e}")
            return
        codigos = [c.strip() for c in self.txt_codigos.get("1.0", "end").splitlines() if c.strip()]
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
        resumo = (f"{res.baixados}/{res.total} documento(s) baixado(s) em:\n{res.pasta}")
        if res.nao_encontrados:
            resumo += f"\n\n{len(res.nao_encontrados)} não encontrado(s)."
        if res.sem_arquivo or res.erros:
            resumo += f"\n{len(res.sem_arquivo)} sem arquivo, {len(res.erros)} com erro."
        self.after(0, lambda: messagebox.showinfo("Download Aconex", resumo))

    def _on_user(self, escolha: str):
        """Mostra os campos manuais só na opção 'Outro'; ajusta a dica."""
        if escolha == self._OUTRO:
            self._manual.grid()
            self._dica.configure(text="Entrada manual: informe os 3 dados do usuário do Aconex. "
                                      "Valem só para esta extração e não são salvos. Para "
                                      "guardar de vez, use 'Cadastrar usuário'.")
        else:
            self._manual.grid_remove()
            self._dica.configure(text="O Client Secret está guardado nesta máquina, cifrado pelo "
                                      "Windows. Para trocá-lo, use 'Editar'.")
        self._atualizar_aviso()

    def _atualizar_aviso(self):
        """Texto de chamada quando ainda não há nenhum usuário cadastrado."""
        from ...aconex_backend import usuarios_disponiveis

        if usuarios_disponiveis():
            self._aviso_cadastro.configure(text="")
            self._aviso_cadastro.grid_remove()
            return
        self._aviso_cadastro.configure(
            text="⚠️  Nenhum usuário cadastrado ainda. Clique em CADASTRAR USUÁRIO e "
                 "informe o Client ID (APP ID), o User ID e o Client Secret que o "
                 "administrador do Aconex passou para você. É uma vez só: fica guardado "
                 "nesta máquina e continua valendo depois das atualizações.")
        self._aviso_cadastro.grid()

    # --- cadastro das credenciais -------------------------------------------
    def ao_exibir(self):
        # O cadastro também é feito nas Configurações, com esta tela já criada:
        # sem reler aqui, o usuário novo não aparecia na lista da Extração.
        self._recarregar_usuarios()

    def _manual_preenchido(self) -> bool:
        return any(w.get().strip() for w in (self.entry_client, self.entry_userid, self.entry_secret))

    def _recarregar_usuarios(self, selecionar: str | None = None):
        from ...aconex_backend import escolher_usuario, usuarios_disponiveis

        disponiveis = usuarios_disponiveis()
        alvo = escolher_usuario(disponiveis, atual=selecionar or self.opt_user.get(),
                                conhecidos=self._usuarios_conhecidos,
                                manual_preenchido=self._manual_preenchido())
        self._usuarios_conhecidos = list(disponiveis)
        self.opt_user.configure(values=disponiveis + [self._OUTRO])
        self.opt_user.set(alvo)
        self._on_user(alvo)

    def _cadastrar(self, nome: str | None = None):
        """Abre o cadastro. Só pode ser chamado na thread da interface."""
        from .credenciais_dialog import cadastrar

        salvo = cadastrar(self.winfo_toplevel(), nome)
        if salvo:
            self._recarregar_usuarios(salvo)
            self.log.log(f"Credenciais de '{salvo}' salvas nesta máquina.")
        return salvo

    def _editar(self):
        escolha = self.opt_user.get()
        if escolha == self._OUTRO:
            self._cadastrar()
            return
        self._cadastrar(escolha)

    def _garantir_credenciais(self) -> bool:
        """Checa, ANTES de gastar tempo, se há com o que autenticar.

        Roda dentro da thread da tarefa, então o diálogo é agendado de volta na
        thread da interface com `after` - abrir janela de outra thread trava o Tk.
        """
        from ...aconex_backend import usuarios_disponiveis

        if usuarios_disponiveis() or self.opt_user.get() == self._OUTRO:
            return True
        self.log.log("Nenhum usuário do Aconex cadastrado - abrindo o cadastro.")
        self.after(0, self._cadastrar)
        return False

    def _montar_config(self):
        """Monta a AconexConfig conforme a escolha (conhecido ou manual)."""
        from ...aconex_backend import AconexConfig
        proxy = self.entry_proxy.get().strip() or None
        escolha = self.opt_user.get()
        if escolha == self._OUTRO:
            client_id = self.entry_client.get().strip()
            user_id = self.entry_userid.get().strip()
            secret = self.entry_secret.get().strip()
            if not (client_id and user_id and secret):
                raise ValueError("Preencha Client ID, User ID e Secret para o usuário manual.")
            return AconexConfig(client_id=client_id, client_secret=secret, user_id=user_id, proxy=proxy)
        return AconexConfig.para_usuario(escolha, proxy=proxy)

    def _tarefa(self, run: RunBar):
        if not self._garantir_credenciais():
            return
        from dotenv import load_dotenv
        load_dotenv()
        from ...aconex_backend import (
            checkpoint_pendente,
            extrair_base,
            limpar_checkpoint,
            nome_arquivo_padrao,
            salvar_excel,
        )
        try:
            config = self._montar_config()
        except (KeyError, ValueError) as e:
            self.log.log(f"ERRO: {e}")
            return

        pendente = checkpoint_pendente(config)
        if pendente is not None:
            self.log.log(f"Há uma extração interrompida em {pendente.atualizado_em} com "
                         f"{pendente.total} registros - será retomada da página "
                         f"{pendente.proxima_pagina}.")
        run.set_progress(0.05)
        self.log.log("Extração iniciada (pode levar vários minutos)...")
        r = extrair_base(config, log_cb=self.log.log, progress_cb=run.set_progress)

        if r.df.empty:
            self.log.log("Nenhum dado retornado.")
            if not r.completa:
                self.after(0, lambda: messagebox.showwarning(
                    "Extração Aconex", f"A extração não foi concluída ({r.motivo}).\n\n"
                    "Rode de novo para continuar de onde parou."))
            return

        if not r.completa:
            self.log.log(f"ATENÇÃO: base PARCIAL ({r.motivo}).")
            salvar = messagebox.askyesno(
                "Extração incompleta",
                f"A extração parou antes do fim ({r.motivo}).\n\n"
                f"{len(r.df)} linhas foram baixadas e ficaram salvas para retomada - "
                f"basta rodar de novo que ela continua da página {r.paginas + 1}.\n\n"
                "Quer salvar agora um Excel com o que já veio (base PARCIAL)?")
            if not salvar:
                self.log.log("Excel parcial não gerado. O progresso segue guardado para retomar.")
                return

        saida = pedir_salvar(self.ctx.config, "saida", nome_arquivo_padrao())
        if not saida:
            self.log.log("Salvamento cancelado. O progresso da extração continua guardado.")
            return
        salvar_excel(r.df, saida)
        run.set_progress(1.0)
        if r.completa:
            # Só descarta o checkpoint depois que o Excel está em disco.
            limpar_checkpoint(config)
            self.log.log(f"Concluído: {len(r.df)} linhas salvas.")
            self.after(0, lambda: messagebox.showinfo(
                "Extração Aconex", f"{len(r.df)} linhas extraídas."))
        else:
            self.log.log(f"Excel PARCIAL salvo com {len(r.df)} linhas. "
                         f"Rode a extração de novo para completar.")
