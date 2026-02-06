"""
B3 Portfolio Dashboard

Dashboard interativo para monitoramento de carteira de acoes da B3.
Exibe treemaps dinamicos com rotacao automatica entre 3 visualizacoes:
variacao diaria, semanal e ganho/perda total.

Funcionalidades:
    - Treemap com cores por variacao percentual
    - Rotacao automatica configurable entre telas
    - Graficos historicos de 30 dias (click no ativo)
    - Alertas para mudancas bruscas (>4%), oportunidades e realizacao
    - Gerenciamento de carteira via interface web
    - Atualizacao a cada 5 minutos via Yahoo Finance (yfinance)

Dados: acoes.csv (ticker, shares, avg_price)
Stack: Plotly Dash, Dash Bootstrap, yfinance, Pandas
Porta: 8050

Autor: Andre Kittler / Casco Digital
"""

import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
from dash import callback_context
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf
from datetime import datetime
import dash_bootstrap_components as dbc
from collections import deque


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], suppress_callback_exceptions=True)

# Fila para armazenar logs (max 50 entradas)
log_queue = deque(maxlen=50)

# Configuracoes padrao de tempo (em segundos) e habilitacao
DEFAULT_TIMES = {
    'daily': 20,
    'weekly': 10,
    'monthly': 10
}

DEFAULT_ENABLED = {
    'daily': True,
    'weekly': True,
    'monthly': True
}


def add_log(message, level='info'):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_queue.append({'time': timestamp, 'level': level, 'message': message})


def load_stocks():
    try:
        df = pd.read_csv('acoes.csv')
        add_log(f"CSV carregado: {len(df)} acoes", 'success')
        return df
    except Exception as e:
        add_log(f"Erro ao carregar acoes.csv: {e}", 'error')
        return pd.DataFrame(columns=['ticker', 'shares', 'avg_price'])


def save_stocks(df):
    try:
        df.to_csv('acoes.csv', index=False)
        add_log(f"CSV salvo com {len(df)} acoes", 'success')
        return True
    except Exception as e:
        add_log(f"Erro ao salvar acoes.csv: {e}", 'error')
        return False


def get_stock_data(ticker, avg_price):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='10d')
        if hist.empty:
            add_log(f"{ticker}: Sem dados", 'warning')
            return None
        current_price = hist['Close'].iloc[-1]
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            change_pct_day = ((current_price - prev_close) / prev_close) * 100
            change_value_day = current_price - prev_close
        else:
            change_pct_day = 0
            change_value_day = 0
        if len(hist) >= 8:
            price_7days_ago = hist['Close'].iloc[-8]
            change_pct_7days = ((current_price - price_7days_ago) / price_7days_ago) * 100
            change_value_7days = current_price - price_7days_ago
        elif len(hist) >= 2:
            price_oldest = hist['Close'].iloc[0]
            change_pct_7days = ((current_price - price_oldest) / price_oldest) * 100
            change_value_7days = current_price - price_oldest
        else:
            change_pct_7days = 0
            change_value_7days = 0
        if avg_price > 0:
            change_pct_total = ((current_price - avg_price) / avg_price) * 100
            change_value_total = current_price - avg_price
        else:
            change_pct_total = 0
            change_value_total = 0
        return {
            'ticker': ticker.replace('.SA', ''),
            'price': current_price,
            'avg_price': avg_price,
            'change_pct_day': change_pct_day,
            'change_value_day': change_value_day,
            'change_pct_7days': change_pct_7days,
            'change_value_7days': change_value_7days,
            'change_pct_total': change_pct_total,
            'change_value_total': change_value_total
        }
    except Exception as e:
        add_log(f"Erro {ticker}: {e}", 'error')
        return None


def fetch_stock_data():
    add_log("Iniciando busca de dados...", 'info')
    stocks_df = load_stocks()
    if stocks_df.empty:
        add_log("CSV vazio", 'warning')
        return None
    data_list = []
    for _, row in stocks_df.iterrows():
        stock_data = get_stock_data(row['ticker'], row.get('avg_price', 0))
        if stock_data:
            stock_data['shares'] = row['shares']
            stock_data['value'] = stock_data['price'] * row['shares']
            data_list.append(stock_data)
    if not data_list:
        add_log("Nenhum dado obtido", 'error')
        return None
    df = pd.DataFrame(data_list)
    total_value = df['value'].sum()
    df['participation'] = (df['value'] / total_value) * 100
    df = df.sort_values('value', ascending=False).reset_index(drop=True)
    add_log(f"Dados atualizados: {len(df)} acoes", 'success')
    return df


