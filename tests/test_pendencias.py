"""Atualizar a planilha de pendências direto do Aconex (spec, seções 8 e 13).

Planilha e questões fictícias, na estrutura medida na planilha real e na API.
"""
from __future__ import annotations

import json
import re
import zipfile
from datetime import date

import openpyxl
import pytest

from builders import COLUNAS_PENDENCIAS, escrever_planilha_pendencias, linha_pendencia
from docmanager import aconex_backend as ab
from docmanager import field_backend as fb
from docmanager.services import gravacao
from docmanager.services import pendencias_update as pu
from docmanager.services import xlsx_cirurgico as xc
from docmanager.services.sobrescricao import DecisaoSobrescricao

CONFIG = ab.AconexConfig(client_id="c", client_secret="s", user_id="u", project_id="1")
IMPEDITIVA = {"Clasificación de pendencia": "Impeditiva"}
DESTAQUE = "FFF4B183"
AZUL, VERMELHO, PRETO = "FF0070C0", "FFFF0000", "FF000000"

CAMPOS = [  # rótulo → (family_id, tipo)
    ("TAG RDS-PP", "F-TAG", "single_select"),
    ("Clasificación de pendencia", "F-CLASSIF", "single_select"),
    ("Documentos de referencia", "F-DOCS", "multi_line_text"),
    ("Fecha prevista para corrección", "F-DATA", "date"),
    ("Cierre", "F-CIERRE", "single_select"),
    ("Área del Solicitante", "F-SOLIC", "single_select"),
    ("¿Pasó a comisionamiento?", "F-PASSOU", "boolean"),
    ("Área responsable SM.DT", "F-RESP", "single_select"),
]
DEFINICOES = [{"id": f"v2-{fam}", "family_id": fam, "label": rot, "type": {"name": tipo}}
              for rot, fam, tipo in CAMPOS]
STATUS_API = {"Open": "Open", "Closed": "Closed", "Work Done": "WorkDone", "In dispute": "InDispute"}


def questao(numero, **valores) -> dict:
    """A questão do Aconex que corresponde a `linha_pendencia(numero, **valores)`."""
    v = linha_pendencia(numero, **valores)
    area = v["Area"].split(" > ")
    campos = []
    for rot, fam, tipo in CAMPOS:
        valor = v.get(rot)
        if tipo == "boolean" and valor:
            valor = {"Sim": "Yes", "Não": "No"}[valor]
        campos.append({"id": f"v1-{fam}", "family_id": fam, "value": valor or None})
    return {
        "issue_id": f"id-{numero}", "issue_number": str(numero),
        "description": v["Issue Description"], "status": STATUS_API[v["Status"]],
        "location_detail": v.get("Location Detail") or "",
        "issue_type": {"id": "9001", "name": v["Issue Type"]},
        "area": {"name": area[-1], "path": [{"name": n} for n in area[:-1]]},
        "meta_data": {"created_at": f"{v['Captured On']}T15:00:00.000Z",
                      "created_by": {"first_name": "FULANO", "last_name": "DE TAL"}},
        "due_date": f"{v['Due Date']}T12:00:00.000Z",
        "custom_fields": campos,
    }


@pytest.fixture
def api(monkeypatch):
    """`api["questoes"]` é o que o Aconex devolve; `api["chamadas"]` conta as buscas."""
    estado = {"questoes": [], "chamadas": 0, "erro": None, "conversas": {},
              "tipos": [{"id": "9001", "custom_fields": DEFINICOES}]}

    def extrair(config, *, log_cb=None, progress_cb=None, com_comentarios=True):
        estado["chamadas"] += 1
        if estado["erro"]:
            raise estado["erro"]
        return fb.ExtracaoQuestoes(list(estado["questoes"]), DEFINICOES, estado["tipos"],
                                   dict(estado["conversas"]))

    monkeypatch.setattr(fb, "extrair_questoes", extrair)
    return estado


def _rodar(caminho, decidir=None, **kw):
    logs = []
    r = pu.atualizar_pendencias(CONFIG, caminho, log_cb=logs.append, decidir_cb=decidir, **kw)
    r.logs = logs
    return r


