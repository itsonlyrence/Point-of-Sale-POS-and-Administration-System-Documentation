#!/usr/bin/env python3
"""
Aling Nena's Grocery POS & Admin System
----------------------------------------
Self-contained backend server.

* Uses only the Python standard library (sqlite3, http.server, hashlib,
  secrets, json) -- nothing to "pip install", nothing that needs internet
  access to run on a store PC.
* Talks to a real SQL database (SQLite) stored in data/pos.db, created
  automatically from schema.sql the first time the server starts.
* Serves the front-end (static/index.html) and a JSON REST API on the
  same port, so a browser pointed at http://localhost:8080 (or the
  PC's LAN IP, for other terminals) is the whole application.

Run:
    python server.py            (defaults to port 8080)
    python server.py 9000        (custom port)

Default accounts (created on first run, change immediately in Admin > Users):
    admin / admin123     (role: admin)
    cashier / cashier123  (role: cashier)
"""

import sqlite3
import hashlib
import secrets
import json
import csv
import io
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "pos.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
STATIC_DIR = os.path.join(BASE_DIR, "static")

WRITE_LOCK = threading.Lock()          # serializes writes across threads
SESSIONS = {}                          # token -> {user_id, username, role, full_name, expires}
SESSION_LIFETIME_SECONDS = 12 * 3600   # 12-hour shift

DEFAULT_SETTINGS = {
    "system_name": "POS System",
    "store_address": "",
    "store_contact": "",
    "receipt_footer": "Thank you for shopping with us!",
}


# ----------------------------------------------------------------------
# Database helpers
# ----------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return digest, salt


def verify_password(password, salt, expected_hash):
    digest, _ = hash_password(password, salt)
    return secrets.compare_digest(digest, expected_hash)


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    fresh = not os.path.exists(DB_PATH)
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    # Make sure every default setting key exists, even on a DB that was
    # created before the settings table existed (upgrade-safe).
    cur = conn.cursor()
    for key, value in DEFAULT_SETTINGS.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()

    if fresh:
        print("[setup] New database detected - seeding default accounts and sample catalog ...")
        cur = conn.cursor()

        for username, pwd, full_name, role in [
            ("admin", "admin123", "Store Administrator", "admin"),
            ("cashier", "cashier123", "Juan Dela Cruz", "cashier"),
        ]:
            digest, salt = hash_password(pwd)
            cur.execute(
                "INSERT INTO users (username, password_hash, password_salt, full_name, role) VALUES (?,?,?,?,?)",
                (username, digest, salt, full_name, role),
            )

        cur.execute("INSERT INTO categories (name) VALUES ('Canned Goods')")
        cur.execute("INSERT INTO categories (name) VALUES ('Noodles & Pasta')")
        cur.execute("INSERT INTO categories (name) VALUES ('Dairy')")
        cur.execute("INSERT INTO categories (name) VALUES ('Condiments')")
        cat_ids = {r["name"]: r["id"] for r in cur.execute("SELECT id, name FROM categories")}

        sample_products = [
            ("1001", "Bear Brand Milk 33g", "Dairy", 14.50, 10.00, 50),
            ("1002", "San Marino Tuna 155g", "Canned Goods", 38.00, 29.00, 30),
            ("1003", "Silver Swan Soy Sauce 340ml", "Condiments", 24.00, 18.00, 25),
            ("1004", "Lucky Me Pancit Canton Kalamansi", "Noodles & Pasta", 16.50, 12.00, 100),
            ("1005", "CDO Carne Norte 100g", "Canned Goods", 32.00, 24.00, 15),
            ("1006", "Great Taste White Twin Pack", "Condiments", 12.00, 8.50, 80),
        ]
        for barcode, name, cat, price, cost, stock in sample_products:
            cur.execute(
                "INSERT INTO products (barcode, name, category_id, price, cost, stock, reorder_level) "
                "VALUES (?,?,?,?,?,?,10)",
                (barcode, name, cat_ids[cat], price, cost, stock),
            )

        conn.commit()
        print("[setup] Done. Default login -> admin/admin123 and cashier/cashier123")
    conn.close()


