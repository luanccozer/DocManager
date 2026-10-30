"""A aparência do DocManager em Qt: os tokens de `ui/tokens.py` virando folha de estilo.

Mesmo sistema visual do SIG-FT (`sigft/app_qt/estilo.py`): as CORES moram em
`tokens.py` (dois temas, mesmos papéis) e este módulo só as lê.
`folha_de_estilo(tema)` monta a folha do app inteiro para "escuro" ou "claro".

Regra da casa: tela nenhuma escreve cor. O que muda de cor muda por
PROPRIEDADE (`variante` do botão, `papel` do rótulo, `ativo` do item do menu)
ou por objectName, e a regra mora aqui - assim a troca de tema alcança tudo
(`tests/test_ui_qt.py` acusa hexadecimal fora deste arquivo e dos tokens).
"""
from __future__ import annotations

from pathlib import Path

from . import tokens

PASTA_RECURSOS = Path(__file__).resolve().parent / "recursos"
PASTA_ICONES = PASTA_RECURSOS / "icones"
PASTA_FONTES = PASTA_RECURSOS / "fontes"
ARQUIVOS_DE_FONTE = ("Roboto-Regular.ttf",)

# Botão e campo com 32 px de altura TOTAL (borda de 1 px incluída), raio 6.
# No QSS o `min-height` NÃO conta a borda: 32 - 2.
ALTURA_BOTAO = 32
ALTURA_CAMPO = 32
ALTURA_BOTAO_ACAO = 40
ALTURA_BOTAO_MENU = 38
BORDA_CONTROLE = 1
LARGURA_BARRA_LATERAL = 248
ALTURA_LINHA_TABELA = 26

# Item escolhido (e sob o mouse) do menu lateral: `marca` a 25% sobre a
# superfície da barra. O texto: `texto` no escuro (10,3:1) e a própria marca no
# claro (6,6:1) - `texto` claro sobre a marca pura dava 2,2:1.
MENU_ESCOLHIDO = {
    "escuro": {"fundo": "#0F3A3F", "texto": tokens.ESCURO["texto"]},
    "claro": {"fundo": "#E3F1F2", "texto": tokens.CLARO["marca"]},
}
PAPEL_MENU_ESCOLHIDO = "menu_escolhido"

# O texto do botão de perigo: branco nos dois temas (o `perigo_fundo` é o mesmo).
TEXTO_SOBRE_PERIGO = "#FFFFFF"
TEXTO_SOBRE_MARCA = "#FFFFFF"
MARCA_HOVER = "#047A83"

# O tema que está valendo ("escuro" ou "claro"). `ui/tema.aplicar` muda; quem
# pinta à mão (ícones, cor de linha da tabela) lê na hora de pintar.
TEMA_ATUAL = "escuro"
# Imagens que a folha usa por arquivo (`tema.aplicar` as gera na cor do tema):
# "seta" (do QComboBox) e "tique" (da caixa de marcar). Vazias: a folha sem elas.
IMAGENS: dict[str, str] = {"seta": "", "tique": ""}


# A letra que está valendo ("normal" ou "grande"); `tema.aplicar_letra` muda.
# "grande" soma 2 px a todos os tamanhos, como na CMI Suite e no SIG-FT.
LETRA_ATUAL = "normal"
LETRAS = ("normal", "grande")
AUMENTO_DA_LETRA = {"normal": 0, "grande": 2}


def fontes() -> dict[str, int]:
    """Os tamanhos de `tokens.FONTE` com o aumento da letra que está valendo."""
    a = AUMENTO_DA_LETRA.get(LETRA_ATUAL, 0)
    return {k: v + a for k, v in tokens.FONTE.items()}


def _tema(tema: str | None) -> str:
    return TEMA_ATUAL if tema is None else tema


def paleta_atual() -> dict[str, str]:
    """A paleta (`tokens.paleta`) do tema que está valendo."""
    return tokens.paleta(TEMA_ATUAL)


def cor_do_papel(papel: str) -> str | None:
    """A cor do `papel` no tema atual: uma chave da paleta ou
    `PAPEL_MENU_ESCOLHIDO`. Papel desconhecido: `None`."""
    if papel == PAPEL_MENU_ESCOLHIDO:
        return MENU_ESCOLHIDO["claro" if TEMA_ATUAL == "claro" else "escuro"]["texto"]
    return paleta_atual().get(papel)


