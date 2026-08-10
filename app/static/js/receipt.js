// ============================================================
// receipt.js - build and print a receipt (checkout + admin reprint)
// ============================================================

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/**
 * items: [{name, price, qty}]
 * sale: {receipt_no, subtotal, discount, total, cash_tendered, change, created_at?}
 * cashierName: string
 */
function buildReceiptHtml(sale, items, cashierName) {
  const when = sale.created_at ? new Date(sale.created_at.replace(' ', 'T')) : new Date();
  const dateStr = when.toLocaleString();
  const line = () => '<div class="receipt-divider"></div>';
  const row = (l, r) => `<div class="flex justify-between"><span>${l}</span><span>${r}</span></div>`;

  let itemsHtml = items.map(i => `
    <div class="mb-1">
      <div>${escapeHtml(i.name)}</div>
      <div class="flex justify-between text-xs">
        <span>${i.qty} x ${Number(i.price).toFixed(2)}</span>
        <span>${(i.qty * i.price).toFixed(2)}</span>
      </div>
    </div>`).join('');

  return `
    <div class="text-center">
      <div class="font-bold text-base">${escapeHtml(SETTINGS.system_name)}</div>
      ${SETTINGS.store_address ? `<div class="text-xs">${escapeHtml(SETTINGS.store_address)}</div>` : ''}
      ${SETTINGS.store_contact ? `<div class="text-xs">${escapeHtml(SETTINGS.store_contact)}</div>` : ''}
    </div>
    ${line()}
    ${row('Receipt #', sale.receipt_no)}
    ${row('Date', dateStr)}
    ${row('Cashier', cashierName || '-')}
    ${line()}
    ${itemsHtml}
    ${line()}
    ${row('Subtotal', (sale.subtotal ?? 0).toFixed(2))}
    ${row('Discount', (sale.discount ?? 0).toFixed(2))}
    <div class="flex justify-between font-bold text-sm"><span>TOTAL</span><span>${'\u20b1'}${(sale.total ?? 0).toFixed(2)}</span></div>
    ${sale.cash_tendered != null ? row('Cash', Number(sale.cash_tendered).toFixed(2)) : ''}
    ${sale.change != null ? row('Change', Number(sale.change).toFixed(2)) : ''}
    ${line()}
    <div class="text-center text-xs">${escapeHtml(SETTINGS.receipt_footer)}</div>
  `;
}

function showReceiptPreview(sale, items, cashierName) {
  document.getElementById('receipt-print-area').innerHTML = buildReceiptHtml(sale, items, cashierName);
  document.getElementById('receipt-preview-body').innerHTML = buildReceiptHtml(sale, items, cashierName);
  document.getElementById('receipt-modal').classList.remove('hidden');
}

function closeReceiptModal() {
  document.getElementById('receipt-modal').classList.add('hidden');
}

function printReceipt() {
  window.print();
}

// Reprint any past sale from the admin Sales tab using its saved line items.
async function reprintSale(id) {
  try {
    const data = await api(`/api/sales/${id}`);
    const items = data.items.map(i => ({ name: i.name_snapshot, price: i.price_snapshot, qty: i.qty }));
    const sale = {
      receipt_no: data.sale.receipt_no,
      subtotal: data.sale.subtotal,
      discount: data.sale.discount,
      total: data.sale.total,
      cash_tendered: data.sale.cash_tendered,
      change: data.sale.change_amount,
      created_at: data.sale.created_at,
    };
    showReceiptPreview(sale, items, data.sale.cashier_name);
  } catch (err) {
    alert(err.message);
  }
}