def log_audit(user, action, details=""):
    """`user` may be a session dict (has 'user_id') or a sqlite3.Row from the
    users table (has 'id') -- both are used as call sites, so accept either."""
    uid = None
    uname = "system"
    if user is not None:
        keys = user.keys()
        uid = user["user_id"] if "user_id" in keys else user["id"] if "id" in keys else None
        uname = user["username"] if "username" in keys else "system"
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log (user_id, username, action, details) VALUES (?,?,?,?)",
        (uid, uname, action, details),
    )
    conn.commit()
    conn.close()


def range_to_since(range_key):
    now = datetime.now()
    if range_key == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_key == "week":
        start = now - timedelta(days=7)
    elif range_key == "month":
        start = now - timedelta(days=30)
    else:
        return None
    return start.strftime("%Y-%m-%d %H:%M:%S")


# ----------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------

def new_session(user_row):
    token = secrets.token_hex(24)
    SESSIONS[token] = {
        "user_id": user_row["id"],
        "username": user_row["username"],
        "role": user_row["role"],
        "full_name": user_row["full_name"],
        "expires": time.time() + SESSION_LIFETIME_SECONDS,
    }
    return token


def session_for_token(token):
    s = SESSIONS.get(token)
    if not s:
        return None
    if s["expires"] < time.time():
        SESSIONS.pop(token, None)
        return None
    return s


# ----------------------------------------------------------------------
# HTTP handler
# ----------------------------------------------------------------------

ROUTES = []  # (method, compiled_regex, handler, required_role_or_None)


def route(method, pattern, role=None):
    regex = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, regex, fn, role))
        return fn

    return deco


class Ctx:
    def __init__(self, handler, params, query, body, user):
        self.h = handler
        self.params = params
        self.query = query
        self.body = body or {}
        self.user = user


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


# ---- Auth routes -------------------------------------------------------

@route("POST", r"/api/login")
def login(ctx):
    username = (ctx.body.get("username") or "").strip().lower()
    password = ctx.body.get("password") or ""
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not row or not row["active"]:
        raise ApiError(401, "Invalid username or password.")
    if not verify_password(password, row["password_salt"], row["password_hash"]):
        raise ApiError(401, "Invalid username or password.")
    token = new_session(row)
    log_audit(row, "login")
    return {
        "token": token,
        "user": {"id": row["id"], "username": row["username"], "role": row["role"], "full_name": row["full_name"]},
    }


@route("POST", r"/api/logout")
def logout(ctx):
    auth = ctx.h.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    SESSIONS.pop(token, None)
    return {"ok": True}


@route("GET", r"/api/me")
def me(ctx):
    if not ctx.user:
        raise ApiError(401, "Not signed in.")
    return {"user": ctx.user}


# ---- Settings (system name / receipt info) --------------------------------

@route("GET", r"/api/settings")
def get_settings(ctx):
    """Public on purpose: the login screen needs the system name before
    anyone has signed in."""
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    settings = dict(DEFAULT_SETTINGS)
    settings.update({r["key"]: r["value"] for r in rows})
    return {"settings": settings}


@route("PUT", r"/api/settings", role="admin")
def update_settings(ctx):
    b = ctx.body
    allowed = ("system_name", "store_address", "store_contact", "receipt_footer")
    changed = {}
    conn = get_conn()
    with WRITE_LOCK:
        for key in allowed:
            if key not in b:
                continue
            value = (b.get(key) or "").strip()
            if key == "system_name" and not value:
                conn.close()
                raise ApiError(400, "System name cannot be empty.")
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            changed[key] = value
        conn.commit()
    conn.close()
    log_audit(ctx.user, "update_settings", json.dumps(changed))
    return {"ok": True}


# ---- Products ------------------------------------------------------------

@route("GET", r"/api/products")
def list_products(ctx):
    conn = get_conn()
    show_all = ctx.query.get("all", ["0"])[0] == "1"
    if show_all and ctx.user and ctx.user["role"] == "admin":
        rows = conn.execute(
            "SELECT p.*, c.name AS category_name FROM products p "
            "LEFT JOIN categories c ON c.id = p.category_id ORDER BY p.name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, c.name AS category_name FROM products p "
            "LEFT JOIN categories c ON c.id = p.category_id WHERE p.active = 1 ORDER BY p.name"
        ).fetchall()
    conn.close()
    return {"products": [dict(r) for r in rows]}


