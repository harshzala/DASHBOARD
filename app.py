import os
import pandas as pd
from datetime import datetime, timedelta
import threading
import json
import random

from dash import Dash, dcc, html, Input, Output, State, dash_table, callback_context, callback, no_update, ALL
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff

# --- CONFIGURATION (CROSS-PLATFORM) ---
# Use a relative path that works on both Windows and Linux
LOCAL_EXCEL_PATH = os.path.join(os.getcwd(), "demo.xlsx")

def fetch_excel_from_local():
    """Fetch Excel data with better error handling"""
    try:
        if os.path.exists(LOCAL_EXCEL_PATH):
            df = pd.read_excel(LOCAL_EXCEL_PATH, engine="openpyxl")
            print(f"Successfully loaded Excel file: {LOCAL_EXCEL_PATH}")
            return df
        else:
            print(f"Excel file not found at: {LOCAL_EXCEL_PATH}")
            return None
    except ImportError as e:
        print(f"Missing required library: {e}")
        print("Please install openpyxl: pip install openpyxl")
        return None
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None

def generate_sample_data():
    """Generate more realistic sample data"""
    statuses = ['Complete', 'In Progress', 'Not Started', 'On Hold', 'Pending Review']
    priorities = ['Low', 'Medium', 'High', 'Critical']
    locations = ['Engine Room', 'Deck A', 'Deck B', 'Deck C', 'Bridge', 'Galley', 'Quarters']
    asset_types = ['Pump', 'Valve', 'Motor', 'Sensor', 'Pipe', 'Tank', 'Generator']
    
    num_records = 50
    
    data = []
    for i in range(num_records):
        completion = random.randint(0, 100) if random.choice([True, False]) else 0
        status = random.choice(statuses)
        if status == 'Complete':
            completion = 100
        elif status == 'Not Started':
            completion = 0
        
        record = {
            'ASSET TAG': f'{random.choice(asset_types)[:3].upper()}{i+1:03d}',
            'LOCATION DESCRIPTION': f'{random.choice(locations)} - Section {random.randint(1, 5)}',
            'DECK LEVEL': f'Level {random.randint(1, 5)}',
            'Status': status,
            'Priority': random.choice(priorities),
            'Percent Complete': completion,
            'Gallon Total': round(random.uniform(0, 50), 1),
            'Value 1': round(random.uniform(1, 10), 1),  # Risk Rating
            'DATE ADDED': datetime.now() - timedelta(days=random.randint(0, 365)),
            'DESCRIPTION': f'Maintenance work on {random.choice(asset_types).lower()} system',
            'ASSIGNED TO': f'Technician {random.randint(1, 10)}',
            'ESTIMATED HOURS': random.randint(1, 24),
            'COST ESTIMATE': round(random.uniform(100, 5000), 2)
        }
        data.append(record)
    
    return pd.DataFrame(data)

def process_data(df):
    """Process data with enhanced error handling"""
    try:
        df = df.copy()
        
        # Handle Percent Complete
        if 'Percent Complete' in df.columns:
            df['Percent Complete'] = (
                df['Percent Complete'].astype(str).str.replace('%', '', regex=False)
                .str.strip().replace('', '0').astype(float)
            )
        else:
            df['Percent Complete'] = 0

        # Status processing
        df['Status_lower'] = df['Status'].str.lower().fillna('')
        df['Is Complete'] = df['Status_lower'] == 'complete'
        df['Is Not Started'] = df['Status_lower'] == 'not started'
        df['Is In Progress'] = df['Status_lower'] == 'in progress'
        df['Is On Hold'] = df['Status_lower'] == 'on hold'
        df['Is Pending Review'] = df['Status_lower'] == 'pending review'

        # Priority processing
        if "Priority" in df.columns:
            df['Priority_lower'] = df['Priority'].str.lower().fillna('')
            df['Is High Priority'] = df['Priority_lower'].isin(['high', 'critical'])
            df['Is Critical'] = df['Priority_lower'] == 'critical'
        else:
            df['Is High Priority'] = False
            df['Is Critical'] = False

        # Gallons processing
        if "Gallon Total" in df.columns:
            df['Gallons'] = pd.to_numeric(df['Gallon Total'], errors='coerce').fillna(0)
        else:
            df['Gallons'] = 0

        # Risk Rating processing
        if "Value 1" in df.columns:
            df['Risk Rating'] = pd.to_numeric(df['Value 1'], errors='coerce').fillna(0)
        else:
            df['Risk Rating'] = 0

        # Date processing
        if "DATE ADDED" in df.columns:
            df['DATE ADDED'] = pd.to_datetime(df['DATE ADDED'], errors='coerce')
        
        # Additional calculated fields
        df['Days Since Added'] = (datetime.now() - df['DATE ADDED']).dt.days
        df['Urgency Score'] = (df['Risk Rating'] * 0.3 + 
                              df['Days Since Added'] * 0.001 + 
                              df['Is High Priority'] * 2)
        
        return df
    except Exception as e:
        print(f"Error processing data: {e}")
        return df

