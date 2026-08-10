// ============================================================
// auth.js - login, logout, and switching between cashier/admin UI
// ============================================================

document.getElementById('login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const errEl = document.getElementById('login-error');
  errEl.classList.add('hidden');
  try {
    const data = await api('/api/login', { method: 'POST', body: JSON.stringify({ username, password }) });
    TOKEN = data.token;
    CURRENT_USER = data.user;
    sessionStorage.setItem('pos_token', TOKEN);
    sessionStorage.setItem('pos_user', JSON.stringify(CURRENT_USER));
    enterApp();
  } catch (err) {
    errEl.innerText = err.message;
    errEl.classList.remove('hidden');
  }
});

function enterApp() {
  document.getElementById('login-section').classList.add('hidden');
  if (CURRENT_USER.role === 'admin') {
    document.getElementById('admin-ui').classList.remove('hidden');
    initAdminUI();
  } else {
    document.getElementById('cashier-ui').classList.remove('hidden');
    document.getElementById('cashier-name').innerText = 'Cashier: ' + (CURRENT_USER.full_name || CURRENT_USER.username);
    initCashierUI();
  }
  applySettingsToUI();
}

async function logout() {
  try { await api('/api/logout', { method: 'POST' }); } catch (e) {}
  TOKEN = null; CURRENT_USER = null;
  sessionStorage.removeItem('pos_token'); sessionStorage.removeItem('pos_user');
  cart = [];
  stopScanner();
  document.getElementById('cashier-ui').classList.add('hidden');
  document.getElementById('admin-ui').classList.add('hidden');
  document.getElementById('login-section').classList.remove('hidden');
  document.getElementById('login-form').reset();
}