@route("POST", r"/api/products", role="admin")
def create_product(ctx):
    b = ctx.body
    required = ["barcode", "name", "price", "stock"]
    for f in required:
        if b.get(f) in (None, ""):
            raise ApiError(400, f"Missing field: {f}")
    conn = get_conn()
    with WRITE_LOCK:
        existing = conn.execute("SELECT id FROM products WHERE barcode = ?", (b["barcode"],)).fetchone()
        if existing:
            conn.close()
            raise ApiError(409, "Barcode already exists.")
        conn.execute(
            "INSERT INTO products (barcode, name, category_id, supplier_id, price, cost, stock, reorder_level) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                b["barcode"], b["name"], b.get("category_id"), b.get("supplier_id"),
                float(b["price"]), float(b.get("cost", 0)), int(b["stock"]), int(b.get("reorder_level", 10)),
            ),
        )
        conn.commit()
    conn.close()
    log_audit(ctx.user, "create_product", f"barcode={b['barcode']} name={b['name']}")
    return {"ok": True}


@route("PUT", r"/api/products/(?P<id>\d+)", role="admin")
def update_product(ctx):
    pid = ctx.params["id"]
    b = ctx.body
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not row:
        conn.close()
        raise ApiError(404, "Product not found.")
    with WRITE_LOCK:
        conn.execute(
            "UPDATE products SET name=?, category_id=?, supplier_id=?, price=?, cost=?, reorder_level=?, "
            "updated_at=datetime('now') WHERE id=?",
            (
                b.get("name", row["name"]),
                b.get("category_id", row["category_id"]),
                b.get("supplier_id", row["supplier_id"]),
                float(b.get("price", row["price"])),
                float(b.get("cost", row["cost"])),
                int(b.get("reorder_level", row["reorder_level"])),
                pid,
            ),
        )
        conn.commit()
    conn.close()
    log_audit(ctx.user, "update_product", f"id={pid}")
    return {"ok": True}


@route("DELETE", r"/api/products/(?P<id>\d+)", role="admin")
def archive_product(ctx):
    pid = ctx.params["id"]
    conn = get_conn()
    with WRITE_LOCK:
        conn.execute("UPDATE products SET active = 0 WHERE id = ?", (pid,))
        conn.commit()
    conn.close()
    log_audit(ctx.user, "archive_product", f"id={pid}")
    return {"ok": True}


@route("POST", r"/api/products/(?P<id>\d+)/restore", role="admin")
def restore_product(ctx):
    pid = ctx.params["id"]
    conn = get_conn()
    with WRITE_LOCK:
        conn.execute("UPDATE products SET active = 1 WHERE id = ?", (pid,))
        conn.commit()
    conn.close()
    log_audit(ctx.user, "restore_product", f"id={pid}")
    return {"ok": True}


@route("POST", r"/api/products/(?P<id>\d+)/adjust-stock", role="admin")
def adjust_stock(ctx):
    pid = ctx.params["id"]
    change = ctx.body.get("change_qty")
    reason = (ctx.body.get("reason") or "").strip()
    if change is None:
        raise ApiError(400, "change_qty is required.")
    change = int(change)
    conn = get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    if not row:
        conn.close()
        raise ApiError(404, "Product not found.")
    new_stock = row["stock"] + change
    if new_stock < 0:
        conn.close()
        raise ApiError(400, "Resulting stock cannot be negative.")
    with WRITE_LOCK:
        conn.execute("UPDATE products SET stock = ?, updated_at = datetime('now') WHERE id = ?", (new_stock, pid))
        conn.execute(
            "INSERT INTO stock_adjustments (product_id, admin_id, change_qty, reason) VALUES (?,?,?,?)",
            (pid, ctx.user["user_id"], change, reason),
        )
        conn.commit()
    conn.close()
    log_audit(ctx.user, "adjust_stock", f"product_id={pid} change={change} reason={reason}")
    return {"ok": True, "new_stock": new_stock}


@route("GET", r"/api/low-stock")
def low_stock(ctx):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM products WHERE active = 1 AND stock <= reorder_level ORDER BY stock ASC"
    ).fetchall()
    conn.close()
    return {"products": [dict(r) for r in rows]}