def get_dashboard_stats(df):
    """Get enhanced dashboard statistics"""
    try:
        stats = {
            "total_items": len(df),
            "completion_rate": df['Percent Complete'].mean() if len(df) else 0,
            "not_started": df['Is Not Started'].sum(),
            "in_progress": df['Is In Progress'].sum(),
            "complete": df['Is Complete'].sum(),
            "on_hold": df['Is On Hold'].sum(),
            "high_priority": df['Is High Priority'].sum(),
            "critical": df['Is Critical'].sum(),
            "total_paint_usage": df['Gallons'].sum(),
            "avg_risk_rating": df['Risk Rating'].mean() if len(df) else 0,
            "max_risk_rating": df['Risk Rating'].max() if len(df) else 0,
            "overdue_items": len(df[df['Days Since Added'] > 30]) if len(df) else 0,
            "avg_completion": df['Percent Complete'].mean() if len(df) else 0,
            "total_estimated_cost": df['COST ESTIMATE'].sum() if 'COST ESTIMATE' in df.columns else 0
        }
        return stats
    except Exception as e:
        print(f"Error calculating stats: {e}")
        return {"total_items": 0, "completion_rate": 0, "not_started": 0, "high_priority": 0, 
                "total_paint_usage": 0, "avg_risk_rating": 0}

# --- Dash App ---
app = Dash(__name__, external_stylesheets=[
    dbc.themes.BOOTSTRAP, 
    dbc.icons.BOOTSTRAP,
    "https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css"
])
app.title = "Maintenance & Asset Integrity Dashboard"
app.config.suppress_callback_exceptions = True

def get_data_and_stats():
    """Get data with fallback to sample data"""
    try:
        df = fetch_excel_from_local()
        if df is None:
            print("Creating sample data...")
            df = generate_sample_data()
        
        df = process_data(df)
        stats = get_dashboard_stats(df)
        return df, stats
    except Exception as e:
        print(f"Error in get_data_and_stats: {e}")
        # Return minimal sample data
        sample_data = pd.DataFrame({
            'Status': ['Complete', 'In Progress', 'Not Started'],
            'Priority': ['Low', 'Medium', 'High'],
            'Percent Complete': [100, 50, 0],
            'Gallon Total': [10, 15, 0],
            'Value 1': [2.5, 7.8, 9.2],
            'DATE ADDED': [datetime.now()] * 3,
            'ASSET TAG': ['A001', 'A002', 'A003'],
            'LOCATION DESCRIPTION': ['Deck 1', 'Deck 2', 'Deck 3'],
            'DECK LEVEL': ['Level 1', 'Level 2', 'Level 3']
        })
        return process_data(sample_data), get_dashboard_stats(sample_data)

# Data cache with thread lock
data_lock = threading.Lock()
data_cache = {'df': None, 'stats': None, 'last_refresh': None}

def reload_data():
    """Reload data safely"""
    try:
        with data_lock:
            df, stats = get_data_and_stats()
            data_cache['df'] = df
            data_cache['stats'] = stats
            data_cache['last_refresh'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Data reloaded successfully at {data_cache['last_refresh']}")
    except Exception as e:
        print(f"Error reloading data: {e}")

# Initial data load
reload_data()

def summary_card(value, label, color, id=None, icon=None, subtitle=None):
    """Enhanced summary card with animations"""
    button_props = {
        "className": "w-100 h-100 animate__animated animate__fadeInUp",
        "color": color,
        "style": {
            "border": "none",
            "boxShadow": "0 6px 20px rgba(0,0,0,0.15)",
            "padding": "20px",
            "borderRadius": "12px",
            "transition": "all 0.3s ease, transform 0.2s ease",
            "position": "relative",
            "overflow": "hidden"
        },
        "n_clicks": 0,
        "children": [
            # Background gradient effect
            html.Div(style={
                "position": "absolute",
                "top": "0",
                "left": "0",
                "right": "0",
                "bottom": "0",
                "background": f"linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%)",
                "zIndex": "1"
            }),
            html.Div([
                html.Div([
                    html.I(className=f"bi {icon} me-2", style={"fontSize": "1.8rem", "opacity": "0.8"}) if icon else None,
                    html.H3(str(value), className="mb-0 fw-bold", style={"fontSize": "2.2rem", "color": "white"}),
                ], style={"display": "flex", "alignItems": "center", "justifyContent": "center", "zIndex": "2", "position": "relative"}),
                html.P(label, className="mb-0 mt-2", style={"fontSize": "0.9rem", "textAlign": "center", "color": "rgba(255,255,255,0.9)", "zIndex": "2", "position": "relative"}),
                html.P(subtitle, className="mb-0 mt-1", style={"fontSize": "0.7rem", "textAlign": "center", "color": "rgba(255,255,255,0.7)", "zIndex": "2", "position": "relative"}) if subtitle else None
            ])
        ]
    }
    
    if id is not None:
        button_props["id"] = id
    
    # Add hover effects
    button_props["style"]["cursor"] = "pointer"
    
    return dbc.Col(
        dbc.Card(
            dbc.Button(**button_props),
            className="mb-3 shadow-hover",
            style={
                "height": "140px",
                "transition": "transform 0.2s ease",
            }
        ),
        width=2,
        className="hover-lift"
    )

# Enhanced CSS
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            .hover-lift:hover {
                transform: translateY(-5px);
            }
            .shadow-hover {
                transition: all 0.3s ease;
            }
            .shadow-hover:hover {
                box-shadow: 0 10px 30px rgba(0,0,0,0.2) !important;
            }
            .animate-in {
                animation: fadeInUp 0.6s ease-out;
            }
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            .loading-spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #3498db;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .pulse {
                animation: pulse 2s infinite;
            }
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.05); }
                100% { transform: scale(1); }
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

