import os
import pandas as pd
from datetime import datetime
import threading

from dash import Dash, dcc, html, Input, Output, State, dash_table, callback_context, callback, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURATION (LOCAL TEST) ---
LOCAL_EXCEL_PATH = r"C:\test\demo.xlsx"


def fetch_excel_from_local():
    try:
        df = pd.read_excel(LOCAL_EXCEL_PATH, engine="openpyxl")
        return df
    except Exception as e:
        print(f"Error reading Excel file from local path: {e}")
        return None


def process_data(df):
    df = df.copy()
    if 'Percent Complete' in df.columns:
        df['Percent Complete'] = (
            df['Percent Complete'].astype(str).str.replace('%', '', regex=False).str.strip().replace('', '0').astype(
                float)
        )
    else:
        df['Percent Complete'] = 0

    df['Status_lower'] = df['Status'].str.lower().fillna('')
    df['Is Complete'] = df['Status_lower'] == 'complete'
    df['Is Not Started'] = df['Status_lower'] == 'not started'
    df['Is In Progress'] = df['Status_lower'] == 'in progress'

    if "Priority" in df.columns:
        df['Priority_lower'] = df['Priority'].str.lower().fillna('')
        df['Is High Priority'] = df['Priority_lower'] == 'high'
    else:
        df['Is High Priority'] = False

    if "Gallon Total" in df.columns:
        df['Gallons'] = pd.to_numeric(df['Gallon Total'], errors='coerce').fillna(0)
    else:
        df['Gallons'] = 0

    if "Value 1" in df.columns:
        df['Risk Rating'] = pd.to_numeric(df['Value 1'], errors='coerce').fillna(0)
    else:
        df['Risk Rating'] = 0

    if "DATE ADDED" in df.columns:
        try:
            df['DATE ADDED'] = pd.to_datetime(df['DATE ADDED'], dayfirst=True, errors='coerce')
        except Exception:
            df['DATE ADDED'] = df['DATE ADDED']

    return df


def get_dashboard_stats(df):
    stats = {
        "total_items": len(df),
        "completion_rate": df['Percent Complete'].mean() if len(df) else 0,
        "not_started": df['Is Not Started'].sum(),
        "high_priority": df['Is High Priority'].sum(),
        "total_paint_usage": df['Gallons'].sum(),
        "avg_risk_rating": df['Risk Rating'].mean() if len(df) else 0,
    }
    return stats


# --- Dash App ---
app = Dash(__name__, external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP])
app.title = "Maintenance & Asset Integrity Dashboard"
app.config.suppress_callback_exceptions = True


def get_data_and_stats():
    df = fetch_excel_from_local()
    if df is None:
        # Create sample data if file doesn't exist
        sample_data = {
            'Status': ['Complete', 'In Progress', 'Not Started', 'Complete', 'High Priority'],
            'Priority': ['Low', 'Medium', 'High', 'Low', 'High'],
            'Percent Complete': [100, 50, 0, 100, 25],
            'Gallon Total': [10, 15, 0, 5, 20],
            'Value 1': [2.5, 7.8, 9.2, 1.1, 8.5],
            'DATE ADDED': [datetime.now()] * 5,
            'ASSET TAG': ['A001', 'A002', 'A003', 'A004', 'A005'],
            'LOCATION DESCRIPTION': ['Deck 1', 'Deck 2', 'Deck 3', 'Deck 1', 'Deck 2'],
            'DECK LEVEL': ['Level 1', 'Level 2', 'Level 3', 'Level 1', 'Level 2']
        }
        df = pd.DataFrame(sample_data)

    df = process_data(df)
    stats = get_dashboard_stats(df)
    return df, stats


# Data cache with thread lock
data_lock = threading.Lock()
data_cache = {'df': None, 'stats': None, 'last_refresh': None}


