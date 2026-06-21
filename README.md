# Spendly — Personal Expense Tracker

**Track every rupee. Own your finances.**

Spendly is a lightweight, beautiful personal expense tracker built with Flask and SQLite. Log expenses, understand your spending patterns, and take control of your financial life — one transaction at a time.

🔗 **Live Demo:** [https://expense-tracker-production-e077.up.railway.app](https://expense-tracker-production-e077.up.railway.app)

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Screenshots](#screenshots)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Running Locally](#running-locally)
  - [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [API Routes](#api-routes)
- [Deployment](#deployment)
- [License](#license)

---

## Features

- **User Authentication** — Register and log in with secure password hashing (Werkzeug). Session-based auth keeps your data private.
- **Expense CRUD** — Create, read, update, and delete expenses. Every field is validated server-side.
- **Dashboard** — View summary stats (total spent, transaction count, top category), a transaction history table, and a visual category breakdown — all in one place.
- **Date Filtering** — Filter expenses by preset ranges (This Month, Last 3 Months, Last 6 Months, All Time) or a custom date range. Filtering applies to summary stats, transactions, and category breakdown simultaneously.
- **Input Preservation** — When form validation fails, all valid fields retain their values so you never have to re-type everything.
- **Ownership Guards** — Users can only see and modify their own expenses. Attempting to access another user's expense returns a 404.
- **SQL Injection Protection** — All database queries use parameterized placeholders (`?`). Tested against injection attempts in every user-input field.
- **Responsive Design** — Clean, modern UI built with custom CSS (no frameworks). Works on desktop and mobile.
- **Indian Rupee (₹)** — All monetary values displayed in INR.

---

## Tech Stack

| Layer          | Technology                |
| -------------- | ------------------------- |
| Backend        | Python 3.10+, Flask 3.1   |
| Database       | SQLite 3 (via `sqlite3`)  |
| Auth           | Werkzeug password hashing |
| Frontend       | Jinja2 templates, vanilla CSS, vanilla JS |
| Testing        | pytest, pytest-flask      |
| Deployment     | Railway (Docker via Nixpacks) |

**Constraints:** No ORM (raw SQL only), no JS frameworks, no external CSS frameworks, no additional pip packages beyond `requirements.txt`.

---

## Architecture

```
spendly/
├── app.py                  # All Flask routes — single file, no blueprints
├── database/
│   ├── __init__.py
│   ├── db.py               # SQLite helpers: get_db(), init_db(), seed_db(), CRUD functions
│   └── queries.py          # Pure query helpers for the profile page (summary, transactions, breakdown)
├── templates/
│   ├── base.html           # Shared layout — navbar, footer, flash messages
│   ├── landing.html         # Marketing landing page with hero + feature cards
│   ├── register.html       # Registration form
│   ├── login.html           # Login form
│   ├── profile.html         # Dashboard — stats, date filter, transactions, category breakdown
│   ├── add_expense.html     # Add expense form
│   ├── edit_expense.html    # Edit expense form (pre-filled)
│   ├── analytics.html       # "Coming Soon" placeholder
│   ├── terms.html           # Terms and Conditions
│   └── privacy.html         # Privacy Policy
├── static/
│   ├── css/
│   │   ├── style.css        # Global styles, navbar, footer, auth pages, hero
│   │   ├── landing.css      # Landing-page overrides (centered hero, dashboard mock)
│   │   ├── profile.css      # Dashboard styles (filter bar, stats, table, breakdown)
│   │   ├── expenses.css     # Expense form overrides (minimal — inherits from style.css)
│   │   └── analytics.css    # Analytics "Coming Soon" page
│   └── js/
│       └── main.js          # Vanilla JS (placeholder for future features)
├── tests/
│   ├── test_backend_connection.py  # DB helper + profile route tests
│   ├── test_07_date_filter.py      # Date filter feature tests (19 test classes, ~90 tests)
│   ├── test_08-add-expense.py      # Add expense feature tests (11 test classes, ~50 tests)
│   ├── test_09-edit-expense.py     # Edit expense feature tests (15 test classes, ~70 tests)
│   └── test_10-delete-expense.py   # Delete expense feature tests (10 test classes, ~40 tests)
├── Procfile                 # Railway deployment: `web: python app.py`
├── requirements.txt         # flask, werkzeug, pytest, pytest-flask
├── CLAUDE.md                 # Project instructions and conventions
└── README.md                 # This file
```

**Design Principles:**
- **Single-file routes** — All route logic lives in `app.py`. No blueprints.
- **DB logic separation** — No SQL in route functions. All database access goes through `database/db.py` (CRUD) and `database/queries.py` (read-only queries).
- **Parameterized queries only** — Every SQL statement uses `?` placeholders. Zero string interpolation in queries.
- **One responsibility per route** — Routes fetch data, pass it to templates, and render. No business logic in route functions.

---

## Screenshots

### Landing Page
A polished marketing page with a hero section, feature cards, and a mock dashboard preview. Call-to-action buttons lead to registration and login.

### Dashboard (Profile)
The main hub after logging in. Shows:
- User info card with avatar, name, email, and "Member since" date
- Three summary stat cards: Total Spent (₹), Transactions, Top Category
- Date filter bar with preset buttons and custom date range form
- Transaction history table with category badges, Edit, and Delete actions
- Category breakdown with visual bar charts and percentages

### Add / Edit Expense
Clean forms with amount (₹), category dropdown (7 categories), date picker, and description. All fields validated server-side with clear error messages.

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Installation

```bash
# Clone the repository
git clone git@github.com:Anshul20052000/spendly-claude.git
cd spendly-claude

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running Locally

```bash
python app.py
```

The app will start on **http://localhost:5001** with a pre-seeded demo user:
- **Email:** `demo@spendly.com`
- **Password:** `demo123`

The database (`expense_tracker.db`) is created automatically on first run with 8 sample expenses spanning June 2026.

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_08-add-expense.py

# Run a specific test class
pytest tests/test_07_date_filter.py::TestThisMonthPreset

# Run tests with print output visible
pytest -s
```

The test suite uses isolated temporary databases for each test (via `tmp_path` fixtures and `monkeypatch`), so tests never interfere with each other or your local database.

---

## Database Schema

### `users` table

| Column        | Type      | Constraints                     |
| ------------- | --------- | ------------------------------- |
| `id`          | INTEGER   | PRIMARY KEY AUTOINCREMENT       |
| `name`        | TEXT      | NOT NULL                        |
| `email`       | TEXT      | UNIQUE, NOT NULL                |
| `password_hash` | TEXT    | NOT NULL                        |
| `created_at`  | TEXT      | NOT NULL DEFAULT (datetime('now')) |

### `expenses` table

| Column        | Type      | Constraints                     |
| ------------- | --------- | ------------------------------- |
| `id`          | INTEGER   | PRIMARY KEY AUTOINCREMENT       |
| `user_id`     | INTEGER   | NOT NULL, FK → users(id)        |
| `amount`      | REAL      | NOT NULL                        |
| `category`    | TEXT      | NOT NULL                        |
| `date`        | TEXT      | NOT NULL (YYYY-MM-DD format)    |
| `description` | TEXT     |                                 |
| `created_at`  | TEXT      | NOT NULL DEFAULT (datetime('now')) |

**Foreign key enforcement** is enabled on every connection via `PRAGMA foreign_keys = ON` in `get_db()`.

---

## API Routes

| Method | Route                    | Auth Required | Description                          |
| ------ | ------------------------ | ------------- | ------------------------------------ |
| GET    | `/`                      | No            | Landing page                         |
| GET/POST | `/register`            | No            | Registration form / create account   |
| GET/POST | `/login`               | No            | Login form / authenticate            |
| GET    | `/logout`                | Yes           | Log out and clear session            |
| GET    | `/profile`               | Yes           | Dashboard (with optional `?date_from=&date_to=` filters) |
| GET    | `/analytics`             | Yes           | Analytics placeholder                |
| GET/POST | `/expenses/add`        | Yes           | Add expense form / create expense    |
| GET/POST | `/expenses/<id>/edit`  | Yes           | Edit expense form / update expense   |
| POST   | `/expenses/<id>/delete`  | Yes           | Delete expense (POST only; GET returns 405) |
| GET    | `/terms`                 | No            | Terms and Conditions                 |
| GET    | `/privacy`               | No            | Privacy Policy                       |

**Validation rules:**
- **Amount:** Required, must be a valid positive number (> 0)
- **Category:** Required, must be one of: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- **Date:** Required, must be in `YYYY-MM-DD` format
- **Description:** Required, max 200 characters

---

## Deployment

Spendly is deployed on [Railway](https://railway.com) and is available at:

### 🌐 [https://expense-tracker-production-e077.up.railway.app](https://expense-tracker-production-e077.up.railway.app)

**Deployment details:**
- Auto-deploys from the `master` branch on GitHub
- Built using Railway's Nixpacks (auto-detects Python/Flask from `requirements.txt`)
- `Procfile` specifies the start command: `web: python app.py`
- The app binds to `0.0.0.0:$PORT` (Railway injects the port via environment variable)
- `SECRET_KEY` can be set via Railway environment variables for stable sessions across deploys

**Note:** The deployed app uses SQLite stored on the container's ephemeral filesystem. Data resets on each redeploy. For production persistence, consider adding a Railway PostgreSQL database.

### Deploy Your Own

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway up
```

---

## License

This project is open source and available under the [MIT License](LICENSE).

---

*Built with ❤️ using Flask, SQLite, and vanilla everything.*