def _restos(pasta):
    return [p.name for p in pasta.iterdir() if p.name.startswith("~$docmanager-")]


def _cenario(tmp_path, api):
    """Planilha com 6 pendências e um Aconex com 2 novas e mudanças em várias."""
    caminho = tmp_path / "ACONEX - MAPEAMENTO PENDÊNCIAS.xlsx"
    escrever_planilha_pendencias(caminho, [
        linha_pendencia(10, **IMPEDITIVA),                                    # vai fechar
        linha_pendencia(9, **IMPEDITIVA),                                     # sem mudança, fonte azul
        linha_pendencia(8, **{"Responsável": "PESSOA MANUAL"}),               # vira impeditiva
        linha_pendencia(7, **{"Captured On": date(2026, 10, 1), "Location Detail": None}),
        linha_pendencia(6, **{"¿Pasó a comisionamiento?": "#TAG DESLOCADO",
                              "Fecha prevista para corrección": "2026-12-01"}),
        linha_pendencia(5),                                                   # só na planilha
    ], fonte_azul=(9,))
    api["questoes"] = [
        questao(12, **IMPEDITIVA),
        questao(11),
        questao(10, Status="Closed", **IMPEDITIVA),
        questao(9, **IMPEDITIVA),
        questao(8, **IMPEDITIVA),
        questao(7, Status="Work Done"),                     # troca; Location Detail preenchida
        questao(6, **{"¿Pasó a comisionamiento?": None}),   # dois apagamentos
    ]
    return caminho


def test_cenario_completo(tmp_path, api):
    caminho = _cenario(tmp_path, api)
    perguntas = []

    def decidir(itens):
        perguntas.append(itens)
        apagar = {i for i, a in enumerate(itens) if a.titulo_coluna == "¿Pasó a comisionamiento?"}
        return DecisaoSobrescricao(aceitas=frozenset(apagar),
                                   recusadas=frozenset(set(range(len(itens))) - apagar))

    r = _rodar(caminho, decidir)
    assert r.ok and r.gravou, r.logs
    assert r.novas == [12, 11] and r.novas_destacadas == 1
    assert r.so_na_planilha == [5]
    # 10 fechou; 7 virou Work Done; 8 virou impeditiva
    assert r.atualizadas == {"Status": 2, "Clasificación de pendencia": 1}
    assert r.preenchidas == 1                        # Location Detail da 7
    assert (r.apagadas, r.mantidas) == (1, 1)
    assert (r.ganharam_cor, r.perderam_cor) == (1, 1)
    assert r.backup and "Cópia de segurança" in r.mensagem
    assert len(perguntas) == 1 and len(perguntas[0]) == 2
    assert {a.titulo_coluna for a in perguntas[0]} == {"¿Pasó a comisionamiento?",
                                                       "Fecha prevista para corrección"}
    assert _restos(tmp_path) == []

    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    numeros = [ws.cell(r, 1).value for r in range(5, 13)]
    assert numeros == [12, 11, 10, 9, 8, 7, 6, 5]
    assert ws.tables["tbRegistros"].ref == "A4:V12"
    linha = {n: r for r, n in enumerate(numeros, 5)}
    cor = lambda n, col="A": ws[f"{col}{linha[n]}"].fill.fgColor.rgb  # noqa: E731

    def texto(n, col="A"):
        c = ws[f"{col}{linha[n]}"].font.color
        return c.rgb if c is not None and c.type == "rgb" else None   # None = automática (preta)
    sem_laranja = lambda n: all(cor(n, c) != DESTAQUE for c in "ABCHJV")  # noqa: E731

    # O destaque agora é o texto vermelho, sem preenchimento (pedido de 2026-11-02).
    assert texto(12) == VERMELHO and texto(12, "V") == VERMELHO and texto(12, "J") == VERMELHO
    assert sem_laranja(12)                                           # nova impeditiva: vermelha
    assert texto(11) == AZUL and texto(11, "H") == AZUL               # nova normal: azul
    assert cor(11, "H") == "FFD9D9D9"                                 # H continua cinza
    assert sem_laranja(10) and texto(10) in (None, PRETO)             # fechou: sem cor; a célula
    assert texto(10, "H") == AZUL and ws[f"H{linha[10]}"].value == "Closed"   # trocada fica azul
    assert texto(10, "B") in (None, PRETO)                            # o resto da linha, preto
    assert cor(10, "H") == "FFD9D9D9" and cor(10, "J") == "FFDDEBF7"  # voltou ao modelo normal
    assert texto(9) == VERMELHO and sem_laranja(9)                    # continua impeditiva
    assert texto(8) == VERMELHO and texto(8, "J") == VERMELHO         # ganhou o vermelho
    assert ws[f"J{linha[8]}"].value == "PESSOA MANUAL"                # manual intacta
    assert texto(7, "H") == AZUL and texto(7, "D") == AZUL            # trocada e preenchida
    assert texto(7, "B") != AZUL                                      # o resto não
    assert ws["A2"].fill.fgColor.rgb != DESTAQUE                      # legenda sem laranja
    assert ws["B2"].font.color.rgb == VERMELHO                        # e o texto vermelho
    assert ws[f"E{linha[10]}"].border.bottom.style == "thin"           # borda preservada
    assert ws[f"H{linha[7]}"].value == "Work Done"
    assert ws[f"D{linha[7]}"].value == "PAINEL-7"
    assert ws[f"F{linha[7]}"].is_date                                  # data real igual: intocada
    assert ws[f"T{linha[6]}"].value is None                            # apagada
    assert ws[f"Q{linha[6]}"].value == "2026-12-01"                    # mantida
    assert ws[f"B{linha[12]}"].value == "05. Pendencia de Comisionamiento"
    assert ws[f"F{linha[12]}"].value == "2026-10-01"
    assert ws.column_dimensions["M"].hidden and ws.freeze_panes == "C5"

    with open(gravacao.pasta_backups() / r.backup.split("/")[-1].split("\\")[-1], "rb"):
        pass
    memoria = json.loads((tmp_path / "dados" / pu.ARQUIVO_MANTIDAS).read_text(encoding="utf-8"))
    assert memoria["mantidas"] == [{"numero": 6, "coluna": "Fecha prevista para corrección",
                                    "valor": "2026-12-01"}]


