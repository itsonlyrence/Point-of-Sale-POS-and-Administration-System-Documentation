// ============================================================
// cashier.js - product grid, cart, checkout
// ============================================================

let products = [];
let cart = [];

async function initCashierUI() {
  await loadProducts();
  renderProductGrid();
  renderCart();
  document.getElementById('barcode-input').focus();
}

async function loadProducts() {
  const showArchived = document.getElementById('show-archived');
  const all = showArchived && showArchived.checked ? '?all=1' : '';
  const data = await api('/api/products' + all);
  products = data.products;
  if (document.getElementById('admin-ui') && !document.getElementById('admin-ui').classList.contains('hidden')) {
    renderInventoryTable();
  }
  if (document.getElementById('cashier-ui') && !document.getElementById('cashier-ui').classList.contains('hidden')) {
    renderProductGrid();
  }
}

function renderProductGrid() {
  const grid = document.getElementById('product-grid');
  grid.innerHTML = '';
  products.filter(p => p.active).forEach(p => {
    grid.innerHTML += `
      <div onclick="addToCart('${p.barcode}')" class="border rounded-lg p-3 flex flex-col justify-between cursor-pointer hover:border-emerald-500 hover:shadow transition bg-gray-50">
        <div><span class="text-xs text-gray-400">#${p.barcode}</span><h4 class="font-semibold text-sm text-gray-800 line-clamp-2">${p.name}</h4></div>
        <div class="mt-2 flex justify-between items-center">
          <span class="text-emerald-600 font-bold">\u20b1${p.price.toFixed(2)}</span>
          <span class="text-xs bg-gray-200 px-2 py-0.5 rounded text-gray-600">Stock: ${p.stock}</span>
        </div>
      </div>`;
  });
}

// ---- Barcode input (works with any USB / handheld scanner, since those
// simply "type" the code followed by Enter - no extra driver needed) ----
document.getElementById('barcode-input').addEventListener('keypress', (e) => { if (e.key === 'Enter') processBarcodeSearch(); });
function processBarcodeSearch() {
  const input = document.getElementById('barcode-input');
  const code = input.value.trim();
  if (!code) return;
  addToCart(code);
  input.value = ''; input.focus();
}

function addToCart(barcode) {
  const product = products.find(p => p.barcode === barcode && p.active);
  if (!product) { alert('Product barcode not found!'); return; }
  if (product.stock <= 0) { alert('Product is out of stock!'); return; }
  const item = cart.find(i => i.barcode === barcode);
  if (item) {
    if (item.qty < product.stock) item.qty++; else alert('Reached maximum available stock limit.');
  } else {
    cart.push({ barcode: product.barcode, name: product.name, price: product.price, qty: 1 });
  }
  renderCart();
}

function updateCartQty(barcode, change) {
  const item = cart.find(i => i.barcode === barcode);
  const product = products.find(p => p.barcode === barcode);
  if (!item) return;
  const newQty = item.qty + change;
  if (product && newQty > product.stock) { alert('Exceeds available stock!'); return; }
  if (newQty > 0) item.qty = newQty; else cart = cart.filter(i => i.barcode !== barcode);
  renderCart();
}

function renderCart() {
  const container = document.getElementById('cart-items');
  const discount = parseFloat(document.getElementById('cart-discount').value) || 0;
  if (cart.length === 0) {
    container.innerHTML = `<p class="text-gray-400 text-center py-8">Cart is empty</p>`;
    document.getElementById('cart-subtotal').innerText = '\u20b10.00';
    document.getElementById('cart-total').innerText = '\u20b10.00';
    calculateChange();
    return;
  }
  container.innerHTML = '';
  let subtotal = 0;
  cart.forEach(item => {
    subtotal += item.price * item.qty;
    container.innerHTML += `
      <div class="flex justify-between items-center border-b pb-2">
        <div><h5 class="text-sm font-semibold text-gray-800">${item.name}</h5><span class="text-xs text-gray-500">\u20b1${item.price.toFixed(2)} x ${item.qty}</span></div>
        <div class="flex items-center space-x-2">
          <button onclick="updateCartQty('${item.barcode}', -1)" class="bg-gray-200 px-2 py-0.5 rounded text-xs">-</button>
          <span class="text-sm font-bold">${item.qty}</span>
          <button onclick="updateCartQty('${item.barcode}', 1)" class="bg-gray-200 px-2 py-0.5 rounded text-xs">+</button>
        </div>
      </div>`;
  });
  const total = Math.max(0, subtotal - discount);
  document.getElementById('cart-subtotal').innerText = `\u20b1${subtotal.toFixed(2)}`;
  document.getElementById('cart-total').innerText = `\u20b1${total.toFixed(2)}`;
  calculateChange();
}

function calculateChange() {
  const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
  const discount = parseFloat(document.getElementById('cart-discount').value) || 0;
  const total = Math.max(0, subtotal - discount);
  const tendered = parseFloat(document.getElementById('cash-tendered').value) || 0;
  const change = tendered - total;
  const el = document.getElementById('cart-change');
  if (change >= 0) { el.innerText = `\u20b1${change.toFixed(2)}`; el.className = 'text-blue-600 font-bold'; }
  else { el.innerText = 'Insufficient Cash'; el.className = 'text-red-500 font-bold'; }
}

async function checkout() {
  if (cart.length === 0) { alert('Cart is empty.'); return; }
  const discount = parseFloat(document.getElementById('cart-discount').value) || 0;
  const cashTendered = parseFloat(document.getElementById('cash-tendered').value) || 0;
  // Snapshot the items for the receipt before the cart is cleared below.
  const soldItems = cart.map(i => ({ name: i.name, price: i.price, qty: i.qty }));
  try {
    const result = await api('/api/sales', {
      method: 'POST', body: JSON.stringify({
        items: cart.map(i => ({ barcode: i.barcode, qty: i.qty })), discount, cash_tendered: cashTendered,
      }),
    });
    cart = [];
    document.getElementById('cash-tendered').value = '';
    document.getElementById('cart-discount').value = '0';
    await loadProducts();
    renderCart();
    showReceiptPreview(result, soldItems, CURRENT_USER.full_name || CURRENT_USER.username);
  } catch (err) {
    alert(err.message);
  }
}
