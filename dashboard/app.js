/* ═══════════════════════════════════════════════════════════
   SUNRISE SUPER PROCUREMENT ASSISTANT — App Logic
   Project: 2026-Y2-S2-KU-AI-02
   ═══════════════════════════════════════════════════════════ */

const SUPABASE_URL = 'https://obbctmyetrdortxyglle.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9iYmN0bXlldHJkb3J0eHlnbGxlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY1OTg1MywiZXhwIjoyMDg3MjM1ODUzfQ.uaOYLnsgpN7R4mcbd4qcd8_jY4swh18Cf8sKF063LOg';
const TABLE = 'replenishment_orders';

/* ── Pagination ──────────────────────────────────────────── */
let currentPage = 1;
const PAGE_SIZE = 50;
let allOrders = [];
let filteredOrders = [];
let selectedIds = new Set();
let currentModal = null;

/* ══ SUPABASE API ══════════════════════════════════════════ */
async function sbFetch(path, options = {}) {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
        headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': options.prefer || 'return=representation',
            ...options.headers
        },
        ...options
    });
    if (!res.ok) {
        const body = await res.text();
        throw new Error(`Supabase error ${res.status}: ${body}`);
    }
    const text = await res.text();
    return text ? JSON.parse(text) : null;
}

async function fetchAllOrders() {
    const data = await sbFetch(`${TABLE}?select=*&order=created_at.asc&limit=5000`);
    return data || [];
}