def test_partes_intactas_byte_a_byte(tmp_path, api):
    caminho = _cenario(tmp_path, api)
    with zipfile.ZipFile(caminho) as z:
        antes = {i.filename: z.read(i) for i in z.infolist()}
    assert _rodar(caminho, lambda itens: DecisaoSobrescricao.aceitar_todas(len(itens))).gravou
    with zipfile.ZipFile(caminho) as z:
        depois = {i.filename: z.read(i) for i in z.infolist()}
        assert [i.filename for i in z.infolist()] == list(antes)
    mudaram = {n for n in antes if antes[n] != depois[n]}
    assert mudaram <= {"xl/worksheets/sheet1.xml", "xl/tables/table1.xml", "xl/styles.xml"}
    assert depois["xl/charts/chart1.xml"] == antes["xl/charts/chart1.xml"]
    assert depois["customXml/item1.xml"] == antes["customXml/item1.xml"]
    raiz = lambda b: b.decode().split("<sheetData>")[0]  # noqa: E731
    assert raiz(depois["xl/worksheets/sheet1.xml"]) == raiz(antes["xl/worksheets/sheet1.xml"]).replace(
        "A2:V10", "A2:V12")


def test_memoria_nao_pergunta_de_novo_e_nada_mudou_nao_grava(tmp_path, api):
    caminho = _cenario(tmp_path, api)
    assert _rodar(caminho, lambda itens: DecisaoSobrescricao.recusar_todas(len(itens))).gravou
    antes = caminho.read_bytes()
    perguntas = []
    r = _rodar(caminho, lambda itens: perguntas.append(itens))
    assert perguntas == []
    assert r.ok and not r.gravou and "já está atualizada" in r.mensagem
    assert r.mantidas == 2
    assert caminho.read_bytes() == antes


