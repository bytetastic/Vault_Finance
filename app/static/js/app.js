/* ══════════════════════════════════════════════
   Vault v2 – app.js
   ══════════════════════════════════════════════ */

// ── Theme ────────────────────────────────────
(function () {
  const t = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', t);
  updateThemeIcon(t);
})();

function updateThemeIcon(t) {
  const icon  = document.getElementById('themeIcon');
  const label = document.getElementById('themeLabel');
  if (icon)  icon.textContent  = t === 'dark' ? '🌙' : '☀️';
  if (label) label.textContent = t === 'dark' ? 'Dark Mode' : 'Light Mode';
}

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  const nxt = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', nxt);
  localStorage.setItem('theme', nxt);
  updateThemeIcon(nxt);
  fetch('/api/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme: nxt }),
  });
}

// ── Sidebar ───────────────────────────────────
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  sb.classList.toggle('collapsed');
  localStorage.setItem('sidebarCollapsed', sb.classList.contains('collapsed') ? '1' : '0');
}

function toggleMobileMenu() {
  const sb  = document.getElementById('sidebar');
  const ov  = document.getElementById('mobOverlay');
  sb.classList.toggle('mobile-open');
  ov.classList.toggle('active');
}
(function () {
  if (localStorage.getItem('sidebarCollapsed') === '1')
    document.getElementById('sidebar')?.classList.add('collapsed');
})();

// ── Modals ────────────────────────────────────
let _activeModal = null;

function openModal(id) {
  closeModal();
  const m = document.getElementById(id);
  const b = document.getElementById('modalBackdrop');
  if (!m) return;
  m.classList.add('active');
  b.classList.add('active');
  _activeModal = id;
  // Trap focus
  requestAnimationFrame(() => m.querySelector('input, select, textarea, button')?.focus());
}

