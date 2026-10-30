from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLineEdit, QPushButton,
)

from ... import __version__
from ...services import updater
from ...services.credenciais import cofre
from .. import dialogos, estilo, icones, tema
from ..components import Card, Seletor, botao, linha, rotulo
from ..ponte import na_ui
from ..propriedades import ler
from .base import BaseView

# (escolha, rótulo, ícone) do seletor de tema - os mesmos três do SIG-FT.
TEMAS = (("escuro", "Escuro", "moon"), ("claro", "Claro", "sun"), ("sistema", "Do Windows", "monitor"))
BASES_CMI = {"reprogramacao": "Reprogramação (quando houver)", "prevista": "Data prevista (base)"}


class _Segmentado(QFrame):
    """Botões lado a lado, um escolhido (`ativo`) - o seletor do SIG-FT."""

    def __init__(self, opcoes, atual, ao_escolher):
        super().__init__()
        self.setObjectName("seletor")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._grupo = QButtonGroup(self)
        self.botoes: dict[str, QPushButton] = {}
        for valor, texto, icone in opcoes:
            b = QPushButton(texto)
            if icone:
                icones.aplicar(b, icone, papel_cor_ativo=estilo.PAPEL_MENU_ESCOLHIDO)
            b.clicked.connect(lambda _=False, v=valor: (self.marcar(v), ao_escolher(v)))
            self._grupo.addButton(b)
            lay.addWidget(b)
            self.botoes[valor] = b
        lay.addStretch(1)
        self.marcar(atual)

    def marcar(self, valor) -> None:
        for v, b in self.botoes.items():
            estilo.definir_propriedade(b, "ativo", v == valor)
            icones.reaplicar(b)

    def escolhido(self) -> str:
        return next((v for v, b in self.botoes.items() if ler(b, "ativo")), "")