def test_memoria_pergunta_de_novo_se_o_valor_mudou(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3, Cierre="SIM")])
    api["questoes"] = [questao(3)]
    assert not _rodar(caminho, lambda itens: DecisaoSobrescricao.recusar_todas(len(itens))).gravou
    escrever_planilha_pendencias(caminho, [linha_pendencia(3, Cierre="OUTRO")])
    perguntas = []
    _rodar(caminho, lambda itens: perguntas.append(itens))
    assert len(perguntas) == 1 and perguntas[0][0].valor_planilha == "OUTRO"


def test_janela_fechada_mantem_sem_memorizar(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3, Cierre="SIM")])
    api["questoes"] = [questao(3)]
    r = _rodar(caminho, lambda itens: None)
    assert r.mantidas == 1 and r.apagadas == 0
    perguntas = []
    _rodar(caminho, lambda itens: perguntas.append(itens))
    assert len(perguntas) == 1


def test_falha_da_api_nao_grava(tmp_path, api):
    caminho = _cenario(tmp_path, api)
    antes = caminho.read_bytes()
    api["erro"] = fb.ErroField("HTTP 503")
    r = _rodar(caminho)
    assert not r.ok and "503" in r.mensagem
    assert caminho.read_bytes() == antes and _restos(tmp_path) == []


def test_recusa_nao_busca_a_api_nem_grava(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), linha_pendencia(3)])
    antes = caminho.read_bytes()
    r = _rodar(caminho)
    assert not r.ok and "mais de uma vez" in r.mensagem
    assert api["chamadas"] == 0
    assert caminho.read_bytes() == antes


def test_validador_que_reprova_nao_grava(tmp_path, api, monkeypatch):
    caminho = _cenario(tmp_path, api)
    antes = caminho.read_bytes()
    monkeypatch.setattr(pu, "validar", lambda *_a: ["linha trocada"])
    r = _rodar(caminho, lambda itens: None)
    assert not r.ok and "linha trocada" in r.mensagem
    assert caminho.read_bytes() == antes and _restos(tmp_path) == []
    assert not (tmp_path / "dados" / "backups").exists() or not list((tmp_path / "dados" / "backups").iterdir())


def test_validador_aceita_o_resultado_do_proprio_plano(tmp_path, api, monkeypatch):
    """O validador de verdade roda em todo teste que grava; aqui ele precisa ter rodado."""
    caminho = _cenario(tmp_path, api)
    chamadas = []
    original = pu.validar
    monkeypatch.setattr(pu, "validar", lambda *a: chamadas.append(1) or original(*a))
    assert _rodar(caminho, lambda itens: None).gravou
    assert chamadas == [1]


def test_impeditiva_fica_vermelha_mesmo_sem_exemplo_na_planilha(tmp_path, api):
    """O vermelho é a cor do texto, não um preenchimento descoberto pelos dados:
    funciona mesmo que a planilha não tenha nenhuma linha destacada."""
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)])
    api["questoes"] = [questao(4, **IMPEDITIVA), questao(3)]
    assert _rodar(caminho).gravou
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert ws["A5"].value == 4 and ws["A5"].font.color.rgb == VERMELHO
    assert ws["A5"].fill.fgColor.rgb != DESTAQUE


def test_azul_da_execucao_anterior_vira_preto_quando_chega_algo_novo(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)], fonte_azul=(3,))   # azul à mão
    api["questoes"] = [questao(4), questao(3)]
    assert _rodar(caminho).gravou
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert ws["A5"].font.color.rgb == AZUL                       # a nova: azul
    assert ws["A6"].font.color.rgb == PRETO                      # o azul de antes: preto

    api["questoes"] = [questao(5), questao(4), questao(3)]
    assert _rodar(caminho).gravou
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert [ws.cell(r, 1).value for r in (5, 6, 7)] == [5, 4, 3]
    assert ws["A5"].font.color.rgb == AZUL                       # o lote de agora
    assert ws["A6"].font.color.rgb == PRETO                      # o lote anterior
    assert ws["A6"].font.bold == ws["A7"].font.bold              # só a cor muda