def get_alerts(df):
    if df is None or df.empty:
        return []

    alerts = []

    # Mudanca brusca (>4% no dia)
    for _, row in df.iterrows():
        if abs(row['change_pct_day']) > 4:
            alert_type = 'success' if row['change_pct_day'] > 0 else 'danger'
            direction = 'ALTA' if row['change_pct_day'] > 0 else 'QUEDA'
            alerts.append({
                'type': alert_type,
                'message': f"🚨 {row['ticker']}: {direction} BRUSCA de {row['change_pct_day']:+.2f}% no dia!"
            })

    # Oportunidade de compra (queda >3% mas positivo no total)
    for _, row in df.iterrows():
        if row['change_pct_day'] < -3 and row['change_pct_total'] > 0:
            alerts.append({
                'type': 'warning',
                'message': f"💡 {row['ticker']}: Possivel oportunidade - Queda de {row['change_pct_day']:.2f}% (ainda +{row['change_pct_total']:.2f}% no total)"
            })

    # Considerar venda (alta >10% no total)
    for _, row in df.iterrows():
        if row['change_pct_total'] > 10:
            alerts.append({
                'type': 'info',
                'message': f"📈 {row['ticker']}: Ganho de {row['change_pct_total']:+.2f}% - Considere realizar lucro"
            })

    return alerts


def get_historical_chart(ticker):
    try:
        if not ticker.endswith('.SA'):
            ticker_full = f'{ticker}.SA'
        else:
            ticker_full = ticker
            ticker = ticker.replace('.SA', '')

        stock = yf.Ticker(ticker_full)
        hist = stock.history(period='1mo')

        if hist.empty:
            return go.Figure().update_layout(
                title='Sem dados disponiveis',
                paper_bgcolor='#1e1e1e',
                plot_bgcolor='#1e1e1e',
                font=dict(color='#e0e0e0')
            )

        color = '#66bb6a' if hist['Close'].iloc[-1] >= hist['Close'].iloc[0] else '#f44336'

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist.index,
            y=hist['Close'],
            mode='lines',
            line=dict(color=color, width=3),
            fill='tozeroy',
            fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.2)',
            name=ticker
        ))

        fig.update_layout(
            title=dict(
                text=f'<b>{ticker} - Ultimos 30 Dias</b>',
                font=dict(size=18, color='#e0e0e0')
            ),
            xaxis=dict(
                title='Data',
                gridcolor='#37474f',
                color='#e0e0e0'
            ),
            yaxis=dict(
                title='Preco (R$)',
                gridcolor='#37474f',
                color='#e0e0e0'
            ),
            paper_bgcolor='#1e1e1e',
            plot_bgcolor='#263238',
            font=dict(color='#e0e0e0'),
            height=400,
            margin=dict(t=50, l=60, r=20, b=50),
            hovermode='x unified',
            images=[dict(
                source=app.get_asset_url('foco.jpg'),
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                sizex=0.3, sizey=0.3,
                xanchor="center", yanchor="middle",
                opacity=0.15,
                layer="below"
            )]
        )

        add_log(f"Grafico de {ticker} gerado", 'info')
        return fig
    except Exception as e:
        add_log(f"Erro ao gerar grafico de {ticker}: {e}", 'error')
        return go.Figure().update_layout(
            title=f'Erro ao carregar dados de {ticker}',
            paper_bgcolor='#1e1e1e',
            plot_bgcolor='#1e1e1e',
            font=dict(color='#e0e0e0')
        )


