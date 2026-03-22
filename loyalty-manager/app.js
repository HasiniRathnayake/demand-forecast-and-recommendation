/* ═══════════════════════════════════════════════
   Smart Loyalty & Promotion Manager — app.js
   Member: Abeynayake D.A · IT24100971
   ═══════════════════════════════════════════════ */

const SUPABASE_URL = 'https://obbctmyetrdortxyglle.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9iYmN0bXlldHJkb3J0eHlnbGxlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTY1OTg1MywiZXhwIjoyMDg3MjM1ODUzfQ.uaOYLnsgpN7R4mcbd4qcd8_jY4swh18Cf8sKF063LOg';
const PROMOS_TABLE = 'promotions';
const SEGMENTS_TABLE = 'customer_segments';

let allPromos = [], allSegments = [], filteredPromos = [];
let currentPage = 1; const PAGE_SIZE = 50;
let segChart = null, campChart = null;
let editingPromoId = null, activeView = 'overview';

async function sb(path, opts = {}) {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
        headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, 'Content-Type': 'application/json', Prefer: opts.prefer || 'return=representation', ...opts.headers }, ...opts
    });
    if (!res.ok) throw new Error(`Supabase ${res.status}: ${await res.text()}`);
    const t = await res.text(); return t ? JSON.parse(t) : null;
}

async function fetchAll() {
    const [p, s] = await Promise.all([
        sb(`${PROMOS_TABLE}?select=*&order=created_at.desc&limit=1000`),
        sb(`${SEGMENTS_TABLE}?select=*&order=segment.asc&limit=200`)
    ]);
    allPromos = p || []; allSegments = s || [];
}

/* ── KPIs ────────────────────────────────────────────────── */
function renderKPIs() {
    const active = allPromos.filter(p => p.status === 'ACTIVE').length;
    const customers = allPromos.reduce((s, p) => s + (p.target_customers || 0), 0);
    const avgDisc = allPromos.length ? allPromos.reduce((s, p) => s + (p.discount_pct || 0), 0) / allPromos.length : 0;
    document.getElementById('kpi-active').textContent = active;
    document.getElementById('kpi-customers').textContent = customers.toLocaleString();
    document.getElementById('kpi-avg-discount').textContent = avgDisc.toFixed(1) + '%';
    document.getElementById('kpi-campaigns').textContent = allPromos.length;
}