def test_sem_nada_novo_o_azul_fica(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)])
    api["questoes"] = [questao(4), questao(3)]
    assert _rodar(caminho).gravou
    antes = caminho.read_bytes()
    assert not _rodar(caminho).gravou                            # nada novo: nada muda
    assert caminho.read_bytes() == antes
    assert openpyxl.load_workbook(caminho)["PENDÊNCIAS"]["A5"].font.color.rgb == AZUL

def test_so_atualizacoes_sem_novas(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), linha_pendencia(2)])
    api["questoes"] = [questao(3, Status="In dispute"), questao(2)]
    r = _rodar(caminho)
    assert r.gravou and r.novas == []
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert ws.tables["tbRegistros"].ref == "A4:V6"
    assert ws["H5"].value == "In dispute"


def test_texto_dificil_e_comentarios(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)])
    api["questoes"] = [questao(4, **{"Issue Description": "=1+1 & <b> \x01 fim"}), questao(3)]
    api["conversas"] = {"id-4": [{"participant": {"id": "-1", "trading_name": "Everyone"},
                                  "comments": [{"content": "ok", "client_captured_at": "2026-09-30T14:00:00Z",
                                                "author": {"first_name": "A", "last_name": "B",
                                                           "organization": {"trading_name": "CMI"}}}]}]}
    assert _rodar(caminho).gravou
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert ws["E5"].value == "=1+1 & <b>  fim" and ws["E5"].data_type == "s"
    assert ws["V5"].value.startswith("With Everyone:\n\"ok\" submitted by A B (CMI)")


def test_coluna_manual_com_nome_de_campo_de_outro_modulo_nao_e_tocada(tmp_path, api):
    colunas = [("Especialidad" if c == "Responsável" else c) for c in COLUNAS_PENDENCIAS]
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3, Especialidad="MANUAL")], colunas=colunas)
    api["tipos"] = [{"id": "9001", "custom_fields": DEFINICOES},
                    {"id": "777", "custom_fields": [{"label": "Especialidad"}]}]
    api["questoes"] = [questao(3, Status="Closed")]
    perguntas = []
    assert _rodar(caminho, lambda itens: perguntas.append(itens)).gravou
    assert perguntas == []
    assert openpyxl.load_workbook(caminho)["PENDÊNCIAS"]["J5"].value == "MANUAL"


def test_sem_planilha_valida(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    openpyxl.Workbook().save(caminho)
    r = _rodar(caminho)
    assert not r.ok and "Tabela do Excel" in r.mensagem and api["chamadas"] == 0


def test_rodar_de_novo_depois_de_gravar_nao_acha_mudanca(tmp_path, api):
    """Texto com caractere proibido ou comentário com quebra de linha não pode virar
    uma 'troca' a cada execução."""
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3)])
    api["questoes"] = [questao(4, **{"Issue Description": "a\x01b\n\nc  d"}), questao(3)]
    assert _rodar(caminho).gravou
    antes = caminho.read_bytes()
    r = _rodar(caminho)
    assert not r.gravou and "já está atualizada" in r.mensagem
    assert caminho.read_bytes() == antes


def test_data_real_que_mudou_vira_data_real(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3, **{"Captured On": date(2026, 10, 1)})])
    api["questoes"] = [questao(3, **{"Captured On": "2026-10-05"})]
    assert _rodar(caminho).gravou
    celula = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]["F5"]
    assert celula.is_date and celula.value.date() == date(2026, 10, 5)


def test_issue_number_guardado_como_texto_nao_reprova_a_conferencia(tmp_path, api):
    """Na planilha real há Issue Number digitado como texto ("131"); a conferência
    comparava texto com número e recusava tudo ("a ordem das pendências não é a planejada")."""
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3, **{"Issue Number": "3"}), linha_pendencia(2)])
    api["questoes"] = [questao(4), questao(3), questao(2)]
    r = _rodar(caminho)
    assert r.ok and r.gravou, r.mensagem
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert [ws.cell(n, 1).value for n in (5, 6, 7)] == [4, "3", 2]


# --- Registros manuais (pedido da equipe, 2026-11-06) -----------------------------------