class ConfigView(BaseView):
    titulo_view = "Configurações"
    subtitulo_view = "Ajustes que valem para todos os módulos"

    def montar(self, body):
        self._aparencia(body)
        self._credenciais(body)
        self._atualizacoes(body)
        self._regra_vip(body)
        self._base_atraso(body)
        self._sugestoes(body)

    def ao_exibir(self):
        # Cadastro feito pela tela da Extração, ou atualização achada depois que
        # esta tela foi criada, têm de aparecer aqui também.
        self._atualizar_lista_cred()
        self._descrever_versao()

    # ───────────────────────────────── aparência ────────────────────────────
    def _aparencia(self, body):
        card = Card("Aparência")
        self.seletor_tema = _Segmentado(TEMAS, tema.valida(self.ctx.config.settings.tema), self._set_tema)
        card.add(self.seletor_tema)
        card.add(rotulo("'Do Windows' acompanha o tema claro ou escuro do sistema, inclusive se ele "
                        "mudar com o app aberto.", "legenda", quebra=True))
        body.addWidget(card)

    def _set_tema(self, escolha: str):
        tema.aplicar(QApplication.instance(), escolha, self.ctx.config)
        self.log.log(f"Tema: {dict((v, t) for v, t, _ in TEMAS)[escolha]}.")

    # ─────────────────────────── credenciais do Aconex ──────────────────────
    def _credenciais(self, body):
        """Lista dos usuários cadastrados - o que substituiu editar o `.env`."""
        card = Card("Credenciais do Aconex")
        card.add(rotulo("Cada pessoa usa a própria credencial do Aconex: Client ID, User ID e Client "
                        "Secret. O segredo fica só nesta máquina, cifrado pelo Windows na sua conta de "
                        "usuário. Ele não vai para o GitHub e continua valendo depois das atualizações.",
                        "suave", quebra=True))
        self._lista_cred = card.add(rotulo("", quebra=True))
        self._opt_cred = Seletor(["(nenhum)"])
        self._opt_cred.setMinimumWidth(220)
        card.add(linha(botao("Cadastrar novo", variante="primario", icone="user-plus",
                             ao_clicar=lambda: self._cadastrar(None)),
                       self._opt_cred,
                       botao("Editar", icone="pencil", ao_clicar=self._editar),
                       botao("Remover", variante="perigo", icone="trash-2", ao_clicar=self._remover)))
        body.addWidget(card)
        self._atualizar_lista_cred()

    def _atualizar_lista_cred(self, selecionar: str | None = None):
        nomes = cofre().listar()
        self._lista_cred.setText(
            ("Cadastrados: " + ", ".join(nomes)) if nomes
            else "Nenhum usuário cadastrado. A Extração Aconex só funciona depois que você cadastrar um.")
        alvo = selecionar or self._opt_cred.get()
        self._opt_cred.definir_itens(nomes or ["(nenhum)"],
                                     alvo if alvo in nomes else (nomes[0] if nomes else "(nenhum)"))

    def _cadastrar(self, nome: str | None):
        from .credenciais_dialog import cadastrar

        if (salvo := cadastrar(self.window(), nome)):
            self._atualizar_lista_cred(salvo)
            self.log.log(f"Credenciais de '{salvo}' salvas nesta máquina.")

    def _editar(self):
        nome = self._opt_cred.get()
        if nome and nome != "(nenhum)":
            self._cadastrar(nome)

    def _remover(self):
        nome = self._opt_cred.get()
        if not nome or nome == "(nenhum)":
            return
        if not dialogos.perguntar(
                "Remover credencial",
                f"Apagar as credenciais de '{nome}' desta máquina?\n\n"
                "O usuário some da lista da Extração Aconex. No Aconex nada muda.", padrao_nao=True,
                parent=self):
            return
        cofre().remover(nome)
        self._atualizar_lista_cred()
        self.log.log(f"Credenciais de '{nome}' removidas.")

    # ───────────────────────────── atualizações ─────────────────────────────
    def _atualizacoes(self, body):
        card = Card("Atualizações do DocManager")
        self._lbl_versao = card.add(rotulo("", quebra=True))
        self._descrever_versao()

        self._sw_auto = QCheckBox("Avisar automaticamente quando sair uma versão nova")
        self._sw_auto.setChecked(self.ctx.config.settings.verificar_atualizacoes)
        self._sw_auto.toggled.connect(self._toggle_auto)
        card.add(self._sw_auto)

        # Canal de testes: também oferece os pré-lançamentos (rc). É assim que
        # se testa a atualização pequena antes de todo mundo receber.
        self._chk_teste = QCheckBox("Versões de teste")
        self._chk_teste.setChecked(self.ctx.config.settings.versoes_de_teste)
        self._chk_teste.toggled.connect(self._toggle_teste)
        card.add(linha(botao("Procurar atualizações agora  (Ctrl+K)", variante="primario",
                             icone="refresh-cw", ao_clicar=self._procurar), self._chk_teste, espaco=16))
        card.add(rotulo(
            "A verificação roda em segundo plano toda vez que o app abre (e, com ele aberto, a cada 6 "
            "horas) e funciona com o Zscaler e a VPN ligados. Quando dá, o download traz só o que mudou "
            "desde a sua versão. O botão 'Procurar atualizações' (ou Ctrl+K, de qualquer tela) verifica "
            "na hora. 'Versões de teste' oferece também as versões ainda em teste. Suas configurações e "
            "credenciais ficam fora da pasta do programa, então a atualização não apaga nada.",
            "suave", quebra=True))
        body.addWidget(card)
        # Se a checagem automática já achou algo (ou achar depois), reflete aqui.
        self.ctx.ao_achar_atualizacao(lambda _info: na_ui(self._descrever_versao))

    def _descrever_versao(self):
        info = self.ctx.atualizacao
        if info is not None:
            texto = (f"Versão instalada: v{__version__}   ·   disponível: v{info.versao}. Clique em "
                     f"'Procurar atualizações agora' para instalar.")
        elif (motivo := updater.motivo_para_nao_verificar()):
            texto = f"Versão instalada: v{__version__}   ·   {motivo}"
        else:
            texto = f"Versão instalada: v{__version__}"
        self._lbl_versao.setText(texto)

    def _toggle_auto(self, ligado: bool):
        self.ctx.config.set_setting("verificar_atualizacoes", ligado)
        if ligado:
            # Voltar a ligar limpa a versão pulada: quem religa quer ser avisado.
            self.ctx.config.set_setting("versao_ignorada", "")
        self.log.log(f"Aviso automático de atualização {'ligado' if ligado else 'desligado'}.")

    def _toggle_teste(self, ligado: bool):
        self.ctx.config.set_setting("versoes_de_teste", ligado)
        self.log.log(f"Versões de teste {'ligadas' if ligado else 'desligadas'}.")

    def _procurar(self):
        self.log.log("Procurando atualizações...")
        if self.ctx.verificar_atualizacao:
            self.ctx.verificar_atualizacao(True)

    # ─────────────────────────── regras de negócio ──────────────────────────
    def _regra_vip(self, body):
        card = Card("Regra estrita das Planilhas VIP (pente fino)")
        self.switch = QCheckBox("Ativar rebaixamento estrito (APROVAÇÃO INTERMEDIÁRIA)")
        self.switch.setChecked(self.ctx.config.settings.regra_estrita_vip)
        self.switch.toggled.connect(lambda v: self.ctx.config.set_setting("regra_estrita_vip", v))
        card.add(self.switch)
        card.add(rotulo(
            "Desligado (padrão): fluxo normal - planilhas de comissionamento e seus documentos são "
            "consolidados sem aprovação intermediária.\n\n"
            "Ligado: documentos de nível 4 sob planilhas VIP só contam como APROVADO quando o status real "
            "é 'Aprovado' seco; aprovações parciais viram APROVAÇÃO INTERMEDIÁRIA. Afeta o Mapa "
            "(consolidado + resumo do nível 3) e o Delta. A exceção do 'Para Aprovação' em planilhas de "
            "comissionamento permanece sempre ativa.", "suave", quebra=True))
        body.addWidget(card)

    def _base_atraso(self, body):
        card = Card("Base do atraso CMI na 1ª emissão (revisão 0A)")
        atual = "prevista" if self.ctx.config.settings.base_atraso_cmi_0a == "prevista" else "reprogramacao"
        self.base_cmi = _Segmentado([(v, t, None) for v, t in BASES_CMI.items()], atual,
                                    lambda v: self.ctx.config.set_setting("base_atraso_cmi_0a", v))
        card.add(self.base_cmi)
        card.add(rotulo(
            "Escolhe sobre qual data o atraso do CMI na revisão 0A é contado:\n\n"
            "• Reprogramação (quando houver): usa a data reprogramada do Controle se existir, senão a "
            "data prevista.\n"
            "• Data prevista (base): usa sempre a data prevista original, ignorando a reprogramação. "
            "Afeta o Histórico Consolidado e o Dashboard.", "suave", quebra=True))
        body.addWidget(card)

    # ───────────────────────────────── sugestões ────────────────────────────
    def _sugestoes(self, body):
        card = Card("Sugestões")
        self.email_sugestoes = QLineEdit(self.ctx.config.settings.email_sugestoes)
        self.email_sugestoes.setPlaceholderText("nome@empresa.com")
        self.email_sugestoes.editingFinished.connect(self._salvar_email_sugestoes)
        card.add(linha(rotulo("E-mail que recebe"), self.email_sugestoes, esticar=1))
        card.add(rotulo("A tela Sugestões abre um rascunho de e-mail para este endereço. Vazio, o "
                        "rascunho abre sem destinatário.", "suave", quebra=True))
        body.addWidget(card)

    def _salvar_email_sugestoes(self):
        email = self.email_sugestoes.text().strip()
        if email and ("@" not in email or " " in email):
            dialogos.aviso("Sugestões", f"{email!r} não parece um e-mail. Nada foi salvo.", self)
            self.email_sugestoes.setText(self.ctx.config.settings.email_sugestoes)
            return
        if email != self.ctx.config.settings.email_sugestoes:
            self.ctx.config.set_setting("email_sugestoes", email)
            self.log.log(f"Sugestões vão para: {email}." if email else "Sugestões sem destinatário fixo.")