def cor_do_texto_da_variante(variante: str | None) -> str:
    """A cor do texto de um botão da `variante` no tema atual - é a cor do
    ícone dele (`icones.aplicar`): o ícone acompanha o texto ao lado."""
    p = paleta_atual()
    if variante == "primario":
        return p["texto_sobre_primaria"]
    if variante == "perigo":
        return TEXTO_SOBRE_PERIGO
    return p["texto"]


def definir_propriedade(widget, nome: str, valor) -> None:
    """`setProperty` que a folha enxerga na hora: o Qt só reavalia os seletores
    `[nome="..."]` de um widget já polido quando ele é repolido."""
    widget.setProperty(nome, valor)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def definir_papel(rotulo, papel: str | None) -> None:
    """Troca o papel de texto (`QLabel[papel=...]`) de um rótulo já na tela."""
    definir_propriedade(rotulo, "papel", papel)


def carregar_fontes() -> list[str]:
    """Registra o Roboto no Qt (chamar depois do QApplication) e o põe como
    fonte do app. Fonte que falta não derruba nada: abre com a padrão."""
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    familias: list[str] = []
    for nome in ARQUIVOS_DE_FONTE:
        indice = QFontDatabase.addApplicationFont(str(PASTA_FONTES / nome))
        if indice >= 0:
            familias.extend(QFontDatabase.applicationFontFamilies(indice))
    fonte = QFont()
    fonte.setFamilies(["Roboto", "Segoe UI"])
    fonte.setPixelSize(fontes()["corpo"])
    QApplication.setFont(fonte)
    return familias


