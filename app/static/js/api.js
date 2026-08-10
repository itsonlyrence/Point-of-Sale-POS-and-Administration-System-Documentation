// ============================================================
// api.js - fetch wrapper, session state, and system settings
// ============================================================

const API = ''; // same origin
let TOKEN = sessionStorage.getItem('pos_token') || null;
let CURRENT_USER = JSON.parse(sessionStorage.getItem('pos_user') || 'null');

// Cached copy of /api/settings, refreshed on load and after admin edits.
let SETTINGS = {
  system_name: 'POS System',
  store_address: '',
  store_contact: '',
  receipt_footer: 'Thank you for shopping with us!',
};

async function api(path, opts = {}) {
  opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
  if (TOKEN) opts.headers['Authorization'] = 'Bearer ' + TOKEN;
  const res = await fetch(API + path, opts);
  if (res.headers.get('Content-Type') && res.headers.get('Content-Type').includes('application/json')) {
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  }
  if (!res.ok) throw new Error('Request failed');
  return res;
}

// Loads the system name / receipt info and applies it to every place the
// brand shows up: <title>, login header, cashier header, admin header.
async function loadSettings() {
  try {
    const data = await api('/api/settings');
    SETTINGS = data.settings;
  } catch (e) {
    // Not signed in yet is fine - /api/settings is public. Any other
    // failure just falls back to the cached defaults above.
  }
  applySettingsToUI();
}

function applySettingsToUI() {
  document.title = SETTINGS.system_name;
  document.querySelectorAll('.system-name-label').forEach(el => {
    el.textContent = SETTINGS.system_name;
  });
}
