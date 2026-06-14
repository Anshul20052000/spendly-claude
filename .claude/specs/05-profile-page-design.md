---
# Spec: Profile Page Design

## Overview
This step upgrades the existing `/profile` page from a basic user-info card into a full-featured personal finance dashboard. The profile already displays the logged-in user's name, email, and member-since date (Step 4). This step adds summary statistics, a transaction history table pulled from the database, a category breakdown with visual bars, and polished profile-specific CSS. The result is a rich, data-driven dashboard that gives users immediate insight into their spending.

## Depends on
- Step 1: Database setup (users + expenses tables, `get_db()`, `get_user_by_id()`)
- Step 2: Registration (user accounts exist)
- Step 3: Login and Logout (session management, `session["user_id"]`)
- Step 4: Profile (basic `/profile` route and `profile.html` template already work)

## Routes
- `GET /profile` — Enhanced to also pass expense summary stats, recent transactions, and category breakdown data — access level: logged-in only

## Database changes
No new tables or columns. Uses existing `users` and `expenses` tables.

New helper functions needed in `database/db.py`:
- `get_expenses_by_user(user_id)` — returns all expenses for a user, ordered by date descending
- `get_expense_summary(user_id)` — returns aggregate data: total spent, transaction count, top category
- `get_category_breakdown(user_id)` — returns per-category totals ordered by amount descending

## Templates
- **Modify:** `templates/profile.html` — replace the basic layout with a full dashboard containing:
  1. **User info card** — avatar initials, name, email, member-since date (keep from Step 4)
  2. **Summary stats row** — 3 stat cards: total spent (₹), number of transactions, top category
  3. **Transaction history table** — date, description, category badge, amount; latest 10 expenses
  4. **Category breakdown** — per-category totals with progress-bar visualisation

## Files to change
- `app.py` — Update the `/profile` route to query expense data and pass it to the template
- `database/db.py` — Add `get_expenses_by_user()`, `get_expense_summary()`, `get_category_breakdown()` helpers
- `templates/profile.html` — Full redesign with dashboard sections
- `static/css/style.css` — Add profile-page CSS variables and classes (or create `static/css/profile.css`)

## Files to create
- `static/css/profile.css` — Profile-specific styles (imported by `profile.html` via `{% block head %}`)

## New dependencies
No new dependencies. Uses existing Flask, werkzeug, sqlite3.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `database/db.py`
- Parameterised queries only — never use f-strings in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for internal links — never hardcode URLs
- Authentication guard: check `session.get("user_id")`; if absent, `redirect(url_for("login"))`
- All DB logic belongs in `database/db.py` — never query SQLite directly in route functions
- Category badges must use a CSS class, not inline colour styles
- Display amounts in INR (₹) format — e.g., ₹1,250.00
- Handle the case where a user has zero expenses gracefully (show 0 stats, empty table message)
- Profile-specific styles go in a separate `profile.css` file, not inline `<style>` tags

## Definition of done
- [ ] Visiting `/profile` without being logged in redirects to `/login`
- [ ] Visiting `/profile` while logged in returns HTTP 200
- [ ] The page displays the user's name, email, and member-since date
- [ ] The page displays a summary stats row with total spent (₹), transaction count, and top category
- [ ] The page displays a transaction history table with the user's actual expenses from the database
- [ ] The page displays a category breakdown section with per-category totals and visual bars
- [ ] A user with no expenses sees zeroed-out stats and an empty-state message instead of an empty table
- [ ] All amounts display in ₹ (INR) format
- [ ] No hex colour values appear in profile templates or CSS — only CSS variables
- [ ] All database queries use parameterised SQL
- [ ] No new pip packages are installed
