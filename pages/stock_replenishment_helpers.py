import math
import os
from datetime import datetime, timezone

import requests
import streamlit as st

from config.settings import SUPABASE_KEY, SUPABASE_URL
from scripts.email_sender import EmailSender

TABLE_REPLENISHMENT = "replenishment_orders"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


@st.cache_data(ttl=1800)
def fetch_orders():
    url = f"{SUPABASE_URL}/rest/v1/demand_forecasts?select=*&order=forecast_date.desc&limit=1000"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


@st.cache_data(ttl=3600)
def fetch_products():
    url = f"{SUPABASE_URL}/rest/v1/product_catalog?select=product_code,product_name"
    resp = requests.get(url, headers=HEADERS)
    return {p["product_code"]: p.get("product_name", "Unknown") for p in resp.json()} if resp.status_code == 200 else {}


def fetch_latest_forecasts(product_codes):
    if not product_codes:
        return {}

    latest_map = {}
    codes = sorted({c for c in product_codes if c})

    chunk_size = 120
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i + chunk_size]
        in_filter = ",".join(chunk)
        url = (
            f"{SUPABASE_URL}/rest/v1/demand_forecasts"
            f"?select=product_code,predicted_demand,forecast_date,confidence_level,model_version"
            f"&product_code=in.({in_filter})"
            f"&order=forecast_date.desc"
            f"&limit=5000"
        )
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            continue

        for row in resp.json():
            code = row.get("product_code")
            fdate = row.get("forecast_date")
            if not code or not fdate:
                continue
            current = latest_map.get(code)
            if current is None or str(fdate) > str(current.get("forecast_date", "")):
                latest_map[code] = row

    return latest_map


@st.cache_data(ttl=1800)
def fetch_forecast_dates():
    url = f"{SUPABASE_URL}/rest/v1/demand_forecasts?select=forecast_date&order=forecast_date.desc&limit=5000"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return []

    dates = sorted({row.get("forecast_date") for row in resp.json() if row.get("forecast_date")}, reverse=True)
    return dates


def fetch_forecasts_for_date(product_codes, forecast_date):
    if not product_codes or not forecast_date:
        return {}

    date_text = str(forecast_date)
    latest_map = {}
    codes = sorted({c for c in product_codes if c})

    chunk_size = 120
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i + chunk_size]
        in_filter = ",".join(chunk)
        url = (
            f"{SUPABASE_URL}/rest/v1/demand_forecasts"
            f"?select=product_code,predicted_demand,forecast_date,confidence_level,model_version,created_at"
            f"&forecast_date=eq.{date_text}"
            f"&product_code=in.({in_filter})"
            f"&order=created_at.desc"
            f"&limit=5000"
        )
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            continue

        for row in resp.json():
            code = row.get("product_code")
            if code and code not in latest_map:
                latest_map[code] = row

    return latest_map


@st.cache_data(ttl=300)
def fetch_suppliers():
    url = f"{SUPABASE_URL}/rest/v1/suppliers?select=*&order=supplier_name.asc"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


@st.cache_data(ttl=60)
def fetch_purchase_orders():
    url = f"{SUPABASE_URL}/rest/v1/purchase_orders?select=*,suppliers(supplier_name,email),replenishment_orders(product_code,suggested_qty)&order=created_at.desc"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


@st.cache_data(ttl=300)
def fetch_product_supplier_map():
    """Infer default supplier per product from historical purchase orders."""
    url = (
        f"{SUPABASE_URL}/rest/v1/purchase_orders"
        f"?select=supplier_id,replenishment_orders(product_code)"
        f"&order=created_at.desc&limit=5000"
    )
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return {}

    counts = {}
    for row in resp.json():
        sid = row.get("supplier_id")
        rep = row.get("replenishment_orders") or {}
        code = rep.get("product_code")
        if not sid or not code:
            continue
        if code not in counts:
            counts[code] = {}
        counts[code][sid] = counts[code].get(sid, 0) + 1

    product_supplier = {}
    for code, sid_counts in counts.items():
        product_supplier[code] = max(sid_counts.items(), key=lambda kv: kv[1])[0]
    return product_supplier


