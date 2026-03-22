import streamlit as st


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        /* ── Google Font ───────────────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

        /* ── CSS Variables ─────────────────────────────────────────────────── */
        :root {
            --accent:       #2563EB;
            --accent-light: #3B82F6;
            --accent-2:     #7C3AED;
            --success:      #059669;
            --warning:      #D97706;
            --danger:       #DC2626;
            --radius:       12px;
            --radius-sm:    6px;
            --shadow:       0 2px 16px rgba(0,0,0,.08);
            --shadow-lg:    0 8px 32px rgba(0,0,0,.12);
        }

        [data-testid="stAppViewContainer"] {
            --bg:         #F8FAFC;
            --surface:    #FFFFFF;
            --border:     #E2E8F0;
            --text-main:  #0F172A;
            --text-muted: #64748B;
            --metric-bg:  #F1F5F9;
        }

        /* ── Base ──────────────────────────────────────────────────────────── */
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'DM Sans', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
        }

        /* ── Hide auto sidebar nav ─────────────────────────────────────────── */
        [data-testid="stSidebarNav"] { display: none !important; }

        /* ── Sidebar ───────────────────────────────────────────────────────── */
        [data-testid="stSidebar"] {
            background: var(--surface);
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            text-align: left;
            background: transparent;
            border: none;
            border-radius: 8px;
            padding: 10px 14px;
            color: #374151;
            font-size: 0.875rem;
            font-weight: 500;
            transition: background 0.15s;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: #eef2ff;
            color: #2563eb;
        }

        /* ── Main header ───────────────────────────────────────────────────── */
        .main-header {
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: var(--accent);
            margin-bottom: .25rem;
        }
        .sub-header {
            font-size: 1rem;
            color: var(--text-muted);
            font-weight: 400;
            margin-bottom: 1.5rem;
        }
        .section-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text-main);
            margin: 1.25rem 0 .5rem;
        }

        /* ── Metric cards ──────────────────────────────────────────────────── */
        .metric-card {
            background: var(--metric-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 1rem 1.25rem;
            box-shadow: var(--shadow);
            transition: transform .15s ease, box-shadow .15s ease;
        }
        .metric-card:hover { transform: translateY(-2px); box-shadow: var(--shadow-lg); }

        /* ── Streamlit metric override ─────────────────────────────────────── */
        [data-testid="metric-container"] {
            background: linear-gradient(135deg, #ffffff 0%, #f0f4ff 100%);
            border: 1px solid #c7d7fd;
            border-top: 3px solid #2563eb;
            border-radius: 12px;
            padding: 20px 24px !important;
            box-shadow: 0 4px 12px rgba(37,99,235,0.08);
            transition: box-shadow 0.2s;
        }
        [data-testid="metric-container"]:hover {
            box-shadow: 0 6px 20px rgba(37,99,235,0.15);
        }
        [data-testid="metric-container"] > div:first-child {
            color: #2563eb;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 6px;
        }
        [data-testid="metric-container"] [data-testid="stMetricValue"] {
            font-size: 1.55rem;
            font-weight: 800;
            color: #111827;
        }

        /* ── Headings ──────────────────────────────────────────────────────── */
        h1 {
            font-size: 1.55rem;
            font-weight: 700;
            color: #111827;
            margin-bottom: 0.15rem;
        }
        h2, h3 {
            font-size: 1.3rem;
            color: #1f2937;
            font-weight: 600;
        }

        /* ── Buttons ───────────────────────────────────────────────────────── */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.875rem;
            transition: all 0.15s;
            border: 1px solid #d1d5db;
            color: #374151;
        }
        .stButton > button:hover {
            border-color: #2563eb;
            color: #2563eb;
        }

        /* ── Tabs ───────────────────────────────────────────────────────────── */
        [data-baseweb="tab-list"] { gap: 4px; }
        [data-baseweb="tab"]      { border-radius: var(--radius-sm); font-weight: 500; }
        [data-testid="stTabs"] [role="tab"] {
            font-weight: 600;
            font-size: 0.875rem;
            color: #6b7280;
        }
        [data-testid="stTabs"] [aria-selected="true"] {
            color: #2563eb;
            border-bottom: 2px solid #2563eb;
        }

        /* ── Tables ─────────────────────────────────────────────────────────── */
        [data-testid="stDataFrame"] {
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            overflow: hidden;
        }

        /* ── Alerts ─────────────────────────────────────────────────────────── */
        .stAlert { border-radius: 10px; font-size: 0.875rem; }
        .alert-info    { background:#DBEAFE; color:#1E40AF; border-left:4px solid #2563EB; border-radius:6px; padding:.6rem 1rem; font-size:.85rem; }
        .alert-warning { background:#FEF3C7; color:#92400E; border-left:4px solid #D97706; border-radius:6px; padding:.6rem 1rem; font-size:.85rem; }
        .alert-success { background:#D1FAE5; color:#065F46; border-left:4px solid #059669; border-radius:6px; padding:.6rem 1rem; font-size:.85rem; }

        /* ── Form inputs ─────────────────────────────────────────────────────── */
        .stTextInput input,
        .stNumberInput input,
        .stSelectbox > div > div {
            border-radius: 8px !important;
            border-color: #d1d5db !important;
            font-size: 0.875rem;
        }

        /* ── Expander ────────────────────────────────────────────────────────── */
        [data-testid="stExpander"] {
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
            background: #ffffff;
        }
        [data-testid="stExpander"] summary {
            font-weight: 600;
            color: #374151;
            font-size: 0.9rem;
        }

        

        /* ── Divider ─────────────────────────────────────────────────────────── */
        hr { border: none; border-top: 1px solid var(--border); margin: 1rem 0; }

        /* ── Footer ──────────────────────────────────────────────────────────── */
        .footer {
            text-align: center;
            color: var(--text-muted);
            font-size: .78rem;
            padding: 2rem 1rem 1rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

