// ============================================================
// admin.js - inventory, categories/suppliers, users, sales, reports,
//            audit log, backup, and system settings (name/receipt info)
// ============================================================

let categories = [];

let currentTab = 'inventory';
function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
  document.getElementById('tab-' + tab).classList.remove('hidden');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  if (tab === 'catalog') { loadCategories(); loadSuppliers(); }
  if (tab === 'users') loadUsers();
  if (tab === 'sales') loadSales();
  if (tab === 'reports') loadReports();
  if (tab === 'audit') loadAuditLog();
  if (tab === 'settings') loadSettingsForm();
}

async function initAdminUI() {
  await loadProducts();
  await loadCategories();
  await updateAdminMetrics();
  switchTab('inventory');
}

async function updateAdminMetrics() {
  const s = await api('/api/reports/summary?range=today');
  document.getElementById('admin-revenue').innerText = `\u20b1${s.revenue.toFixed(2)}`;
  document.getElementById('admin-tx').innerText = s.transactions;
  document.getElementById('admin-items-sold').innerText = s.items_sold;
  document.getElementById('admin-low-stock').innerText = s.low_stock_count;
}

// ---- Inventory ----
function renderInventoryTable() {
  const tbody = document.getElementById('inventory-table-body');
  if (!tbody) return;
  tbody.innerHTML = '';
  products.forEach(p => {
    const stockBadge = p.stock <= p.reorder_level
      ? `<span class="bg-red-100 text-red-600 px-2 py-0.5 rounded text-xs font-bold">${p.stock} (Low)</span>`
      : `<span class="bg-green-100 text-green-700 px-2 py-0.5 rounded text-xs">${p.stock}</span>`;
    const archivedBadge = p.active ? '' : '<span class="ml-2 text-xs text-gray-400">(archived)</span>';
    tbody.innerHTML += `
      <tr class="border-b">
        <td class="p-3 font-mono text-gray-500">${p.barcode}</td>
        <td class="p-3 font-medium text-gray-800">${p.name}${archivedBadge}</td>
        <td class="p-3">${p.category_name || '-'}</td>
        <td class="p-3">\u20b1${p.price.toFixed(2)}</td>
        <td class="p-3">\u20b1${(p.cost || 0).toFixed(2)}</td>
        <td class="p-3">${stockBadge}</td>
        <td class="p-3">${p.reorder_level}</td>
        <td class="p-3 space-x-2 whitespace-nowrap">
          <button onclick="openStockModal(${p.id})" class="text-blue-600 hover:text-blue-800 text-xs"><i class="fa-solid fa-boxes-packing"></i> Stock</button>
          <button onclick="openEditProductModal(${p.id})" class="text-emerald-600 hover:text-emerald-800 text-xs"><i class="fa-solid fa-pen"></i> Edit</button>
          ${p.active
            ? `<button onclick="archiveProduct(${p.id})" class="text-red-500 hover:text-red-700 text-xs"><i class="fa-solid fa-box-archive"></i> Archive</button>`
            : `<button onclick="restoreProduct(${p.id})" class="text-gray-500 hover:text-gray-700 text-xs"><i class="fa-solid fa-rotate-left"></i> Restore</button>`}
        </td>
      </tr>`;
  });
}

function openAddProductModal() {
  document.getElementById('product-form').reset();
  document.getElementById('edit-product-id').value = '';
  populateCategorySelect();
  document.getElementById('product-modal').classList.remove('hidden');
}
function openEditProductModal(id) {
  const p = products.find(x => x.id === id);
  if (!p) return;
  populateCategorySelect();
  document.getElementById('edit-product-id').value = p.id;
  document.getElementById('new-barcode').value = p.barcode;
  document.getElementById('new-name').value = p.name;
  document.getElementById('new-category-select').value = p.category_id || '';
  document.getElementById('new-price').value = p.price;
  document.getElementById('new-cost').value = p.cost;
  document.getElementById('new-stock').value = p.stock;
  document.getElementById('new-reorder').value = p.reorder_level;
  document.getElementById('new-barcode').disabled = true;
  document.getElementById('new-stock').disabled = true;
  document.getElementById('product-modal').classList.remove('hidden');
}
function closeAddProductModal() {
  document.getElementById('product-modal').classList.add('hidden');
  document.getElementById('new-barcode').disabled = false;
  document.getElementById('new-stock').disabled = false;
}
function populateCategorySelect() {
  const sel = document.getElementById('new-category-select');
  sel.innerHTML = '<option value="">(none)</option>' + categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
}