def create_treemap(df, view_type='day'):
    if df is None or df.empty:
        return go.Figure()

    if view_type == 'day':
        change_pct_col = 'change_pct_day'
        change_value_col = 'change_value_day'
        title_text = 'Variação do Dia'
    elif view_type == '7days':
        change_pct_col = 'change_pct_7days'
        change_value_col = 'change_value_7days'
        title_text = 'Variação dos Últimos 7 Dias'
    else:
        change_pct_col = 'change_pct_total'
        change_value_col = 'change_value_total'
        title_text = 'Ganho/Perda Total'

    labels = []
    for _, row in df.iterrows():
        arrow = "▲" if row[change_pct_col] >= 0 else "▼"
        sign = "+" if row[change_pct_col] >= 0 else ""
        if view_type == 'total':
            label = (f"<b style='font-size:16px'>{row['ticker']} {arrow}</b><br><br>"
                    f"<span style='font-size:22px'><b>R$ {row['price']:.2f}</b></span><br>"
                    f"<span style='font-size:13px; opacity:0.85'>Med: R$ {row['avg_price']:.2f}</span><br>"
                    f"<span style='font-size:15px; font-weight:bold'>{sign}{row[change_pct_col]:.2f}%</span><br>"
                    f"<span style='font-size:12px'>({sign}R$ {row[change_value_col]:.2f})</span>")
        else:
            label = (f"<b style='font-size:16px'>{row['ticker']} {arrow}</b><br><br>"
                    f"<span style='font-size:22px'><b>R$ {row['price']:.2f}</b></span><br>"
                    f"<span style='font-size:15px; font-weight:bold'>{sign}{row[change_pct_col]:.2f}%</span><br>"
                    f"<span style='font-size:12px'>({sign}R$ {row[change_value_col]:.2f})</span>")
        labels.append(label)

    fig = go.Figure(go.Treemap(
        labels=df['ticker'],
        parents=[''] * len(df),
        values=df['value'],
        text=labels,
        textposition='middle center',
        texttemplate='%{text}',
        textfont=dict(size=12, color='white', family='Segoe UI, Arial'),
        pathbar=dict(visible=False),
        marker=dict(
            colors=df[change_pct_col],
            colorscale=[
                [0.0, '#b71c1c'],
                [0.4, '#d32f2f'],
                [0.48, '#f44336'],
                [0.5, '#546e7a'],
                [0.52, '#66bb6a'],
                [0.6, '#43a047'],
                [1.0, '#1b5e20']
            ],
            cmid=0,
            colorbar=dict(
                title=dict(text="Variação %", font=dict(color='#e0e0e0')),
                ticksuffix="%",
                x=1.02,
                thickness=15,
                len=0.5,
                bgcolor='#263238',
                tickfont=dict(color='#e0e0e0'),
                bordercolor='#37474f',
                borderwidth=2
            ),
            line=dict(width=3, color='#1a1a1a')
        ),
        hovertemplate=(
            '<b style="font-size:14px">%{label}</b><br><br>'
            '<span style="font-size:13px">Preco: R$ %{customdata[0]:,.2f}</span><br>'
            '<span style="font-size:13px">Variacao: %{color:+.2f}%</span><br>'
            '<span style="font-size:13px">Participacao: %{customdata[1]:.2f}%</span><br>'
            '<span style="font-size:12px; opacity:0.8">Quantidade: %{customdata[2]:.0f} acoes</span>'
            '<extra></extra>'
        ),
        customdata=df[['price', 'participation', 'shares']].values
    ))

    fig.update_layout(
        title=dict(
            text=f'<b>{title_text}</b>',
            x=0.5,
            xanchor='center',
            font=dict(size=23, color='#e0e0e0')
        ),
        margin=dict(t=65, l=10, r=110, b=10),
        height=820,
        paper_bgcolor='#1e1e1e',
        plot_bgcolor='#1e1e1e',
        font=dict(color='#e0e0e0')
    )
    return fig


def build_rotation_map(settings, enabled):
    """Constroi o mapa de rotacao baseado nas configuracoes de tempo e telas habilitadas"""
    daily_time = settings.get('daily', DEFAULT_TIMES['daily'])
    weekly_time = settings.get('weekly', DEFAULT_TIMES['weekly'])
    monthly_time = settings.get('monthly', DEFAULT_TIMES['monthly'])

    daily_enabled = enabled.get('daily', True)
    weekly_enabled = enabled.get('weekly', True)
    monthly_enabled = enabled.get('monthly', True)

    # Cada item no mapa representa 5 segundos
    rotation_map = []

    if daily_enabled:
        daily_slots = daily_time // 5
        rotation_map.extend([0] * daily_slots)

    if weekly_enabled:
        weekly_slots = weekly_time // 5
        rotation_map.extend([1] * weekly_slots)

    if monthly_enabled:
        monthly_slots = monthly_time // 5
        rotation_map.extend([2] * monthly_slots)

    # Se nenhuma tela estiver habilitada, retorna apenas a diaria
    return rotation_map if rotation_map else [0, 0, 0, 0]


app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Store(id='time-settings', storage_type='local', data=DEFAULT_TIMES),
    dcc.Store(id='enabled-settings', storage_type='local', data=DEFAULT_ENABLED),
    html.Div(id='page-content', style={'min-height': '100vh'})
])


