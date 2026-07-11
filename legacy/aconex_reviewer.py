import customtkinter as ctk
from tkinter import filedialog, messagebox
import numpy as np
import openpyxl
from collections import Counter 
from openpyxl.chart import BarChart, Reference, Series
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.chart.marker import DataPoint
from openpyxl.chart.axis import ChartLines
from openpyxl.drawing.line import LineProperties
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.fill import PatternFillProperties, ColorChoice
import pandas as pd
import os
import json
from datetime import datetime
import sys
import threading
import requests
import base64
import urllib3
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from tkinter import ttk
from datetime import timedelta
import threading
import webbrowser
from PIL import Image
import urllib.request
from data_manager import DataManager
import dash_ib # type: ignore
from dotenv import load_dotenv
try:
    import pyi_splash # type: ignore
except ImportError:
    pass
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
# --- 1. gerenciador de Configurações (Memória na Pasta Documentos) ---
class ConfigManager:
    # Define o caminho: C:\Users\Nome\Documents\DocManager_Itaipu\config.json
    _DOCS_DIR = os.path.join(os.path.expanduser("~"), "Documents")
    _APP_DIR = os.path.join(_DOCS_DIR, "DocManager_Itaipu")
    CONFIG_FILE = os.path.join(_APP_DIR, "config.json")
    @staticmethod
    def _ensure_folder():
        """Cria a pasta no Documentos se ela não existir"""
        if not os.path.exists(ConfigManager._APP_DIR):
            try:
                os.makedirs(ConfigManager._APP_DIR)
            except Exception as e:
                print(f"Erro ao criar pasta de config: {e}")
    @staticmethod
    def load_config():
        if os.path.exists(ConfigManager.CONFIG_FILE):
            try:
                with open(ConfigManager.CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    @staticmethod
    def save_config(key, value):
        ConfigManager._ensure_folder() # Garante que a pasta existe antes de salvar
        config = ConfigManager.load_config()
        config[key] = value
        try:
            with open(ConfigManager.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar config: {e}")
    @staticmethod
    def get_last_path(key_suffix):
        """
        Recupera o caminho. Se o caminho salvo não existir neste PC 
        (ex: troca de usuário), retorna a pasta Documentos.
        """
        config = ConfigManager.load_config()
        saved_path = config.get(f"last_path_{key_suffix}", "")
        # Validação Inteligente:
        # Se existe um caminho salvo E esse caminho é válido neste computador:
        if saved_path and os.path.exists(saved_path):
            return saved_path

        # Se não, retorna a pasta Documentos padrão para não dar erro
        return ConfigManager._DOCS_DIR
# --- 2. Janela de Erro ao Salvar (Pop-up Customizado) ---
class SaveRetryDialog(ctk.CTkToplevel):
    def __init__(self, master, filename, retry_callback):
        super().__init__(master)
        self.retry_callback = retry_callback
        self.filename = filename

        self.title("Arquivo Aberto")
        self.geometry("400x200")
        self.attributes("-topmost", True)

        self.update_idletasks()
        try:
            x = master.winfo_x() + (master.winfo_width() // 2) - 200
            y = master.winfo_y() + (master.winfo_height() // 2) - 100
            self.geometry(f"+{x}+{y}")
        except:
            pass
        label = ctk.CTkLabel(self, text=f"Não foi possível salvar o arquivo:\n\n{os.path.basename(filename)}\n\nEle parece estar aberto. Feche-o e tente novamente.", wraplength=350)
        label.pack(pady=20, padx=20)
        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.pack(pady=10)
        btn_cancel = ctk.CTkButton(frame_btns, text="Cancelar", fg_color="red", command=self.destroy)
        btn_cancel.pack(side="left", padx=10)
        btn_retry = ctk.CTkButton(frame_btns, text="Tentar Novamente", command=self.tentar_novamente)
        btn_retry.pack(side="left", padx=10)
    def tentar_novamente(self):
        self.destroy()
        self.retry_callback()
# --- 3. Manipulador de Excel (I/O) ---
class ExcelHandler:
    def selecionar_arquivo(self, tipo_arquivo):
        initial_dir = ConfigManager.get_last_path(tipo_arquivo)
        filename = filedialog.askopenfilename(
            title=f"Selecione o arquivo ({tipo_arquivo})",
            initialdir=initial_dir,
            filetypes=[("Excel Files", "*.xlsx *.xlsm *.xls")]
        )
        if filename:
            ConfigManager.save_config(f"last_path_{tipo_arquivo}", os.path.dirname(filename))
        return filename
    def listar_abas(self, caminho_arquivo):
        try:
            workbook = openpyxl.load_workbook(caminho_arquivo, read_only=True, keep_links=False)
            sheet_names = workbook.sheetnames
            workbook.close()
            return sheet_names
        except Exception as e:
            print(f"Erro ao ler abas: {e}")
            return []
    def salvar_com_retry(self, workbook, caminho, parent_window_for_popup):
        saved = False
        while not saved:
            try:
                workbook.save(caminho)
                saved = True
                return True
            except PermissionError:
                user_retry = [False]
                def on_retry(): user_retry[0] = True
                dialog = SaveRetryDialog(parent_window_for_popup, caminho, on_retry)
                parent_window_for_popup.wait_window(dialog)
                if not user_retry[0]: return False
            except Exception as e:
                messagebox.showerror("Erro Crítico", f"Erro ao salvar: {e}")
                return False
    def salvar_arquivo(self, default_name="Relatorio.xlsx", defaultextension=".xlsx", filetypes=None):
        """
        Abre a janela de diálogo 'Salvar Como' e retorna o caminho escolhido pelo usuário.
        """
        # Tenta pegar o último local onde o usuário salvou algo
        initial_dir = ConfigManager.get_last_path("last_save_dir")

        if filetypes is None:
            filetypes = [("Excel Files", "*.xlsx")]
        filename = filedialog.asksaveasfilename(
            title="Salvar Arquivo Como",
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=defaultextension,
            filetypes=filetypes
        )
        if filename:
            # Salva o diretório escolhido para a próxima vez
            ConfigManager.save_config("last_path_last_save_dir", os.path.dirname(filename))

        return filename
# --- 5. Tela de Mapeamento (View) ---
class MappingView(ctk.CTkFrame):
    def __init__(self, master, excel_handler, **kwargs):
        super().__init__(master, **kwargs)
        self.excel_handler = excel_handler
        self.data_manager = DataManager() # Instancia a lógica

        self.path_aconex = None
        self.path_mapping = None
        self.sheet_aconex = ctk.StringVar()
        self.sheet_mapping = ctk.StringVar()
        self.row_header = 1
        self.colunas_lista_planos_execução = {
            'primeiro_título':                       'GRUPO',
            'coluna_grupo':                          'GRUPO',
            'coluna_sistema':                        'SISTEMA',
            'coluna_oep':                            'OEP',
            'coluna_etapa_1':                        'ETAPA 1',
            'coluna_etapa_2':                        'ETAPA 2',
            'coluna_etapa_3':                        'ETAPA 3',
            'coluna_etapa_4':                        'ETAPA 4',
            'coluna_código_cmi':                     'Nº CMI',
            'coluna_código_itaipu':                  'N° ITAIPU',
            'coluna_descrição':                      'DESCRIÇÃO DO DOCUMENTO',
            'coluna_mês_referência':                 'MÊS DE REFERÊNCIA',
            'coluna_data_previsão_emissão_etapa_1':  'DATA PREVISTA EMISSÃO ETAPA 1',
            'coluna_reprogramada_etapa_1':           'DATA REPROGRAMADA',
            'coluna_data_previsão_emissão_etapa_2':  'DATA PREVISTA EMISSÃO ETAPA 2',
            'coluna_reprogramada_etapa_2':           'DATA REPROGRAMADA',
            'coluna_data_previsão_emissão_etapa_3':  'DATA PREVISTA EMISSÃO ETAPA 3',
            'coluna_reprogramada_etapa_3':           'DATA REPROGRAMADA',
            'coluna_data_previsão_emissão_etapa_4':  'DATA PREVISTA EMISSÃO ETAPA 4 OU DEMAIS',
            'coluna_reprogramada_etapa_4':           'DATA REPROGRAMADA',
            'coluna_emitido_não_emitido':            'EMITIDO / NÃO EMITIDO',
            'coluna_data_último_status':             'DATA ÚLTIMA EMISSÃO',
            'coluna_revisão':                        'ÚLTIMA REV. EMITIDA',
            'coluna_responsável':                    'RESPONSÁVEL',
            'coluna_status_real':                    'STATUS REAL',
            'coluna_status_emissão':                 'STATUS',
            'coluna_observação':                     'OBSERVAÇÃO',
            'coluna_nível':                          'NÍVEL',
            'coluna_status_consolidado':             'STATUS CONSOLIDADO',
            'coluna_com_itaipu':                     'COM ITAIPU',
            'coluna_plano_de_execução':              'PLANO DE EXECUÇÃO',
            'coluna_predecessor':                    'PREDECESSOR',
            'coluna_resumo_quantidades':             'RESUMO QUANTIDADES',
            'coluna_filtro_etapa':                   'TAG ETAPA',
            # --- NOVAS COLUNAS DO POWER BI ---
            'coluna_dias_status':                    'DIAS NO STATUS ATUAL',
            'coluna_situacao_prazo':                 'SITUAÇÃO DO PRAZO',
            'coluna_dias_atraso':                    'DIAS DE ATRASO',
            'coluna_total_ciclos':                   'TOTAL DE CICLOS',
            'coluna_ciclos_aprovar':                 'CICLOS PARA APROVAR',
            'coluna_downgrade':                      'DOWNGRADE',
            # --- NOVAS COLUNAS DE ATRASO ACUMULADO ---
            'coluna_atraso_acum_ib':                 'ATRASO ACUMULADO IB',
            'coluna_atraso_acum_cmi':                'ATRASO ACUMULADO CMI'
        }
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(7, weight=1) # <- MUDANÇA CHAVE: Agora é a linha 7 que estica!

        self.label_title = ctk.CTkLabel(self, text="Atualização de Mapeamento de Planos", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.frame_aconex = ctk.CTkFrame(self)
        self.frame_aconex.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        self.criar_componentes_aconex()
        self.frame_mapping = ctk.CTkFrame(self)
        self.frame_mapping.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        self.criar_componentes_mapping()
        # --- NOVO BLOCO: CONTROLE DE DOCUMENTOS (KAIZEN) ---
        self.path_controle = None
        self.sheet_controle = ctk.StringVar()
        self.frame_controle = ctk.CTkFrame(self)
        self.frame_controle.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.criar_componentes_controle()
        # --- BOTÃO DE DELTA ---
        self.btn_delta = ctk.CTkButton(self, text="⏳ Analisar Mudanças por Período", command=self.abrir_delta_view, fg_color="#5A5A5A", hover_color="#404040")
        self.btn_delta.grid(row=4, column=0, padx=20, pady=(5, 10), sticky="w")
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=5, column=0, padx=20, pady=(10, 5), sticky="ew")
        self.progress_bar.set(0)
        self.btn_executar = ctk.CTkButton(self, text="Iniciar Atualização", command=self.iniciar_atualizacao, height=40, fg_color="green", hover_color="darkgreen")
        self.btn_executar.grid(row=6, column=0, padx=20, pady=20, sticky="ew")
        # --- TEXTBOX LOG (Agora na linha 7, que preenche a tela toda) ---
        self.textbox_log = ctk.CTkTextbox(self)
        self.textbox_log.grid(row=7, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log("Sistema pronto. Selecione os arquivos.")
    def log(self, mensagem):
        self.textbox_log.insert("end", mensagem + "\n")
        self.textbox_log.see("end")
    def criar_componentes_aconex(self):
        self.frame_aconex.grid_columnconfigure(0, minsize=220)
        lbl = ctk.CTkLabel(self.frame_aconex, text="1. Base de Dados Aconex (Histórico)", font=ctk.CTkFont(weight="bold"))
        lbl.grid(row=0, column=0, padx=10, pady=10, sticky="w", columnspan=2)
        btn = ctk.CTkButton(self.frame_aconex, text="Selecionar Arquivo", command=self.selecionar_aconex, width=150)
        btn.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        self.lbl_path_aconex = ctk.CTkLabel(self.frame_aconex, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_path_aconex.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="w")
        lbl_sheet = ctk.CTkLabel(self.frame_aconex, text="Aba (Sheet):")
        lbl_sheet.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")
        self.opt_sheet_aconex = ctk.CTkOptionMenu(self.frame_aconex, variable=self.sheet_aconex, values=["Selecione o arquivo primeiro"])
        self.opt_sheet_aconex.grid(row=2, column=1, padx=10, pady=(0, 10), sticky="w")
    def criar_componentes_mapping(self):
        self.frame_mapping.grid_columnconfigure(0, minsize=220)
        lbl = ctk.CTkLabel(self.frame_mapping, text="2. Planilha de Mapeamento", font=ctk.CTkFont(weight="bold"))
        lbl.grid(row=0, column=0, padx=10, pady=10, sticky="w", columnspan=2)
        btn = ctk.CTkButton(self.frame_mapping, text="Selecionar Arquivo", command=self.selecionar_mapping, width=150)
        btn.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        self.lbl_path_mapping = ctk.CTkLabel(self.frame_mapping, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_path_mapping.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="w")
        lbl_sheet = ctk.CTkLabel(self.frame_mapping, text="Aba (Sheet):")
        lbl_sheet.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")
        self.opt_sheet_mapping = ctk.CTkOptionMenu(self.frame_mapping, variable=self.sheet_mapping, values=["Selecione o arquivo primeiro"])
        self.opt_sheet_mapping.grid(row=2, column=1, padx=10, pady=(0, 10), sticky="w")
    def selecionar_aconex(self):
        path = self.excel_handler.selecionar_arquivo("aconex")
        if path:
            self.path_aconex = path
            self.lbl_path_aconex.configure(text=os.path.basename(path), text_color="white")
            self.log(f"Carregando Aconex: {path}")
            abas = self.excel_handler.listar_abas(path)
            self.opt_sheet_aconex.configure(values=abas)
            if "Documentos" in abas: self.sheet_aconex.set("Documentos")
            elif abas: self.sheet_aconex.set(abas[0])
    def selecionar_mapping(self):
        path = self.excel_handler.selecionar_arquivo("mapping")
        if path:
            self.path_mapping = path
            self.lbl_path_mapping.configure(text=os.path.basename(path), text_color="white")
            self.log(f"Carregando Mapeamento: {path}")
            abas = self.excel_handler.listar_abas(path)
            self.opt_sheet_mapping.configure(values=abas)
            if abas: self.sheet_mapping.set(abas[0])
    def criar_componentes_controle(self):
        self.frame_controle.grid_columnconfigure(0, minsize=220)
        lbl = ctk.CTkLabel(self.frame_controle, text="3. Controle de Documentos (Opcional - Atualiza Data prevista de emissão)", font=ctk.CTkFont(weight="bold"))
        lbl.grid(row=0, column=0, padx=10, pady=5, sticky="w", columnspan=2)
        btn = ctk.CTkButton(self.frame_controle, text="Selecionar Arquivo", command=self.selecionar_controle, width=150)
        btn.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="w")
        self.lbl_path_controle = ctk.CTkLabel(self.frame_controle, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_path_controle.grid(row=1, column=1, padx=10, pady=(0, 5), sticky="w")
        lbl_sheet = ctk.CTkLabel(self.frame_controle, text="Aba (Sheet):")
        lbl_sheet.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="w")
        self.opt_sheet_controle = ctk.CTkOptionMenu(self.frame_controle, variable=self.sheet_controle, values=["Selecione o arquivo primeiro"])
        self.opt_sheet_controle.grid(row=2, column=1, padx=10, pady=(0, 5), sticky="w")
    def selecionar_controle(self):
        path = self.excel_handler.selecionar_arquivo("controle_docs")
        if path:
            self.path_controle = path
            self.lbl_path_controle.configure(text=os.path.basename(path), text_color="white")
            self.log(f"Carregando Controle: {path}")
            abas = self.excel_handler.listar_abas(path)
            self.opt_sheet_controle.configure(values=abas)
            if abas: self.sheet_controle.set(abas[0])
    # --- NOVO MÉTODO PARA ABRIR A JANELA DE DELTA ---
    def abrir_delta_view(self):
        # 1. Validações Básicas
        if not self.path_mapping:
            messagebox.showwarning("Aviso", "Selecione a Planilha de Mapeamento primeiro.")
            return
        if not self.path_aconex:
             messagebox.showinfo("Aviso", "Selecione o Histórico Aconex para prosseguir.")
             return
        try:
            wb = openpyxl.load_workbook(self.path_mapping, read_only=True)
            sheet_name = self.sheet_mapping.get() if self.sheet_mapping.get() else wb.sheetnames[0]
            ws = wb[sheet_name]

            # Reutiliza sua função 'find_headers' para achar a linha certa
            headers_encontrados = self.find_headers(ws)
            wb.close()

            if not headers_encontrados:
                messagebox.showerror("Erro", "Não foi possível encontrar a linha de cabeçalho (N° ITAIPU) na planilha.")
                return
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao ler arquivo de mapeamento: {e}")
            return
        # 3. Configura os nomes EXATOS das colunas

        cols_config = {
            'header_row': self.row_header, # Ex: Linha 5
            'doc': self.colunas_lista_planos_execução['coluna_código_itaipu'], # "N° ITAIPU"
            'grupo': self.colunas_lista_planos_execução['coluna_grupo'],       # "GRUPO"
            'sistema': self.colunas_lista_planos_execução['coluna_sistema'],   # "SISTEMA"
            'nivel': self.colunas_lista_planos_execução['coluna_nível'],       # "NÍVEL"
            'titulo': self.colunas_lista_planos_execução['coluna_descrição'],  # "DESCRIÇÃO DO DOCUMENTO"
            'predecessor': self.colunas_lista_planos_execução['coluna_predecessor'] # <--- NOVO
        }
        # 4. Abre a Janela passando a configuração correta
        DeltaView(
            self, 
            self.data_manager, 
            self.path_mapping, 
            sheet_name, 
            self.path_aconex, 
            self.sheet_aconex.get(),
            cols_config # <--- O segredo vai aqui
        )
    def find_headers(self, ws):
        headers = {}
        for r in range(1, 6):
            found_any = False
            for cell in ws[r]:
                if cell.value:
                    headers[str(cell.value).strip()] = cell.column
                    found_any = True
            if found_any and 'N° ITAIPU' in headers:
                self.row_header = r
                return headers
        return {}
    def get_val(self, ws, headers, col_key, row):
        col_name = self.colunas_lista_planos_execução.get(col_key)
        col_idx = headers.get(col_name)
        if col_idx:
            val = ws.cell(row=row, column=col_idx).value
            return str(val).strip() if val is not None else ""
        return ""
    def set_val(self, ws, headers, col_key, row, valor):
        col_name = self.colunas_lista_planos_execução.get(col_key)
        col_idx = headers.get(col_name)
        if col_idx:
            ws.cell(row=row, column=col_idx).value = valor
    def iniciar_atualizacao(self):
        if not self.path_aconex or not self.path_mapping:
            messagebox.showwarning("Aviso", "Selecione os dois arquivos.")
            return
        self.btn_executar.configure(state="disabled")
        self.log("--- INICIANDO ATUALIZAÇÃO ---")

        # 1. Carregar Aconex
        self.log("Lendo base de dados Aconex (pode demorar um pouco)...")
        self.update_idletasks()
        sucesso, msg = self.data_manager.carregar_aconex(self.path_aconex, self.sheet_aconex.get())
        if not sucesso:
            self.log(f"ERRO: {msg}")
            self.btn_executar.configure(state="normal")
            return
        self.log(msg)
        # =========================================================================
        # 1.5. [NOVO] LER CONTROLE DE DOCUMENTOS (Opcional - Data Etapa 1)
        # =========================================================================
        dicionario_datas_previstas = {}
        if self.path_controle:
            self.log("Lendo Controle de Documentos (Datas Previstas)...")
            self.update_idletasks()
            try:
                # header=3 pula as 3 primeiras linhas (começa a ler os dados na linha 4)
                df_controle = pd.read_excel(self.path_controle, sheet_name=self.sheet_controle.get(), header=3)
                col_data = 'DATA PREVISTA DE EMISSÃO ACONEX'

                if col_data in df_controle.columns:
                    df_controle[col_data] = pd.to_datetime(df_controle[col_data], errors='coerce')

                    # Criação do Dicionário "The Flash" (Sem chamar a API/Aconex)
                    for _, row_ctrl in df_controle.iterrows():
                        cod_itaipu_ctrl = str(row_ctrl.get('CODIFICAÇÃO ITAIPÚ (ACONEX)', '')).strip()
                        cod_cmi_ctrl = str(row_ctrl.get('NÚMERO INTERNO', '')).strip()
                        data_prev = row_ctrl.get(col_data, pd.NaT)

                        if pd.notna(data_prev):
                            # Salva a data para ambos os códigos (se existirem) como chaves independentes
                            if cod_itaipu_ctrl:
                                dicionario_datas_previstas[cod_itaipu_ctrl] = data_prev.date()
                            if cod_cmi_ctrl:
                                dicionario_datas_previstas[cod_cmi_ctrl] = data_prev.date()

                    self.log(f"Sucesso: {len(dicionario_datas_previstas)} chaves de data rápidas criadas na memória.")
                else:
                    self.log(f"Aviso: Coluna '{col_data}' não encontrada. A atualização de datas será pulada.")
            except Exception as e:
                self.log(f"Aviso ao ler Controle de Documentos: {e}. O processo continuará normalmente.")
        # =========================================================================
        # 2. Abrir Mapeamento
        self.log("Abrindo planilha de Mapeamento...")
        try:
            wb_mapping = openpyxl.load_workbook(self.path_mapping)
            ws = wb_mapping[self.sheet_mapping.get()]
        except Exception as e:
            self.log(f"Erro ao abrir mapeamento: {e}")
            self.btn_executar.configure(state="normal")
            return
        # 3. Mapear Cabeçalhos
        headers_idx = self.find_headers(ws)
        if not headers_idx:
            self.log("ERRO: Coluna 'N° ITAIPU' não encontrada nas primeiras 5 linhas.")
            self.btn_executar.configure(state="normal")
            return

        max_row = ws.max_row
        start_row = self.row_header + 2 

        self.log(f"Processando linhas {start_row} a {max_row}...")
        self.progress_bar.set(0)
        # --- LOOP PRINCIPAL ---
        for row in range(start_row, max_row + 1):
            progresso = (row - start_row) / (max_row - start_row + 1)
            if row % 10 == 0:
                self.progress_bar.set(progresso)
                self.update_idletasks()
            c_itaipu = self.get_val(ws, headers_idx, 'coluna_código_itaipu', row)
            c_cmi = self.get_val(ws, headers_idx, 'coluna_código_cmi', row)
            if not c_itaipu and not c_cmi: continue
            df_tracking = self.data_manager.localiza_doc_historico(c_itaipu, c_cmi)

            # =========================================================================
            # [NOVO] INJEÇÃO DA DATA PREVISTA ETAPA 1 E LIMPEZA DE ZUMBIS
            # =========================================================================
            col_data_prev = headers_idx.get(self.colunas_lista_planos_execução['coluna_data_previsão_emissão_etapa_1'])
            if col_data_prev:
                celula_atual = ws.cell(row=row, column=col_data_prev)
                valor_atual = celula_atual.value

                # MATADOR DE ZUMBIS: Se for string vazia, converte para None (Null real)
                if valor_atual is not None and str(valor_atual).strip() == "":
                    celula_atual.value = None
                    valor_atual = None

                # FAST PATH / SLOW PATH: Injeção Segura e Desempate
                if self.path_controle and not df_tracking.empty and valor_atual is None:
                    # 1. Lista todos os códigos que esse documento já teve na vida
                    codigos_historicos = self.data_manager.obter_codigos_historicos(df_tracking)

                    datas_encontradas = {}
                    # 2. Pergunta ao dicionário rápido se ele tem data para algum desses códigos
                    for cod in codigos_historicos:
                        if cod in dicionario_datas_previstas:
                            datas_encontradas[cod] = dicionario_datas_previstas[cod]

                    datas_unicas = set(datas_encontradas.values())

                    # 3. Análise dos Cenários
                    if len(datas_unicas) == 1:
                        # CENÁRIO A (Fast Path): Só achou uma data. É ela mesma!
                        celula_atual.value = list(datas_unicas)[0]

                    elif len(datas_unicas) > 1:
                        # CENÁRIO C (Slow Path/Fallback): Conflito! Códigos do mesmo doc com datas diferentes no Excel do Controle.
                        # Regra de Desempate de Ouro: Confiar na data que está atrelada ao código mais recente (o que está no Mapeamento agora)
                        if c_itaipu in datas_encontradas:
                            celula_atual.value = datas_encontradas[c_itaipu]
                        elif c_cmi in datas_encontradas:
                            celula_atual.value = datas_encontradas[c_cmi]
                        else:
                            # Se os códigos do Mapeamento não baterem (muito raro), pega a data mais nova para segurança
                            celula_atual.value = max(datas_unicas)

                # Formata visualmente
                celula_atual.number_format = 'dd/mm/yyyy'
            # =========================================================================
            if df_tracking.empty:
                # 1. Limpa dados visuais (Mata as células zumbis com None)
                self.set_val(ws, headers_idx, 'coluna_revisão', row, None)
                self.set_val(ws, headers_idx, 'coluna_data_último_status', row, None)
                self.set_val(ws, headers_idx, 'coluna_status_emissão', row, None)

                # 2. Crava os Status Calculados
                self.set_val(ws, headers_idx, 'coluna_status_real',     row, "NÃO EMITIDO")
                self.set_val(ws, headers_idx, 'coluna_status_consolidado',     row, "NÃO EMITIDO")

                self.set_val(ws, headers_idx, 'coluna_emitido_não_emitido', row, "NÃO EMITIDO")
                # Se não tem histórico (NÃO EMITIDO), está parado com a CMI:
                self.set_val(ws, headers_idx, 'coluna_com_itaipu', row, "CMI")
                # =========================================================================
                # [CORREÇÃO] INJEÇÃO DOS KPIS ANTES DO 'CONTINUE' (PARA OS NÃO EMITIDOS)
                # =========================================================================
                data_prev_etapa1 = self.get_val(ws, headers_idx, 'coluna_data_previsão_emissão_etapa_1', row)

                kpis = self.data_manager.analisar_kpis_documento(
                    df_tracking=df_tracking, # Vai vazio, a função sabe lidar
                    status_real="NÃO EMITIDO",
                    revisao_atual="",
                    data_prevista=data_prev_etapa1
                )

                self.set_val(ws, headers_idx, 'coluna_dias_status', row, kpis['dias_status'])
                self.set_val(ws, headers_idx, 'coluna_situacao_prazo', row, kpis['situacao_prazo'])
                self.set_val(ws, headers_idx, 'coluna_dias_atraso', row, kpis['dias_atraso'])
                self.set_val(ws, headers_idx, 'coluna_total_ciclos', row, kpis['total_ciclos'])
                self.set_val(ws, headers_idx, 'coluna_ciclos_aprovar', row, kpis['ciclos_aprovar'])
                self.set_val(ws, headers_idx, 'coluna_downgrade', row, kpis['downgrade'])

                # =========================================================================
                # INJEÇÃO DOS ATRASOS ACUMULADOS (NÃO EMITIDOS)
                # =========================================================================
                acumulados = self.data_manager.calcular_atrasos_acumulados(
                    df_tracking=df_tracking,
                    status_real="NÃO EMITIDO",
                    data_prevista=data_prev_etapa1
                )
                self.set_val(ws, headers_idx, 'coluna_atraso_acum_ib', row, acumulados['atraso_acumulado_itaipu'])
                self.set_val(ws, headers_idx, 'coluna_atraso_acum_cmi', row, acumulados['atraso_acumulado_cmi'])
                # =========================================================================
                continue
            # =========================================================================
            # [INÍCIO DO BLOCO NOVO] - FILTRO DE ETAPAS (NÍVEL 1 e 2)
            # =========================================================================

            # 1. Lê o Nível e o Texto do Filtro da linha atual
            nivel_row = self.get_val(ws, headers_idx, 'coluna_nível', row)
            texto_filtro = self.get_val(ws, headers_idx, 'coluna_filtro_etapa', row)
            # 2. Verifica a condição: É Nível 1 ou 2? Tem algo escrito no filtro?
            if nivel_row in ['1', '2'] and texto_filtro:
                # 3. Aplica o filtro no histórico COMPLETO antes de qualquer coisa
                # Isso garante que revisões antigas (Etapa 1) sumam da memória 
                # se estamos procurando "Etapa 1 e 2".
                df_tracking = self.data_manager.filtrar_historico_por_titulo(df_tracking, texto_filtro)

                # Se o filtro for muito restrito e não sobrar nada (ex: erro de digitação no Excel),
                # df_tracking ficará vazio e o código vai tratar como "Não encontrado" nas linhas abaixo,
                # o que é o comportamento seguro correto.
            # C.1 - Dados Estáticos (Current=True)
            linha_estatica = pd.Series()
            docs_current = df_tracking[df_tracking["Current"].str.lower() == "true"]
            if not docs_current.empty:
                linha_estatica = docs_current.iloc[0]

            if not linha_estatica.empty:
                self.set_val(ws, headers_idx, 'coluna_código_itaipu', row, linha_estatica.get('No. do Documento'))
                self.set_val(ws, headers_idx, 'coluna_código_cmi', row, linha_estatica.get('Controle do Emissor'))
                self.set_val(ws, headers_idx, 'coluna_descrição', row, linha_estatica.get('Título'))
            # C.2 - Dados Dinâmicos e Preparação para Status Real
            linha_dinamica = None

            df_para_calculo = df_tracking.copy() 
            docs_current = df_tracking[df_tracking["Current"].astype(str).str.lower() == "true"]
            cand_current = docs_current.iloc[0] if not docs_current.empty else None
            if cand_current is not None:
                status_rev = str(cand_current.get("Status da Revisão", "")).lower()
                revisao_atual = str(cand_current.get("Revisão", "")).strip()
                if "terminated" not in status_rev:
                    linha_dinamica = cand_current
                else:
                    rev_norm = self.data_manager.normalizar_revisao(revisao_atual)
                    rev_limite = self.data_manager.normalizar_revisao("0A")
                    if rev_norm <= rev_limite: 
                        linha_dinamica = None 
                        df_para_calculo = pd.DataFrame() 
                    else:
                        df_historico_valido = df_tracking[df_tracking["Revisão"].str.strip() != revisao_atual].copy()
                        df_para_calculo = df_historico_valido 

                        if not df_historico_valido.empty:
                            try:
                                df_historico_valido['Versão_Int'] = pd.to_numeric(df_historico_valido['Versão'], errors='coerce')
                                linha_dinamica = df_historico_valido.sort_values(by=['Versão_Int', 'Versão'], ascending=False).iloc[0]
                            except:
                                linha_dinamica = df_historico_valido.sort_values(by='Versão', ascending=False).iloc[0]
                        else:
                            linha_dinamica = None
            elif not df_tracking.empty:
                 try:
                    aux = df_tracking.copy()
                    aux['Versão_Int'] = pd.to_numeric(aux['Versão'], errors='coerce')
                    linha_dinamica = aux.sort_values(by=['Versão_Int', 'Versão'], ascending=False).iloc[0]
                 except:
                    linha_dinamica = df_tracking.iloc[0]
            # --- Aplicação dos Dados Visuais ---
            revisao_final = ""
            status_final = ""

            if linha_dinamica is not None:
                self.set_val(ws, headers_idx, 'coluna_data_último_status', row, linha_dinamica.get('Data de Alteração'))
                self.set_val(ws, headers_idx, 'coluna_revisão', row, linha_dinamica.get('Revisão'))
                self.set_val(ws, headers_idx, 'coluna_status_emissão', row, linha_dinamica.get('Status'))
                revisao_final = str(linha_dinamica.get('Revisão', '')).strip()
                status_final = str(linha_dinamica.get('Status', '')).strip()
            else:
                # Mata as células zumbis com None
                self.set_val(ws, headers_idx, 'coluna_data_último_status', row, None)
                self.set_val(ws, headers_idx, 'coluna_revisão', row, None)
                self.set_val(ws, headers_idx, 'coluna_status_emissão', row, None)
            if df_para_calculo.empty:
                status_real = "NÃO EMITIDO"
            else:
                status_real = self.data_manager.calcular_status_real(df_para_calculo, revisao_final)

            self.set_val(ws, headers_idx, 'coluna_status_real', row, status_real)
            emitido_status = self.data_manager.calcular_emitido_nao_emitido(status_real)
            self.set_val(ws, headers_idx, 'coluna_emitido_não_emitido', row, emitido_status)
            status_consolidado = self.data_manager.calcula_status_consolidado(status_real, status_final, emitido_status)
            self.set_val(ws, headers_idx, 'coluna_status_consolidado', row, status_consolidado)
            com_quem = self.data_manager.calcula_parado_com(status_final)
            self.set_val(ws, headers_idx, 'coluna_com_itaipu', row, com_quem)
            # =========================================================================
            # [NOVO] INJEÇÃO DOS KPIS ANALÍTICOS (POWER BI)
            # =========================================================================
            # Pega a data prevista que foi atualizada/injetada lá em cima no código
            data_prev_etapa1 = self.get_val(ws, headers_idx, 'coluna_data_previsão_emissão_etapa_1', row)

            kpis = self.data_manager.analisar_kpis_documento(
                df_tracking=df_tracking,
                status_real=status_real,
                revisao_atual=revisao_final,
                data_prevista=data_prev_etapa1
            )

            # Carimba os resultados no Excel
            self.set_val(ws, headers_idx, 'coluna_dias_status', row, kpis['dias_status'])
            self.set_val(ws, headers_idx, 'coluna_situacao_prazo', row, kpis['situacao_prazo'])
            self.set_val(ws, headers_idx, 'coluna_dias_atraso', row, kpis['dias_atraso'])
            self.set_val(ws, headers_idx, 'coluna_total_ciclos', row, kpis['total_ciclos'])
            self.set_val(ws, headers_idx, 'coluna_ciclos_aprovar', row, kpis['ciclos_aprovar'])
            self.set_val(ws, headers_idx, 'coluna_downgrade', row, kpis['downgrade'])

            # =========================================================================
            # INJEÇÃO DOS ATRASOS ACUMULADOS (FLUXO NORMAL)
            # =========================================================================
            acumulados = self.data_manager.calcular_atrasos_acumulados(
                df_tracking=df_tracking,
                status_real=status_real,
                data_prevista=data_prev_etapa1
            )
            self.set_val(ws, headers_idx, 'coluna_atraso_acum_ib', row, acumulados['atraso_acumulado_itaipu'])
            self.set_val(ws, headers_idx, 'coluna_atraso_acum_cmi', row, acumulados['atraso_acumulado_cmi'])
            # =========================================================================
        self.log("Dados atualizados. Calculando Predecessores...")
        # --- LOOP HIERARQUIA ---
        for row in range(start_row, max_row + 1):
            nivel_atual = self.get_val(ws, headers_idx, 'coluna_nível', row)
            cod_itaipu = self.get_val(ws, headers_idx, 'coluna_código_itaipu', row)

            plano_exec = ""
            predecessor = ""

            if nivel_atual == '1':
                plano_exec = cod_itaipu
                predecessor = cod_itaipu
            else:
                linha_aux = row - 1
                while linha_aux >= start_row:
                    nivel_aux = self.get_val(ws, headers_idx, 'coluna_nível', linha_aux)
                    cod_aux = self.get_val(ws, headers_idx, 'coluna_código_itaipu', linha_aux)

                    if not nivel_aux.isdigit() or not nivel_atual.isdigit():
                        linha_aux -= 1
                        continue
                    if predecessor == '' and int(nivel_aux) < int(nivel_atual):
                        predecessor = cod_aux
                    if plano_exec == '' and nivel_aux == '1':
                        plano_exec = cod_aux
                    if plano_exec and predecessor:
                        break
                    linha_aux -= 1

            self.set_val(ws, headers_idx, 'coluna_plano_de_execução', row, plano_exec)
            self.set_val(ws, headers_idx, 'coluna_predecessor', row, predecessor)
        # =========================================================================
        # [NOVO] LOOP 2.5 - O PENTE FINO DAS PLANILHAS (Regra Estrita de Nível 4)
        # =========================================================================
        self.log("Aplicando regras estritas de aprovação para Planilhas...")
        self.update_idletasks()

        planilhas_vip = set()

        # 1. Caça aos Pais: Encontrar Planilhas de Nível 3
        for r in range(start_row, max_row + 1):
            nivel = self.get_val(ws, headers_idx, 'coluna_nível', r)
            if nivel == '3':
                titulo = str(self.get_val(ws, headers_idx, 'coluna_descrição', r)).upper()
                if 'PLANILHA' in titulo:
                    cod_itaipu = self.get_val(ws, headers_idx, 'coluna_código_itaipu', r)
                    if cod_itaipu:
                        planilhas_vip.add(cod_itaipu)

        # 2. Varredura dos Filhos: Rebaixar o Status Consolidado do Nível 4
        if planilhas_vip:
            for r in range(start_row, max_row + 1):
                nivel = self.get_val(ws, headers_idx, 'coluna_nível', r)
                predecessor = self.get_val(ws, headers_idx, 'coluna_predecessor', r)

                if nivel == '4' and predecessor in planilhas_vip:
                    status_real_atual = self.get_val(ws, headers_idx, 'coluna_status_real', r)
                    status_cons_atual = self.get_val(ws, headers_idx, 'coluna_status_consolidado', r)

                    novo_cons = self.data_manager.calcula_status_consolidado_estrito(status_real_atual, status_cons_atual)
                    self.set_val(ws, headers_idx, 'coluna_status_consolidado', r, novo_cons)
        self.log("Calculando Resumo de Quantidades...")

        # --- LOOP RESUMO ---
        col_pred_idx = headers_idx.get(self.colunas_lista_planos_execução['coluna_predecessor'])
        col_stat_idx = headers_idx.get(self.colunas_lista_planos_execução['coluna_status_consolidado'])
        col_cod_idx = headers_idx.get(self.colunas_lista_planos_execução['coluna_código_itaipu'])
        dados_resumo = []
        for r in range(start_row, max_row + 1):
            dados_resumo.append({
                'row': r,
                'codigo': str(ws.cell(r, col_cod_idx).value).strip() if ws.cell(r, col_cod_idx).value else "",
                'predecessor': str(ws.cell(r, col_pred_idx).value).strip() if ws.cell(r, col_pred_idx).value else "",
                'status_cons': str(ws.cell(r, col_stat_idx).value).strip().upper() if ws.cell(r, col_stat_idx).value else "",
                'nivel': self.get_val(ws, headers_idx, 'coluna_nível', r)
            })
        for item in dados_resumo:
            row = item['row']
            nivel = item['nivel']
            status_cons = item['status_cons']

            self.set_val(ws, headers_idx, 'coluna_resumo_quantidades', row, "")
            if nivel in ['1', '2'] and status_cons == 'APROVADO':
                self.set_val(ws, headers_idx, 'coluna_resumo_quantidades', row, "Plano Aprovado")
                continue
            # NOTA: O 'elif' de bloqueio do Nível 3 foi removido para que o resumo das planilhas seja sempre calculado.
            if nivel in ['1', '2', '3']:
                cod_pai = item['codigo']
                if not cod_pai: continue
                qtd = 0; aprov = 0; aprov_inter = 0; proc = 0; nao_aprov = 0; nao_emit = 0
                for filho in dados_resumo:
                    if filho['predecessor'] == cod_pai and filho['row'] != row:
                         if not filho['codigo']: continue
                         qtd += 1
                         s = filho['status_cons']
                         if s == 'APROVADO': aprov += 1
                         elif s == 'APROVAÇÃO INTERMEDIÁRIA': aprov_inter += 1
                         elif s == 'NÃO APROVADO': nao_aprov += 1
                         elif s == 'NÃO EMITIDO': nao_emit += 1
                         elif s == 'EM PROCESSO': proc += 1

                if qtd > 0:
                    if nivel == '3':
                        # Apenas Nível 3 mostra a quebra de Aprovação Intermediária
                        txt = f'Total: {qtd}\nAprovados: {aprov}\nAprovação Intermediária: {aprov_inter}\nEm Processo: {proc}\nNão Aprovados: {nao_aprov}\nNão Emitidos: {nao_emit}'
                    else:
                        # Níveis 1 e 2 mantêm a visualização original limpa
                        txt = f'Total: {qtd}\nAprovados: {aprov}\nEm Processo: {proc}\nNão Aprovados: {nao_aprov}\nNão Emitidos: {nao_emit}'

                    self.set_val(ws, headers_idx, 'coluna_resumo_quantidades', row, txt)
        self.log("Salvando arquivo...")
        salvo = self.excel_handler.salvar_com_retry(wb_mapping, self.path_mapping, self.winfo_toplevel())

        self.progress_bar.set(1)
        if salvo:
            self.log("SUCESSO: Mapeamento atualizado.")
            messagebox.showinfo("Sucesso", "Atualização concluída!")
        else:
            self.log("CANCELADO: Não foi possível salvar.")

        self.btn_executar.configure(state="normal")
class DeltaView(ctk.CTkToplevel):
    def __init__(self, parent, data_manager, path_map, sheet_map, path_hist, sheet_hist, cols_config):
        super().__init__(parent)
        self.title("Análise de Mudanças (Delta)")
        # Aumentamos a largura para acomodar perfeitamente as 7 colunas da Visão Bruta
        self.geometry("1150x600")

        self.data_manager = data_manager
        self.path_map = path_map
        self.sheet_map = sheet_map
        self.path_hist = path_hist
        self.sheet_hist = sheet_hist
        self.cols_config = cols_config
        self.setup_ui()
        self.configurar_estilo_treeview()
        self.lift() # Traz para frente visualmente
        self.focus_force() # Força o foco do teclado/mouse para ela
        self.grab_set() # (Opcional) Impede clicar na janela de trás enquanto essa estiver aberta (Modal)

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        # --- Topo: Filtros ---
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(self.frame_top, text="Período de Análise:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
        self.entry_ini = ctk.CTkEntry(self.frame_top, placeholder_text="DD/MM/AAAA", width=100)
        self.entry_ini.pack(side="left", padx=5)
        ctk.CTkLabel(self.frame_top, text="até").pack(side="left", padx=5)
        self.entry_fim = ctk.CTkEntry(self.frame_top, placeholder_text="DD/MM/AAAA", width=100)
        self.entry_fim.pack(side="left", padx=5)

        ctk.CTkLabel(self.frame_top, text="Agrupar por:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(15, 5))
        self.var_agrupador = ctk.StringVar(value="Grupo") # Valor Padrão
        self.opt_agrupador = ctk.CTkOptionMenu(self.frame_top, variable=self.var_agrupador, values=["Grupo", "Sistema"], width=100)
        self.opt_agrupador.pack(side="left", padx=5)

        # --- NOVO: Seletor de Visão (Efetiva x Bruta) ---
        ctk.CTkLabel(self.frame_top, text="Visão:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(15, 5))
        self.var_tipo_visao = ctk.StringVar(value="Efetiva")
        # Se o usuário mudar a visão, limpamos a árvore forçando ele a clicar em Verificar novamente (pois a base filtrada muda)
        self.seg_visao = ctk.CTkSegmentedButton(self.frame_top, variable=self.var_tipo_visao, values=["Efetiva", "Bruta"], command=lambda _: self.tree.delete(*self.tree.get_children()))
        self.seg_visao.pack(side="left", padx=5)

        self.btn_filtrar = ctk.CTkButton(self.frame_top, text="Verificar Mudanças", command=self.executar_analise, fg_color="#E59400", hover_color="#B87700")
        self.btn_filtrar.pack(side="left", padx=20)
        # --- NOVO: Checkbox de Filtro ---
        self.var_ignorar_aprovados = ctk.BooleanVar(value=False)
        self.chk_ignorar = ctk.CTkCheckBox(
            self.frame_top, 
            text="Ocultar se já estava Aprovado", 
            variable=self.var_ignorar_aprovados,
            command=lambda: self.povoar_arvore(self.dados_cache) if hasattr(self, 'dados_cache') else None
        )
        self.chk_ignorar.pack(side="left", padx=10)
        # --- Centro: Treeview ---
        self.frame_tree = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.frame_tree.grid_columnconfigure(0, weight=1)
        self.frame_tree.grid_rowconfigure(0, weight=1)
        # DEFINIÇÃO DAS COLUNAS MÁXIMAS (Todas as possíveis)
        cols = ("info_antes", "raw_antes", "real_antes", "seta", "info_depois", "raw_depois", "real_depois")
        self.tree = ttk.Treeview(self.frame_tree, columns=cols, selectmode="browse")

        # Cabeçalhos Padrão (Serão renomeados dinamicamente)
        self.tree.heading("#0", text="Grupo / Nível / Documento", anchor="w")
        self.tree.heading("info_antes", text="Rev/Data (Antes)", anchor="w")
        self.tree.heading("raw_antes", text="Aconex (Antes)", anchor="w")
        self.tree.heading("real_antes", text="Efetivo (Antes)", anchor="w")
        self.tree.heading("seta", text=" ", anchor="center")
        self.tree.heading("info_depois", text="Rev/Data (Depois)", anchor="w")
        self.tree.heading("raw_depois", text="Aconex (Depois)", anchor="w")
        self.tree.heading("real_depois", text="Efetivo (Depois)", anchor="w")

        # Larguras
        self.tree.column("#0", width=300, minwidth=200) # Ajustado para caber o resto
        self.tree.column("info_antes", width=115, minwidth=100)
        self.tree.column("raw_antes", width=115, minwidth=100)
        self.tree.column("real_antes", width=115, minwidth=100)
        self.tree.column("seta", width=30, minwidth=30, anchor="center")
        self.tree.column("info_depois", width=115, minwidth=100)
        self.tree.column("raw_depois", width=115, minwidth=100)
        self.tree.column("real_depois", width=115, minwidth=100)
        # Scrollbar
        vsb = ttk.Scrollbar(self.frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        # EVENTO DE CLIQUE DUPLO
        self.tree.bind("<Double-1>", self.on_double_click)
        # --- Rodapé ---
        self.frame_footer = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_footer.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

        self.lbl_status = ctk.CTkLabel(self.frame_footer, text="Aguardando filtro...", text_color="gray")
        self.lbl_status.pack(side="left")

        self.btn_exportar = ctk.CTkButton(self.frame_footer, text="📊 Exportar Excel", command=self.exportar_excel, fg_color="#1F538D", state="disabled")
        self.btn_exportar.pack(side="right")
    def configurar_estilo_treeview(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", background="#3a3a3a", foreground="white", font=("Arial", 10, "bold"))
        style.map("Treeview", background=[('selected', '#1f538d')])
    def on_double_click(self, event):
        # Pega o item clicado
        item_id = self.tree.identify_row(event.y)
        if not item_id: return
        item_text = self.tree.item(item_id, "text")

        # Verifica se é um documento (tem ícone de página)
        if "📄" in item_text:
            # Extrai apenas o código (remove o ícone e espaços)
            # Ex: "📄 DOC-123" -> "DOC-123"
            codigo = item_text.replace("📄", "").strip()

            # Copia para clipboard
            self.clipboard_clear()
            self.clipboard_append(codigo)
            self.update() # Necessário no tkinter para efetivar a clipboard

            messagebox.showinfo("Copiado", f"Código copiado:\n{codigo}")
    def executar_analise(self):
        dt_ini = self.entry_ini.get()
        dt_fim = self.entry_fim.get()
        if not dt_ini or not dt_fim:
            messagebox.showwarning("Aviso", "Preencha as duas datas.")
            return
        self.btn_filtrar.configure(state="disabled", text="Processando...")
        self.lbl_status.configure(text="Cruzando dados... Aguarde.")
        self.update()
        for item in self.tree.get_children():
            self.tree.delete(item)
        agrupador_escolhido = self.var_agrupador.get() # "Grupo" ou "Sistema"
        visao_escolhida = self.var_tipo_visao.get() # "Efetiva" ou "Bruta"

        sucesso, dados_arvore, total = self.data_manager.calcular_mudancas_periodo(
            self.path_map, self.sheet_map, 
            self.path_hist, self.sheet_hist, 
            dt_ini, dt_fim,
            self.cols_config,
            agrupador_escolhido,
            tipo_visao=visao_escolhida
        )
        if sucesso:
            # --- NOVO: Salva no cache para poder filtrar depois sem recalcular ---
            self.dados_cache = dados_arvore 
            self.povoar_arvore(dados_arvore) # Chama o povoar normal

            # Nota: O texto do total pode ficar levemente impreciso se filtrar, 
            # mas mostra o total processado.
            self.lbl_status.configure(text=f"Análise concluída. Base bruta: {total} alterações.")
            self.btn_exportar.configure(state="normal") # Libera o botão de exportação
        else:
            messagebox.showerror("Erro", f"Falha: {dados_arvore}")
            self.lbl_status.configure(text="Erro.")
            self.btn_exportar.configure(state="disabled")
        self.btn_filtrar.configure(state="normal", text="Verificar Mudanças")
    def povoar_arvore(self, dados):
        # Limpa a árvore atual antes de repovoar (CASO ESTEJA REFILTRANDO)
        for item in self.tree.get_children():
            self.tree.delete(item)

        nome_agrupador = self.var_agrupador.get()
        visao_atual = self.var_tipo_visao.get()
        self.tree.heading("#0", text=f"{nome_agrupador} / Nível / Documento")
        # MUDANÇA DINÂMICA DE COLUNAS (OCULTA OU EXIBE) E CABEÇALHOS
        if visao_atual == "Efetiva":
            # Esconde as colunas de Rev/Data na visão efetiva
            self.tree.configure(displaycolumns=("raw_antes", "real_antes", "seta", "raw_depois", "real_depois"))
            self.tree.heading("raw_antes", text="Status Aconex (Antes)")
            self.tree.heading("real_antes", text="Status Efetivo (Antes)")
            self.tree.heading("raw_depois", text="Status Aconex (Depois)")
            self.tree.heading("real_depois", text="Status Efetivo (Depois)")
        else:
            # Exibe as 7 colunas completas na visão bruta
            self.tree.configure(displaycolumns=("info_antes", "raw_antes", "real_antes", "seta", "info_depois", "raw_depois", "real_depois"))
            self.tree.heading("info_antes", text="Rev e Data (Antes)")
            self.tree.heading("raw_antes", text="Status Aconex (Antes)")
            self.tree.heading("real_antes", text="Status Efetivo (Antes)")
            self.tree.heading("info_depois", text="Rev e Data (Depois)")
            self.tree.heading("raw_depois", text="Status Aconex (Depois)")
            self.tree.heading("real_depois", text="Status Efetivo (Depois)")
        ICON_GRUPO = "📂"
        ICON_NIVEL = "L"
        ICON_DOC = "📄"

        # Lista de status que consideramos "Já Resolvidos/Aprovados"
        STATUS_APROVADOS = ['Aprovado', 'Aprovado com Comentários', 'Para Assinatura']
        filtrar = self.var_ignorar_aprovados.get() # True ou False
        count_exibidos = 0
        for grupo in sorted(dados.keys()):
            # Precisamos filtrar a lista antes de criar o grupo visualmente
            # senão criamos grupos vazios

            # Dicionário temporário para guardar só o que passou no filtro
            grupo_filtrado = {}
            total_itens_grupo = 0
            for nivel, lista_docs in dados[grupo].items():
                docs_validos = []
                for doc in lista_docs:
                    # --- A LÓGICA DO FILTRO ---
                    status_antes = str(doc['real_antes']).strip()

                    if filtrar and status_antes in STATUS_APROVADOS:
                        continue # Pula este documento (não adiciona)

                    docs_validos.append(doc)

                if docs_validos:
                    grupo_filtrado[nivel] = docs_validos
                    total_itens_grupo += len(docs_validos)
            # Se depois do filtro sobrou algo no grupo, adiciona na árvore
            if total_itens_grupo > 0:
                id_grupo = self.tree.insert("", "end", text=f"{ICON_GRUPO} {grupo} ({total_itens_grupo})", open=True)

                for nivel in sorted(grupo_filtrado.keys()):
                    lista_docs = grupo_filtrado[nivel]
                    id_nivel = self.tree.insert(id_grupo, "end", text=f"{ICON_NIVEL} {nivel} ({len(lista_docs)})", open=True)

                    for doc in lista_docs:
                        count_exibidos += 1
                        texto_display = f"{ICON_DOC} {doc['doc']}"

                        # VALORES SEMPRE COMPLETOS (A interface esconde os irrelevantes automaticamente)
                        val_info_1 = f"Rev {doc.get('rev_antes', '-')} ({doc.get('data_antes', '-')})" if doc.get('rev_antes', '-') != "-" else "-"
                        val_raw_1 = doc['raw_antes']
                        val_real_1 = doc['real_antes']

                        val_info_2 = f"Rev {doc.get('rev_depois', '-')} ({doc.get('data_depois', '-')})" if doc.get('rev_depois', '-') != "-" else "-"
                        val_raw_2 = doc['raw_depois']
                        val_real_2 = doc['real_depois']
                        self.tree.insert(id_nivel, "end", 
                                         text=texto_display, 
                                         values=(
                                             val_info_1,
                                             val_raw_1, 
                                             val_real_1, 
                                             "➜", 
                                             val_info_2,
                                             val_raw_2, 
                                             val_real_2
                                         ))

        # Atualiza label se filtrou
        if filtrar:
            self.lbl_status.configure(text=f"Exibindo {count_exibidos} documentos (Filtro Ativo).")
    def exportar_excel(self):
        if not hasattr(self, 'dados_cache'): return

        from tkinter import filedialog
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        # 1. Formatação das Datas para o Título (DD/MM/AAAA -> DD.MM.YY)
        d1_raw = self.entry_ini.get().strip().replace("/", ".")
        d2_raw = self.entry_fim.get().strip().replace("/", ".")

        d1 = d1_raw[:6] + d1_raw[8:] if len(d1_raw) == 10 else d1_raw
        d2 = d2_raw[:6] + d2_raw[8:] if len(d2_raw) == 10 else d2_raw

        aba_atual = str(self.sheet_map).replace(" ", "_")
        sugestao_nome = f"{aba_atual}_{d1}_ate_{d2}.xlsx"

        # 2. Pergunta onde o usuário quer salvar
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=sugestao_nome,
            title="Salvar Exportação Delta",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if not filepath: return

        # 3. Criação do Excel e Estilos Base
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Mudanças do Período"

        visao_atual = self.var_tipo_visao.get()
        nome_agrupador = self.var_agrupador.get()

        # 4. Cabeçalhos Dinâmicos
        headers = [nome_agrupador, "Nível", "Documento", "Título"]
        if visao_atual == "Efetiva":
            headers += ["Status Aconex (Antes)", "Status Efetivo (Antes)", "Status Aconex (Depois)", "Status Efetivo (Depois)"]
        else:
            # NOVA REGRA: Colunas de Revisão e Data separadas na Visão Bruta
            headers += [
                "Revisão (Antes)", "Data (Antes)", "Status Aconex (Antes)", "Status Efetivo (Antes)", 
                "Revisão (Depois)", "Data (Depois)", "Status Aconex (Depois)", "Status Efetivo (Depois)"
            ]

        ws.append(headers)

        # Estilos Visuais Premium
        header_fill = PatternFill(start_color="1F538D", end_color="1F538D", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        align_center = Alignment(horizontal="center", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
        thin_border = Border(left=Side(style='thin', color="CCCCCC"), 
                             right=Side(style='thin', color="CCCCCC"), 
                             top=Side(style='thin', color="CCCCCC"), 
                             bottom=Side(style='thin', color="CCCCCC"))

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = align_center
            cell.border = thin_border

        # 5. Inserção de Dados (Respeitando o Filtro de Ocultar Aprovados)
        filtrar = self.var_ignorar_aprovados.get()
        STATUS_APROVADOS = ['Aprovado', 'Aprovado com Comentários', 'Para Assinatura']

        row_idx = 2
        for grupo in sorted(self.dados_cache.keys()):
            for nivel, lista_docs in self.dados_cache[grupo].items():
                for doc in lista_docs:
                    if filtrar and str(doc['real_antes']).strip() in STATUS_APROVADOS:
                        continue

                    if visao_atual == "Efetiva":
                        linha = [
                            grupo, nivel, doc['doc'], doc['titulo'],
                            doc['raw_antes'], doc['real_antes'],
                            doc['raw_depois'], doc['real_depois']
                        ]
                    else:
                        from datetime import datetime

                        # Helper para converter a string (DD/MM/YY) de volta para um objeto Date real para o Excel
                        def formatar_data_excel(data_str):
                            if data_str and data_str != "-":
                                try:
                                    return datetime.strptime(data_str, '%d/%m/%y').date()
                                except:
                                    return data_str
                            return "-"
                        rev_a = doc.get('rev_antes', '-')
                        data_a_excel = formatar_data_excel(doc.get('data_antes', '-'))

                        rev_d = doc.get('rev_depois', '-')
                        data_d_excel = formatar_data_excel(doc.get('data_depois', '-'))

                        # NOVA REGRA: Injeção das colunas totalmente separadas
                        linha = [
                            grupo, nivel, doc['doc'], doc['titulo'],
                            rev_a, data_a_excel, doc['raw_antes'], doc['real_antes'],
                            rev_d, data_d_excel, doc['raw_depois'], doc['real_depois']
                        ]

                    ws.append(linha)

                    # Garantir que as células com datas tenham a formatação de data curta nativa do Excel
                    if visao_atual == "Bruta":
                        if linha[5] != "-": ws.cell(row=row_idx, column=6).number_format = 'dd/mm/yyyy'
                        if linha[9] != "-": ws.cell(row=row_idx, column=10).number_format = 'dd/mm/yyyy'

                    # Aplica a borda em todas as células da nova linha
                    for cell in ws[row_idx]:
                        cell.border = thin_border
                        cell.alignment = align_left

                    row_idx += 1

        # 6. Ajuste Automático da Largura das Colunas
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            # Limita a largura máxima para 60 para não ficar gigante em nomes muito compridos
            adjusted_width = min(max_length + 2, 60)
            ws.column_dimensions[column].width = adjusted_width

        # 7. Salva o Arquivo Final
        try:
            wb.save(filepath)
            messagebox.showinfo("Exportação Concluída", f"Relatório salvo com sucesso!\n\nLocal:\n{filepath}")
        except PermissionError:
            messagebox.showerror("Erro de Permissão", "O Excel está aberto? Feche o arquivo e tente novamente.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar o arquivo:\n{e}")

# --- 6. Tela de Verificação de Status ---
class StatusCheckView(ctk.CTkFrame):
    def __init__(self, master, excel_handler, **kwargs):
        super().__init__(master, **kwargs)
        self.excel_handler = excel_handler
        self.data_manager = DataManager() # Instancia lógica compartilhada

        # Variáveis (Aba Excel)
        self.path_list = None
        self.sheet_list = ctk.StringVar()
        self.header_row_var = ctk.StringVar(value="1") # Padrão linha 1

        self.col_itaipu = ctk.StringVar()
        self.col_cmi = ctk.StringVar()
        self.colunas_encontradas = []
        # Variáveis (Aba Lista Rápida)
        self.tipo_codigo_lista = ctk.StringVar(value="Código Itaipu")
        self.setup_ui()
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1) # Mudou para 5 pois adicionamos uma linha

        # Título
        self.label_title = ctk.CTkLabel(self, text="Verificação de Status de Documentos", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        # =========================================================
        # --- BASE ACONEX (GLOBAL PARA TODAS AS ABAS) ---
        # =========================================================
        self.frame_aconex = ctk.CTkFrame(self)
        self.frame_aconex.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(self.frame_aconex, text="Base Aconex (Obrigatório):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.btn_load_aconex = ctk.CTkButton(self.frame_aconex, text="Selecionar Arquivo", command=self.carregar_base_aconex_ui)
        self.btn_load_aconex.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.lbl_aconex_path = ctk.CTkLabel(self.frame_aconex, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_aconex_path.grid(row=0, column=2, padx=10, pady=10, sticky="w")
        # =========================================================
        # --- TABVIEW (GERENCIADOR DE ABAS) ---
        # =========================================================
        self.tabview = ctk.CTkTabview(self, height=220)
        self.tabview.grid(row=2, column=0, padx=20, pady=5, sticky="ew") # Mudou para row=2

        self.tab_excel = self.tabview.add("Via Arquivo Excel")
        self.tab_lista = self.tabview.add("Via Lista Rápida")
        self.tab_toda_aconex = self.tabview.add("Todos Aconex")
        # ---------------------------------------------------------
        # ABA 1: VIA ARQUIVO EXCEL
        # ---------------------------------------------------------
        self.tab_excel.grid_columnconfigure(0, weight=1)
        self.frame_config = ctk.CTkFrame(self.tab_excel, fg_color="transparent")
        self.frame_config.grid(row=0, column=0, sticky="ew")

        # 1. Seleção de Arquivo e Aba
        ctk.CTkLabel(self.frame_config, text="1. Lista de Documentos (Excel):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.btn_file = ctk.CTkButton(self.frame_config, text="Selecionar Arquivo", command=self.selecionar_arquivo)
        self.btn_file.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        self.lbl_path = ctk.CTkLabel(self.frame_config, text="...", text_color="gray")
        self.lbl_path.grid(row=0, column=2, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(self.frame_config, text="Aba (Sheet):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.opt_sheet = ctk.CTkOptionMenu(self.frame_config, variable=self.sheet_list, values=["Selecione arquivo"])
        self.opt_sheet.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        # 2. Definição de Cabeçalho
        ctk.CTkLabel(self.frame_config, text="2. Configuração de Leitura:", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, padx=10, pady=(15,5), sticky="w")

        frame_row = ctk.CTkFrame(self.frame_config, fg_color="transparent")
        frame_row.grid(row=3, column=0, columnspan=3, sticky="w", padx=10)

        ctk.CTkLabel(frame_row, text="Linha do Cabeçalho:").pack(side="left", padx=(0,10))
        self.entry_row = ctk.CTkEntry(frame_row, textvariable=self.header_row_var, width=50)
        self.entry_row.pack(side="left", padx=5)

        self.btn_load_cols = ctk.CTkButton(frame_row, text="Carregar Colunas", command=self.carregar_colunas, fg_color="#E59400", hover_color="#B87700", width=120)
        self.btn_load_cols.pack(side="left", padx=10)
        # 3. Mapeamento de Colunas
        ctk.CTkLabel(self.frame_config, text="3. Identifique as Colunas:", font=ctk.CTkFont(weight="bold")).grid(row=4, column=0, padx=10, pady=(15,5), sticky="w")
        ctk.CTkLabel(self.frame_config, text="Coluna Cód. Itaipu:").grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.opt_col_itaipu = ctk.CTkOptionMenu(self.frame_config, variable=self.col_itaipu, values=["Carregue as colunas primeiro"])
        self.opt_col_itaipu.grid(row=5, column=1, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(self.frame_config, text="Coluna Cód. CMI:").grid(row=6, column=0, padx=10, pady=5, sticky="w")
        self.opt_col_cmi = ctk.CTkOptionMenu(self.frame_config, variable=self.col_cmi, values=["Carregue as colunas primeiro"])
        self.opt_col_cmi.grid(row=6, column=1, padx=10, pady=5, sticky="w")
        # ---------------------------------------------------------
        # ABA 2: VIA LISTA RÁPIDA
        # ---------------------------------------------------------
        self.tab_lista.grid_columnconfigure(0, weight=1)
        self.frame_lista = ctk.CTkFrame(self.tab_lista, fg_color="transparent")
        self.frame_lista.grid(row=0, column=0, sticky="nsew", pady=10)
        ctk.CTkLabel(self.frame_lista, text="Tipo de Código:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="nw")

        # Segmented Button ou OptionMenu para escolher o tipo de código colado
        self.opt_tipo_lista = ctk.CTkOptionMenu(self.frame_lista, variable=self.tipo_codigo_lista, values=["Código Itaipu", "Código CMI"])
        self.opt_tipo_lista.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(self.frame_lista, text="Cole os Códigos\n(um por linha):").grid(row=1, column=0, padx=10, pady=5, sticky="nw")

        self.textbox_lista = ctk.CTkTextbox(self.frame_lista, width=400, height=130)
        self.textbox_lista.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        # ---------------------------------------------------------
        # ABA 3: TODOS ACONEX (Interface Simples)
        # ---------------------------------------------------------
        self.tab_toda_aconex.grid_columnconfigure(0, weight=1)
        self.frame_toda = ctk.CTkFrame(self.tab_toda_aconex, fg_color="transparent")
        self.frame_toda.grid(row=0, column=0, sticky="nsew", pady=20)

        lbl_info = ctk.CTkLabel(
            self.frame_toda, 
            text="Esta opção analisará automaticamente TODOS os documentos\nvigentes da base de dados Aconex carregada.", 
            justify="center", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_info.pack(pady=20)
        # =========================================================
        # --- COMPONENTES GERAIS (FORA DAS ABAS) ---
        # =========================================================
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=3, column=0, padx=20, pady=(15, 0), sticky="ew") # Mudou para row=3
        self.progress_bar.set(0)
        self.btn_executar = ctk.CTkButton(self, text="Gerar Relatório de Status", command=self.iniciar_processo, height=40, fg_color="green", hover_color="darkgreen")
        self.btn_executar.grid(row=4, column=0, padx=20, pady=15, sticky="ew") # Mudou para row=4
        self.textbox_log = ctk.CTkTextbox(self)
        self.textbox_log.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="nsew") # Mudou para row=5
        self.log("Sistema pronto. Selecione a base Aconex e a sua lista.")
    def log(self, msg):
        self.textbox_log.insert("end", msg + "\n")
        self.textbox_log.see("end")
    def carregar_base_aconex_ui(self):
        path_aconex = self.excel_handler.selecionar_arquivo("aconex")
        if not path_aconex: return

        abas = self.excel_handler.listar_abas(path_aconex)
        aba_aconex = "Documentos" if "Documentos" in abas else (abas[0] if abas else "")

        self.log("Carregando base Aconex na memória... Aguarde.")
        self.update_idletasks()

        sucesso, msg = self.data_manager.carregar_aconex(path_aconex, aba_aconex)

        if sucesso:
            self.lbl_aconex_path.configure(text=os.path.basename(path_aconex), text_color="white")
            self.log("✅ Base Aconex carregada com sucesso!")
        else:
            self.log(msg)
            messagebox.showerror("Erro", msg)

    def selecionar_arquivo(self):
        path = self.excel_handler.selecionar_arquivo("status_list")
        if path:
            self.path_list = path
            self.lbl_path.configure(text=os.path.basename(path))
            abas = self.excel_handler.listar_abas(path)
            self.opt_sheet.configure(values=abas)
            if abas: self.sheet_list.set(abas[0])
    def carregar_colunas(self):
        if not self.path_list:
            messagebox.showwarning("Aviso", "Selecione um arquivo primeiro.")
            return

        try:
            row_idx = int(self.header_row_var.get()) - 1 
            if row_idx < 0: row_idx = 0

            df = pd.read_excel(self.path_list, sheet_name=self.sheet_list.get(), header=row_idx, nrows=0)
            cols = list(df.columns)

            self.colunas_encontradas = [str(c) for c in cols if "Unnamed" not in str(c)]

            # --- MODIFICAÇÃO: Injeção da opção "- NENHUM -" ---
            opcoes_colunas = ["- NENHUM -"] + self.colunas_encontradas

            self.opt_col_itaipu.configure(values=opcoes_colunas)
            self.opt_col_cmi.configure(values=opcoes_colunas)

            if self.colunas_encontradas:
                self.col_itaipu.set(self.colunas_encontradas[0])
                if len(self.colunas_encontradas) > 1:
                    self.col_cmi.set(self.colunas_encontradas[1])
                else:
                    self.col_cmi.set("- NENHUM -") # Se só tem 1 coluna, seta o outro como nenhum automaticamente

            self.log(f"Colunas carregadas da linha {row_idx + 1}.")

        except Exception as e:
            self.log(f"Erro ao ler colunas: {e}")
            messagebox.showerror("Erro", f"Erro ao ler linha: {e}")
    def iniciar_processo(self):
        aba_ativa = self.tabview.get()

        # Validações preliminares baseadas na aba
        if aba_ativa == "Via Arquivo Excel" and not self.path_list:
            messagebox.showwarning("Aviso", "Selecione o arquivo Excel.")
            return
        elif aba_ativa == "Via Lista Rápida":
            texto_colado = self.textbox_lista.get("1.0", "end-1c").strip()
            if not texto_colado:
                messagebox.showwarning("Aviso", "Cole os códigos na caixa de texto.")
                return

        # Verificação rígida da Base Aconex (COMUM PARA TODAS AS ABAS)
        if self.data_manager.df_aconex is None:
            messagebox.showwarning("Aviso", "Por favor, carregue a Base Aconex no botão do topo antes de gerar o relatório.")
            return
        self.btn_executar.configure(state="disabled")
        self.log("--- INICIANDO VERIFICAÇÃO ---")
        self.progress_bar.set(0)
        try:
            # =========================================================
            # 1. NORMALIZAÇÃO DO DATAFRAME df_input
            # =========================================================
            if aba_ativa == "Via Arquivo Excel":
                row_header = int(self.header_row_var.get()) - 1
                df_input = pd.read_excel(self.path_list, sheet_name=self.sheet_list.get(), header=row_header, dtype=str)
                df_input = df_input.fillna('')
                col_itaipu_nome = self.col_itaipu.get()
                col_cmi_nome = self.col_cmi.get()
                # Tratamento do "- NENHUM -" criando colunas em branco temporárias
                if col_itaipu_nome == "- NENHUM -":
                    df_input["_coluna_vazia_itaipu"] = ""
                    col_itaipu_nome = "_coluna_vazia_itaipu"

                if col_cmi_nome == "- NENHUM -":
                    df_input["_coluna_vazia_cmi"] = ""
                    col_cmi_nome = "_coluna_vazia_cmi"
                # Filtro de linhas vazias
                df_input = df_input[ (df_input[col_itaipu_nome].str.strip() != '') | (df_input[col_cmi_nome].str.strip() != '') ]
            elif aba_ativa == "Via Lista Rápida":
                # Caso: Via Lista Rápida (Cria um DataFrame artificial em memória)
                linhas = [linha.strip() for linha in self.textbox_lista.get("1.0", "end-1c").split('\n') if linha.strip()]
                tipo_selecionado = self.tipo_codigo_lista.get()

                if tipo_selecionado == "Código Itaipu":
                    df_input = pd.DataFrame({"Itaipu": linhas, "CMI": [""] * len(linhas)})
                else:
                    df_input = pd.DataFrame({"Itaipu": [""] * len(linhas), "CMI": linhas})

                col_itaipu_nome = "Itaipu"
                col_cmi_nome = "CMI"

            else:
                # Caso: Todos Aconex
                self.log("Filtrando base Aconex para obter todos os documentos vigentes...")
                df_base = self.data_manager.df_aconex.copy()

                # Filtra apenas o Current == True
                df_current = df_base[df_base['Current'].astype(str).str.lower() == 'true'].copy()

                # Pega as colunas de códigos. Usa strings vazias se a coluna não existir (segurança)
                col_it = 'No. do Documento' if 'No. do Documento' in df_current.columns else ''
                col_cm = 'Controle do Emissor' if 'Controle do Emissor' in df_current.columns else ''

                lista_itaipu = df_current[col_it].tolist() if col_it else [""] * len(df_current)
                lista_cmi = df_current[col_cm].tolist() if col_cm else [""] * len(df_current)

                df_input = pd.DataFrame({"Itaipu": lista_itaipu, "CMI": lista_cmi})

                # Remove linhas completamente vazias e duplicatas
                df_input = df_input[ (df_input["Itaipu"].str.strip() != '') | (df_input["CMI"].str.strip() != '') ]
                df_input = df_input.drop_duplicates()

                col_itaipu_nome = "Itaipu"
                col_cmi_nome = "CMI"
            # =========================================================
            resultado_dados = []
            total = len(df_input)

            # Contador detalhado para o gráfico
            status_counter = Counter()

            # Flag para saber se precisamos exibir os status de modelo no gráfico
            tem_modelos_na_lista = False
            # 2. Processamento
            for idx, row in df_input.iterrows():
                progresso = (len(resultado_dados) + 1) / total
                if len(resultado_dados) % 5 == 0:
                    self.progress_bar.set(progresso)
                    self.update_idletasks()
                c_itaipu = str(row.get(col_itaipu_nome, '')).strip()
                c_cmi = str(row.get(col_cmi_nome, '')).strip()
                df_tracking = self.data_manager.localiza_doc_historico(c_itaipu, c_cmi)

                dados_linha = {
                    'Código Itaipu': c_itaipu,
                    'Código CMI': c_cmi,
                    'Título': '',
                    'Revisão': '',
                    'Data': '',
                    'Status Aconex': '',
                    'Status Real': 'NÃO EMITIDO'
                }
                if not df_tracking.empty:
                    # --- Lógica de Linha da Verdade ---
                    linha_dinamica = None
                    docs_current = df_tracking[df_tracking["Current"].astype(str).str.lower() == "true"]
                    cand_current = docs_current.iloc[0] if not docs_current.empty else None
                    # Título e Códigos
                    if cand_current is not None:
                        dados_linha['Título'] = cand_current.get('Título', '')

                        if cand_current.get('No. do Documento'): 
                            dados_linha['Código Itaipu'] = cand_current.get('No. do Documento')
                        if cand_current.get('Controle do Emissor'): 
                            dados_linha['Código CMI'] = cand_current.get('Controle do Emissor')

                    elif not df_tracking.empty:
                        # Fallback: se não achar o 'Current', pega da linha mais recente do histórico
                        linha_topo = df_tracking.iloc[0]
                        dados_linha['Título'] = linha_topo.get('Título', '')

                        if linha_topo.get('No. do Documento'): 
                            dados_linha['Código Itaipu'] = linha_topo.get('No. do Documento')
                        if linha_topo.get('Controle do Emissor'): 
                            dados_linha['Código CMI'] = linha_topo.get('Controle do Emissor')
                    # Lógica Terminated / Retrocesso
                    if cand_current is not None:
                        status_rev = str(cand_current.get("Status da Revisão", "")).lower()
                        revisao_atual = str(cand_current.get("Revisão", "")).strip()
                        if "terminated" not in status_rev:
                            linha_dinamica = cand_current
                        else:
                            rev_norm = self.data_manager.normalizar_revisao(revisao_atual)
                            rev_limite = self.data_manager.normalizar_revisao("0A")
                            if rev_norm <= rev_limite:
                                linha_dinamica = None
                            else:
                                df_valid = df_tracking[df_tracking["Revisão"].str.strip() != revisao_atual].copy()
                                if not df_valid.empty:
                                    try:
                                        df_valid['Versão_Int'] = pd.to_numeric(df_valid['Versão'], errors='coerce')
                                        linha_dinamica = df_valid.sort_values(by=['Versão_Int', 'Versão'], ascending=False).iloc[0]
                                    except:
                                        linha_dinamica = df_valid.sort_values(by='Versão', ascending=False).iloc[0]
                    elif not df_tracking.empty:
                         linha_dinamica = df_tracking.iloc[0]
                    # Preencher dados visuais
                    rev_final = ""
                    if linha_dinamica is not None:
                        dados_linha['Revisão'] = linha_dinamica.get('Revisão', '')
                        dados_linha['Data'] = linha_dinamica.get('Data de Alteração', '')
                        dados_linha['Status Aconex'] = linha_dinamica.get('Status', '')
                        rev_final = str(linha_dinamica.get('Revisão', '')).strip()
                    else:
                        dados_linha['Status Aconex'] = ''
                    # Extrair o Tipo do Documento para rotear a lógica
                    tipo_doc = ""
                    if cand_current is not None:
                        tipo_doc = str(cand_current.get('Tipo do Documento', '')).strip().upper()
                    elif not df_tracking.empty:
                        tipo_doc = str(df_tracking.iloc[0].get('Tipo do Documento', '')).strip().upper()

                    is_modelo = "MODEL" in tipo_doc  # Cobre "Model" e "Modelo"

                    # [NOVO] Acende a bandeira para o gráfico gerar as barras de modelo depois
                    if is_modelo:
                        tem_modelos_na_lista = True
                    # Preparar base de cálculo removendo Terminated (se for o caso)
                    df_calc = df_tracking.copy()
                    if cand_current is not None and "terminated" in str(cand_current.get("Status da Revisão", "")).lower():
                        revisao_atual = str(cand_current.get("Revisão", "")).strip()
                        rev_norm = self.data_manager.normalizar_revisao(revisao_atual)
                        if rev_norm <= self.data_manager.normalizar_revisao("0A"):
                            df_calc = pd.DataFrame()
                        else:
                            df_calc = df_tracking[df_tracking["Revisão"].str.strip() != revisao_atual].copy()
                    # Calcular Status Real: O grande roteador
                    if df_calc.empty:
                        s_real = "NÃO EMITIDO"
                    else:
                        if is_modelo:
                            s_real = self.data_manager.calcular_status_real_modelo(df_calc, rev_final)
                        else:
                            s_real = self.data_manager.calcular_status_real(df_calc, rev_final)

                    dados_linha['Status Real'] = s_real
                else:
                     dados_linha['Status Real'] = 'NÃO EMITIDO' 
                # Incrementa contador
                status_counter[dados_linha['Status Real']] += 1
                resultado_dados.append(dados_linha)
            # 3. Geração do Excel (Totalmente preservado)
            self.log("Gerando Excel formatado...")
            nome_arq = f"Status_Docs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=nome_arq, title="Salvar Relatório")

            if not save_path:
                self.btn_executar.configure(state="normal")
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Status Documentos"
            ws.column_dimensions['A'].width = 25
            ws.column_dimensions['B'].width = 25
            ws.column_dimensions['C'].width = 60
            ws.column_dimensions['D'].width = 10
            ws.column_dimensions['E'].width = 15
            ws.column_dimensions['F'].width = 25
            ws.column_dimensions['G'].width = 25
            headers = ['Código Itaipu', 'Código CMI', 'Título', 'Revisão', 'Data', 'Status Aconex', 'Status Real']
            for col_num, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                cell.alignment = Alignment(horizontal='center')

            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for r_idx, dados in enumerate(resultado_dados, 2):
                ws.cell(row=r_idx, column=1, value=dados['Código Itaipu'])
                ws.cell(row=r_idx, column=2, value=dados['Código CMI'])
                ws.cell(row=r_idx, column=3, value=dados['Título'])
                ws.cell(row=r_idx, column=4, value=dados['Revisão']).alignment = Alignment(horizontal='center')
                ws.cell(row=r_idx, column=5, value=dados['Data']).alignment = Alignment(horizontal='center')
                ws.cell(row=r_idx, column=6, value=dados['Status Aconex'])

                cell_real = ws.cell(row=r_idx, column=7, value=dados['Status Real'])
                cell_real.alignment = Alignment(horizontal='center', vertical='center')

                s_real = dados['Status Real']
                if s_real in ['Aprovado', 'Aprovado com Comentários', 'Para Assinatura'] or s_real.startswith('Aprovado -'):
                    cell_real.font = Font(color="006100") 
                    cell_real.fill = PatternFill(start_color="C6EFCE", fill_type="solid")
                elif s_real == 'Em Processo' or s_real.startswith('Em Análise -') or s_real.startswith('Emissão Inicial -'):
                    cell_real.font = Font(color="0000FF")
                elif s_real in ['Não Aprovado', 'NÃO EMITIDO'] or s_real.startswith('Não Aprovado -'):
                    cell_real.font = Font(color="9C0006")
                    cell_real.fill = PatternFill(start_color="FFC7CE", fill_type="solid")
            # 4. Gráfico
            col_chart = 10
            ws.cell(row=1, column=col_chart, value="Status")
            ws.cell(row=1, column=col_chart+1, value="Qtd")
            ordem_grafico = [
                'Aprovado', 'Para Assinatura', 'Para Aprovação', 'Aprovado com Comentários',
                'Em Processo',
                'Não Aprovado', 'NÃO EMITIDO'
            ]

            # Adiciona a ordem estruturada para os modelos APENAS se houver modelos na lista
            if tem_modelos_na_lista:
                ordem_modelos = [
                    'Aprovado - LOD 350', 'Aprovado - LOD 300', 'Aprovado - Fase Preliminar',
                    'Em Análise - LOD 350', 'Em Análise - LOD 300', 'Em Análise - Fase Preliminar',
                    'Emissão Inicial - LOD 350', 'Emissão Inicial - LOD 300', 'Emissão Inicial - Fase Preliminar',
                    'Não Aprovado - LOD 350', 'Não Aprovado - LOD 300', 'Não Aprovado - Fase Preliminar'
                ]
                ordem_grafico.extend(ordem_modelos)
            VERDE = "16B63C"
            AZUL  = "0070C0"
            VERMELHO = "C00000"
            CINZA = "808080"
            def definir_cor(status):
                st_upper = status.upper()

                # 1. Grupo dos Aprovados (Verde)
                if st_upper in ['APROVADO', 'APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA', 'PARA APROVAÇÃO'] or st_upper.startswith('APROVADO -'):
                    return VERDE
                # 2. Grupo dos Reprovados / Não Emitidos (Vermelho)
                elif "NÃO" in st_upper or "NAO" in st_upper:
                    return VERMELHO
                # 3. Grupo em Andamento (Azul)
                elif st_upper == 'EM PROCESSO' or st_upper.startswith('EM ANÁLISE -') or st_upper.startswith('EMISSÃO INICIAL -'):
                    return AZUL
                # 4. Status Fantasmas ou Informativos (Cinza)
                else:
                    return CINZA
            row_aux = 2
            lista_cores_para_aplicar = []
            for st in ordem_grafico:
                val = status_counter.get(st, 0)
                if val > 0:
                    ws.cell(row=row_aux, column=col_chart, value=st)
                    ws.cell(row=row_aux, column=col_chart+1, value=val)
                    lista_cores_para_aplicar.append(definir_cor(st))
                    row_aux += 1
            for st, val in status_counter.items():
                if st not in ordem_grafico and val > 0:
                    ws.cell(row=row_aux, column=col_chart, value=st)
                    ws.cell(row=row_aux, column=col_chart+1, value=val)
                    lista_cores_para_aplicar.append(definir_cor(st))
                    row_aux += 1
            chart = BarChart()
            chart.type = "bar"
            chart.title = "Situação da documentação analisada"
            chart.title.overlay = False 
            chart.style = 1 
            chart.height = 10
            chart.width = 20
            chart.legend = None 
            data = Reference(ws, min_col=col_chart+1, min_row=1, max_row=row_aux-1)
            cats = Reference(ws, min_col=col_chart, min_row=2, max_row=row_aux-1)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            chart.x_axis.delete = False            
            chart.x_axis.tickLblPos = "low"       
            chart.x_axis.scaling.orientation = "maxMin" 
            chart.y_axis.delete = False            
            chart.y_axis.tickLblPos = "none"      
            chart.y_axis.scaling.orientation = "minMax" 
            chart.y_axis.crosses = "max"          
            chart.y_axis.majorGridlines = ChartLines() 
            chart.y_axis.majorGridlines.spPr = GraphicalProperties(
                ln=LineProperties(
                    solidFill=ColorChoice(srgbClr="D9D9D9"),
                    prstDash="sysDot", 
                    w=10000 
                )
            )
            chart.x_axis.majorGridlines = ChartLines()
            chart.x_axis.majorGridlines.spPr = GraphicalProperties(
                ln=LineProperties(
                    solidFill=ColorChoice(srgbClr="F2F2F2"), 
                    w=10000 
                )
            )
            series = chart.series[0]
            for i, cor_hex in enumerate(lista_cores_para_aplicar):
                pt = DataPoint(idx=i)
                pt.graphicalProperties.solidFill = cor_hex
                series.dPt.append(pt)
            series.dLbls = DataLabelList()
            series.dLbls.showVal = True       
            series.dLbls.showCatName = False  
            series.dLbls.showSerName = False  
            series.dLbls.showLegendKey = False 
            series.dLbls.position = 'outEnd'  
            ws.add_chart(chart, "J5")
            wb.save(save_path)
            self.log(f"Salvo em: {os.path.basename(save_path)}")
            messagebox.showinfo("Sucesso", "Relatório Gerado!")

            try: os.startfile(save_path)
            except: pass
        except Exception as e:
            self.log(f"ERRO: {e}")
            messagebox.showerror("Erro", str(e))

        self.btn_executar.configure(state="normal")
        self.progress_bar.set(0)
# --- 9. Tela de API Aconex (Integração Completa) ---
class AconexView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # --- LISTA DE USUÁRIOS (ADICIONE AQUI AS NOVAS PESSOAS) ---
        self.CREDENCIAIS_SALVAS = {
            "Bianca Santos": { 
                "CLIENT_ID": "SCP_BIANCA_SANTOS_ACONEX_client_APPID",
                "CLIENT_SECRET": os.getenv("SECRET_BIANCA", ""),
                "USER_ID": "1208460585"
            },
            "Luan Cozer": {
                "CLIENT_ID": "SCP_LUAN_COZER_ACONEX_client_APPID",
                "CLIENT_SECRET": os.getenv("SECRET_LUAN", ""),
                "USER_ID": "1208560183"
            },
            "Rafhael Martins": { 
                "CLIENT_ID": "SCP_RAFHAEL_MARTINS_ACONEX_client_APPID",
                "CLIENT_SECRET": os.getenv("SECRET_RAFHAEL", ""),
                "USER_ID": "1208639621"
            },

        }
        self.PROJECT_ID = "1207975853" 
        self.ACONEX_INSTANCE = "https://us1.aconex.com"
        self.AUTH_URL = "https://constructionandengineering.oraclecloud.com/auth/token"
        # Campos da API
        self.CAMPOS_LISTA = (
            "statusid,current,trackingId,title,docno,revision,"
            "versionnumber,reviewstatus,Especialidad_singleSelect,"
            "Subespecialidad_singleSelect,doctype,registered,Dcc_singleSelect,"
            "ControlDelEmisor_singleLineText,Idioma_singleSelect,reviewsource,"
            "Disciplina_singleSelect,"
            "TipoDeDocumentoDcc_singleSelect,ControlCmi_singleLineText"
        )
        self.CAMPOS_STRING = "".join(self.CAMPOS_LISTA).replace("\n", "").replace(" ", "")
        # Variáveis de Interface
        self.user_var = ctk.StringVar(value="Luan Cozer")
        self.client_id_var = ctk.StringVar()
        self.client_secret_var = ctk.StringVar()
        self.user_id_var = ctk.StringVar()

        self.setup_ui()
        self.atualizar_campos("Luan Cozer") # Carrega o padrão ao iniciar
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        # Título
        self.label_title = ctk.CTkLabel(self, text="Extração Automática Aconex (API)", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        # --- Área de Configuração ---
        self.frame_config = ctk.CTkFrame(self)
        self.frame_config.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        # Seleção de Usuário
        ctk.CTkLabel(self.frame_config, text="Selecione o Usuário:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Cria a lista de opções: Todos os nomes do dicionário + "Outro"
        opcoes_menu = list(self.CREDENCIAIS_SALVAS.keys()) + ["Outros"]

        self.opt_user = ctk.CTkOptionMenu(self.frame_config, variable=self.user_var, values=opcoes_menu, command=self.atualizar_campos)
        self.opt_user.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        # Campos de Credenciais
        ctk.CTkLabel(self.frame_config, text="Client ID:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.entry_client_id = ctk.CTkEntry(self.frame_config, textvariable=self.client_id_var, width=300)
        self.entry_client_id.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(self.frame_config, text="Client Secret:").grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.entry_secret = ctk.CTkEntry(self.frame_config, textvariable=self.client_secret_var, width=300, show="*")
        self.entry_secret.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(self.frame_config, text="Aconex User ID:").grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.entry_userid = ctk.CTkEntry(self.frame_config, textvariable=self.user_id_var, width=300)
        self.entry_userid.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        # --- Configuração de Proxy (Manual) ---
        ctk.CTkLabel(self.frame_config, text="Proxy (Opcional):").grid(row=4, column=0, padx=10, pady=5, sticky="e")
        self.proxy_var = ctk.StringVar()
        self.entry_proxy = ctk.CTkEntry(self.frame_config, textvariable=self.proxy_var, width=300, placeholder_text="Ex: http://proxy.ge.com:80")
        self.entry_proxy.grid(row=4, column=1, padx=10, pady=5, sticky="w")

        # Dica visual
        lbl_dica = ctk.CTkLabel(self.frame_config, text="* Deixe vazio para detectar automaticamente", font=("Arial", 10), text_color="gray")
        lbl_dica.grid(row=5, column=1, sticky="w", padx=10)
        # --- Área de Ação ---
        self.frame_action = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_action.grid(row=2, column=0, padx=20, pady=20, sticky="ew")

        self.btn_run = ctk.CTkButton(self.frame_action, text="INICIAR EXTRAÇÃO TOTAL", command=self.iniciar_thread, height=50, fg_color="#b30000", hover_color="#800000")
        self.btn_run.pack(fill="x")

        self.progress = ctk.CTkProgressBar(self.frame_action)
        self.progress.pack(fill="x", pady=(10, 0))
        self.progress.set(0)
        # Logs
        self.textbox_log = ctk.CTkTextbox(self)
        self.textbox_log.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="nsew")
    def get_proxies_configurados(self):
        """
        Define qual proxy usar.
        Prioridade 1: O que o usuário digitou na tela.
        Prioridade 2: O que o Windows (Internet Explorer) está usando.
        """
        # 1. Tenta pegar do campo de texto manual
        proxy_manual = self.proxy_var.get().strip()
        if proxy_manual:
            self.log(f"Usando Proxy Manual: {proxy_manual}")
            return {
                "http": proxy_manual,
                "https": proxy_manual # Usa o mesmo para HTTPS
            }

        # 2. Tenta detectar do sistema (Windows)
        try:
            proxies_sistema = urllib.request.getproxies()
            if proxies_sistema:
                self.log("Proxy do Sistema detectado automaticamente.")
                return proxies_sistema
        except:
            pass

        self.log("Nenhum proxy detectado. Tentando conexão direta...")
        return None
    def atualizar_campos(self, choice):
        # Se 'choice' vier None (na inicialização), pega o valor atual da variável
        selecao = choice if choice else self.user_var.get()
        if selecao in self.CREDENCIAIS_SALVAS:
            # Pega os dados desse usuário específico
            dados = self.CREDENCIAIS_SALVAS[selecao]

            self.client_id_var.set(dados["CLIENT_ID"])
            self.client_secret_var.set(dados["CLIENT_SECRET"])
            self.user_id_var.set(dados["USER_ID"])

            # Trava os campos para não editar acidentalmente
            self.entry_client_id.configure(state="disabled")
            self.entry_secret.configure(state="disabled")
            self.entry_userid.configure(state="disabled")
        else:
            # Caso "Outro"
            self.client_id_var.set("")
            self.client_secret_var.set("")
            self.user_id_var.set("")

            # Libera para digitar
            self.entry_client_id.configure(state="normal")
            self.entry_secret.configure(state="normal")
            self.entry_userid.configure(state="normal")
    def log(self, msg):
        # O self.after(0, ...) garante que o Tkinter atualize a tela na thread correta sem travar!
        def atualizar_tela():
            self.textbox_log.insert("end", msg + "\n")
            self.textbox_log.see("end")
        self.after(0, atualizar_tela)
    def iniciar_thread(self):
        # Validação simples
        if not self.client_id_var.get() or not self.client_secret_var.get():
            messagebox.showwarning("Aviso", "Preencha as credenciais.")
            return
        self.btn_run.configure(state="disabled", text="Extraindo... (Tempo aprox ~30min)")
        self.progress.set(0)
        self.progress.start() # Modo indeterminado (vai e volta) pois não sabemos o total exato de páginas de antemão

        # Inicia a thread para não travar o app
        threading.Thread(target=self.executar_script_aconex, daemon=True).start()
    def get_auth_token(self, sessao_rede):
        """ Recebe a sessão (Session) para aproveitar o túnel seguro """
        creds = base64.b64encode(f"{self.client_id_var.get()}:{self.client_secret_var.get()}".encode()).decode()
        headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
        data = {"grant_type": "client_credentials", "user_id": self.user_id_var.get(), "user_site": self.ACONEX_INSTANCE}
        try:
            # REMOVIDO o verify=False! O Zscaler agora será aceito pelo truststore nativamente.
            resp = sessao_rede.post(self.AUTH_URL, headers=headers, data=data, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("access_token")
            else:
                self.log(f"Erro Autenticação: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            self.log(f"Erro Conexão Auth: {e}")
            return None
    def executar_script_aconex(self):
        try:
            # --- 1. MÁGICA DO ZSCALER (TRUSTSTORE) ---
            import truststore
            truststore.inject_into_ssl() # Injeta os certificados do Windows no Python

            # --- 2. MÁGICA DA SESSÃO (MANTÉM O TÚNEL ABERTO) ---
            session = requests.Session()
            meus_proxies = self.get_proxies_configurados()
            if meus_proxies:
                session.proxies.update(meus_proxies)
            # Helpers Thread-Safe para a Interface (Evita Crash)
            def resetar_botoes():
                self.btn_run.configure(state="normal", text="INICIAR EXTRAÇÃO TOTAL")
                self.progress.stop()
                self.progress.set(1)
            # Pega o token usando a sessão nova
            token = self.get_auth_token(session)
            if not token:
                self.after(0, resetar_botoes)
                return
            base_url = f"{self.ACONEX_INSTANCE}/api/projects/{self.PROJECT_ID}/register"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/xml",
                "Accept-Encoding": "gzip, deflate" # Removido 'chunked' (melhora compatibilidade com proxy GE)
            }

            all_data = []
            page = 1
            total_coletado = 0

            agora = datetime.now()
            timestamp = agora.strftime("%d.%m.%y_%Hh%Mm")
            arquivo_final = f"Aconex_Historico_{timestamp}.xlsx"
            self.log("-" * 60)
            self.log(f"Iniciando extração do Projeto ID: {self.PROJECT_ID}")
            self.log(f"Arquivo Final será: {arquivo_final}")
            self.log("-" * 60)
            while True:
                params = {
                    "search_query": "", "return_fields": self.CAMPOS_STRING, "search_type": "PAGED",
                    "page_size": 500, "page_number": page, "show_document_history": "true",
                    "sort_field": "docno", "sort_direction": "ASC"
                }
                sucesso = False
                r = None

                # Retry Logic com Sessão
                for tentativa in range(3):
                    try:
                        # O túnel da sessão cuida do SSL sem reclamar do Zscaler
                        r = session.get(base_url, headers=headers, params=params, timeout=60)
                        if r.status_code == 200:
                            sucesso = True
                            break
                        elif r.status_code == 400: break
                        elif r.status_code == 401:
                            self.log("Token expirado. Renovando...")
                            token = self.get_auth_token(session)
                            if token: headers["Authorization"] = f"Bearer {token}"
                            continue
                        else:
                            self.log(f" [Erro {r.status_code}] Tentativa {tentativa+1}...")
                            time.sleep(5)
                    except Exception as e:
                        self.log(f" [Erro Conexão] {e}")
                        time.sleep(5)
                if not sucesso or (r and r.status_code == 400):
                    self.log(f"Fim da paginação ou erro fatal na página {page}.")
                    break
                # Parser XML (Idêntico ao seu original, não mudei nada aqui)
                try:
                    root = ET.fromstring(r.content)
                    docs_pagina = []
                    for d in root.iter():
                        if 'Document' in d.tag and 'Documents' not in d.tag:
                            item = {}
                            tem_dados = False
                            for field in d:
                                tag = field.tag.split('}')[-1] if '}' in field.tag else field.tag
                                if field.text is not None:
                                    item[tag] = field.text
                                    tem_dados = True
                            if tem_dados: docs_pagina.append(item)

                    qtd = len(docs_pagina)
                    if qtd == 0: break

                    all_data.extend(docs_pagina)
                    total_coletado += qtd
                    self.log(f"Página {page}: +{qtd} docs (Total: {total_coletado})")

                    if qtd < 500:
                        self.log("Última página atingida.")
                        break

                    page += 1
                except Exception as e:
                    self.log(f"Erro XML página {page}: {e}")
                    break

            # --- PÓS PROCESSAMENTO ---
            if all_data:
                self.log(f"Processando DataFrame com {len(all_data)} linhas...")

                # Atualiza a UI para mostrar 90%
                def set_noventa_porcento():
                    self.progress.stop()
                    self.progress.set(0.9)
                self.after(0, set_noventa_porcento)

                df = pd.DataFrame(all_data)
                df.dropna(how='all', inplace=True)
                mapa_colunas = {
                    "ControlDelEmisor_singleLineText": "Controle do Emissor",
                    "DateModified": "Data de Alteração",
                    "DocumentNumber": "No. do Documento",
                    "Title": "Título",
                    "Revision": "Revisão",
                    "TrackingId": "Tracking ID",
                    "DocumentStatus": "Status",
                    "DocumentType": "Tipo do Documento",
                    "ReviewSource": "Fonte",
                    "ReviewStatus": "Status da Revisão",
                    "VersionNumber": "Versão",
                    "Idioma_singleSelect": "Idioma",
                    "Subespecialidad_singleSelect": "Subespecialidade",
                    "Especialidad_singleSelect": "Especialidade",
                    "Dcc_singleSelect": "Subtipo DCC",
                    "TipoDeDocumentoDcc_singleSelect": "Tipo do Documento DCC",
                    "ControlCmi_singleLineText": "Control CMI",
                    "Disciplina_singleSelect": "Disciplina (Modelo)"
                }
                df.rename(columns=mapa_colunas, inplace=True)

                # 2. Reordenar Colunas (Lógica Solicitada)
                self.log("Reordenando colunas conforme padrão...")
                ordem_desejada = [
                    "No. do Documento", "Controle do Emissor", "Tracking ID", "Revisão", 
                    "Data de Alteração", "Status", "Título", "Tipo do Documento", 
                    "Especialidade", "Subespecialidade", "Tipo do Documento DCC", 
                    "Subtipo DCC", "Fonte", "Status da Revisão", "Versão", 
                    "Current", "Idioma", "Control CMI", "Disciplina (Modelo)"
                ]

                # Garante que só pegamos colunas que existem para não dar erro
                colunas_existentes = [c for c in ordem_desejada if c in df.columns]
                # Adiciona o resto que sobrou no final
                colunas_extras = [c for c in df.columns if c not in colunas_existentes]

                df = df[colunas_existentes + colunas_extras]
                # 3. Formatar Datas (Lista Ampliada)
                self.log("Formatando datas...")
                cols_data = ["Data de Alteração", "registered", "FechaDeInicio_date", "FechaFin_date"]
                for col in cols_data:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                        df[col] = df[col].dt.strftime('%d/%m/%Y').fillna("")
                # Salva Excel
                self.log("Solicitando local para salvar...")

                caminho_salvar = filedialog.asksaveasfilename(
                    defaultextension=".xlsx",
                    initialfile=arquivo_final,
                    title="Salvar Histórico Aconex Como",
                    filetypes=[("Excel Files", "*.xlsx")]
                )
                if caminho_salvar:
                    self.salvar_excel_customizado(df, caminho_salvar)
                    self.log(f"CONCLUÍDO! Arquivo salvo em: {caminho_salvar}")
                    messagebox.showinfo("Sucesso", f"Extração Concluída!\nSalvo em: {caminho_salvar}")

                    # Tenta abrir a pasta/arquivo
                    try: os.startfile(caminho_salvar)
                    except: pass
                else:
                    self.log("Salvamento cancelado pelo usuário (arquivo perdido da memória).")
            else:
                self.log("Nenhum dado extraído.")
                messagebox.showwarning("Aviso", "Nenhum dado retornado pela API.")
        except Exception as e:
            self.log(f"ERRO CRÍTICO NO SCRIPT: {e}")
            messagebox.showerror("Erro", str(e))

        finally:
            self.progress.stop()
            self.progress.set(1)
            self.btn_run.configure(state="normal", text="INICIAR EXTRAÇÃO TOTAL")
    def salvar_excel_customizado(self, df, nome_arquivo):
        self.log(f"Aplicando formatação visual (XlsxWriter)...")
        try:
            writer = pd.ExcelWriter(nome_arquivo, engine='xlsxwriter')
            df.to_excel(writer, index=False, sheet_name='Documentos')

            workbook = writer.book
            worksheet = writer.sheets['Documentos']

            formato_padrao = workbook.add_format({'text_wrap': True, 'valign': 'top'})
            formato_cabecalho = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'top', 'bottom': 1})

            larguras = {
                "No. do Documento": 26.27, "Controle do Emissor": 24.09, "Revisão": 10.18,
                "Data de Alteração": 19.18, "Status": 17, "Status da Revisão": 17,
                "Título": 76, "Current": 8.09, "Tipo do Documento": 23.27,
                "Tracking ID": 19.45, "Versão": 8.09, "Idioma": 13.55,
                "Especialidade": 30.09, "Subespecialidade": 34.45,
                "Tipo do Documento DCC": 23.67, "Subtipo DCC": 23.67,
                "Control CMI": 27, "Disciplina (Modelo)": 20, "Fonte": 20
            }
            for i, col_name in enumerate(df.columns):
                width = larguras.get(col_name, 20)
                worksheet.set_column(i, i, width, formato_padrao)
                worksheet.write(0, i, col_name, formato_cabecalho)
            worksheet.set_row(0, 15)
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

            writer.close()
        except Exception as e:
            self.log(f"Erro ao salvar Excel: {e}")
            # Fallback para pandas simples se xlsxwriter falhar
            df.to_excel(nome_arquivo, index=False)
# --- 10. Relatório de avanço
class ReportView(ctk.CTkFrame):
    def __init__(self, master, excel_handler, **kwargs):
        super().__init__(master, **kwargs)
        self.excel_handler = excel_handler
        self.data_manager = DataManager()

        # Variáveis (Base Aconex Global)
        self.path_aconex = None
        self.sheet_aconex = ctk.StringVar()

        self.setup_ui()
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1) # Ajustado para 5 devido ao Tabview
        self.label_title = ctk.CTkLabel(self, text="Módulo de Relatórios (Avanço & Integração)", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        # =========================================================
        # --- BASE ACONEX (GLOBAL PARA AS ABAS) ---
        # =========================================================
        self.frame_aconex = ctk.CTkFrame(self)
        self.frame_aconex.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(self.frame_aconex, text="Base Aconex (Extrato Bruto):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.btn_load_aconex = ctk.CTkButton(self.frame_aconex, text="Carregar Base", command=self.carregar_base_aconex_ui)
        self.btn_load_aconex.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.lbl_aconex_path = ctk.CTkLabel(self.frame_aconex, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_aconex_path.grid(row=0, column=2, padx=10, pady=10, sticky="w")
        ctk.CTkLabel(self.frame_aconex, text="Aba (Sheet):").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.opt_sheet = ctk.CTkOptionMenu(self.frame_aconex, variable=self.sheet_aconex, values=["Selecione arquivo"])
        self.opt_sheet.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        # =========================================================
        # --- TABVIEW (GERENCIADOR DE ABAS) ---
        # =========================================================
        self.tabview = ctk.CTkTabview(self, height=150)
        self.tabview.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.tab_avanco = self.tabview.add("Relatório de Avanço")
        self.tab_integracao = self.tabview.add("Auditoria de Integração")
        # Aba 1: Relatório de Avanço
        self.tab_avanco.grid_columnconfigure(0, weight=1)
        lbl_info_avanco = ctk.CTkLabel(self.tab_avanco, text="Gera o Relatório de Avanço Físico completo baseado no histórico do Aconex.\n(Calcula SLA, ciclo de aprovação, devoluções e emite a planilha matriz.)", justify="center", font=ctk.CTkFont(size=14))
        lbl_info_avanco.pack(pady=20)
        # Aba 2: Auditoria de Integração
        self.tab_integracao.grid_columnconfigure(0, weight=1)
        lbl_info_integ = ctk.CTkLabel(self.tab_integracao, text="Analisa o fluxo de integração (Status das Revisões 0AA e 0A)\npara todos os documentos com DCC válido em vigência (Current=True).", justify="center", font=ctk.CTkFont(size=14))
        lbl_info_integ.pack(pady=(15, 5))

        texto_dccs = "DCCs Analisados: LB010, LB020, LC030, LC040, LC060, LC061, LC070, LD010, LD020,\nLD040, LD050, LD051, LH011, LU010, DC070, DC075, CC051, EC020, BD010,\nBD011, BD012, BD013, BD014, BD015, BD016, BS020, BS110."
        lbl_dccs = ctk.CTkLabel(self.tab_integracao, text=texto_dccs, justify="center", font=ctk.CTkFont(size=11, slant="italic"), text_color="gray")
        lbl_dccs.pack(pady=(0, 15))
        # =========================================================
        # --- COMPONENTES GERAIS (AÇÃO E LOGS) ---
        # =========================================================
        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=3, column=0, padx=20, pady=(15, 0), sticky="ew")
        self.progress.set(0)
        self.btn_process = ctk.CTkButton(self, text="Gerar Relatório Selecionado", command=self.processar, height=40, fg_color="green", hover_color="darkgreen")
        self.btn_process.grid(row=4, column=0, padx=20, pady=15, sticky="ew")
        self.textbox_log = ctk.CTkTextbox(self)
        self.textbox_log.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="nsew")
    def log(self, msg):
        self.textbox_log.insert("end", msg + "\n")
        self.textbox_log.see("end")
    def carregar_base_aconex_ui(self):
        path = self.excel_handler.selecionar_arquivo("aconex")
        if path:
            self.path_aconex = path
            self.lbl_aconex_path.configure(text=os.path.basename(path), text_color="white")
            abas = self.excel_handler.listar_abas(path)

            self.opt_sheet.configure(values=abas)
            if "Documentos" in abas: 
                self.sheet_aconex.set("Documentos")
            elif abas: 
                self.sheet_aconex.set(abas[0])

            self.log("Carregando base Aconex na memória... Aguarde.")
            self.update_idletasks()

            # Carrega a base dinamicamente para o self.data_manager.df_aconex
            sucesso, msg = self.data_manager.carregar_aconex(self.path_aconex, self.sheet_aconex.get())

            if sucesso:
                self.log("✅ Base Aconex carregada com sucesso!")
            else:
                self.log(msg)
                messagebox.showerror("Erro", msg)
    def processar(self):
        aba_ativa = self.tabview.get()

        # Verificação rígida da Base Aconex global
        if not self.path_aconex or self.data_manager.df_aconex is None:
            messagebox.showwarning("Aviso", "Por favor, carregue a Base Aconex no botão superior antes de gerar o relatório.")
            return
        self.btn_process.configure(state="disabled")
        self.progress.set(0)
        self.log(f"--- INICIANDO: {aba_ativa.upper()} ---")
        self.update_idletasks()
        def update_prog(msg, val):
            self.log(msg)
            self.progress.set(val)
            self.update_idletasks()
        sucesso = False
        df_resultado = None
        nome_padrao_arquivo = ""
        titulo_salvamento = ""
        try:
            if aba_ativa == "Relatório de Avanço":
                # Executa a função clássica do avanço
                sucesso, df_resultado = self.data_manager.gerar_relatorio_avanco(
                    self.path_aconex, 
                    self.sheet_aconex.get(),
                    update_prog
                )
                nome_padrao_arquivo = f"Relatorio_Avanco_{datetime.now().strftime('%d%m%y')}.xlsx"
                titulo_salvamento = "Salvar Relatório de Avanço"

            elif aba_ativa == "Auditoria de Integração":
                # Executa a nova função do DCC
                update_prog("Auditando fluxo de integração (DCCs e histórico)...", 0.5)
                df_resultado = self.data_manager.auditar_fluxo_integracao(self.data_manager.df_aconex)

                if df_resultado is not None and not df_resultado.empty:
                    sucesso = True
                    update_prog("Auditoria concluída com sucesso.", 1.0)
                else:
                    sucesso = False
                    df_resultado = "Nenhum documento encontrado nos critérios ou erro na geração."

                nome_padrao_arquivo = f"Auditoria_Integracao_{datetime.now().strftime('%d%m%y')}.xlsx"
                titulo_salvamento = "Salvar Auditoria de Integração"
            # -------------------------------------------------
            # ROTINA DE SALVAMENTO DE ACORDO COM O RELATÓRIO
            # -------------------------------------------------
            if sucesso and df_resultado is not None:
                self.log("Dados processados. Selecione o local para salvar...")

                path_save = filedialog.asksaveasfilename(
                    defaultextension=".xlsx",
                    initialfile=nome_padrao_arquivo,
                    title=titulo_salvamento,
                    filetypes=[("Excel Files", "*.xlsx")]
                )
                if path_save:
                    if aba_ativa == "Relatório de Avanço":
                        # Mantém a sua formatação customizada original
                        self.salvar_excel_formatado(df_resultado, path_save)
                    else:
                        # Salva Auditoria de Integração com formatação visual limpa e filtros
                        self.salvar_excel_integracao_formatado(df_resultado, path_save)

                    self.log(f"✅ Salvo em: {path_save}")
                    messagebox.showinfo("Sucesso", f"{aba_ativa} Gerado com Sucesso!")
                    try: os.startfile(path_save)
                    except: pass
                else:
                    self.log("Salvamento cancelado.")
            else:
                self.log(f"Falha ou base vazia: {df_resultado}")
        except Exception as e:
            self.log(f"Erro crítico durante o processo: {e}")
            messagebox.showerror("Erro Crítico", str(e))

        finally:
            self.btn_process.configure(state="normal")
    def salvar_excel_formatado(self, df, path):
        # Usa xlsxwriter para formatar
        writer = pd.ExcelWriter(path, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Relatorio')

        workbook = writer.book
        worksheet = writer.sheets['Relatorio']

        # --- ESTILOS (CALIBRI 9) ---
        estilo_base = {
            'font_name': 'Calibri',
            'font_size': 9,
            'valign': 'top'
        }

        # Estilo Cabeçalho: Negrito, Borda inferior
        fmt_header = workbook.add_format({**estilo_base, 'bold': True, 'bottom': 1, 'text_wrap': True})

        # Estilo Corpo: Texto normal
        fmt_body = workbook.add_format({**estilo_base, 'text_wrap': True})

        # --- LARGURAS ---
        larguras = {
            'No. do Documento': 23.29,
            'Controle do Emissor': 24,
            'Título': 97.86,
            'Tipo do Documento': 12.29,
            'Revisão': 6.71,
            'Status': 13.86,
            'Data de Alteração': 12,
            "Status da Revisão": 13.86,
            'Fonte da revisão': 17.43,
            'Empresa': 8,
            'Data Devolução': 12
        }
        for i, col in enumerate(df.columns):
            width = larguras.get(col, 20)

            # Esconder coluna Controle do Emissor (Opção 'hidden': True)
            options = {'hidden': True} if col == 'Controle do Emissor' else {}

            # Aplica largura e formato do corpo na coluna inteira
            worksheet.set_column(i, i, width, fmt_body, options)

            # Sobrescreve o cabeçalho com o formato de cabeçalho
            worksheet.write(0, i, col, fmt_header)

        # Filtros e Congelamento
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
        worksheet.freeze_panes(1, 0)

        writer.close()
    def salvar_excel_integracao_formatado(self, df, path):
        # Usa xlsxwriter para formatar (idêntico ao padrão, mas com larguras ajustadas)
        writer = pd.ExcelWriter(path, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Auditoria_Integracao')

        workbook = writer.book
        worksheet = writer.sheets['Auditoria_Integracao']

        # --- ESTILOS (CALIBRI 9) ---
        estilo_base = {
            'font_name': 'Calibri',
            'font_size': 9,
            'valign': 'top'
        }

        # Estilo Cabeçalho (Fundo Azul, Letras Brancas em Negrito)
        fmt_header = workbook.add_format({
            **estilo_base, 
            'bold': True, 
            'bottom': 1, 
            'text_wrap': True,
            'bg_color': '#4F81BD',
            'font_color': 'white'
        })

        # Estilo Corpo
        fmt_body = workbook.add_format({**estilo_base, 'text_wrap': True})

        # --- LARGURAS ESPECÍFICAS (Nomes Amigáveis) ---
        larguras = {
            'No. do Documento': 28,
            'Controle do Emissor': 28,
            'Título': 65,
            'Integração': 15,
            'Data Envio 0AA': 18,
            'Status Envio 0AA': 22,
            'Data Retorno 0AA': 18,
            'Status Retorno 0AA': 22,
            'Data Envio 0A': 18,
            'Status Envio 0A': 22,
            'Data Retorno 0A': 18,
            'Status Retorno 0A': 22
        }
        # Aplica a formatação coluna por coluna
        for i, col in enumerate(df.columns):
            width = larguras.get(col, 20) # 20 é o padrão se a coluna não estiver no dicionário

            # Aplica largura e formato do corpo
            worksheet.set_column(i, i, width, fmt_body)

            # Sobrescreve a linha 0 (cabeçalho) com o formato bold
            worksheet.write(0, i, col, fmt_header)

        # Filtros e Congelamento de painel
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
        worksheet.freeze_panes(1, 0)

        writer.close()
# --- 11. Dashboard
class DashboardView(ctk.CTkFrame):
    def __init__(self, master, excel_handler, **kwargs):
        super().__init__(master, **kwargs)

        # Instância local e handlers
        self.data_manager = DataManager()
        self.excel_handler = excel_handler

        # Variáveis de controle
        self.server_thread = None
        self.server_running = False
        self.caminho_arquivo_atual = None
        self.setup_ui()
    def setup_ui(self):
        # Configuração do Grid Principal (Igual ao StatusCheckView)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) # O Log (linha 3) vai expandir
        # --- TÍTULO ---
        self.label_title = ctk.CTkLabel(
            self, 
            text="Painel do Dashboard (BI) e Relatórios", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        # --- SEÇÃO 1: FONTE DE DADOS ---
        self.frame_data = ctk.CTkFrame(self)
        self.frame_data.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        # Layout interno do frame de dados
        ctk.CTkLabel(self.frame_data, text="1. Fonte de Dados (Base Aconex):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.btn_load = ctk.CTkButton(
            self.frame_data, 
            text="Selecionar Arquivo .xlsx", 
            command=self.carregar_base_aconex,
            width=150
        )
        self.btn_load.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.lbl_arquivo = ctk.CTkLabel(self.frame_data, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_arquivo.grid(row=0, column=2, padx=10, pady=10, sticky="w")
        # --- SEÇÃO 2: OPERAÇÕES (RELATÓRIO E DASHBOARD) ---
        self.frame_ops = ctk.CTkFrame(self)
        self.frame_ops.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.frame_ops.grid_columnconfigure(1, weight=1) # Espaça as colunas
        # Coluna Esquerda: Excel
        self.frame_excel_area = ctk.CTkFrame(self.frame_ops, fg_color="transparent")
        self.frame_excel_area.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(self.frame_excel_area, text="2. Relatórios Estáticos", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,5))

        self.btn_export = ctk.CTkButton(
            self.frame_excel_area, 
            text="Gerar Histórico Formatado (.xlsx) 📥", 
            command=self.gerar_excel_historico,
            fg_color="#E59400", hover_color="#B87700",
            state="disabled",
            width=250,
            height=35
        )
        self.btn_export.pack(anchor="w", pady=5)
        ctk.CTkLabel(self.frame_excel_area, text="Gera planilha com histórico linear", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
        # Coluna Direita: Dashboard
        self.frame_dash_area = ctk.CTkFrame(self.frame_ops, fg_color="transparent")
        self.frame_dash_area.grid(row=0, column=1, padx=20, pady=10, sticky="nsew")

        ctk.CTkLabel(self.frame_dash_area, text="3. Dashboard Interativo", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0,5))

        self.btn_launch = ctk.CTkButton(
            self.frame_dash_area, 
            text="Iniciar Dashboard no Navegador 🚀", 
            command=self.abrir_dashboard_web,
            fg_color="#2CC985", hover_color="#00A36C",
            state="disabled",
            width=250,
            height=35
        )
        self.btn_launch.pack(anchor="w", pady=5)

        self.lbl_status_dash = ctk.CTkLabel(self.frame_dash_area, text="Status: Servidor Parado", text_color="#FF474C", font=ctk.CTkFont(size=11, weight="bold"))
        self.lbl_status_dash.pack(anchor="w")
        # --- SEÇÃO 3: LOG DE EXECUÇÃO (Igual ao StatusCheck) ---
        self.textbox_log = ctk.CTkTextbox(self)
        self.textbox_log.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="nsew")

        self.log("Sistema pronto. Carregue a base de dados para iniciar.")
    # -------------------------------------------------------------------------
    # FUNÇÕES AUXILIARES
    # -------------------------------------------------------------------------
    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.textbox_log.insert("end", f"[{timestamp}] {msg}\n")
        self.textbox_log.see("end")
    # -------------------------------------------------------------------------
    # FUNÇÕES LÓGICAS
    # -------------------------------------------------------------------------
    def carregar_base_aconex(self):
        self.log("Solicitando arquivo Aconex...")
        caminho = self.excel_handler.selecionar_arquivo("aconex")

        if not caminho: 
            self.log("Seleção de arquivo cancelada.")
            return
        self.btn_load.configure(state="disabled", text="Lendo...")
        self.update_idletasks()
        # Tenta carregar
        abas = self.excel_handler.listar_abas(caminho)
        aba_alvo = "Documentos" if "Documentos" in abas else abas[0]

        self.log(f"Carregando arquivo: {os.path.basename(caminho)} (Aba: {aba_alvo})...")
        sucesso, msg = self.data_manager.carregar_aconex(caminho, aba_alvo)
        if sucesso:
            self.caminho_arquivo_atual = caminho
            self.lbl_arquivo.configure(text=os.path.basename(caminho), text_color="#2CC985")
            self.btn_export.configure(state="normal")
            self.btn_launch.configure(state="normal")
            self.log("Base de dados carregada com sucesso na memória.")
        else:
            self.lbl_arquivo.configure(text="Erro no arquivo", text_color="#FF474C")
            self.log(f"ERRO: {msg}")
            messagebox.showerror("Erro", msg)
        self.btn_load.configure(state="normal", text="Carregar Arquivo .xlsx")
    def gerar_excel_historico(self):
        if self.data_manager.df_aconex is None: return
        path_salvar = self.excel_handler.salvar_arquivo(
            default_name="Historico_Consolidado_IB.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx")]
        )
        if not path_salvar: return
        self.btn_export.configure(state="disabled", text="Processando...")
        self.log("Iniciando geração de relatório Excel...")
        self.update_idletasks()
        try:
            self.log("1/2 Limpando e organizando dados...")
            df_limpo = self.data_manager.gerar_dataset_dashboard(self.data_manager.df_aconex)

            self.log("2/2 Formatando e salvando arquivo...")
            sucesso, msg = self.data_manager.gerar_excel_historico_formatado(df_limpo, path_salvar)
            if sucesso:
                self.log(f"Sucesso! Arquivo salvo em: {path_salvar}")
                messagebox.showinfo("Sucesso", msg)
                try: os.startfile(path_salvar)
                except: pass
            else:
                self.log(f"Erro ao salvar: {msg}")
                messagebox.showerror("Erro", msg)
        except Exception as e:
            self.log(f"ERRO CRÍTICO: {e}")
            messagebox.showerror("Erro Crítico", f"Falha: {e}")
        self.btn_export.configure(state="normal", text="Gerar Histórico Formatado (.xlsx) 📥")
    def abrir_dashboard_web(self):
        if self.data_manager.df_aconex is None: return
        self.btn_launch.configure(state="disabled", text="Iniciando...")
        self.log("Preparando dados para o Dashboard...")
        self.update_idletasks()
        try:
            # Prepara dados
            df_limpo = self.data_manager.gerar_dataset_dashboard(self.data_manager.df_aconex)
            df_wide = self.data_manager.preparar_tabela_wide(df_limpo)
            if df_wide.empty:
                self.log("Aviso: Base vazia após processamento.")
                messagebox.showwarning("Aviso", "A base de dados gerou uma tabela vazia.")
                self.btn_launch.configure(state="normal", text="Iniciar Dashboard no Navegador 🚀")
                return
            self.log(f"Dados processados. {len(df_wide)} revisões enviadas para o motor gráfico.")
            # Injeta dados
            dash_ib.df_wide_global = df_wide
            dash_ib.app.layout = dash_ib.create_layout(df_wide)
            # Inicia thread
            if not self.server_running:
                self.run_dash_thread()
            else:
                self.log("Dados atualizados no Dashboard. Recarregue a página no navegador.")
                webbrowser.open("http://127.0.0.1:8050/")
                self.btn_launch.configure(state="normal", text="Reabrir Navegador")
        except Exception as e:
            self.log(f"ERRO DASH: {e}")
            messagebox.showerror("Erro Dash", f"Não foi possível iniciar o Dashboard:\n{e}")
            self.btn_launch.configure(state="normal", text="Iniciar Dashboard no Navegador 🚀")
    def run_dash_thread(self):
        def thread_target():
            try:
                # use_reloader=False é OBRIGATÓRIO
                dash_ib.app.run(debug=True, port=8050, use_reloader=False)
            except Exception as e:
                print(f"Erro Thread Dash: {e}")
        self.server_thread = threading.Thread(target=thread_target, daemon=True)
        self.server_thread.start()

        self.server_running = True
        self.lbl_status_dash.configure(text="Status: Rodando (Porta 8050)", text_color="#2CC985")
        self.btn_launch.configure(state="normal", text="Reabrir Navegador")
        self.log("Servidor Dash iniciado com sucesso em http://127.0.0.1:8050/")

        webbrowser.open("http://127.0.0.1:8050/")
# --- 12. Corella vs Aconex
class CorellaView(ctk.CTkFrame):
    def __init__(self, master, excel_handler, **kwargs):
        super().__init__(master, **kwargs)
        self.excel_handler = excel_handler
        self.data_manager = DataManager()

        self.path_corella = None
        self.path_aconex = None

        self.sheet_aconex = ctk.StringVar()
        self.setup_ui()
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        # Título
        self.label_title = ctk.CTkLabel(self, text="Verificação Corella vs Aconex", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        # --- CONTAINER DE ARQUIVOS (LAYOUT MELHORADO) ---
        self.frame_files = ctk.CTkFrame(self)
        self.frame_files.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.frame_files.grid_columnconfigure(1, weight=0) # Labels fixas
        self.frame_files.grid_columnconfigure(2, weight=1) # Nome do arquivo estica
        # LINHA 1: Corella
        ctk.CTkLabel(self.frame_files, text="1. Arquivo Corella:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.btn_corella = ctk.CTkButton(self.frame_files, text="Selecionar", command=self.select_corella, width=100, fg_color="#E67E22", hover_color="#D35400")
        self.btn_corella.grid(row=0, column=1, padx=5, pady=10, sticky="w")

        self.lbl_corella = ctk.CTkLabel(self.frame_files, text="Nenhum arquivo", text_color="gray")
        self.lbl_corella.grid(row=0, column=2, padx=10, sticky="w")
        # LINHA 2: Aconex
        ctk.CTkLabel(self.frame_files, text="2. Aconex (Excel):", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.btn_aconex = ctk.CTkButton(self.frame_files, text="Selecionar", command=self.select_aconex, width=100, fg_color="#2980B9", hover_color="#2471A3")
        self.btn_aconex.grid(row=1, column=1, padx=5, pady=10, sticky="w")

        # Frame interno para Nome + Aba ficarem na mesma linha sem quebrar
        self.subframe_aconex = ctk.CTkFrame(self.frame_files, fg_color="transparent")
        self.subframe_aconex.grid(row=1, column=2, sticky="w", padx=5)

        self.lbl_aconex = ctk.CTkLabel(self.subframe_aconex, text="Nenhum arquivo", text_color="gray")
        self.lbl_aconex.pack(side="left", padx=(5, 15))

        ctk.CTkLabel(self.subframe_aconex, text="Aba:").pack(side="left")
        self.opt_sheet_aconex = ctk.CTkOptionMenu(self.subframe_aconex, variable=self.sheet_aconex, values=["-"], width=150)
        self.opt_sheet_aconex.pack(side="left", padx=5)
        # --- FILTROS ---
        self.frame_filter = ctk.CTkFrame(self)
        self.frame_filter.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        ctk.CTkLabel(self.frame_filter, text="Filtro de Códigos (HNS/KKS):").grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        self.entry_filter = ctk.CTkEntry(self.frame_filter, placeholder_text="Ex: CBA, MEU, GBV", width=300)
        self.entry_filter.grid(row=0, column=1, padx=10, pady=(10, 5), sticky="w")
        # NOVO CAMPO: Textbox multilinhas com altura reduzida (height=60) para barra de rolagem
        ctk.CTkLabel(self.frame_filter, text="Lista Exata (Cole do Excel):").grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nw")
        self.textbox_docs = ctk.CTkTextbox(self.frame_filter, width=300, height=60)
        self.textbox_docs.grid(row=1, column=1, padx=10, pady=(5, 10), sticky="w")
        # --- AÇÕES ---
        self.frame_actions = ctk.CTkFrame(self)
        self.frame_actions.grid(row=3, column=0, padx=20, pady=20, sticky="ew")

        self.btn_task1 = ctk.CTkButton(self.frame_actions, text="🔍 Task 1: Documentos Faltantes no Corella", command=self.run_missing, state="disabled", height=40, fg_color="#C0392B", hover_color="#A93226")
        self.btn_task1.pack(side="left", padx=20, pady=10, expand=True, fill="x")
        self.btn_task2 = ctk.CTkButton(self.frame_actions, text="📊 Task 2: Comparar Versões (Divergências)", command=self.run_versions, state="disabled", height=40, fg_color="#27AE60", hover_color="#229954")
        self.btn_task2.pack(side="right", padx=20, pady=10, expand=True, fill="x")
        # --- LOG ---
        self.textbox_log = ctk.CTkTextbox(self)
        self.textbox_log.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log("Sistema pronto. Selecione os arquivos.")
    def log(self, msg):
        self.textbox_log.insert("end", f"> {msg}\n")
        self.textbox_log.see("end")
    def check_ready(self):
        if self.path_corella and self.path_aconex:
            self.btn_task1.configure(state="normal")
            self.btn_task2.configure(state="normal")
        else:
            self.btn_task1.configure(state="disabled")
            self.btn_task2.configure(state="disabled")
    def select_corella(self):
        path = filedialog.askopenfilename(filetypes=[("Corella", "*.xls *.xml *.xlsx")])
        if path:
            self.path_corella = path
            self.lbl_corella.configure(text=os.path.basename(path), text_color="white")
            self.log(f"Corella selecionado: {path}")
            self.check_ready()
    def select_aconex(self):
        path = self.excel_handler.selecionar_arquivo("aconex") 
        if path:
            self.path_aconex = path
            self.lbl_aconex.configure(text=os.path.basename(path), text_color="white")
            self.log(f"Aconex selecionado: {path}")

            # Carrega as abas e seleciona 'Documentos' se existir
            abas = self.excel_handler.listar_abas(path)
            self.opt_sheet_aconex.configure(values=abas)

            if "Documentos" in abas: 
                self.sheet_aconex.set("Documentos")
            elif abas: 
                self.sheet_aconex.set(abas[0])

            self.check_ready()
    # --- LÓGICA DE SALVAMENTO (LOCAL) ---
    def _salvar_excel_formatado(self, df, colunas, filename, sheet_name="Resultados"):
        try:
            cols_reais = [c for c in colunas if c in df.columns]
            if not cols_reais: cols_reais = df.columns

            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df[cols_reais].to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]

                cor_cabecalho = PatternFill(start_color="DDD9C4", end_color="DDD9C4", fill_type="solid")
                alinhamento_wrap = Alignment(wrap_text=True, vertical='center', horizontal='left')

                # MUDANÇA: ADICIONADAS AS COLUNAS EM PORTUGUÊS DA API
                REGRAS_LARGURA = {
                    'Título': 100, 'Titulo': 100,
                    'Control del Emisor': 30, 'Controle do Emissor': 30, # PT-BR
                    'Revisão': 15, 'Revision': 15, 'Versão ': 15,
                    'Qtd_rev_corella': 15, 'Qtd_Versoes_Aconex': 15, 'Ultima_Revisao_Aconex': 15,
                    'Status': 25, 'State': 25,
                    'Especialidad': 30, 'Especialidade': 30,         # PT-BR
                    'Subespecialidad': 45, 'Subespecialidade': 45,   # PT-BR
                    'Diferenca': 12, 'Originator [...]': 20
                }
                LARGURA_PADRAO = 25

                for column in worksheet.columns:
                    col_header = column[0].value
                    col_letter = column[0].column_letter
                    largura = REGRAS_LARGURA.get(col_header, LARGURA_PADRAO)
                    worksheet.column_dimensions[col_letter].width = largura
                    for cell in column:
                        cell.alignment = alinhamento_wrap
                        if cell.row == 1:
                            cell.fill = cor_cabecalho
                            cell.font = Font(bold=True)

                worksheet.row_dimensions[1].height = 18
                for row in worksheet.iter_rows(min_row=2):
                    worksheet.row_dimensions[row[0].row].height = 30
                worksheet.auto_filter.ref = worksheet.dimensions

            return True
        except Exception as e:
            self.log(f"Erro ao salvar Excel: {e}")
            return False
    # --- EXECUÇÃO DAS TASKS ---
    def run_missing(self):
        self.log("--- Iniciando Task 1 (Faltantes) ---")

        # 1. Leitura (Backend) - MUDANÇA: Nome da função atualizado
        self.log("Lendo arquivos...")
        df_aconex, err_a = self.data_manager.ler_aconex_api_fiel(self.path_aconex, self.sheet_aconex.get())
        df_corella, err_c = self.data_manager.ler_arquivo_corella_fiel(self.path_corella)

        if err_a: 
            self.log(f"Erro Aconex: {err_a}"); return
        if err_c: 
            self.log(f"Erro Corella: {err_c}"); return
        # 2. Processamento (Backend)
        filtro_kks = self.entry_filter.get()
        # Captura todo o texto colado da linha 1, coluna 0 até o final (removendo a última quebra de linha default do Tkinter)
        filtro_exato = self.textbox_docs.get("1.0", "end-1c") 

        # Chama passando os dois filtros
        df_missing = self.data_manager.comparar_missing_docs_api(df_aconex, df_corella, filtro_kks, filtro_exato)
        if df_missing.empty:
            self.log("Resultado: Nenhum documento faltante encontrado.")
            messagebox.showinfo("Sucesso", "Tudo sincronizado! Nada faltando.")
        else:
            self.log(f"Resultado: {len(df_missing)} documentos faltando no Corella.")
            save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", title="Salvar Relatório Faltantes")
            if save_path:
                # 3. Salvamento - MUDANÇA: Colunas em PORTUGUÊS (API)
                cols = ['Controle do Emissor', 'Título', 'Especialidade', 'Subespecialidade', 'Revisão', 'Status']
                sucesso = self._salvar_excel_formatado(df_missing, cols, save_path, "Faltantes")

                if sucesso:
                    self.log(f"Relatório salvo: {save_path}")
                    try: os.startfile(save_path)
                    except: pass
    def run_versions(self):
        self.log("--- Iniciando Task 2 (Versões) ---")

        # 1. Leitura - MUDANÇA: Nome da função atualizado
        self.log("Lendo arquivos...")
        df_aconex, err_a = self.data_manager.ler_aconex_api_fiel(self.path_aconex, self.sheet_aconex.get())
        df_corella, err_c = self.data_manager.ler_arquivo_corella_fiel(self.path_corella)

        if err_a: 
            self.log(f"Erro Aconex: {err_a}"); return
        if err_c: 
            self.log(f"Erro Corella: {err_c}"); return
        # 2. Processamento (Backend)
        filtro_kks = self.entry_filter.get()
        filtro_exato = self.textbox_docs.get("1.0", "end-1c")

        # Chama passando os dois filtros
        df_diff = self.data_manager.comparar_versoes_tracking_id(df_aconex, df_corella, filtro_kks, filtro_exato)
        if df_diff.empty:
            self.log("Resultado: Nenhuma divergência de versão encontrada.")
            messagebox.showinfo("Sucesso", "Versões sincronizadas.")
        else:
            self.log(f"Resultado: {len(df_diff)} documentos com divergência de versão.")
            save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", title="Salvar Relatório Divergências")
            if save_path:
                # 3. Salvamento - MUDANÇA: Colunas em PORTUGUÊS (API)
                cols = [
                    'Controle do Emissor', 'Título', 'Especialidade', 'Subespecialidade',
                    'Revisão', 'Qtd_Versoes_Aconex', 
                    'Revision', 'Qtd_rev_corella', 'Diferenca', 'State', 'Originator [...]'
                ]
                sucesso = self._salvar_excel_formatado(df_diff, cols, save_path, "Divergencias")

                if sucesso:
                    self.log(f"Relatório salvo: {save_path}")
                    try: os.startfile(save_path)
                    except: pass
# --- 13. Kaizen Atualização dos mapas para o C&C
class KaizenView(ctk.CTkFrame):
    def __init__(self, master, excel_handler, data_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.excel_handler = excel_handler
        self.data_manager = data_manager # Recebemos a mesma instância de dados

        # Variáveis de Caminho e Abas
        self.path_mae = None # Mapeamento Original
        self.path_filha = None # Kaizen Antigo
        self.path_aconex = None # Aconex (Tracking ID)
        self.path_p6 = None # Primavera P6 (Opcional)
        self.path_backlog = None # NOVO: Backlog

        self.sheet_mae = ctk.StringVar()
        self.sheet_filha = ctk.StringVar()
        self.sheet_aconex = ctk.StringVar()
        self.sheet_p6 = ctk.StringVar()
        self.sheet_backlog = ctk.StringVar() # NOVO: Backlog

        self.row_header_mae = 1
        self.row_header_filha = 1
        # --- DICIONÁRIO DAS 8 NOVAS COLUNAS KAIZEN ---
        self.colunas_novas_kaizen = [
            "ID P6", 
            "FINISH DATE", 
            "SITE NEEDED DATE", 
            "VARIANCE", 
            "ACCOUNTABLE", 
            "RESPONSIBLE", 
            "SERVIÇO DE PLANILHA SUBCONTRATADO DO FORNECEDOR?", 
            "PROTOCOLOS DE MONTAGEM (ALINHADOS C/ CRONOGRAMA NEEDED DATE)"
        ]
        # --- LAYOUT E INTERFACE ---
        self.grid_columnconfigure(0, weight=1)

        # PROÍBE explicitamente as linhas superiores de ganharem espaço em branco
        self.grid_rowconfigure((0, 1, 2, 3), weight=0) 
        self.grid_rowconfigure(4, weight=1) # SÓ a linha 4 (Log) estica

        self.label_title = ctk.CTkLabel(self, text="Sincronizador Kaizen (Reconstrução Automática)", font=ctk.CTkFont(size=20, weight="bold"))
        self.label_title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        # --- CONTAINER INVISÍVEL PARA COLUNAS DUPLAS ---
        # sticky="new" força a colar no topo, puxando o grid para cima
        self.frame_arquivos = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_arquivos.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="new")

        self.frame_arquivos.grid_columnconfigure(0, weight=1, uniform="col")
        self.frame_arquivos.grid_columnconfigure(1, weight=1, uniform="col")
        # Fundo mais escuro que a base do app para dar contraste, mantendo bordas arredondadas
        estilo_card = {"fg_color": ("#D4D4D4", "#1A1A1A"), "corner_radius": 8}
        # --- OS 5 CARDS DE FUNDO ---
        # 1. Mapeamento Original (Esquerda)
        self.frame_mae = ctk.CTkFrame(self.frame_arquivos, **estilo_card)
        self.frame_mae.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="new") # Mudado para "new"
        self.criar_componentes_arquivo(self.frame_mae, "1. Mapeamento Oficial", self.selecionar_mae, "path_mae", "sheet_mae", "opt_sheet_mae")
        # 2. Kaizen Antigo (Esquerda)
        self.frame_filha = ctk.CTkFrame(self.frame_arquivos, **estilo_card)
        self.frame_filha.grid(row=1, column=0, padx=(0, 10), pady=10, sticky="new") # Mudado para "new"
        self.criar_componentes_arquivo(self.frame_filha, "2. Planilha Kaizen", self.selecionar_filha, "path_filha", "sheet_filha", "opt_sheet_filha")
        # 3. Aconex Histórico (Esquerda)
        self.frame_aconex = ctk.CTkFrame(self.frame_arquivos, **estilo_card)
        self.frame_aconex.grid(row=2, column=0, padx=(0, 10), pady=10, sticky="new") # Mudado para "new"
        self.criar_componentes_arquivo(self.frame_aconex, "3. Base Aconex (Histórico)", self.selecionar_aconex, "path_aconex", "sheet_aconex", "opt_sheet_aconex")
        # 4. Planilha Primavera P6 (Direita)
        self.frame_p6 = ctk.CTkFrame(self.frame_arquivos, **estilo_card)
        self.frame_p6.grid(row=0, column=1, padx=(10, 0), pady=10, sticky="new") # Mudado para "new"
        self.criar_componentes_arquivo(self.frame_p6, "4. Extração P6 (Datas Nível 1 e 2)", self.selecionar_p6, "path_p6", "sheet_p6", "opt_sheet_p6")
        # 5. Planilha Backlog (Direita)
        self.frame_backlog = ctk.CTkFrame(self.frame_arquivos, **estilo_card)
        self.frame_backlog.grid(row=1, column=1, padx=(10, 0), pady=10, sticky="new") # Mudado para "new"
        self.criar_componentes_arquivo(self.frame_backlog, "5. Backlog (Planilhas e Protocolos)", self.selecionar_backlog, "path_backlog", "sheet_backlog", "opt_sheet_backlog")
        # (O bloco do Card Vazio 6 foi totalmente removido para evitar margens fantasmas)
        # Progresso e Botões puxados logo para baixo dos cards (Linhas 2 e 3)
        # pady=(0, 5) remove o buraco branco acima da barra de progresso
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=2, column=0, padx=20, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0)
        self.btn_executar = ctk.CTkButton(self, text="Iniciar Mapeamento Kaizen", command=self.iniciar_sincronismo, height=40, fg_color="green", hover_color="darkgreen")
        self.btn_executar.grid(row=3, column=0, padx=20, pady=(5, 10), sticky="ew")
        # Log (Agora na linha 4, expandindo por todo o resto da tela)
        # O pady top de 0 garante que o log suba imediatamente após o botão
        self.textbox_log = ctk.CTkTextbox(self)
        self.textbox_log.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.log("Módulo Kaizen Inicializado. Selecione os arquivos para começar.")
    # --- FUNÇÕES DE INTERFACE ---
    def log(self, mensagem):
        self.textbox_log.insert("end", mensagem + "\n")
        self.textbox_log.see("end")
    def criar_componentes_arquivo(self, frame, titulo, comando_selecao, var_path_name, var_sheet_name, var_opt_name):
        # Coluna do botão mais ajustada para evitar card inchado
        frame.grid_columnconfigure(0, minsize=150)
        frame.grid_columnconfigure(1, weight=1)

        # Título do Card - Restaurado para a fonte padrão CTk (menor)
        lbl = ctk.CTkLabel(frame, text=titulo, font=ctk.CTkFont(weight="bold"))
        lbl.grid(row=0, column=0, padx=10, pady=10, sticky="w", columnspan=2)

        # Botão - Largura original do seu modelo
        btn = ctk.CTkButton(frame, text="Selecionar Arquivo", command=comando_selecao, width=150)
        btn.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")

        # Caminho do Arquivo - Mantemos o wraplength por segurança, mas com paddings menores
        lbl_path = ctk.CTkLabel(frame, text="Nenhum arquivo selecionado", text_color="gray", wraplength=250, justify="left")
        lbl_path.grid(row=1, column=1, padx=10, pady=(0, 10), sticky="w")
        setattr(self, f"lbl_{var_path_name}", lbl_path) 

        # Rótulo Aba
        lbl_sheet = ctk.CTkLabel(frame, text="Aba (Sheet):")
        lbl_sheet.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")

        # Dropdown de Abas (dynamic_resizing=True e sticky="w" para não esticar forçado)
        opt_sheet = ctk.CTkOptionMenu(frame, variable=getattr(self, var_sheet_name), values=["Selecione o arquivo primeiro"], dynamic_resizing=True)
        opt_sheet.grid(row=2, column=1, padx=10, pady=(0, 10), sticky="w")
        setattr(self, var_opt_name, opt_sheet)
    def processar_selecao(self, tipo, path_var, lbl_var, sheet_var, opt_var):
        path = self.excel_handler.selecionar_arquivo(tipo)
        if path:
            setattr(self, path_var, path)

            # Idêntico à lógica do MappingView
            getattr(self, lbl_var).configure(text=os.path.basename(path), text_color="white")
            self.log(f"Carregado: {path}")

            abas = self.excel_handler.listar_abas(path)
            getattr(self, opt_var).configure(values=abas)

            # Se for aconex e tiver aba "Documentos", já seleciona ela
            if tipo == "aconex" and "Documentos" in abas:
                getattr(self, sheet_var).set("Documentos")
            elif abas: 
                getattr(self, sheet_var).set(abas[0])
    def selecionar_mae(self):
        self.processar_selecao("mapeamento_mae", "path_mae", "lbl_path_mae", "sheet_mae", "opt_sheet_mae")
    def selecionar_filha(self):
        self.processar_selecao("kaizen_filha", "path_filha", "lbl_path_filha", "sheet_filha", "opt_sheet_filha")
    def selecionar_aconex(self):
        self.processar_selecao("aconex", "path_aconex", "lbl_path_aconex", "sheet_aconex", "opt_sheet_aconex")
    def selecionar_p6(self):
        self.processar_selecao("primavera_p6", "path_p6", "lbl_path_p6", "sheet_p6", "opt_sheet_p6")

    def selecionar_backlog(self):
        self.processar_selecao("backlog", "path_backlog", "lbl_path_backlog", "sheet_backlog", "opt_sheet_backlog")
    def carregar_dicionario_backlog(self):
        """Lê o Backlog e cria um dicionário imutável amarrado ao Tracking ID do Aconex."""
        dicionario = {}
        if not self.path_backlog: return dicionario

        self.log("Lendo Planilha de Backlog...")
        self.update_idletasks()
        try:
            # 1. Acha cabeçalho
            df_temp = pd.read_excel(self.path_backlog, sheet_name=self.sheet_backlog.get(), nrows=15, header=None)
            header_idx = 0
            for i, row in df_temp.iterrows():
                valores_linha = [str(v).strip().upper() for v in row.values]
                if 'N° ITAIPU' in valores_linha:
                    header_idx = i
                    break

            df_backlog = pd.read_excel(self.path_backlog, sheet_name=self.sheet_backlog.get(), header=header_idx)

            # 2. Tratamento das colunas de Data que nos importam
            col_data_p6 = "DATA NECESSÁRIA (P6)"
            col_data_prevista = "DATA PREVISTA DE EMISSÃO"
            if col_data_p6 in df_backlog.columns:
                df_backlog[col_data_p6] = pd.to_datetime(df_backlog[col_data_p6], dayfirst=True, errors='coerce')
            if col_data_prevista in df_backlog.columns:
                df_backlog[col_data_prevista] = pd.to_datetime(df_backlog[col_data_prevista], dayfirst=True, errors='coerce')
            # 3. Monta o Dicionário
            for _, row in df_backlog.iterrows():
                c_itaipu = str(row.get("N° ITAIPU", "")).strip()
                if not c_itaipu or c_itaipu == "NAN": continue

                c_pred = str(row.get("PREDECESSOR", "")).strip()

                tracking_id = c_itaipu # Fallback caso não exista no histórico
                df_track = self.data_manager.localiza_doc_historico(c_itaipu, "")
                if not df_track.empty: tracking_id = df_track.iloc[0]['Tracking ID']

                dicionario[tracking_id] = {
                    "N° ITAIPU": c_itaipu,
                    "DESCRIÇÃO DO DOCUMENTO": str(row.get("DESCRIÇÃO DO DOCUMENTO", "")).strip(),
                    "STATUS ATUAL": str(row.get("STATUS ATUAL", "")).strip(),
                    "DATA NECESSÁRIA (P6)": row.get(col_data_p6, pd.NaT) if col_data_p6 in df_backlog.columns else pd.NaT,
                    "DATA PREVISTA DE EMISSÃO": row.get(col_data_prevista, pd.NaT) if col_data_prevista in df_backlog.columns else pd.NaT,
                    "PREDECESSOR": c_pred
                }
            self.log(f"Backlog: {len(dicionario)} itens lidos com sucesso.")
        except Exception as e:
            self.log(f"Aviso ao ler Backlog: {e}")

        return dicionario
    def find_headers(self, ws):
        """Encontra os cabeçalhos na planilha para sabermos as colunas exatas."""
        headers = {}
        for r in range(1, 10):
            found_any = False
            for cell in ws[r]:
                if cell.value:
                    headers[str(cell.value).strip()] = cell.column
                    found_any = True
            if found_any and 'N° ITAIPU' in headers:
                return headers, r
        return {}, 0
    def obter_cor_linha(self, grupo, nivel):
        """Retorna o código HEX da cor da linha baseada na regra de negócio."""
        nivel_str = str(nivel).strip()

        if nivel_str.endswith('.0'):
            nivel_str = nivel_str[:-2]

        if nivel_str == '1': return '808080'
        if nivel_str == '2': return 'BFBFBF'
        if nivel_str == '3': return 'D9D9D9'
        if nivel_str == '4': return 'F2F2F2'

        return 'FFFFFF' # Branco padrão
    def carregar_dicionario_p6(self):
        """Lê o extrato P6 com blindagem contra sujeira de dados, espaços e formatações americanas."""
        dicionario = {}
        if not self.path_p6:
            return dicionario

        import pandas as pd
        self.log("Lendo extração do Primavera P6...")
        self.update_idletasks()
        try:
            # 1. Encontrar o cabeçalho ignorando espaços em branco e letras minúsculas
            df_temp = pd.read_excel(self.path_p6, sheet_name=self.sheet_p6.get(), nrows=15, header=None)
            header_idx = 0
            for i, row in df_temp.iterrows():
                valores_linha = [str(v).strip().upper() for v in row.values]
                if 'ACTIVITY ID' in valores_linha:
                    header_idx = i
                    break

            # 2. Carrega a base e PADRONIZA as colunas
            df_p6 = pd.read_excel(self.path_p6, sheet_name=self.sheet_p6.get(), header=header_idx)
            df_p6.columns = df_p6.columns.astype(str).str.strip().str.upper()

            col_id = "ACTIVITY ID"
            col_finish = "FINISH"

            if col_id in df_p6.columns and col_finish in df_p6.columns:
                for _, row in df_p6.iterrows():
                    # Limpeza agressiva do ID
                    id_val = str(row.get(col_id, "")).strip().upper()

                    # Captura o valor bruto da data (Pode ser string ou já um objeto Datetime do Excel)
                    raw_date = row.get(col_finish, "")

                    if not id_val or id_val == "NAN" or pd.isna(raw_date) or str(raw_date).strip().lower() in ["nan", "nat", ""]:
                        continue

                    # Tratamento da data
                    if isinstance(raw_date, str):
                        data_str = raw_date.strip()
                        if data_str.endswith(" A"):
                            data_str = data_str[:-2].strip()
                    else:
                        data_str = str(raw_date) # Converte Timestamp para string de forma segura

                    try:
                        # Converte para data verdadeira do Python
                        data_val = pd.to_datetime(data_str, errors='coerce')
                        if pd.notna(data_val):
                            dicionario[id_val] = data_val
                    except:
                        pass

                self.log(f"P6: {len(dicionario)} datas de aprovação (Finish) carregadas e formatadas.")
            else:
                self.log(f"Aviso P6: Colunas não encontradas. Cabeçalhos lidos: {list(df_p6.columns)}")
        except Exception as e:
            self.log(f"Aviso fatal ao ler P6: {e}")

        return dicionario

    # --- O MOTOR CENTRAL (Parte 2: Extração e Preparação) ---
    def iniciar_sincronismo(self):
        import pandas as pd
        import openpyxl
        from openpyxl.styles import PatternFill, Alignment, Border, Side, Font
        from tkinter import filedialog
        import datetime as dt 
        if not self.path_mae or not self.path_filha or not self.path_aconex:
            messagebox.showwarning("Aviso", "Os arquivos do Mapeamento, Kaizen Antigo e Aconex são obrigatórios!")
            return

        self.log("--- INICIANDO RECONSTRUÇÃO KAIZEN ---")
        self.btn_executar.configure(state="disabled")
        self.progress_bar.set(0)
        self.update_idletasks()

        # 1. Carregar Aconex
        self.log("1. Carregando Base Aconex...")
        sucesso, msg = self.data_manager.carregar_aconex(self.path_aconex, self.sheet_aconex.get())
        if not sucesso:
            self.log(f"ERRO: {msg}")
            self.btn_executar.configure(state="normal")
            return
        # 2. Carregar P6
        dicionario_p6 = self.carregar_dicionario_p6()
        dicionario_backlog = self.carregar_dicionario_backlog()
        # 3. O Resgate (Kaizen Antigo) com CHAVE HIERÁRQUICA
        self.log("2. Resgatando dados manuais do Kaizen Antigo...")
        self.update_idletasks()

        bolso_kaizen = {}
        protocolos_resgatados = [] # [NOVO] Guarda a linha inteira dos protocolos
        try:
            df_temp = pd.read_excel(self.path_filha, sheet_name=self.sheet_filha.get(), nrows=15, header=None)
            header_idx = 0
            for i, row in df_temp.iterrows():
                if 'N° ITAIPU' in row.values:
                    header_idx = i
                    break

            df_antigo = pd.read_excel(self.path_filha, sheet_name=self.sheet_filha.get(), header=header_idx)

            if 'SITE NEEDED DATE' in df_antigo.columns:
                df_antigo['SITE NEEDED DATE'] = pd.to_datetime(df_antigo['SITE NEEDED DATE'], dayfirst=True, errors='coerce')
            for _, row in df_antigo.iterrows():
                c_itaipu = str(row.get('N° ITAIPU', '')).strip()
                # Matador de decimais fantasmas do Pandas (ex: 12345.0 vira 12345)
                if c_itaipu.endswith('.0'): c_itaipu = c_itaipu[:-2]

                c_cmi = str(row.get('Nº CMI', '')).strip()
                desc = str(row.get('DESCRIÇÃO DO DOCUMENTO', '')).strip().upper()

                if not c_itaipu and not c_cmi: continue

                # --- [NOVO] SEQUESTRO DO PROTOCOLO BLINDADO ---
                if "PROTOCOLO" in desc:
                    # Limpa espaços nas chaves das colunas para garantir o match com openpyxl
                    linha_limpa = {str(k).strip(): v for k, v in row.items()}
                    linha_limpa['N° ITAIPU'] = c_itaipu # Garante o ID limpo na foto resgatada
                    protocolos_resgatados.append(linha_limpa)
                    continue 

                tracking_id = None
                df_track = self.data_manager.localiza_doc_historico(c_itaipu, c_cmi)
                if not df_track.empty:
                    tracking_id = df_track.iloc[0]['Tracking ID']
                # CORREÇÃO DA REGRA DE NEGÓCIO: Define a chave que nunca perde os dados
                chave_resgate = tracking_id if tracking_id else (c_itaipu if c_itaipu else c_cmi)
                if chave_resgate:
                    bolso_kaizen[chave_resgate] = {
                        "ID P6": row.get("ID P6", ""),
                        "SITE NEEDED DATE": row.get("SITE NEEDED DATE", pd.NaT),
                        "ACCOUNTABLE": row.get("ACCOUNTABLE", ""),
                        "RESPONSIBLE": row.get("RESPONSIBLE", ""),
                        "SERVIÇO DE PLANILHA SUBCONTRATADO DO FORNECEDOR?": row.get("SERVIÇO DE PLANILHA SUBCONTRATADO DO FORNECEDOR?", ""),
                        "PROTOCOLOS DE MONTAGEM (ALINHADOS C/ CRONOGRAMA NEEDED DATE)": row.get("PROTOCOLOS DE MONTAGEM (ALINHADOS C/ CRONOGRAMA NEEDED DATE)", "")
                    }
            self.log(f"Sucesso: {len(bolso_kaizen)} documentos manuais salvos na memória.")
        except Exception as e:
            self.log(f"Erro fatal ao ler Kaizen Antigo: {e}")
            self.btn_executar.configure(state="normal")
            return
        # 4. Preparação da Base Limpa e DoW Dinâmico
        self.log("3. Abrindo Mapeamento Original e desenhando nova estrutura...")
        self.progress_bar.set(0.2)
        self.update_idletasks()

        try:
            wb_kaizen = openpyxl.load_workbook(self.path_mae)
            ws_kaizen = wb_kaizen[self.sheet_mae.get()]
        except Exception as e:
            self.log(f"Erro ao abrir Mapeamento Original: {e}")
            self.btn_executar.configure(state="normal")
            return

        headers_existentes, row_hdr = self.find_headers(ws_kaizen)
        if not headers_existentes:
            self.log("ERRO: Cabeçalho 'N° ITAIPU' não encontrado no Mapeamento Original.")
            self.btn_executar.configure(state="normal")
            return
        max_col = max(headers_existentes.values())

        fill_preto = PatternFill(start_color="000000", end_color="000000", fill_type="solid")
        fill_linha_3 = PatternFill(start_color="FF757171", end_color="FF757171", fill_type="solid")
        font_branca = Font(name='Calibri', size=10, color="FFFFFF", bold=True)
        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        borda_branca_espessa = Border(
            left=Side(style='medium', color='FFFFFF'), 
            right=Side(style='medium', color='FFFFFF'), 
            top=Side(style='medium', color='FFFFFF'), 
            bottom=Side(style='medium', color='FFFFFF')
        )
        self.colunas_idx_novas = {} 
        for i, nome_col in enumerate(self.colunas_novas_kaizen):
            col_num = max_col + i + 1
            celula = ws_kaizen.cell(row=row_hdr, column=col_num, value=nome_col)
            celula.fill = fill_preto
            celula.font = font_branca
            celula.alignment = align_center
            celula.border = borda_branca_espessa

            letra_col = openpyxl.utils.get_column_letter(col_num)
            ws_kaizen.column_dimensions[letra_col].width = 25.14
            ws_kaizen.cell(row=3, column=col_num).fill = fill_linha_3

            self.colunas_idx_novas[nome_col] = col_num
        # CORREÇÃO 3: DoW Dinâmico (Segue as colunas mesmo que o Mapeamento cresça)
        col_dow_1 = self.colunas_idx_novas.get("SERVIÇO DE PLANILHA SUBCONTRATADO DO FORNECEDOR?")
        col_dow_2 = self.colunas_idx_novas.get("PROTOCOLOS DE MONTAGEM (ALINHADOS C/ CRONOGRAMA NEEDED DATE)")

        if col_dow_1 and col_dow_2:
            try:
                letra1 = openpyxl.utils.get_column_letter(col_dow_1)
                letra2 = openpyxl.utils.get_column_letter(col_dow_2)
                ws_kaizen.merge_cells(f'{letra1}1:{letra2}1')
                celula_dow = ws_kaizen[f'{letra1}1']
                celula_dow.value = "DoW"
                celula_dow.fill = fill_preto
                celula_dow.font = font_branca
                celula_dow.alignment = align_center
            except Exception as e:
                self.log(f"Aviso: Não foi possível mesclar colunas DoW ({e})")
        letra_max_col = openpyxl.utils.get_column_letter(max_col + 8) 
        dimensao_filtro = f"A{row_hdr}:{letra_max_col}{ws_kaizen.max_row}"
        ws_kaizen.auto_filter.ref = dimensao_filtro
        self.log("Estrutura visual Kaizen criada com sucesso!")
        self.progress_bar.set(0.4)

        # 5. Restauração e Regras Matemáticas (-60 dias e P6)
        self.log("4. Restaurando dados e calculando (P6 e Efeito Cascata)...")

        # [PAINEL DE CONFIGURAÇÃO DE RECUO DE DATAS]
        # Se a regra de recuo (em dias) mudar no futuro, altere apenas estes números:
        RECUO_P6_PARA_NIVEL_1_E_2 = 0
        RECUO_PREDECESSOR_PARA_NIVEL_3 = 60
        RECUO_PREDECESSOR_PARA_NIVEL_4 = 60

        col_itaipu_mae = headers_existentes.get('N° ITAIPU')
        col_cmi_mae = headers_existentes.get('Nº CMI')
        col_nivel_mae = headers_existentes.get('NÍVEL')
        col_grupo_mae = headers_existentes.get('GRUPO')
        col_pred_mae = headers_existentes.get('PREDECESSOR')
        col_data_etapa1 = headers_existentes.get('DATA PREVISTA EMISSÃO ETAPA 1')
        memoria_needed_dates = {}
        font_calibri = Font(name='Calibri', size=10)
        borda_fina = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
        max_row = ws_kaizen.max_row

        for row in range(row_hdr + 1, max_row + 1):
            # CORREÇÃO 2: Proteção de Crash caso a coluna não exista no Excel original
            c_itaipu = str(ws_kaizen.cell(row=row, column=col_itaipu_mae).value or "").strip() if col_itaipu_mae else ""
            c_cmi = str(ws_kaizen.cell(row=row, column=col_cmi_mae).value or "").strip() if col_cmi_mae else ""

            if not c_itaipu and not c_cmi: 
                continue
            nivel_doc = str(ws_kaizen.cell(row=row, column=col_nivel_mae).value or "").strip() if col_nivel_mae else ""
            grupo_doc = str(ws_kaizen.cell(row=row, column=col_grupo_mae).value or "").strip() if col_grupo_mae else ""
            predecessor = str(ws_kaizen.cell(row=row, column=col_pred_mae).value or "").strip() if col_pred_mae else ""

            finish_date_val = None
            if col_data_etapa1:
                finish_date_val = ws_kaizen.cell(row=row, column=col_data_etapa1).value

            cor_hex = self.obter_cor_linha(grupo_doc, nivel_doc)
            fill_linha = PatternFill(start_color="FF" + cor_hex, end_color="FF" + cor_hex, fill_type="solid")
            tracking_id = None
            df_track = self.data_manager.localiza_doc_historico(c_itaipu, c_cmi)
            if not df_track.empty:
                tracking_id = df_track.iloc[0]['Tracking ID']
            dados_resgatados = {}
            # CORREÇÃO DA REGRA DE NEGÓCIO: Resgate Seguro por Hierarquia
            if tracking_id and tracking_id in bolso_kaizen:
                dados_resgatados = bolso_kaizen[tracking_id]
            elif c_itaipu and c_itaipu in bolso_kaizen:
                dados_resgatados = bolso_kaizen[c_itaipu]
            elif c_cmi and c_cmi in bolso_kaizen:
                dados_resgatados = bolso_kaizen[c_cmi]
            # Inicia assumindo a data manual antiga, mas vamos esmagá-la com cálculos se houver base
            site_needed_date = dados_resgatados.get("SITE NEEDED DATE", pd.NaT)
            id_p6_raw = str(dados_resgatados.get("ID P6", "")).strip()

            # --- TRATAMENTO DO ALT+ENTER E ESPAÇOS NO ID P6 (Super Blindado) ---
            # Se o usuário colou com vários espaços ao invés de ALT+ENTER, o split normal falha.
            # Vamos usar regex para quebrar por \n, \r ou por 2+ espaços seguidos.
            id_p6_emissao = ""
            id_p6_aprovacao = ""

            if id_p6_raw:
                import re
                # Troca quebras de linha ou 2+ espaços por um separador único '|'
                id_p6_limpo = re.sub(r'[\r\n]+|\s{2,}', '|', id_p6_raw)
                partes_id = [p.strip().upper() for p in id_p6_limpo.split('|') if p.strip()]

                if len(partes_id) >= 2:
                    id_p6_emissao = partes_id[0]   # Primeiro ID: Emissão
                    id_p6_aprovacao = partes_id[1] # Segundo ID: Aprovação
                elif len(partes_id) == 1:
                    id_p6_emissao = partes_id[0]   # Se só tiver um, usa para ambos
                    id_p6_aprovacao = partes_id[0] 

            # --- O EFEITO CASCATA (SOBRESCRITA FORÇADA) ---

            # 1. Atualização da FINISH DATE (Apenas Níveis 1 e 2, via ID Emissão)
            if nivel_doc in ['1', '2'] and id_p6_emissao in dicionario_p6:
                finish_date_val = dicionario_p6[id_p6_emissao]
            # --- [NOVO] O DEUS EX MACHINA DO BACKLOG PARA PLANILHAS (Nível 3) ---
            chave_backlog = tracking_id if tracking_id else c_itaipu
            if nivel_doc == '3' and chave_backlog in dicionario_backlog:
                dados_bk = dicionario_backlog[chave_backlog]

                # A) Atualiza FINISH DATE com DATA PREVISTA DE EMISSÃO
                data_prev_bk = dados_bk.get("DATA PREVISTA DE EMISSÃO", pd.NaT)
                if pd.notna(data_prev_bk):
                    finish_date_val = data_prev_bk

                # B) Esmaga o STATUS no mapeamento original (Excel Base)
                status_bk = dados_bk.get("STATUS ATUAL", "")
                if status_bk:
                    col_status_idx = headers_existentes.get('STATUS')
                    if col_status_idx: 
                        ws_kaizen.cell(row=row, column=col_status_idx).value = status_bk
            # 2. Atualização da SITE NEEDED DATE (Via ID Aprovação ou Cascata)
            if nivel_doc in ['1', '2'] and id_p6_aprovacao in dicionario_p6:
                # O P6 É A FONTE DA VERDADE: Subtrai os dias da data Finish do P6
                data_finish_p6 = dicionario_p6[id_p6_aprovacao]
                site_needed_date = data_finish_p6 - dt.timedelta(days=RECUO_P6_PARA_NIVEL_1_E_2)

            elif nivel_doc in ['3', '4'] and predecessor and predecessor in memoria_needed_dates:
                # O PAI É A FONTE DA VERDADE: Subtrai os dias baseados no nível do filho atual
                data_pai = memoria_needed_dates[predecessor]
                if isinstance(data_pai, (dt.datetime, dt.date)):
                    if nivel_doc == '3':
                        site_needed_date = data_pai - dt.timedelta(days=RECUO_PREDECESSOR_PARA_NIVEL_3)
                    else: # Nível 4
                        site_needed_date = data_pai - dt.timedelta(days=RECUO_PREDECESSOR_PARA_NIVEL_4)

            # Atualiza a memória para que os próximos filhos herdem a data que acabamos de calcular
            if pd.notna(site_needed_date) and site_needed_date is not None:
                memoria_needed_dates[c_itaipu] = site_needed_date

            variance_val = ""
            if isinstance(finish_date_val, (dt.datetime, dt.date)) and isinstance(site_needed_date, (dt.datetime, dt.date)):
                f_date = finish_date_val.date() if isinstance(finish_date_val, dt.datetime) else finish_date_val
                s_date = site_needed_date.date() if isinstance(site_needed_date, dt.datetime) else site_needed_date
                variance_val = (f_date - s_date).days
            valores_para_injetar = {
                "ID P6": dados_resgatados.get("ID P6", ""),
                "FINISH DATE": finish_date_val,
                "SITE NEEDED DATE": site_needed_date if pd.notna(site_needed_date) else "",
                "VARIANCE": variance_val,
                "ACCOUNTABLE": dados_resgatados.get("ACCOUNTABLE", ""),
                "RESPONSIBLE": dados_resgatados.get("RESPONSIBLE", ""),
                "SERVIÇO DE PLANILHA SUBCONTRATADO DO FORNECEDOR?": dados_resgatados.get("SERVIÇO DE PLANILHA SUBCONTRATADO DO FORNECEDOR?", ""),
                "PROTOCOLOS DE MONTAGEM (ALINHADOS C/ CRONOGRAMA NEEDED DATE)": dados_resgatados.get("PROTOCOLOS DE MONTAGEM (ALINHADOS C/ CRONOGRAMA NEEDED DATE)", "")
            }
            for nome_col, valor in valores_para_injetar.items():
                if nome_col in self.colunas_idx_novas:
                    col_num = self.colunas_idx_novas[nome_col]
                    celula = ws_kaizen.cell(row=row, column=col_num)

                    # se for nulo ou string vazia, injeta None
                    if pd.isna(valor) or str(valor) == "NaT" or str(valor).strip() == "":
                        celula.value = None
                    else:
                        celula.value = valor

                    celula.fill = fill_linha
                    celula.font = font_calibri
                    celula.border = borda_fina
                    celula.alignment = align_center

                    if nome_col in ["FINISH DATE", "SITE NEEDED DATE"] and valor != "":
                        celula.number_format = 'dd/mm/yyyy'
            if row % 10 == 0:
                self.progress_bar.set(0.4 + (0.6 * (row / max_row)))
                self.update_idletasks()
        # 6. Salvamento
        self.progress_bar.set(1.0)
        self.log("5. Abrindo janela para salvar o arquivo...")

        nome_sugerido = os.path.basename(self.path_mae).replace(".xlsx", " - KAIZEN_ATUALIZADO.xlsx")
        caminho_salvar = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=nome_sugerido,
            title="Salvar Mapeamento Kaizen Reconstruído",
            filetypes=[("Arquivos Excel", "*.xlsx")]
        )

        if not caminho_salvar:
            self.log("Operação de salvamento cancelada pelo usuário.")
            self.btn_executar.configure(state="normal")
            return
        self.log(f"Salvando arquivo em: {caminho_salvar}")
        self.update_idletasks()

        salvo = self.excel_handler.salvar_com_retry(wb_kaizen, caminho_salvar, self.winfo_toplevel())

        if salvo:
            # === [NOVO] ACIONAMENTO DO MOTOR XLWINGS PARA INJEÇÃO DOS PROTOCOLOS ===
            self.injetar_protocolos_xlwings(caminho_salvar, dicionario_backlog, headers_existentes, memoria_needed_dates, protocolos_resgatados)

            messagebox.showinfo("Sucesso", f"Reconstrução Kaizen concluída!\nArquivo salvo em:\n{caminho_salvar}")
            self.log("SUCESSO ABSOLUTO! Motor Kaizen Finalizado.")
        else:
            self.log("ERRO: O arquivo não pôde ser salvo (feche-o se estiver aberto).")

        self.btn_executar.configure(state="normal")
    def injetar_protocolos_xlwings(self, caminho_arquivo, dicionario_backlog, headers_existentes, memoria_needed_dates, protocolos_resgatados):
        """Abre o Excel em modo invisível, une Kaizen Antigo com Backlog e injeta a linha inteira."""
        import datetime as dt
        import pandas as pd

        # 1. Unir as Colunas para saber onde injetar cada dado
        todas_colunas = {**headers_existentes, **self.colunas_idx_novas}

        # 2. Mesclar Protocolos do Kaizen Antigo com o Backlog
        mapa_protocolos = {str(p.get('N° ITAIPU', '')).strip(): p for p in protocolos_resgatados if str(p.get('N° ITAIPU', '')).strip()}

        for k, v in dicionario_backlog.items():
            if "PROTOCOLO" in str(v.get("DESCRIÇÃO DO DOCUMENTO", "")).upper():
                c_itaipu = str(v.get("N° ITAIPU", "")).strip()
                if c_itaipu.endswith('.0'): c_itaipu = c_itaipu[:-2] # Blindagem extra

                if c_itaipu in mapa_protocolos:
                    # MATCH PERFEITO! Mantém a digitação manual (GRUPO, SISTEMA) e atualiza os dados vitais
                    mapa_protocolos[c_itaipu]["STATUS"] = v.get("STATUS ATUAL") 
                    mapa_protocolos[c_itaipu]["FINISH DATE"] = v.get("DATA NECESSÁRIA (P6)")
                    mapa_protocolos[c_itaipu]["PREDECESSOR"] = v.get("PREDECESSOR") 
                    # --- NOVO: Se o título mudar no Backlog, esmaga o título velho do Kaizen ---
                    mapa_protocolos[c_itaipu]["DESCRIÇÃO DO DOCUMENTO"] = v.get("DESCRIÇÃO DO DOCUMENTO")
                else:
                    # Protocolo inédito criado pela engenharia no Backlog
                    novo_prot = {
                        "N° ITAIPU": c_itaipu,
                        "DESCRIÇÃO DO DOCUMENTO": v.get("DESCRIÇÃO DO DOCUMENTO"),
                        "PREDECESSOR": v.get("PREDECESSOR"), 
                        "STATUS": v.get("STATUS ATUAL"), 
                        "FINISH DATE": v.get("DATA NECESSÁRIA (P6)"),
                        "NÍVEL": "3"
                    }
                    mapa_protocolos[c_itaipu] = novo_prot
        lista_final_protocolos = list(mapa_protocolos.values())

        if not lista_final_protocolos:
            return # Nada a fazer

        self.log(f"Iniciando injeção de {len(lista_final_protocolos)} Protocolos (Via XLWINGS)...")
        self.update_idletasks()

        try:
            import xlwings as xw
        except ImportError:
            self.log("ERRO: Biblioteca 'xlwings' não instalada. Pip install xlwings necessário.")
            return
        col_itaipu_idx = headers_existentes.get('N° ITAIPU')
        col_pred_idx = headers_existentes.get('PREDECESSOR')
        col_needed_idx = self.colunas_idx_novas.get("SITE NEEDED DATE")
        col_variance_idx = self.colunas_idx_novas.get("VARIANCE") 
        RECUO_PREDECESSOR_PARA_NIVEL_3 = 60
        max_col_total = max(headers_existentes.values()) + len(self.colunas_novas_kaizen)

        app = xw.App(visible=False)
        try:
            wb = app.books.open(caminho_arquivo)
            ws = wb.sheets[self.sheet_mae.get()]

            # Pega o limite real da planilha de forma dinâmica
            max_row = ws.api.UsedRange.Rows.Count

            for prot in lista_final_protocolos:
                pai_codigo = str(prot.get("PREDECESSOR", "")).strip()
                if not pai_codigo or pai_codigo == "NAN" or pai_codigo == "None": continue

                linha_alvo = -1

                # Acha o Pai e desce até o último da família
                for r in range(1, max_row + 1):
                    # Usando range().value para garantir compatibilidade nativa com a API do Excel
                    val_itaipu = str(ws.range((r, col_itaipu_idx)).value or "").strip()
                    if val_itaipu == pai_codigo:
                        linha_alvo = r + 1
                        while linha_alvo <= max_row:
                            val_pred = str(ws.range((linha_alvo, col_pred_idx)).value or "").strip()
                            if val_pred != pai_codigo:
                                break
                            linha_alvo += 1
                        break

                if linha_alvo != -1:
                    # 1. Injeta a linha vazia (Excel Nativo)
                    ws.range(f"{linha_alvo}:{linha_alvo}").insert(shift='down')
                    max_row += 1 

                    # 2. O CLIQUE MÁGICO (O pedido que você fez!)
                    # Simula o usuário selecionando a linha e clicando no botão "Agrupar" (Data > Group)
                    ws.range(f"{linha_alvo}:{linha_alvo}").api.Group()

                    # 3. Copia TODOS os dados recuperados para as respectivas colunas
                    for col_name, val in prot.items():
                        if pd.isna(val): continue 

                        col_idx = todas_colunas.get(col_name)
                        if col_idx:
                            # Previne erro de formato injetando o tipo puro do Python
                            if isinstance(val, pd.Timestamp):
                                ws.range((linha_alvo, col_idx)).value = val.to_pydatetime()
                            else:
                                ws.range((linha_alvo, col_idx)).value = val

                    # 4. Efeito Cascata: Atualiza a SITE NEEDED DATE e VARIANCE
                    dt_needed = None
                    if col_needed_idx and pai_codigo in memoria_needed_dates:
                        data_pai_calc = memoria_needed_dates[pai_codigo]
                        if isinstance(data_pai_calc, (dt.datetime, dt.date)):
                            dt_needed = data_pai_calc - dt.timedelta(days=RECUO_PREDECESSOR_PARA_NIVEL_3)
                            ws.range((linha_alvo, col_needed_idx)).value = dt_needed

                    # Calcula e injeta a Variância (Finish Date - Site Needed Date)
                    if col_variance_idx and dt_needed is not None:
                        finish_date_prot = prot.get("FINISH DATE")
                        if pd.notna(finish_date_prot) and isinstance(finish_date_prot, (dt.datetime, dt.date, pd.Timestamp)):
                            # Normaliza para .date() ignorando as horas para evitar erros de cálculo
                            f_date = finish_date_prot.date() if isinstance(finish_date_prot, (dt.datetime, pd.Timestamp)) else finish_date_prot
                            s_date = dt_needed.date() if isinstance(dt_needed, dt.datetime) else dt_needed
                            ws.range((linha_alvo, col_variance_idx)).value = (f_date - s_date).days

                    # 5. Pintura Cinza e Bordas Finas (Estética Nível 3)
                    rng = ws.range((linha_alvo, 1), (linha_alvo, max_col_total))
                    rng.color = (217, 217, 217)
                    rng.api.Font.Bold = False
                    rng.api.Font.Color = 0x000000 

                    for border_id in range(7, 11): 
                        rng.api.Borders(border_id).LineStyle = 1
                        rng.api.Borders(border_id).Weight = 2
            wb.save()
            self.log("Injeção dos protocolos finalizada com sucesso.")
        except Exception as e:
            self.log(f"Erro fatal no xlwings: {e}")
        finally:
            try: wb.close()
            except: pass
            app.quit()
def resource_path(relative_path):
    """ Obtém o caminho absoluto, funcionando tanto no VS Code quanto no .exe """
    try:
        # PyInstaller cria uma pasta temporária (modo executável)
        base_path = sys._MEIPASS
    except Exception:
        # Modo desenvolvimento: pega o diretório onde o arquivo .py ESTÁ SALVO
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
env_path = resource_path('.env')
load_dotenv(env_path)
# --- 12. Main App ---
class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CONFIGURAÇÃO DE CORES (Setup Inicial) ---
        # "blue" (padrão), "green" (verde itaipu), "dark-blue" (mais profissional)
        ctk.set_default_color_theme("dark-blue") 

        # --- CONFIGURAÇÕES DA JANELA ---
        self.title("Sistema de Gestão de Documentos - Engenharia")
        self.geometry("1100x750")

        # Ícone da Janela
        try:
            icon_path = resource_path(os.path.join("assets", "logo_definitivo.ico"))
            self.iconbitmap(icon_path)
        except Exception:
            pass 
        # --- DADOS ---
        self.excel_handler = ExcelHandler()
        self.data_manager = DataManager() 

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        # --- SIDEBAR ---
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        # MOLA (Empurra o rodapé para o fundo)
        self.sidebar_frame.grid_rowconfigure(9, weight=1) 
        # ---------------------------------------------------------
        # 1. LOGO E TÍTULO
        # ---------------------------------------------------------
        try:
            logo_filename = "logo_final.png" 
            logo_path = resource_path(os.path.join("assets", logo_filename))
            pil_image = Image.open(logo_path)

            self.logo_image = ctk.CTkImage(light_image=pil_image, 
                                           dark_image=pil_image, 
                                           size=(100, 100)) 

            self.logo_label = ctk.CTkLabel(self.sidebar_frame, image=self.logo_image, text="")
            self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 10)) 

        except Exception as e:
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="LOGO", font=ctk.CTkFont(weight="bold"))
            self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        self.app_name = ctk.CTkLabel(self.sidebar_frame, 
                                     text="DocManager\nItaipu", 
                                     font=ctk.CTkFont(size=20, weight="bold"))
        self.app_name.grid(row=1, column=0, padx=20, pady=(0, 20))
        # ---------------------------------------------------------
        # 2. BOTÕES DE NAVEGAÇÃO
        # ---------------------------------------------------------
        self.btn_map = ctk.CTkButton(self.sidebar_frame, text="Mapa dos Planos", command=lambda: self.select_frame("mapping"))
        self.btn_map.grid(row=2, column=0, padx=20, pady=10)
        self.btn_status = ctk.CTkButton(self.sidebar_frame, text="Status Documentos", command=lambda: self.select_frame("status"))
        self.btn_status.grid(row=3, column=0, padx=20, pady=10)

        self.btn_aconex = ctk.CTkButton(self.sidebar_frame, text="API Aconex", command=lambda: self.select_frame("aconex"))
        self.btn_aconex.grid(row=4, column=0, padx=20, pady=10)
        self.btn_report = ctk.CTkButton(self.sidebar_frame, text="Relatórios", command=lambda: self.select_frame("report"))
        self.btn_report.grid(row=5, column=0, padx=20, pady=10)

        self.btn_hist = ctk.CTkButton(self.sidebar_frame, text="Histórico/Dash", command=lambda: self.select_frame("dashboard"))
        self.btn_hist.grid(row=6, column=0, padx=20, pady=10)
        self.btn_corella = ctk.CTkButton(self.sidebar_frame, text="Corella vs Aconex", command=lambda: self.select_frame("corella"))
        self.btn_corella.grid(row=7, column=0, padx=20, pady=10) 
        self.btn_kaizen = ctk.CTkButton(self.sidebar_frame, text="Mapa Kaizen C&C", command=lambda: self.select_frame("kaizen")) #fg_color="#6c5ce7", hover_color="#4a3bbf")
        self.btn_kaizen.grid(row=8, column=0, padx=20, pady=10)
        # ---------------------------------------------------------
        # 3. CONTROLES DE APARÊNCIA (Claro/Escuro)
        # ---------------------------------------------------------
        # Linha 8 é o Espaço Vazio (Weight 1)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Aparência:", anchor="w")
        self.appearance_mode_label.grid(row=10, column=0, padx=20, pady=(10, 0))

        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, 
                                                             values=["Dark", "Light"],
                                                             command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=11, column=0, padx=20, pady=(0, 20))

        # ---------------------------------------------------------
        # 4. RODAPÉ (VERSÃO)
        # ---------------------------------------------------------
        versao_app = os.getenv("VERSAO", "2.0.0") 
        self.version_label = ctk.CTkLabel(self.sidebar_frame, text=f'Versão {versao_app}', text_color="gray50", font=ctk.CTkFont(size=10)) 
        self.version_label.grid(row=12, column=0, padx=20, pady=(0, 20), sticky="s")
        # --- CONTAINER DIREITO ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        # --- INICIALIZAÇÃO DAS VIEWS ---
        self.mapping_view = MappingView(self.container, self.excel_handler)
        self.status_view = StatusCheckView(self.container, self.excel_handler)
        self.status_view.data_manager = self.data_manager
        self.dashboard_view = DashboardView(self.container, self.excel_handler)
        self.aconex_view = AconexView(self.container) 
        self.report_view = ReportView(self.container, self.excel_handler) 
        self.corella_view = CorellaView(self.container, self.excel_handler)
        self.kaizen_view = KaizenView(self.container, self.excel_handler, self.data_manager)

        # Define o padrão inicial
        self.appearance_mode_optionemenu.set("System")
        self.select_frame("mapping")
    # --- MÉTODOS DE CONTROLE ---
    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
    def select_frame(self, name):
        for widget in self.container.winfo_children():
            widget.grid_forget()
        if name == "mapping": self.mapping_view.grid(row=0, column=0, sticky="nsew")
        elif name == "status": self.status_view.grid(row=0, column=0, sticky="nsew")
        elif name == "dashboard": self.dashboard_view.grid(row=0, column=0, sticky="nsew")
        elif name == "aconex": self.aconex_view.grid(row=0, column=0, sticky="nsew")
        elif name == "report": self.report_view.grid(row=0, column=0, sticky="nsew")
        elif name == "corella": self.corella_view.grid(row=0, column=0, sticky="nsew")
        elif name == "kaizen": self.kaizen_view.grid(row=0, column=0, sticky="nsew") 
if __name__ == "__main__":
    app = MainApp()
    try:
        import pyi_splash # type: ignore
        if pyi_splash.is_alive():
            pyi_splash.close()
    except ImportError:
        pass
    # ----------------------
    app.mainloop()