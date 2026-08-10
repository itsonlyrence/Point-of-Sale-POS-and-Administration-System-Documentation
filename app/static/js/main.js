// ============================================================
// main.js - app bootstrap
// ============================================================

(async function bootstrap() {
  await loadSettings();
  if (TOKEN && CURRENT_USER) { enterApp(); }
})();