def main_layout():
    return dbc.Container([
        html.Div(id='alerts-container', style={'margin-top': '10px'}),

        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Div([
                        html.Img(
                            src=app.get_asset_url('foco.jpg'),
                            style={
                                'height': '55px',
                                'width': '55px',
                                'border-radius': '10px',
                                'margin-right': '15px',
                                'box-shadow': '0 2px 8px rgba(102,187,106,0.3)'
                            }
                        ),
                        html.H1(
                            'Mapa de Ações',
                            style={'display': 'inline-block', 'color': '#66bb6a', 'margin': '0', 'vertical-align': 'middle', 'font-size': '30px'}
                        ),
                        html.Img(
                            src=app.get_asset_url('foco.jpg'),
                            style={
                                'height': '55px',
                                'width': '55px',
                                'border-radius': '10px',
                                'margin-left': '15px',
                                'box-shadow': '0 2px 8px rgba(102,187,106,0.3)'
                            }
                        )
                    ], style={'display': 'flex', 'align-items': 'center', 'justify-content': 'center'}),
                    html.Div([
                        html.A(
                            html.Button('⚙', style={
                                'border': 'none',
                                'background': '#2e7d32',
                                'color': 'white',
                                'border-radius': '50%',
                                'width': '45px',
                                'height': '45px',
                                'font-size': '22px',
                                'cursor': 'pointer',
                                'box-shadow': '0 4px 12px rgba(46,125,50,0.4)',
                                'margin-right': '8px'
                            }),
                            href='/editar'
                        ),
                        html.A(
                            html.Button('📋', style={
                                'border': 'none',
                                'background': '#1976d2',
                                'color': 'white',
                                'border-radius': '50%',
                                'width': '45px',
                                'height': '45px',
                                'font-size': '22px',
                                'cursor': 'pointer',
                                'box-shadow': '0 4px 12px rgba(25,118,210,0.4)'
                            }),
                            href='/logs'
                        )
                    ], style={'position': 'absolute', 'right': '30px', 'top': '27px', 'display': 'flex'})
                ], style={'position': 'relative', 'margin-bottom': '8px'}),

                html.Div([
                    dbc.Badge(
                        id='time',
                        color='dark',
                        className='me-3',
                        style={'font-size': '13px', 'padding': '8px 15px'}
                    ),
                    dbc.Badge(
                        id='countdown',
                        color='success',
                        style={'font-size': '14px', 'padding': '8px 15px', 'font-weight': 'bold'}
                    )
                ], style={'text-align': 'center', 'margin-bottom': '18px'}),

                html.Div([
                    dcc.Graph(id='treemap', config={'displayModeBar': False}),

                    # Botao de navegacao DENTRO da moldura, canto inferior direito
                    html.Div([
                        html.Button('⬅', id='btn-prev', n_clicks=0, style={
                            'border': 'none',
                            'background': '#1976d2',
                            'color': 'white',
                            'border-radius': '50%',
                            'width': '45px',
                            'height': '45px',
                            'font-size': '20px',
                            'cursor': 'pointer',
                            'box-shadow': '0 4px 12px rgba(25,118,210,0.4)',
                            'margin-right': '5px'
                        }),
                        html.Button('➡', id='btn-next', n_clicks=0, style={
                            'border': 'none',
                            'background': '#1976d2',
                            'color': 'white',
                            'border-radius': '50%',
                            'width': '45px',
                            'height': '45px',
                            'font-size': '20px',
                            'cursor': 'pointer',
                            'box-shadow': '0 4px 12px rgba(25,118,210,0.4)'
                        })
                    ], style={
                        'position': 'absolute',
                        'bottom': '25px',
                        'right': '25px',
                        'display': 'flex',
                        'gap': '5px',
                        'z-index': '1000'
                    })
                ], style={'position': 'relative'})
            ], style={'padding': '20px'})
        ], style={'margin-top': '10px', 'border-radius': '15px'}),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id='modal-title')),
            dbc.ModalBody([
                dcc.Graph(id='historical-chart', config={'displayModeBar': False})
            ]),
            dbc.ModalFooter(
                dbc.Button("Fechar", id="close-modal", className="ms-auto", n_clicks=0, color='secondary')
            )
        ], id="modal", size="lg", is_open=False),

        dcc.Store(id='data'),
        dcc.Store(id='view', data=0),
        dcc.Interval(id='rotate', interval=5000, n_intervals=0),
        dcc.Interval(id='fetch', interval=300000, n_intervals=0),
        dcc.Interval(id='countdown-timer', interval=1000, n_intervals=0)
    ], fluid=True, style={'padding': '20px', 'background-color': '#121212', 'min-height': '100vh'})


def logs_layout():
    return dbc.Container([
        html.H2('📋 Log de Status', className='text-center mb-4', style={'color': '#42a5f5', 'margin-top': '20px'}),

        dbc.Button('← Voltar', href='/', color='secondary', size='lg', className='mb-4', style={'border-radius': '8px'}),

        dbc.Card([
            dbc.CardBody([
                html.Div(id='log-display', style={
                    'height': '600px',
                    'overflow-y': 'auto',
                    'font-family': 'monospace',
                    'font-size': '13px',
                    'background-color': '#0d0d0d',
                    'padding': '15px',
                    'border-radius': '5px'
                })
            ])
        ], style={'border-radius': '12px'}),

        dcc.Interval(id='log-update', interval=2000, n_intervals=0)
    ], fluid=True, style={'padding': '30px', 'background-color': '#121212', 'min-height': '100vh', 'max-width': '1400px'})