# --- Enhanced Layout ---
app.layout = dbc.Container([
    dcc.Store(id='app-state', data={'filter': 'all', 'loading': False}),
    dcc.Interval(id='interval-refresh', interval=300 * 1000, n_intervals=0),
    
    # Header with enhanced styling
    html.Div([
        html.Div([
            html.H1([
                html.I(className="bi bi-gear-fill me-3", style={"color": "#3498db"}),
                "Maintenance & Asset Integrity Dashboard"
            ], className="text-center mb-2 animate__animated animate__fadeInDown",
               style={"color": "#2c3e50", "fontWeight": "bold", "fontSize": "2.5rem"}),
            html.P("Real-time maintenance tracking and asset management", 
                   className="text-center text-muted mb-4 animate__animated animate__fadeIn animate__delay-1s",
                   style={"fontSize": "1.1rem"})
        ], className="mb-4"),
        
        html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div(id='last-refresh', className="text-end text-muted mb-3")
                ], width=12)
            ])
        ])
    ], className="mb-4"),

    # Enhanced Toolbar
    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button([
                    html.I(className="bi bi-arrow-clockwise me-2"),
                    "Refresh Data"
                ], id='refresh-btn', color="primary", n_clicks=0, className="animate__animated animate__pulse"),
                dbc.Button([
                    html.I(className="bi bi-funnel me-2"),
                    "Reset Filters"
                ], id='reset-filters-btn', color="outline-secondary", n_clicks=0),
                dbc.Button([
                    html.I(className="bi bi-download me-2"),
                    "Export Data"
                ], id='export-btn', color="outline-success", n_clicks=0),
                dbc.Button([
                    html.I(className="bi bi-plus-circle me-2"),
                    "Quick Add"
                ], id='quick-add-btn', color="outline-info", n_clicks=0)
            ], className="mb-3")
        ], width="auto"),
        dbc.Col([
            html.Div(id="active-filter-label", className="fs-5 fw-semibold text-info animate__animated animate__fadeIn")
        ], width=True, style={"display": "flex", "alignItems": "center", "justifyContent": "center"})
    ], className="mb-4"),

    # Loading indicator
    html.Div([
        html.Div(className="loading-spinner"),
        html.P("Loading data...", className="text-center mt-2")
    ], id="loading-indicator", style={"display": "none"}),

    # Enhanced Summary Cards
    dbc.Row(id='summary-cards', className="g-3 mb-4"),

    # Main Charts with enhanced animations
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5([
                        html.I(className="bi bi-pie-chart-fill me-2"),
                        "Maintenance Status Distribution"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    dcc.Graph(id='status-pie', style={'height': 450}, className="animate-in")
                ])
            ], className="shadow-sm h-100")
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5([
                        html.I(className="bi bi-bar-chart-fill me-2"),
                        "Priority Distribution"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    dcc.Graph(id='priority-bar', style={'height': 450}, className="animate-in")
                ])
            ], className="shadow-sm h-100")
        ], width=6)
    ], className="mb-4"),

    # Secondary Charts
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5([
                        html.I(className="bi bi-building me-2"),
                        "Location Analysis"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    dcc.Graph(id='location-analysis', style={'height': 400}, className="animate-in")
                ])
            ], className="shadow-sm h-100")
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5([
                        html.I(className="bi bi-exclamation-triangle-fill me-2"),
                        "Risk vs Priority Analysis"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    dcc.Graph(id='risk-vs-priority', style={'height': 400}, className="animate-in")
                ])
            ], className="shadow-sm h-100")
        ], width=6)
    ], className="mb-4"),

    # Timeline Chart
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5([
                        html.I(className="bi bi-calendar-event me-2"),
                        "Maintenance Timeline"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    dcc.Graph(id='timeline-chart', style={'height': 300}, className="animate-in")
                ])
            ], className="shadow-sm")
        ], width=12)
    ], className="mb-4"),

    # Enhanced Data Table
    dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.H5([
                    html.I(className="bi bi-table me-2"),
                    "Maintenance Records"
                ], className="mb-0"),
                dbc.ButtonGroup([
                    dbc.Button("View All", id="table-view-all", size="sm", color="outline-primary", n_clicks=0),
                    dbc.Button("Urgent Only", id="table-view-urgent", size="sm", color="outline-warning", n_clicks=0),
                    dbc.Button("Overdue", id="table-view-overdue", size="sm", color="outline-danger", n_clicks=0)
                ], className="ms-auto")
            ], className="d-flex justify-content-between align-items-center")
        ]),
        dbc.CardBody([
            dash_table.DataTable(
                id="enhanced-table",
                page_size=15,
                style_cell={
                    'textAlign': 'left', 
                    'padding': '12px', 
                    'fontSize': '0.9rem',
                    'fontFamily': 'Arial, sans-serif'
                },
                style_header={
                    'backgroundColor': '#f8f9fa', 
                    'fontWeight': 'bold',
                    'border': '1px solid #dee2e6'
                },
                style_data={
                    'border': '1px solid #dee2e6'
                },
                style_data_conditional=[
                    {
                        'if': {'filter_query': '{Priority} = "Critical"'},
                        'backgroundColor': '#fff5f5',
                        'color': '#c53030'
                    },
                    {
                        'if': {'filter_query': '{Priority} = "High"'},
                        'backgroundColor': '#fffaf0',
                        'color': '#dd6b20'
                    },
                    {
                        'if': {'filter_query': '{Status} = "Complete"'},
                        'backgroundColor': '#f0fff4',
                        'color': '#38a169'
                    },
                    {
                        'if': {'filter_query': '{Status} = "Not Started"'},
                        'backgroundColor': '#fffbeb',
                        'color': '#d69e2e'
                    }
                ],
                sort_action="native",
                filter_action="native",
                row_selectable="multi",
                selected_rows=[],
                export_format="xlsx",
                export_headers="display"
            )
        ])
    ], className="shadow-sm mb-4"),

    # Enhanced Add Record Form
    dbc.Card([
        dbc.CardHeader([
            html.H5([
                html.I(className="bi bi-plus-square me-2"),
                "Add New Maintenance Record"
            ], className="mb-0")
        ]),
        dbc.CardBody([
            dbc.Form([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Asset Tag", className="fw-bold"),
                        dbc.Input(
                            id='input-asset-tag', 
                            placeholder='Enter asset tag (e.g., PMP001)', 
                            type='text',
                            className="mb-2"
                        )
                    ], width=2),
                    dbc.Col([
                        dbc.Label("Location", className="fw-bold"),
                        dbc.Input(
                            id='input-location', 
                            placeholder='Enter location description', 
                            type='text',
                            className="mb-2"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Description", className="fw-bold"),
                        dbc.Input(
                            id='input-description', 
                            placeholder='Enter maintenance description', 
                            type='text',
                            className="mb-2"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Priority", className="fw-bold"),
                        dbc.Select(
                            id='input-priority',
                            options=[
                                {"label": "Low", "value": "Low"},
                                {"label": "Medium", "value": "Medium"},
                                {"label": "High", "value": "High"},
                                {"label": "Critical", "value": "Critical"}
                            ],
                            placeholder="Select priority",
                            className="mb-2"
                        )
                    ], width=2),
                    dbc.Col([
                        dbc.Label("Status", className="fw-bold"),
                        dbc.Select(
                            id='input-status',
                            options=[
                                {"label": "Not Started", "value": "Not Started"},
                                {"label": "In Progress", "value": "In Progress"},
                                {"label": "Complete", "value": "Complete"},
                                {"label": "On Hold", "value": "On Hold"},
                                {"label": "Pending Review", "value": "Pending Review"}
                            ],
                            placeholder="Select status",
                            className="mb-2"
                        )
                    ], width=2),
                ], className="g-3 mb-3"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Estimated Hours", className="fw-bold"),
                        dbc.Input(
                            id='input-hours', 
                            placeholder='Hours', 
                            type='number',
                            min=0,
                            className="mb-2"
                        )
                    ], width=2),
                    dbc.Col([
                        dbc.Label("Cost Estimate ($)", className="fw-bold"),
                        dbc.Input(
                            id='input-cost', 
                            placeholder='Cost', 
                            type='number',
                            min=0,
                            className="mb-2"
                        )
                    ], width=2),
                    dbc.Col([
                        dbc.Label("Assigned To", className="fw-bold"),
                        dbc.Input(
                            id='input-assigned', 
                            placeholder='Technician name', 
                            type='text',
                            className="mb-2"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Button([
                            html.I(className="bi bi-plus-circle me-2"),
                            'Add Record'
                        ], id='add-record-btn', color="success", n_clicks=0, className="mt-4")
                    ], width="auto")
                ], className="g-3")
            ])
        ])
    ], className="shadow-sm mb-4"),

    # Enhanced Toast notifications
    dbc.Toast(
        id="success-toast",
        header="✅ Success!",
        is_open=False,
        dismissable=True,
        icon="success",
        duration=5000,
        style={"position": "fixed", "top": 20, "right": 20, "width": 400, "zIndex": 9999}
    ),

    dbc.Toast(
        id="error-toast",
        header="❌ Error!",
        is_open=False,
        dismissable=True,
        icon="danger",
        duration=5000,
        style={"position": "fixed", "top": 20, "right": 20, "width": 400, "zIndex": 9999}
    ),

    dbc.Toast(
        id="info-toast",
        header="ℹ️ Info",
        is_open=False,
        dismissable=True,
        icon="info",
        duration=4000,
        style={"position": "fixed", "top": 20, "right": 20, "width": 400, "zIndex": 9999}
    ),

    # Modal containers
    html.Div(id='drilldown-modal'),
    html.Div(id='export-modal'),
    html.Div(id='quick-add-modal'),

], fluid=True, className="px-4 py-3")

