# pages/short_shipment_page.py
import streamlit as st
import sys, os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import numpy as np
import sqlite3

# Add module path
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'modules', 'short_shipment_detector'
))

from detectors import ShortShipmentDetector
from utils import validate_email, validate_phone

def render_short_shipment():
    """Wrapper that renders short shipment module inside shared app"""

    # Import their database functions
    from database import (
        get_db_connection, init_database,
        add_sample_data, get_suppliers_sqlite, get_products_sqlite
    )

    # Initialize
    init_database()
    detector = ShortShipmentDetector()

    def is_supabase(conn):
        return hasattr(conn, 'table') and callable(getattr(conn, 'table'))

    def is_sqlite(conn):
        return hasattr(conn, 'cursor') and hasattr(conn, 'execute')

    conn      = get_db_connection()
    conn_type = "supabase" if is_supabase(conn) else \
                "sqlite"   if is_sqlite(conn)   else "unknown"

    # ── Navigation tabs ───────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard",
        "📦 Record Delivery",
        "🏭 Suppliers",
        "🛒 Products",
        "📈 Analytics",
        "🏆 Product Performance"
    ])

    # ── Helper: get deliveries ────────────────────────────
    def get_deliveries(start_date, end_date):
        try:
            if conn_type == "supabase":
                start_str = start_date.strftime('%Y-%m-%d')
                end_str   = end_date.strftime('%Y-%m-%d')
                response  = conn.table("deliveries")\
                    .select("""
                        delivery_id, invoice_number, delivery_date,
                        supplier_id,
                        suppliers!inner(supplier_name, contact_number, email),
                        delivery_items(
                            delivery_item_id, product_code,
                            billed_quantity, received_quantity,
                            products!inner(
                                product_name, category,
                                cost_price, unit_price
                            )
                        )
                    """)\
                    .gte("delivery_date", start_str)\
                    .lte("delivery_date", end_str)\
                    .order("delivery_date", desc=True)\
                    .execute()

                data = []
                for delivery in response.data:
                    supplier_name = delivery.get('suppliers', {}).get(
                        'supplier_name', 'Unknown'
                    )
                    for item in delivery.get('delivery_items', []):
                        product_info = item.get('products', {})
                        billed   = float(item.get('billed_quantity', 0))
                        received = float(item.get('received_quantity', 0))
                        disc     = received - billed
                        disc_pct = (disc / billed * 100) if billed > 0 else 0
                        data.append({
                            'delivery_date':        delivery.get('delivery_date'),
                            'invoice_number':       delivery.get('invoice_number'),
                            'supplier_name':        supplier_name,
                            'product_name':         product_info.get('product_name', 'Unknown'),
                            'category':             product_info.get('category', 'Unknown'),
                            'cost_price':           float(product_info.get('cost_price', 0)),
                            'ordered_quantity':     billed,
                            'received_quantity':    received,
                            'discrepancy_quantity': disc,
                            'discrepancy_percentage': round(disc_pct, 1),
                            'financial_impact':     disc * float(
                                product_info.get('cost_price', 0)
                            ),
                        })
                return pd.DataFrame(data)
            else:
                query = """
                    SELECT d.delivery_date, d.order_number as invoice_number,
                           d.product_code, p.product_name, p.category,
                           p.cost_price, d.ordered_quantity,
                           d.received_quantity, d.discrepancy_quantity,
                           d.discrepancy_percentage, d.financial_impact,
                           s.supplier_name
                    FROM deliveries d
                    LEFT JOIN products p  ON d.product_code = p.product_code
                    LEFT JOIN suppliers s ON d.supplier_id  = s.supplier_id
                    WHERE d.delivery_date BETWEEN ? AND ?
                    ORDER BY d.delivery_date DESC
                """
                db_conn = sqlite3.connect('supermarket.db')
                df = pd.read_sql_query(
                    query, db_conn,
                    params=[
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d')
                    ]
                )
                db_conn.close()
                return df
        except Exception as e:
            st.error(f"Error fetching deliveries: {e}")
            return pd.DataFrame()

    # ════════════════════════════════════════════════════
    # TAB 1: DASHBOARD
    # ════════════════════════════════════════════════════
    with tab1:
        st.markdown('<div class="section-title">📊 Shipment Dashboard</div>',
                    unsafe_allow_html=True)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            start_date = st.date_input("From", value=date.today() - timedelta(days=30),
                                       key="dash_start")
        with col_d2:
            end_date = st.date_input("To", value=date.today(), key="dash_end")

        df = get_deliveries(start_date, end_date)

        if df.empty:
            st.markdown(
                '<div class="alert-info">No deliveries found for this period. '
                'Add sample data or record a delivery.</div>',
                unsafe_allow_html=True
            )
            if st.button("📥 Load Sample Data"):
                add_sample_data()
                st.rerun()
        else:
            conditions = [
                abs(df['discrepancy_quantity']) < 0.01,
                df['discrepancy_quantity'] < 0,
                df['discrepancy_quantity'] > 0
            ]
            choices    = ['✅ Accurate', '⚠️ Short Shipped', '📦 Over Delivered']
            df['status'] = np.select(conditions, choices, default='Unknown')

            # KPIs
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total Deliveries", len(df))
            with c2:
                accurate = len(df[df['status'] == '✅ Accurate'])
                st.metric("Accurate",         accurate)
            with c3:
                short = len(df[df['status'] == '⚠️ Short Shipped'])
                st.metric("Short Shipped",    short)
            with c4:
                impact = df['financial_impact'].sum()
                st.metric("Financial Impact", f"LKR {abs(impact):,.2f}")

            st.markdown("---")

            # Status pie chart
            col_l, col_r = st.columns(2)
            with col_l:
                st.markdown('<div class="section-title">Delivery Status</div>',
                            unsafe_allow_html=True)
                status_counts = df['status'].value_counts().reset_index()
                status_counts.columns = ['Status', 'Count']
                fig = px.pie(
                    status_counts, values='Count', names='Status',
                    color_discrete_sequence=['#059669', '#DC2626', '#2563EB'],
                    hole=0.35
                )
                fig.update_layout(
                    height=300, margin=dict(t=20, b=20),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True,
                                config={"displaylogo": False})

            with col_r:
                st.markdown('<div class="section-title">Discrepancy Trend</div>',
                            unsafe_allow_html=True)
                df['delivery_date'] = pd.to_datetime(df['delivery_date'])
                trend = df.groupby('delivery_date')[
                    'discrepancy_quantity'
                ].sum().reset_index()
                fig2 = px.bar(
                    trend, x='delivery_date', y='discrepancy_quantity',
                    color_discrete_sequence=['#DC2626']
                )
                fig2.update_layout(
                    height=300, margin=dict(t=20, b=20),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig2, use_container_width=True,
                                config={"displaylogo": False})

            # Recent deliveries
            st.markdown('<div class="section-title">Recent Deliveries</div>',
                        unsafe_allow_html=True)
            display_cols = [c for c in [
                'delivery_date', 'invoice_number', 'supplier_name',
                'product_name', 'ordered_quantity', 'received_quantity',
                'discrepancy_quantity', 'discrepancy_percentage',
                'financial_impact', 'status'
            ] if c in df.columns]
            st.dataframe(df[display_cols].head(20),
                         use_container_width=True, hide_index=True)

    # ════════════════════════════════════════════════════
    # TAB 2: RECORD DELIVERY
    # ════════════════════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-title">📦 Record New Delivery</div>',
                    unsafe_allow_html=True)

        if conn_type == "supabase":
            suppliers_df = pd.DataFrame(
                conn.table("suppliers").select("*").execute().data
            )
            products_df  = pd.DataFrame(
                conn.table("products").select("*").execute().data
            )
        else:
            suppliers_df = get_suppliers_sqlite()
            products_df  = get_products_sqlite()

        if suppliers_df.empty or products_df.empty:
            st.markdown(
                '<div class="alert-warning">Please add suppliers and products first.</div>',
                unsafe_allow_html=True
            )
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                order_num   = st.text_input("Order/Invoice Number")
                supplier    = st.selectbox(
                    "Supplier",
                    suppliers_df['supplier_name'].tolist()
                    if 'supplier_name' in suppliers_df.columns else []
                )
                del_date    = st.date_input("Delivery Date", value=date.today())

            with col_f2:
                product     = st.selectbox(
                    "Product",
                    products_df['product_name'].tolist()
                    if 'product_name' in products_df.columns else []
                )
                ordered_qty  = st.number_input("Ordered Quantity",  min_value=0, value=100)
                received_qty = st.number_input("Received Quantity", min_value=0, value=100)

            # Live discrepancy preview
            disc_qty = received_qty - ordered_qty
            disc_pct = (disc_qty / ordered_qty * 100) if ordered_qty > 0 else 0
            _, _, status = detector.calculate_discrepancy(ordered_qty, received_qty)

            st.markdown("---")
            pc1, pc2, pc3 = st.columns(3)
            pc1.metric("Discrepancy",   f"{disc_qty:+.0f} units")
            pc2.metric("Percentage",    f"{disc_pct:+.1f}%")
            pc3.metric("Status",        status)

            notes = st.text_area("Notes", placeholder="Optional notes about this delivery")

            if st.button("💾 Save Delivery", type="primary",
                         use_container_width=True):
                if not order_num:
                    st.error("Please enter an order/invoice number.")
                else:
                    try:
                        # Get product cost price
                        if 'product_name' in products_df.columns:
                            prod_row   = products_df[
                                products_df['product_name'] == product
                            ]
                            cost_price = float(
                                prod_row['cost_price'].iloc[0]
                            ) if not prod_row.empty else 0
                        else:
                            cost_price = 0

                        fin_impact = disc_qty * cost_price

                        if conn_type == "supabase":
                            st.info("Supabase insert not implemented in wrapper. "
                                    "Use direct module for recording.")
                        else:
                            # Get IDs
                            sup_row = suppliers_df[
                                suppliers_df['supplier_name'] == supplier
                            ]
                            prod_row2 = products_df[
                                products_df['product_name'] == product
                            ]
                            sup_id   = sup_row.iloc[0]['supplier_id'] \
                                       if not sup_row.empty else None
                            prod_code = prod_row2.iloc[0]['product_code'] \
                                        if not prod_row2.empty else None

                            db_conn = sqlite3.connect('supermarket.db')
                            cursor  = db_conn.cursor()
                            cursor.execute("""
                                INSERT INTO deliveries
                                (order_number, supplier_id, product_code,
                                 ordered_quantity, received_quantity,
                                 delivery_date, discrepancy_quantity,
                                 discrepancy_percentage, financial_impact, notes)
                                VALUES (?,?,?,?,?,?,?,?,?,?)
                            """, [
                                order_num, sup_id, prod_code,
                                ordered_qty, received_qty,
                                del_date.strftime('%Y-%m-%d'),
                                disc_qty, round(disc_pct, 1),
                                fin_impact, notes
                            ])
                            db_conn.commit()
                            db_conn.close()
                            st.success("✅ Delivery recorded successfully!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error saving delivery: {e}")

    # ════════════════════════════════════════════════════
    # TAB 3: SUPPLIERS
    # ════════════════════════════════════════════════════
    with tab3:
        st.markdown('<div class="section-title">🏭 Suppliers</div>',
                    unsafe_allow_html=True)

        if conn_type == "supabase":
            suppliers_df = pd.DataFrame(
                conn.table("suppliers").select("*").execute().data
            )
        else:
            suppliers_df = get_suppliers_sqlite()

        if not suppliers_df.empty:
            st.dataframe(suppliers_df, use_container_width=True, hide_index=True)
        else:
            st.markdown(
                '<div class="alert-info">No suppliers found.</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")
        st.markdown("#### ➕ Add New Supplier")
        sc1, sc2 = st.columns(2)
        with sc1:
            new_sup_id   = st.text_input("Supplier ID (e.g. SUP004)")
            new_sup_name = st.text_input("Supplier Name")
            new_contact  = st.text_input("Contact Person")
        with sc2:
            new_phone    = st.text_input("Phone")
            new_email    = st.text_input("Email")
            new_address  = st.text_input("Address")

        if st.button("➕ Add Supplier", type="primary"):
            if not new_sup_id or not new_sup_name:
                st.error("Supplier ID and Name are required.")
            else:
                try:
                    if conn_type == "sqlite":
                        db_conn = sqlite3.connect('supermarket.db')
                        cursor  = db_conn.cursor()
                        cursor.execute("""
                            INSERT INTO suppliers
                            (supplier_id, supplier_name, contact_person,
                             phone, email, address)
                            VALUES (?,?,?,?,?,?)
                        """, [new_sup_id, new_sup_name, new_contact,
                              new_phone, new_email, new_address])
                        db_conn.commit()
                        db_conn.close()
                        st.success("✅ Supplier added!")
                        st.rerun()
                    else:
                        st.info("Use Supabase dashboard to add suppliers.")
                except Exception as e:
                    st.error(f"Error adding supplier: {e}")

    # ════════════════════════════════════════════════════
    # TAB 4: PRODUCTS
    # ════════════════════════════════════════════════════
    with tab4:
        st.markdown('<div class="section-title">🛒 Products</div>',
                    unsafe_allow_html=True)

        if conn_type == "supabase":
            products_df = pd.DataFrame(
                conn.table("products").select("*").execute().data
            )
        else:
            products_df = get_products_sqlite()

        if not products_df.empty:
            st.dataframe(products_df, use_container_width=True, hide_index=True)
        else:
            st.markdown(
                '<div class="alert-info">No products found.</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")
        st.markdown("#### ➕ Add New Product")
        pc1, pc2 = st.columns(2)
        with pc1:
            new_prod_code = st.text_input("Product Code (e.g. P010)")
            new_prod_name = st.text_input("Product Name")
            new_category  = st.text_input("Category")
        with pc2:
            new_unit_price = st.number_input("Unit Price", min_value=0.0, value=0.0)
            new_cost_price = st.number_input("Cost Price", min_value=0.0, value=0.0)
            new_reorder    = st.number_input("Reorder Level", min_value=0, value=10)

        if st.button("➕ Add Product", type="primary"):
            if not new_prod_code or not new_prod_name:
                st.error("Product Code and Name are required.")
            else:
                try:
                    if conn_type == "sqlite":
                        db_conn = sqlite3.connect('supermarket.db')
                        cursor  = db_conn.cursor()
                        cursor.execute("""
                            INSERT INTO products
                            (product_code, product_name, category,
                             unit_price, cost_price, reorder_level)
                            VALUES (?,?,?,?,?,?)
                        """, [new_prod_code, new_prod_name, new_category,
                              new_unit_price, new_cost_price, new_reorder])
                        db_conn.commit()
                        db_conn.close()
                        st.success("✅ Product added!")
                        st.rerun()
                    else:
                        st.info("Use Supabase dashboard to add products.")
                except Exception as e:
                    st.error(f"Error adding product: {e}")

    # ════════════════════════════════════════════════════
    # TAB 5: ANALYTICS
    # ════════════════════════════════════════════════════
    with tab5:
        st.markdown('<div class="section-title">📈 Analytics & Fraud Detection</div>',
                    unsafe_allow_html=True)

        col_a1, col_a2 = st.columns(2)
        with col_a1:
            a_start = st.date_input("From", value=date.today() - timedelta(days=90),
                                    key="ana_start")
        with col_a2:
            a_end   = st.date_input("To",   value=date.today(),
                                    key="ana_end")

        df_ana = get_deliveries(a_start, a_end)

        if df_ana.empty:
            st.markdown(
                '<div class="alert-info">No data for analytics.</div>',
                unsafe_allow_html=True
            )
        else:
            conditions = [
                abs(df_ana['discrepancy_quantity']) < 0.01,
                df_ana['discrepancy_quantity'] < 0,
                df_ana['discrepancy_quantity'] > 0
            ]
            df_ana['status'] = np.select(
                conditions,
                ['✅ Accurate', '⚠️ Short Shipped', '📦 Over Delivered'],
                default='Unknown'
            )

            # Supplier analysis
            st.markdown('<div class="section-title">🏭 Supplier Performance</div>',
                        unsafe_allow_html=True)
            sup_stats = df_ana.groupby('supplier_name').agg(
                Deliveries   = ('delivery_date', 'count'),
                Avg_Disc_Pct = ('discrepancy_percentage', 'mean'),
                Fin_Impact   = ('financial_impact', 'sum'),
                Issues       = ('status', lambda x: (x != '✅ Accurate').sum())
            ).reset_index()
            sup_stats.columns = [
                'Supplier', 'Deliveries', 'Avg Disc %',
                'Financial Impact', 'Issues'
            ]

            fig_sup = px.bar(
                sup_stats, x='Supplier', y='Avg Disc %',
                color='Avg Disc %',
                color_continuous_scale=['green', 'yellow', 'red'],
                title='Average Discrepancy by Supplier'
            )
            fig_sup.update_layout(
                height=320, margin=dict(t=40, b=20),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_sup, use_container_width=True,
                            config={"displaylogo": False})
            st.dataframe(sup_stats, use_container_width=True, hide_index=True)

            # Fraud detection
            st.markdown("---")
            st.markdown('<div class="section-title">🔍 Fraud Pattern Detection</div>',
                        unsafe_allow_html=True)
            try:
                flags, risk_score, risk_level = detector.detect_fraud_patterns(df_ana)
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.metric("Risk Score", f"{risk_score}/100")
                with rc2:
                    st.metric("Risk Level", risk_level)

                if flags:
                    for flag in flags:
                        if 'CRITICAL' in flag or 'ALERT' in flag:
                            st.error(flag)
                        elif 'WARNING' in flag or 'PATTERN' in flag:
                            st.warning(flag)
                        else:
                            st.info(flag)
                else:
                    st.markdown(
                        '<div class="alert-success">✅ No fraud patterns detected.</div>',
                        unsafe_allow_html=True
                    )
            except Exception as e:
                st.error(f"Fraud detection error: {e}")

    # ════════════════════════════════════════════════════
    # TAB 6: PRODUCT PERFORMANCE
    # ════════════════════════════════════════════════════
    with tab6:
        st.markdown('<div class="section-title">🏆 Product Performance</div>',
                    unsafe_allow_html=True)

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            p_start = st.date_input("From", value=date.today() - timedelta(days=30),
                                    key="perf_start")
        with col_p2:
            p_end   = st.date_input("To",   value=date.today(),
                                    key="perf_end")

        df_perf = get_deliveries(p_start, p_end)

        if df_perf.empty:
            st.markdown(
                '<div class="alert-info">No data available.</div>',
                unsafe_allow_html=True
            )
        else:
            conditions = [
                abs(df_perf['discrepancy_quantity']) < 0.01,
                df_perf['discrepancy_quantity'] < 0,
                df_perf['discrepancy_quantity'] > 0
            ]
            df_perf['status'] = np.select(
                conditions,
                ['✅ Accurate', '⚠️ Short Shipped', '📦 Over Delivered'],
                default='Unknown'
            )

            pt1, pt2, pt3, pt4 = st.tabs([
                "📊 Highest Discrepancy",
                "💸 Financial Loss",
                "📈 Most Frequent",
                "✅ Most Accurate"
            ])

            with pt1:
                rank = df_perf.groupby('product_name')[
                    'discrepancy_percentage'
                ].mean().reset_index()
                rank = rank.sort_values(
                    'discrepancy_percentage', ascending=False
                ).head(10)
                if not rank.empty:
                    fig = px.bar(
                        rank, x='product_name', y='discrepancy_percentage',
                        color='discrepancy_percentage',
                        color_continuous_scale=['green', 'yellow', 'red']
                    )
                    fig.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig, use_container_width=True,
                                    config={"displaylogo": False})
                    st.dataframe(rank, use_container_width=True, hide_index=True)

            with pt2:
                loss = df_perf.groupby('product_name')[
                    'financial_impact'
                ].sum().reset_index()
                loss = loss.sort_values(
                    'financial_impact', ascending=True
                ).head(10)
                if not loss.empty:
                    fig2 = px.bar(
                        loss, x='product_name', y='financial_impact',
                        color='financial_impact',
                        color_continuous_scale=['red', 'yellow', 'green']
                    )
                    fig2.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig2, use_container_width=True,
                                    config={"displaylogo": False})
                    st.dataframe(loss, use_container_width=True, hide_index=True)

            with pt3:
                freq = df_perf.groupby('product_name').agg(
                    Issues         = ('status', lambda x: (x != '✅ Accurate').sum()),
                    Total_Deliveries = ('delivery_date', 'count')
                ).reset_index()
                freq['Issue Rate %'] = (
                    freq['Issues'] / freq['Total_Deliveries'] * 100
                ).round(1)
                freq = freq.sort_values('Issues', ascending=False).head(10)
                if not freq.empty:
                    st.dataframe(freq, use_container_width=True, hide_index=True)

            with pt4:
                acc = df_perf.groupby('product_name').agg(
                    Accurate         = ('status', lambda x: (x == '✅ Accurate').sum()),
                    Total_Deliveries = ('delivery_date', 'count')
                ).reset_index()
                acc['Accuracy %'] = (
                    acc['Accurate'] / acc['Total_Deliveries'] * 100
                ).round(1)
                acc = acc.sort_values('Accuracy %', ascending=False).head(10)
                if not acc.empty:
                    fig4 = px.bar(
                        acc, x='product_name', y='Accuracy %',
                        color='Accuracy %',
                        color_continuous_scale=['red', 'yellow', 'green']
                    )
                    fig4.update_layout(
                        height=300,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig4, use_container_width=True,
                                    config={"displaylogo": False})
                    st.dataframe(acc, use_container_width=True, hide_index=True)

            # Export
            st.markdown("---")
            summary = df_perf.groupby(['product_name', 'category']).agg(
                Ordered  = ('ordered_quantity',     'sum'),
                Received = ('received_quantity',    'sum'),
                Disc_Qty = ('discrepancy_quantity', 'sum'),
                Avg_Disc = ('discrepancy_percentage','mean'),
                Fin_Impact = ('financial_impact',   'sum'),
                Issues   = ('status', lambda x: (x != '✅ Accurate').sum()),
                Deliveries = ('delivery_date',      'count')
            ).reset_index()
            csv = summary.to_csv(index=False)
            st.download_button(
                label="📥 Export Report (CSV)",
                data=csv,
                file_name=f"product_performance_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )