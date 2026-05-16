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
  const label   = document.getElementById('themeLabel');
  const tooltip = document.getElementById('themeTooltip');
  const iconEl  = document.getElementById('themeIcon');
  const txt = t === 'dark' ? 'Light Mode' : 'Dark Mode';
  if (label)   label.textContent   = txt;
  if (tooltip) tooltip.textContent = txt;
  if (iconEl) {
    if (t === 'dark') {
      // Sun icon (switch to light)
      iconEl.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>';
    } else {
      // Moon icon (switch to dark)
      iconEl.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    }
  }
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

// ── Sidebar v2 — collapsible ──────────────────
function toggleSidebar() {
  const layout = document.getElementById('appLayout');
  const toggle = document.getElementById('sbToggle');
  if (!layout) return;
  const collapsed = layout.classList.toggle('sb-collapsed');
  localStorage.setItem('sbCollapsed', collapsed ? '1' : '0');
  if (toggle) toggle.style.transform = collapsed ? 'rotate(180deg)' : '';
}

function toggleMobileMenu() { /* handled by CSS bottom rail */ }

(function () {
  if (localStorage.getItem('sbCollapsed') === '1') {
    const layout = document.getElementById('appLayout');
    const toggle = document.getElementById('sbToggle');
    if (layout) layout.classList.add('sb-collapsed');
    if (toggle) toggle.style.transform = 'rotate(180deg)';
  }
})();

// ── Ripple effect ─────────────────────────────
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.btn-primary,.btn-ghost,.btn-secondary,.btn-danger,.btn-pill,.btn');
  if (!btn || btn.classList.contains('icon-btn') || btn.classList.contains('icon-btn-sm')) return;
  const r = document.createElement('span');
  const d = Math.max(btn.offsetWidth, btn.offsetHeight);
  const rect = btn.getBoundingClientRect();
  r.className = 'ripple-ink';
  r.style.cssText = `width:${d}px;height:${d}px;left:${e.clientX-rect.left-d/2}px;top:${e.clientY-rect.top-d/2}px;position:absolute;border-radius:50%;pointer-events:none;`;
  btn.appendChild(r);
  setTimeout(() => r.remove(), 650);
}, true);

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
  // Init custom selects in this modal
  setTimeout(() => {
    if (window.initCustomSelects) window.initCustomSelects(m);
    // Focus first input
    m.querySelector('input:not([type="hidden"]):not([type="color"]), .cs-trigger')?.focus?.();
  }, 40);
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

// ── German date/month helpers ─────────────────────────────────────────
const DE_MONTHS = ['Januar','Februar','März','April','Mai','Juni',
                   'Juli','August','September','Oktober','November','Dezember'];
const DE_MONTHS_SHORT = ['Jan','Feb','Mär','Apr','Mai','Jun',
                          'Jul','Aug','Sep','Okt','Nov','Dez'];

