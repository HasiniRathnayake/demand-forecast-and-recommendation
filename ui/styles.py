import streamlit as st


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        /* ── Google Font ───────────────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

        /* ── CSS Variables – Light / Dark ──────────────────────────────────── */
        :root {
            --accent:       #2563EB;
            --accent-light: #3B82F6;
            --accent-2:     #7C3AED;
            --success:      #059669;
            --warning:      #D97706;
            --danger:       #DC2626;
            --holiday-clr:  #EA580C;
            --weekend-clr:  #0891B2;
            --ai-clr:       #7C3AED;
            --radius:       12px;
            --radius-sm:    6px;
            --shadow:       0 2px 16px rgba(0,0,0,.08);
            --shadow-lg:    0 8px 32px rgba(0,0,0,.12);
        }

        /* Light */
        [data-testid="stAppViewContainer"] {
            --bg:         #F8FAFC;
            --surface:    #FFFFFF;
            --border:     #E2E8F0;
            --text-main:  #0F172A;
            --text-muted: #64748B;
            --metric-bg:  #F1F5F9;
        }
        /* Dark  */
        @media (prefers-color-scheme: dark) {
            [data-testid="stAppViewContainer"] {
                --bg:         #0F172A;
                --surface:    #1E293B;
                --border:     #334155;
                --text-main:  #F1F5F9;
                --text-muted: #94A3B8;
                --metric-bg:  #1E293B;
            }
        }

        /* ── Base ──────────────────────────────────────────────────────────── */
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'DM Sans', sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
        }

        /* ── Sidebar ───────────────────────────────────────────────────────── */
        [data-testid="stSidebar"] {
            background: var(--surface);
            border-right: 1px solid var(--border);
        }
<<<<<<< HEAD
=======
        /* Hide auto-discovered page navigation */
        [data-testid="stSidebarNav"] { display: none !important; }
>>>>>>> origin/main

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
            display: flex;
            align-items: center;
            gap: .4rem;
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
        .metric-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--accent);
            font-family: 'DM Mono', monospace;
        }
        .metric-label {
            font-size: .75rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .metric-delta {
            font-size: .8rem;
            color: var(--success);
            font-weight: 500;
            margin-top: .2rem;
        }

        /* ── Badges ────────────────────────────────────────────────────────── */
        .badge {
            display: inline-flex;
            align-items: center;
            gap: .25rem;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: .72rem;
            font-weight: 600;
            line-height: 1.6;
            letter-spacing: .02em;
        }
        .badge-holiday  { background: #FEF3C7; color: #92400E; }
        .badge-weekend  { background: #ECFDF5; color: #065F46; }
        .badge-ai       { background: #EDE9FE; color: #5B21B6; }
        .badge-model    { background: #DBEAFE; color: #1E40AF; }
        .badge-weather  { background: #F0FDF4; color: #166534; }

        @media (prefers-color-scheme: dark) {
            .badge-holiday  { background: #78350F; color: #FDE68A; }
            .badge-weekend  { background: #064E3B; color: #6EE7B7; }
            .badge-ai       { background: #4C1D95; color: #DDD6FE; }
            .badge-model    { background: #1E3A5F; color: #93C5FD; }
            .badge-weather  { background: #14532D; color: #86EFAC; }
        }

        /* ── Weather widget ─────────────────────────────────────────────────── */
        .weather-card {
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%);
            color: #fff;
            border-radius: var(--radius);
            padding: 1rem 1.25rem;
            margin-bottom: .75rem;
        }
        .weather-temp   { font-size: 2rem; font-weight: 700; font-family: 'DM Mono', monospace; }
        .weather-label  { font-size: .75rem; opacity: .85; letter-spacing: .04em; text-transform: uppercase; }
        .weather-detail { font-size: .85rem; opacity: .9; }

        /* ── Product info grid ──────────────────────────────────────────────── */
        .product-info-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: .3rem .75rem;
            background: var(--metric-bg);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: .75rem 1rem;
            font-size: .85rem;
        }
        .info-label  { color: var(--text-muted); font-weight: 500; }
        .info-value  { color: var(--text-main);  font-weight: 600; }

        /* ── Alert / error banners ──────────────────────────────────────────── */
        .alert-info    { background:#DBEAFE; color:#1E40AF; border-left:4px solid #2563EB; border-radius:var(--radius-sm); padding:.6rem 1rem; font-size:.85rem; }
        .alert-warning { background:#FEF3C7; color:#92400E; border-left:4px solid #D97706; border-radius:var(--radius-sm); padding:.6rem 1rem; font-size:.85rem; }
        .alert-success { background:#D1FAE5; color:#065F46; border-left:4px solid #059669; border-radius:var(--radius-sm); padding:.6rem 1rem; font-size:.85rem; }
        @media (prefers-color-scheme: dark) {
            .alert-info    { background:#1E3A5F; color:#93C5FD; }
            .alert-warning { background:#78350F; color:#FDE68A; }
            .alert-success { background:#064E3B; color:#6EE7B7; }
        }

        /* ── Tabs ───────────────────────────────────────────────────────────── */
        [data-baseweb="tab-list"]    { gap: 4px; }
        [data-baseweb="tab"]         { border-radius: var(--radius-sm); font-weight: 500; }

        /* ── Footer ─────────────────────────────────────────────────────────── */
        .footer {
            text-align: center;
            color: var(--text-muted);
            font-size: .78rem;
            padding: 2rem 1rem 1rem;
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }

        /* ── Divider ────────────────────────────────────────────────────────── */
        hr { border: none; border-top: 1px solid var(--border); margin: 1rem 0; }

        /* ── Streamlit overrides ─────────────────────────────────────────────── */
        [data-testid="stMetric"]      { background: var(--metric-bg); border-radius: var(--radius); padding: .75rem 1rem; border: 1px solid var(--border); }
        [data-testid="stExpander"]    { border: 1px solid var(--border); border-radius: var(--radius); }
        div[data-testid="stDataFrame"] { border-radius: var(--radius); overflow: hidden; }
        </style>
        """,
        unsafe_allow_html=True,
    )