def edit_layout():
    return dbc.Container([
        html.H2(
            '⚙️ Gerenciar Acoes',
            className='text-center mb-4',
            style={'color': '#66bb6a', 'margin-top': '20px'}
        ),

        dbc.Button(
            '← Voltar',
            href='/',
            color='secondary',
            size='lg',
            className='mb-4',
            style={'border-radius': '8px'}
        ),

        dbc.Card([
            dbc.CardBody([
                html.H4('⏱️ Configurar Tempo de Exibicao', className='mb-4', style={'color': '#42a5f5'}),
                html.P('Configure quanto tempo (em segundos) cada tela ficara visivel e quais telas deseja exibir:', 
                       style={'color': '#b0bec5', 'margin-bottom': '20px'}),

                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    dbc.Switch(
                                        id='switch-daily',
                                        value=True,
                                        label='',
                                        style={'transform': 'scale(1.3)', 'margin-right': '10px'}
                                    ),
                                    html.Span('Tela Diaria', style={'font-weight': 'bold', 'color': '#e0e0e0', 'font-size': '16px'})
                                ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '10px'}),
                                dbc.Input(id='input-time-daily', type='number', value=20, min=5, step=5, size='lg')
                            ])
                        ], style={'background-color': '#263238', 'border': '1px solid #37474f'})
                    ], width=4),

                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    dbc.Switch(
                                        id='switch-weekly',
                                        value=True,
                                        label='',
                                        style={'transform': 'scale(1.3)', 'margin-right': '10px'}
                                    ),
                                    html.Span('Tela Semanal', style={'font-weight': 'bold', 'color': '#e0e0e0', 'font-size': '16px'})
                                ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '10px'}),
                                dbc.Input(id='input-time-weekly', type='number', value=10, min=5, step=5, size='lg')
                            ])
                        ], style={'background-color': '#263238', 'border': '1px solid #37474f'})
                    ], width=4),

                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    dbc.Switch(
                                        id='switch-monthly',
                                        value=True,
                                        label='',
                                        style={'transform': 'scale(1.3)', 'margin-right': '10px'}
                                    ),
                                    html.Span('Tela Mensal', style={'font-weight': 'bold', 'color': '#e0e0e0', 'font-size': '16px'})
                                ], style={'display': 'flex', 'align-items': 'center', 'margin-bottom': '10px'}),
                                dbc.Input(id='input-time-monthly', type='number', value=10, min=5, step=5, size='lg')
                            ])
                        ], style={'background-color': '#263238', 'border': '1px solid #37474f'})
                    ], width=4)
                ]),

                html.Div(id='validation-warning', style={'margin-top': '15px', 'font-weight': 'bold', 'font-size': '14px'}),

                dbc.Button(
                    'Salvar Configuracoes',
                    id='btn-save-times',
                    n_clicks=0,
                    color='primary',
                    size='lg',
                    className='mt-3',
                    style={'font-weight': 'bold', 'border-radius': '8px', 'padding': '12px 40px'}
                ),
                html.Div(id='time-message', style={'margin-top': '15px', 'font-weight': 'bold', 'font-size': '15px'})
            ])
        ], className='mb-4', style={'border-radius': '12px'}),

        dbc.Card([
            dbc.CardBody([
                html.H4('➕ Adicionar Nova Acao', className='mb-4', style={'color': '#66bb6a'}),
                dbc.Row([
                    dbc.Col([
                        dbc.Label('Ticker (ex: PETR4)', style={'font-weight': 'bold'}),
                        dbc.Input(id='input-ticker', type='text', placeholder='PETR4', size='lg')
                    ], width=4),
                    dbc.Col([
                        dbc.Label('Quantidade', style={'font-weight': 'bold'}),
                        dbc.Input(id='input-shares', type='number', placeholder='100', size='lg')
                    ], width=4),
                    dbc.Col([
                        dbc.Label('Preco Medio', style={'font-weight': 'bold'}),
                        dbc.Input(id='input-price', type='text', placeholder='10.50', size='lg')
                    ], width=4)
                ]),
                dbc.Button(
                    'Adicionar',
                    id='btn-add',
                    n_clicks=0,
                    color='success',
                    size='lg',
                    className='mt-3',
                    style={'font-weight': 'bold', 'border-radius': '8px', 'padding': '12px 40px'}
                ),
                html.Div(id='add-message', style={'margin-top': '15px', 'font-weight': 'bold', 'font-size': '15px'})
            ])
        ], className='mb-4', style={'border-radius': '12px'}),

        dbc.Card([
            dbc.CardBody([
                html.H4('📋 Acoes Cadastradas', className='mb-4', style={'color': '#66bb6a'}),
                html.Div(id='stocks-table'),
                html.Div(id='delete-message', style={'margin-top': '15px', 'font-weight': 'bold', 'font-size': '15px'}),
                dcc.Store(id='update-trigger', data=0),
                html.Div(id='delete-trigger', style={'display': 'none'})
            ])
        ], style={'border-radius': '12px'})
    ], fluid=True, style={'padding': '30px', 'background-color': '#121212', 'min-height': '100vh', 'max-width': '1400px'})


