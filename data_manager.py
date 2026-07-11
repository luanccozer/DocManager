import unicodedata
import numpy as np
import openpyxl
import pandas as pd
import xml.etree.ElementTree as ET
import re
from datetime import timedelta
class DataManager:
    def __init__(self):
        self.df_aconex = None

        # Listas de Status definidos
        self.status_possíveis_documentos = [
            'Anulado', 'Approved', 'Aprovado', 'Aprovado com Comentários', 'Approved with Comments', 
            'Aprobado con Comentarios','Cancelado', 'Deleted', 'Em Processo', 'Informativo', 
            'Não Aprovado', 'No Aprobado', 'Para Análise', 'Para Aprovação', 'Para Assinatura', 
            'Para Informação', 'Apto para Firma', 'Para Firma', 'Em Integração', 'Integrado', 
            'Não Integrado', 'Em Validação', 'Validado', 'Não Validado', 'Aceito', 'Não Aceito', 
            '01 Aceito', '03 Nao Aceito', 'Para Integraçao'
        ]
        self.status_aprovados = ['Aprovado', 'Aprovado com Comentários', 'Para Assinatura']
        self.status_reprovados = ['Não Aprovado']
        self.status_em_integracao = [
            'Em Integração', 'Integrado', 'Não Integrado', 'Em Validação', 'Validado', 
            'Não Validado', 'Aceito', 'Não Aceito', '01 Aceito', '03 Nao Aceito',   'Para Aprovação', 'Para Integraçao'
        ]
        self.STATUS_VALIDOS_COMPARACAO = ['Não Aprovado', 'Em Processo', 'Aprovado com Comentários', 
                                          'Para Assinatura', 'Aprovado', 'Para Informação', 'Informativo']

        self.status_mod_aprov_pre = ['P0 - Modelo Aprovado', 'P1 - Modelo Aprovado']
        self.status_mod_aprov_300 = ['S1 - LOD 300 - Sem Incidentes', 'S1 - LOD 300 - Finalizado']
        self.status_mod_aprov_350 = ['S3 - LOD 350 - Aprovado', 'S4 - LOD 350 - Aprovado']

        self.status_mod_reprov_pre = ['Não Aprovado', 'P0 - Modelo Não Aprovado', 'P1 - Modelo Não Aprovado']
        self.status_mod_reprov_300 = ['S1 - LOD 300 - Com Incidentes']
        self.status_mod_reprov_350 = ['S3 - LOD 350 - Com Incidentes', 'S3 - LOD 350 - Não Aprovado']

        self.status_mod_analise_pre = ['P0 - Validação do Modelo', 'P1 - Validação do Modelo BIM', 'Para Análise', 'Para Aprovação']
        self.status_mod_analise_300 = ['S1 - LOD 300 - Revisão de Modelo']
        self.status_mod_analise_350 = ['S3 - LOD 350 - Revisão de Modelo']

        self.status_mod_inicial_pre = ['Em Processo', 'P0 - Emissão Inicial', 'P1 - Emissão Inicial']
        self.status_mod_inicial_300 = ['S0 - Initial Status', 'S0 - LOD 300 - Inicial']
        self.status_mod_inicial_350 = ['S2 - LOD 350 - Inicial']

        self.status_mod_info = ['Para Informação']
        # O conjunto de todos os status válidos para filtrar os "fantasmas"
        self.status_modelos_validos = (
            self.status_mod_aprov_pre + self.status_mod_aprov_300 + self.status_mod_aprov_350 +
            self.status_mod_reprov_pre + self.status_mod_reprov_300 + self.status_mod_reprov_350 +
            self.status_mod_analise_pre + self.status_mod_analise_300 + self.status_mod_analise_350 +
            self.status_mod_inicial_pre + self.status_mod_inicial_300 + self.status_mod_inicial_350 +
            self.status_mod_info
        )

    def carregar_aconex(self, caminho, aba):
        try:
            # Carrega como string para evitar conversões automáticas indesejadas
            self.df_aconex = pd.read_excel(caminho, sheet_name=aba, dtype=str)
            self.df_aconex = self.df_aconex.fillna('')

            # Limpeza (strip) nas colunas chave
            cols_strip = ["No. do Documento", "Controle do Emissor", "Tracking ID", "Current", "Status da Revisão", "Revisão", "Status", "Versão"]
            for col in cols_strip:
                if col in self.df_aconex.columns:
                    self.df_aconex[col] = self.df_aconex[col].astype(str).str.strip()

            return True, f"Base Aconex carregada: {len(self.df_aconex)} linhas."
        except Exception as e:
            return False, f"Erro ao carregar Aconex: {e}"
    def localiza_doc_historico(self, codigo_itaipu, codigo_cmi):
        if self.df_aconex is None:
            return pd.DataFrame()
        # Limpeza preventiva
        it = str(codigo_itaipu).strip() if codigo_itaipu else ""
        cmi = str(codigo_cmi).strip() if codigo_cmi else ""
        matches = pd.DataFrame()

        # 1. Tentativa Ouro: Busca exata pelos dois códigos simultaneamente
        if len(it) > 3 and len(cmi) > 3:
            matches = self.df_aconex[(self.df_aconex["No. do Documento"] == it) & 
                                     (self.df_aconex["Controle do Emissor"] == cmi)]

        # 2. Tentativa Prata: Busca apenas pelo CMI (Mais forte/imutável)
        if matches.empty and len(cmi) > 3:
            matches = self.df_aconex[self.df_aconex["Controle do Emissor"] == cmi]
        # 3. Tentativa Bronze: Busca apenas pelo Itaipu (Pode sofrer com erros de digitação como falta de ponto)
        if matches.empty and len(it) > 3:
            matches = self.df_aconex[self.df_aconex["No. do Documento"] == it]
        if matches.empty:
            return pd.DataFrame()
        # 4. Resolução de Conflitos de Tracking ID
        unique_ids = matches["Tracking ID"].unique()
        tracking_id_eleito = None

        if len(unique_ids) == 1:
            tracking_id_eleito = unique_ids[0]
        else:
            # Caso de duplicidade: Desempate pela Data de Alteração
            try:
                candidatos = matches.copy()
                candidatos['Data_Obj'] = pd.to_datetime(candidatos['Data de Alteração'], dayfirst=True, errors='coerce')
                candidatos = candidatos.sort_values(by='Data_Obj', ascending=False, na_position='last')
                tracking_id_eleito = candidatos.iloc[0]["Tracking ID"]
            except Exception:
                tracking_id_eleito = unique_ids[0]
        # 5. Retorna o histórico completo do ID vencedor
        if tracking_id_eleito:
            return self.df_aconex[self.df_aconex["Tracking ID"] == tracking_id_eleito].copy()

        return pd.DataFrame()
    def normalizar_revisao(self, rev):
        if not rev: return ''
        r = rev.upper().replace('R', '').strip()
        return r.ljust(3, 'z')
    def calcular_emitido_nao_emitido(self, status_consolidado):
        """
        Lógica Simplificada:
        Se o Status Consolidado (Real) já determinou que é 'NÃO EMITIDO', 
        então é isso. Qualquer outra coisa significa que o documento existe (EMITIDO).
        """
        st = str(status_consolidado).strip().upper()

        if not st or st == "NÃO EMITIDO":
            return "NÃO EMITIDO"
        else:
            return "EMITIDO"
    def calcular_status_real(self, df_tracking, revisao_current):
        """
        Calcula Status Real (Lógica de Batalha de Versões + Exceção de Integração).
        """
        # 1. VALIDAÇÃO BÁSICA
        if df_tracking.empty or not revisao_current:
            return "NÃO EMITIDO"

        # --- IDENTIFICAÇÃO DE TIPOLOGIA (EXCEÇÃO PLANILHAS) ---
        is_planilha = False
        if 'Título' in df_tracking.columns:
            # Pega o título da primeira linha, converte para string e maiúsculo
            titulo_doc = str(df_tracking['Título'].iloc[0]).strip().upper()
            #if 'MODELO 3D' in titulo_doc:
                #return "MODELO 3D"
            if 'PLANILHA' in titulo_doc and 'COMISSIONAMENTO'in titulo_doc:
                is_planilha = True
        # --- LISTAS ESTRITAS ---
        status_aprovacao = ['APROVADO', 'APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA']
        status_reprovacao = ['NÃO APROVADO']
        status_informativo = ['INFORMATIVO', 'PARA INFORMAÇÃO']
        status_anulacao = ['CANCELADO', 'ANULADO','ISSUED FOR ANNULMENT']

        # Converte a lista da classe para Upper Case para garantir o match
        lista_integracao_upper = [str(s).strip().upper() for s in self.status_em_integracao]
        # --- NOVA REGRA DO "PARA ANÁLISE" (DATA DE CORTE: 19/08/2024) ---
        def verificar_se_integracao(status_texto, data_texto):
            st = str(status_texto).strip().upper()
            if st in lista_integracao_upper:
                return True
            # Regra condicional
            if st in ['PARA ANÁLISE', 'PARA ANALISE']:
                try:
                    dt = pd.to_datetime(data_texto, dayfirst=True)
                    if dt >= pd.to_datetime('2024-08-19'):
                        return True
                except: pass
            return False
        # APLICA A REGRA DE NEGÓCIO DE PLANILHAS
        if is_planilha:
            status_aprovacao.append('PARA APROVAÇÃO')
            # Remove da lista de integração para não dar conflito (se existir lá)
            if 'PARA APROVAÇÃO' in lista_integracao_upper:
                lista_integracao_upper.remove('PARA APROVAÇÃO')
        # Preparar Versão Numérica
        df_tracking = df_tracking.copy()
        df_tracking['Versão_Int'] = pd.to_numeric(df_tracking['Versão'], errors='coerce').fillna(0)
        # 2. DEFINIR STATUS ATUAL (LINHA DA VERDADE)
        try:
            df_curr = df_tracking[df_tracking['Revisão'].str.strip() == revisao_current.strip()]
            if df_curr.empty: return "NÃO EMITIDO"

            # Pega a linha com maior versão da revisão atual
            linha_atual = df_curr.sort_values(by=['Versão_Int'], ascending=False).iloc[0]
            status_atual_str = str(linha_atual['Status']).strip().upper()
        except:
            return "NÃO EMITIDO"
        # 3. VERIFICAÇÃO IMEDIATA (Se hoje já é definitivo, ganha de tudo)
        if status_atual_str in status_aprovacao: return linha_atual['Status']
        if status_atual_str in status_anulacao:  return linha_atual['Status']
        if status_atual_str in status_reprovacao:
            if not revisao_current.isdigit(): # Se for A, B, C... retorna reprovado direto
                return linha_atual['Status']
        if status_atual_str in status_informativo: return linha_atual['Status']
        # 4. PREPARAR O CAMPO DE BATALHA
        # Define quem participa da "batalha" de versões baseado se é Status Real ou Fantasma (Integração)

        df_historico = df_tracking[df_tracking['Revisão'].str.strip() != revisao_current.strip()].copy()
        # --- CENÁRIO A: STATUS INTERNO/INTEGRAÇÃO ("FANTASMA") ---
        # O documento está na engenharia (ex: Em Validação) ou sofreu erro de tramitação.
        if verificar_se_integracao(status_atual_str, linha_atual.get('Data de Alteração', '')):

            # NOVA REGRA (TENTATIVA DE SALVAMENTO):
            # Procura dentro da PRÓPRIA revisão atual se já existiu um status oficial antes do fantasma.
            status_oficiais = status_aprovacao + status_reprovacao + status_informativo
            df_curr_real = df_curr[df_curr['Status'].str.strip().str.upper().isin(status_oficiais)].copy()

            if not df_curr_real.empty:
                # Achou um veredito real na mesma revisão! Pega a versão mais recente desse veredito.
                linha_salva = df_curr_real.sort_values(by=['Versão_Int'], ascending=False).iloc[0]
                return linha_salva['Status']

            # Se não achou nada (era fantasma desde o começo), segue a regra normal:
            if df_historico.empty:
                return "NÃO EMITIDO"

            # Ignora a revisão atual vazia de vereditos. O status real será o vencedor do histórico passado.
            df_alvo_batalha = df_historico
        # --- CENÁRIO B: STATUS EXTERNO/PROCESSO ("REAL") ---
        # O documento está tramitando (ex: Em Processo).
        else:
            # Se não tem histórico (ex: 0A Em Processo)
            if df_historico.empty:
                if status_atual_str == 'EM PROCESSO': return 'Em Processo'
                return "NÃO EMITIDO"
            # Se tem histórico (ex: 1A Em Processo)
            # AÇÃO: Filtra apenas a FAMÍLIA ATUAL. A mudança de família (0->1) reseta a aprovação.
            familia_atual = str(revisao_current).strip()[0]
            mask_familia = df_historico['Revisão'].astype(str).str.strip().str.startswith(familia_atual)

            df_alvo_batalha = df_historico[mask_familia]

            # Se após filtrar a família o histórico ficou vazio (Primeira vez da família 1A)
            if df_alvo_batalha.empty:
                if status_atual_str == 'EM PROCESSO': return 'Em Processo'
                return "NÃO EMITIDO"
        # 5. A BATALHA DE VERSÕES (REI DA COLINA)
        # Roda sobre o df_alvo_batalha definido acima

        versao_aprovada_max = -1
        status_aprovada_txt = ""
        versao_reprovada_max = -1
        status_reprovada_txt = ""
        versao_informativa_max = -1
        status_informativa_txt = ""
        for _, row in df_alvo_batalha.iterrows():
            st = str(row['Status']).strip().upper()
            v = row['Versão_Int']
            rev_row = str(row['Revisão']).strip() 
            if st in status_aprovacao:
                if v > versao_aprovada_max:
                    versao_aprovada_max = v
                    status_aprovada_txt = row['Status']

            elif st in status_reprovacao:
                if rev_row.isdigit():
                    continue
                if v > versao_reprovada_max:
                    versao_reprovada_max = v
                    status_reprovada_txt = row['Status']

            elif st in status_informativo:
                if v > versao_informativa_max:
                    versao_informativa_max = v
                    status_informativa_txt = row['Status']
        # 6. O VEREDITO DA BATALHA

        # Reprovado ganha?
        if versao_reprovada_max > versao_aprovada_max and versao_reprovada_max > versao_informativa_max:
            if status_atual_str in lista_integracao_upper:
                return status_reprovada_txt # Retorna "NÃO APROVADO"
            return "Em Processo"
        # Aprovado ganha?
        if versao_aprovada_max > versao_reprovada_max and versao_aprovada_max > versao_informativa_max:
            return status_aprovada_txt
        # Informativo ganha?
        if versao_informativa_max > versao_reprovada_max and versao_informativa_max > versao_aprovada_max:
            return status_informativa_txt
        # 7. FALLBACK (EMPATE OU SEM DADOS)

        # Se era Status Interno (Fantasma), tenta pegar o último status do histórico
        if status_atual_str in lista_integracao_upper:
            if not df_alvo_batalha.empty:
                ultima_linha = df_alvo_batalha.sort_values(by=['Versão_Int'], ascending=False).iloc[0]
                st_ultima = str(ultima_linha['Status']).strip().upper()

                # CORREÇÃO AQUI:
                # Se o histórico recuperado ("Integrado") TAMBÉM for um status interno,
                # então o documento continua sem nunca ter sido emitido de verdade.
                if verificar_se_integracao(st_ultima, ultima_linha.get('Data de Alteração', '')):
                    return "NÃO EMITIDO"

                if st_ultima == 'EM PROCESSO': return 'Em Processo'
                return ultima_linha['Status'] 

            return "NÃO EMITIDO"
        # Se era Status Externo
        if status_atual_str == 'EM PROCESSO':
            return 'Em Processo'
        return "NÃO EMITIDO"
    def calcula_status_consolidado(self, status_real, status_emissao, emitido_nao_emitido):
        sr = status_real if status_real else ""
        se = status_emissao if status_emissao else ""
        ene = emitido_nao_emitido if emitido_nao_emitido else ""
        if sr in ['Aprovado com Comentários', 'Aprovado', 'Para Assinatura', 'Informativo', 'Para Aprovação']:
            return 'APROVADO'
        elif se == 'Em Processo' and sr == 'Análise 1ª Emissão':
            return 'EM PROCESSO'
        elif sr == 'Não Aprovado' and se == 'Não Aprovado':
            return 'NÃO APROVADO'
        elif sr == 'Não Aprovado' and (se in self.status_em_integracao or str(se).strip().upper() in ['PARA ANÁLISE', 'PARA ANALISE']):
            return 'NÃO APROVADO'
        elif sr == 'Não Aprovado' and se == 'Em Processo':
            return 'EM PROCESSO'

        # NOVA REGRA: Mapeamento de Cancelamento
        elif str(sr).strip().upper() in ['ANULADO', 'CANCELADO', 'ISSUED FOR ANNULMENT']:
            return 'CANCELADO'

        elif sr == 'NÃO EMITIDO':
            return 'NÃO EMITIDO'
        elif (not sr) and (ene == 'SATedms'):
            return 'SATedms'
        elif sr == 'Em Processo' and se == 'Em Processo':
            return 'EM PROCESSO'
        else:
            return 'ERRO'
    def calcula_status_consolidado_estrito(self, status_real, status_consolidado_atual):
        """
        Regra estrita para Planilhas Nível 3: Só vira 'APROVADO' se o status real for exatamente 'Aprovado'.
        Qualquer outra variação de aprovação parcial vira 'APROVAÇÃO INTERMEDIÁRIA'.
        """
        sr = status_real if status_real else ""

        if sr == 'Aprovado':
            return 'APROVADO'
        elif sr in ['Aprovado com Comentários', 'Para Assinatura', 'Informativo', 'Para Aprovação']:
            return 'APROVAÇÃO INTERMEDIÁRIA'

        # Se não for nenhum dos dois acima (ex: Não Aprovado, Em Processo), mantém o que já tinha sido calculado
        return status_consolidado_atual

    def calcula_parado_com(self, status):
        if status == 'Em Processo':
            return 'ITAIPU'
        else:
            return 'CMI'
    def obter_codigos_historicos(self, df_tracking):
        """
        Varre o histórico de um documento (Tracking ID) e retorna uma lista com TODOS
        os códigos (Itaipu e CMI) únicos que ele já possuiu ao longo das revisões.
        """
        codigos_unicos = set()

        if not df_tracking.empty:
            if 'No. do Documento' in df_tracking.columns:
                # Extrai todos os códigos Itaipu do histórico, limpa os espaços e ignora vazios
                cods_itaipu = df_tracking['No. do Documento'].dropna().astype(str).str.strip()
                codigos_unicos.update(cods_itaipu.tolist())

            if 'Controle do Emissor' in df_tracking.columns:
                # Extrai todos os códigos CMI do histórico
                cods_cmi = df_tracking['Controle do Emissor'].dropna().astype(str).str.strip()
                codigos_unicos.update(cods_cmi.tolist())

        # Remove eventuais strings vazias ou nulas que possam ter passado
        codigos_unicos.discard("")
        codigos_unicos.discard("nan")
        codigos_unicos.discard("None")

        return list(codigos_unicos)

    def gerar_relatorio_ciclos_avancado(self, caminho_arquivo, aba):
        try:
            # 1. Carregar e Preparar
            df = pd.read_excel(caminho_arquivo, sheet_name=aba, dtype=str)
            df['Data_Obj'] = pd.to_datetime(df['Data de Alteração'], dayfirst=True, errors='coerce')

            # Limpeza e Filtros Básicos
            cols_filtro = ['Especialidade', 'Subespecialidade', 'Tipo do Documento', 'Tipo do Documento DCC', 'Subtipo DCC']
            for col in cols_filtro:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
                    df.loc[df[col].str.lower().isin(['nan', 'none', '0', '', ' ']), col] = ""
            status_validos = [
                'Aprovado', 'Aprovado com Comentários', 'Para Assinatura', 
                'Não Aprovado', 'Em Processo', 'Para Análise', 
                'Cancelado', 'Informativo' 
            ]
            df = df[df['Status'].str.strip().isin(status_validos)].copy()

            # Normalização de Datas Antigas (Regra 19/08/24)
            data_corte = pd.to_datetime('2024-08-19')
            mask_antigo_processo = (df['Data_Obj'] < data_corte) & (df['Status'] == 'Em Processo')
            df.loc[mask_antigo_processo, 'Status'] = 'Em Processo (CMI)'
            mask_antigo_analise = (df['Data_Obj'] < data_corte) & (df['Status'] == 'Para Análise')
            df.loc[mask_antigo_analise, 'Status'] = 'Em Processo'
            df = df.sort_values(by=['Tracking ID', 'Data_Obj'], ascending=[True, True])
            # 2. Algoritmo de Ciclos (Transposição)
            ciclos_consolidados = []
            timeline_events = [] # Para o gráfico de curva diária
            for tracking_id, grupo in df.groupby('Tracking ID'):
                grupo = grupo.reset_index(drop=True)

                # Propagação do Código Itaipu (O mais recente vale para todos)
                codigos_encontrados = grupo['No. do Documento'].replace('', pd.NA).dropna()
                cod_itaipu_final = codigos_encontrados.iloc[-1] if not codigos_encontrados.empty else ""

                # Metadados estáticos (pegos da última linha)
                meta = grupo.iloc[-1]

                # Variáveis de Estado para o Loop
                ultimo_retorno_data = None # Para calcular delay CMI
                ciclo_itaipu_atual = None # Dicionário temporário
                for idx, row in grupo.iterrows():
                    status = row['Status']
                    data = row['Data_Obj']
                    revisao = row['Revisão']

                    if pd.isna(data): continue
                    # A. Identificou ENVIO (Início Itaipu / Fim CMI)
                    if status == 'Em Processo':
                        # Se tinha ciclo Itaipu aberto anterior sem fechar, fecha forçado (erro de fluxo) ou ignora
                        # Vamos assumir novo envio = novo ciclo

                        # 1. Calcula Delay CMI (Tempo desde o último retorno até este envio)
                        dias_cmi = 0
                        status_prazo_cmi = "N/A"
                        prazo_cmi = 15 # Regra padrão

                        if ultimo_retorno_data:
                            dias_corridos_cmi = (data - ultimo_retorno_data).days
                            atraso_real_cmi = max(0, dias_corridos_cmi - prazo_cmi)

                            # Registra na timeline para gráfico (Período que ficou com CMI)
                            timeline_events.append({
                                'Responsavel': 'CMI',
                                'Inicio': ultimo_retorno_data,
                                'Fim': data,
                                'Prazo': prazo_cmi,
                                'Tracking ID': tracking_id
                            })
                            dias_cmi = dias_corridos_cmi

                        # 2. Abre Ciclo Itaipu
                        prazo_itaipu = 30 if self.normalizar_revisao(revisao) == self.normalizar_revisao('0A') else 15

                        ciclo_itaipu_atual = {
                            'Tracking ID': tracking_id,
                            'codigo itaipu': cod_itaipu_final,
                            'Codigo CMI': row.get('Controle do Emissor', ''),
                            'Titulo': row.get('Título', ''),
                            'Especialidade': row.get('Especialidade', ''),
                            'Subespecialidade': row.get('Subespecialidade', ''),
                            'Tipo de Documento DCC': row.get('Tipo do Documento DCC', ''),
                            'Subtipo DCC': row.get('Subtipo DCC', ''),
                            'Tipo de Documento': row.get('Tipo do Documento', ''),
                            'Revisão': revisao,
                            'Data de envio': data,
                            'Status': status, # Em Processo
                            'Data de retorno': None,
                            'Status de retorno': None,
                            'Dias CMI (Pré-Envio)': dias_cmi if ultimo_retorno_data else None,
                            'Prazo Itaipu': prazo_itaipu
                        }
                    # B. Identificou RETORNO (Fim Itaipu)
                    elif status in ['Aprovado', 'Aprovado com Comentários', 'Para Assinatura', 'Não Aprovado']:
                        if ciclo_itaipu_atual:
                            ciclo_itaipu_atual['Data de retorno'] = data
                            ciclo_itaipu_atual['Status de retorno'] = status

                            # Registra timeline Itaipu
                            timeline_events.append({
                                'Responsavel': 'Itaipu',
                                'Inicio': ciclo_itaipu_atual['Data de envio'],
                                'Fim': data,
                                'Prazo': ciclo_itaipu_atual['Prazo Itaipu'],
                                'Tracking ID': tracking_id
                            })

                            ciclos_consolidados.append(ciclo_itaipu_atual)
                            ciclo_itaipu_atual = None # Fecha ciclo

                        # Marca data para contar tempo do CMI no próximo
                        ultimo_retorno_data = data
                # C. Checa se ficou algum ciclo Itaipu aberto (Documento atualmente com Itaipu)
                if ciclo_itaipu_atual:
                    ciclos_consolidados.append(ciclo_itaipu_atual)
                    # Timeline aberta (vai até hoje)
                    timeline_events.append({
                        'Responsavel': 'Itaipu',
                        'Inicio': ciclo_itaipu_atual['Data de envio'],
                        'Fim': pd.Timestamp.now(),
                        'Prazo': ciclo_itaipu_atual['Prazo Itaipu'],
                        'Tracking ID': tracking_id
                    })
                # D. Checa se ficou ciclo CMI aberto (Documento atualmente conosco para correção)
                elif ultimo_retorno_data:
                    # Se o último evento foi um retorno e não teve envio posterior -> Está com CMI
                    timeline_events.append({
                        'Responsavel': 'CMI',
                        'Inicio': ultimo_retorno_data,
                        'Fim': pd.Timestamp.now(),
                        'Prazo': 15,
                        'Tracking ID': tracking_id
                    })
            # 3. Gerar DataFrame Final (Formatado)
            df_final = pd.DataFrame(ciclos_consolidados)

            # --- Exportação Excel Formatado ---
            path_excel = "base_ciclos_consolidada.xlsx"

            # Mapeamento de colunas final
            colunas_ordenadas = [
                'codigo itaipu', 'Codigo CMI', 'Titulo', 'Especialidade', 'Subespecialidade',
                'Tipo de Documento DCC', 'Subtipo DCC', 'Tipo de Documento', 'Revisão',
                'Data de envio', 'Status', 'Data de retorno', 'Status de retorno', 'Dias CMI (Pré-Envio)'
            ]
            # Garante que as colunas existem (caso dataframe vazio)
            for c in colunas_ordenadas:
                if c not in df_final.columns: df_final[c] = ""

            df_export = df_final[colunas_ordenadas].copy()

            # Formatação de Datas para String (DD/MM/AAAA) para o Excel ficar bonito
            for col_data in ['Data de envio', 'Data de retorno']:
                df_export[col_data] = df_export[col_data].apply(lambda x: x.strftime('%d/%m/%Y') if pd.notnull(x) else "")
            # Salva Excel com Openpyxl para aplicar estilos
            df_export.to_excel(path_excel, index=False, sheet_name="Ciclos")

            wb = openpyxl.load_workbook(path_excel)
            ws = wb.active

            # Configuração de Larguras (Solicitado)
            larguras = {
                "codigo itaipu": 26.27, "No. do Documento": 26.27, # Mapeando variações
                "Codigo CMI": 24.09, "Controle do Emissor": 24.09,
                "Revisão": 10.18,
                "Data de envio": 19.18, "Data de retorno": 19.18,
                "Status": 17, "Status de retorno": 17,
                "Titulo": 76, "Título": 76,
                "Tipo de Documento": 23.27, "Tipo do Documento": 23.27,
                "Especialidade": 30.09,
                "Subespecialidade": 34.45,
                "Tipo de Documento DCC": 23.67, "Tipo do Documento DCC": 23.67,
                "Subtipo DCC": 23.67
            }

            # Aplica formatação
            from openpyxl.styles import Alignment, Font
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions

            for col_idx, col_cells in enumerate(ws.columns, 1):
                col_letter = openpyxl.utils.get_column_letter(col_idx)
                header_val = ws.cell(row=1, column=col_idx).value

                # Aplica largura
                if header_val in larguras:
                    ws.column_dimensions[col_letter].width = larguras[header_val]

                # Wrap text em tudo
                for cell in col_cells:
                    cell.alignment = Alignment(wrap_text=True, vertical='center')
                    if cell.row == 1:
                        cell.font = Font(bold=True)

            wb.save(path_excel)
            # 4. Processamento da Timeline (Para o Gráfico de Curva)
            # Salva num CSV separado para o Streamlit ler rápido
            df_timeline = pd.DataFrame(timeline_events)
            df_timeline.to_csv("dados_timeline.csv", index=False)

            return True, df_final
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Erro: {str(e)}"
    def obter_snapshot_status(self, df_historico_doc, data_corte):
        """
        Retorna (Status Raw, Status Real, Revisao, Data) de um documento considerando apenas
        o histórico existente até a data_corte, lidando com revisões canceladas (Terminated).
        """
        # Filtra histórico até a data (Viagem no Tempo)
        df_cut = df_historico_doc[df_historico_doc['Data_Obj'] <= data_corte].copy()

        # CORREÇÃO: Adequando o retorno de segurança para devolver os 4 valores esperados
        if df_cut.empty:
            return "N/A", "NÃO EMITIDO", "-", pd.NaT
        df_cut['Versão_Int'] = pd.to_numeric(df_cut['Versão'], errors='coerce').fillna(0)
        # Loop de "Limpeza Temporal": garante que vamos ignorar revisões canceladas no passado
        while not df_cut.empty:
            # Ordena pela MAIOR VERSÃO primeiro (garantia de pegar o topo daquele momento)
            df_cut = df_cut.sort_values(by=['Versão_Int', 'Data_Obj'], ascending=[False, False])

            linha_topo = df_cut.iloc[0]
            status_rev = str(linha_topo.get("Status da Revisão", "")).lower()
            revisao_topo = str(linha_topo.get("Revisão", "")).strip()
            if "terminated" in status_rev:
                rev_norm = self.normalizar_revisao(revisao_topo)
                # Se for maior que 0A, excluímos a revisão inteira e deixamos o loop rodar de novo
                if rev_norm > self.normalizar_revisao("0A"):
                    df_cut = df_cut[df_cut["Revisão"].str.strip() != revisao_topo]
                else:
                    # Se cancelou a primeira revisão da vida útil, ele volta a ser "Não Emitido"
                    df_cut = df_cut.iloc[0:0] 
            else:
                # Se NÃO é terminated, achamos o "Current Histórico" válido! Quebra o loop.
                break
        # Se após limparmos os Terminateds a tabela esvaziou
        if df_cut.empty:
            return "N/A", "NÃO EMITIDO", "-", pd.NaT
        # Pegamos os dados finais do topo real consolidado
        linha_vencedora = df_cut.iloc[0]
        status_raw = str(linha_vencedora.get('Status', ''))
        revisao_final = str(linha_vencedora.get('Revisão', '')).strip()
        data_final = linha_vencedora.get('Data_Obj', pd.NaT)

        # O histórico df_cut já está limpo (sem revisões futuras e sem as canceladas desse período)
        status_real = self.calcular_status_real(df_cut, revisao_final)

        return status_raw, status_real, revisao_final, data_final
    def calcular_mudancas_periodo(self, path_mapping, sheet_map, path_aconex, sheet_aconex, data_ini_str, data_fim_str, cols_config, agrupador_escolhido="Grupo", tipo_visao="Efetiva"):
        try:
            # 1. Datas
            try:
                dt_ini = pd.to_datetime(data_ini_str, dayfirst=True)
                dt_fim = pd.to_datetime(data_fim_str, dayfirst=True)
                dt_fim = dt_fim.replace(hour=23, minute=59, second=59)
                dt_corte_antes = dt_ini - pd.Timedelta(seconds=1) 
            except:
                return False, "Erro data", 0
            # 2. Carregar Mapeamento (USANDO A LINHA DE CABEÇALHO CORRETA)
            # cols_config['header_row'] vem da MappingView, que já sabe onde está o cabeçalho (ex: linha 5)
            # O Pandas usa base 0, e o openpyxl base 1. Geralmente MappingView.row_header é base 1.
            # Se row_header for 6 (Excel), no pandas header deve ser 5.
            header_idx = cols_config.get('header_row', 0)
            if header_idx > 0: header_idx -= 1 
            df_map = pd.read_excel(path_mapping, sheet_name=sheet_map, header=header_idx, dtype=str).fillna('')

            # 3. Carregar Histórico e Criar Vínculos Inteligentes
            df_hist = pd.read_excel(path_aconex, sheet_name=sheet_aconex, dtype=str)
            df_hist['Data_Obj'] = pd.to_datetime(df_hist['Data de Alteração'], dayfirst=True, errors='coerce')
            df_hist = df_hist.dropna(subset=['Data_Obj'])

            # Normaliza colunas chave para Upper
            if 'Tracking ID' in df_hist.columns:
                df_hist['Tracking ID'] = df_hist['Tracking ID'].astype(str).str.strip().str.upper()

            df_hist['No. do Documento'] = df_hist['No. do Documento'].astype(str).str.strip().str.upper()
            # A. Agrupa o histórico pelo TRACKING ID (A chave imutável)
            # Se não tiver Tracking ID, usa o próprio Doc Number como fallback
            hist_by_tracking = {}
            map_doc_to_tracking = {} # Dicionário para descobrir o Tracking ID através do Nome
            # Primeiro, se existe a coluna Tracking ID, usamos ela para agrupar
            tem_tracking = 'Tracking ID' in df_hist.columns
            if tem_tracking:
                for tracking_id, group in df_hist.groupby('Tracking ID'):
                    hist_by_tracking[tracking_id] = group

                    # Mapeia TODOS os nomes de documentos que aparecem nesse grupo para este Tracking ID
                    # Assim, se eu buscar pelo nome Velho ou Novo, caio no mesmo Tracking ID
                    nomes_nesse_grupo = group['No. do Documento'].unique()
                    for nome in nomes_nesse_grupo:
                        map_doc_to_tracking[nome] = tracking_id
            else:
                # Fallback: Se não tem coluna Tracking ID, agrupa por documento mesmo
                for doc_no, group in df_hist.groupby('No. do Documento'):
                    hist_by_tracking[doc_no] = group
                    map_doc_to_tracking[doc_no] = doc_no
            arvore_mudancas = {}
            total_mudancas = 0
            # 4. Usar nomes de colunas fornecidos pelo usuário
            col_doc = cols_config.get('doc', 'N° ITAIPU')
            if agrupador_escolhido == "Sistema":
                col_agrupador = cols_config.get('sistema', 'SISTEMA')
            else:
                col_agrupador = cols_config.get('grupo', 'GRUPO')
            col_nivel = cols_config.get('nivel', 'NÍVEL')
            col_titulo = cols_config.get('titulo', 'DESCRIÇÃO DO DOCUMENTO')
            # Verifica se a coluna Doc existe mesmo
            if col_doc not in df_map.columns:
                return False, f"Coluna '{col_doc}' não encontrada.", 0
            col_pred = cols_config.get('predecessor', 'PREDECESSOR')
            # --- [NOVO] O PENTE FINO DA MEMÓRIA NO DELTA ---
            planilhas_vip = set()
            for _, row in df_map.iterrows():
                if str(row.get(col_nivel, '')).strip() == '3':
                    if 'PLANILHA' in str(row.get(col_titulo, '')).upper():
                        cod = str(row.get(col_doc, '')).strip().upper()
                        if cod: planilhas_vip.add(cod)

            docs_restritos = set()
            if planilhas_vip:
                for _, row in df_map.iterrows():
                    if str(row.get(col_nivel, '')).strip() == '4':
                        pred = str(row.get(col_pred, '')).strip().upper()
                        if pred in planilhas_vip:
                            cod = str(row.get(col_doc, '')).strip().upper()
                            if cod: docs_restritos.add(cod)
            # -------------------------------------------------
            for idx, row in df_map.iterrows():
                raw_doc = str(row.get(col_doc, '')).strip()
                if not raw_doc: continue

                doc_key = raw_doc.upper()
                is_restrito = doc_key in docs_restritos # Identifica se sofre a regra de Obras

                # 1. Descobre qual é o Tracking ID desse documento
                tracking_id = map_doc_to_tracking.get(doc_key)

                if tracking_id is None: 
                    df_doc = None
                else:
                    df_doc = hist_by_tracking.get(tracking_id)
                if df_doc is None: continue
                # EXTRAÇÃO DAS 4 VARIÁVEIS DA MÁQUINA DO TEMPO
                status_raw_antes, status_real_antes, rev_antes, data_antes = self.obter_snapshot_status(df_doc, dt_corte_antes)
                status_raw_depois, status_real_depois, rev_depois, data_depois = self.obter_snapshot_status(df_doc, dt_fim)
                # --- APLICAÇÃO DO STATUS EFETIVO ---
                if is_restrito:
                    status_efetivo_antes = self.calcula_status_consolidado_estrito(status_real_antes, status_real_antes)
                    status_efetivo_depois = self.calcula_status_consolidado_estrito(status_real_depois, status_real_depois)
                else:
                    status_efetivo_antes = status_real_antes
                    status_efetivo_depois = status_real_depois
                # =======================================================
                # O NOVO TRIGGER DUAL-ENGINE
                # =======================================================
                mudou = False

                if tipo_visao == "Efetiva":
                    # Visão Executiva: Só importa se o Status Consolidado/Efetivo mudou
                    if status_efetivo_antes != status_efetivo_depois:
                        mudou = True
                else:
                    # Visão Bruta: Importa se a Data de Tramitação mudou (Avançou uma casa no histórico)
                    if pd.isna(data_antes) and pd.notna(data_depois):
                        mudou = True # O documento nasceu no período
                    elif pd.notna(data_antes) and pd.notna(data_depois) and data_antes != data_depois:
                        mudou = True # Houve nova tramitação
                    elif status_efetivo_antes != status_efetivo_depois:
                        mudou = True # Fallback de segurança

                if mudou:
                    total_mudancas += 1

                    valor_agrupador = str(row.get(col_agrupador, f'SEM {agrupador_escolhido.upper()}')).strip()
                    nivel = str(row.get(col_nivel, 'SEM NÍVEL')).strip()
                    titulo = str(row.get(col_titulo, '')).strip()

                    # Formatação segura das datas para texto
                    dt_antes_str = data_antes.strftime('%d/%m/%y') if pd.notna(data_antes) else "-"
                    dt_depois_str = data_depois.strftime('%d/%m/%y') if pd.notna(data_depois) else "-"
                    item_dado = {
                        'doc': raw_doc,
                        'titulo': titulo,
                        'nivel': nivel,
                        'grupo': valor_agrupador, 
                        'raw_antes': status_raw_antes,
                        'real_antes': status_efetivo_antes, 
                        'raw_depois': status_raw_depois,
                        'real_depois': status_efetivo_depois,
                        # NOVOS DADOS PARA A INTERFACE BRUTA
                        'rev_antes': rev_antes,
                        'data_antes': dt_antes_str,
                        'rev_depois': rev_depois,
                        'data_depois': dt_depois_str
                    }
                    if valor_agrupador not in arvore_mudancas: arvore_mudancas[valor_agrupador] = {}
                    if nivel not in arvore_mudancas[valor_agrupador]: arvore_mudancas[valor_agrupador][nivel] = []
                    arvore_mudancas[valor_agrupador][nivel].append(item_dado)

            return True, arvore_mudancas, total_mudancas
        except Exception as e:
            return False, f"Erro: {str(e)}", 0
    def gerar_relatorio_avanco(self, caminho_arquivo, aba, progress_callback=None):
        try:
            if progress_callback: progress_callback("Lendo arquivo completo...", 0.1)

            # Lemos tudo como string para evitar perdas de formatação
            df = pd.read_excel(caminho_arquivo, sheet_name=aba, dtype=str)

            # Adicionei 'Tracking ID' e 'Versão' nas colunas obrigatórias, pois são o motor dessa nova lógica
            cols_obrigatorias = ["No. do Documento", "Revisão", "Status", "Tipo do Documento", 
                                 "Current", "Data de Alteração", "Título", "Status da Revisão", 
                                 "Tracking ID", "Versão"]

            if not all(col in df.columns for col in cols_obrigatorias):
                return False, f"Colunas obrigatórias faltando. Verifique se 'Tracking ID' e 'Versão' existem."
            # Funções Auxiliares
            def normalizar_texto(texto):
                if not isinstance(texto, str): return str(texto)
                nfkd = unicodedata.normalize('NFKD', texto)
                palavra_sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)])
                return palavra_sem_acento.upper().strip()
            # ==============================================================================
            # FASE 0: TRATAMENTO DO "TERMINATED" (A LÓGICA NOVA)
            # ==============================================================================
            if progress_callback: progress_callback("Processando lógica de Terminated...", 0.2)
            # 1. Identificar quem são os "Problemáticos" (Current=True E Terminated)
            # Normaliza colunas para garantir o match
            mask_current = df['Current'].astype(str).str.strip().str.lower() == 'true'
            mask_terminated = df['Status da Revisão'].astype(str).str.strip().str.lower().str.contains('terminated')

            # Dataframe só com os Tracking IDs e as Revisões que devem morrer
            # Ex: Tracking ID: 12345, Revisão: 0C
            df_to_kill = df.loc[mask_current & mask_terminated, ['Tracking ID', 'Revisão']].drop_duplicates()
            if not df_to_kill.empty:
                # Criamos uma chave única combinada para facilitar a exclusão em massa
                # Chave = "ID_REVISAO"
                df['temp_key'] = df['Tracking ID'].astype(str) + "_" + df['Revisão'].astype(str)
                keys_to_kill = df_to_kill['Tracking ID'].astype(str) + "_" + df_to_kill['Revisão'].astype(str)

                # Exclui TODAS as linhas que tenham essa combinação de ID e Revisão
                # Ou seja, matamos a revisão 0C inteira do documento, sobrando a 0B, 0A...
                df = df[~df['temp_key'].isin(keys_to_kill)].drop(columns=['temp_key'])
            # ==============================================================================
            # FASE 1: SELEÇÃO DA "LINHA DA VERDADE" (FALLBACK)
            # ==============================================================================
            # Agora que removemos os terminated, precisamos descobrir qual é a linha atual
            # para cada documento (Tracking ID). A regra é: Maior Versão > Maior Data.
            # Converter Versão para número para ordenar corretamente (10 > 9, mas "9" > "10" em texto)
            df['Versão_Int'] = pd.to_numeric(df['Versão'], errors='coerce').fillna(0)

            # Converter Data para garantir ordenação secundária
            df['Data_Temp'] = pd.to_datetime(df['Data de Alteração'], dayfirst=True, errors='coerce')
            # Ordena: Por ID, depois Versão (Maior pro Menor), depois Data (Mais recente)
            df = df.sort_values(by=['Tracking ID', 'Versão_Int', 'Data_Temp'], ascending=[True, False, False])
            # O PULO DO GATO: Remove duplicatas de Tracking ID mantendo o primeiro (o mais recente/maior versão)
            df = df.drop_duplicates(subset=['Tracking ID'], keep='first')
            # ==============================================================================
            # FASE 2: LIMPEZA E FILTROS (REGRAS ANTIGAS)
            # ==============================================================================
            if progress_callback: progress_callback("Aplicando filtros de limpeza...", 0.4)
            # 2.1 Limpeza de Revisões (Regex)
            def revisao_valida(rev):
                rev = str(rev).strip().upper()
                if re.search(r'[A-Z]{2}', rev) or re.search(r'[^A-Z0-9]', rev):
                    return False
                return True
            df = df[df['Revisão'].apply(revisao_valida)]
            # 2.2 Filtro de Status Válidos
            status_validos = [
                'Anulado', 'Aprovado', 'Aprovado com Comentários', 'Cancelado', 
                'Em Processo', 'Informativo', 'Não Aprovado', 
                'Para Análise', 'Para Assinatura', 'Para Informação'
            ]
            df = df[df['Status'].str.strip().isin(status_validos)]
            # 2.3 Remover Lixo (RDI, Docs específicos)
            df = df[~df['No. do Documento'].str.strip().str.upper().str.startswith("RDI")]

            docs_lixo = ["ESCRITÓRIO CMI", "FORNECEDOR ZEI-GE ITP", "NEE-CF-U1_U18A-A_D-EL06125-M3-TEL"]
            df = df[~df['No. do Documento'].str.strip().str.upper().isin(docs_lixo)]
            # 2.4 Tipos Indesejados
            df['Temp_Tipo_Check'] = df['Tipo do Documento'].apply(normalizar_texto)
            tipos_excluir_norm = ["MODELO", "DOCUMENTO DE REFERENCIA", "CONTRACTOR DOCUMENTS", "INSPECAO", "DISPOSICAO DE CAMPO"]
            df = df[~df['Temp_Tipo_Check'].isin(tipos_excluir_norm)]
            # ==============================================================================
            # FASE 3: ENRIQUECIMENTO E REGRAS DE NEGÓCIO
            # ==============================================================================
            if progress_callback: progress_callback("Formatando relatório final...", 0.8)
            # Tratamento de Data Final
            # Nota: Usamos 'Data_Temp' que já criamos antes para evitar refazer to_datetime
            df = df.dropna(subset=['Data_Temp'])

            # Regra de Mudança de Status pela Data
            data_corte = pd.to_datetime("2024-08-18")
            mask_mudanca_status = (df['Data_Temp'] > data_corte) & (df['Status'] == 'Em Processo')
            df.loc[mask_mudanca_status, 'Status'] = 'Para Análise'
            # Colunas Calculadas
            df['Empresa'] = np.where(df['Status'] == 'Para Análise', 'IB', 'CMI')

            # --- [NOVA REGRA DE SLA] 30 dias para Rev 0A, 15 dias para o resto ---
            mask_0a = df['Revisão'].astype(str).str.strip().str.upper() == '0A'
            dias_prazo = np.where(mask_0a, 30, 15)

            # Soma os dias dinamicamente usando pd.to_timedelta (vetorizado para ser instantâneo)
            df['Data Devolução'] = (df['Data_Temp'] + pd.to_timedelta(dias_prazo, unit='D')).dt.strftime('%d/%m/%Y')

            df['Data de Alteração'] = df['Data_Temp'].dt.strftime('%d/%m/%Y')
            # --- NORMALIZAÇÃO DE TIPOS (Lógica Mantida) ---
            df['Temp_Tipo'] = df['Tipo do Documento'].apply(normalizar_texto)
            df['Temp_Titulo'] = df['Título'].apply(normalizar_texto)
            df['Temp_DCC'] = df.get('Subtipo DCC', '').astype(str).apply(normalizar_texto)
            df['Temp_Tipo_DCC'] = df.get('Tipo do Documento DCC', '').astype(str).apply(normalizar_texto)
            # Regras Prioridade 1
            df.loc[df['Temp_Tipo'] == 'DOCUMENTO TECNICO', 'Tipo do Documento'] = 'Técnico'
            df.loc[df['Temp_Tipo'] == 'MANAGEMENT DOCUMENT', 'Tipo do Documento'] = 'Gerenciamento'
            # Regras Prioridade 2 (Gerenciamento)
            termos_gerenciamento = ["PLANO DE EXECUCAO", "PLANO DE MIGRACAO", "PLANO DE COMISSIONAMENTO", 
                                    "PLANO DE DESCOMISSIONAMENTO", "PLANO DE DESMONTAGEM"]
            regex_titulos = '|'.join([re.escape(t) for t in termos_gerenciamento])

            mask_ger = df['Temp_Titulo'].str.contains(regex_titulos, regex=True) | \
                       (df['Temp_Tipo_DCC'] == 'DOCUMENTACAO TECNICA E DE GESTAO')
            df.loc[mask_ger, 'Tipo do Documento'] = 'Gerenciamento'
            # Regras Prioridade 3 (Chefões)
            mask_ws = df['Temp_Titulo'].str.contains("WORKSTATEMENT", na=False) | df['Temp_DCC'].str.contains("WORKSTATEMENT", na=False)
            df.loc[mask_ws, 'Tipo do Documento'] = 'WORKSTATEMENT'
            mask_crit = df['Temp_Titulo'].str.contains("CRITERIO", regex=True) | df['Temp_DCC'].str.contains("CRITERIO", regex=True)
            df.loc[mask_crit, 'Tipo do Documento'] = 'Critério'
            # ==============================================================================
            # SAÍDA
            # ==============================================================================
            df.rename(columns={'Fonte': 'Fonte da revisão'}, inplace=True)

            colunas_finais = [
                'No. do Documento', 'Controle do Emissor', 'Título', 'Tipo do Documento',
                'Revisão', 'Status', 'Data de Alteração', "Status da Revisão", 'Fonte da revisão', 
                'Empresa', 'Data Devolução'
            ]

            cols_existentes = [c for c in colunas_finais if c in df.columns]
            df_final = df[cols_existentes].copy()
            if progress_callback: progress_callback("Concluído.", 1.0)

            return True, df_final
        except Exception as e:
            # traceback.print_exc() # Útil para debug no terminal
            return False, f"Erro ao gerar relatório: {str(e)}"

    def filtrar_historico_por_titulo(self, df_historico, texto_filtro):
        """
        Mantém no DataFrame apenas as linhas cujo Título contém o texto_filtro.
        A comparação é insensível a maiúsculas/minúsculas e acentos.
        """
        if df_historico.empty or not texto_filtro:
            return df_historico
        # Função interna para normalizar (remove acentos e põe em upper)
        def normalizar(txt):
            if not isinstance(txt, str): return str(txt)
            nfkd = unicodedata.normalize('NFKD', txt)
            return u"".join([c for c in nfkd if not unicodedata.combining(c)]).upper().strip()
        termo_busca = normalizar(texto_filtro)
        # Cria uma máscara booleana: True para linhas onde o título contém o termo
        mask = df_historico['Título'].apply(lambda x: termo_busca in normalizar(x))

        # Retorna apenas as linhas sobreviventes
        return df_historico[mask].copy()
    def gerar_dataset_dashboard(self, df_bruto):
        if df_bruto.empty: return pd.DataFrame()
        # --- LISTAS DE CONTROLE ---
        status_validos = [
            'Anulado', 'Aprovado', 'Aprovado com Comentários', 'Cancelado', 
            'Em Processo', 'Informativo', 'Não Aprovado', 'Para Análise', 
            'Para Aprovação', 'Para Assinatura', 'Para Informação'
        ]

        # NOVO FILTRO DE TIPOS
        tipos_validos = ['Documento Técnico', 'Management Document']
        df = df_bruto.copy()
        # 1. FILTROS BÁSICOS (Lixaria Grossa)

        # Filtra Status da Revisão (Terminated)
        if 'Status da Revisão' in df.columns:
            df = df[df['Status da Revisão'].astype(str).str.strip() != 'Terminated']

        # Filtra Status Válidos
        df = df[df['Status'].isin(status_validos)]
        # [NOVO] Filtra Tipo do Documento
        # Verifica se a coluna existe para não quebrar o código
        col_tipo = 'Tipo do Documento'
        if col_tipo in df.columns:
            df = df[df[col_tipo].isin(tipos_validos)]
        # 2. Limpeza Técnica (Revisão e Datas)
        df['Revisão'] = df['Revisão'].astype(str).str.upper().str.replace('R', '', regex=False).str.strip()
        df = df[df['Revisão'].str.len() <= 2]
        df['Data de Alteração'] = pd.to_datetime(df['Data de Alteração'], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['Data de Alteração'])
        df['Versão_Int'] = pd.to_numeric(df['Versão'], errors='coerce').fillna(0)
        # 3. Regras de Negócio Temporais (Corte 19/08/2024)
        data_corte = pd.Timestamp("2024-08-19")
        # Regra do Passado (Separação Interno vs Envio)
        mask_proc_antigo = (df['Data de Alteração'] <= data_corte) & (df['Status'] == 'Em Processo')
        df.loc[mask_proc_antigo, 'Status'] = 'Em Processo (CMI)'
        mask_analise_antigo = (df['Data de Alteração'] <= data_corte) & (df['Status'] == 'Para Análise')
        df.loc[mask_analise_antigo, 'Status'] = 'Em Processo'
        # Limpeza do Futuro
        mask_lixo_futuro = (df['Data de Alteração'] > data_corte) & (df['Status'] == 'Para Análise')
        df = df[~mask_lixo_futuro]
        # --- REGRAS CIRÚRGICAS PARA O STATUS "PARA APROVAÇÃO" ---
        mask_para_aprovacao = df['Status'] == 'Para Aprovação'

        # Exceção 1: Planilhas de Comissionamento -> Salvamos transformando em "Para Assinatura"
        mask_comissionamento = df['Título'].str.contains(r'PLANILHA[S]? DE COMISSIONAMENTO', case=False, na=False)
        df.loc[mask_para_aprovacao & mask_comissionamento, 'Status'] = 'Para Assinatura'
        # Exceção 2 (COMENTADA): Documento Específico -> Salvamos transformando em "Em Processo"
        # Descomente e altere 'PALAVRA_CHAVE_AQUI' quando lembrar o título exato
        # mask_doc_especifico = df['Título'].str.contains('PALAVRA_CHAVE_AQUI', case=False, na=False)
        # df.loc[mask_para_aprovacao & mask_doc_especifico, 'Status'] = 'Em Processo'

        # O EXTERMÍNIO: Tudo o que sobrou com o nome "Para Aprovação" (não caiu nas exceções) é descartado.
        # Assim não conta atraso nem para Itaipu, nem para CMI.
        df = df[df['Status'] != 'Para Aprovação']
       # 4. Ordenação (Preparação para Deduplicação)
        # Mais recente e maior versão no topo. 
        # REMOVIDO o 'Status' para a ordem alfabética não matar a linha do tempo!
        df = df.sort_values(
            by=['Tracking ID', 'Revisão', 'Data de Alteração', 'Versão_Int'], 
            ascending=[True, True, False, False]
        )
        # =========================================================
        # 4.5. [NOVO] INJEÇÃO DE METADADOS (SOBRESCRIÇÃO ABSOLUTA)
        # =========================================================
        cols_meta = ['Especialidade', 'Subespecialidade', 'Tipo do Documento DCC', 'Subtipo DCC']
        cols_presentes = [c for c in cols_meta if c in df.columns]

        if cols_presentes:
            import numpy as np
            df[cols_presentes] = df[cols_presentes].replace(r'^\s*$', np.nan, regex=True)

            # Agrupa por documento, pega a ÚLTIMA linha que tem dado válido (iloc[-1]) e SOBRESCREVE todas as revisões do grupo
            for col in cols_presentes:
                df[col] = df.groupby('Tracking ID')[col].transform(
                    lambda x: x.dropna().iloc[-1] if not x.dropna().empty else np.nan
                )

            df[cols_presentes] = df[cols_presentes].fillna("")
        # =========================================================

        # 5. LIMPEZA FINAL (Lógica IDA vs VOLTA)
        # TIME 1: ENVIOS (Apenas 'Em Processo' limpo)
        df_envios = df[df['Status'] == 'Em Processo'].copy()
        df_envios = df_envios.drop_duplicates(subset=['Tracking ID', 'Revisão'], keep='first')
        # TIME 2: RETORNOS (Tudo que não contém a palavra "Em Processo")
        # Isso impede que o "Em Processo (CMI)" seja lido como um retorno do cliente
        df_retornos = df[~df['Status'].str.contains('Em Processo', case=False, na=False)].copy()
        df_retornos = df_retornos.drop_duplicates(subset=['Tracking ID', 'Revisão'], keep='first')
        # Junta tudo
        df_final = pd.concat([df_envios, df_retornos])
        # Ordenação final para visualização
        df_final = df_final.sort_values(by=['Tracking ID', 'Revisão', 'Data de Alteração'])
        return df_final
    def gerar_excel_historico_formatado(self, df_limpo, caminho_saida):
        """
        Recebe o DataFrame limpo (gerado por gerar_dataset_dashboard), 
        pivota para 1 linha por revisão e salva um Excel formatado.
        """
        if df_limpo.empty:
            return False, "DataFrame vazio."
        # 1. PREPARAÇÃO DAS COLUNAS ESTÁTICAS (METADADOS)
        # Para garantir que temos os dados cadastrais (Título, Tipo, etc), pegamos uma base única por revisão.
        # Usamos 'keep=last' para pegar os metadados mais recentes disponíveis naquela revisão.
        colunas_estaticas = [
            'No. do Documento', 'Controle do Emissor', 'Tracking ID', 'Título', 
            'Tipo do Documento', 'Especialidade', 'Subespecialidade', 
            'Tipo do Documento DCC', 'Subtipo DCC', 'Versão', 'Current', 'Revisão'
        ]

        # Filtra apenas as colunas que realmente existem no df para não dar erro
        cols_existentes = [c for c in colunas_estaticas if c in df_limpo.columns]
        df_base = df_limpo.drop_duplicates(subset=['Tracking ID', 'Revisão'], keep='last')[cols_existentes].copy()
        # 2. PIVOTEAMENTO (Separar Ida e Volta)

        # Time Envio (Ida)
        df_envio = df_limpo[df_limpo['Status'] == 'Em Processo'][['Tracking ID', 'Revisão', 'Data de Alteração', 'Status']].copy()
        df_envio = df_envio.rename(columns={'Data de Alteração': 'Data de Envio', 'Status': 'Status Envio'})

        # Time Retorno (Volta)
        df_retorno = df_limpo[df_limpo['Status'] != 'Em Processo'][['Tracking ID', 'Revisão', 'Data de Alteração', 'Status']].copy()
        df_retorno = df_retorno.rename(columns={'Data de Alteração': 'Data de Retorno', 'Status': 'Status Retorno'})
        # 3. MERGE (Junta tudo na df_base)
        df_final = pd.merge(df_base, df_envio, on=['Tracking ID', 'Revisão'], how='left')
        df_final = pd.merge(df_final, df_retorno, on=['Tracking ID', 'Revisão'], how='left')
        # Preenche vazios de Status para ficar bonito
        # Se não tem envio (caso raro de erro na base), deixamos NaT/Vazio
        # Se não tem retorno, é pq ainda está com o cliente (deixamos vazio)

        # 4. ORDENAÇÃO INTELIGENTE (0A antes de 0 -> 0Z)
        # Cria uma coluna auxiliar para ordenação
        def criar_sort_key(rev):
            rev = str(rev).strip().upper()
            # Se a revisão for apenas numérica (ex: "0", "1"), adiciona "Z" para ir pro final (ex: "0Z")
            # Assim "0A" vem antes de "0Z" na ordem alfabética
            if rev.isdigit():
                return rev + 'Z'
            return rev
        df_final['Sort_Key'] = df_final['Revisão'].apply(criar_sort_key)

        # Ordena por Tracking ID e pela Chave Auxiliar
        df_final = df_final.sort_values(by=['Tracking ID', 'Sort_Key'])

        # Remove a coluna auxiliar
        df_final = df_final.drop(columns=['Sort_Key'])
        # 5. REORDENAÇÃO FINAL DAS COLUNAS (Conforme pedido)
        colunas_finais = [
            "No. do Documento", "Controle do Emissor", "Tracking ID", "Título", 
            "Tipo do Documento", "Especialidade", "Subespecialidade", 
            "Tipo do Documento DCC", "Subtipo DCC", "Versão", "Current", "Revisão", 
            "Data de Envio", "Status Envio", "Data de Retorno", "Status Retorno"
        ]

        # Garante que só selecionamos o que existe (segurança)
        cols_export = [c for c in colunas_finais if c in df_final.columns]
        df_final = df_final[cols_export]
        # --- [NOVO] LIMPEZA DAS DATAS (Remove o 00:00:00 antes de exportar) ---
        for col_date in ['Data de Envio', 'Data de Retorno']:
            if col_date in df_final.columns:
                df_final[col_date] = pd.to_datetime(df_final[col_date]).dt.strftime('%d/%m/%Y')
        # --- PARTE VISUAL (EXCEL WRITER) ---
        try:
            with pd.ExcelWriter(caminho_saida, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Histórico')

                # Pega os objetos do openpyxl para formatar
                workbook = writer.book
                worksheet = writer.sheets['Histórico']
                # Configuração de Larguras (Dicionário de Configuração)
                larguras = {
                    "No. do Documento": 27,
                    "Controle do Emissor": 27,
                    "Tracking ID": 27,
                    "Título": 60,
                    "Tipo do Documento": 20,
                    "Especialidade": 27,
                    "Subespecialidade": 33,
                    "Tipo do Documento DCC": 25,
                    "Subtipo DCC": 25,
                    "Versão": 8,
                    "Current": 8,
                    "Revisão": 10,
                    "Data de Envio": 15,
                    "Status Envio": 25,
                    "Data de Retorno": 15,
                    "Status Retorno": 25
                }
                from openpyxl.styles import Alignment
                # Itera sobre as colunas para aplicar largura e Wrap Text
                for i, col in enumerate(df_final.columns):
                    col_letter = chr(65 + i) # A, B, C... (funciona bem até 26 colunas)
                    # Se passar de Z, o openpyxl tem função utils, mas aqui vamos simples
                    # Melhor usar o iterador do worksheet:

                # Iteração segura pelas colunas do Excel
                for col_idx, column_cells in enumerate(worksheet.columns, 1):
                    # Pega o nome do cabeçalho (valor da primeira célula)
                    header_val = column_cells[0].value

                    # Define largura se estiver no dicionário
                    if header_val in larguras:
                        # Ajusta largura da coluna (letra da coluna)
                        col_letter = column_cells[0].column_letter
                        worksheet.column_dimensions[col_letter].width = larguras[header_val]
                    # Aplica Wrap Text em TODAS as células da coluna (menos cabeçalho se quiser, mas aqui vai em tudo)
                    for cell in column_cells:
                        cell.alignment = Alignment(wrap_text=True, vertical='center')

                # Aplica o AutoFiltro no cabeçalho
                worksheet.auto_filter.ref = worksheet.dimensions
            return True, f"Arquivo gerado com sucesso: {caminho_saida}"
        except Exception as e:
            return False, f"Erro ao salvar Excel: {e}"

    def preparar_tabela_wide(self, df_limpo):
        """
        Gera a base de dados MESTRA para o Dashboard (em memória).
        Esta função replica EXATAMENTE a lógica de dados do relatório Excel,
        incluindo todas as colunas de metadados para filtros.
        """
        if df_limpo.empty: return pd.DataFrame()
        # 1. DEFINIÇÃO DE COLUNAS (METADADOS COMPLETOS)
        colunas_estaticas = [
            'No. do Documento',      # Máscara Principal
            'Controle do Emissor',   # Segunda Estampa (Importante)
            'Tracking ID',           # Elo de ligação
            'Título',
            'Tipo do Documento',     # Filtro Macro
            'Especialidade',         # Filtro Novo
            'Subespecialidade',      # Filtro Novo
            'Tipo do Documento DCC', # Filtro Novo
            'Subtipo DCC',           # Filtro Novo
            'Versão', 
            'Current', 
            'Revisão'
        ]

        cols_existentes = [c for c in colunas_estaticas if c in df_limpo.columns]

        df_base = df_limpo.sort_values(by=['Data de Alteração']).drop_duplicates(
            subset=['Tracking ID', 'Revisão'], keep='last'
        )[cols_existentes].copy()
        # 2. PIVOTEAMENTO (Separação dos Times: Envio vs Retorno)

        # Time Envio (Ida - Status 'Em Processo')
        df_envio = df_limpo[df_limpo['Status'] == 'Em Processo'][
            ['Tracking ID', 'Revisão', 'Data de Alteração', 'Status']
        ].rename(columns={'Data de Alteração': 'Data Envio', 'Status': 'Status Envio'})

        df_retorno = df_limpo[df_limpo['Status'] != 'Em Processo'][
            ['Tracking ID', 'Revisão', 'Data de Alteração', 'Status']
        ].rename(columns={'Data de Alteração': 'Data Retorno', 'Status': 'Status Retorno'})
        df_wide = pd.merge(df_base, df_envio, on=['Tracking ID', 'Revisão'], how='left')
        df_wide = pd.merge(df_wide, df_retorno, on=['Tracking ID', 'Revisão'], how='left')
        def criar_sort_key(rev):
            rev = str(rev).strip().upper()
            if rev.isalpha(): return '00_' + rev       # A, B -> 00_A (Primeiro)
            if not rev.isdigit(): return '10_' + rev   # 0A, 1B -> 10_0A (Segundo)
            return '20_' + rev.zfill(3)                # 0, 1 -> 20_000 (Terceiro)
        df_wide['Sort_Key'] = df_wide['Revisão'].apply(criar_sort_key)

        # Ordena pelo Tracking ID e pela sequência lógica da revisão
        df_wide = df_wide.sort_values(by=['Tracking ID', 'Sort_Key'])

        # Remove a chave auxiliar (não precisamos dela no Dash)
        df_wide = df_wide.drop(columns=['Sort_Key'])
        def calc_sla(row):
            rev = str(row['Revisão']).strip().upper()
            # Regra: Revisão 0A = 30 dias, qualquer outra = 15 dias
            if rev == '0A': return 30
            return 15
        df_wide['SLA_Itaipu'] = df_wide.apply(calc_sla, axis=1)

        return df_wide

    def calcular_kpis_revisoes(self, df_wide):
        """
        Calcula a média de revisões necessárias para atingir certos status.
        Retorna um dicionário com os dois indicadores.
        """
        if df_wide.empty:
            return {'ciclo_aprovacao': 0, 'ciclo_completo': 0}
        # Status considerados "Aprovado Tecnicamente" (Libera a obra)
        status_aprovacao_tecnica = [
            'APROVADO', 'APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA', 
            'APPROVED', 'APPROVED WITH COMMENTS' # Caso tenha inglês
        ]

        # Status "Final" (Fecha o ciclo no Aconex)
        status_final = ['APROVADO', 'APPROVED']
        kpi_aprovacao = []
        kpi_final = []
        # Agrupa por Tracking ID para analisar a vida do documento
        # Ordena por Sort_Key (ordem de revisão: 0A, 0B, 0, 1...) se existir, ou Data
        for _, grupo in df_wide.groupby('Tracking ID'):
            grupo = grupo.sort_values('Data Envio')
            revisoes = grupo.to_dict('records')

            # KPI 1: Quantas revisões até a primeira aprovação técnica?
            contagem_tec = 0
            encontrou_tec = False

            # KPI 2: Quantas revisões até o Aprovado Final?
            contagem_fin = 0
            encontrou_fin = False
            for i, rev in enumerate(revisoes):
                st = str(rev.get('Status Retorno', '')).upper()

                # Conta revisões (Índice + 1)

                if not encontrou_tec:
                    if st in status_aprovacao_tecnica:
                        kpi_aprovacao.append(i + 1) # Rev 0A é a 1ª, Rev 0B é a 2ª...
                        encontrou_tec = True

                if not encontrou_fin:
                    if st in status_final:
                        kpi_final.append(i + 1)
                        encontrou_fin = True

        # Calcula Médias
        media_aprovacao = sum(kpi_aprovacao) / len(kpi_aprovacao) if kpi_aprovacao else 0
        media_final = sum(kpi_final) / len(kpi_final) if kpi_final else 0
        return {
            'ciclo_aprovacao': round(media_aprovacao, 1),
            'ciclo_completo': round(media_final, 1)
        }
    def gerar_curva_atrasos(self, df_wide, limite_dias=None, ignorar_parciais=False):
        """
        Gera um DataFrame Time Series (Dia a Dia) com a evolução do Backlog.

        Args:
            df_wide: DataFrame processado (uma linha por revisão).
            limite_dias (int, optional): Se fornecido, limita o número de dias acumulados 
                                         para o cálculo da média (Slicer/Capping).
        """
        if df_wide.empty: 
            return pd.DataFrame()
        # Garante datas datetime
        if 'Data Envio' not in df_wide.columns or df_wide['Data Envio'].isnull().all():
            return pd.DataFrame()
        # 1. Define o Horizonte de Tempo (Inicio do Projeto até Hoje)
        data_min = df_wide['Data Envio'].min()
        data_max = pd.Timestamp.now().normalize()

        if pd.isnull(data_min): 
            return pd.DataFrame()
        dias_projeto = pd.date_range(start=data_min, end=data_max, freq='D')
        # Lista de intervalos de atraso
        # Formato: {'inicio': dt, 'fim': dt, 'resp': 'ITAIPU'/'CMI'}
        intervalos_atraso = []
        # ---------------------------------------------------------------------
        # A. CÁLCULO ATRASO ITAIPU (Aprovação)
        # ---------------------------------------------------------------------
        # Regra: Se (Data Envio + SLA) < (Data Retorno ou Hoje)
        for _, row in df_wide.iterrows():
            if pd.isnull(row['Data Envio']): continue

            # Prazo limite
            sla = row.get('SLA_Itaipu', 15) # Default 15 se não tiver coluna
            dt_limite = row['Data Envio'] + pd.Timedelta(days=sla)

            # Data final real (Retorno ou Hoje)
            dt_fim_real = row['Data Retorno'] if pd.notnull(row['Data Retorno']) else data_max

            if dt_fim_real > dt_limite:
                inicio = dt_limite + pd.Timedelta(days=1)
                fim = min(dt_fim_real, data_max) # Não projeta futuro

                if fim >= inicio:
                    intervalos_atraso.append({'inicio': inicio, 'fim': fim, 'resp': 'ITAIPU'})
        # ---------------------------------------------------------------------
        # B. CÁLCULO ATRASO CMI (Reemissão)
        # ---------------------------------------------------------------------

        # --- [NOVA LÓGICA DE STATUS "FINALIZADOS"] ---
        status_morte_subita = ['APROVADO', 'CANCELADO', 'ANULADO', 'APPROVED']
        if ignorar_parciais:
            status_morte_subita.extend(['APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA', 'APPROVED WITH COMMENTS'])

        # Regra: Se (Data Retorno Anterior + 15 dias) < (Data Envio Próxima ou Hoje)
        # Ordena para garantir sequência cronológica das revisões
        df_ordenado = df_wide.sort_values(by=['Tracking ID', 'Data Envio'])

        for tracking_id, grupo in df_ordenado.groupby('Tracking ID'):
            revisoes = grupo.to_dict('records')

            # 1. Entre revisões (Janela Deslizante)
            for i in range(len(revisoes) - 1):
                atual = revisoes[i]
                proxima = revisoes[i+1]

                # Se atingiu a condição de parada estipulada pelo botão, mata o atraso!
                st = str(atual.get('Status Retorno', '')).upper()
                if st in status_morte_subita: continue

                if pd.isnull(atual['Data Retorno']): continue

                dt_limite = atual['Data Retorno'] + pd.Timedelta(days=15)

                # Se demorou mais que 15 dias para emitir a próxima
                if proxima['Data Envio'] > dt_limite:
                    intervalos_atraso.append({
                        'inicio': dt_limite + pd.Timedelta(days=1), 
                        'fim': proxima['Data Envio'], 
                        'resp': 'CMI'
                    })

            # 2. Última revisão (Pendente atual)
            ultimo = revisoes[-1]
            st_ult = str(ultimo.get('Status Retorno', '')).upper()
            status_encerramento = status_morte_subita + ['NAN', 'NONE', ''] # Junta a regra dinâmica com os vazios

            # Se tem data de retorno E NÃO foi finalizado/aprovado na regra estipulada
            if pd.notnull(ultimo['Data Retorno']) and st_ult not in status_encerramento:
                dt_limite = ultimo['Data Retorno'] + pd.Timedelta(days=15)

                # Se já estourou o prazo hoje
                if data_max > dt_limite:
                    intervalos_atraso.append({
                        'inicio': dt_limite + pd.Timedelta(days=1), 
                        'fim': data_max, 
                        'resp': 'CMI'
                    })
        # ---------------------------------------------------------------------
        # C. CONSOLIDAÇÃO DIÁRIA (COM SLICER/CAP)
        # ---------------------------------------------------------------------
        # Estrutura: mapa[data]['ITAIPU'] = {'qtd': 0, 'soma_dias': 0}
        mapa_datas = {d: {'ITAIPU': {'qtd': 0, 'soma': 0}, 'CMI': {'qtd': 0, 'soma': 0}} for d in dias_projeto}
        for item in intervalos_atraso:
            # Gera range de dias desse atraso específico
            dias_intervalo = pd.date_range(start=item['inicio'], end=item['fim'], freq='D')

            # Contador de dias corridos desse atraso
            contador = 1

            for dia in dias_intervalo:
                if dia in mapa_datas:
                    resp = item['resp']

                    # --- LÓGICA DO SLICER ---
                    dias_a_computar = contador
                    if limite_dias is not None:
                        # Se passou do limite, usa o teto (ex: 200) para a média, 
                        # mas continua contando 1 na quantidade
                        if dias_a_computar > limite_dias:
                            dias_a_computar = limite_dias

                    mapa_datas[dia][resp]['qtd'] += 1
                    mapa_datas[dia][resp]['soma'] += dias_a_computar

                contador += 1
        # Transforma dicionário em DataFrame Final
        dados_finais = []
        for dia in dias_projeto:
            d_it = mapa_datas[dia]['ITAIPU']
            d_cmi = mapa_datas[dia]['CMI']

            # Calcula médias (proteção contra divisão por zero)
            media_it = (d_it['soma'] / d_it['qtd']) if d_it['qtd'] > 0 else 0
            media_cmi = (d_cmi['soma'] / d_cmi['qtd']) if d_cmi['qtd'] > 0 else 0

            dados_finais.append({
                'Data': dia,
                'Qtd_Itaipu': d_it['qtd'],
                'Media_Dias_Itaipu': round(media_it, 1),
                'Qtd_CMI': d_cmi['qtd'],
                'Media_Dias_CMI': round(media_cmi, 1)
            })

        return pd.DataFrame(dados_finais)
    def gerar_evolucao_prazos(self, df_wide, freq='ME', limite_dias=None):
        """
        Gera séries temporais de média de dias para:
        1. Itaipu Rev 0A (Ref: Data Retorno)
        2. Itaipu Demais (Ref: Data Retorno)
        3. CMI Reemissão (Ref: Data Envio da atual) - Exclui Rev 0A
        """
        if df_wide.empty: return {}
        # Garante datetime
        df = df_wide.copy()
        for col in ['Data Envio', 'Data Retorno']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        # Dicionário para armazenar os DataFrames resultantes
        series_temporais = {}
        # --- A. PREPARAÇÃO ITAIPU (0A e Demais) ---
        # Base: Documentos que já retornaram
        df_it = df.dropna(subset=['Data Envio', 'Data Retorno']).copy()
        df_it['Dias'] = (df_it['Data Retorno'] - df_it['Data Envio']).dt.days
        df_it = df_it[df_it['Dias'] >= 0] # Remove inconsistências
        # Aplica Limitador (Slicer) - Capping
        if limite_dias:
            df_it['Dias'] = df_it['Dias'].clip(upper=limite_dias)
        # Separa 0A vs Demais
        # Normaliza a revisão para string, maiúsculo e remove espaços para garantir o filtro
        mask_0a = df_it['Revisão'].astype(str).str.upper().str.strip() == '0A'

        # Agrupa Temporalmente (Pela Data de Retorno - quando o ciclo fechou)
        # 1. ITAIPU 0A
        df_0a = df_it[mask_0a].set_index('Data Retorno').resample(freq).agg(
            Media_Dias=('Dias', 'mean'),
            Qtd_Docs=('Dias', 'count')
        )
        # Remove períodos sem documentos para não quebrar o gráfico (gaps)
        series_temporais['ITAIPU_0A'] = df_0a[df_0a['Qtd_Docs'] > 0]
        # 2. ITAIPU DEMAIS
        df_demais = df_it[~mask_0a].set_index('Data Retorno').resample(freq).agg(
            Media_Dias=('Dias', 'mean'),
            Qtd_Docs=('Dias', 'count')
        )
        series_temporais['ITAIPU_DEMAIS'] = df_demais[df_demais['Qtd_Docs'] > 0]
        # --- B. PREPARAÇÃO CMI (Reemissão) ---
        # CORREÇÃO: Removemos a ordenação por 'Data Envio'. 
        # Confiamos 100% na ordem cronológica de revisões entregue pelo 'preparar_tabela_wide'.
        df_cmi = df.copy()

        # Pega a data de retorno da revisão ANTERIOR (Shift)
        df_cmi['Dt_Retorno_Ant'] = df_cmi.groupby('Tracking ID')['Data Retorno'].shift(1)

        # Filtra: Tem que ter envio atual e retorno anterior válido
        df_cmi = df_cmi.dropna(subset=['Data Envio', 'Dt_Retorno_Ant'])

        # EXCLUSÃO DA REVISÃO 0A (Regra de Negócio: Não conta tempo de CMI na primeira emissão)
        df_cmi = df_cmi[df_cmi['Revisão'].astype(str).str.upper().str.strip() != '0A']
        df_cmi['Dias'] = (df_cmi['Data Envio'] - df_cmi['Dt_Retorno_Ant']).dt.days
        df_cmi = df_cmi[df_cmi['Dias'] >= 0]
        # Aplica Limitador
        if limite_dias:
            df_cmi['Dias'] = df_cmi['Dias'].clip(upper=limite_dias)
        # Agrupa Temporalmente (Pela Data de Envio - quando o CMI entregou)
        df_cmi_agg = df_cmi.set_index('Data Envio').resample(freq).agg(
            Media_Dias=('Dias', 'mean'),
            Qtd_Docs=('Dias', 'count')
        )
        series_temporais['CMI'] = df_cmi_agg[df_cmi_agg['Qtd_Docs'] > 0]
        return series_temporais

    def _converter_revisao_corella_logica(self, rev):
        """Converte revisão Corella (letras/traços) para números."""
        rev_str = str(rev).strip().upper()
        if rev_str == '-': return 1 
        if len(rev_str) == 1 and rev_str.isalpha(): return ord(rev_str) - 63
        return 0
    def ler_arquivo_corella_fiel(self, filepath):
        """Lê Corella (Excel ou XML). Mantido igual ao original."""
        if not filepath: return None, "Caminho vazio."
        df = None
        # 1. Tenta Excel Nativo
        try:
            df = pd.read_excel(filepath)
        except:
            pass
        # 2. Tenta Parser XML
        if df is None:
            try:
                tree = ET.parse(filepath)
                root = tree.getroot()
                xml_rows = [elem for elem in root.iter() if elem.tag.endswith('Row')]
                if not xml_rows: return None, "XML sem linhas."
                all_data = []
                for row in xml_rows:
                    row_data = []
                    cells = [elem for elem in row if elem.tag.endswith('Cell')]
                    for cell in cells:
                        data_node = next((child for child in cell if child.tag.endswith('Data')), None)
                        row_data.append(data_node.text if (data_node is not None and data_node.text) else "")
                    if any(row_data): all_data.append(row_data)
                if len(all_data) < 2: return None, "Dados insuficientes."
                max_cols = len(all_data[0])
                normalized_data = [r[:max_cols] + [""]*(max_cols - len(r)) for r in all_data]
                df = pd.DataFrame(normalized_data[1:], columns=normalized_data[0])
            except Exception as e:
                return None, f"Erro leitura Corella: {e}"
        # 3. Tratamento
        if df is not None:
            try:
                df.columns = [str(c).strip() for c in df.columns]
                if 'Revision' in df.columns:
                    df['Qtd_rev_corella'] = df['Revision'].apply(self._converter_revisao_corella_logica)
                else:
                    df['Qtd_rev_corella'] = 0 
                return df, None
            except Exception as e:
                return None, f"Erro tratamento Corella: {e}"
        return None, "Falha desconhecida."
    def ler_aconex_api_fiel(self, filepath, sheet_name=0):
        """
        Lê o arquivo da API procurando o cabeçalho 'Controle do Emissor'.
        Retorna o DataFrame bruto.
        """
        try:
            aba = sheet_name if sheet_name else 0

            # 1. Tenta ler primeiras 50 linhas para achar cabeçalho
            try:
                df_temp = pd.read_excel(filepath, sheet_name=aba, header=None, nrows=50)
            except:
                # Fallback: tenta primeira aba
                df_temp = pd.read_excel(filepath, sheet_name=0, header=None, nrows=50)
                aba = 0
            header_idx = -1
            # Palavras-chave da API
            keywords = ["CONTROLE DO EMISSOR", "TRACKING ID"]
            for idx, row in df_temp.iterrows():
                row_str = " ".join([str(x).upper() for x in row.values])
                if any(k in row_str for k in keywords):
                    header_idx = idx
                    break

            if header_idx == -1: 
                return None, f"Cabeçalho 'Controle do Emissor' não encontrado."

            # 2. Lê os dados
            # Se a aba foi identificada pelo fallback, usa 0, senão usa o nome/indice passado
            aba_load = 0 if aba == 0 else (sheet_name if sheet_name else 0)

            df = pd.read_excel(filepath, sheet_name=aba_load, header=header_idx)
            df.columns = [str(c).strip() for c in df.columns]

            return df, None
        except Exception as e:
            return None, f"Erro leitura Aconex: {e}"
    def _preparar_aconex_base(self, df_aconex, filtro_codigos="", filtro_docs_exatos=""):
        """
        Aplica filtros comuns (HNS, Documentos Exatos, Status, Limpeza de Revisão).
        Retorna DF limpo.
        """
        df = df_aconex.copy()
        # 1. Filtro de Códigos (Regex no Controle do Emissor) - MANTIDO
        if filtro_codigos:
            codigos = [c.strip().upper() for c in filtro_codigos.split(',') if c.strip()]
            if codigos:
                regex = '|'.join(codigos)
                if 'Controle do Emissor' in df.columns:
                    df = df[df['Controle do Emissor'].astype(str).str.contains(regex, case=False, na=False)]
        # NOVO: 1.5 Filtro de Documentos Exatos (Copiados do Excel)
        if filtro_docs_exatos:
            import re
            # Quebra o texto colado por linhas (\n), vírgulas ou ponto-e-vírgula e remove vazios
            docs_exatos = [d.strip().upper() for d in re.split(r'[\n,;]+', filtro_docs_exatos) if d.strip()]
            if docs_exatos and 'Controle do Emissor' in df.columns:
                # Filtra mantendo apenas os documentos que estão exatamente na lista colada
                df = df[df['Controle do Emissor'].astype(str).str.strip().str.upper().isin(docs_exatos)]
        # 2. Filtro de Status
        if 'Status' in df.columns:
            # Lista de status válidos
            STATUS_VALIDOS = ['Não Aprovado', 'Em Processo', 'Aprovado com Comentários', 'Para Assinatura', 'Aprovado', 'Para Informação']
            df = df[df['Status'].astype(str).str.strip().isin(STATUS_VALIDOS)]
        # 3. Limpeza de Revisão (Remove R e 3 digitos)
        if 'Revisão' in df.columns:
             df['Revisão'] = df['Revisão'].astype(str).str.strip().str.replace(r'^R', '', regex=True)
             df = df[df['Revisão'].str.len() != 3] # Remove 0AA, 1AB...
        return df
    def comparar_missing_docs_api(self, df_aconex, df_corella, filtro_codigos="", filtro_docs_exatos=""):
        """
        TASK 1: Faltantes.
        Lógica:
        1. Pega apenas Current == True no Aconex.
        2. Verifica se Controle do Emissor existe no Document Number do Corella.
        """
        # 1. Prepara base (Filtros de Status e Código)
        df_base = self._preparar_aconex_base(df_aconex, filtro_codigos, filtro_docs_exatos)

        # 2. Filtra CURRENT == TRUE (A fotografia atual)
        # Normaliza a coluna Current para string minúscula para garantir
        if 'Current' in df_base.columns:
            df_current = df_base[df_base['Current'].astype(str).str.lower() == 'true'].copy()
        else:
            return pd.DataFrame() # Sem coluna Current não dá para fazer
        # 3. Merge com Corella (Left Join)
        col_corella = 'Document Number' if 'Document Number' in df_corella.columns else df_corella.columns[0]

        df_merged = pd.merge(
            df_current,
            df_corella[[col_corella]],
            left_on='Controle do Emissor',
            right_on=col_corella,
            how='left',
            indicator=True
        )
        # 4. Pega quem sobro na esquerda (Aconex) e não achou na direita (Corella)
        df_missing = df_merged[df_merged['_merge'] == 'left_only'].copy()

        # Colunas para exportar (PT-BR)
        cols_export = ['Controle do Emissor', 'Título', 'Especialidade', 'Subespecialidade', 'Revisão', 'Status']
        cols_finais = [c for c in cols_export if c in df_missing.columns]

        return df_missing[cols_finais]
    def comparar_versoes_tracking_id(self, df_aconex, df_corella, filtro_codigos="", filtro_docs_exatos=""):
        """
        TASK 2: Comparação de Ciclos.
        Lógica:
        1. Corella -> Aconex (pelo Nome) -> Pega Tracking ID.
        2. Agrupa Aconex pelo Tracking ID (Histórico Completo).
        3. Compara contagens.
        """
        # 1. Prepara base Aconex (Limpa Status ruins, revisões internas, filtros HNS)
        df_aconex_clean = self._preparar_aconex_base(df_aconex, filtro_codigos, filtro_docs_exatos)
        # 2. Agrupamento Inteligente no Aconex (Tracking ID)
        # Queremos: Qtd de Revisões, Última Revisão, e o Controle do Emissor "Oficial" (do Current)

        # Passo 2a: Contagem por Tracking ID
        df_counts = df_aconex_clean.groupby('Tracking ID')['Revisão'].nunique().reset_index()
        df_counts.rename(columns={'Revisão': 'Qtd_Versoes_Aconex'}, inplace=True)

        # Passo 2b: Pegar metadados do documento vigente (Current=True) para ter o Nome correto
        if 'Current' in df_aconex_clean.columns:
            df_currents = df_aconex_clean[df_aconex_clean['Current'].astype(str).str.lower() == 'true'].copy()
            # Se tiver duplicidade de current (erro na base), remove duplicatas de tracking ID
            df_currents = df_currents.drop_duplicates(subset=['Tracking ID'])
        else:
            return pd.DataFrame()
        # Passo 2c: Junta Contagem com Metadados
        df_aconex_consolidado = pd.merge(df_currents, df_counts, on='Tracking ID', how='left')
        # 3. Prepara Corella
        col_corella = 'Document Number' if 'Document Number' in df_corella.columns else df_corella.columns[0]

        # 4. Merge Final: Corella x Aconex Consolidado
        # Usamos Inner Join pois queremos comparar apenas o que existe nos dois
        cols_corella_req = [col_corella, 'Revision', 'Qtd_rev_corella', 'State', 'Originator [...]']
        cols_corella_exist = [c for c in cols_corella_req if c in df_corella.columns]
        df_final = pd.merge(
            df_aconex_consolidado,
            df_corella[cols_corella_exist],
            left_on='Controle do Emissor', # Link pelo nome
            right_on=col_corella,
            how='inner'
        )
        # 5. Calcula Divergências
        df_divergencia = df_final[df_final['Qtd_Versoes_Aconex'] != df_final['Qtd_rev_corella']].copy()
        df_divergencia['Diferenca'] = df_divergencia['Qtd_Versoes_Aconex'] - df_divergencia['Qtd_rev_corella']

        # Seleciona colunas para relatorio
        cols_return = [
            'Controle do Emissor', 'Título', 'Especialidade', 'Subespecialidade',
            'Revisão', 'Qtd_Versoes_Aconex', # Dados Aconex
            'Revision', 'Qtd_rev_corella',   # Dados Corella
            'Diferenca', 'State', 'Originator [...]'
        ]
        # Filtra só as que existem
        cols_return = [c for c in cols_return if c in df_divergencia.columns]

        return df_divergencia[cols_return]

    def extrair_dados_mapeamento(self, path, sheet_name, col_cod='N° ITAIPU'):
        """Lê a planilha Mãe e retorna uma lista de dicionários mantendo a ordem exata."""
        try:
            # 1. Encontrar a linha do cabeçalho dinamicamente nas primeiras 10 linhas
            df_temp = pd.read_excel(path, sheet_name=sheet_name, nrows=10, header=None)
            header_idx = 0
            for i, row in df_temp.iterrows():
                if col_cod in row.values:
                    header_idx = i
                    break
            # 2. Ler o arquivo real a partir do cabeçalho encontrado
            df = pd.read_excel(path, sheet_name=sheet_name, header=header_idx)

            # 3. Limpeza: Remover linhas sem Nº Itaipu e preencher "vazios" com string vazia
            df = df.dropna(subset=[col_cod])
            df = df.fillna("")

            return df.to_dict('records'), True, "Dados da Mãe extraídos com sucesso."
        except Exception as e:
            return [], False, f"Erro ao extrair dados da Mãe: {e}"

    def calcular_status_real_modelo(self, df_tracking, revisao_current):
        """ Motor exclusivo para modelos BIM, baseado em Milestones (LOD) e varredura de Fantasmas. """
        if df_tracking.empty or not revisao_current:
            return "NÃO EMITIDO"

        # 1. Organiza o histórico de trás pra frente (do mais novo pro mais antigo)
        try:
            df_hist = df_tracking.copy()
            df_hist['Versão_Int'] = pd.to_numeric(df_hist['Versão'], errors='coerce').fillna(0)
            df_hist = df_hist.sort_values(by=['Versão_Int', 'Versão'], ascending=[False, False])
        except:
            df_hist = df_tracking
        validos_upper = [s.strip().upper() for s in self.status_modelos_validos]
        status_encontrado = None

        # 2. Regra do Fantasma: Coleta TODO o histórico válido (ignorando fantasmas)
        historico_valido = []
        for _, row in df_hist.iterrows():
            st_raw = str(row.get('Status', '')).strip().upper()
            if st_raw in validos_upper:
                historico_valido.append(st_raw)

        if not historico_valido:
            return "NÃO EMITIDO"

        status_mais_recente = historico_valido[0]
        status_final = status_mais_recente

        # 3. Regra de Bloqueio de Milestone (Milestone Lock)
        aprov_350_upper = [s.upper() for s in self.status_mod_aprov_350]
        aprov_300_upper = [s.upper() for s in self.status_mod_aprov_300]
        aprov_pre_upper = [s.upper() for s in self.status_mod_aprov_pre]

        fase_350_upper = aprov_350_upper + [s.upper() for s in self.status_mod_reprov_350 + self.status_mod_analise_350 + self.status_mod_inicial_350]
        fase_300_upper = aprov_300_upper + [s.upper() for s in self.status_mod_reprov_300 + self.status_mod_analise_300 + self.status_mod_inicial_300]
        fase_pre_upper = aprov_pre_upper + [s.upper() for s in self.status_mod_reprov_pre + self.status_mod_analise_pre + self.status_mod_inicial_pre]
        # Se estou em uma fase (ex: LOD 350) e já fui aprovado nela no passado, a aprovação congela e vence!
        if status_mais_recente in fase_350_upper:
            if any(st in aprov_350_upper for st in historico_valido):
                return "Aprovado - LOD 350"

        elif status_mais_recente in fase_300_upper:
            if any(st in aprov_300_upper for st in historico_valido):
                return "Aprovado - LOD 300"

        elif status_mais_recente in fase_pre_upper:
            if any(st in aprov_pre_upper for st in historico_valido):
                return "Aprovado - Fase Preliminar"
        # 4. Mapeia o status final para o Nível exato do Relatório
        if status_final in aprov_350_upper: return "Aprovado - LOD 350"
        if status_final in aprov_300_upper: return "Aprovado - LOD 300"
        if status_final in aprov_pre_upper: return "Aprovado - Fase Preliminar"

        if status_final in [s.upper() for s in self.status_mod_reprov_350]: return "Não Aprovado - LOD 350"
        if status_final in [s.upper() for s in self.status_mod_reprov_300]: return "Não Aprovado - LOD 300"
        if status_final in [s.upper() for s in self.status_mod_reprov_pre]: return "Não Aprovado - Fase Preliminar"

        if status_final in [s.upper() for s in self.status_mod_analise_350]: return "Em Análise - LOD 350"
        if status_final in [s.upper() for s in self.status_mod_analise_300]: return "Em Análise - LOD 300"
        if status_final in [s.upper() for s in self.status_mod_analise_pre]: return "Em Análise - Fase Preliminar"

        if status_final in [s.upper() for s in self.status_mod_inicial_350]: return "Emissão Inicial - LOD 350"
        if status_final in [s.upper() for s in self.status_mod_inicial_300]: return "Emissão Inicial - LOD 300"
        if status_final in [s.upper() for s in self.status_mod_inicial_pre]: return "Emissão Inicial - Fase Preliminar"

        if status_final in [s.upper() for s in self.status_mod_info]: return "Informativo"

        return "NÃO EMITIDO"
    def analisar_kpis_documento(self, df_tracking, status_real, revisao_atual, data_prevista):
        """
        Processa o histórico e gera os KPIs. Blindado contra ciclos internos (0AA)
        e sincronizado com a 'Data Última Emissão' do Mapeamento.
        """

        hoje = pd.Timestamp.now().normalize()
        res = {
            'dias_status': "", 'situacao_prazo': "-", 'dias_atraso': "",
            'total_ciclos': 0, 'ciclos_aprovar': 0, 'downgrade': "NÃO"
        }
        # =========================================================
        # 1. CENÁRIO: NÃO EMITIDO (Proteção 'Data não informada')
        # =========================================================
        if status_real == "NÃO EMITIDO":
            if pd.notna(data_prevista) and str(data_prevista).strip() != "":
                try:
                    dt_prev = pd.to_datetime(data_prevista, errors='coerce').normalize()
                    if pd.notna(dt_prev):
                        atraso = (hoje - dt_prev).days
                        res['dias_atraso'] = atraso
                        res['situacao_prazo'] = "Atrasado" if atraso > 0 else "No Prazo"
                    else:
                        res['situacao_prazo'] = "Data não informada"
                except:
                    res['situacao_prazo'] = "Data não informada"
            else:
                res['situacao_prazo'] = "Data não informada"
            return res
        # =========================================================
        # 2. LIMPEZA E PREPARAÇÃO DO HISTÓRICO
        # =========================================================
        df_clean = df_tracking.copy()
        if df_clean.empty: return res
        # --- 1º PASSO: Limpeza Absoluta da Coluna de Revisão ---
        # Garante que não haja espaços invisíveis antes do agrupamento
        df_clean['Revisão'] = df_clean['Revisão'].astype(str).str.upper().str.replace('R', '', regex=False).str.strip()

        # O PULO DO GATO: Extermina ciclos internos da CMI (ex: 0AA)
        df_clean = df_clean[df_clean['Revisão'].str.len() <= 2]
        # --- 2º PASSO: A LÓGICA DE EXTERMÍNIO INTELIGENTE (Terminated) ---
        # Transforma a 'Versão' em número para podermos comparar quem é maior
        df_clean['Versão_Int'] = pd.to_numeric(df_clean['Versão'], errors='coerce').fillna(0)

        mask_term = df_clean['Status da Revisão'].astype(str).str.lower().str.contains('terminated', na=False)

        # Descobre qual foi a VERSÃO MÁXIMA terminada para CADA revisão limpa
        max_term_por_rev = df_clean[mask_term].groupby('Revisão')['Versão_Int'].max()

        # Mapeia esse limite e aplica o filtro de sobrevivência
        df_clean['Max_Term_Versao'] = df_clean['Revisão'].map(max_term_por_rev).fillna(-1)
        df_clean = df_clean[df_clean['Versão_Int'] > df_clean['Max_Term_Versao']]

        if df_clean.empty: return res
        # --- 3º PASSO: Prepara as datas para a viagem no tempo ---
        df_clean['Data_Alter_Obj'] = pd.to_datetime(df_clean['Data de Alteração'], errors='coerce', dayfirst=True)
        df_clean = df_clean.dropna(subset=['Data_Alter_Obj']).sort_values('Data_Alter_Obj')
        # =========================================================
        # 3. CÁLCULO DE CICLOS E DOWNGRADE
        # =========================================================
        revisoes_unicas = df_clean['Revisão'].dropna().unique()
        res['total_ciclos'] = len(revisoes_unicas)
        # Adicionado 'APTO PARA FIRMA' conforme sua solicitação nas regras de sucesso
        status_sucesso = ['APROVADO', 'APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA', 'APPROVED', 'APPROVED WITH COMMENTS', 'INFORMATIVO', 'PARA INFORMAÇÃO', 'APTO PARA FIRMA']
        status_falha = ['NÃO APROVADO']
        status_cancelado = ['CANCELADO', 'ANULADO', 'ISSUED FOR ANNULMENT']
        # --- PARTE 1: Ciclos para Aprovar (Leitura Cronológica) ---
        ja_foi_aprovado = False
        revisoes_vistas = set()
        for _, row in df_clean.iterrows():
            st = str(row['Status']).strip().upper()
            rev = str(row['Revisão']).strip().upper()
            revisoes_vistas.add(rev)
            if not ja_foi_aprovado and st in status_sucesso:
                ja_foi_aprovado = True
                res['ciclos_aprovar'] = len(revisoes_vistas)
        # --- PARTE 2: A Nova Lógica Absoluta de Downgrade (Batalha de Versões) ---
        # Isola e formata a coluna inteira para busca de alta performance
        status_upper_series = df_clean['Status'].astype(str).str.strip().str.upper()

        # Filtra as linhas exatas onde ocorreram os sucessos e as falhas
        mask_sucesso = status_upper_series.isin(status_sucesso)
        mask_falha = status_upper_series.isin(status_falha)

        versoes_sucesso = df_clean.loc[mask_sucesso, 'Versão_Int']
        versoes_falha = df_clean.loc[mask_falha, 'Versão_Int']

        # Se o documento tem pelo menos um sucesso e pelo menos uma falha na história
        if not versoes_sucesso.empty and not versoes_falha.empty:
            primeira_aprovacao = versoes_sucesso.min()

            # Se existe QUALQUER falha ('NÃO APROVADO') com versão estritamente maior
            # que a versão da primeira aprovação, o Downgrade é carimbado.
            if (versoes_falha > primeira_aprovacao).any():
                res['downgrade'] = "SIM"
        # =========================================================
        # 4. VIAGEM NO TEMPO (SLAs E DATAS)
        # =========================================================

        status_real_limpo = str(status_real).strip().upper()

        # Se for um status de sucesso (Aprovado), limpa a cobrança visual.
        if status_real_limpo in status_sucesso:
            res['situacao_prazo'] = "Doc Aprovado"
            res['dias_status'] = ""
            res['dias_atraso'] = ""
            return res

        # NOVA REGRA: Se o documento morreu, zera a cobrança visual.
        if status_real_limpo in status_cancelado:
            res['situacao_prazo'] = "Doc Cancelado"
            res['dias_status'] = ""
            res['dias_atraso'] = ""
            return res
        if status_real_limpo == "EM PROCESSO":
            # BOLA COM A ITAIPU
            sla = 30 if str(revisao_atual).strip().upper() == '0A' else 15

            # SOLUÇÃO: Filtramos apenas pela Revisão Atual. Se o Mapeamento já disse que está 
            # "Em Processo", confiamos nisso e pegamos a data da última movimentação (max).
            df_rev = df_clean[df_clean['Revisão'].astype(str).str.strip().str.upper() == str(revisao_atual).strip().upper()]

            if not df_rev.empty:
                dt_ref = df_rev['Data_Alter_Obj'].max() # Pega a data exata da emissão mais recente
                dias = (hoje - dt_ref).days
                res['dias_status'] = dias
                res['dias_atraso'] = dias - sla
                res['situacao_prazo'] = "Atrasado" if res['dias_atraso'] > 0 else "No Prazo"

        else:
            # BOLA COM A CMI (Não Aprovado, etc)
            sla = 15

            # Correção sintaxe Pandas: .astype(str).str.strip().str.upper()
            df_retornos = df_clean[df_clean['Status'].astype(str).str.strip().str.upper().isin(status_sucesso + status_falha + status_cancelado)]

            if not df_retornos.empty:
                dt_ref = df_retornos['Data_Alter_Obj'].max()
                dias = (hoje - dt_ref).days
                res['dias_status'] = dias
                res['dias_atraso'] = dias - sla
                res['situacao_prazo'] = "Atrasado" if res['dias_atraso'] > 0 else "No Prazo"
        return res

    def calcular_atrasos_acumulados(self, df_tracking, status_real, data_prevista):
        """
        Calcula o Atraso Acumulado Bruto (sem banco de horas) da Itaipu e da CMI.
        Audita o histórico cronologicamente: Nascedouro, Ciclos de Análise e Retrabalhos.
        """
        hoje = pd.Timestamp.now().normalize()
        res = {'atraso_acumulado_itaipu': 0, 'atraso_acumulado_cmi': 0}

        status_real_limpo = str(status_real).strip().upper()
        status_sucesso = ['APROVADO', 'APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA', 'APPROVED', 'APPROVED WITH COMMENTS', 'INFORMATIVO', 'PARA INFORMAÇÃO']
        status_falha = ['NÃO APROVADO']
        status_cancelado = ['CANCELADO', 'ANULADO', 'ISSUED FOR ANNULMENT']

        # Status que exigem retrabalho da CMI
        status_exige_retrabalho = status_falha + ['APROVADO', 'APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA', 'APPROVED', 'APPROVED WITH COMMENTS']
        # =========================================================
        # PREPARAÇÃO (Matador de Zumbis e Limpeza - Mesma regra validada)
        # =========================================================
        df_clean = df_tracking.copy()
        if df_clean.empty and status_real_limpo != "NÃO EMITIDO": 
            return res
        if not df_clean.empty:
            df_clean['Revisão'] = df_clean['Revisão'].astype(str).str.upper().str.replace('R', '', regex=False).str.strip()
            df_clean = df_clean[df_clean['Revisão'].str.len() <= 2]
            df_clean['Versão_Int'] = pd.to_numeric(df_clean['Versão'], errors='coerce').fillna(0)
            mask_term = df_clean['Status da Revisão'].astype(str).str.lower().str.contains('terminated', na=False)
            max_term_por_rev = df_clean[mask_term].groupby('Revisão')['Versão_Int'].max()
            df_clean['Max_Term_Versao'] = df_clean['Revisão'].map(max_term_por_rev).fillna(-1)
            df_clean = df_clean[df_clean['Versão_Int'] > df_clean['Max_Term_Versao']]
            df_clean['Data_Alter_Obj'] = pd.to_datetime(df_clean['Data de Alteração'], errors='coerce', dayfirst=True)
            df_clean = df_clean.dropna(subset=['Data_Alter_Obj']).sort_values('Data_Alter_Obj')
            df_clean['Status_Upper'] = df_clean['Status'].astype(str).str.strip().str.upper()
        # =========================================================
        # MOMENTO A: O NASCEDOURO (Cobrança da Data Prevista - CMI)
        # =========================================================
        dt_prev = pd.NaT
        if pd.notna(data_prevista) and str(data_prevista).strip() != "":
            # Adicionamos dayfirst=True para corrigir o aviso (UserWarning)
            dt_prev = pd.to_datetime(data_prevista, errors='coerce', dayfirst=True)
            # Verificamos se a data não é nula (NaT) antes de aplicar o normalize
            if pd.notna(dt_prev):
                dt_prev = dt_prev.normalize()
        # CORREÇÃO: Evita o KeyError protegendo a busca da coluna caso o DataFrame venha vazio
        if not df_clean.empty and 'Revisão' in df_clean.columns:
            revisoes_cronologicas = df_clean['Revisão'].dropna().unique()
        else:
            revisoes_cronologicas = []
        if pd.notna(dt_prev):
            if df_clean.empty or status_real_limpo == "NÃO EMITIDO":
                # Documento não nasceu e já passou da data
                atraso_nasc = (hoje - dt_prev).days
                res['atraso_acumulado_cmi'] += max(0, atraso_nasc)
            elif len(revisoes_cronologicas) > 0:
                # Documento nasceu. Pega a ÚLTIMA data de 'Em Processo' da PRIMEIRA revisão.
                primeira_rev = revisoes_cronologicas[0]
                df_nasc = df_clean[(df_clean['Revisão'] == primeira_rev) & (df_clean['Status_Upper'] == 'EM PROCESSO')]
                if not df_nasc.empty:
                    data_nascimento = df_nasc['Data_Alter_Obj'].max() # CORREÇÃO: max() garante a última versão válida do envio
                    atraso_nasc = (data_nascimento - dt_prev).days
                    res['atraso_acumulado_cmi'] += max(0, atraso_nasc)
        if df_clean.empty:
            return res
        # =========================================================
        # MOMENTOS B e C: A LINHA DO TEMPO (Itaipu e CMI Retrabalho)
        # =========================================================
        documento_aprovado = False # A Bandeira que dita se a bola está na Via Crítica
        for i, rev in enumerate(revisoes_cronologicas):
            df_rev = df_clean[df_clean['Revisão'] == rev]

            # --- GATILHOS DA ITAIPU (Momento B) ---
            df_envio = df_rev[df_rev['Status_Upper'] == 'EM PROCESSO']
            if df_envio.empty:
                continue # Se a revisão não tem "Em Processo", é ruído. Ignora o ciclo.

            inicio_itaipu = df_envio['Data_Alter_Obj'].max() 
            df_veredito = df_rev[df_rev['Status_Upper'].isin(status_sucesso + status_falha)]

            fim_itaipu = None
            veredito_status = None

            if not df_veredito.empty:
                fim_itaipu = df_veredito['Data_Alter_Obj'].max() 
                veredito_status = df_veredito.loc[df_veredito['Data_Alter_Obj'].idxmax(), 'Status_Upper']
            elif status_real_limpo == "EM PROCESSO" and i == len(revisoes_cronologicas) - 1:
                fim_itaipu = hoje
            # Contabilidade Itaipu (Sem Banco de Horas)
            if fim_itaipu is not None:
                sla_itaipu = 30 if rev == '0A' else 15
                dias_itaipu = (fim_itaipu - inicio_itaipu).days

                # REGRA CONCEITUAL: Só cobra a Itaipu se o documento AINDA NÃO estava aprovado.
                # Nota: A Itaipu é cobrada pelo ciclo em que ELA DÁ a aprovação. 
                if not documento_aprovado:
                    res['atraso_acumulado_itaipu'] += max(0, dias_itaipu - sla_itaipu)
            # ATUALIZA A BANDEIRA DE ACORDO COM O VEREDITO DESTA REVISÃO
            if veredito_status in status_sucesso or veredito_status in status_cancelado:
                documento_aprovado = True   # Congela relógios
            elif veredito_status in status_falha:
                documento_aprovado = False  # Downgrade! Descongela relógios
            # --- GATILHOS DA CMI DE RETRABALHO (Momento C) ---
            # A CMI só é cobrada por retrabalho se o documento NÃO estiver aprovado (Bandeira Abaixada)
            if not documento_aprovado and veredito_status in status_falha:
                inicio_cmi = fim_itaipu
                fim_cmi = None

                if i + 1 < len(revisoes_cronologicas):
                    prox_rev = revisoes_cronologicas[i+1]
                    df_prox_envio = df_clean[(df_clean['Revisão'] == prox_rev) & (df_clean['Status_Upper'] == 'EM PROCESSO')]
                    if not df_prox_envio.empty:
                        fim_cmi = df_prox_envio['Data_Alter_Obj'].max() 

                if fim_cmi is None and status_real_limpo not in status_sucesso and status_real_limpo != "EM PROCESSO":
                    fim_cmi = hoje

                if fim_cmi is not None:
                    sla_cmi = 15
                    dias_cmi = (fim_cmi - inicio_cmi).days
                    res['atraso_acumulado_cmi'] += max(0, dias_cmi - sla_cmi)
        return res

    def auditar_fluxo_integracao(self, df_aconex_completo):
        """
        Audita quais documentos deveriam ter passado pela integração (Revisão 0AA) mas não passaram.
        Regras:
        1. Ser o documento atual (Current == True).
        2. Conter um dos DCCs alvos no "No. do Documento".
        3. Não possuir a revisão "0AA" em todo o seu histórico (agrupado pelo Tracking ID).
        """
        if df_aconex_completo is None or df_aconex_completo.empty:
            return pd.DataFrame()
        # Garante que não vamos alterar o dataframe original na memória
        df_base = df_aconex_completo.copy()
        # ---------------------------------------------------------
        # PASSO 1: FOTOGRAFIA ATUAL (Current == True)
        # ---------------------------------------------------------
        if 'Current' not in df_base.columns:
            return pd.DataFrame() # Falha segura se a base vier incorreta

        mask_current = df_base['Current'].astype(str).str.strip().str.lower() == 'true'
        df_current = df_base[mask_current].copy()
        # ---------------------------------------------------------
        # PASSO 2: FILTRO DA FAMÍLIA DCC
        # ---------------------------------------------------------
        dccs_validos = [
            'LB010', 'LB020', 'LC030', 'LC040', 'LC060', 'LC061', 'LC070',
            'LD010', 'LD020', 'LD040', 'LD050', 'LD051', 'LH011', 'LU010',
            'DC070', 'DC075', 'CC051', 'EC020', 'BD010', 'BD011', 'BD012',
            'BD013', 'BD014', 'BD015', 'BD016', 'BS020', 'BS110'
        ]
        # Cria uma string Regex no formato: 'LB010|LB020|LC030|...'
        # Isso faz o pandas procurar qualquer um desses termos na linha
        regex_dcc = '|'.join(dccs_validos)
        # Filtra mantendo apenas as linhas onde o "No. do Documento" contém algum dos DCCs
        mask_dcc = df_current['No. do Documento'].astype(str).str.contains(regex_dcc, case=False, na=False)
        df_alvo = df_current[mask_dcc].copy()
        if df_alvo.empty:
            return pd.DataFrame() # Nenhum documento se enquadrou nos DCCs
        # ---------------------------------------------------------
        # PASSO 3: PREPARAR O HISTÓRICO (Ordenação e Limpeza)
        # ---------------------------------------------------------
        df_base['Revisão_Limpa'] = df_base['Revisão'].astype(str).str.strip().str.upper()
        df_base['Versão_Int'] = pd.to_numeric(df_base['Versão'], errors='coerce').fillna(0)

        # O pulo do gato: ordenar do mais antigo pro mais novo para pegar o "Primeiro" e "Último" corretamente
        df_base = df_base.sort_values(by=['Tracking ID', 'Versão_Int'], ascending=[True, True])
        # ---------------------------------------------------------
        # PASSO 4: EXTRAÇÃO DOS MARCOS (0AA e 0A)
        # ---------------------------------------------------------
        # Isola as revisões 0AA e agrega pegando a primeira e última linha de cada documento
        df_0aa = df_base[df_base['Revisão_Limpa'] == '0AA']
        agg_0aa = df_0aa.groupby('Tracking ID').agg(
            Data_Primeiro_Envio_0AA=('Data de Alteração', 'first'),
            Status_Primeiro_Envio_0AA=('Status', 'first'),
            Data_Ultimo_Retorno_0AA=('Data de Alteração', 'last'),
            Status_Ultimo_Retorno_0AA=('Status', 'last')
        ).reset_index()
        # Isola as revisões 0A e faz o mesmo processo
        df_0a = df_base[df_base['Revisão_Limpa'] == '0A']
        agg_0a = df_0a.groupby('Tracking ID').agg(
            Data_Primeiro_Envio_0A=('Data de Alteração', 'first'),
            Status_Primeiro_Envio_0A=('Status', 'first'),
            Data_Ultimo_Retorno_0A=('Data de Alteração', 'last'),
            Status_Ultimo_Retorno_0A=('Status', 'last')
        ).reset_index()
        # ---------------------------------------------------------
        # PASSO 5: O VEREDITO (Merge Final)
        # ---------------------------------------------------------
        # Junta os agregados na nossa lista de documentos alvo (Current == True)
        df_final = df_alvo.merge(agg_0aa, on='Tracking ID', how='left')
        df_final = df_final.merge(agg_0a, on='Tracking ID', how='left')
        # Cria a coluna de Integração: Se tem data na primeira 0AA, é SIM, senão NÃO.
        df_final['INTEGRAÇÃO'] = np.where(df_final['Data_Primeiro_Envio_0AA'].notna(), 'SIM', 'NÃO')
        # ---------------------------------------------------------
        # SAÍDA FORMATADA E RENOMEADA
        # ---------------------------------------------------------
        colunas_relatorio = [
            'No. do Documento', 'Controle do Emissor', 'Título', 'INTEGRAÇÃO',
            'Data_Primeiro_Envio_0AA', 'Status_Primeiro_Envio_0AA', 
            'Data_Ultimo_Retorno_0AA', 'Status_Ultimo_Retorno_0AA',
            'Data_Primeiro_Envio_0A', 'Status_Primeiro_Envio_0A', 
            'Data_Ultimo_Retorno_0A', 'Status_Ultimo_Retorno_0A'
        ]

        colunas_existentes = [c for c in colunas_relatorio if c in df_final.columns]
        df_final = df_final[colunas_existentes].fillna("")
        # Renomeia as colunas para o padrão amigável solicitado para o Excel
        mapa_nomes = {
            'INTEGRAÇÃO': 'Integração',
            'Data_Primeiro_Envio_0AA': 'Data Envio 0AA',
            'Status_Primeiro_Envio_0AA': 'Status Envio 0AA',
            'Data_Ultimo_Retorno_0AA': 'Data Retorno 0AA',
            'Status_Ultimo_Retorno_0AA': 'Status Retorno 0AA',
            'Data_Primeiro_Envio_0A': 'Data Envio 0A',
            'Status_Primeiro_Envio_0A': 'Status Envio 0A',
            'Data_Ultimo_Retorno_0A': 'Data Retorno 0A',
            'Status_Ultimo_Retorno_0A': 'Status Retorno 0A'
        }
        df_final = df_final.rename(columns=mapa_nomes)
        return df_final