async function updateStatus(orderId, newStatus) {
    await sbFetch(`${TABLE}?order_id=eq.${encodeURIComponent(orderId)}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus })
    });
}

async function bulkUpdateStatus(orderIds, newStatus) {
    const ids = orderIds.map(id => encodeURIComponent(`"${id}"`)).join(',');
    await sbFetch(`${TABLE}?order_id=in.(${orderIds.map(id => `"${id}"`).join(',')})`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
        prefer: 'return=minimal'
    });
}

/* ══ STATS ══════════════════════════════════════════════════ */
function computeStats(orders) {
    const total = orders.length;
    const pending = orders.filter(o => o.status === 'PENDING_APPROVAL').length;
    const approved = orders.filter(o => o.status === 'APPROVED').length;
    const rejected = orders.filter(o => o.status === 'REJECTED').length;
    const totalUnits = orders.reduce((s, o) => s + (o.suggested_qty || 0), 0);
    const totalValue = orders.reduce((s, o) => s + (o.estimated_order_value_kwd || 0), 0);
    return { total, pending, approved, rejected, totalUnits, totalValue };
}

function renderStats(stats) {
    const fmt = n => n.toLocaleString();
    document.getElementById('kpi-total').textContent = fmt(stats.total);
    document.getElementById('kpi-pending').textContent = fmt(stats.pending);
    document.getElementById('kpi-approved').textContent = fmt(stats.approved);
    document.getElementById('kpi-rejected').textContent = fmt(stats.rejected);
    document.getElementById('kpi-units').textContent = fmt(stats.totalUnits);
    document.getElementById('kpi-value').textContent = fmt(Math.round(stats.totalValue));
}

/* ══ TABLE RENDERING ═══════════════════════════════════════ */
function statusBadge(status) {
    const cls = status === 'PENDING_APPROVAL' ? 'pending'
        : status === 'APPROVED' ? 'approved' : 'rejected';
    const label = status === 'PENDING_APPROVAL' ? '⏳ Pending' : status === 'APPROVED' ? '✅ Approved' : '❌ Rejected';
    return `<span class="status-badge status-${cls}">${label}</span>`;
}

function stockClass(level, reorder) {
    if (level === 0) return 'stock-zero';
    if (level <= reorder) return 'stock-low';
    return 'stock-ok';
}

function renderUrgentTable(orders) {
    const urgent = orders
        .filter(o => o.status === 'PENDING_APPROVAL')
        .sort((a, b) => (a.current_stock_level / (a.reorder_point || 1)) - (b.current_stock_level / (b.reorder_point || 1)))
        .slice(0, 10);

    const tbody = document.getElementById('urgent-tbody');
    if (!urgent.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-row">🎉 No critical stockouts!</td></tr>';
        return;
    }

    tbody.innerHTML = urgent.map(o => `
    <tr>
      <td><code style="font-size:11px;color:var(--text-muted)">${o.order_id}</code></td>
      <td><div class="product-name" title="${o.product_name}">${o.product_name}</div></td>
      <td><span class="product-code">${o.product_code}</span></td>
      <td class="${stockClass(o.current_stock_level, o.reorder_point)}">${o.current_stock_level}</td>
      <td>${o.reorder_point}</td>
      <td><span class="qty-badge">${o.suggested_qty}</span></td>
      <td>${o.forecast_7day_demand?.toFixed(1) || '—'}</td>
      <td>
        <button class="row-btn row-btn-approve" onclick="quickApprove('${o.order_id}')">✅</button>
        <button class="row-btn row-btn-reject"  onclick="quickReject('${o.order_id}')">❌</button>
        <button class="row-btn row-btn-view"    onclick="openModal('${o.order_id}')">🔍</button>
      </td>
    </tr>
  `).join('');
}

function renderOrdersTable(orders, page) {
    const start = (page - 1) * PAGE_SIZE;
    const end = start + PAGE_SIZE;
    const slice = orders.slice(start, end);
    const totalPages = Math.ceil(orders.length / PAGE_SIZE);

    const tbody = document.getElementById('orders-tbody');
    if (!slice.length) {
        tbody.innerHTML = '<tr><td colspan="12" class="loading-row">No records found</td></tr>';
    } else {
        tbody.innerHTML = slice.map(o => `
      <tr>
        <td><input type="checkbox" class="row-check" data-id="${o.order_id}" ${selectedIds.has(o.order_id) ? 'checked' : ''} /></td>
        <td><code style="font-size:11px;color:var(--text-muted)">${o.order_id}</code></td>
        <td><div class="product-name" title="${o.product_name}">${o.product_name}</div></td>
        <td><span class="product-code">${o.product_code}</span></td>
        <td class="${stockClass(o.current_stock_level, o.reorder_point)}">${o.current_stock_level}</td>
        <td>${o.reorder_point}</td>
        <td><span class="qty-badge">${o.suggested_qty}</span></td>
        <td>${o.daily_sales_velocity ?? '—'}</td>
        <td>${o.forecast_7day_demand?.toFixed(1) || '—'}</td>
        <td class="value-cell">${o.estimated_order_value_kwd ? o.estimated_order_value_kwd.toLocaleString() : '—'}</td>
        <td>${statusBadge(o.status)}</td>
        <td>
          <button class="row-btn row-btn-view"    onclick="openModal('${o.order_id}')">🔍 View</button>
          ${o.status !== 'APPROVED' ? `<button class="row-btn row-btn-approve" onclick="quickApprove('${o.order_id}')">✅</button>` : ''}
          ${o.status !== 'REJECTED' ? `<button class="row-btn row-btn-reject"  onclick="quickReject('${o.order_id}')">❌</button>` : ''}
          ${o.status !== 'PENDING_APPROVAL' ? `<button class="row-btn row-btn-undo" onclick="quickPending('${o.order_id}')">↩</button>` : ''}
        </td>
      </tr>
    `).join('');
    }

    document.getElementById('page-info').textContent = `Page ${page} of ${totalPages} (${orders.length.toLocaleString()} records)`;
    document.getElementById('btn-prev').disabled = page <= 1;
    document.getElementById('btn-next').disabled = page >= totalPages;

    // Checkbox listeners
    document.querySelectorAll('.row-check').forEach(cb => {
        cb.addEventListener('change', e => {
            const id = e.target.dataset.id;
            if (e.target.checked) selectedIds.add(id); else selectedIds.delete(id);
            updateBulkActionsBar();
        });
    });
}

function renderSimpleTable(orders, tbodyId, cols) {
    const tbody = document.getElementById(tbodyId);
    if (!orders.length) {
        tbody.innerHTML = `<tr><td colspan="${cols}" class="loading-row">No records found</td></tr>`;
        return;
    }
    tbody.innerHTML = orders.map(o => `
    <tr>
      <td><code style="font-size:11px;color:var(--text-muted)">${o.order_id}</code></td>
      <td><div class="product-name" title="${o.product_name}">${o.product_name}</div></td>
      <td><span class="product-code">${o.product_code}</span></td>
      <td><span class="qty-badge">${o.suggested_qty}</span></td>
      <td class="value-cell">${o.estimated_order_value_kwd ? o.estimated_order_value_kwd.toLocaleString() : '—'}</td>
      <td>
        <button class="row-btn row-btn-view" onclick="openModal('${o.order_id}')">🔍 View</button>
        <button class="row-btn row-btn-undo" onclick="quickPending('${o.order_id}')">↩ Undo</button>
      </td>
    </tr>
  `).join('');
}

/* ══ FILTER & SORT ══════════════════════════════════════════ */
function applyFilters() {
    const search = document.getElementById('search-input').value.toLowerCase().trim();
    const status = document.getElementById('filter-status').value;
    const sort = document.getElementById('filter-sort').value;

    let orders = [...allOrders];

    if (search) {
        orders = orders.filter(o =>
            (o.product_name || '').toLowerCase().includes(search) ||
            (o.product_code || '').toLowerCase().includes(search) ||
            (o.order_id || '').toLowerCase().includes(search)
        );
    }
    if (status) orders = orders.filter(o => o.status === status);

    if (sort === 'urgency') {
        orders.sort((a, b) => (a.current_stock_level / Math.max(a.reorder_point, 1)) - (b.current_stock_level / Math.max(b.reorder_point, 1)));
    } else if (sort === 'qty_desc') {
        orders.sort((a, b) => b.suggested_qty - a.suggested_qty);
    } else if (sort === 'qty_asc') {
        orders.sort((a, b) => a.suggested_qty - b.suggested_qty);
    } else if (sort === 'value_desc') {
        orders.sort((a, b) => (b.estimated_order_value_kwd || 0) - (a.estimated_order_value_kwd || 0));
    }

    filteredOrders = orders;
    currentPage = 1;
    renderOrdersTable(filteredOrders, currentPage);
}

/* ══ MODAL ══════════════════════════════════════════════════ */
function openModal(orderId) {
    const o = allOrders.find(r => r.order_id === orderId);
    if (!o) return;
    currentModal = o;

    const badge = document.getElementById('modal-badge');
    const cls = o.status === 'PENDING_APPROVAL' ? 'pending' : o.status === 'APPROVED' ? 'approved' : 'rejected';
    badge.className = `modal-badge status-badge status-${cls}`;
    badge.textContent = o.status.replace('_', ' ');

    document.getElementById('modal-title').textContent = o.product_name;
    document.getElementById('modal-code').textContent = o.product_code;
    document.getElementById('md-stock').textContent = o.current_stock_level ?? '—';
    document.getElementById('md-reorder').textContent = o.reorder_point ?? '—';
    document.getElementById('md-optimal').textContent = o.optimal_level ?? '—';
    document.getElementById('md-pending-po').textContent = o.pending_po_qty ?? '—';
    document.getElementById('md-suggest').textContent = o.suggested_qty ?? '—';
    document.getElementById('md-velocity').textContent = (o.daily_sales_velocity ?? '—') + ' units/day';
    document.getElementById('md-forecast').textContent = (o.forecast_7day_demand ?? '—') + ' units';
    document.getElementById('md-value').textContent = o.estimated_order_value_kwd ? o.estimated_order_value_kwd.toLocaleString() : '—';
    document.getElementById('modal-reasoning').textContent = o.reasoning || 'No reasoning provided.';

    document.getElementById('modal-approve').style.display = o.status !== 'APPROVED' ? '' : 'none';
    document.getElementById('modal-reject').style.display = o.status !== 'REJECTED' ? '' : 'none';

    document.getElementById('modal-overlay').classList.add('open');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
    currentModal = null;
}

/* ══ STATUS ACTIONS ════════════════════════════════════════ */
async function quickApprove(orderId) {
    await setStatus(orderId, 'APPROVED');
}
async function quickReject(orderId) {
    await setStatus(orderId, 'REJECTED');
}
async function quickPending(orderId) {
    await setStatus(orderId, 'PENDING_APPROVAL');
}

async function setStatus(orderId, status) {
    try {
        await updateStatus(orderId, status);
        const order = allOrders.find(o => o.order_id === orderId);
        if (order) order.status = status;
        refresh();
        showToast(`Order ${orderId} → ${status.replace('_', ' ')}`, 'success');
    } catch (e) {
        showToast('Update failed: ' + e.message, 'error');
    }
}

function updateBulkActionsBar() {
    const bar = document.getElementById('bulk-actions');
    bar.style.display = selectedIds.size > 0 ? 'flex' : 'none';
}

async function bulkAction(newStatus) {
    if (!selectedIds.size) return;
    const ids = [...selectedIds];
    try {
        // Update one by one (REST API doesn't support bulk IN patch cleanly)
        await Promise.all(ids.map(id => updateStatus(id, newStatus)));
        ids.forEach(id => {
            const o = allOrders.find(r => r.order_id === id);
            if (o) o.status = newStatus;
        });
        selectedIds.clear();
        updateBulkActionsBar();
        document.getElementById('select-all').checked = false;
        refresh();
        showToast(`${ids.length} orders → ${newStatus.replace('_', ' ')}`, 'success');
    } catch (e) {
        showToast('Bulk update failed: ' + e.message, 'error');
    }
}

/* ══ CSV EXPORT ════════════════════════════════════════════ */
function exportCSV() {
    const data = activeView === 'orders' ? filteredOrders : allOrders;
    const headers = ['order_id', 'product_code', 'product_name', 'current_stock_level', 'reorder_point', 'optimal_level',
        'suggested_qty', 'daily_sales_velocity', 'forecast_7day_demand', 'estimated_order_value_kwd', 'status'];
    const rows = data.map(o => headers.map(h => JSON.stringify(o[h] ?? '')).join(','));
    const csv = [headers.join(','), ...rows].join('\n');

    const a = document.createElement('a');
    a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
    a.download = `replenishment_orders_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    showToast('CSV exported ✅', 'success');
}

/* ══ NAVIGATION ════════════════════════════════════════════ */
let activeView = 'dashboard';
const VIEWS = {
    dashboard: { id: 'view-dashboard', title: 'Dashboard', sub: 'Stock Replenishment Overview', nav: 'nav-dashboard' },
    orders: { id: 'view-orders', title: 'Reorder Queue', sub: 'Review & Approve Replenishment', nav: 'nav-orders' },
    approved: { id: 'view-approved', title: 'Approved Orders', sub: 'Orders cleared for procurement', nav: 'nav-approved' },
    rejected: { id: 'view-rejected', title: 'Rejected Orders', sub: 'Orders declined by your team', nav: 'nav-rejected' },
};

function switchView(viewKey) {
    activeView = viewKey;
    Object.entries(VIEWS).forEach(([key, v]) => {
        document.getElementById(v.id).classList.toggle('active', key === viewKey);
        document.getElementById(v.nav).classList.toggle('active', key === viewKey);
    });
    const v = VIEWS[viewKey];
    document.getElementById('page-title').textContent = v.title;
    document.getElementById('page-sub').textContent = v.sub;
    renderView(viewKey);
}

function renderView(viewKey) {
    if (viewKey === 'dashboard') {
        const stats = computeStats(allOrders);
        renderStats(stats);
        renderUrgentTable(allOrders);
    } else if (viewKey === 'orders') {
        applyFilters();
    } else if (viewKey === 'approved') {
        renderSimpleTable(allOrders.filter(o => o.status === 'APPROVED'), 'approved-tbody', 6);
    } else if (viewKey === 'rejected') {
        renderSimpleTable(allOrders.filter(o => o.status === 'REJECTED'), 'rejected-tbody', 6);
    }
}

/* ══ TOAST ══════════════════════════════════════════════════ */
let toastTimer;
function showToast(msg, type = '') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = `toast ${type} show`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2800);
}

