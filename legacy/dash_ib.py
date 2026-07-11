import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from data_manager import DataManager
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUMEN, dbc.icons.BOOTSTRAP])
app.title = "Aconex Analytics"
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* --- ESTILO GERAL DE SCROLL --- */
            ::-webkit-scrollbar { width: 8px; }
            ::-webkit-scrollbar-track { background: #1A252F; }
            ::-webkit-scrollbar-thumb { background: #5D6D7E; border-radius: 4px; }
            ::-webkit-scrollbar-thumb:hover { background: #3498db; }
            /* --- DROPDOWN CONTROL (A CAIXA ONDE VOCÊ CLICA) --- */
            .Select-control {
                background-color: #FFFFFF !important;
                border: 1px solid #BDC3C7 !important;
                border-radius: 4px !important;
            }
            /* Texto selecionado (Tags) */
            .Select-value {
                background-color: #ECF0F1 !important;
                border: 1px solid #BDC3C7 !important;
                color: #2C3E50 !important;
                margin: 2px !important;
            }
            .Select-value-label { color: #2C3E50 !important; }
            /* --- O MENU FLUTUANTE (CORREÇÃO DE SOBREPOSIÇÃO) --- */

            /* Container da lista de opções */
            .Select-menu-outer {
                z-index: 9999 !important;
                box-shadow: 0 10px 30px rgba(0,0,0,0.4) !important;
                border: 1px solid #34495E !important;
                background-color: #ffffff !important;
            }
            /* --- AS OPÇÕES (AQUI ESTÁ A MÁGICA VISUAL) --- */
            .Select-option {
                color: #2C3E50 !important;
                padding: 10px 12px !important;
                border-bottom: 1px solid #F2F3F4;
                background-color: white !important;
                transition: all 0.2s ease-in-out;

                /* Truque para cortar texto longo sem quebrar layout */
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
                max-width: 100%;
            }
            /* ESTADO HOVER: O EFEITO "CARD FLUTUANTE" */
            .Select-option:hover {
                /* Quebra o texto para mostrar tudo */
                white-space: normal !important; 
                overflow: visible !important;
                height: auto !important;

                /* Cores e Destaque */
                background-color: #2C3E50 !important; /* Fundo Escuro */
                color: #F1C40F !important; /* Texto Amarelo Ouro */

                /* Efeito de Pop-out */
                cursor: pointer;
                position: relative; /* Garante que fique acima dos outros */
                z-index: 10000 !important; /* Força ficar no topo */

                /* Bordas e Sombras para dar profundidade */
                border-left: 5px solid #3498db;
                box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                transform: scale(1.01); /* Leve zoom */
            }
            /* Garante que o input de texto e textareas fiquem bonitos */
            .form-control:focus {
                border-color: #3498db;
                box-shadow: 0 0 0 0.2rem rgba(52, 152, 219, 0.25);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''
# Paleta de Cores Base
CORES = {
    'sidebar': '#1A252F',
    'background': '#F0F2F5',
    'card_bg': '#FFFFFF',
    'text_primary': '#2C3E50',
    'Barra_Envio': '#2980b9',   
    'Barra_Retorno': '#27ae60', 
    'Linha_Acumulado': '#8e44ad',
    'Delay_Itaipu': '#d35400',
    'Delay_CMI': '#c0392b'
}
# Variável Global
df_wide_global = pd.DataFrame()
# =============================================================================
# COMPONENTES UI
# =============================================================================
def card_kpi(titulo, valor, cor_texto, subtexto="", icone="bi bi-hash"):
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.I(className=f"{icone}", style={'fontSize': '1.4rem', 'color': cor_texto}),
                ], className="me-3 p-2 rounded-circle bg-light d-flex align-items-center justify-content-center", style={'width': '45px', 'height': '45px'}),
                html.Div([
                    html.H5(titulo, className="text-muted text-uppercase fw-bold mb-0", style={'fontSize': '0.7rem', 'letterSpacing': '1px'}),
                    html.H2(valor, className="fw-bold mb-0", style={'color': cor_texto, 'fontSize': '1.8rem'}),
                ])
            ], className="d-flex align-items-center"),
            html.Div(subtexto, className="small text-muted mt-2 ps-1") if subtexto else None
        ])
    ], className="shadow-sm border-0 h-100")