@app.callback(Output('page-content', 'children'), Input('url', 'pathname'))
def display_page(pathname):
    if pathname == '/editar':
        return edit_layout()
    elif pathname == '/logs':
        return logs_layout()
    return main_layout()


@app.callback([Output('data', 'data'), Output('time', 'children')], Input('fetch', 'n_intervals'))
def update_data(n):
    df = fetch_stock_data()
    if df is not None:
        return df.to_dict('records'), f"🕐 Atualizado em {datetime.now().strftime('%d/%m/%Y as %H:%M:%S')}"
    return None, "❌ Erro"


@app.callback(Output('alerts-container', 'children'), Input('data', 'data'))
def update_alerts(data):
    if data is None:
        return []

    df = pd.DataFrame(data)
    alerts = get_alerts(df)

    if not alerts:
        return []

    return [
        dbc.Alert(
            alert['message'],
            color=alert['type'],
            dismissable=True,
            duration=15000,
            className='mb-2',
            style={'font-size': '14px', 'font-weight': 'bold'}
        ) for alert in alerts[:5]
    ]


@app.callback(Output('log-display', 'children'), Input('log-update', 'n_intervals'))
def update_log(n):
    if not log_queue:
        return html.P('Nenhum log disponivel', style={'color': '#78909c', 'margin': '0'})

    log_colors = {
        'success': '#66bb6a',
        'error': '#f44336',
        'warning': '#ffa726',
        'info': '#42a5f5'
    }

    logs = []
    for log in reversed(list(log_queue)):
        color = log_colors.get(log['level'], '#e0e0e0')
        logs.append(
            html.Div([
                html.Span(f"[{log['time']}] ", style={'color': '#78909c'}),
                html.Span(f"{log['message']}", style={'color': color})
            ], style={'margin-bottom': '5px'})
        )

    return logs


@app.callback(
    Output('validation-warning', 'children'),
    [Input('switch-daily', 'value'), Input('switch-weekly', 'value'), Input('switch-monthly', 'value')]
)
def validate_switches(daily, weekly, monthly):
    if not daily and not weekly and not monthly:
        return html.Div('⚠️ Pelo menos uma tela deve estar habilitada!', style={'color': '#f44336'})
    return ''


@app.callback(
    [Output('time-settings', 'data'), Output('enabled-settings', 'data'), 
     Output('time-message', 'children'), Output('time-message', 'style')],
    Input('btn-save-times', 'n_clicks'),
    [State('input-time-daily', 'value'), State('input-time-weekly', 'value'), 
     State('input-time-monthly', 'value'), State('switch-daily', 'value'),
     State('switch-weekly', 'value'), State('switch-monthly', 'value')],
    prevent_initial_call=True
)
def save_time_settings(n_clicks, daily, weekly, monthly, daily_enabled, weekly_enabled, monthly_enabled):
    if n_clicks == 0:
        return DEFAULT_TIMES, DEFAULT_ENABLED, '', {}

    if not daily_enabled and not weekly_enabled and not monthly_enabled:
        return dash.no_update, dash.no_update, '⚠️ Pelo menos uma tela deve estar habilitada!', {'color': '#f44336', 'margin-top': '10px'}

    new_settings = {
        'daily': daily or DEFAULT_TIMES['daily'],
        'weekly': weekly or DEFAULT_TIMES['weekly'],
        'monthly': monthly or DEFAULT_TIMES['monthly']
    }

    new_enabled = {
        'daily': daily_enabled,
        'weekly': weekly_enabled,
        'monthly': monthly_enabled
    }

    enabled_screens = []
    if daily_enabled:
        enabled_screens.append(f"Diaria ({daily}s)")
    if weekly_enabled:
        enabled_screens.append(f"Semanal ({weekly}s)")
    if monthly_enabled:
        enabled_screens.append(f"Mensal ({monthly}s)")

    screens_text = ", ".join(enabled_screens)
    add_log(f"Configuracoes atualizadas: {screens_text}", 'success')

    return new_settings, new_enabled, f'✅ Configuracoes salvas: {screens_text}', {'color': '#66bb6a', 'margin-top': '10px'}