# ---- Categories & suppliers ----------------------------------------------

@route("GET", r"/api/categories")
def list_categories(ctx):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return {"categories": [dict(r) for r in rows]}


@route("POST", r"/api/categories", role="admin")
def create_category(ctx):
    name = (ctx.body.get("name") or "").strip()
    if not name:
        raise ApiError(400, "Name is required.")
    conn = get_conn()
    with WRITE_LOCK:
        try:
            conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise ApiError(409, "Category already exists.")
    conn.close()
    log_audit(ctx.user, "create_category", name)
    return {"ok": True}


@route("DELETE", r"/api/categories/(?P<id>\d+)", role="admin")
def delete_category(ctx):
    cid = ctx.params["id"]
    conn = get_conn()
    with WRITE_LOCK:
        conn.execute("UPDATE products SET category_id = NULL WHERE category_id = ?", (cid,))
        conn.execute("DELETE FROM categories WHERE id = ?", (cid,))
        conn.commit()
    conn.close()
    log_audit(ctx.user, "delete_category", f"id={cid}")
    return {"ok": True}


@route("GET", r"/api/suppliers")
def list_suppliers(ctx):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return {"suppliers": [dict(r) for r in rows]}


@route("POST", r"/api/suppliers", role="admin")
def create_supplier(ctx):
    name = (ctx.body.get("name") or "").strip()
    contact = (ctx.body.get("contact") or "").strip()
    if not name:
        raise ApiError(400, "Name is required.")
    conn = get_conn()
    with WRITE_LOCK:
        try:
            conn.execute("INSERT INTO suppliers (name, contact) VALUES (?,?)", (name, contact))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise ApiError(409, "Supplier already exists.")
    conn.close()
    log_audit(ctx.user, "create_supplier", name)
    return {"ok": True}


@route("DELETE", r"/api/suppliers/(?P<id>\d+)", role="admin")
def delete_supplier(ctx):
    sid = ctx.params["id"]
    conn = get_conn()
    with WRITE_LOCK:
        conn.execute("UPDATE products SET supplier_id = NULL WHERE supplier_id = ?", (sid,))
        conn.execute("DELETE FROM suppliers WHERE id = ?", (sid,))
        conn.commit()
    conn.close()
    log_audit(ctx.user, "delete_supplier", f"id={sid}")
    return {"ok": True}


# ---- Users (admin) ---------------------------------------------------------

@route("GET", r"/api/users", role="admin")
def list_users(ctx):
    conn = get_conn()
    rows = conn.execute("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY username").fetchall()
    conn.close()
    return {"users": [dict(r) for r in rows]}


@route("POST", r"/api/users", role="admin")
def create_user(ctx):
    b = ctx.body
    username = (b.get("username") or "").strip().lower()
    password = b.get("password") or ""
    full_name = (b.get("full_name") or "").strip()
    role = b.get("role")
    if not username or not password or role not in ("admin", "cashier"):
        raise ApiError(400, "username, password and a valid role are required.")
    if len(password) < 4:
        raise ApiError(400, "Password must be at least 4 characters.")
    digest, salt = hash_password(password)
    conn = get_conn()
    with WRITE_LOCK:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, password_salt, full_name, role) VALUES (?,?,?,?,?)",
                (username, digest, salt, full_name, role),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise ApiError(409, "Username already exists.")
    conn.close()
    log_audit(ctx.user, "create_user", f"username={username} role={role}")
    return {"ok": True}


@route("PUT", r"/api/users/(?P<id>\d+)", role="admin")
def update_user(ctx):
    uid = ctx.params["id"]
    b = ctx.body
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not row:
        conn.close()
        raise ApiError(404, "User not found.")
    updates = {
        "full_name": b.get("full_name", row["full_name"]),
        "role": b.get("role", row["role"]),
        "active": int(b.get("active", row["active"])),
    }
    with WRITE_LOCK:
        conn.execute(
            "UPDATE users SET full_name=?, role=?, active=? WHERE id=?",
            (updates["full_name"], updates["role"], updates["active"], uid),
        )
        if b.get("password"):
            digest, salt = hash_password(b["password"])
            conn.execute("UPDATE users SET password_hash=?, password_salt=? WHERE id=?", (digest, salt, uid))
        conn.commit()
    conn.close()
    log_audit(ctx.user, "update_user", f"id={uid}")
    return {"ok": True}