# =============================================================================
# LAYOUT
# =============================================================================
def create_layout(df_inicial):
    # Função auxiliar para pegar opções iniciais
    def get_options(col):
        if df_inicial.empty or col not in df_inicial.columns: return []
        return [{'label': str(x), 'value': str(x), 'title': str(x)} for x in sorted(df_inicial[col].dropna().unique())]
    # Estilos
    style_input_white = {
        'backgroundColor': '#FFFFFF', 'border': 'none', 'borderRadius': '4px',
        'color': '#2C3E50', 'fontSize': '0.9rem', 'padding': '10px', 'width': '100%'
    }
    label_style = {'color': '#BDC3C7', 'fontWeight': 'bold', 'fontSize': '0.75rem', 'marginTop': '15px', 'marginBottom': '5px', 'textTransform': 'uppercase'}
    # --- SIDEBAR FIXA ---
    sidebar = html.Div([
        # Cabeçalho
        html.Div([
            html.I(className="bi bi-bar-chart-fill text-info me-2", style={'fontSize': '1.8rem'}),
            html.Div([
                html.H3("Aconex BI", className="text-white fw-bold mb-0", style={'fontSize': '1.4rem'}),
                html.Small("Engineering Analytics", className="text-muted", style={'fontSize': '0.75rem'})
            ])
        ], className="d-flex align-items-center mb-4 pt-2"),

        html.Hr(style={'borderColor': 'rgba(255,255,255,0.1)', 'margin': '20px 0'}),

        # Inputs de Busca
        html.Label("🔍 Buscar Docs (Lista/Excel)", style=label_style),
        dbc.Textarea(
            id='input-search-docs',
            placeholder="Cole códigos aqui...\nEx: 1234-DE-001\n5678-FD-002",
            style={**style_input_white, 'height': '80px'}, className="shadow-sm"
        ),
        html.Label("📝 Buscar na Descrição", style=label_style),
        dbc.Input(id='input-search-desc', placeholder="Ex: Painel...", type="text", style=style_input_white, className="shadow-sm"),
        html.Hr(style={'borderColor': 'rgba(255,255,255,0.1)', 'margin': '20px 0'}),
        # Filtros Dinâmicos
        html.Div([
            html.Label("Especialidade", style=label_style),
            dcc.Dropdown(id='filtro-esp', options=[{'label': i, 'value': i, 'title': i} for i in get_options('Especialidade')], multi=True, placeholder="Selecione..."),

            html.Label("Subespecialidade", style=label_style),
            dcc.Dropdown(id='filtro-subesp', options=[{'label': i, 'value': i} for i in get_options('Subespecialidade')], multi=True, placeholder="Selecione..."),
            html.Label("Tipo Documento", style=label_style),
            dcc.Dropdown(id='filtro-tipo', options=[{'label': i, 'value': i} for i in get_options('Tipo do Documento')], multi=True, placeholder="Selecione..."),
            html.Label("Tipo DCC", style=label_style),
            dcc.Dropdown(id='filtro-tipo-dcc', options=[{'label': i, 'value': i} for i in get_options('Tipo do Documento DCC')], multi=True, placeholder="Selecione..."),

             html.Label("Subtipo DCC", style=label_style),
            dcc.Dropdown(id='filtro-subtipo-dcc', options=[{'label': i, 'value': i} for i in get_options('Subtipo DCC')], multi=True, placeholder="Selecione..."),
        ], style={'maxHeight': '45vh', 'overflowY': 'auto', 'paddingRight': '5px'}),
        dbc.Button([html.I(className="bi bi-lightning-fill me-2"), "Aplicar Filtros"], id='btn-update', color="primary", className="w-100 mt-4 shadow fw-bold", style={'borderRadius': '50px', 'padding': '12px'}),

    ], style={'position': 'fixed', 'top': 0, 'left': 0, 'bottom': 0, 'width': '280px', 'padding': '25px', 'backgroundColor': CORES['sidebar'], 'zIndex': 1050, 'boxShadow': '4px 0 15px rgba(0,0,0,0.1)', 'overflowY': 'auto'})
    # --- CONTEÚDO ---
    content = html.Div([
        dcc.Store(id='store-drilldown-ids', data=[]), 
        # Cabeçalho Página
        dbc.Row([dbc.Col([html.H4("Visão Geral do Projeto", className="fw-bold text-dark"), html.P("Dashboard de Controle de Engenharia e Prazos", className="text-muted small")])], className="mb-4"),
        # KPIs
        dbc.Row(id='row-kpis', className="mb-4 g-3"),
        # 1. Status Current
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col(html.H5("Status da Documentação Vigente", className="mb-0 fw-bold text-primary"), width=8),
                    dbc.Col(html.Small("* Clique para detalhar", className="text-muted fst-italic text-end"), width=4)
                ], align="center")
            ], className="bg-white border-0 border-bottom pt-3 pb-2 px-4"),
            dbc.CardBody([
                dcc.Graph(id='graph-status-current', style={'height': '350px'}, config={'displayModeBar': False}),
                dbc.Collapse([
                    html.Hr(),
                    dash_table.DataTable(
                        id='table-drilldown',
                        columns=[{"name": "Documento", "id": "No. do Documento"}, {"name": "Título", "id": "Título"}, {"name": "Rev", "id": "Revisão"}, {"name": "Envio", "id": "Data Envio"}, {"name": "Status", "id": "Status_Final"}],
                        page_current=0, page_size=10, page_action='custom',
                        style_table={'overflowX': 'auto'}, style_header={'backgroundColor': '#ECF0F1', 'fontWeight': 'bold'},
                        style_cell={'textAlign': 'left', 'fontSize': '12px', 'padding': '8px'},
                        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#F9F9F9'}]
                    )
                ], id='collapse-table', is_open=False)
            ], className="px-2")
        ], className="shadow-sm border-0 mb-4"),
        # 2. Histórico
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    dbc.Col(html.H5("Histórico de Emissões vs Retornos", className="mb-0 fw-bold text-dark"), width=8),
                    dbc.Col(dbc.RadioItems(id="radio-hist-freq", options=[{"label": "Diário", "value": "D"}, {"label": "Mensal", "value": "ME"}], value="ME", inline=True, className="text-end small"), width=4)
                ], align="center")
            ], className="bg-white border-0 border-bottom pt-3 pb-2 px-4"),
            dbc.CardBody(dcc.Graph(id='graph-history', style={'height': '450px'}), className="p-2")
        ], className="shadow-sm border-0 mb-4"),
        # 3. Performance de Prazos (VISUAL CORRIGIDO E ALINHADO)
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    # Lado Esquerdo: Título
                    dbc.Col(html.H5("Análise Temporal de Ciclos", className="mb-0 fw-bold text-dark"), width=4),
                    # Lado Direito: Barra de Ferramentas Unificada
                    dbc.Col(
                        html.Div([
                            # Grupo 1: Frequência
                            html.Div([
                                html.Span("Freq:", className="small text-muted fw-bold me-2"),
                                dbc.RadioItems(
                                    id="radio-prazos-freq",
                                    options=[{"label": "Diário", "value": "D"}, {"label": "Mensal", "value": "ME"}],
                                    value="ME", inline=True,
                                    labelClassName="small", inputClassName="me-1"
                                ),
                            ], className="d-flex align-items-center border-end pe-3 me-3"),
                            # Grupo 2: Teto (Dias)
                            html.Div([
                                html.Span("Teto:", className="small text-muted fw-bold me-2"),
                                dcc.Input(
                                    id='input-cycle-cap', type='number', value=200, min=10, step=10,
                                    className="form-control form-control-sm text-center", 
                                    style={'width': '60px', 'height': '25px', 'padding': '0'}
                                )
                            ], className="d-flex align-items-center border-end pe-3 me-3"),
                            # Grupo 3: Séries (Checklist)
                            dbc.Checklist(
                                options=[
                                    {"label": "Itaipu (0A)", "value": "ITAIPU_0A"},
                                    {"label": "Itaipu (+)", "value": "ITAIPU_DEMAIS"},
                                    {"label": "CMI", "value": "CMI"},
                                ],
                                value=["ITAIPU_0A", "ITAIPU_DEMAIS", "CMI"],
                                id="check-prazos-series",
                                inline=True, switch=True,
                                labelClassName="small text-muted"
                            )
                        ], className="d-flex justify-content-end align-items-center"),
                        width=8
                    )
                ], align="center")
            ], className="bg-white border-0 border-bottom pt-3 pb-2 px-4"),
            dbc.CardBody(dcc.Graph(id='graph-cycle-performance', style={'height': '400px'}), className="p-2")
        ], className="shadow-sm border-0 mb-4"),
        # 4. Atrasos
        # 4. Atrasos (VISUAL CORRIGIDO E ALINHADO)
        dbc.Card([
            dbc.CardHeader([
                dbc.Row([
                    # Lado Esquerdo: Título
                    dbc.Col(html.H5("Backlog de Atrasos", className="mb-0 fw-bold text-danger"), width=5),
                    # Lado Direito: Barra de Ferramentas
                    dbc.Col(
                        html.Div([
                            # Grupo 1: Teto
                            html.Div([
                                html.Span("Escala Máx:", className="small text-muted fw-bold me-2"),
                                dcc.Input(
                                    id='input-delay-cap', type='number', value=200, min=10, step=10,
                                    className="form-control form-control-sm text-center",
                                    style={'width': '60px', 'height': '25px', 'padding': '0'}
                                )
                            ], className="d-flex align-items-center border-end pe-3 me-3"),
                            # Grupo 2: Séries
                            dbc.Checklist(
                                options=[
                                    {"label": "Itaipu", "value": "ITAIPU"}, 
                                    {"label": "CMI", "value": "CMI"}
                                ],
                                value=["ITAIPU", "CMI"],
                                id="check-delay-series",
                                inline=True, switch=True,
                                labelClassName="small text-muted fw-bold me-2"
                            ),
                            # Grupo 3: Regra de Parada (Aprovação Parcial)
                            dbc.Checklist(
                                options=[{"label": "Encerrar atraso no 'Aprov. c/ Comentários'", "value": "IGNORAR"}],
                                value=["IGNORAR"], # Começa ligado por padrão (se quiser desligado, deixe [])
                                id="check-delay-ignorar",
                                inline=True, switch=True,
                                labelClassName="small text-primary fw-bold"
                            )
                        ], className="d-flex justify-content-end align-items-center"),
                        width=7
                    )
                ], align="center")
            ], className="bg-white border-0 border-bottom pt-3 pb-2 px-4"),
            dbc.CardBody(dcc.Graph(id='graph-delay', style={'height': '450px'}), className="p-2")
        ], className="shadow-sm border-0 mb-5"),
    ], style={'marginLeft': '280px', 'padding': '30px', 'backgroundColor': CORES['background'], 'minHeight': '100vh'})
    return html.Div([sidebar, content])