@st.cache_data(ttl=300)
def fetch_supplier_product_map():
    """Return supplier_id -> [product_code] from supplier_product_map table."""
    url = (
        f"{SUPABASE_URL}/rest/v1/supplier_product_map"
        f"?select=supplier_id,product_code"
        f"&order=supplier_id.asc"
    )
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return {}

    mapping = {}
    for row in resp.json() or []:
        sid = row.get("supplier_id")
        pcode = row.get("product_code")
        if not sid or not pcode:
            continue
        if sid not in mapping:
            mapping[sid] = []
        mapping[sid].append(pcode)
    return mapping


@st.cache_data(ttl=60)
def fetch_approval_logs(limit=100):
    url = (
        f"{SUPABASE_URL}/rest/v1/override_logs"
        f"?select=order_id,product_code,predicted_quantity,ordered_quantity,anomaly_flag,override_reason,overridden_by,overridden_at"
        f"&order=overridden_at.desc&limit={int(limit)}"
    )
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else []


@st.cache_data(ttl=1)
def fetch_replenishment_status(order_ids):
    if not order_ids:
        return {}

    status_map = {}
    ids = sorted({oid for oid in order_ids if oid})
    chunk_size = 120
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i:i + chunk_size]
        in_filter = ",".join(chunk)
        url = (
            f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}"
            f"?select=order_id,status,suggested_qty"
            f"&order_id=in.({in_filter})"
            f"&limit=5000"
        )
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            continue
        for row in resp.json():
            status_map[row.get("order_id")] = row
    return status_map


def _actor_identity():
    user = st.session_state.get("user", {}) or {}
    username = str(user.get("username", "Unknown Admin")).capitalize()
    user_id = user.get("user_id") or user.get("id") or user.get("employee_id") or "N/A"
    return f"{username} [{user_id}]"


def ensure_replenishment_row(order_context, predicted_qty):
    order_id = order_context.get("order_id")
    if not order_id:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "order_id": order_id,
        "generated_at": now_iso,
        "product_code": order_context.get("product_code", "UNKNOWN"),
        "product_name": order_context.get("product_name", "UNKNOWN PRODUCT"),
        "current_stock_level": int(order_context.get("current_stock_level") or 0),
        "reorder_point": int(order_context.get("reorder_point") or 1),
        "optimal_level": int(order_context.get("reorder_point") or 1) + int(predicted_qty or 1),
        "pending_po_qty": 0,
        "effective_stock": int(order_context.get("current_stock_level") or 0),
        "suggested_qty": int(predicted_qty or 1),
        "estimated_order_value_kwd": float(order_context.get("estimated_order_value_kwd") or 0),
        "daily_sales_velocity": float(order_context.get("daily_sales_velocity") or 0),
        "forecast_7day_demand": float(order_context.get("forecast_7day_demand") or predicted_qty or 1),
        "status": "PENDING_APPROVAL",
        "reasoning": order_context.get("reasoning") or "Generated from demand forecast",
        "created_at": now_iso,
    }

    url = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?on_conflict=order_id"
    req_headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    resp = requests.post(url, headers=req_headers, json=payload)
    return resp.status_code in [200, 201, 204]


def purchase_order_exists(order_id):
    url = (
        f"{SUPABASE_URL}/rest/v1/purchase_orders"
        f"?select=po_id&replenishment_order_id=eq.{order_id}&limit=1"
    )
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return False
    data = resp.json() or []
    return len(data) > 0


def approval_log_exists(order_id):
    url = (
        f"{SUPABASE_URL}/rest/v1/override_logs"
        f"?select=log_id&order_id=eq.{order_id}&limit=1"
    )
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return False
    data = resp.json() or []
    return len(data) > 0