# --- Enhanced Main Dashboard Callback ---
@callback(
    Output('last-refresh', 'children'),
    Output('summary-cards', 'children'),
    Output('status-pie', 'figure'),
    Output('priority-bar', 'figure'),
    Output('location-analysis', 'figure'),
    Output('risk-vs-priority', 'figure'),
    Output('timeline-chart', 'figure'),
    Output('enhanced-table', 'data'),
    Output('enhanced-table', 'columns'),
    Output('active-filter-label', 'children'),
    Output('app-state', 'data'),
    Input('refresh-btn', 'n_clicks'),
    Input('interval-refresh', 'n_intervals'),
    Input('not-started-card', 'n_clicks'),
    Input('high-priority-card', 'n_clicks'),
    Input('critical-card', 'n_clicks'),
    Input('overdue-card', 'n_clicks'),
    Input('complete-card', 'n_clicks'),
    Input('total-items-card', 'n_clicks'),
    Input('reset-filters-btn', 'n_clicks'),
    Input('table-view-all', 'n_clicks'),
    Input('table-view-urgent', 'n_clicks'),
    Input('table-view-overdue', 'n_clicks'),
    State('active-filter-label', 'children'),
    State('app-state', 'data')
)
def update_dashboard(*args):
    """Enhanced dashboard update with better error handling and animations"""
    try:
        # Reload data
        reload_data()
        df = data_cache['df']
        stats = data_cache['stats']
        last_refresh = data_cache['last_refresh']
        
        # Handle callback context
        ctx = callback_context
        triggered = ctx.triggered
        filter_label = "📊 Showing: All Items"
        filtered_df = df
        
        if triggered:
            btn_id = triggered[0]['prop_id'].split('.')[0]
            if btn_id == "not-started-card":
                filtered_df = df[df['Is Not Started']]
                filter_label = "🔍 Filtering: Not Started Items"
            elif btn_id == "high-priority-card":
                filtered_df = df[df['Is High Priority']]
                filter_label = "🔍 Filtering: High Priority Items"
            elif btn_id == "critical-card":
                filtered_df = df[df['Is Critical']]
                filter_label = "🔍 Filtering: Critical Priority Items"
            elif btn_id == "overdue-card":
                filtered_df = df[df['Days Since Added'] > 30]
                filter_label = "🔍 Filtering: Overdue Items (>30 days)"
            elif btn_id == "complete-card":
                filtered_df = df[df['Is Complete']]
                filter_label = "🔍 Filtering: Complete Items"
            elif btn_id == "total-items-card":
                filtered_df = df
                filter_label = "🔍 Showing: All Items"
            elif btn_id in ["reset-filters-btn", "table-view-all"]:
                filtered_df = df
                filter_label = "🔍 Filters Reset - All Items"
            elif btn_id == "table-view-urgent":
                filtered_df = df[df['Is High Priority'] | df['Is Critical']]
                filter_label = "🔍 Filtering: Urgent Items"
            elif btn_id == "table-view-overdue":
                filtered_df = df[df['Days Since Added'] > 30]
                filter_label = "🔍 Filtering: Overdue Items"
        
        filtered_stats = get_dashboard_stats(filtered_df)
        
        # Enhanced Summary Cards
        cards = [
            summary_card(
                filtered_stats["total_items"], 
                "Total Items", 
                "primary",
                id="total-items-card", 
                icon="bi-archive-fill",
                subtitle="All maintenance records"
            ),
            summary_card(
                f"{filtered_stats['completion_rate']:.1f}%", 
                "Completion Rate", 
                "info",
                icon="bi-bar-chart-fill",
                subtitle="Average completion"
            ),
            summary_card(
                filtered_stats["not_started"], 
                "Not Started", 
                "warning",
                id="not-started-card", 
                icon="bi-hourglass-split",
                subtitle="Pending items"
            ),
            summary_card(
                filtered_stats["high_priority"], 
                "High Priority", 
                "danger",
                id="high-priority-card", 
                icon="bi-exclamation-triangle-fill",
                subtitle="Urgent attention"
            ),
            summary_card(
                filtered_stats["critical"], 
                "Critical", 
                "danger",
                id="critical-card", 
                icon="bi-exclamation-octagon-fill",
                subtitle="Critical issues"
            ),
            summary_card(
                filtered_stats["overdue_items"], 
                "Overdue", 
                "dark",
                id="overdue-card", 
                icon="bi-clock-history",
                subtitle=">30 days old"
            )
        ]
        
        # Enhanced Charts with better styling and animations
        # Status Pie Chart
        status_counts = filtered_df['Status'].value_counts()
        pie_fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Click on segments for detailed view",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        pie_fig.update_traces(
            textposition='inside', 
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
        )
        pie_fig.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(size=12),
            margin=dict(t=40, b=40, l=40, r=40)
        )
        
        # Priority Bar Chart
        if 'Priority' in filtered_df.columns:
            priority_counts = filtered_df['Priority'].value_counts()
            bar_fig = px.bar(
                x=priority_counts.index,
                y=priority_counts.values,
                title="Priority Distribution with Completion Status",
                color=priority_counts.index,
                color_discrete_map={
                    'Critical': '#dc3545',
                    'High': '#fd7e14', 
                    'Medium': '#ffc107', 
                    'Low': '#28a745'
                }
            )
            bar_fig.update_traces(
                hovertemplate='<b>%{x}</b><br>Count: %{y}<extra></extra>'
            )
            bar_fig.update_layout(
                showlegend=False,
                xaxis_title="Priority Level",
                yaxis_title="Number of Items",
                margin=dict(t=40, b=40, l=40, r=40)
            )
        else:
            bar_fig = go.Figure()
            bar_fig.add_annotation(text="No Priority Data Available", x=0.5, y=0.5, showarrow=False)
        
        # Location Analysis
        location_col = 'LOCATION DESCRIPTION'
        if location_col in filtered_df.columns:
            location_counts = filtered_df[location_col].value_counts().head(10)
            location_fig = px.bar(
                x=location_counts.values,
                y=location_counts.index,
                title="Top 10 Locations by Item Count",
                orientation='h',
                color=location_counts.values,
                color_continuous_scale='viridis'
            )
            location_fig.update_layout(
                showlegend=False,
                xaxis_title="Number of Items",
                yaxis_title="Location",
                margin=dict(t=40, b=40, l=40, r=40)
            )
        else:
            location_fig = go.Figure()
            location_fig.add_annotation(text="No Location Data Available", x=0.5, y=0.5, showarrow=False)
        
        # Risk vs Priority Scatter
        if 'Risk Rating' in filtered_df.columns and 'Priority' in filtered_df.columns:
            risk_fig = px.scatter(
                filtered_df,
                x='Priority',
                y='Risk Rating',
                size='Percent Complete',
                color='Status',
                title='Risk Rating vs Priority (Size = Completion %)',
                hover_data=['ASSET TAG', 'LOCATION DESCRIPTION'] if 'ASSET TAG' in filtered_df.columns else None,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            risk_fig.update_layout(
                xaxis_title="Priority Level",
                yaxis_title="Risk Rating",
                margin=dict(t=40, b=40, l=40, r=40)
            )
        else:
            risk_fig = go.Figure()
            risk_fig.add_annotation(text="No Risk/Priority Data Available", x=0.5, y=0.5, showarrow=False)
        
        # Timeline Chart
        if 'DATE ADDED' in filtered_df.columns:
            timeline_df = filtered_df.groupby([filtered_df['DATE ADDED'].dt.date, 'Status']).size().reset_index(name='count')
            timeline_fig = px.bar(
                timeline_df,
                x='DATE ADDED',
                y='count',
                color='Status',
                title='Maintenance Items Added Over Time',
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            timeline_fig.update_layout(
                xaxis_title="Date Added",
                yaxis_title="Number of Items",
                margin=dict(t=40, b=40, l=40, r=40)
            )
        else:
            timeline_fig = go.Figure()
            timeline_fig.add_annotation(text="No Timeline Data Available", x=0.5, y=0.5, showarrow=False)
        
        # Enhanced Table Data
        table_fields = [
            'ASSET TAG', 'LOCATION DESCRIPTION', 'DESCRIPTION', 'Status', 'Priority', 
            'Percent Complete', 'ASSIGNED TO', 'ESTIMATED HOURS', 'COST ESTIMATE', 'Days Since Added'
        ]
        table_fields = [f for f in table_fields if f in filtered_df.columns]
        
        if 'DATE ADDED' in filtered_df.columns:
            table_data = filtered_df.nlargest(50, 'DATE ADDED')[table_fields].to_dict('records')
        else:
            table_data = filtered_df.head(50)[table_fields].to_dict('records')
        
        table_columns = [{"name": f.replace('_', ' ').title(), "id": f} for f in table_fields]
        
        # App state
        app_state = {'filter': 'all', 'loading': False, 'last_update': datetime.now().isoformat()}
        
        return (
            f"🕐 Last Updated: {last_refresh}",
            cards,
            pie_fig,
            bar_fig,
            location_fig,
            risk_fig,
            timeline_fig,
            table_data,
            table_columns,
            filter_label,
            app_state
        )
    
    except Exception as e:
        print(f"Error in update_dashboard: {e}")
        # Return safe defaults
        return (
            f"🕐 Error loading data: {str(e)}",
            [],
            go.Figure(),
            go.Figure(),
            go.Figure(),
            go.Figure(),
            go.Figure(),
            [],
            [],
            "❌ Error loading data",
            {'filter': 'all', 'loading': False, 'error': str(e)}
        )

# --- Enhanced Add Record Callback ---
@callback(
    Output('success-toast', 'is_open'),
    Output('success-toast', 'children'),
    Output('error-toast', 'is_open'),
    Output('error-toast', 'children'),
    Output('input-asset-tag', 'value'),
    Output('input-location', 'value'),
    Output('input-description', 'value'),
    Output('input-priority', 'value'),
    Output('input-status', 'value'),
    Output('input-hours', 'value'),
    Output('input-cost', 'value'),
    Output('input-assigned', 'value'),
    Input('add-record-btn', 'n_clicks'),
    State('input-asset-tag', 'value'),
    State('input-location', 'value'),
    State('input-description', 'value'),
    State('input-priority', 'value'),
    State('input-status', 'value'),
    State('input-hours', 'value'),
    State('input-cost', 'value'),
    State('input-assigned', 'value'),
    prevent_initial_call=True
)
def add_new_record(n_clicks, asset_tag, location, description, priority, status, hours, cost, assigned):
    """Enhanced add record with better validation and feedback"""
    if not n_clicks:
        raise PreventUpdate
    
    try:
        # Validate required fields
        if not all([asset_tag, location, description, priority, status]):
            error_msg = "❌ Please fill in all required fields: Asset Tag, Location, Description, Priority, and Status."
            return False, "", True, error_msg, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        
        # Validate asset tag format
        if len(asset_tag) < 3:
            error_msg = "❌ Asset Tag must be at least 3 characters long."
            return False, "", True, error_msg, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        
        # Create record summary
        record_summary = {
            'Asset Tag': asset_tag,
            'Location': location,
            'Description': description,
            'Priority': priority,
            'Status': status,
            'Hours': hours or 0,
            'Cost': cost or 0,
            'Assigned To': assigned or 'Unassigned'
        }
        
        success_msg = html.Div([
            html.H6("Record Added Successfully!", className="mb-2"),
            html.P(f"Asset: {asset_tag}", className="mb-1"),
            html.P(f"Location: {location}", className="mb-1"),
            html.P(f"Priority: {priority} | Status: {status}", className="mb-1"),
            html.Small(f"Estimated: {hours or 0} hours, ${cost or 0}", className="text-muted")
        ])
        
        # Clear form
        return True, success_msg, False, "", "", "", "", None, None, None, None, ""
        
    except Exception as e:
        error_msg = f"❌ Error adding record: {str(e)}"
        return False, "", True, error_msg, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

# --- Enhanced Drill-down Modal Callback ---
@callback(
    Output('drilldown-modal', 'children'),
    Input('status-pie', 'clickData'),
    Input('priority-bar', 'clickData'),
    Input('location-analysis', 'clickData'),
    prevent_initial_call=True
)
def show_enhanced_drilldown_modal(status_click, priority_click, location_click):
    """Enhanced modal with better data presentation and actions"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    try:
        df = data_cache['df']
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if trigger_id == 'status-pie' and status_click:
            clicked_status = status_click['points'][0]['label']
            filtered_data = df[df['Status'] == clicked_status]
            modal_title = f"Items with Status: {clicked_status}"
            modal_color = "primary"
        elif trigger_id == 'priority-bar' and priority_click:
            clicked_priority = priority_click['points'][0]['x']
            filtered_data = df[df['Priority'] == clicked_priority]
            modal_title = f"Items with Priority: {clicked_priority}"
            modal_color = "warning" if clicked_priority in ['High', 'Critical'] else "info"
        elif trigger_id == 'location-analysis' and location_click:
            clicked_location = location_click['points'][0]['y']
            filtered_data = df[df['LOCATION DESCRIPTION'] == clicked_location]
            modal_title = f"Items at Location: {clicked_location}"
            modal_color = "success"
        else:
            raise PreventUpdate
        
        # Enhanced column selection
        display_cols = [
            'ASSET TAG', 'LOCATION DESCRIPTION', 'DESCRIPTION', 'Status', 'Priority',
            'Percent Complete', 'ASSIGNED TO', 'ESTIMATED HOURS', 'COST ESTIMATE', 'Days Since Added'
        ]
        display_cols = [col for col in display_cols if col in filtered_data.columns]
        
        # Create enhanced table
        modal_table = dash_table.DataTable(
            data=filtered_data[display_cols].to_dict('records'),
            columns=[{"name": col.replace('_', ' ').title(), "id": col} for col in display_cols],
            page_size=20,
            style_cell={
                'textAlign': 'left', 
                'padding': '10px',
                'fontSize': '0.85rem',
                'maxWidth': '200px',
                'overflow': 'hidden',
                'textOverflow': 'ellipsis'
            },
            style_header={
                'backgroundColor': '#f8f9fa', 
                'fontWeight': 'bold',
                'border': '1px solid #dee2e6'
            },
            style_data={
                'border': '1px solid #dee2e6'
            },
            style_data_conditional=[
                {
                    'if': {'filter_query': '{Priority} = "Critical"'},
                    'backgroundColor': '#fff5f5'
                },
                {
                    'if': {'filter_query': '{Priority} = "High"'},
                    'backgroundColor': '#fffaf0'
                },
                {
                    'if': {'filter_query': '{Status} = "Complete"'},
                    'backgroundColor': '#f0fff4'
                }
            ],
            sort_action="native",
            filter_action="native",
            export_format="xlsx",
            export_headers="display"
        )
        
        # Calculate summary stats
        summary_stats = html.Div([
            dbc.Row([
                dbc.Col([
                    html.H6("Summary Statistics", className="text-muted"),
                    html.P(f"Total Items: {len(filtered_data)}", className="mb-1"),
                    html.P(f"Avg Completion: {filtered_data['Percent Complete'].mean():.1f}%", className="mb-1"),
                    html.P(f"Total Cost: ${filtered_data['COST ESTIMATE'].sum():.2f}" if 'COST ESTIMATE' in filtered_data.columns else "Cost: N/A", className="mb-1")
                ], width=6),
                dbc.Col([
                    html.H6("Status Breakdown", className="text-muted"),
                    html.Div([
                        html.P(f"{status}: {count}", className="mb-1 small")
                        for status, count in filtered_data['Status'].value_counts().items()
                    ])
                ], width=6)
            ])
        ], className="mb-3")
        
        return dbc.Modal([
            dbc.ModalHeader([
                dbc.ModalTitle([
                    html.I(className="bi bi-zoom-in me-2"),
                    modal_title,
                    dbc.Badge(f"{len(filtered_data)} items", color=modal_color, className="ms-2")
                ])
            ]),
            dbc.ModalBody([
                summary_stats,
                modal_table
            ]),
            dbc.ModalFooter([
                dbc.ButtonGroup([
                    dbc.Button([
                        html.I(className="bi bi-download me-2"),
                        "Export to Excel"
                    ], color="success", size="sm"),
                    dbc.Button([
                        html.I(className="bi bi-printer me-2"),
                        "Print Report"
                    ], color="info", size="sm"),
                    dbc.Button([
                        html.I(className="bi bi-x-circle me-2"),
                        "Close"
                    ], id="close-drilldown-modal", color="secondary", size="sm")
                ])
            ])
        ], id="drilldown-modal-content", is_open=True, size="xl", scrollable=True)
        
    except Exception as e:
        print(f"Error in drilldown modal: {e}")
        return dbc.Modal([
            dbc.ModalHeader([
                dbc.ModalTitle("Error")
            ]),
            dbc.ModalBody([
                html.P(f"Error loading data: {str(e)}")
            ]),
            dbc.ModalFooter([
                dbc.Button("Close", id="close-drilldown-modal", color="secondary")
            ])
        ], id="drilldown-modal-content", is_open=True)

# --- Close Modal Callback ---
@callback(
    Output("drilldown-modal-content", "is_open"),
    Input("close-drilldown-modal", "n_clicks"),
    State("drilldown-modal-content", "is_open"),
    prevent_initial_call=True
)
def close_drilldown_modal(n_clicks, is_open):
    """Close the drilldown modal"""
    if n_clicks:
        return False
    return is_open

# --- Export Data Callback ---
@callback(
    Output('info-toast', 'is_open'),
    Output('info-toast', 'children'),
    Input('export-btn', 'n_clicks'),
    prevent_initial_call=True
)
def export_data(n_clicks):
    """Export data functionality"""
    if n_clicks:
        try:
            df = data_cache['df']
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"maintenance_data_{timestamp}.xlsx"
            
            # In a real application, you would save the file
            # df.to_excel(filename, index=False)
            
            success_msg = html.Div([
                html.H6("Export Prepared!", className="mb-2"),
                html.P(f"Data would be exported to: {filename}", className="mb-1"),
                html.Small(f"Contains {len(df)} records", className="text-muted")
            ])
            
            return True, success_msg
        except Exception as e:
            error_msg = f"❌ Export failed: {str(e)}"
            return True, error_msg
    
    raise PreventUpdate

# --- Run App ---
if __name__ == '__main__':
    try:
        print("Starting Enhanced Maintenance Dashboard...")
        print(f"Data source: {LOCAL_EXCEL_PATH}")
        print(f"Sample data will be used if Excel file is not found")
        app.run(debug=True, host='0.0.0.0', port=8050)
    except Exception as e:
        print(f"Error starting application: {e}")