document.getElementById('product-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const editId = document.getElementById('edit-product-id').value;
  const payload = {
    barcode: document.getElementById('new-barcode').value.trim(),
    name: document.getElementById('new-name').value.trim(),
    category_id: document.getElementById('new-category-select').value || null,
    price: parseFloat(document.getElementById('new-price').value),
    cost: parseFloat(document.getElementById('new-cost').value) || 0,
    stock: parseInt(document.getElementById('new-stock').value) || 0,
    reorder_level: parseInt(document.getElementById('new-reorder').value) || 10,
  };
  try {
    if (editId) { await api(`/api/products/${editId}`, { method: 'PUT', body: JSON.stringify(payload) }); }
    else { await api('/api/products', { method: 'POST', body: JSON.stringify(payload) }); }
    closeAddProductModal();
    await loadProducts();
    renderInventoryTable();
    await updateAdminMetrics();
  } catch (err) { alert(err.message); }
});

async function archiveProduct(id) {
  if (!confirm('Archive this product? It will no longer appear at checkout, but sales history is kept.')) return;
  await api(`/api/products/${id}`, { method: 'DELETE' });
  await loadProducts(); renderInventoryTable(); await updateAdminMetrics();
}
async function restoreProduct(id) {
  await api(`/api/products/${id}/restore`, { method: 'POST' });
  await loadProducts(); renderInventoryTable();
}

function openStockModal(id) {
  document.getElementById('adjust-product-id').value = id;
  document.getElementById('stock-form').reset();
  document.getElementById('adjust-product-id').value = id;
  document.getElementById('stock-modal').classList.remove('hidden');
}
function closeStockModal() { document.getElementById('stock-modal').classList.add('hidden'); }
document.getElementById('stock-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('adjust-product-id').value;
  const change_qty = parseInt(document.getElementById('adjust-qty').value);
  const reason = document.getElementById('adjust-reason').value.trim();
  try {
    await api(`/api/products/${id}/adjust-stock`, { method: 'POST', body: JSON.stringify({ change_qty, reason }) });
    closeStockModal();
    await loadProducts(); renderInventoryTable(); await updateAdminMetrics();
  } catch (err) { alert(err.message); }
});

// ---- Categories / suppliers ----
async function loadCategories() {
  const data = await api('/api/categories');
  categories = data.categories;
  const list = document.getElementById('category-list');
  if (list) list.innerHTML = categories.map(c => `<li class="flex justify-between items-center py-2"><span>${c.name}</span><button onclick="deleteCategory(${c.id})" class="text-red-500 text-xs"><i class="fa-solid fa-trash"></i></button></li>`).join('') || '<li class="text-gray-400 py-2">No categories yet.</li>';
}
document.getElementById('category-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('new-category').value.trim();
  try { await api('/api/categories', { method: 'POST', body: JSON.stringify({ name }) }); document.getElementById('category-form').reset(); await loadCategories(); }
  catch (err) { alert(err.message); }
});
async function deleteCategory(id) {
  if (!confirm('Delete this category?')) return;
  await api(`/api/categories/${id}`, { method: 'DELETE' });
  await loadCategories(); await loadProducts(); renderInventoryTable();
}

