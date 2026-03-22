/* ═══════════════════════════════════════════════
   Short-Shipment Detector — app.js
   Member: H.A.Wickramathilaka · IT24100427
   ═══════════════════════════════════════════════ */

const SUPABASE_URL = 'https://obbctmyetrdortxyglle.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9iYmN0bXlldHJkb3J0eHlnbGxlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY1OTg1MywiZXhwIjoyMDg3MjM1ODUzfQ.uaOYLnsgpN7R4mcbd4qcd8_jY4swh18Cf8sKF063LOg';
const TABLE = 'shipment_records';

let allShipments = [], filteredShipments = [], currentPage = 1;
const PAGE_SIZE = 50;
let supplierChart = null;
let editingId = null, activeView = 'overview';

async function sb(path, opts = {}) {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
        headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json', Prefer: opts.prefer || 'return=representation', ...opts.headers }, ...opts
    });
    if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`);
    const t = await res.text(); return t ? JSON.parse(t) : null;
}

async function fetchAll() { allShipments = await sb(`${TABLE}?select=*&order=delivery_date.desc&limit=5000`) || []; }

/* ── Auto-flag discrepancies ─────────────────── */
function flagged(s) { return (s.received_qty || 0) < (s.ordered_qty || 0); }
function shortQty(s) { return Math.max(0, (s.ordered_qty || 0) - (s.received_qty || 0)); }
function severity(s) {
    const pct = (s.ordered_qty || 0) > 0 ? shortQty(s) / s.ordered_qty * 100 : 0;
    if (pct >= 30) return 'HIGH'; if (pct >= 10) return 'MEDIUM'; return 'LOW';
}

function renderKPIs() {
    const total = allShipments.length;
    const flaggedCount = allShipments.filter(flagged).length;
    const resolved = allShipments.filter(s => s.status === 'RESOLVED').length;
    const loss = allShipments.filter(s => s.status === 'SHORT').reduce((acc, s) => acc + shortQty(s) * (s.unit_cost_kwd || 0), 0);
    document.getElementById('kpi-total').textContent = total.toLocaleString();
    document.getElementById('kpi-flagged').textContent = flaggedCount.toLocaleString();
    document.getElementById('kpi-loss').textContent = loss.toFixed(3);
    document.getElementById('kpi-resolved').textContent = resolved.toLocaleString();
}

function renderSupplierChart() {
    const bySupplier = {};
    allShipments.filter(flagged).forEach(s => {
        bySupplier[s.supplier] = (bySupplier[s.supplier] || 0) + 1;
    });
    const sorted = Object.entries(bySupplier).sort((a, b) => b[1] - a[1]).slice(0, 10);
    const ctx = document.getElementById('supplier-chart').getContext('2d');
    if (supplierChart) supplierChart.destroy();
    supplierChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(([k]) => k),
            datasets: [{ label: 'Discrepancy Count', data: sorted.map(([, v]) => v), backgroundColor: 'rgba(239,68,68,0.6)', borderColor: '#ef4444', borderWidth: 1, borderRadius: 4 }]
        },
        options: { responsive: true, maintainAspectRatio: false, indexAxis: 'y', plugins: { legend: { labels: { color: '#94a3b8', font: { family: 'Inter' } } } }, scales: { x: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } }, y: { ticks: { color: '#475569' }, grid: { color: '#1e2d45' } } } }
    });
}

function renderRecentAlerts() {
    const alerts = allShipments.filter(s => s.status === 'SHORT').slice(0, 8);
    const tbody = document.getElementById('recent-alerts-tbody');
    if (!alerts.length) { tbody.innerHTML = '<tr><td colspan="7" class="loading-row">No active alerts — system is monitoring shipments.</td></tr>'; return; }
    tbody.innerHTML = alerts.map(s => `<tr>
    <td><span class="font-mono">${s.po_number}</span></td>
    <td>${s.supplier}</td>
    <td>${s.ordered_qty}</td>
    <td class="text-red">${s.received_qty}</td>
    <td class="text-red">-${shortQty(s)} units</td>
    <td><span class="badge ${s.status === 'SHORT' ? 'badge-danger' : s.status === 'RESOLVED' ? 'badge-success' : 'badge-info'}">${s.status}</span></td>
    <td><button class="btn btn-success btn-sm" onclick="resolveAlert('${s.id}')">✅ Resolve</button></td>
  </tr>`).join('');
}

function applyFilters() {
    const search = document.getElementById('search-ship').value.toLowerCase();
    const status = document.getElementById('filter-status').value;
    filteredShipments = allShipments.filter(s => {
        const m = !search || (s.po_number || '').toLowerCase().includes(search) || (s.supplier || '').toLowerCase().includes(search) || (s.sku || '').toLowerCase().includes(search);
        const st = !status || s.status === status;
        return m && st;
    });
    currentPage = 1; renderShipTable();
}

function renderShipTable() {
    const slice = filteredShipments.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
    const total = Math.ceil(filteredShipments.length / PAGE_SIZE);
    const tbody = document.getElementById('ship-tbody');
    if (!slice.length) { tbody.innerHTML = '<tr><td colspan="10" class="loading-row">No records found.</td></tr>'; }
    else tbody.innerHTML = slice.map(s => {
        const disc = shortQty(s);
        return `<tr>
      <td>${s.delivery_date || '—'}</td>
      <td><span class="font-mono">${s.po_number}</span></td>
      <td>${s.supplier}</td>
      <td><span class="font-mono">${s.sku || '—'}</span></td>
      <td>${s.ordered_qty}</td>
      <td>${s.invoiced_qty || '—'}</td>
      <td>${s.received_qty}</td>
      <td class="${disc > 0 ? 'text-red' : ''}">${disc > 0 ? '-' + disc + ' SHORT' : 'OK'}</td>
      <td><span class="badge ${s.status === 'SHORT' ? 'badge-danger' : s.status === 'RESOLVED' ? 'badge-success' : 'badge-info'}">${s.status}</span></td>
      <td>
        <button class="btn-icon" onclick="openShipModal('${s.id}')">✏️</button>
        ${s.status === 'SHORT' ? `<button class="btn-icon" onclick="resolveAlert('${s.id}')">✅</button>` : ''}
        <button class="btn-icon" onclick="deleteShipment('${s.id}')">🗑️</button>
      </td>
    </tr>`;
    }).join('');
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${total || 1} (${filteredShipments.length.toLocaleString()})`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= total;
}

