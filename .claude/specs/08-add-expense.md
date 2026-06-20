---
# Spec: Add Expense

## Overview
This step implements the "Add Expense" feature for Spendly. Currently, the `/expenses/add` route is a stub returning a plain string. This step replaces it with a full form that lets a logged-in user record a new expense — amount, category, date, and description — validates the input, persists it to the database, and redirects to the profile page with a success message. This is the eighth step in the Spendly roadmap and the first feature that writes to the expenses table.

## Depends on
Step 1: Database setup (expenses table exists with schema: id, user_id, amount, category, date, description, created_at).
Step 2: Registration (users can create accounts).
Step 3: Login and Logout (session management with `session["user_id"]`).
Step 4: Profile (user dashboard exists, providing a place to link from and redirect to).

## Routes
- `GET /expenses/add` — Render the add-expense form — access level: logged-in (redirects to `/login` if not authenticated)
- `POST /expenses/add` — Process the add-expense form submission, validate input, insert expense into DB, redirect to `/profile` with success message — access level: logged-in

## Database changes
No new tables or columns. The `expenses` table was created in Step 1 with all needed fields. This step inserts new rows via a new helper function.

A new helper function is added to `database/db.py`:
- `create_expense(user_id, amount, category, date, description)` — inserts a new expense row, returns the new expense's `id`.

## Templates
- **Create:** `templates/add_expense.html` — Form page extending `base.html` with fields: amount (number), category (select dropdown), date (date input), description (text input), and a submit button.
- **Modify:** None (profile.html already links to `add_expense` in the empty-state message).

## Files to change
- `app.py` — Replace the stub `/expenses/add` route with GET and POST handlers.
- `database/db.py` — Add `create_expense()` helper function.
- `static/css/style.css` — Add expense form styles (or create a new `expenses.css` — see rules below).

## Files to create
- `templates/add_expense.html` — Add expense form template.
- `static/css/expenses.css` — Page-specific styles for the expense form (optional; can be added to `style.css`).

## New dependencies
No new dependencies. Uses existing Flask, werkzeug, and sqlite3.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw SQLite via `database/db.py`.
- Parameterised queries only — never use f-strings in SQL.
- Use CSS variables — never hardcode hex values.
- All templates extend `base.html`.
- Use `url_for()` for internal links — never hardcode URLs.
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`.
- Authentication: if `"user_id"` not in session, redirect to `/login` for both GET and POST.
- Validation rules:
  - Amount: required, must be a positive number (greater than 0).
  - Category: required, must be one of the fixed categories: Food, Transport, Bills, Health, Entertainment, Shopping, Other.
  - Date: required, must be a valid date in `YYYY-MM-DD` format.
  - Description: required, non-empty string (max 200 characters).
- On validation failure, re-render the form with flash messages showing the errors and preserve user input.
- On success, insert the expense and redirect to `/profile` with a flash message: "Expense added successfully!"
- The amount should be stored as a float/real in the database.
- Use `request.form.get()` to retrieve form values, with `.strip()` for string fields.
- Use `flash()` for all validation error messages and the success message.

## Definition of done
- [ ] Accessing `/expenses/add` while logged in shows a form with fields: Amount, Category (dropdown), Date, Description, and a submit button.
- [ ] Accessing `/expenses/add` while NOT logged in redirects to `/login`.
- [ ] Submitting the form with valid data creates a new expense in the database linked to the current user.
- [ ] After successful submission, the user is redirected to `/profile` with a success message.
- [ ] Submitting with an empty or invalid amount shows an error and re-renders the form.
- [ ] Submitting with an invalid category shows an error and re-renders the form.
- [ ] Submitting with an empty or invalid date shows an error and re-renders the form.
- [ ] Submitting with an empty description shows an error and re-renders the form.
- [ ] The form preserves user input on validation failure.
- [ ] The stub message "Add expense — coming in Step 7" is replaced with the actual form.
- [ ] All database interactions use parameterized queries.
- [ ] No new Flask blueprints are used (routes stay in `app.py`).
- [ ] No external CSS or JS frameworks are used.
- [ ] The page uses CSS variables (no hardcoded hex values).
- [ ] All internal links use `url_for()`.