@app.callback(
    [Output('input-time-daily', 'value'), Output('input-time-weekly', 'value'), 
     Output('input-time-monthly', 'value'), Output('switch-daily', 'value'),
     Output('switch-weekly', 'value'), Output('switch-monthly', 'value')],
    Input('url', 'pathname'),
    [State('time-settings', 'data'), State('enabled-settings', 'data')]
)
def load_time_settings(pathname, settings, enabled):
    if pathname == '/editar':
        return (
            settings.get('daily', DEFAULT_TIMES['daily']),
            settings.get('weekly', DEFAULT_TIMES['weekly']),
            settings.get('monthly', DEFAULT_TIMES['monthly']),
            enabled.get('daily', DEFAULT_ENABLED['daily']),
            enabled.get('weekly', DEFAULT_ENABLED['weekly']),
            enabled.get('monthly', DEFAULT_ENABLED['monthly'])
        )
    return dash.no_update


@app.callback(
    Output('view', 'data'), 
    [Input('rotate', 'n_intervals'), Input('btn-prev', 'n_clicks'), Input('btn-next', 'n_clicks')], 
    [State('view', 'data'), State('time-settings', 'data'), State('enabled-settings', 'data')]
)
def rotate_or_navigate(n_intervals, prev_clicks, next_clicks, current_view, settings, enabled):
    ctx = callback_context

    if not ctx.triggered:
        return current_view

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    rotation_map = build_rotation_map(settings, enabled)

    # Navegacao manual via botoes
    if trigger_id == 'btn-prev':
        return (current_view - 1) % 3
    elif trigger_id == 'btn-next':
        return (current_view + 1) % 3

    # Rotacao automatica normal
    index = n_intervals % len(rotation_map)
    return rotation_map[index]


@app.callback(
    Output('countdown', 'children'), 
    [Input('countdown-timer', 'n_intervals')], 
    [State('time-settings', 'data'), State('enabled-settings', 'data')]
)
def update_countdown(n, settings, enabled):
    rotation_map = build_rotation_map(settings, enabled)
    total_cycle = len(rotation_map) * 5
    seconds_in_cycle = n % total_cycle
    position = seconds_in_cycle // 5

    current_view = rotation_map[position]

    remaining_slots = 0
    for i in range(position, len(rotation_map)):
        if rotation_map[i] == current_view:
            remaining_slots += 1
        else:
            break

    seconds_within_slot = seconds_in_cycle % 5
    remaining = (remaining_slots * 5) - seconds_within_slot

    return f"⏱️ {remaining}s"


@app.callback(Output('treemap', 'figure'), [Input('data', 'data'), Input('view', 'data')])
def update_display(data, view_idx):
    if data is None:
        return go.Figure()
    df = pd.DataFrame(data)
    views = ['day', '7days', 'total']
    return create_treemap(df, views[view_idx] if view_idx is not None else 'day')


@app.callback(
    [Output("modal", "is_open"), Output("modal-title", "children"), Output("historical-chart", "figure")],
    [Input("treemap", "clickData"), Input("close-modal", "n_clicks")],
    [State("modal", "is_open")]
)
def toggle_modal(clickData, close_clicks, is_open):
    ctx = callback_context

    if not ctx.triggered:
        return False, "", go.Figure()

    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == "treemap" and clickData:
        ticker = clickData['points'][0]['label']
        return True, f"📈 Historico - {ticker}", get_historical_chart(ticker)

    if trigger_id == "close-modal":
        return False, "", go.Figure()

    return is_open, "", go.Figure()


