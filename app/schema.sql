-- ============================================================
-- Aling Nena's Grocery POS & Admin System
-- Database schema (SQLite / standard SQL)
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    full_name     TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL CHECK (role IN ('admin', 'cashier')),
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT UNIQUE NOT NULL,
    contact TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode       TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    category_id   INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    supplier_id   INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
    price         REAL NOT NULL DEFAULT 0,
    cost          REAL NOT NULL DEFAULT 0,
    stock         INTEGER NOT NULL DEFAULT 0,
    reorder_level INTEGER NOT NULL DEFAULT 10,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sales (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no     TEXT UNIQUE NOT NULL,
    cashier_id     INTEGER REFERENCES users(id),
    subtotal       REAL NOT NULL DEFAULT 0,
    discount       REAL NOT NULL DEFAULT 0,
    total          REAL NOT NULL DEFAULT 0,
    cash_tendered  REAL NOT NULL DEFAULT 0,
    change_amount  REAL NOT NULL DEFAULT 0,
    voided         INTEGER NOT NULL DEFAULT 0,
    void_reason    TEXT DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sale_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id        INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id     INTEGER REFERENCES products(id),
    barcode        TEXT NOT NULL,
    name_snapshot  TEXT NOT NULL,
    price_snapshot REAL NOT NULL,
    qty            INTEGER NOT NULL,
    line_total     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_adjustments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    admin_id    INTEGER REFERENCES users(id),
    change_qty  INTEGER NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id),
    username    TEXT,
    action      TEXT NOT NULL,
    details     TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_stock_adj_product ON stock_adjustments(product_id);
