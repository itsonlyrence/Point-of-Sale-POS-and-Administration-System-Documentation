// ============================================================
// scanner.js - camera-based barcode scanning
//
// A real USB/handheld barcode scanner needs no special code here: it
// acts like a keyboard, "typing" the barcode into #barcode-input and
// sending Enter, which processBarcodeSearch() (cashier.js) already
// handles. This file only adds the *optional* fallback of scanning
// with a webcam, using the html5-qrcode library loaded in index.html.
// ============================================================

let html5QrScanner = null;
let scannerRunning = false;

async function openScanner() {
  document.getElementById('scanner-modal').classList.remove('hidden');
  const statusEl = document.getElementById('scanner-status');
  statusEl.textContent = 'Starting camera...';
  statusEl.className = 'text-sm text-gray-500 text-center mt-2';

  if (typeof Html5Qrcode === 'undefined') {
    statusEl.textContent = 'Camera scanner library failed to load (no internet access?). Use the text field or a USB scanner instead.';
    statusEl.className = 'text-sm text-red-600 text-center mt-2';
    return;
  }

  try {
    html5QrScanner = new Html5Qrcode('scanner-reader', {
      formatsToSupport: [
        Html5QrcodeSupportedFormats.EAN_13,
        Html5QrcodeSupportedFormats.EAN_8,
        Html5QrcodeSupportedFormats.UPC_A,
        Html5QrcodeSupportedFormats.UPC_E,
        Html5QrcodeSupportedFormats.CODE_128,
        Html5QrcodeSupportedFormats.CODE_39,
        Html5QrcodeSupportedFormats.QR_CODE,
      ],
      verbose: false,
    });
    await html5QrScanner.start(
      { facingMode: 'environment' },
      { fps: 12, qrbox: { width: 260, height: 160 } },
      onScanSuccess,
      () => {} // per-frame "not found yet" noise - ignore
    );
    scannerRunning = true;
    statusEl.textContent = 'Point the camera at a barcode.';
  } catch (err) {
    statusEl.textContent = 'Could not access the camera: ' + err.message + '. Check camera permissions.';
    statusEl.className = 'text-sm text-red-600 text-center mt-2';
  }
}

function onScanSuccess(decodedText) {
  const statusEl = document.getElementById('scanner-status');
  statusEl.textContent = 'Scanned: ' + decodedText;
  statusEl.className = 'text-sm text-emerald-600 font-semibold text-center mt-2';
  // Small beep so the cashier gets audible confirmation, same as a real scanner.
  playBeep();
  addToCart(decodedText.trim());
  closeScanner();
}

async function closeScanner() {
  document.getElementById('scanner-modal').classList.add('hidden');
  await stopScanner();
}

async function stopScanner() {
  if (html5QrScanner && scannerRunning) {
    try { await html5QrScanner.stop(); html5QrScanner.clear(); } catch (e) {}
  }
  scannerRunning = false;
  html5QrScanner = null;
}

function playBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.frequency.value = 1000;
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    osc.start();
    osc.stop(ctx.currentTime + 0.08);
  } catch (e) { /* audio not available - not critical */ }
}