function deMonth(dateOrStr) {
  const d = typeof dateOrStr === 'string' ? new Date(dateOrStr + 'T00:00:00') : dateOrStr;
  return `${DE_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}
function deMonthShort(dateOrStr) {
  const d = typeof dateOrStr === 'string' ? new Date(dateOrStr + 'T00:00:00') : dateOrStr;
  return `${DE_MONTHS_SHORT[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
}
function deDate(dateOrStr) {
  const d = typeof dateOrStr === 'string' ? new Date(dateOrStr + 'T00:00:00') : dateOrStr;
  return `${String(d.getDate()).padStart(2,'0')}.${String(d.getMonth()+1).padStart(2,'0')}.${d.getFullYear()}`;
}

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

// ═══════════════════════════════════════════════════════════════════════
// CUSTOM SELECT — replaces ALL native <select> with styled dropdowns
// Auto-initializes on DOMContentLoaded + after any modal opens
// ═══════════════════════════════════════════════════════════════════════

(function () {
  const ACTIVE_DROPDOWNS = new WeakMap();

  function buildCustomSelect(nativeSelect) {
    if (ACTIVE_DROPDOWNS.has(nativeSelect)) return; // already replaced

    const wrapper = document.createElement('div');
    wrapper.className = 'cs-wrap';
    wrapper.style.cssText = `position:relative;display:inline-block;width:${nativeSelect.style.width||'100%'}`;
    if (nativeSelect.style.minWidth) wrapper.style.minWidth = nativeSelect.style.minWidth;

    // Read options
    const getOptions = () => [...nativeSelect.options].map(o => ({ val: o.value, label: o.text.trim(), disabled: o.disabled }));

    // Trigger element (shows current value)
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'cs-trigger';

    const updateTrigger = () => {
      const sel = nativeSelect.options[nativeSelect.selectedIndex];
      trigger.textContent = sel ? sel.text.trim() : '—';
      trigger.dataset.empty = (!nativeSelect.value) ? '1' : '0';
    };
    updateTrigger();

    // Dropdown panel
    const panel = document.createElement('div');
    panel.className = 'cs-panel';
    panel.style.display = 'none';

    const renderPanel = () => {
      panel.innerHTML = '';
      getOptions().forEach(opt => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'cs-item' + (opt.val === nativeSelect.value ? ' selected' : '');
        item.textContent = opt.label;
        item.dataset.val = opt.val;
        if (opt.disabled) item.disabled = true;
        item.addEventListener('click', (e) => {
          e.stopPropagation();
          nativeSelect.value = opt.val;
          nativeSelect.dispatchEvent(new Event('change', { bubbles: true }));
          updateTrigger();
          renderPanel(); // update selected state
          closePanel();
        });
        panel.appendChild(item);
      });
    };

    let isOpen = false;

    const openPanel = () => {
      renderPanel();
      panel.style.display = 'block';
      isOpen = true;
      trigger.classList.add('open');
      // Position: flip up if near bottom of viewport
      requestAnimationFrame(() => {
        const rect = wrapper.getBoundingClientRect();
        const spaceBelow = window.innerHeight - rect.bottom;
        if (spaceBelow < panel.offsetHeight + 8 && rect.top > panel.offsetHeight + 8) {
          panel.style.top = 'auto';
          panel.style.bottom = '100%';
          panel.style.marginBottom = '4px';
          panel.style.marginTop = '0';
        } else {
          panel.style.top = '100%';
          panel.style.bottom = 'auto';
          panel.style.marginTop = '4px';
          panel.style.marginBottom = '0';
        }
      });
    };

    const closePanel = () => {
      panel.style.display = 'none';
      isOpen = false;
      trigger.classList.remove('open');
    };

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      // Close all other dropdowns first
      document.querySelectorAll('.cs-trigger.open').forEach(t => {
        if (t !== trigger) t.click(); // close others
      });
      isOpen ? closePanel() : openPanel();
    });

    // Close on outside click
    document.addEventListener('click', () => { if (isOpen) closePanel(); }, { capture: true, passive: true });

    // Close on Escape
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen) closePanel(); });

    // Sync if native select changes programmatically
    nativeSelect.addEventListener('change', updateTrigger);

    // Build DOM
    nativeSelect.style.display = 'none';
    nativeSelect.insertAdjacentElement('afterend', wrapper);
    wrapper.appendChild(trigger);
    wrapper.appendChild(panel);

    ACTIVE_DROPDOWNS.set(nativeSelect, wrapper);
  }

  function initAllSelects(root) {
    const container = root || document;
    container.querySelectorAll('select').forEach(sel => {
      // Skip if already wrapped, hidden, or part of a filter-group with inline style
      if (sel.closest('.cs-wrap')) return;
      if (sel.id === 'docType') return; // handled by tab buttons
      buildCustomSelect(sel);
    });
  }

  // Init on page load
  document.addEventListener('DOMContentLoaded', () => setTimeout(() => initAllSelects(), 50));

  // Re-init when modals open (selects might be rendered dynamically)
  // openModal integration handled directly in openModal() function above

  // Re-init after dynamic content (review table)
  window.initCustomSelects = initAllSelects;
})();




// ═══════════════════════════════════════════════════════════════════════
// PAGE TRANSITIONS v2 — CSS class based, no inline style manipulation
//
// How it works:
// - CSS handles ALL entrance animations via @keyframes on .main, .v2-hero,
//   .v2-kpi-cell:nth-child(), .v2-card:nth-child() etc.
// - JS only adds .page-exiting class on nav click (triggers CSS exit anim)
//   then navigates after animation completes
// - No element.style.opacity, no element.style.transform — ever
// ═══════════════════════════════════════════════════════════════════════