function renderCharts() {
    // Segment doughnut
    const segCounts = { HIGH_VALUE: 0, REGULAR: 0, AT_RISK: 0, NEW: 0 };
    allSegments.forEach(s => { if (segCounts[s.segment] !== undefined) segCounts[s.segment] += s.customer_count || 0; });
    const ctx1 = document.getElementById('segment-chart').getContext('2d');
    if (segChart) segChart.destroy();
    segChart = new Chart(ctx1, { type: 'doughnut', data: { labels: ['High Value', 'Regular', 'At-Risk', 'New'], datasets: [{ data: Object.values(segCounts), backgroundColor: ['#8b5cf6', '#3b82f6', '#ef4444', '#10b981'], borderWidth: 2, borderColor: '#111827' }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#94a3b8', font: { family: 'Inter' } } } } } });

    // Campaign status pie
    const status = { ACTIVE: 0, SCHEDULED: 0, ENDED: 0, PAUSED: 0 };
    allPromos.forEach(p => { if (status[p.status] !== undefined) status[p.status]++; });
    const ctx2 = document.getElementById('campaign-chart').getContext('2d');
    if (campChart) campChart.destroy();
    campChart = new Chart(ctx2, { type: 'pie', data: { labels: Object.keys(status), datasets: [{ data: Object.values(status), backgroundColor: ['#10b981', '#3b82f6', '#475569', '#f59e0b'], borderWidth: 2, borderColor: '#111827' }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#94a3b8', font: { family: 'Inter' } } } } } });
}

function renderActivePromos() {
    const actives = allPromos.filter(p => p.status === 'ACTIVE').slice(0, 8);
    const tbody = document.getElementById('active-promos-tbody');
    if (!actives.length) { tbody.innerHTML = '<tr><td colspan="7" class="loading-row">No active promotions. Create one with "+ New Promotion".</td></tr>'; return; }
    tbody.innerHTML = actives.map(p => `<tr>
    <td>${p.name}</td>
    <td><span class="badge badge-purple">${p.segment?.replace('_', ' ')}</span></td>
    <td class="text-accent">${p.discount_pct || 0}%</td>
    <td><span class="badge badge-info">${p.channel}</span></td>
    <td>${(p.target_customers || 0).toLocaleString()}</td>
    <td>${p.end_date || '—'}</td>
    <td><button class="btn btn-danger btn-sm" onclick="setPromoStatus('${p.id}','ENDED')">End</button></td>
  </tr>`).join('');
}

/* ── Segments ────────────────────────────────────────────── */
function renderSegmentKPIs() {
    const counts = { HIGH_VALUE: 0, REGULAR: 0, AT_RISK: 0, NEW: 0 };
    allSegments.forEach(s => { if (counts[s.segment] !== undefined) counts[s.segment] += s.customer_count || 0; });
    document.getElementById('seg-high').textContent = counts.HIGH_VALUE.toLocaleString();
    document.getElementById('seg-regular').textContent = counts.REGULAR.toLocaleString();
    document.getElementById('seg-atrisk').textContent = counts.AT_RISK.toLocaleString();
    document.getElementById('seg-new').textContent = counts.NEW.toLocaleString();
}

function renderSegmentsTable() {
    const tbody = document.getElementById('segments-tbody');
    if (!allSegments.length) { tbody.innerHTML = '<tr><td colspan="6" class="loading-row">No segment data. Click "+ Add Segment" to define customer groups.</td></tr>'; return; }
    tbody.innerHTML = allSegments.map(s => {
        const promoCount = allPromos.filter(p => p.segment === s.segment && p.status === 'ACTIVE').length;
        return `<tr>
      <td><span class="badge badge-purple">${s.segment?.replace(/_/g, ' ')}</span></td>
      <td>${(s.customer_count || 0).toLocaleString()}</td>
      <td>${s.avg_spend_kwd?.toFixed(3) || '—'}</td>
      <td>${s.last_purchase_date || '—'}</td>
      <td><span class="badge ${promoCount > 0 ? 'badge-success' : 'badge-muted'}">${promoCount} active</span></td>
      <td><button class="btn-icon" onclick="deleteSegment('${s.id}')">🗑️</button></td>
    </tr>`;
    }).join('');
}

/* ── Promotions table ────────────────────────────────────── */
function applyFilters() {
    const s = document.getElementById('search-promo').value.toLowerCase();
    const st = document.getElementById('filter-promo-status').value;
    filteredPromos = allPromos.filter(p => (!s || (p.name || '').toLowerCase().includes(s)) && (!st || p.status === st));
    currentPage = 1; renderPromosTable();
}

const BADGE_MAP = { ACTIVE: 'badge-success', SCHEDULED: 'badge-info', ENDED: 'badge-muted', PAUSED: 'badge-pending' };
function renderPromosTable() {
    const slice = filteredPromos.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
    const total = Math.ceil(filteredPromos.length / PAGE_SIZE);
    const tbody = document.getElementById('promos-tbody');
    if (!slice.length) { tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No promotions found.</td></tr>'; }
    else tbody.innerHTML = slice.map(p => `<tr>
    <td>${p.name}</td>
    <td><span class="badge badge-purple">${p.segment?.replace(/_/g, ' ')}</span></td>
    <td class="text-accent">${p.discount_pct || 0}%</td>
    <td><span class="badge badge-info">${p.channel}</span></td>
    <td>${p.start_date || '—'}</td>
    <td>${p.end_date || '—'}</td>
    <td><span class="badge ${BADGE_MAP[p.status] || 'badge-muted'}">${p.status}</span></td>
    <td>
      <button class="btn-icon" onclick="openPromoModal('${p.id}')">✏️</button>
      ${p.status !== 'ACTIVE' ? `<button class="btn-icon" onclick="setPromoStatus('${p.id}','ACTIVE')">▶️</button>` : ''}
      <button class="btn-icon" onclick="deletePromo('${p.id}')">🗑️</button>
    </td>
  </tr>`).join('');
    document.getElementById('page-info').textContent = `Page ${currentPage} of ${total || 1} (${filteredPromos.length.toLocaleString()})`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= total;
}

/* ── Campaigns view ──────────────────────────────────────── */
function renderCampaigns() {
    const container = document.getElementById('campaign-cards');
    if (!allPromos.length) { container.innerHTML = '<div class="loading-row">No campaigns yet.</div>'; return; }
    const statusGroups = { ACTIVE: [], SCHEDULED: [], PAUSED: [], ENDED: [] };
    allPromos.forEach(p => { if (statusGroups[p.status]) statusGroups[p.status].push(p); });
    const statusColors = { ACTIVE: 'var(--green)', SCHEDULED: 'var(--blue)', PAUSED: 'var(--accent)', ENDED: 'var(--text-muted)' };
    container.innerHTML = Object.entries(statusGroups).filter(([, arr]) => arr.length > 0).map(([st, arr]) => `
    <div class="card" style="border-top:3px solid ${statusColors[st]}">
      <div class="card-header">
        <span class="card-title">${st}</span>
        <span class="badge ${BADGE_MAP[st]}">${arr.length}</span>
      </div>
      <div class="card-body" style="display:flex;flex-direction:column;gap:10px">
        ${arr.map(p => `
          <div style="background:var(--bg-base);border-radius:8px;padding:12px;border:1px solid var(--border)">
            <div style="font-weight:600;font-size:13px;margin-bottom:4px">${p.name}</div>
            <div style="font-size:12px;color:var(--text-muted)">${p.segment?.replace(/_/g, ' ')} · ${p.channel} · <span style="color:var(--accent)">${p.discount_pct || 0}% off</span></div>
            ${p.start_date ? `<div style="font-size:11px;color:var(--text-muted);margin-top:4px">${p.start_date} → ${p.end_date || 'ongoing'}</div>` : ''}
          </div>`).join('')}
      </div>
    </div>`).join('');
}

/* ── Promo CRUD ──────────────────────────────────────────── */
function openPromoModal(id) {
    editingPromoId = id || null;
    document.getElementById('promo-modal-title').textContent = id ? 'Edit Promotion' : 'New Promotion';
    const p = id ? allPromos.find(x => x.id === id) : null;
    document.getElementById('pm-id').value = id || '';
    document.getElementById('pm-name').value = p?.name || '';
    document.getElementById('pm-segment').value = p?.segment || 'HIGH_VALUE';
    document.getElementById('pm-discount').value = p?.discount_pct || '';
    document.getElementById('pm-channel').value = p?.channel || 'EMAIL';
    document.getElementById('pm-status').value = p?.status || 'SCHEDULED';
    document.getElementById('pm-start').value = p?.start_date || '';
    document.getElementById('pm-end').value = p?.end_date || '';
    document.getElementById('pm-customers').value = p?.target_customers || '';
    document.getElementById('pm-desc').value = p?.offer_description || '';
    document.getElementById('promo-modal').classList.add('open');
}

async function savePromo() {
    const payload = {
        name: document.getElementById('pm-name').value.trim(),
        segment: document.getElementById('pm-segment').value,
        discount_pct: parseFloat(document.getElementById('pm-discount').value) || 0,
        channel: document.getElementById('pm-channel').value,
        status: document.getElementById('pm-status').value,
        start_date: document.getElementById('pm-start').value || null,
        end_date: document.getElementById('pm-end').value || null,
        target_customers: parseInt(document.getElementById('pm-customers').value) || 0,
        offer_description: document.getElementById('pm-desc').value.trim()
    };
    if (!payload.name) { showToast('Promotion name is required', 'error'); return; }
    try {
        if (editingPromoId) await sb(`${PROMOS_TABLE}?id=eq.${editingPromoId}`, { method: 'PATCH', body: JSON.stringify(payload), prefer: 'return=minimal' });
        else await sb(PROMOS_TABLE, { method: 'POST', body: JSON.stringify(payload) });
        showToast('Promotion saved ✅', 'success');
        document.getElementById('promo-modal').classList.remove('open');
        await refresh();
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function setPromoStatus(id, status) {
    await sb(`${PROMOS_TABLE}?id=eq.${id}`, { method: 'PATCH', body: JSON.stringify({ status }), prefer: 'return=minimal' });
    showToast(`Status → ${status}`, 'success'); await refresh();
}

async function deletePromo(id) {
    if (!confirm('Delete this promotion?')) return;
    await sb(`${PROMOS_TABLE}?id=eq.${id}`, { method: 'DELETE', prefer: 'return=minimal' });
    showToast('Deleted', 'info'); await refresh();
}

/* ── Segment CRUD ────────────────────────────────────────── */
async function saveSegment() {
    const payload = {
        segment: document.getElementById('sgm-segment').value,
        customer_count: parseInt(document.getElementById('sgm-count').value) || 0,
        avg_spend_kwd: parseFloat(document.getElementById('sgm-avg-spend').value) || null,
        last_purchase_date: document.getElementById('sgm-last-purchase').value || null
    };
    try {
        await sb(SEGMENTS_TABLE, { method: 'POST', body: JSON.stringify(payload) });
        showToast('Segment saved ✅', 'success');
        document.getElementById('seg-modal').classList.remove('open');
        await refresh();
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function deleteSegment(id) {
    if (!confirm('Delete this segment?')) return;
    await sb(`${SEGMENTS_TABLE}?id=eq.${id}`, { method: 'DELETE', prefer: 'return=minimal' });
    showToast('Deleted', 'info'); await refresh();
}

/* ── Navigation ──────────────────────────────────────────── */
const VIEWS = {
    overview: { v: 'view-overview', n: 'nav-overview', t: 'Overview', s: 'Loyalty & promotion overview' },
    segments: { v: 'view-segments', n: 'nav-segments', t: 'Customer Segments', s: 'Segmented customer groups' },
    promotions: { v: 'view-promotions', n: 'nav-promotions', t: 'Promotions', s: 'All promotion records' },
    campaigns: { v: 'view-campaigns', n: 'nav-campaigns', t: 'Campaigns', s: 'Campaign status board' }
};

function switchView(key) {
    activeView = key;
    Object.entries(VIEWS).forEach(([k, v]) => { document.getElementById(v.v).classList.toggle('active', k === key); document.getElementById(v.n).classList.toggle('active', k === key); });
    document.getElementById('page-title').textContent = VIEWS[key].t;
    document.getElementById('page-sub').textContent = VIEWS[key].s;
    if (key === 'overview') { renderKPIs(); renderCharts(); renderActivePromos(); }
    if (key === 'segments') { renderSegmentKPIs(); renderSegmentsTable(); }
    if (key === 'promotions') applyFilters();
    if (key === 'campaigns') renderCampaigns();
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
    document.getElementById('search-promo').addEventListener('input', applyFilters);
    document.getElementById('filter-promo-status').addEventListener('change', applyFilters);
    document.getElementById('btn-prev').addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderPromosTable(); } });
    document.getElementById('btn-next').addEventListener('click', () => { const t = Math.ceil(filteredPromos.length / PAGE_SIZE); if (currentPage < t) { currentPage++; renderPromosTable(); } });
    document.getElementById('btn-refresh').addEventListener('click', refresh);
    document.getElementById('btn-add-promo').addEventListener('click', () => openPromoModal(null));
    document.getElementById('btn-add-segment').addEventListener('click', () => document.getElementById('seg-modal').classList.add('open'));
    document.getElementById('promo-modal-close').addEventListener('click', () => document.getElementById('promo-modal').classList.remove('open'));
    document.getElementById('promo-modal-cancel').addEventListener('click', () => document.getElementById('promo-modal').classList.remove('open'));
    document.getElementById('promo-modal-save').addEventListener('click', savePromo);
    document.getElementById('seg-modal-close').addEventListener('click', () => document.getElementById('seg-modal').classList.remove('open'));
    document.getElementById('seg-modal-cancel').addEventListener('click', () => document.getElementById('seg-modal').classList.remove('open'));
    document.getElementById('seg-modal-save').addEventListener('click', saveSegment);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('open')); });
    window.openPromoModal = openPromoModal; window.deletePromo = deletePromo; window.setPromoStatus = setPromoStatus; window.deleteSegment = deleteSegment;
    refresh();
});