# =============================================================================
# LÓGICA DE FILTRAGEM (Engine Tracking ID)
# =============================================================================
def filtrar_completo(df, filtros, busca_docs, busca_desc):
    if df.empty: return df
    mask = pd.Series(True, index=df.index)

    # 1. BUSCA POR LISTA (Correção Técnica: Expansão para Tracking ID)
    if busca_docs:
        raw = str(busca_docs).replace(',', '\n').replace(';', '\n')
        codigos_input = [x.strip() for x in raw.split('\n') if x.strip()]

        if codigos_input:
            # A. Encontra as linhas que batem com o código digitado (mesmo se antigo)
            linhas_match = df[df['No. do Documento'].isin(codigos_input)]

            if not linhas_match.empty:
                # B. Pega os Tracking IDs dessas linhas
                ids_vinculados = linhas_match['Tracking ID'].unique()

                # C. O filtro final é PELO ID, ignorando o nome do documento antigo
                # Isso traz o histórico completo + a versão vigente (Current=True)
                mask &= df['Tracking ID'].isin(ids_vinculados)
            else:
                # Se não achou nada, força mask False
                mask = pd.Series(False, index=df.index)
    # 2. Busca Descrição
    if busca_desc:
        mask &= df['Título'].str.contains(str(busca_desc), case=False, na=False)
    # 3. Dropdowns (Filtros Normais)
    mapa = {
        'filtro-esp': 'Especialidade', 'filtro-subesp': 'Subespecialidade',
        'filtro-tipo': 'Tipo do Documento', 'filtro-tipo-dcc': 'Tipo do Documento DCC',
        'filtro-subtipo-dcc': 'Subtipo DCC'
    }
    for fid, col in mapa.items():
        if filtros.get(fid): mask &= df[col].isin(filtros[fid])

    return df[mask]