async function loadSuppliers() {
  const data = await api('/api/suppliers');
  const list = document.getElementById('supplier-list');
  list.innerHTML = data.suppliers.map(s => `<li class="flex justify-between items-center py-2"><span>${s.name}${s.contact ? ' <span class=\"text-gray-400\">(' + s.contact + ')</span>' : ''}</span><button onclick="deleteSupplier(${s.id})" class="text-red-500 text-xs"><i class="fa-solid fa-trash"></i></button></li>`).join('') || '<li class="text-gray-400 py-2">No suppliers yet.</li>';
}
document.getElementById('supplier-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = document.getElementById('new-supplier-name').value.trim();
  const contact = document.getElementById('new-supplier-contact').value.trim();
  try { await api('/api/suppliers', { method: 'POST', body: JSON.stringify({ name, contact }) }); document.getElementById('supplier-form').reset(); await loadSuppliers(); }
  catch (err) { alert(err.message); }
});
async function deleteSupplier(id) { if (!confirm('Delete this supplier?')) return; await api(`/api/suppliers/${id}`, { method: 'DELETE' }); await loadSuppliers(); }

// ---- Users (admin: add staff / cashier accounts) ----
async function loadUsers() {
  const data = await api('/api/users');
  const tbody = document.getElementById('users-table-body');
  tbody.innerHTML = data.users.map(u => `
    <tr class="border-b">
      <td class="p-3 font-mono">${u.username}</td>
      <td class="p-3">${u.full_name || '-'}</td>
      <td class="p-3"><span class="px-2 py-0.5 rounded text-xs ${u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'}">${u.role}</span></td>
      <td class="p-3">${u.active ? '<span class="text-green-600 text-xs">Active</span>' : '<span class="text-gray-400 text-xs">Inactive</span>'}</td>
      <td class="p-3 space-x-2">
        ${u.active ? `<button onclick="deactivateUser(${u.id})" class="text-red-500 hover:text-red-700 text-xs"><i class="fa-solid fa-user-slash"></i> Deactivate</button>` : ''}
      </td>
    </tr>`).join('');
}
function openAddUserModal() { document.getElementById('user-form').reset(); document.getElementById('user-modal').classList.remove('hidden'); }
function closeAddUserModal() { document.getElementById('user-modal').classList.add('hidden'); }
document.getElementById('user-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    username: document.getElementById('new-user-username').value.trim(),
    full_name: document.getElementById('new-user-fullname').value.trim(),
    password: document.getElementById('new-user-password').value,
    role: document.getElementById('new-user-role').value,
  };
  try { await api('/api/users', { method: 'POST', body: JSON.stringify(payload) }); closeAddUserModal(); await loadUsers(); }
  catch (err) { alert(err.message); }
});
async function deactivateUser(id) {
  if (!confirm('Deactivate this account? They will no longer be able to sign in.')) return;
  try { await api(`/api/users/${id}`, { method: 'DELETE' }); await loadUsers(); } catch (err) { alert(err.message); }
}

// ---- Sales / void (with receipt reprint) ----
async function loadSales() {
  const range = document.getElementById('sales-range').value;
  const data = await api(`/api/sales?range=${range}`);
  const tbody = document.getElementById('sales-table-body');
  tbody.innerHTML = data.sales.map(s => `
    <tr class="border-b ${s.voided ? 'opacity-50' : ''}">
      <td class="p-3 font-mono">${s.receipt_no}</td>
      <td class="p-3">${s.created_at}</td>
      <td class="p-3">${s.cashier_name || '-'}</td>
      <td class="p-3">\u20b1${s.total.toFixed(2)}</td>
      <td class="p-3">${s.voided ? '<span class="text-red-500 text-xs">Voided</span>' : '<span class="text-green-600 text-xs">Completed</span>'}</td>
      <td class="p-3 space-x-2 whitespace-nowrap">
        <button onclick="reprintSale(${s.id})" class="text-blue-600 hover:text-blue-800 text-xs"><i class="fa-solid fa-print"></i> Print</button>
        ${s.voided ? '' : `<button onclick="openVoidModal(${s.id})" class="text-red-500 hover:text-red-700 text-xs"><i class="fa-solid fa-ban"></i> Void</button>`}
      </td>
    </tr>`).join('');
}
function openVoidModal(id) { document.getElementById('void-sale-id').value = id; document.getElementById('void-form').reset(); document.getElementById('void-sale-id').value = id; document.getElementById('void-modal').classList.remove('hidden'); }
function closeVoidModal() { document.getElementById('void-modal').classList.add('hidden'); }
document.getElementById('void-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('void-sale-id').value;
  const reason = document.getElementById('void-reason').value.trim();
  try {
    await api(`/api/sales/${id}/void`, { method: 'POST', body: JSON.stringify({ reason }) });
    closeVoidModal(); await loadSales(); await loadProducts(); await updateAdminMetrics();
  } catch (err) { alert(err.message); }
});