def update_order_status(order_id, status, supplier_id=None, final_qty=None, order_context=None, predicted_qty=None):
    if status == "APPROVED" and order_context:
        ensured = ensure_replenishment_row(order_context, predicted_qty if predicted_qty is not None else final_qty)
        if not ensured:
            st.error("Failed to stage order record for approval.")
            return False

    url = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?order_id=eq.{order_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}

    payload = {"status": status}
    if final_qty is not None:
        payload["suggested_qty"] = final_qty

    resp = requests.patch(url, headers=req_headers, json=payload)

    if resp.status_code in [200, 204]:
        if status == "APPROVED" and supplier_id:
            if not purchase_order_exists(order_id):
                po_url = f"{SUPABASE_URL}/rest/v1/purchase_orders"
                po_resp = requests.post(po_url, headers=req_headers, json={
                    "replenishment_order_id": order_id,
                    "supplier_id": supplier_id,
                    "status": "PENDING_DISPATCH"
                })
                if po_resp.status_code not in [200, 201, 204]:
                    # Treat duplicate insert race as success if PO now exists.
                    if po_resp.status_code == 409 and purchase_order_exists(order_id):
                        pass
                    else:
                        detail = po_resp.text.strip()
                        st.error(f"Failed to create purchase order ({po_resp.status_code}). {detail}")
                        return False
        fetch_replenishment_status.clear()
        fetch_purchase_orders.clear()
        st.toast(f"Order {order_id} marked as {status}!", icon="✅")
        return True

    st.error("Failed to update status.")
    return False


def save_override_log(order_id, code, predicted, ordered, reason, anomaly_flag):
    url = f"{SUPABASE_URL}/rest/v1/override_logs"
    payload = {
        "order_id": order_id,
        "product_code": code,
        "predicted_quantity": int(predicted),
        "ordered_quantity": int(ordered),
        "anomaly_flag": bool(anomaly_flag),
        "override_reason": reason,
        "overridden_by": _actor_identity()
    }
    resp = requests.post(url, headers=HEADERS, json=payload)
    if resp.status_code not in [200, 201]:
        # If order_id is unique in this environment, update existing row instead of failing.
        if resp.status_code == 409 and approval_log_exists(order_id):
            patch_url = f"{SUPABASE_URL}/rest/v1/override_logs?order_id=eq.{order_id}"
            patch_headers = {**HEADERS, "Prefer": "return=minimal"}
            patch_resp = requests.patch(patch_url, headers=patch_headers, json=payload)
            if patch_resp.status_code in [200, 204]:
                fetch_approval_logs.clear()
                return True

        detail = resp.text.strip()
        st.error(f"Failed to save approval log. ({resp.status_code}) {detail}")
        return False
        
    fetch_approval_logs.clear()
    return True

def _commit_override(order_id, code, predicted, ordered, supplier_id, reason, order_context):
    ensured = ensure_replenishment_row(order_context or {}, predicted)
    if not ensured:
        st.error("Failed to stage order record for approval.")
        return

    anomaly_flag = int(predicted) != int(ordered)
    if not save_override_log(order_id, code, predicted, ordered, reason, anomaly_flag):
        return

    if update_order_status(
        order_id,
        "APPROVED",
        supplier_id,
        final_qty=ordered,
        order_context=order_context,
        predicted_qty=predicted,
    ):
        st.session_state.pop("pending_override", None)
        st.session_state.pop("override_reason_inline", None)
        st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("Confirm Order Approval")
    def _override_confirmation_dialog(order_id, code, predicted, ordered, supplier_id, order_context):
        st.warning("Please confirm this supplier order action.")
        st.markdown(f"**Predicted:** {predicted} units — **Requested:** {ordered} units")
        reason = st.text_area(
            "Approval Reason (saved to audit logs)",
            placeholder="Example: Promo campaign uplift, seasonal peak, manager directive...",
        )

        rc1, rc2 = st.columns(2)
        if rc1.button("Cancel", use_container_width=True):
            st.rerun()
        if rc2.button("Yes, I am sure", type="primary", use_container_width=True):
            if not reason.strip():
                st.error("Please provide a reason before confirming.")
            else:
                _commit_override(order_id, code, predicted, ordered, supplier_id, reason.strip(), order_context)