# =============================================================================
# CALLBACK 1: ATUALIZAÇÃO DOS FILTROS (CASCADING FILTERS)
# =============================================================================
@app.callback(
    [Output('filtro-esp', 'options'),
     Output('filtro-subesp', 'options'),
     Output('filtro-tipo', 'options'),
     Output('filtro-tipo-dcc', 'options'),
     Output('filtro-subtipo-dcc', 'options')],
    [Input('btn-update', 'n_clicks')], # Gatilho principal
    [State('filtro-esp', 'value'), State('filtro-subesp', 'value'),
     State('filtro-tipo', 'value'), State('filtro-tipo-dcc', 'value'), State('filtro-subtipo-dcc', 'value'),
     State('input-search-docs', 'value'), State('input-search-desc', 'value')]
)
def update_filter_options(n_clicks, f_esp, f_subesp, f_tipo, f_t_dcc, f_s_dcc, s_docs, s_desc):
    # Se não houver dados, retorna vazio
    if df_wide_global.empty:
        return [], [], [], [], []
    # Cria dicionário de filtros ATUAIS
    filtros = {'filtro-esp': f_esp, 'filtro-subesp': f_subesp, 'filtro-tipo': f_tipo, 'filtro-tipo-dcc': f_t_dcc, 'filtro-subtipo-dcc': f_s_dcc}

    # Filtra o dataframe com base na seleção atual
    df_filt = filtrar_completo(df_wide_global, filtros, s_docs, s_desc)

    # Função helper para extrair únicas ordenadas
    def get_opts(df, col):
        return sorted([str(x) for x in df[col].unique() if str(x) != 'nan'])
    # Retorna opções disponíveis apenas dentro do universo filtrado
    return (
        [{'label': i, 'value': i, 'title': i} for i in get_opts(df_filt, 'Especialidade')],
        [{'label': i, 'value': i, 'title': i} for i in get_opts(df_filt, 'Subespecialidade')],
        [{'label': i, 'value': i, 'title': i} for i in get_opts(df_filt, 'Tipo do Documento')],
        [{'label': i, 'value': i, 'title': i} for i in get_opts(df_filt, 'Tipo do Documento DCC')],
        [{'label': i, 'value': i, 'title': i} for i in get_opts(df_filt, 'Subtipo DCC')]
    )