/* ══ REFRESH ════════════════════════════════════════════════ */
async function refresh() {
    document.getElementById('last-updated').textContent = 'Refreshing…';
    try {
        allOrders = await fetchAllOrders();
        filteredOrders = [...allOrders];
        renderView(activeView);
        const now = new Date().toLocaleTimeString();
        document.getElementById('last-updated').textContent = `Updated ${now}`;
    } catch (e) {
        showToast('Failed to load data: ' + e.message, 'error');
        document.getElementById('last-updated').textContent = 'Error refreshing';
    }
}

/* ══ INIT ═══════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {

    // Nav
    Object.entries(VIEWS).forEach(([key]) => {
        document.getElementById(VIEWS[key].nav).addEventListener('click', (e) => {
            e.preventDefault();
            switchView(key);
        });
    });

    // Search & Filter
    document.getElementById('search-input').addEventListener('input', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);
    document.getElementById('filter-sort').addEventListener('change', applyFilters);

    // Select all
    document.getElementById('select-all').addEventListener('change', e => {
        const checked = e.target.checked;
        document.querySelectorAll('.row-check').forEach(cb => {
            cb.checked = checked;
            if (checked) selectedIds.add(cb.dataset.id);
            else selectedIds.delete(cb.dataset.id);
        });
        updateBulkActionsBar();
    });

    // Bulk actions
    document.getElementById('btn-approve-all').addEventListener('click', () => bulkAction('APPROVED'));
    document.getElementById('btn-reject-all').addEventListener('click', () => bulkAction('REJECTED'));

    // Pagination
    document.getElementById('btn-prev').addEventListener('click', () => {
        if (currentPage > 1) { currentPage--; renderOrdersTable(filteredOrders, currentPage); }
    });
    document.getElementById('btn-next').addEventListener('click', () => {
        const totalPages = Math.ceil(filteredOrders.length / PAGE_SIZE);
        if (currentPage < totalPages) { currentPage++; renderOrdersTable(filteredOrders, currentPage); }
    });

    // Refresh
    document.getElementById('btn-refresh').addEventListener('click', refresh);

    // Export
    document.getElementById('btn-export').addEventListener('click', exportCSV);

    // Modal
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('modal-overlay').addEventListener('click', e => {
        if (e.target === document.getElementById('modal-overlay')) closeModal();
    });
    document.getElementById('modal-approve').addEventListener('click', async () => {
        if (currentModal) { await quickApprove(currentModal.order_id); closeModal(); }
    });
    document.getElementById('modal-reject').addEventListener('click', async () => {
        if (currentModal) { await quickReject(currentModal.order_id); closeModal(); }
    });

    // Keyboard close modal
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

    // Make quick actions global
    window.quickApprove = quickApprove;
    window.quickReject = quickReject;
    window.quickPending = quickPending;
    window.openModal = openModal;

    // Initial load
    refresh();
});