def reload_data():
    with data_lock:
        df, stats = get_data_and_stats()
        data_cache['df'] = df
        data_cache['stats'] = stats
        data_cache['last_refresh'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Initial data load
reload_data()


def summary_card(value, label, color, id=None, icon=None):
    button_props = {
        "className": "w-100 h-100",
        "color": color,
        "style": {
            "border": "none",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.1)",
            "padding": "20px",
            "borderRadius": "8px",
            "transition": "all 0.3s ease"
        },
        "n_clicks": 0,
        "children": [
            html.Div([
                html.I(className=f"bi {icon} me-2", style={"fontSize": "1.5rem"}) if icon else None,
                html.H3(value, className="mb-0 fw-bold", style={"fontSize": "2rem"}),
            ], style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
            html.P(label, className="mb-0 mt-2", style={"fontSize": "0.9rem", "textAlign": "center"})
        ]
    }

    if id is not None:
        button_props["id"] = id

    return dbc.Col(
        dbc.Card(
            dbc.Button(**button_props),
            className="mb-3",
            style={"height": "120px"}
        ),
        width=2
    )


# --- Layout ---
app.layout = dbc.Container([
    dcc.Interval(id='interval-refresh', interval=300 * 1000, n_intervals=0),

    # Header
    html.Div([
        html.H1("🔧 Maintenance & Asset Integrity Dashboard",
                className="text-center mb-4",
                style={"color": "#2c3e50", "fontWeight": "bold"}),
        html.Div(id='last-refresh', className="text-end text-muted mb-3"),
    ]),

    # Toolbar
    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button("🔄 Refresh Data", id='refresh-btn', color="primary", n_clicks=0),
                dbc.Button("🔍 Reset Filters", id='reset-filters-btn', color="outline-secondary", n_clicks=0),
            ])
        ], width="auto"),
        dbc.Col([
            html.Div(id="active-filter-label", className="fs-5 fw-semibold text-info")
        ], width=True, style={"display": "flex", "alignItems": "center", "justifyContent": "center"})
    ], className="mb-4"),

    # Summary Cards
    dbc.Row(id='summary-cards', className="g-2 mb-4"),

    # Main Charts
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📊 Maintenance Status Distribution"),
                dbc.CardBody([
                    dcc.Graph(id='status-pie', style={'height': 400})
                ])
            ], className="shadow-sm")
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🎯 Priority Distribution"),
                dbc.CardBody([
                    dcc.Graph(id='priority-bar', style={'height': 400})
                ])
            ], className="shadow-sm")
        ], width=6)
    ], className="mb-4"),

    # Secondary Charts
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🏢 Deck Level Analysis"),
                dbc.CardBody([
                    dcc.Graph(id='deck-bar', style={'height': 400})
                ])
            ], className="shadow-sm")
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("⚠️ Risk vs Priority Analysis"),
                dbc.CardBody([
                    dcc.Graph(id='risk-vs-priority', style={'height': 400})
                ])
            ], className="shadow-sm")
        ], width=6)
    ], className="mb-4"),

    # Recent Items Table
    dbc.Card([
        dbc.CardHeader("📋 Recent Maintenance Items"),
        dbc.CardBody([
            dash_table.DataTable(
                id="recent-table",
                page_size=10,
                style_cell={'textAlign': 'left', 'padding': '10px', 'fontSize': '0.9rem'},
                style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
                style_data_conditional=[
                    {'if': {'column_id': 'Priority', 'filter_query': '{Priority} = "High"'},
                     'backgroundColor': '#ffe5e5'},
                    {'if': {'column_id': 'Status', 'filter_query': '{Status} = "Not Started"'},
                     'backgroundColor': '#fff6cc'},
                    {'if': {'column_id': 'Status', 'filter_query': '{Status} = "Complete"'},
                     'backgroundColor': '#e5ffe5'},
                ],
                sort_action="native",
                filter_action="native"
            )
        ])
    ], className="shadow-sm mb-4"),

    # Add Record Form
    dbc.Card([
        dbc.CardHeader("➕ Add New Maintenance Record (Demo)"),
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Asset Tag"),
                    dbc.Input(id='input-asset-tag', placeholder='Enter asset tag', type='text')
                ], width=2),
                dbc.Col([
                    dbc.Label("Location"),
                    dbc.Input(id='input-location', placeholder='Enter location', type='text')
                ], width=3),
                dbc.Col([
                    dbc.Label("Description"),
                    dbc.Input(id='input-description', placeholder='Enter description', type='text')
                ], width=3),
                dbc.Col([
                    dbc.Label("Priority"),
                    dbc.Select(
                        id='input-priority',
                        options=[
                            {"label": "Low", "value": "Low"},
                            {"label": "Medium", "value": "Medium"},
                            {"label": "High", "value": "High"}
                        ],
                        placeholder="Select priority"
                    )
                ], width=2),
                dbc.Col([
                    dbc.Label("Status"),
                    dbc.Select(
                        id='input-status',
                        options=[
                            {"label": "Not Started", "value": "Not Started"},
                            {"label": "In Progress", "value": "In Progress"},
                            {"label": "Complete", "value": "Complete"}
                        ],
                        placeholder="Select status"
                    )
                ], width=2),
            ], className="g-3 mb-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Button('➕ Add Record', id='add-record-btn', color="success", n_clicks=0)
                ], width="auto")
            ])
        ])
    ], className="shadow-sm"),

    # Toast notifications
    dbc.Toast(
        id="add-toast",
        header="✅ Success!",
        is_open=False,
        dismissable=True,
        icon="success",
        duration=4000,
        style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999}
    ),

    dbc.Toast(
        id="error-toast",
        header="❌ Error!",
        is_open=False,
        dismissable=True,
        icon="danger",
        duration=4000,
        style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999}
    ),

    # Modal placeholder
    html.Div(id='drilldown-modal'),

], fluid=True)


