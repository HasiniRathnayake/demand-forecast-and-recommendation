import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# We know exactly the structure we want to inject.
new_block = """# ── Route: stock replenishment ────────────────────────────────────────────────
elif page == "stock_replenishment":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout
    from pages.stock_replenishment import render_stock_replenishment

    inject_styles()
    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_replenish"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown('<p class="main-header">📦 Stock Replenishment</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">Automated ML stock replenishment suggestions</p>', unsafe_allow_html=True)
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="replenish_logout"):
            logout()

    st.markdown("---")
    render_stock_replenishment()
    st.markdown('<div class="footer">Sunrise Supermarket · Stock Replenishment · SLIIT</div>', unsafe_allow_html=True)

# ── Route: smart inventory intake ────────────────────────────────────────────
elif page == "inventory_intake":
    from ui.styles import inject_styles
    from services.auth_service import get_current_user, logout
    from pages.inventory_intake_page import render_inventory_intake

    inject_styles()
    col_back, col_title, col_user = st.columns([1, 5, 1])
    with col_back:
        if st.button("← Hub", key="back_inventory"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()
    with col_title:
        st.markdown('<p class="main-header">🏪 Smart Inventory Intake</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">AI-assisted receiving validation and anomaly capture</p>', unsafe_allow_html=True)
    with col_user:
        user = get_current_user()
        if user:
            st.caption(f"👤 {user.get('username','').capitalize()}")
        if st.button("Logout", key="inventory_logout"):
            logout()

    st.markdown("---")
    render_inventory_intake()
    st.markdown('<div class="footer">Sunrise Supermarket · Smart Inventory Intake · SLIIT</div>', unsafe_allow_html=True)

# ── Route: waste & performance monitor ───────────────────────────────────────
elif page == "waste_monitor":
    from ui.styles            import inject_styles
    from ui.sidebar           import render_sidebar
    from pages.dashboard      import show_dashboard
    from pages.waste_records  import show_waste_records
    from pages.ai_performance import show_ai_performance_comparison, show_ai_performance_analytics
    from pages.savings_report import show_savings_report

    inject_styles()
    user     = st.session_state.get("user", {}) or {}
    username = user.get("username", "User").capitalize()

    start, end = render_sidebar()
    col_hub, col_title, col_spacer, col_logout = st.columns([1, 4, 3, 1])

    with col_hub:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("← Hub", key="hub_btn"):
            st.session_state.current_page = "main_dashboard"
            st.rerun()

    with col_title:
        st.markdown(
            '''
            <div style="text-align:center;padding-top:0.3rem">
                <span style="font-size:2.2rem;font-weight:700;color:#2563EB;">
                    📊 Sunrise Supermarket
                </span><br>
                <span style="font-size:1.1rem;color:#64748B;">
                    Waste &amp; Performance Monitor
                </span>
            </div>
            ''',
            unsafe_allow_html=True,
        )

    with col_spacer:
        pass

    with col_logout:
        st.markdown(
            f'<div style="text-align:center;color:#374151;font-size:0.82rem;'
            f'font-weight:500;margin-bottom:0.3rem;">👤 {username}</div>',
            unsafe_allow_html=True,
        )
        if st.button("Logout", key="wpm_logout", use_container_width=True):
            for key in list(st.session_state.keys())[:]:
                del st.session_state[key]
            st.rerun()

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "🗑️ Waste Records",
        "🤖 Comparisons & Records",
        "📈 AI Performance",
        "💰 Savings Report",
    ])

    with tab1: show_dashboard(start, end)
    with tab2: show_waste_records(start, end)
    with tab3: show_ai_performance_comparison(start, end)
    with tab4: show_ai_performance_analytics(start, end)
    with tab5: show_savings_report()

"""

# Use regex to strip the ENTIRE conflict block from <<<<<<< HEAD to >>>>>>> [hash]
pattern = r"<<<<<<< HEAD.*?>>>>>>> 2e77f5ac08bb28ff3438dcbb62086e8a69ea77de"
text = re.sub(pattern, new_block, text, flags=re.DOTALL)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)
