# style.py - Add spacing fixes
def load_css(theme="light"):
    """
    Load CSS based on selected theme
    """
    
    if theme == "light":
        return """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            
            /* Remove default Streamlit padding */
            .main .block-container {
                padding-top: 0.5rem !important;
                padding-bottom: 0rem !important;
            }
            
            /* Reduce spacing between header and content */
            .stApp {
                background: #f8fafc;
                font-family: 'Inter', sans-serif;
            }
            
            /* Reduce margin on main header */
            .main-header {
                background: white;
                padding: 1.2rem 2rem;
                border-radius: 12px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                margin-bottom: 0.5rem !important;
                border: 1px solid #e2e8f0;
                text-align: center;
            }
            
            .main-header h1 {
                font-size: 1.5rem;
                font-weight: 600;
                color: #0f172a;
                margin-bottom: 0.2rem;
            }
            
            .main-header p {
                color: #475569;
                font-size: 0.85rem;
                margin-bottom: 0;
            }
            
            /* Reduce spacing between elements */
            .stMarkdown {
                margin-bottom: 0.5rem !important;
            }
            
            /* Reduce spacing for columns */
            .row-widget.stButton {
                margin-top: 0rem;
            }
            
            /* Reduce spacing for date inputs */
            .stDateInput {
                margin-bottom: 0.5rem;
            }
            
            /* Section headers with less spacing */
            .section-header {
                font-size: 1.1rem;
                font-weight: 600;
                color: #0f172a;
                margin: 0.8rem 0 0.5rem 0 !important;
                padding-bottom: 0.3rem;
                border-bottom: 2px solid #e2e8f0;
                display: inline-block;
            }
            
            /* KPI metrics row spacing */
            .stColumns {
                gap: 0.8rem !important;
                margin-bottom: 0.5rem !important;
            }
            
            /* Metric cards */
            .metric-card {
                background: white;
                padding: 0.8rem !important;
                border-radius: 12px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
                text-align: center;
                border: 1px solid #e2e8f0;
                margin-bottom: 0.5rem;
            }
            
            .metric-value {
                font-size: 1.6rem;
                font-weight: 700;
                color: #0f172a;
                line-height: 1.2;
            }
            
            .metric-label {
                font-size: 0.7rem;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-top: 0.2rem;
            }
            
            /* Tabs styling */
            .stTabs [data-baseweb="tab-list"] {
                gap: 4px;
                background: white;
                padding: 4px;
                border-radius: 12px;
                border: 1px solid #e2e8f0;
                margin-top: 0.5rem;
                margin-bottom: 0.5rem;
            }
            
            .stTabs [data-baseweb="tab"] {
                border-radius: 8px !important;
                padding: 6px 16px !important;
                font-weight: 500;
                color: #475569 !important;
                font-size: 0.85rem;
            }
            
            /* Reduce spacing for dataframe */
            .stDataFrame {
                margin-top: 0.5rem !important;
            }
            
            /* Alert section spacing */
            .stAlert {
                margin-top: 0rem !important;
                margin-bottom: 0.5rem !important;
                padding: 0.5rem 1rem !important;
            }
            
            /* Sidebar spacing */
            .css-1d391kg .block-container {
                padding-top: 1rem;
            }
            
            /* Horizontal line spacing */
            hr {
                margin: 0.5rem 0 !important;
            }
            
            /* Table header spacing */
            .stDataFrame thead tr th {
                background: #f1f5f9 !important;
                color: #1e293b !important;
                font-weight: 600 !important;
                font-size: 0.8rem !important;
                padding: 8px 12px !important;
            }
            
            .stDataFrame tbody tr td {
                background: white !important;
                color: #334155 !important;
                padding: 8px 12px !important;
                font-size: 0.85rem !important;
            }
            
            /* Sidebar */
            .css-1d391kg {
                background: #1e293b !important;
                border-right: 1px solid #334155 !important;
            }
            
            .css-1d391kg .stMarkdown h3 {
                margin-top: 0.5rem;
                margin-bottom: 0.5rem;
            }
            
            /* Selected menu item */
            .css-1d391kg .st-emotion-cache-1v3fvcr[data-selected="true"] {
                background-color: #cbd5e1 !important;
                color: #1e293b !important;
                border-left: 3px solid #6366f1 !important;
            }
            
            /* Sidebar metrics */
            .css-1d391kg .stMetric {
                margin-bottom: 0.5rem;
            }
            
            /* Badges */
            .badge-success {
                background: #dcfce7;
                color: #166534;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.7rem;
                font-weight: 500;
                display: inline-block;
            }
            
            .badge-danger {
                background: #fee2e2;
                color: #991b1b;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.7rem;
                font-weight: 500;
                display: inline-block;
            }
            
            .badge-warning {
                background: #fef9c3;
                color: #854d0e;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.7rem;
                font-weight: 500;
                display: inline-block;
            }
        </style>
        """
    
    else:
        # Dark theme
        return """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
            
            .main .block-container {
                padding-top: 0.5rem !important;
            }
            
            .stApp {
                background: #0f172a;
                font-family: 'Inter', sans-serif;
            }
            
            .main-header {
                background: #1e293b;
                padding: 1.2rem 2rem;
                border-radius: 12px;
                margin-bottom: 0.5rem !important;
                border: 1px solid #334155;
                text-align: center;
            }
            
            .main-header h1 {
                font-size: 1.5rem;
                color: #f1f5f9;
            }
            
            .main-header p {
                color: #94a3b8;
                font-size: 0.85rem;
            }
            
            .section-header {
                font-size: 1.1rem;
                font-weight: 600;
                color: #f1f5f9;
                margin: 0.8rem 0 0.5rem 0 !important;
                border-bottom: 2px solid #334155;
            }
            
            .metric-card {
                background: #1e293b;
                padding: 0.8rem !important;
                border-radius: 12px;
                text-align: center;
                border: 1px solid #334155;
            }
            
            .metric-value {
                font-size: 1.6rem;
                color: #f1f5f9;
            }
            
            .metric-label {
                font-size: 0.7rem;
                color: #94a3b8;
            }
            
            .stDataFrame thead tr th {
                background: #1e293b !important;
                color: #f1f5f9 !important;
            }
            
            .stDataFrame tbody tr td {
                background: #0f172a !important;
                color: #cbd5e1 !important;
            }
            
            .stButton > button {
                background: #6366f1 !important;
                color: white !important;
            }
            
            .css-1d391kg {
                background: #0f172a !important;
            }
            
            .css-1d391kg .st-emotion-cache-1v3fvcr[data-selected="true"] {
                background-color: #cbd5e1 !important;
                color: #0f172a !important;
            }
        </style>
        """