def override_confirmation_dialog(order_id, code, predicted, ordered, supplier_id, order_context):
    if hasattr(st, "dialog"):
        _override_confirmation_dialog(order_id, code, predicted, ordered, supplier_id, order_context)
        return

    has_anomaly = int(predicted) != int(ordered)

    st.session_state["pending_override"] = {
        "order_id": order_id,
        "code": code,
        "predicted": predicted,
        "ordered": ordered,
        "supplier_id": supplier_id,
        "order_context": order_context,
        "has_anomaly": has_anomaly,
    }
    st.rerun()


def update_po_status(po_id, status, do_rerun=True):
    url = f"{SUPABASE_URL}/rest/v1/purchase_orders?po_id=eq.{po_id}"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}
    resp = requests.patch(url, headers=req_headers, json={"status": status})
    if resp.status_code not in [200, 204]:
        st.error(f"Failed to update PO status to {status}.")
        return False
    fetch_purchase_orders.clear()
    if do_rerun:
        st.rerun()
    return True


def save_po_log(po_id, supplier_id, product_code, quantity, expected_delivery_date, email_address, sent_by, notes=""):
    url = f"{SUPABASE_URL}/rest/v1/supplier_po_logs"
    if hasattr(expected_delivery_date, "isoformat"):
        expected_delivery_date = expected_delivery_date.isoformat()
    data = {
        "po_id": po_id,
        "supplier_id": supplier_id,
        "product_code": product_code,
        "quantity": quantity,
        "expected_delivery_date": expected_delivery_date,
        "email_address": email_address,
        "sent_by": sent_by,
        "email_sent": True,
        "email_sent_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    resp = requests.post(url, headers=HEADERS, json=data)
    return resp.status_code in [200, 201]


def _test_recipient_email():
    return (
        os.getenv("SUPPLIER_TEST_EMAIL")
        or os.getenv("EMAIL_TEST_RECIPIENT")
        or os.getenv("EMAIL_USER")
        or os.getenv("EMAIL_FROM")
    )


def send_po_email(po_row, catalog_map, expected_delivery_date, notes="", test_mode=True):
    sup = po_row.get("suppliers") or {}
    supplier_email = sup.get("email") or ""

    if test_mode:
        recipient_email = _test_recipient_email()
        if not recipient_email or "@" not in recipient_email:
            st.error("Missing test recipient email in .env. Set SUPPLIER_TEST_EMAIL or EMAIL_TEST_RECIPIENT.")
            return False
    else:
        recipient_email = supplier_email
        if not recipient_email or "@" not in recipient_email:
            st.error("Supplier email is missing/invalid in database for this supplier.")
            return False

    rep = po_row.get("replenishment_orders") or {}
    po_id = po_row.get("po_id")
    product_code = rep.get("product_code", "UNKNOWN")
    product_name = catalog_map.get(product_code, f"Unknown Product ({product_code})")
    quantity = int(rep.get("suggested_qty") or 0)

    email_data = {
        "supplier_name": sup.get("supplier_name") or "Supplier",
        "po_id": str(po_id)[:8].upper(),
        "product_name": product_name,
        "product_code": product_code,
        "quantity": quantity,
        "order_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "expected_delivery_date": expected_delivery_date.isoformat(),
        "notes": (notes or "").strip(),
        "store_name": "Sunrise Super",
    }

    email_sender = EmailSender()
    success, msg = email_sender.send_supplier_po_email(recipient_email, email_data)
    if not success:
        st.error(f"Failed to send email: {msg}")
        return False

    delivery_mode = "TEST" if test_mode else "LIVE"
    clean_notes = (notes or "").strip()
    combined_notes = f"Mode: {delivery_mode}. {clean_notes}".strip()
    save_po_log(
        po_id=po_id,
        supplier_id=po_row.get("supplier_id"),
        product_code=product_code,
        quantity=quantity,
        expected_delivery_date=expected_delivery_date,
        email_address=recipient_email,
        sent_by=_actor_identity(),
        notes=combined_notes,
    )

    updated = update_po_status(po_id, "SENT", do_rerun=False)
    if not updated:
        return False

    sent_msg = "test mode" if test_mode else "live supplier email"
    st.success(f"Email sent via {sent_msg} to {recipient_email} and PO marked SENT.")
    return True


def delete_purchase_order(po_id, rep_order_id):
    url_po = f"{SUPABASE_URL}/rest/v1/purchase_orders?po_id=eq.{po_id}"
    requests.delete(url_po, headers=HEADERS)

    if rep_order_id:
        url_rep = f"{SUPABASE_URL}/rest/v1/{TABLE_REPLENISHMENT}?order_id=eq.{rep_order_id}"
        req_headers = {**HEADERS, "Prefer": "return=minimal"}
        requests.patch(url_rep, headers=req_headers, json={"status": "CANCELLED"})

    fetch_purchase_orders.clear()
    fetch_replenishment_status.clear()
    st.toast("Order successfully canceled!", icon="🛑")
    st.rerun()


def get_next_supplier_id():
    """Generate next supplier ID in SUP-XXX format."""
    suppliers = fetch_suppliers()
    if not suppliers:
        return "SUP-001"
    
    max_num = 0
    for sup in suppliers:
        sid = sup.get("supplier_id", "")
        if sid.startswith("SUP-"):
            try:
                num = int(sid.replace("SUP-", ""))
                max_num = max(max_num, num)
            except ValueError:
                pass
    
    return f"SUP-{max_num + 1:03d}"


def save_supplier(supplier_id, name, email, phone, selected_products=None):
    url = f"{SUPABASE_URL}/rest/v1/suppliers"
    req_headers = {**HEADERS, "Prefer": "return=resolution"}
    data = {"supplier_id": supplier_id, "supplier_name": name, "email": email, "contact_number": phone}

    resp = requests.post(url, headers=HEADERS, json=data)
    created = resp.status_code in [200, 201, 204]

    if resp.status_code == 409:
        patch_resp = requests.patch(f"{url}?supplier_id=eq.{supplier_id}", headers=req_headers, json=data)
        if patch_resp.status_code not in [200, 204]:
            detail = patch_resp.text.strip()
            return False, f"Failed to update supplier ({patch_resp.status_code}). {detail}"
    elif not created:
        detail = resp.text.strip()
        return False, f"Failed to save supplier ({resp.status_code}). {detail}"
    
    # Save supplier-product mappings when provided by the form.
    if selected_products is not None:
        map_ok, map_msg = _save_supplier_products(supplier_id, selected_products)
        if not map_ok:
            return False, map_msg

    action = "created" if created else "updated"
    mapped_count = len(selected_products or [])
    fetch_suppliers.clear()
    return True, f"Supplier {supplier_id} {action} successfully. Products mapped: {mapped_count}."

def _save_supplier_products(supplier_id, product_codes):
    """Replace product mappings for a supplier in supplier_product_map."""
    table_url = f"{SUPABASE_URL}/rest/v1/supplier_product_map"
    req_headers = {**HEADERS, "Prefer": "return=minimal"}

    # Replace existing mappings with the latest selection.
    del_url = f"{table_url}?supplier_id=eq.{supplier_id}"
    del_resp = requests.delete(del_url, headers=req_headers)
    if del_resp.status_code not in [200, 204]:
        detail = del_resp.text.strip()
        return False, f"Failed to clear old product mappings ({del_resp.status_code}). {detail}"

    if not product_codes:
        return True, ""

    payload = [
        {"supplier_id": supplier_id, "product_code": str(code)}
        for code in sorted({c for c in product_codes if c})
    ]

    post_url = f"{table_url}?on_conflict=supplier_id,product_code"
    post_headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    post_resp = requests.post(post_url, headers=post_headers, json=payload)
    if post_resp.status_code not in [200, 201, 204]:
        detail = post_resp.text.strip()
        return False, f"Failed to save product mappings ({post_resp.status_code}). {detail}"
        
    fetch_supplier_product_map.clear()
    return True, ""

def delete_supplier(supplier_id):
    url = f"{SUPABASE_URL}/rest/v1/suppliers?supplier_id=eq.{supplier_id}"
    requests.delete(url, headers=HEADERS)
    fetch_suppliers.clear()
    st.toast("Supplier removed!", icon="🗑️")
    st.rerun()