@app.callback(
    [Output('add-message', 'children'), Output('add-message', 'style'),
     Output('input-ticker', 'value'), Output('input-shares', 'value'),
     Output('input-price', 'value'), Output('update-trigger', 'data')],
    Input('btn-add', 'n_clicks'),
    [State('input-ticker', 'value'), State('input-shares', 'value'),
     State('input-price', 'value'), State('update-trigger', 'data')]
)
def add_stock(n_clicks, ticker, shares, price, trigger):
    if n_clicks == 0:
        return '', {}, '', '', '', trigger

    if not ticker or not shares or not price:
        return '⚠️ Preencha todos os campos!', {'color': '#f44336', 'margin-top': '10px', 'font-weight': 'bold'}, ticker, shares, price, trigger

    try:
        ticker = ticker.upper().strip()
        if not ticker.endswith('.SA'):
            ticker = f'{ticker}.SA'

        price = str(price).replace(',', '.')
        price_float = float(price)
        shares_int = int(shares)

        df = load_stocks()

        if ticker in df['ticker'].values:
            return f'⚠️ {ticker} ja cadastrado!', {'color': '#f44336', 'margin-top': '10px', 'font-weight': 'bold'}, ticker, shares, price, trigger

        new_row = pd.DataFrame([{'ticker': ticker, 'shares': shares_int, 'avg_price': price_float}])
        df = pd.concat([df, new_row], ignore_index=True)

        if save_stocks(df):
            add_log(f"{ticker} adicionado", 'success')
            return f'✅ {ticker} adicionado com sucesso!', {'color': '#66bb6a', 'margin-top': '10px', 'font-weight': 'bold'}, '', '', '', trigger + 1
        else:
            return '❌ Erro ao salvar!', {'color': '#f44336', 'margin-top': '10px', 'font-weight': 'bold'}, ticker, shares, price, trigger

    except Exception as e:
        add_log(f"Erro ao adicionar: {str(e)}", 'error')
        return f'❌ Erro: {str(e)}', {'color': '#f44336', 'margin-top': '10px', 'font-weight': 'bold'}, ticker, shares, price, trigger


@app.callback(
    [Output('stocks-table', 'children'), Output('delete-message', 'children')],
    [Input('update-trigger', 'data'), Input('url', 'pathname'), Input('delete-trigger', 'children')]
)
def update_table(trigger, pathname, delete_trigger):
    df = load_stocks()

    if df.empty:
        return html.P('📭 Nenhuma acao cadastrada.', style={'color': '#78909c', 'font-style': 'italic', 'font-size': '15px'}), ''

    table_rows = []
    for idx, row in df.iterrows():
        table_rows.append(
            html.Tr([
                html.Td(
                    row['ticker'],
                    style={'padding': '15px', 'border-bottom': '1px solid #37474f', 'font-weight': 'bold', 'color': '#66bb6a'}
                ),
                html.Td(
                    f"{row['shares']}",
                    style={'padding': '15px', 'border-bottom': '1px solid #37474f', 'text-align': 'center', 'color': '#e0e0e0'}
                ),
                html.Td(
                    f"R$ {row['avg_price']:.2f}",
                    style={'padding': '15px', 'border-bottom': '1px solid #37474f', 'text-align': 'right', 'color': '#e0e0e0'}
                ),
                html.Td(
                    html.Button('🗑️', id={'type': 'delete-btn', 'index': idx}, n_clicks=0, className='delete-btn', style={
                        'background': '#c62828',
                        'color': 'white',
                        'border': 'none',
                        'padding': '8px 16px',
                        'border-radius': '6px',
                        'cursor': 'pointer',
                        'font-size': '18px'
                    }),
                    style={'padding': '15px', 'border-bottom': '1px solid #37474f', 'text-align': 'center'}
                )
            ], style={'transition': 'background-color 0.2s ease'})
        )

    table = html.Table([
        html.Thead(html.Tr([
            html.Th('Ticker', style={'padding': '15px', 'border-bottom': '2px solid #66bb6a', 'text-align': 'left', 'color': '#66bb6a', 'font-size': '16px'}),
            html.Th('Quantidade', style={'padding': '15px', 'border-bottom': '2px solid #66bb6a', 'text-align': 'center', 'color': '#66bb6a', 'font-size': '16px'}),
            html.Th('Preco Medio', style={'padding': '15px', 'border-bottom': '2px solid #66bb6a', 'text-align': 'right', 'color': '#66bb6a', 'font-size': '16px'}),
            html.Th('Acao', style={'padding': '15px', 'border-bottom': '2px solid #66bb6a', 'text-align': 'center', 'color': '#66bb6a', 'font-size': '16px'})
        ])),
        html.Tbody(table_rows)
    ], style={'width': '100%', 'border-collapse': 'collapse', 'background-color': '#1e1e1e'})

    return table, ''


@app.callback(
    Output('delete-trigger', 'children'),
    Input({'type': 'delete-btn', 'index': dash.dependencies.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def delete_stock(n_clicks_list):
    ctx = callback_context

    if not ctx.triggered or not any(n_clicks_list):
        return ''

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    try:
        import json
        button_dict = json.loads(button_id)
        row_idx = button_dict['index']

        df = load_stocks()
        if row_idx < len(df):
            ticker = df.iloc[row_idx]['ticker']
            df = df.drop(row_idx).reset_index(drop=True)
            save_stocks(df)
            add_log(f"{ticker} removido", 'info')
            return f'{ticker} removido'
    except Exception as e:
        add_log(f"Erro ao deletar: {e}", 'error')

    return ''


if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8050, debug=False)