def registro_manual(chave="M-01", **valores) -> dict:
    """Uma linha feita pela equipe no fim da tabela: sem número do Aconex no Issue Number."""
    base = {"Issue Number": chave, "Issue Type": "Registro da equipe", "Area": "PROJETO EXEMPLO",
            "Issue Description": f"Achado em campo {chave}", "Captured On": "2026-11-01",
            "Status": "Open", "Responsável": "PESSOA MANUAL"}
    base.update(valores)
    return base


def _cor_do_texto(ws, ref):
    c = ws[ref].font.color
    return c.rgb if c is not None and c.type == "rgb" else None   # None = automática (preta)


def test_registros_manuais_no_fim_ficam_intactos_e_descem(tmp_path, api):
    """Issue Number com letras ou vazio não é do Aconex: nem o valor nem o formato da
    linha mudam (nem o vermelho de impeditiva, nem a volta do azul ao preto); ela só
    desce junto com o resto quando entram pendências novas no topo."""
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [
        linha_pendencia(3, **{"Responsável": "PESSOA A"}),
        linha_pendencia(2, **IMPEDITIVA),
        registro_manual("M-01", **IMPEDITIVA),                     # impeditiva aberta, feita à mão
        registro_manual("M-02"),                                   # azul à mão
        registro_manual(None, **{"Issue Description": "Sem número"}),
    ], fonte_azul=("M-02",))
    antes = xc.ler(caminho, pu.CHAVE)
    api["questoes"] = [questao(5, **IMPEDITIVA), questao(4), questao(3, Status="Closed"),
                       questao(2, **IMPEDITIVA)]
    r = _rodar(caminho)
    assert r.ok and r.gravou, r.mensagem
    assert r.novas == [5, 4] and r.so_na_planilha == [] and r.acima_do_aconex == []
    assert (r.manuais, r.manuais_sem_numero) == (3, 1)
    assert "3 registros manuais, sem número do Aconex, ficaram como estavam." in r.mensagem
    assert "1 registro manual está com o Issue Number vazio" in r.mensagem
    assert any("2 pendências do Aconex e 3 registros manuais" in m for m in r.logs)

    depois = xc.ler(caminho, pu.CHAVE)
    assert depois.tabela.ref == "A4:V11"
    for linha in (7, 8, 9):                  # cada registro: o mesmo XML, duas linhas abaixo
        assert pu._sem_enderecos(depois.linha(linha + 2)) == pu._sem_enderecos(antes.linha(linha))
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert [ws.cell(n, 1).value for n in range(5, 12)] == [5, 4, 3, 2, "M-01", "M-02", None]
    assert ws["H7"].value == "Closed" and ws["J7"].value == "PESSOA A"     # do Aconex: em dia
    assert _cor_do_texto(ws, "A5") == VERMELHO                              # nova impeditiva
    assert _cor_do_texto(ws, "A9") != VERMELHO                              # M-01: sem vermelho
    assert _cor_do_texto(ws, "A10") == AZUL                                 # M-02: o azul fica
    assert ws["E11"].value == "Sem número" and ws["J9"].value == "PESSOA MANUAL"


def test_registro_manual_no_meio_da_tabela_fica_no_lugar(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), registro_manual("EXTRA 1"), linha_pendencia(2)])
    api["questoes"] = [questao(4), questao(3, Status="Work Done"), questao(2)]
    r = _rodar(caminho)
    assert r.ok and r.gravou and r.manuais == 1, r.mensagem
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert [ws.cell(n, 1).value for n in range(5, 9)] == [4, 3, "EXTRA 1", 2]
    assert ws["H6"].value == "Work Done" and ws["H7"].value == "Open"


def test_linha_vazia_no_fim_da_tabela_nao_reprova(tmp_path, api):
    """Tabela estendida para digitar depois: a última linha ainda vazia. O pandas não a
    lê (descarta as vazias do fim), e a conferência não pode contar com ela."""
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), linha_pendencia(2), {}])
    api["questoes"] = [questao(4), questao(3), questao(2)]
    r = _rodar(caminho)
    assert r.ok and r.gravou, r.mensagem
    assert r.manuais == 0 and "registro manual" not in r.mensagem
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert ws.tables["tbRegistros"].ref == "A4:V8"
    assert [ws.cell(n, 1).value for n in range(5, 9)] == [4, 3, 2, None]


