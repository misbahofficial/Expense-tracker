from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "spending.db")

# ── DB Setup ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            icon TEXT DEFAULT '📦'
        );

        INSERT OR IGNORE INTO categories (name, icon) VALUES
            ('Inventory / Stock',  '🛒'),
            ('Rent & Utilities',   '🏠'),
            ('Staff & Wages',      '👥'),
            ('Marketing & Ads',    '📣'),
            ('Equipment & Tools',  '🔧'),
            ('Packaging',          '📦'),
            ('Transport & Fuel',   '🚚'),
            ('Miscellaneous',      '💸');

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT    NOT NULL,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            description TEXT,
            amount      REAL    NOT NULL CHECK(amount > 0),
            payment_method TEXT DEFAULT 'Cash',
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER UNIQUE REFERENCES categories(id),
            monthly_limit REAL NOT NULL
        );
        """)

init_db()

# ── Helpers ─────────────────────────────────────────────────────────────────
def row_to_dict(row):
    return dict(row) if row else None

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

# Categories
@app.route("/api/categories")
def get_categories():
    with get_db() as db:
        rows = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/categories", methods=["POST"])
def add_category():
    data = request.json
    name = data.get("name", "").strip()
    icon = data.get("icon", "📦").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    try:
        with get_db() as db:
            db.execute("INSERT INTO categories (name, icon) VALUES (?, ?)", (name, icon))
        return jsonify({"message": "Category added"}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Category already exists"}), 409

# Expenses – Add
@app.route("/api/expenses", methods=["POST"])
def add_expense():
    data = request.json
    required = ["date", "category_id", "amount"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"{f} is required"}), 400
    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Amount must be a positive number"}), 400

    with get_db() as db:
        db.execute(
            """INSERT INTO expenses (date, category_id, description, amount, payment_method)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["date"],
                data["category_id"],
                data.get("description", ""),
                amount,
                data.get("payment_method", "Cash"),
            ),
        )
    return jsonify({"message": "Expense added"}), 201

# Expenses – List / Filter
@app.route("/api/expenses")
def get_expenses():
    start  = request.args.get("start")
    end    = request.args.get("end")
    cat_id = request.args.get("category_id")
    method = request.args.get("payment_method")
    limit  = int(request.args.get("limit", 200))

    query = """
        SELECT e.*, c.name AS category_name, c.icon AS category_icon
        FROM expenses e JOIN categories c ON e.category_id = c.id
        WHERE 1=1
    """
    params = []
    if start:
        query += " AND e.date >= ?"; params.append(start)
    if end:
        query += " AND e.date <= ?"; params.append(end)
    if cat_id:
        query += " AND e.category_id = ?"; params.append(cat_id)
    if method:
        query += " AND e.payment_method = ?"; params.append(method)

    query += " ORDER BY e.date DESC, e.id DESC LIMIT ?"
    params.append(limit)

    with get_db() as db:
        rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

# Expense – Delete
@app.route("/api/expenses/<int:eid>", methods=["DELETE"])
def delete_expense(eid):
    with get_db() as db:
        db.execute("DELETE FROM expenses WHERE id = ?", (eid,))
    return jsonify({"message": "Deleted"})

# Expense – Edit
@app.route("/api/expenses/<int:eid>", methods=["PUT"])
def edit_expense(eid):
    data = request.json
    try:
        amount = float(data["amount"])
    except (ValueError, TypeError, KeyError):
        return jsonify({"error": "Valid amount required"}), 400
    with get_db() as db:
        db.execute(
            """UPDATE expenses SET date=?, category_id=?, description=?,
               amount=?, payment_method=? WHERE id=?""",
            (data["date"], data["category_id"], data.get("description",""),
             amount, data.get("payment_method","Cash"), eid)
        )
    return jsonify({"message": "Updated"})

# Dashboard Summary
@app.route("/api/summary")
def summary():
    today      = datetime.today().strftime("%Y-%m-%d")
    month_start= datetime.today().replace(day=1).strftime("%Y-%m-%d")
    week_start = (datetime.today() - timedelta(days=datetime.today().weekday())).strftime("%Y-%m-%d")

    with get_db() as db:
        def total(start, end=today):
            row = db.execute(
                "SELECT COALESCE(SUM(amount),0) as t FROM expenses WHERE date BETWEEN ? AND ?",
                (start, end)
            ).fetchone()
            return row["t"]

        today_total  = total(today)
        week_total   = total(week_start)
        month_total  = total(month_start)

        # Category breakdown this month
        cat_rows = db.execute("""
            SELECT c.name, c.icon, COALESCE(SUM(e.amount),0) AS total
            FROM categories c
            LEFT JOIN expenses e ON e.category_id=c.id AND e.date BETWEEN ? AND ?
            GROUP BY c.id ORDER BY total DESC
        """, (month_start, today)).fetchall()

        # Daily trend last 30 days
        trend_rows = db.execute("""
            SELECT date, SUM(amount) AS total
            FROM expenses
            WHERE date >= ?
            GROUP BY date ORDER BY date
        """, ((datetime.today()-timedelta(days=29)).strftime("%Y-%m-%d"),)).fetchall()

        # Payment method split this month
        pay_rows = db.execute("""
            SELECT payment_method, SUM(amount) AS total
            FROM expenses WHERE date BETWEEN ? AND ?
            GROUP BY payment_method
        """, (month_start, today)).fetchall()

        # Top 5 biggest expenses this month
        top_rows = db.execute("""
            SELECT e.description, e.amount, e.date, c.name AS cat, c.icon
            FROM expenses e JOIN categories c ON e.category_id=c.id
            WHERE e.date BETWEEN ? AND ?
            ORDER BY e.amount DESC LIMIT 5
        """, (month_start, today)).fetchall()

    return jsonify({
        "today":   today_total,
        "week":    week_total,
        "month":   month_total,
        "categories": [dict(r) for r in cat_rows],
        "trend":   [dict(r) for r in trend_rows],
        "payment_split": [dict(r) for r in pay_rows],
        "top_expenses": [dict(r) for r in top_rows],
    })

# Budgets
@app.route("/api/budgets")
def get_budgets():
    month_start= datetime.today().replace(day=1).strftime("%Y-%m-%d")
    today      = datetime.today().strftime("%Y-%m-%d")
    with get_db() as db:
        rows = db.execute("""
            SELECT b.id, b.category_id, c.name, c.icon, b.monthly_limit,
                   COALESCE(SUM(e.amount),0) AS spent
            FROM budgets b
            JOIN categories c ON b.category_id=c.id
            LEFT JOIN expenses e ON e.category_id=b.category_id AND e.date BETWEEN ? AND ?
            GROUP BY b.id
        """, (month_start, today)).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/budgets", methods=["POST"])
def set_budget():
    data = request.json
    cat_id = data.get("category_id")
    limit  = data.get("monthly_limit")
    if not cat_id or not limit:
        return jsonify({"error": "category_id and monthly_limit required"}), 400
    with get_db() as db:
        db.execute("""INSERT INTO budgets (category_id, monthly_limit) VALUES (?,?)
                      ON CONFLICT(category_id) DO UPDATE SET monthly_limit=excluded.monthly_limit""",
                   (cat_id, float(limit)))
    return jsonify({"message": "Budget saved"}), 201

@app.route("/api/budgets/<int:bid>", methods=["DELETE"])
def delete_budget(bid):
    with get_db() as db:
        db.execute("DELETE FROM budgets WHERE id=?", (bid,))
    return jsonify({"message": "Deleted"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)