function renderAlerts() {
    const alerts = allShipments.filter(s => s.status === 'SHORT');
    const tbody = document.getElementById('alerts-tbody');
    if (!alerts.length) { tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No active alerts. Great work!</td></tr>'; return; }
    tbody.innerHTML = alerts.map(s => {
        const short = shortQty(s); const loss = (short * (s.unit_cost_kwd || 0)).toFixed(3);
        const sev = severity(s);
        return `<tr>
      <td>${s.delivery_date || '—'}</td>
      <td><span class="font-mono">${s.po_number}</span></td>
      <td>${s.supplier}</td>
      <td><span class="font-mono">${s.sku || '—'}</span></td>
      <td class="text-red">${short} units</td>
      <td class="text-red">${loss}</td>
      <td><span class="badge ${sev === 'HIGH' ? 'badge-danger' : sev === 'MEDIUM' ? 'badge-pending' : 'badge-info'}">${sev}</span></td>
      <td><button class="btn btn-success btn-sm" onclick="resolveAlert('${s.id}')">Resolve</button></td>
    </tr>`;
    }).join('');
}

function openShipModal(id) {
    editingId = id || null;
    document.getElementById('ship-modal-title').textContent = id ? 'Edit Shipment Record' : 'New Shipment Record';
    const s = id ? allShipments.find(x => x.id === id) : null;
    document.getElementById('sm-id').value = id || '';
    document.getElementById('sm-date').value = s?.delivery_date || new Date().toISOString().split('T')[0];
    document.getElementById('sm-po').value = s?.po_number || '';
    document.getElementById('sm-supplier').value = s?.supplier || '';
    document.getElementById('sm-sku').value = s?.sku || '';
    document.getElementById('sm-product').value = s?.product_name || '';
    document.getElementById('sm-ordered').value = s?.ordered_qty || '';
    document.getElementById('sm-invoiced').value = s?.invoiced_qty || '';
    document.getElementById('sm-received').value = s?.received_qty || '';
    document.getElementById('sm-cost').value = s?.unit_cost_kwd || '';
    document.getElementById('sm-notes').value = s?.notes || '';
    document.getElementById('ship-modal').classList.add('open');
}

async function saveShipment() {
    const ordered = parseInt(document.getElementById('sm-ordered').value) || 0;
    const received = parseInt(document.getElementById('sm-received').value) || 0;
    const payload = {
        delivery_date: document.getElementById('sm-date').value,
        po_number: document.getElementById('sm-po').value.trim(),
        supplier: document.getElementById('sm-supplier').value.trim(),
        sku: document.getElementById('sm-sku').value.trim(),
        product_name: document.getElementById('sm-product').value.trim(),
        ordered_qty: ordered,
        invoiced_qty: parseInt(document.getElementById('sm-invoiced').value) || null,
        received_qty: received,
        unit_cost_kwd: parseFloat(document.getElementById('sm-cost').value) || null,
        status: received < ordered ? 'SHORT' : 'OK',
        notes: document.getElementById('sm-notes').value.trim()
    };
    if (!payload.po_number || !payload.supplier || !ordered) { showToast('PO#, Supplier, and Ordered Qty are required', 'error'); return; }
    try {
        if (editingId) await sb(`${TABLE}?id=eq.${editingId}`, { method: 'PATCH', body: JSON.stringify(payload), prefer: 'return=minimal' });
        else await sb(TABLE, { method: 'POST', body: JSON.stringify(payload) });
        showToast(payload.status === 'SHORT' ? '⚠️ Short-shipment detected and flagged!' : 'Shipment saved ✅', 'success');
        document.getElementById('ship-modal').classList.remove('open');
        await refresh();
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function resolveAlert(id) {
    await sb(`${TABLE}?id=eq.${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'RESOLVED' }), prefer: 'return=minimal' });
    showToast('Alert resolved ✅', 'success'); await refresh();
}

async function resolveAll() {
    const shorts = allShipments.filter(s => s.status === 'SHORT');
    await Promise.all(shorts.map(s => sb(`${TABLE}?id=eq.${s.id}`, { method: 'PATCH', body: JSON.stringify({ status: 'RESOLVED' }), prefer: 'return=minimal' })));
    showToast(`${shorts.length} alerts resolved ✅`, 'success'); await refresh();
}

async function deleteShipment(id) {
    if (!confirm('Delete this shipment record?')) return;
    await sb(`${TABLE}?id=eq.${id}`, { method: 'DELETE', prefer: 'return=minimal' });
    showToast('Deleted', 'info'); await refresh();
}

function exportCSV() {
    const h = ['delivery_date', 'po_number', 'supplier', 'sku', 'product_name', 'ordered_qty', 'invoiced_qty', 'received_qty', 'unit_cost_kwd', 'status'];
    const csv = [h.join(','), ...filteredShipments.map(s => h.map(k => JSON.stringify(s[k] ?? '')).join(','))].join('\n');
    const a = document.createElement('a'); a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv); a.download = `shipments_${new Date().toISOString().split('T')[0]}.csv`; a.click();
}

const VIEWS = {
    overview: { v: 'view-overview', n: 'nav-overview', t: 'Overview', s: 'Shipment discrepancy detection overview' },
    shipments: { v: 'view-shipments', n: 'nav-shipments', t: 'Shipment Records', s: 'All delivery records' },
    alerts: { v: 'view-alerts', n: 'nav-alerts', t: 'Active Alerts', s: 'Unresolved discrepancy alerts' }
};

function switchView(key) {
    activeView = key;
    Object.entries(VIEWS).forEach(([k, v]) => { document.getElementById(v.v).classList.toggle('active', k === key); document.getElementById(v.n).classList.toggle('active', k === key); });
    document.getElementById('page-title').textContent = VIEWS[key].t;
    document.getElementById('page-sub').textContent = VIEWS[key].s;
    if (key === 'overview') { renderKPIs(); renderSupplierChart(); renderRecentAlerts(); }
    if (key === 'shipments') applyFilters();
    if (key === 'alerts') renderAlerts();
}

let toastT;
function showToast(msg, type = '') { const t = document.getElementById('toast'); t.textContent = msg; t.className = `toast ${type} show`; clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove('show'), 2800); }

async function refresh() {
    document.getElementById('last-updated').textContent = 'Loading…';
    try { await fetchAll(); switchView(activeView); document.getElementById('last-updated').textContent = 'Updated ' + new Date().toLocaleTimeString(); }
    catch (e) { showToast('Error: ' + e.message, 'error'); }
}

document.addEventListener('DOMContentLoaded', () => {
    Object.keys(VIEWS).forEach(k => document.getElementById(VIEWS[k].n).addEventListener('click', e => { e.preventDefault(); switchView(k); }));
    document.getElementById('search-ship').addEventListener('input', applyFilters);
    document.getElementById('filter-status').addEventListener('change', applyFilters);
    document.getElementById('btn-prev').addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderShipTable(); } });
    document.getElementById('btn-next').addEventListener('click', () => { const t = Math.ceil(filteredShipments.length / PAGE_SIZE); if (currentPage < t) { currentPage++; renderShipTable(); } });
    document.getElementById('btn-refresh').addEventListener('click', refresh);
    document.getElementById('btn-add-shipment').addEventListener('click', () => openShipModal(null));
    document.getElementById('btn-export').addEventListener('click', exportCSV);
    document.getElementById('btn-resolve-all').addEventListener('click', resolveAll);
    document.getElementById('ship-modal-close').addEventListener('click', () => document.getElementById('ship-modal').classList.remove('open'));
    document.getElementById('ship-modal-cancel').addEventListener('click', () => document.getElementById('ship-modal').classList.remove('open'));
    document.getElementById('ship-modal-save').addEventListener('click', saveShipment);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open')); });
    window.openShipModal = openShipModal; window.deleteShipment = deleteShipment; window.resolveAlert = resolveAlert;
    refresh();
});