def folha_de_estilo(tema: str | None = None) -> str:
    """A folha QSS do app inteiro no `tema` ("escuro" ou "claro"). Sem argumento,
    o tema que está valendo (`TEMA_ATUAL`)."""
    tema = _tema(tema)
    p = tokens.paleta(tema)
    menu = MENU_ESCOLHIDO["claro" if tema == "claro" else "escuro"]
    f = fontes()
    raio, raio_cartao = tokens.RAIO["controle"], tokens.RAIO["cartao"]
    fam = '"Roboto", "Segoe UI"'
    mono = '"Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono", monospace'
    altura_botao = ALTURA_BOTAO - 2 * BORDA_CONTROLE
    altura_acao = ALTURA_BOTAO_ACAO - 2 * BORDA_CONTROLE
    altura_campo = ALTURA_CAMPO - 2 * BORDA_CONTROLE
    perigo_hover = _escurecer(p["perigo_fundo"], 0.15)
    seta = (f"QComboBox::down-arrow {{ image: url({IMAGENS['seta']}); width: 14px; height: 14px; }}"
            if IMAGENS.get("seta") else "")
    tique = (f"QCheckBox::indicator:checked {{ image: url({IMAGENS['tique']}); }}"
             if IMAGENS.get("tique") else "")
    # Notas que não cabem dentro da folha:
    # * botão sem variante = secundário (contorno `borda`, texto `texto`);
    # * primário: texto ESCURO no tema escuro (branco sobre o verde vivo dava 3,1:1);
    # * #console: escuro nos DOIS temas (é saída de log), fonte mono;
    # * papel "aviso" ganha o fundo `superficie` (pílula): só ali chega a 4,5:1 no claro.
    return f"""
QMainWindow, #conteudo, #tela, QDialog {{ background: {p['fundo']}; }}
QWidget {{ font-family: {fam}; color: {p['texto']}; font-size: {f['corpo']}px; }}
QToolTip {{ background: {p['superficie_alta']}; color: {p['texto']}; border: 1px solid {p['borda']};
    padding: 4px 8px; }}
#sidebar {{ background: {p['superficie']}; border: none; border-right: 1px solid {p['borda']}; }}
#app_nome {{ font-size: 20px; font-weight: bold; }}
#app_sub, #rodape_versao {{ color: {p['texto_suave']}; font-size: {f['legenda']}px; }}
#rodape_versao[novo="true"] {{ color: {p['primaria']}; font-weight: bold; }}
#titulo_view {{ font-size: {f['titulo'] + 2}px; font-weight: bold; }}
#subtitulo_view {{ color: {p['texto_suave']}; font-size: {f['corpo']}px; }}

QPushButton {{ border-radius: {raio}px; color: {p['texto']}; background: transparent;
    border: {BORDA_CONTROLE}px solid {p['borda']}; padding: 0 14px;
    min-height: {altura_botao}px; font-size: {f['corpo']}px; }}
QPushButton:hover {{ background: {p['superficie_alta']}; }}
QPushButton:pressed {{ background: {p['borda']}; }}
QPushButton:disabled {{ color: {p['texto_suave']}; }}
QPushButton[variante="primario"] {{ background: {p['primaria']}; border-color: {p['primaria']};
    color: {p['texto_sobre_primaria']}; font-weight: bold; }}
QPushButton[variante="primario"]:hover {{ background: {p['primaria_hover']}; border-color: {p['primaria_hover']}; }}
QPushButton[variante="primario"]:disabled {{ background: {p['superficie_alta']}; border-color: {p['borda']};
    color: {p['texto_suave']}; }}
QPushButton[variante="perigo"] {{ background: {p['perigo_fundo']}; border-color: {p['perigo_fundo']};
    color: {TEXTO_SOBRE_PERIGO}; }}
QPushButton[variante="perigo"]:hover {{ background: {perigo_hover}; border-color: {perigo_hover}; }}
QPushButton[variante="perigo"]:disabled {{ background: {p['superficie_alta']}; border-color: {p['borda']};
    color: {p['texto_suave']}; }}
QPushButton[variante="fantasma"] {{ border-color: transparent; color: {p['texto_suave']}; }}
QPushButton[variante="fantasma"]:hover {{ background: {p['superficie_alta']}; color: {p['texto']}; }}
QPushButton[acao="true"] {{ min-height: {altura_acao}px; padding: 0 18px; font-size: {f['corpo'] + 1}px; }}
QPushButton[menu="true"] {{ background: transparent; text-align: left; padding: 0 12px; border: none;
    min-height: {ALTURA_BOTAO_MENU}px; max-height: {ALTURA_BOTAO_MENU}px; font-size: {f['corpo'] + 1}px; }}
QPushButton[menu="true"]:hover, QPushButton[menu="true"][ativo="true"] {{ background: {menu['fundo']};
    color: {menu['texto']}; }}
QPushButton[menu="true"][ativo="true"] {{ font-weight: bold; }}

QLabel[papel="legenda"] {{ color: {p['texto_suave']}; font-size: {f['legenda']}px; }}
QLabel[papel="suave"] {{ color: {p['texto_suave']}; }}
QLabel[papel="secao"] {{ font-size: {f['secao']}px; font-weight: bold; }}
QLabel[papel="titulo"] {{ font-size: {f['titulo']}px; font-weight: bold; }}
QLabel[papel="destaque"] {{ color: {p['primaria']}; font-weight: bold; }}
QLabel[papel="aviso"] {{ color: {p['aviso']}; background: {p['superficie']}; border-radius: {raio}px;
    padding: 6px 8px; }}
QLabel[papel="erro"] {{ color: {p['perigo']}; }}
QLabel[papel="ok"] {{ color: {p['primaria']}; }}
QLabel[papel="info"] {{ color: {p['info']}; }}

#card {{ background: {p['superficie']}; border: 1px solid {p['borda']}; border-radius: {raio_cartao}px; }}
#novidades {{ background: {p['superficie']}; border: 1px solid {p['primaria']}; border-radius: {raio_cartao}px; }}
#novidades QLabel {{ background: transparent; }}
#novidades_titulo {{ color: {p['primaria']}; font-size: {f['secao']}px; font-weight: bold; }}
#card[clicavel="true"]:hover, #card[destaque="true"] {{ border: 1px solid {p['primaria']}; }}
#card_titulo {{ color: {p['texto_suave']}; font-size: {f['corpo']}px; font-weight: bold; }}
#card QLabel, #card QCheckBox, #card QRadioButton {{ background: transparent; }}

#console {{ background: {p['console_fundo']}; border: none; border-radius: {raio}px;
    color: {p['console_texto']}; font-family: {mono}; font-size: 12px; padding: 4px; }}
QPlainTextEdit#caixa_texto, QTextEdit#caixa_texto {{ background: {p['superficie_alta']}; color: {p['texto']};
    border: 1px solid {p['borda']}; border-radius: {raio}px; font-family: {mono}; font-size: 12px; }}
QPlainTextEdit#caixa_texto:focus {{ border-color: {p['primaria']}; }}
#notas {{ background: {p['superficie_alta']}; border: 1px solid {p['borda']}; border-radius: {raio}px;
    color: {p['texto']}; padding: 4px; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 2px solid {p['texto_suave']};
    border-radius: 4px; background: transparent; }}
QCheckBox::indicator:hover {{ border-color: {p['primaria']}; }}
QCheckBox::indicator:checked {{ background: {p['primaria']}; border-color: {p['primaria']}; }}
QCheckBox::indicator:disabled {{ border-color: {p['borda']}; }}
{tique}
QProgressBar {{ background: {p['superficie_alta']}; border: none; border-radius: 5px;
    min-height: 10px; max-height: 10px; }}
QProgressBar::chunk {{ background: {p['primaria']}; border-radius: 5px; }}
QLineEdit {{ background: {p['superficie_alta']}; border: {BORDA_CONTROLE}px solid {p['borda']};
    border-radius: {raio}px; color: {p['texto']}; placeholder-text-color: {p['texto_suave']};
    padding: 0 8px; min-height: {altura_campo}px; max-height: {altura_campo}px; }}
QLineEdit:focus {{ border-color: {p['primaria']}; }}
QLineEdit:disabled {{ color: {p['texto_suave']}; }}
QComboBox {{ background: {p['superficie_alta']}; border: {BORDA_CONTROLE}px solid {p['borda']};
    border-radius: {raio}px; padding: 0 10px; color: {p['texto']};
    min-height: {altura_campo}px; max-height: {altura_campo}px; }}
QComboBox:focus, QComboBox:on {{ border-color: {p['primaria']}; }}
QComboBox:disabled {{ color: {p['texto_suave']}; }}
QComboBox::drop-down {{ border: none; width: 26px; subcontrol-origin: padding;
    subcontrol-position: center right; }}
{seta}
QComboBox QAbstractItemView {{ background: {p['superficie']}; color: {p['texto']};
    selection-background-color: {menu['fundo']}; selection-color: {menu['texto']};
    border: 1px solid {p['borda']}; outline: none; }}

#barra_abas {{ background: {p['superficie_alta']}; border-radius: {raio}px; }}
#barra_abas QPushButton {{ background: transparent; border: none; border-radius: {raio}px;
    color: {p['texto']}; padding: 0 14px; }}
#barra_abas QPushButton:hover {{ background: {p['borda']}; }}
#barra_abas QPushButton:checked {{ background: {p['marca']}; color: {TEXTO_SOBRE_MARCA}; font-weight: bold; }}
#barra_abas QPushButton:checked:hover {{ background: {MARCA_HOVER}; }}

#seletor QPushButton[ativo="true"] {{ background: {menu['fundo']}; color: {menu['texto']};
    border-color: {menu['fundo']}; font-weight: bold; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['borda']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p['texto_suave']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['borda']}; border-radius: 3px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {p['texto_suave']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTreeView {{ background: {p['superficie']}; color: {p['texto']}; border: 1px solid {p['borda']};
    border-radius: {raio}px; outline: none; font-size: 12px; alternate-background-color: {p['superficie_alta']};
    selection-background-color: {menu['fundo']}; selection-color: {menu['texto']}; }}
QTreeView::item {{ min-height: {ALTURA_LINHA_TABELA}px; padding-left: 2px; border: none; }}
QTreeView::item:hover {{ background: {p['superficie_alta']}; }}
QTreeView::item:selected {{ background: {menu['fundo']}; color: {menu['texto']}; }}
QHeaderView {{ background: {p['superficie_alta']}; }}
QHeaderView::section {{ background: {p['superficie_alta']}; color: {p['texto']}; padding: 0 6px;
    border: none; border-right: 1px solid {p['borda']}; border-bottom: 1px solid {p['borda']};
    min-height: {ALTURA_LINHA_TABELA}px; font-size: 12px; font-weight: bold; }}

#barra_ferramentas {{ background: {p['superficie']}; border: 1px solid {p['borda']};
    border-radius: {raio_cartao}px; }}
#barra_ferramentas QLabel {{ background: transparent; }}
"""


def cor_da_linha(estado: str) -> str | None:
    """Cor do TEXTO de uma linha de tabela por estado, no tema atual: 'alerta'
    (documento repetido em mais de um grupo, data-alvo vencida) ou 'apagado'
    (já emitido). Desconhecido: `None` (cor padrão da tabela)."""
    p = paleta_atual()
    return {"alerta": p["perigo"], "apagado": p["texto_suave"]}.get(estado)


def _escurecer(cor: str, fator: float) -> str:
    """`cor` ("#RRGGBB") com cada canal multiplicado por `1 - fator`: o hover do
    botão de perigo, que não tem token próprio."""
    cor = cor.lstrip("#")
    canais = (round(int(cor[i:i + 2], 16) * (1 - fator)) for i in (0, 2, 4))
    return "#" + "".join(f"{c:02X}" for c in canais)