def test_tabela_so_com_registros_manuais_recebe_as_pendencias(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [registro_manual("M-01")])
    api["questoes"] = [questao(2, **IMPEDITIVA), questao(1)]
    r = _rodar(caminho)
    assert r.ok and r.gravou and r.novas == [2, 1], r.mensagem
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert [ws.cell(n, 1).value for n in range(5, 8)] == [2, 1, "M-01"]
    assert _cor_do_texto(ws, "A5") == VERMELHO and _cor_do_texto(ws, "A6") == AZUL


def test_tabela_sem_nenhuma_linha_gravada_recebe_as_pendencias(tmp_path, api):
    """A linha da tabela vazia pode nem estar no XML: sem modelo, as novas vão sem estilo."""
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [{}])
    with zipfile.ZipFile(caminho) as z:
        partes = [(i, z.read(i)) for i in z.infolist()]
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        for info, dados in partes:
            if info.filename == "xl/worksheets/sheet1.xml":
                dados = re.sub(rb'<row r="5".*?</row>', b"", dados, flags=re.S)
            z.writestr(info, dados)
    api["questoes"] = [questao(2), questao(1)]
    r = _rodar(caminho)
    assert r.ok and r.gravou, r.mensagem
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert ws.tables["tbRegistros"].ref == "A4:V7"
    assert [ws.cell(n, 1).value for n in range(5, 8)] == [2, 1, None]


def test_registro_manual_com_numero_repetido_recusa_e_explica(tmp_path, api):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), linha_pendencia(2), registro_manual(3)])
    antes = caminho.read_bytes()
    r = _rodar(caminho)
    assert not r.ok and api["chamadas"] == 0
    assert "'Issue Number' 3 aparece mais de uma vez na tabela (linhas 5 e 7)" in r.mensagem
    assert "use letras" in r.mensagem
    assert caminho.read_bytes() == antes


def test_numero_acima_do_ultimo_do_aconex_fica_e_avisa(tmp_path, api):
    """Registro feito à mão numerado na sequência (151 com o Aconex no 4) seria tomado
    pela pendência 151 quando ela existir: fica como está, mas o aviso diz para trocar."""
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), linha_pendencia(2), registro_manual(151)])
    api["questoes"] = [questao(4), questao(3), questao(2)]
    r = _rodar(caminho)
    assert r.ok and r.gravou, r.mensagem
    assert r.so_na_planilha == [151] and r.acima_do_aconex == [151] and r.manuais == 0
    assert "o Issue Number 151 é maior que o último do Aconex (4)" in r.mensagem
    assert "troque por letras" in r.mensagem
    assert "Nenhuma pendência da planilha sumiu do Aconex." in r.mensagem
    ws = openpyxl.load_workbook(caminho)["PENDÊNCIAS"]
    assert ws["A8"].value == 151 and ws["E8"].value == "Achado em campo 151"


def test_validador_reprova_registro_manual_alterado(tmp_path, api, monkeypatch):
    caminho = tmp_path / "p.xlsx"
    escrever_planilha_pendencias(caminho, [linha_pendencia(3), registro_manual("M-01")])
    api["questoes"] = [questao(4), questao(3)]
    antes = caminho.read_bytes()
    aplicar = xc.aplicar

    def mexe_no_registro_manual(pasta, edicao, avisar=None):
        partes = aplicar(pasta, edicao, avisar)
        aba = partes[pasta.aba_parte].decode("utf-8")   # M-01 desceu da linha 6 para a 7
        partes[pasta.aba_parte] = re.sub(r'(<c r="J7" s=")\d+(")', r"\g<1>0\g<2>", aba).encode("utf-8")
        return partes

    monkeypatch.setattr(xc, "aplicar", mexe_no_registro_manual)
    r = _rodar(caminho)
    assert not r.ok and "o registro manual da linha 6 mudou" in r.mensagem
    assert caminho.read_bytes() == antes and _restos(tmp_path) == []