# --- Main Dashboard Callback ---
@callback(
    Output('last-refresh', 'children'),
    Output('summary-cards', 'children'),
    Output('status-pie', 'figure'),
    Output('priority-bar', 'figure'),
    Output('deck-bar', 'figure'),
    Output('risk-vs-priority', 'figure'),
    Output('recent-table', 'data'),
    Output('recent-table', 'columns'),
    Output('active-filter-label', 'children'),
    Input('refresh-btn', 'n_clicks'),
    Input('interval-refresh', 'n_intervals'),
    Input('not-started-card', 'n_clicks'),
    Input('high-priority-card', 'n_clicks'),
    Input('total-items-card', 'n_clicks'),
    Input('reset-filters-btn', 'n_clicks'),
    State('active-filter-label', 'children')
)
def update_dashboard(n_clicks, n_intervals, not_started_click, high_priority_click,
                     total_items_click, reset_filter_click, active_filter_label):
    reload_data()
    df = data_cache['df']
    stats = data_cache['stats']
    last_refresh = data_cache['last_refresh']

    # Filter logic
    ctx = callback_context
    triggered = ctx.triggered
    filter_label = "Showing: All Items"
    filtered_df = df

    if triggered:
        btn_id = triggered[0]['prop_id'].split('.')[0]
        if btn_id == "not-started-card":
            filtered_df = df[df['Is Not Started']]
            filter_label = "🔍 Filtering: Not Started Items"
        elif btn_id == "high-priority-card":
            filtered_df = df[df['Is High Priority']]
            filter_label = "🔍 Filtering: High Priority Items"
        elif btn_id == "total-items-card":
            filtered_df = df
            filter_label = "🔍 Showing: All Items"
        elif btn_id == "reset-filters-btn":
            filtered_df = df
            filter_label = "🔍 Filters Reset - All Items"
        else:
            filter_label = active_filter_label or "Showing: All Items"

    filtered_stats = get_dashboard_stats(filtered_df)

    # Summary Cards
    cards = [
        summary_card(filtered_stats["total_items"], "Total Maintenance Items", "primary",
                     id="total-items-card", icon="bi-archive-fill"),
        summary_card(f"{filtered_stats['completion_rate']:.1f}%", "Overall Completion Rate", "info",
                     icon="bi-bar-chart-fill"),
        summary_card(filtered_stats["not_started"], "Items Not Started", "warning",
                     id="not-started-card", icon="bi-hourglass-split"),
        summary_card(filtered_stats["high_priority"], "High Priority Items", "danger",
                     id="high-priority-card", icon="bi-exclamation-triangle-fill"),
        summary_card(f"{filtered_stats['total_paint_usage']:.0f}", "Total Paint Usage (gal)", "secondary",
                     icon="bi-droplet-fill"),
        summary_card(f"{filtered_stats['avg_risk_rating']:.1f}", "Average Risk Rating", "dark",
                     icon="bi-shield-lock-fill"),
    ]

    # Charts with animations
    # Status Pie Chart
    status_counts = filtered_df['Status'].value_counts()
    pie_fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Click on a slice to see details",
        hole=0.4,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    pie_fig.update_traces(textposition='inside', textinfo='percent+label')
    pie_fig.update_layout(
        transition={'duration': 500, 'easing': 'cubic-in-out'},
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Priority Bar Chart
    if 'Priority' in filtered_df.columns:
        priority_counts = filtered_df['Priority'].value_counts()
        bar_fig = px.bar(
            x=priority_counts.index,
            y=priority_counts.values,
            title="Priority Distribution",
            color=priority_counts.index,
            color_discrete_map={'High': '#e74c3c', 'Medium': '#f39c12', 'Low': '#27ae60'}
        )
        bar_fig.update_layout(
            transition={'duration': 500, 'easing': 'cubic-in-out'},
            showlegend=False
        )
    else:
        bar_fig = go.Figure()
        bar_fig.add_annotation(text="No Priority Data Available", x=0.5, y=0.5, showarrow=False)

    # Deck Bar Chart
    deck_col = 'DECK LEVEL' if 'DECK LEVEL' in filtered_df.columns else 'Deck Level'
    if deck_col in filtered_df.columns:
        deck_counts = filtered_df[deck_col].value_counts()
        deck_fig = px.bar(
            x=deck_counts.index,
            y=deck_counts.values,
            title="Items by Deck Level",
            color=deck_counts.values,
            color_continuous_scale='viridis'
        )
        deck_fig.update_layout(
            transition={'duration': 500, 'easing': 'cubic-in-out'},
            showlegend=False
        )
    else:
        deck_fig = go.Figure()
        deck_fig.add_annotation(text="No Deck Level Data Available", x=0.5, y=0.5, showarrow=False)

    # Risk vs Priority Scatter
    if 'Risk Rating' in filtered_df.columns and 'Priority' in filtered_df.columns:
        risk_fig = px.strip(
            filtered_df,
            x='Priority',
            y='Risk Rating',
            title='Risk Rating Distribution by Priority',
            color='Priority',
            stripmode='overlay',
            hover_data=['ASSET TAG'] if 'ASSET TAG' in filtered_df.columns else None
        )
        risk_fig.update_layout(
            transition={'duration': 500, 'easing': 'cubic-in-out'}
        )
    else:
        risk_fig = go.Figure()
        risk_fig.add_annotation(text="No Risk/Priority Data Available", x=0.5, y=0.5, showarrow=False)

    # Recent Items Table
    table_fields = ['DATE ADDED', 'ASSET TAG', 'LOCATION DESCRIPTION', 'Status', 'Priority', 'Percent Complete']
    table_fields = [f for f in table_fields if f in filtered_df.columns]

    if 'DATE ADDED' in filtered_df.columns:
        table_data = filtered_df.nlargest(10, 'DATE ADDED')[table_fields].to_dict('records')
    else:
        table_data = filtered_df.head(10)[table_fields].to_dict('records')

    table_columns = [{"name": f.replace('_', ' ').title(), "id": f} for f in table_fields]

    return (
        f"🕐 Last Updated: {last_refresh}",
        cards,
        pie_fig,
        bar_fig,
        deck_fig,
        risk_fig,
        table_data,
        table_columns,
        filter_label
    )


# --- Add Record Callback ---
@callback(
    Output('add-toast', 'is_open'),
    Output('add-toast', 'children'),
    Output('error-toast', 'is_open'),
    Output('error-toast', 'children'),
    Output('input-asset-tag', 'value'),
    Output('input-location', 'value'),
    Output('input-description', 'value'),
    Output('input-priority', 'value'),
    Output('input-status', 'value'),
    Input('add-record-btn', 'n_clicks'),
    State('input-asset-tag', 'value'),
    State('input-location', 'value'),
    State('input-description', 'value'),
    State('input-priority', 'value'),
    State('input-status', 'value'),
    prevent_initial_call=True
)
def add_new_record(n_clicks, asset_tag, location, description, priority, status):
    if not n_clicks:
        raise PreventUpdate

    if asset_tag and location and description and priority and status:
        success_msg = f"✅ Record added: {asset_tag} at {location} - {description} ({priority} priority, {status})"
        return True, success_msg, False, "", "", "", "", None, None
    else:
        error_msg = "❌ Please fill in all fields before adding the record."
        return False, "", True, error_msg, no_update, no_update, no_update, no_update, no_update


# --- Drill-down Modal Callback ---
@callback(
    Output('drilldown-modal', 'children'),
    Input('status-pie', 'clickData'),
    prevent_initial_call=True
)
def show_drilldown_modal(clickData):
    if not clickData:
        raise PreventUpdate

    clicked_status = clickData['points'][0]['label']
    df = data_cache['df']
    filtered_data = df[df['Status'] == clicked_status]

    # Select relevant columns for the modal table
    display_cols = ['ASSET TAG', 'LOCATION DESCRIPTION', 'Priority', 'Percent Complete', 'DATE ADDED']
    display_cols = [col for col in display_cols if col in filtered_data.columns]

    modal_table = dash_table.DataTable(
        data=filtered_data[display_cols].to_dict('records'),
        columns=[{"name": col.replace('_', ' ').title(), "id": col} for col in display_cols],
        page_size=15,
        style_cell={'textAlign': 'left', 'padding': '8px'},
        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
        sort_action="native",
        filter_action="native"
    )

    return dbc.Modal([
        dbc.ModalHeader([
            dbc.ModalTitle(f"📋 Items with Status: {clicked_status} ({len(filtered_data)} items)")
        ]),
        dbc.ModalBody([
            modal_table
        ]),
        dbc.ModalFooter([
            dbc.Button("Close", id="close-drilldown-modal", className="ms-auto", n_clicks=0)
        ])
    ], id="drilldown-modal-content", is_open=True, size="xl")


# --- Close Modal Callback ---
@callback(
    Output("drilldown-modal-content", "is_open"),
    Input("close-drilldown-modal", "n_clicks"),
    State("drilldown-modal-content", "is_open"),
    prevent_initial_call=True
)
def close_drilldown_modal(n_clicks, is_open):
    if n_clicks:
        return False
    return is_open


# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True, port=8050)