(function () {
  'use strict';

  const NAV_SELECTOR = 'a.sb-item, a.nav-item, .sb-item[href], .nav-item[href]';
  const EXIT_DURATION = 140; // ms — must match @keyframes vu-exit duration

  // ── Intercept nav clicks ─────────────────────────────────────────────
  document.addEventListener('click', function (e) {
    const link = e.target.closest(NAV_SELECTOR);
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href || href === '#' || href.startsWith('javascript') || href === '/logout') return;
    if (link.classList.contains('active')) return; // already here, no transition

    e.preventDefault();

    const main = document.querySelector('.main, .stream');
    if (!main) { window.location.href = href; return; }

    // Add exit class → CSS animation plays (sidebar is excluded via CSS)
    main.classList.add('page-exiting');
    main.style.setProperty('--cover-display', 'none');
    // Ensure sidebar doesn't animate
    document.querySelector('.sb, .sidebar, .rail')?.style.setProperty('animation', 'none', 'important');

    // Navigate after exit animation finishes
    setTimeout(() => { window.location.href = href; }, EXIT_DURATION);
  }, { capture: false });

  // ── KPI accent lines ─────────────────────────────────────────────────
  // Add .loaded immediately — CSS animation-delay on .loaded::before
  // handles the timing (350ms delay built into CSS)
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.v2-kpi-cell').forEach(cell => cell.classList.add('loaded'));
  });

})();

// ═══════════════════════════════════════════════════════════════════════
// BACKGROUND PARTICLE SYSTEM — Elegant floating dots
// Theme: financial data points, market nodes, security network
// Pure canvas, 60fps via requestAnimationFrame, GPU-friendly
// ═══════════════════════════════════════════════════════════════════════

(function () {
  'use strict';

  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const isDark = () => document.documentElement.getAttribute('data-theme') === 'dark';

  // Particle config
  const COUNT    = 38;   // number of particles
  const MAX_DIST = 160;  // max distance for connection lines
  const SPEED    = 0.25; // base movement speed

  let W, H, particles = [];
  let animId;
  let lastTheme = isDark();

  // Resize handler
  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  // Particle factory
  function makeParticle() {
    const angle = Math.random() * Math.PI * 2;
    const speed = SPEED * (0.4 + Math.random() * 0.6);
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      r: 1 + Math.random() * 1.5,  // radius 1–2.5px
      opacity: 0.15 + Math.random() * 0.35,
      pulse: Math.random() * Math.PI * 2,  // phase for opacity pulse
    };
  }

  function init() {
    resize();
    particles = Array.from({ length: COUNT }, makeParticle);
  }

  function getColors() {
    const dark = isDark();
    return {
      dot:  dark ? 'rgba(92,194,138,'  : 'rgba(31,122,68,',
      line: dark ? 'rgba(92,194,138,'  : 'rgba(31,122,68,',
      bg:   dark ? [15, 15, 16]        : [245, 245, 247],
    };
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    const C = getColors();
    const now = Date.now() / 1000;

    // Update + draw particles
    particles.forEach(p => {
      // Move
      p.x += p.vx;
      p.y += p.vy;

      // Wrap around edges with soft margin
      if (p.x < -20)  p.x = W + 20;
      if (p.x > W+20) p.x = -20;
      if (p.y < -20)  p.y = H + 20;
      if (p.y > H+20) p.y = -20;

      // Pulse opacity
      const pulseOpacity = p.opacity * (0.7 + 0.3 * Math.sin(now * 0.8 + p.pulse));

      // Draw dot
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = C.dot + pulseOpacity + ')';
      ctx.fill();
    });

    // Draw connection lines between nearby particles
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const a = particles[i], b = particles[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < MAX_DIST) {
          const alpha = (1 - dist / MAX_DIST) * 0.18;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.strokeStyle = C.line + alpha + ')';
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      }
    }

    animId = requestAnimationFrame(draw);
  }

  // Start
  window.addEventListener('resize', () => {
    resize();
    // Redistribute particles on resize
    particles.forEach(p => {
      p.x = Math.min(p.x, W);
      p.y = Math.min(p.y, H);
    });
  });

  // Pause when tab hidden (save CPU)
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      cancelAnimationFrame(animId);
    } else {
      draw();
    }
  });

  // Respect reduced motion
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    canvas.style.display = 'none';
    return;
  }

  document.addEventListener('DOMContentLoaded', () => {
    init();
    draw();
  });

})();