@route("DELETE", r"/api/users/(?P<id>\d+)", role="admin")
def delete_user(ctx):
    uid = ctx.params["id"]
    if str(ctx.user["user_id"]) == uid:
        raise ApiError(400, "You cannot delete your own account while signed in.")
    conn = get_conn()
    admins_left = conn.execute("SELECT COUNT(*) c FROM users WHERE role='admin' AND active=1").fetchone()["c"]
    target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if target and target["role"] == "admin" and admins_left <= 1:
        conn.close()
        raise ApiError(400, "Cannot delete the last remaining admin account.")
    with WRITE_LOCK:
        conn.execute("UPDATE users SET active = 0 WHERE id = ?", (uid,))
        conn.commit()
    conn.close()
    log_audit(ctx.user, "deactivate_user", f"id={uid}")
    return {"ok": True}


# ---- Sales / checkout -------------------------------------------------------

@route("POST", r"/api/sales")
def checkout(ctx):
    if not ctx.user:
        raise ApiError(401, "Not signed in.")
    items = ctx.body.get("items") or []
    discount = float(ctx.body.get("discount") or 0)
    cash_tendered = float(ctx.body.get("cash_tendered") or 0)
    if not items:
        raise ApiError(400, "Cart is empty.")

    conn = get_conn()
    with WRITE_LOCK:
        try:
            subtotal = 0.0
            line_data = []
            for it in items:
                barcode = it.get("barcode")
                qty = int(it.get("qty", 0))
                if qty <= 0:
                    raise ApiError(400, f"Invalid quantity for {barcode}.")
                prod = conn.execute("SELECT * FROM products WHERE barcode = ? AND active = 1", (barcode,)).fetchone()
                if not prod:
                    raise ApiError(404, f"Product not found: {barcode}")
                if prod["stock"] < qty:
                    raise ApiError(400, f"Insufficient stock for {prod['name']} (have {prod['stock']}).")
                line_total = round(prod["price"] * qty, 2)
                subtotal += line_total
                line_data.append((prod, qty, line_total))

            total = max(0.0, round(subtotal - discount, 2))
            if cash_tendered < total:
                raise ApiError(400, "Cash tendered is less than the total amount.")
            change = round(cash_tendered - total, 2)
            receipt_no = datetime.now().strftime("%Y%m%d%H%M%S") + secrets.token_hex(2).upper()

            cur = conn.execute(
                "INSERT INTO sales (receipt_no, cashier_id, subtotal, discount, total, cash_tendered, change_amount) "
                "VALUES (?,?,?,?,?,?,?)",
                (receipt_no, ctx.user["user_id"], round(subtotal, 2), discount, total, cash_tendered, change),
            )
            sale_id = cur.lastrowid

            for prod, qty, line_total in line_data:
                conn.execute(
                    "INSERT INTO sale_items (sale_id, product_id, barcode, name_snapshot, price_snapshot, qty, line_total) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (sale_id, prod["id"], prod["barcode"], prod["name"], prod["price"], qty, line_total),
                )
                conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, prod["id"]))

            conn.commit()
        except ApiError:
            conn.rollback()
            conn.close()
            raise
        except Exception as e:
            conn.rollback()
            conn.close()
            raise ApiError(500, f"Checkout failed: {e}")
    conn.close()
    log_audit(ctx.user, "checkout", f"receipt={receipt_no} total={total}")
    return {
        "ok": True,
        "receipt_no": receipt_no,
        "sale_id": sale_id,
        "subtotal": round(subtotal, 2),
        "discount": discount,
        "total": total,
        "cash_tendered": cash_tendered,
        "change": change,
    }