// ---- Reports ----
async function loadReports() {
  const range = document.getElementById('report-range').value;
  const top = await api(`/api/reports/top-products?range=${range}&limit=10`);
  document.getElementById('top-products-body').innerHTML = top.products.map(p => `<tr class="border-b"><td class="p-2">${p.name}</td><td class="p-2 text-center">${p.qty_sold}</td><td class="p-2 text-right">\u20b1${p.revenue.toFixed(2)}</td></tr>`).join('') || '<tr><td class="p-2 text-gray-400" colspan="3">No sales in range.</td></tr>';
  const byCashier = await api(`/api/reports/by-cashier?range=${range}`);
  document.getElementById('by-cashier-body').innerHTML = byCashier.cashiers.map(c => `<tr class="border-b"><td class="p-2">${c.username}</td><td class="p-2 text-center">${c.tx}</td><td class="p-2 text-right">\u20b1${c.revenue.toFixed(2)}</td></tr>`).join('') || '<tr><td class="p-2 text-gray-400" colspan="3">No sales in range.</td></tr>';
}
function exportCsv() {
  const range = document.getElementById('report-range').value;
  const url = `/api/reports/export.csv?range=${range}`;
  fetch(url, { headers: { 'Authorization': 'Bearer ' + TOKEN } })
    .then(r => r.blob())
    .then(blob => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'sales_export.csv';
      a.click();
    });
}

// ---- Audit ----
async function loadAuditLog() {
  const data = await api('/api/audit-log');
  document.getElementById('audit-table-body').innerHTML = data.log.map(l => `<tr class="border-b"><td class="p-3">${l.created_at}</td><td class="p-3">${l.username}</td><td class="p-3">${l.action}</td><td class="p-3 text-gray-500">${l.details || ''}</td></tr>`).join('');
}

// ---- Backup ----
function downloadBackup() {
  fetch('/api/backup', { headers: { 'Authorization': 'Bearer ' + TOKEN } })
    .then(r => r.blob())
    .then(blob => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'pos_backup.db';
      a.click();
    });
}

// ---- Settings (change system name + receipt info) ----
function loadSettingsForm() {
  document.getElementById('settings-system-name').value = SETTINGS.system_name || '';
  document.getElementById('settings-store-address').value = SETTINGS.store_address || '';
  document.getElementById('settings-store-contact').value = SETTINGS.store_contact || '';
  document.getElementById('settings-receipt-footer').value = SETTINGS.receipt_footer || '';
}
document.getElementById('settings-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    system_name: document.getElementById('settings-system-name').value.trim(),
    store_address: document.getElementById('settings-store-address').value.trim(),
    store_contact: document.getElementById('settings-store-contact').value.trim(),
    receipt_footer: document.getElementById('settings-receipt-footer').value.trim(),
  };
  const statusEl = document.getElementById('settings-status');
  try {
    await api('/api/settings', { method: 'PUT', body: JSON.stringify(payload) });
    await loadSettings(); // refresh cached SETTINGS + apply to header/title everywhere
    statusEl.textContent = 'Saved.';
    statusEl.className = 'text-sm text-emerald-600';
  } catch (err) {
    statusEl.textContent = err.message;
    statusEl.className = 'text-sm text-red-600';
  }
});