function closeModal() {
  document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
  document.getElementById('modalBackdrop')?.classList.remove('active');
  _activeModal = null;
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── Confirm Dialog ────────────────────────────
let _confirmCb = null;
function showConfirm(msg, cb) {
  document.getElementById('confirmMsg').textContent = msg;
  _confirmCb = cb;
  document.getElementById('confirmOkBtn').onclick = () => { closeModal(); _confirmCb?.(); };
  openModal('confirmModal');
}

// ── Toast ─────────────────────────────────────
function showToast(msg, type = 'success', duration = 3200) {
  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${icons[type] || '💬'}</span><span>${escHtml(String(msg))}</span>`;
  document.getElementById('toasts').appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ── Utils ─────────────────────────────────────
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtAmount(amount, cfg = {}) {
  const cur = cfg.currency || '€';
  const pos = cfg.currency_position || 'after';
  const v = Math.abs(amount).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return pos === 'before' ? `${cur}${v}` : `${v} ${cur}`;
}

// ── Currency prefix update ────────────────────
function loadCurrencyPrefix() {
  fetch('/api/settings').then(r => r.json()).then(cfg => {
    const pre = document.getElementById('currencyPrefix');
    if (pre) pre.textContent = cfg.currency || '€';
    window.APP_CFG = cfg;
  });
}

// ── Categories cache ──────────────────────────
let _catsCache = null;
async function fetchCategories(typeFilter = '') {
  const url = '/api/categories' + (typeFilter ? `?type=${typeFilter}` : '');
  const resp = await fetch(url);
  _catsCache = await resp.json();
  return _catsCache;
}

// ── Transaction Modal ─────────────────────────
let _txType = 'expense';
let _editingTxId = null;

function setTxType(t) {
  _txType = t;
  document.getElementById('txType').value = t;
  document.getElementById('btnExpense').classList.toggle('active', t === 'expense');
  document.getElementById('btnIncome').classList.toggle('active',  t === 'income');
  document.getElementById('budgetMonthWrap').style.display = '';  // always visible
  populateCatSelect();
}

function openAddTx(defaultType) {
  _editingTxId = null;
  document.getElementById('txId').value        = '';
  document.getElementById('txAmount').value    = '';
  document.getElementById('txDesc').value      = '';
  document.getElementById('txEmoji').value     = '';
  document.getElementById('txNote').value      = '';
  document.getElementById('txTags').value      = '';
  document.getElementById('txImagePath').value = '';
  document.getElementById('txBudgetMonth').value = '';
  const preview = document.getElementById('txImagePreview');
  preview.innerHTML = ''; preview.classList.add('hidden');
  document.getElementById('emojiPicker').classList.add('hidden');
  document.getElementById('txDate').value = new Date().toISOString().split('T')[0];
  document.getElementById('txModalTitle').textContent = 'Transaktion hinzufügen';
  document.getElementById('txSaveBtn').textContent = 'Speichern';
  setTxType(defaultType || 'expense');
  loadCurrencyPrefix();
  loadQuickEntries();
  loadTagSuggestions();
  openModal('txModal');
}

async function openEditTx(id) {
  const resp = await fetch(`/api/transactions/${id}`);
  const tx   = await resp.json();
  _editingTxId = id;
  document.getElementById('txId').value        = id;
  document.getElementById('txAmount').value    = tx.amount;
  document.getElementById('txDesc').value      = tx.description;
  document.getElementById('txEmoji').value     = tx.emoji;
  document.getElementById('txNote').value      = tx.note;
  document.getElementById('txDate').value      = tx.date;
  document.getElementById('txImagePath').value = tx.image_path || '';
  document.getElementById('txBudgetMonth').value = tx.budget_month || '';
  document.getElementById('txTags').value      = (tx.tags || []).map(t => '#'+t).join(' ');
  document.getElementById('txModalTitle').textContent = 'Transaktion bearbeiten';
  document.getElementById('txSaveBtn').textContent = '✏️ Aktualisieren';
  setTxType(tx.type);
  await populateCatSelect(tx.category_id);
  if (tx.image_path) {
    const preview = document.getElementById('txImagePreview');
    preview.innerHTML = `<img src="${tx.image_path}" alt=""><span class="remove-img" onclick="clearImage()">✕</span>`;
    preview.classList.remove('hidden');
  }
  loadCurrencyPrefix();
  openModal('txModal');
}

async function populateCatSelect(selected) {
  const cats = await fetchCategories(_txType === 'income' ? 'income' : 'expense');
  const sel  = document.getElementById('txCategory');
  sel.innerHTML = '<option value="">Ohne Kategorie</option>';
  cats.forEach(c => {
    const o = document.createElement('option');
    o.value = c.id; o.textContent = `${c.emoji} ${c.name}`;
    if (selected && String(selected) === String(c.id)) o.selected = true;
    sel.appendChild(o);
  });
}

async function saveTx(e) {
  e.preventDefault();
  const btn = document.getElementById('txSaveBtn');
  btn.textContent = '…'; btn.disabled = true;

  const rawTags = document.getElementById('txTags').value;
  const tags = rawTags.split(/[\s,]+/).map(t => t.replace(/^#/,'')).filter(Boolean);
  const body = {
    type:         document.getElementById('txType').value,
    amount:       parseFloat(document.getElementById('txAmount').value),
    description:  document.getElementById('txDesc').value,
    emoji:        document.getElementById('txEmoji').value,
    category_id:  document.getElementById('txCategory').value || null,
    date:         document.getElementById('txDate').value,
    note:         document.getElementById('txNote').value,
    image_path:   document.getElementById('txImagePath').value,
    budget_month: document.getElementById('txBudgetMonth').value || null,
    tags,
  };

  const id  = document.getElementById('txId').value;
  const url = id ? `/api/transactions/${id}` : '/api/transactions';
  const method = id ? 'PUT' : 'POST';
  const resp = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await resp.json();

  btn.textContent = id ? '✏️ Aktualisieren' : 'Speichern';
  btn.disabled = false;

  if (data.success) {
    showToast(id ? 'Aktualisiert ✓' : 'Gespeichert ✓', 'success');
    closeModal();
    if (typeof refreshTxList === 'function')      refreshTxList();
    else if (typeof loadDashboard === 'function') loadDashboard();
    else location.reload();
  } else {
    showToast(data.error || 'Fehler', 'error');
  }
}

async function deleteTx(id) {
  showConfirm('Transaktion wirklich löschen?', async () => {
    const resp = await fetch(`/api/transactions/${id}`, { method: 'DELETE' });
    const data = await resp.json();
    if (data.success) {
      showToast('Gelöscht', 'success');
      if (typeof refreshTxList === 'function')      refreshTxList();
      else if (typeof loadDashboard === 'function') loadDashboard();
      else location.reload();
    } else {
      showToast(data.error || 'Fehler', 'error');
    }
  });
}

// ── Emoji Picker ──────────────────────────────
const EMOJIS = ['😀','😂','🥳','😍','🤑','💸','💰','💳','🏠','🛒','🚗','🍽️','🎮','✈️',
  '👗','📱','⚕️','📚','🏋️','☕','🎁','🛍️','💼','📊','🏦','💻','🎬','🎵','🍺','🚀',
  '❤️','🔥','⚡','🌟','✅','🔔','📅','🗑️','⚙️','🔄','🧾','🏡','🚌','🍕','💊','🎓'];

function buildEmojiPicker() {
  const picker = document.getElementById('emojiPicker');
  if (!picker || picker.children.length > 0) return;
  picker.innerHTML = EMOJIS.map(em =>
    `<button type="button" class="emoji-btn" onclick="pickEmoji('${em}')">${em}</button>`
  ).join('');
}

function toggleEmojiPicker() {
  buildEmojiPicker();
  document.getElementById('emojiPicker').classList.toggle('hidden');
}

function pickEmoji(em) {
  document.getElementById('txEmoji').value = em;
  document.getElementById('txDesc').value  = document.getElementById('txDesc').value || '';
  document.getElementById('emojiPicker').classList.add('hidden');
}

// ── Image Upload ──────────────────────────────
async function handleImageUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  const resp = await fetch('/api/upload', { method: 'POST', body: fd });
  const data = await resp.json();
  if (data.success) {
    document.getElementById('txImagePath').value = data.path;
    const preview = document.getElementById('txImagePreview');
    preview.innerHTML = `<img src="${data.path}" alt=""><span class="remove-img" onclick="clearImage()">✕</span>`;
    preview.classList.remove('hidden');
  } else {
    showToast(data.error || 'Upload fehlgeschlagen', 'error');
  }
}

function clearImage() {
  document.getElementById('txImagePath').value = '';
  const preview = document.getElementById('txImagePreview');
  preview.innerHTML = ''; preview.classList.add('hidden');
}

// ── Category Modal ────────────────────────────
function openAddCat() {
  document.getElementById('catId').value        = '';
  document.getElementById('catName').value      = '';
  document.getElementById('catEmoji').value     = '📁';
  document.getElementById('catColor').value     = '#22d3a0';
  document.getElementById('catType').value      = 'expense';
  document.getElementById('catBudget').value    = '0';
  const it = document.getElementById('catIncomeType');
  if (it) it.value = 'regular';
  document.getElementById('catModalTitle').textContent = 'Kategorie hinzufügen';
  if (typeof toggleIncomeType === 'function') toggleIncomeType();
  openModal('catModal');
}

async function saveCat(e) {
  e.preventDefault();
  const id = document.getElementById('catId').value;
  const body = {
    name:         document.getElementById('catName').value,
    emoji:        document.getElementById('catEmoji').value || '📁',
    color:        document.getElementById('catColor').value,
    type:         document.getElementById('catType').value,
    budget_limit: parseFloat(document.getElementById('catBudget').value) || 0,
    income_type:  document.getElementById('catIncomeType')?.value || 'regular',
  };
  const url    = id ? `/api/categories/${id}` : '/api/categories';
  const method = id ? 'PUT' : 'POST';
  const resp   = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data   = await resp.json();
  if (data.success) {
    showToast(id ? 'Aktualisiert ✓' : 'Erstellt ✓', 'success');
    closeModal();
    setTimeout(() => location.reload(), 700);
  } else {
    showToast(data.error || 'Fehler', 'error');
  }
}

// ── Recurring Transaction Modal ───────────────
function setRecType(t) {
  document.getElementById('recType').value = t;
  document.getElementById('recBtnExpense')?.classList.toggle('active', t === 'expense');
  document.getElementById('recBtnIncome')?.classList.toggle('active',  t === 'income');
}

async function saveRecurring(e) {
  e.preventDefault();
  const id = document.getElementById('recId').value;
  const body = {
    name:        document.getElementById('recName').value,
    type:        document.getElementById('recType').value,
    amount:      parseFloat(document.getElementById('recAmount').value),
    emoji:       document.getElementById('recEmoji').value || '🔄',
    category_id: document.getElementById('recCategory').value || null,
    frequency:   document.getElementById('recFreq').value,
    start_date:  document.getElementById('recStart').value,
    end_date:    document.getElementById('recEnd').value || null,
    note:        document.getElementById('recNote').value,
    active:      true,
  };
  const url    = id ? `/api/recurring/${id}` : '/api/recurring';
  const method = id ? 'PUT' : 'POST';
  const resp   = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data   = await resp.json();
  if (data.success) {
    showToast(id ? 'Aktualisiert ✓' : 'Erstellt ✓', 'success');
    closeModal();
    setTimeout(() => location.reload(), 700);
  } else {
    showToast(data.error || 'Fehler', 'error');
  }
}

// ── Chart helpers ─────────────────────────────
function chartColors() {
  const s = getComputedStyle(document.documentElement);
  return {
    accent:     s.getPropertyValue('--accent').trim(),
    expense:    s.getPropertyValue('--expense').trim(),
    income:     s.getPropertyValue('--income').trim(),
    text2:      s.getPropertyValue('--text-2').trim(),
    border:     s.getPropertyValue('--border').trim(),
    glass2:     s.getPropertyValue('--glass-2').trim(),
  };
}

Chart.defaults.font.family   = "'Plus Jakarta Sans', sans-serif";
Chart.defaults.color          = '#8b96b0';

function makeBarChart(ctx, labels, incomes, expenses) {
  const c = chartColors();
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: 'Einnahmen', data: incomes,  backgroundColor: c.income  + '55', borderColor: c.income,  borderWidth: 2, borderRadius: 8 },
        { label: 'Ausgaben',  data: expenses, backgroundColor: c.expense + '55', borderColor: c.expense, borderWidth: 2, borderRadius: 8 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'top', labels: { usePointStyle: true, padding: 16 } } },
      scales: {
        x: { grid: { color: c.border }, ticks: { color: c.text2 } },
        y: { grid: { color: c.border }, ticks: { color: c.text2, callback: v => v + ' €' } },
      },
    },
  });
}

function makeDoughnutChart(ctx, labels, values, colors) {
  return new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '72%',
      plugins: { legend: { position: 'right', labels: { usePointStyle: true, padding: 14, boxWidth: 10 } } },
    },
  });
}

function makeLineChart(ctx, labels, data, label, color) {
  const c = chartColors();
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label, data, borderColor: color, borderWidth: 2.5,
        backgroundColor: color + '22', fill: true, tension: 0.45, pointRadius: 3,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: c.border }, ticks: { color: c.text2 } },
        y: { grid: { color: c.border }, ticks: { color: c.text2, callback: v => v + ' €' } },
      },
    },
  });
}

// ── Quick Entries ─────────────────────────────
async function loadQuickEntries() {
  const resp = await fetch('/api/quickentries');
  const entries = await resp.json();
  const bar  = document.getElementById('quickEntryBar');
  const btns = document.getElementById('quickEntryBtns');
  if (!entries.length) { bar.style.display = 'none'; return; }
  bar.style.display = '';
  btns.innerHTML = entries.map(e => `
    <button type="button" class="qe-btn" onclick="applyQuickEntry(${e.id})"
            data-id="${e.id}" data-amount="${e.amount}" data-type="${e.type}"
            data-desc="${escHtml(e.name)}" data-emoji="${e.emoji}"
            data-cat="${e.category_id||''}">
      ${e.emoji} ${escHtml(e.name)} · ${e.amount.toLocaleString('de-DE',{minimumFractionDigits:2})} €
    </button>`).join('');
}

function applyQuickEntry(id) {
  const btn = document.querySelector(`.qe-btn[data-id="${id}"]`);
  if (!btn) return;
  setTxType(btn.dataset.type);
  document.getElementById('txAmount').value = btn.dataset.amount;
  document.getElementById('txDesc').value   = btn.dataset.desc;
  document.getElementById('txEmoji').value  = btn.dataset.emoji;
  if (btn.dataset.cat) {
    setTimeout(() => {
      const sel = document.getElementById('txCategory');
      if (sel) sel.value = btn.dataset.cat;
    }, 300);
  }
  document.querySelectorAll('.qe-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
}

// ── Tag Suggestions ───────────────────────────
async function loadTagSuggestions() {
  const resp = await fetch('/api/tags');
  const tags = await resp.json();
  const wrap = document.getElementById('tagSuggestions');
  if (!wrap || !tags.length) return;
  wrap.innerHTML = tags.slice(0,12).map(t =>
    `<button type="button" class="tag-chip" onclick="toggleTagSuggestion('${escHtml(t)}')">#${escHtml(t)}</button>`
  ).join('');
}

function toggleTagSuggestion(tag) {
  const inp = document.getElementById('txTags');
  const current = inp.value.split(/[\s,]+/).map(t => t.replace(/^#/,'')).filter(Boolean);
  if (current.includes(tag)) {
    inp.value = current.filter(t => t !== tag).map(t => '#'+t).join(' ');
  } else {
    inp.value = [...current, tag].map(t => '#'+t).join(' ');
  }
  // Update chip active state
  document.querySelectorAll('.tag-chip').forEach(c => {
    const t = c.textContent.replace('#','').trim();
    const active = inp.value.includes('#'+t);
    c.classList.toggle('active', active);
  });
}

// ── Init on load ──────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadCurrencyPrefix();
});