@route("GET", r"/api/sales")
def list_sales(ctx):
    if not ctx.user:
        raise ApiError(401, "Not signed in.")
    conn = get_conn()
    q = "SELECT s.*, u.username AS cashier_name FROM sales s LEFT JOIN users u ON u.id = s.cashier_id WHERE 1=1"
    args = []
    since = range_to_since(ctx.query.get("range", [""])[0])
    if since:
        q += " AND s.created_at >= ?"
        args.append(since)
    if ctx.query.get("cashier_id"):
        q += " AND s.cashier_id = ?"
        args.append(ctx.query["cashier_id"][0])
    if ctx.user["role"] != "admin":
        q += " AND s.cashier_id = ?"
        args.append(ctx.user["user_id"])
    q += " ORDER BY s.created_at DESC LIMIT 500"
    rows = conn.execute(q, args).fetchall()
    conn.close()
    return {"sales": [dict(r) for r in rows]}


@route("GET", r"/api/sales/(?P<id>\d+)")
def get_sale(ctx):
    if not ctx.user:
        raise ApiError(401, "Not signed in.")
    conn = get_conn()
    sale = conn.execute("SELECT s.*, u.username AS cashier_name FROM sales s LEFT JOIN users u ON u.id=s.cashier_id WHERE s.id=?", (ctx.params["id"],)).fetchone()
    if not sale:
        conn.close()
        raise ApiError(404, "Sale not found.")
    items = conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (ctx.params["id"],)).fetchall()
    conn.close()
    return {"sale": dict(sale), "items": [dict(i) for i in items]}


@route("POST", r"/api/sales/(?P<id>\d+)/void", role="admin")
def void_sale(ctx):
    sid = ctx.params["id"]
    reason = (ctx.body.get("reason") or "").strip()
    conn = get_conn()
    sale = conn.execute("SELECT * FROM sales WHERE id = ?", (sid,)).fetchone()
    if not sale:
        conn.close()
        raise ApiError(404, "Sale not found.")
    if sale["voided"]:
        conn.close()
        raise ApiError(400, "Sale already voided.")
    items = conn.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sid,)).fetchall()
    with WRITE_LOCK:
        for it in items:
            if it["product_id"]:
                conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (it["qty"], it["product_id"]))
        conn.execute("UPDATE sales SET voided = 1, void_reason = ? WHERE id = ?", (reason, sid))
        conn.commit()
    conn.close()
    log_audit(ctx.user, "void_sale", f"id={sid} reason={reason}")
    return {"ok": True}


# ---- Reports ----------------------------------------------------------------

@route("GET", r"/api/reports/summary")
def report_summary(ctx):
    if not ctx.user:
        raise ApiError(401, "Not signed in.")
    since = range_to_since(ctx.query.get("range", ["today"])[0])
    conn = get_conn()
    q = "SELECT COALESCE(SUM(total),0) rev, COUNT(*) tx FROM sales WHERE voided = 0"
    args = []
    if since:
        q += " AND created_at >= ?"
        args.append(since)
    row = conn.execute(q, args).fetchone()

    q2 = "SELECT COALESCE(SUM(si.qty),0) items FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE s.voided = 0"
    if since:
        q2 += " AND s.created_at >= ?"
    items_sold = conn.execute(q2, args).fetchone()["items"]

    low_stock_count = conn.execute("SELECT COUNT(*) c FROM products WHERE active=1 AND stock <= reorder_level").fetchone()["c"]
    conn.close()
    return {
        "revenue": round(row["rev"], 2),
        "transactions": row["tx"],
        "items_sold": items_sold,
        "low_stock_count": low_stock_count,
    }


@route("GET", r"/api/reports/top-products")
def report_top_products(ctx):
    if not ctx.user:
        raise ApiError(401, "Not signed in.")
    since = range_to_since(ctx.query.get("range", ["month"])[0])
    limit = int(ctx.query.get("limit", ["10"])[0])
    conn = get_conn()
    q = (
        "SELECT si.barcode, si.name_snapshot AS name, SUM(si.qty) AS qty_sold, SUM(si.line_total) AS revenue "
        "FROM sale_items si JOIN sales s ON s.id = si.sale_id WHERE s.voided = 0"
    )
    args = []
    if since:
        q += " AND s.created_at >= ?"
        args.append(since)
    q += " GROUP BY si.barcode, si.name_snapshot ORDER BY qty_sold DESC LIMIT ?"
    args.append(limit)
    rows = conn.execute(q, args).fetchall()
    conn.close()
    return {"products": [dict(r) for r in rows]}


