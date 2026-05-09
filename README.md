# ShopLedger — Daily Spending Tracker

A full-stack Flask web app for retail shop daily expense tracking.

## Features
- 📊 **Dashboard** — Today / Week / Month KPIs, category bar chart, payment donut, 30-day trend sparkline, top expenses
- ➕ **Add Expense** — Date, category, amount, payment method, description
- 🕒 **History** — Filterable table (by date range, category, payment method) with edit & delete
- 🎯 **Budgets** — Set monthly limits per category with live progress bars (safe / warning / over)
- 🏷️ **Categories** — Add custom emoji-tagged expense categories
- 💾 **SQLite backend** — All data persisted in `spending.db`

## Quick Start

```bash
cd shop_tracker
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5000**

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/summary` | Dashboard KPIs & charts data |
| GET | `/api/expenses` | List expenses (filterable) |
| POST | `/api/expenses` | Add expense |
| PUT | `/api/expenses/<id>` | Edit expense |
| DELETE | `/api/expenses/<id>` | Delete expense |
| GET | `/api/categories` | List categories |
| POST | `/api/categories` | Add category |
| GET | `/api/budgets` | List budgets with spend |
| POST | `/api/budgets` | Set/update budget |
| DELETE | `/api/budgets/<id>` | Remove budget |

## Project Structure
```
shop_tracker/
├── app.py              # Flask backend
├── spending.db         # SQLite database (auto-created)
├── requirements.txt
└── templates/
    └── index.html      # Single-page frontend
```