# =============================================================================
# CALLBACK 2: ATUALIZAÇÃO DOS GRÁFICOS
# =============================================================================
@app.callback(
    [Output('graph-status-current', 'figure'),
     Output('graph-history', 'figure'),
     Output('graph-cycle-performance', 'figure'),
     Output('graph-delay', 'figure'),
     Output('row-kpis', 'children'),
     Output('store-drilldown-ids', 'data')],
    [Input('btn-update', 'n_clicks'),
     Input('radio-hist-freq', 'value'),
     Input('radio-prazos-freq', 'value'),
     Input('input-delay-cap', 'value'),
     Input('input-cycle-cap', 'value'),
     Input('check-delay-series', 'value'),
     Input('check-delay-ignorar', 'value'), # <--- NOVO INPUT
     Input('check-prazos-series', 'value')],
    [State('filtro-esp', 'value'), State('filtro-subesp', 'value'),
     State('filtro-tipo', 'value'), State('filtro-tipo-dcc', 'value'), State('filtro-subtipo-dcc', 'value'),
     State('input-search-docs', 'value'), State('input-search-desc', 'value')]
)
def update_graphs(n_clicks, freq_hist, freq_prazos, delay_cap, cycle_cap, delay_opts, delay_ignorar, prazos_opts, f_esp, f_subesp, f_tipo, f_t_dcc, f_s_dcc, s_docs, s_desc):
    # BLINDAGEM 1: Evita crash de iteração se o usuário desmarcar todos os checklists (evita o tipo None)
    delay_opts = delay_opts or []
    prazos_opts = prazos_opts or []
    filtros = {'filtro-esp': f_esp, 'filtro-subesp': f_subesp, 'filtro-tipo': f_tipo, 'filtro-tipo-dcc': f_t_dcc, 'filtro-subtipo-dcc': f_s_dcc}

    if df_wide_global.empty:
        vazio = go.Figure().update_layout(title="Aguardando dados...", xaxis={'visible':False}, yaxis={'visible':False})
        return vazio, vazio, vazio, vazio, [], []
    df_filt = filtrar_completo(df_wide_global, filtros, s_docs, s_desc)

    if df_filt.empty:
        vazio = go.Figure().update_layout(title="Nenhum resultado encontrado.")
        return vazio, vazio, vazio, vazio, [], []
    # --- 1. STATUS CURRENT (CORREÇÃO TÉCNICA) ---
    # Captura True, 'true', 1, '1', 'TRUE' ou 'yes'
    mask_cur = df_filt['Current'].apply(lambda x: str(x).lower().strip() in ['true', '1', 'yes'])
    df_cur = df_filt[mask_cur].copy()

    # Fallback: Se não achar nenhum current, pega a última revisão de cada Tracking ID
    if df_cur.empty and not df_filt.empty:
         df_cur = df_filt.sort_values('Data Envio').drop_duplicates('Tracking ID', keep='last')
    # Define status final
    df_cur['Status_Final'] = df_cur.apply(lambda r: r['Status Retorno'] if pd.notnull(r['Status Retorno']) else r['Status Envio'], axis=1)

    st_counts = df_cur['Status_Final'].value_counts()

    # MAPA DE CORES RIGOROSO (COM STRIP)
    def get_color(status):
        # Normaliza o texto para evitar erros de digitação
        st = str(status).upper().strip()

        # 1. STATUS DE CANCELAMENTO (CINZA) - Prioridade Alta
        # Agora Cancelado e Anulado são tons de cinza (neutros/mortos)  
        if 'CANCELADO' in st or 'ANULADO' in st:
            return '#7f8c8d'  # Cinza (Concrete) - Diferente do cinza default

        # 2. STATUS INFORMATIVOS (AMARELO)
        # Agrupa "Informativo" e "Para Informação" na mesma cor
        if 'INFORMATIVO' in st or 'PARA INFORMA' in st: 
            return "#f1c40f"  # Amarelo Ouro (Sun Flower)
        # 3. CHECAGENS ESPECÍFICAS DE PROCESSO
        if 'EM PROCESSO (CMI)' in st: return "#ef6d17" # Laranja Escuro (Pumpkin)

        # 4. APROVAÇÕES COM RESTRIÇÃO (VERDE CLARO)
        if 'APROVADO COM COMENTÁRIOS' in st or 'COMENTARIOS' in st: 
            return '#2ecc71' # Verde Esmeralda

        # 5. APROVAÇÕES LIMPAS (VERDE ESCURO)
        # Importante: Checar isso DEPOIS de "Comentários"
        if 'APROVADO' in st and 'NÃO' not in st: 
            return '#27ae60' # Verde Nephritis
        if 'ASSINATURA' in st: 
            return '#16a085' # Verde Green Sea

        # 6. REPROVAÇÕES (VERMELHO)
        if 'NÃO APROVADO' in st or 'REPROVADO' in st: 
            return '#c0392b' # Vermelho (Pomegranate)

        # 7. EM PROCESSO GENÉRICO (AZUL)
        if 'EM PROCESSO' in st: 
            return '#3498db' # Azul (Peter River)

        # Default (Caso venha algo vazio ou desconhecido)
        return '#95a5a6' # Cinza Claro (Asbestos)
    colors = [get_color(x) for x in st_counts.index]

    fig_st = go.Figure(go.Bar(
        x=st_counts.values, y=st_counts.index, orientation='h',
        text=st_counts.values, textposition='auto', marker_color=colors
    ))
    fig_st.update_layout(
        margin=dict(l=20, r=20, t=10, b=20),
        yaxis={'categoryorder':'total ascending'},
        clickmode='event+select',
        plot_bgcolor='white'
    )
    # --- 2. KPIs ---
    dm = DataManager()

    # 1. Definir o Universo: Apenas revisões 0A que JÁ VOLTARAM (têm status de retorno)
    # Normalizamos para garantir que pegue '0A', '0a', '0', etc.
    revs_iniciais = ['0A']

    # Filtro 1: É revisão inicial? (Usamos df_filt para pegar o histórico, não só o atual)
    mask_rev_0a = df_filt['Revisão'].astype(str).str.upper().str.strip().isin(revs_iniciais)

    # Filtro 2: Tem status de retorno? (Ignora quem ainda está "Em Processo" de ida)
    mask_tem_retorno = df_filt['Status Retorno'].notna() & (df_filt['Status Retorno'] != '')
    df_ftr_base = df_filt[mask_rev_0a & mask_tem_retorno].copy()
    status_sucesso = ['APROVADO', 'APROVADO COM COMENTÁRIOS', 'PARA ASSINATURA']

    # Cria coluna temporária limpa para comparação
    df_ftr_base['Status_Check'] = df_ftr_base['Status Retorno'].astype(str).str.upper().str.strip()

    # Conta quantos deram certo (O Numerador)
    qtd_sucesso = df_ftr_base[df_ftr_base['Status_Check'].isin(status_sucesso)].shape[0]
    total_0a = df_ftr_base.shape[0]

    # Cálculo Final
    ftr = (qtd_sucesso / total_0a * 100) if total_0a > 0 else 0

    # Restante dos KPIs (Mantido igual, mas usando o total_cur para o card 'Vigentes')
    total_cur = len(df_cur) 
    kpis_rev = dm.calcular_kpis_revisoes(df_filt)

    kpis = [
        dbc.Col(card_kpi("Vigentes", f"{total_cur}", "#3498db"), width=3),
        dbc.Col(card_kpi("First Time Right", f"{ftr:.1f}%", "#27ae60", f"Base: {total_0a} Docs 0A", "bi-check-circle-fill"), width=3),
        dbc.Col(card_kpi("Ciclo Técnico", f"{kpis_rev['ciclo_aprovacao']}", "#f39c12", "Revisões Médias", "bi-arrow-repeat"), width=3),
        dbc.Col(card_kpi("Ciclo Final", f"{kpis_rev['ciclo_completo']}", "#8e44ad", "Revisões Médias", "bi-check-all"), width=3),
    ]
    # --- 3. HISTÓRICO ---
    fig_hist = make_subplots(specs=[[{"secondary_y": True}]])

    # BLINDAGEM 2: Verifica se o DataFrame não fica vazio após o dropna antes de fazer o resample
    df_env_valid = df_filt[['Data Envio']].dropna()
    if not df_env_valid.empty:
        df_env = df_env_valid.set_index('Data Envio').resample(freq_hist).size()
        df_ac = df_env_valid.set_index('Data Envio').resample('D').size().cumsum()
        if freq_hist == 'ME': df_ac = df_ac.resample('ME').last()

        fig_hist.add_trace(go.Bar(x=df_env.index, y=df_env.values, name="Emitidos", marker_color=CORES['Barra_Envio'], opacity=0.7), secondary_y=False)
        fig_hist.add_trace(go.Scatter(x=df_ac.index, y=df_ac.values, name="Acumulado", line=dict(color=CORES['Linha_Acumulado'], width=3)), secondary_y=True)
    df_ret_valid = df_filt[['Data Retorno']].dropna()
    if not df_ret_valid.empty:
        df_ret = df_ret_valid.set_index('Data Retorno').resample(freq_hist).size()
        fig_hist.add_trace(go.Bar(x=df_ret.index, y=df_ret.values, name="Recebidos", marker_color=CORES['Barra_Retorno'], opacity=0.7), secondary_y=False)

    fig_hist.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        plot_bgcolor='white', hovermode="x unified"
    )
    # --- 4. PERFORMANCE CICLOS TEMPORAL (MODIFICADO) ---
    # BLINDAGEM 3: Correção da variável (cycle_cap) e proteção contra input vazio
    limite_ciclo = int(cycle_cap) if cycle_cap is not None and str(cycle_cap).strip() != "" else 200

    # Chama a NOVA função de evolução temporal no DataManager
    series_ciclos = dm.gerar_evolucao_prazos(df_filt, freq=freq_prazos, limite_dias=limite_ciclo)
    fig_ciclos = go.Figure()

    # 1. Itaipu 0A (Meta 30 dias)
    if 'ITAIPU_0A' in prazos_opts and 'ITAIPU_0A' in series_ciclos:
        d = series_ciclos['ITAIPU_0A']
        fig_ciclos.add_trace(go.Scatter(
            x=d.index, y=d['Media_Dias'], 
            name="Itaipu (0A)", mode='lines+markers',
            line=dict(color="#91ff00", width=3, shape='spline'),
            customdata=d['Qtd_Docs'], 
            hovertemplate="<b>Data:</b> %{x|%d/%m/%Y}<br><b>Média:</b> %{y:.1f} dias<br><b>Base:</b> %{customdata} docs<extra></extra>"
        ))
        # Linha de Referência 30d (Só aparece se a série estiver ativa)
        fig_ciclos.add_hline(y=30, line_dash="dash", line_color="#16a085", annotation_text="Meta 30d", annotation_position="top left")
    # 2. Itaipu Demais (Meta 15 dias)
    if 'ITAIPU_DEMAIS' in prazos_opts and 'ITAIPU_DEMAIS' in series_ciclos:
        d = series_ciclos['ITAIPU_DEMAIS']
        fig_ciclos.add_trace(go.Scatter(
            x=d.index, y=d['Media_Dias'], 
            name="Itaipu (Demais)", mode='lines+markers',
            line=dict(color="#f30a0a", width=3, shape='spline'),
            customdata=d['Qtd_Docs'], 
            hovertemplate="<b>Data:</b> %{x|%d/%m/%Y}<br><b>Média:</b> %{y:.1f} dias<br><b>Base:</b> %{customdata} docs<extra></extra>"
        ))
    # 3. CMI Reemissão (Meta 15 dias)
    if 'CMI' in prazos_opts and 'CMI' in series_ciclos:
        d = series_ciclos['CMI']
        fig_ciclos.add_trace(go.Scatter(
            x=d.index, y=d['Media_Dias'], 
            name="CMI (Reemissão)", mode='lines+markers',
            line=dict(color="#b439e9", width=3, shape='spline'),
            customdata=d['Qtd_Docs'], 
            hovertemplate="<b>Data:</b> %{x|%d/%m/%Y}<br><b>Média:</b> %{y:.1f} dias<br><b>Base:</b> %{customdata} docs<extra></extra>"
        ))
    # Linha de Referência 15d (Aparece se Itaipu Demais OU CMI estiverem ativos)
    if 'ITAIPU_DEMAIS' in prazos_opts or 'CMI' in prazos_opts:
        fig_ciclos.add_hline(y=15, line_dash="dash", line_color="gray", annotation_text="Meta 15d", annotation_position="bottom left")
    fig_ciclos.update_layout(
        margin=dict(l=20, r=20, t=30, b=20), 
        legend=dict(orientation="h", y=1.02, x=0.5), 
        plot_bgcolor='white', hovermode="x unified",
        yaxis_title="Média Dias Corridos"
    )
    # --- 4. ATRASOS ---
    lim = int(delay_cap) if delay_cap else 200
    ignorar_parciais = True if "IGNORAR" in (delay_ignorar or []) else False # Captura o status do botão

    df_atrasos = dm.gerar_curva_atrasos(df_filt, limite_dias=lim, ignorar_parciais=ignorar_parciais)

    fig_delay = go.Figure()
    if not df_atrasos.empty:
        hover_tmpl = "<b>Data:</b> %{x|%d/%m/%Y}<br><b>Qtd:</b> %{y}<br><b>Média:</b> %{customdata} dias<extra></extra>"
        if "ITAIPU" in delay_opts:
            fig_delay.add_trace(go.Scatter(x=df_atrasos['Data'], y=df_atrasos['Qtd_Itaipu'], name="Itaipu", fill='tozeroy', line=dict(color=CORES['Delay_Itaipu']), customdata=df_atrasos['Media_Dias_Itaipu'], hovertemplate=hover_tmpl))
        if "CMI" in delay_opts:
            fig_delay.add_trace(go.Scatter(x=df_atrasos['Data'], y=df_atrasos['Qtd_CMI'], name="CMI", fill='tozeroy', line=dict(color=CORES['Delay_CMI']), customdata=df_atrasos['Media_Dias_CMI'], hovertemplate=hover_tmpl))

    fig_delay.update_layout(
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        plot_bgcolor='white', xaxis_title="Linha do Tempo"
    )
    drill_data = df_cur[['Tracking ID', 'Revisão', 'Status_Final']].to_dict('records')
    return fig_st, fig_hist, fig_ciclos, fig_delay, kpis, drill_data
# =============================================================================
# CALLBACK DRILLDOWN (Mantido)
# =============================================================================
@app.callback(
    [Output('table-drilldown', 'data'), Output('collapse-table', 'is_open')],
    [Input('graph-status-current', 'clickData'), Input('table-drilldown', 'page_current'), Input('table-drilldown', 'page_size')],
    [State('store-drilldown-ids', 'data')]
)
def update_table(clickData, page_current, page_size, store_data):
    if not clickData or not store_data: return [], False
    st_clicado = clickData['points'][0]['label']
    ids_filt = [r for r in store_data if r['Status_Final'] == st_clicado]
    if not ids_filt: return [], True

    inicio = page_current * page_size
    fim = (page_current + 1) * page_size
    ids_pag = pd.DataFrame(ids_filt[inicio:fim])

    df_view = pd.merge(ids_pag, df_wide_global, on=['Tracking ID', 'Revisão'], how='left')
    for c in ['Data Envio', 'Data Retorno']:
        if c in df_view.columns: df_view[c] = pd.to_datetime(df_view[c]).dt.strftime('%d/%m/%Y')

    return df_view.to_dict('records'), True
if __name__ == "__main__":
    app.run(debug=True, port=8050)