@route("GET", r"/api/reports/by-cashier")
def report_by_cashier(ctx):
    if not ctx.user:
        raise ApiError(401, "Not signed in.")
    since = range_to_since(ctx.query.get("range", ["month"])[0])
    conn = get_conn()
    q = (
        "SELECT u.username, COUNT(*) tx, COALESCE(SUM(s.total),0) revenue "
        "FROM sales s JOIN users u ON u.id = s.cashier_id WHERE s.voided = 0"
    )
    args = []
    if since:
        q += " AND s.created_at >= ?"
        args.append(since)
    q += " GROUP BY u.username ORDER BY revenue DESC"
    rows = conn.execute(q, args).fetchall()
    conn.close()
    return {"cashiers": [dict(r) for r in rows]}


@route("GET", r"/api/reports/export.csv", role="admin")
def export_csv(ctx):
    since = range_to_since(ctx.query.get("range", ["month"])[0])
    conn = get_conn()
    q = "SELECT s.receipt_no, s.created_at, u.username AS cashier, s.subtotal, s.discount, s.total, s.voided FROM sales s LEFT JOIN users u ON u.id=s.cashier_id WHERE 1=1"
    args = []
    if since:
        q += " AND s.created_at >= ?"
        args.append(since)
    q += " ORDER BY s.created_at DESC"
    rows = conn.execute(q, args).fetchall()
    conn.close()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Receipt No", "Date", "Cashier", "Subtotal", "Discount", "Total", "Voided"])
    for r in rows:
        writer.writerow([r["receipt_no"], r["created_at"], r["cashier"], r["subtotal"], r["discount"], r["total"], "Yes" if r["voided"] else "No"])
    return ("text/csv", buf.getvalue().encode("utf-8"), "sales_export.csv")


# ---- Audit log & backup (admin) ---------------------------------------------

@route("GET", r"/api/audit-log", role="admin")
def audit_log_view(ctx):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 300").fetchall()
    conn.close()
    return {"log": [dict(r) for r in rows]}


@route("GET", r"/api/backup", role="admin")
def backup_db(ctx):
    with open(DB_PATH, "rb") as f:
        data = f.read()
    log_audit(ctx.user, "backup_download")
    fname = "pos_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
    return ("application/octet-stream", data, fname)


# ----------------------------------------------------------------------
# HTTP plumbing
# ----------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "GroceryPOS/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _current_user(self):
        auth = self.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        return session_for_token(token)

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file_bytes(self, content_type, data, filename=None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"
        safe_path = os.path.normpath(path).lstrip("/\\")
        full_path = os.path.join(STATIC_DIR, safe_path)
        if not full_path.startswith(STATIC_DIR) or not os.path.isfile(full_path):
            self._send_json(404, {"error": "Not found"})
            return
        ext = os.path.splitext(full_path)[1].lower()
        ctype = {
            ".html": "text/html", ".js": "application/javascript", ".css": "text/css",
            ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if not path.startswith("/api/"):
            if method == "GET":
                self._serve_static(path)
            else:
                self._send_json(404, {"error": "Not found"})
            return

        body = {}
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
            except Exception:
                body = {}

        for r_method, regex, fn, role in ROUTES:
            if r_method != method:
                continue
            m = regex.match(path)
            if not m:
                continue
            user = self._current_user()
            if role and (not user or user["role"] != role):
                self._send_json(403 if user else 401, {"error": "Admin access required." if user else "Not signed in."})
                return
            ctx = Ctx(self, m.groupdict(), query, body, user)
            try:
                result = fn(ctx)
            except ApiError as e:
                self._send_json(e.status, {"error": e.message})
                return
            except Exception as e:
                self._send_json(500, {"error": f"Server error: {e}"})
                return
            if isinstance(result, tuple):
                ctype, data, fname = result
                self._send_file_bytes(ctype, data, fname)
            else:
                self._send_json(200, result)
            return

        self._send_json(404, {"error": "Unknown API route."})

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"[server] Grocery POS running -> http://localhost:{port}")
    print(f"[server] Database file       -> {DB_PATH}")
    print("[server] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Stopped.")


if __name__ == "__main__":
    main()
