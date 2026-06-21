# Spec: Edit Expense

## Overview

Edit Expense allows a logged-in user to modify an existing expense record they
previously added. The route pre-fills a form with the current values from the
database, validates the updated input using the same rules as the add-expense
flow, and persists the change back to SQLite. This is the natural counterpart to
Step 7's add-expense route and keeps the expense-management loop coherent before
moving on to delete (Step 9).

## Depends on

- **08-add-expense** — reuses the same validation rules, form-field names, and
  template layout.

## Routes

- `GET /expenses/<int:id>/edit` — render a pre-filled edit form — logged-in only
- `POST /expenses/<int:id>/edit` — validate and persist changes, then redirect
  to `/profile` — logged-in only

## Database changes

No new tables or columns. The existing `expenses` table already stores every
field the edit form touches (`amount`, `category`, `date`, `description`).

A new helper `update_expense(id, user_id, amount, category, date, description)`
will be added to `database/db.py` to execute the `UPDATE` statement with a
parameterised query.

## Templates

- **Create:** `templates/edit_expense.html` — mirrors `add_expense.html`
  (same form fields, same `expenses.css` stylesheet) but pre-populates inputs
  from the expense row passed by the route and submits to
  `url_for('edit_expense', id=expense.id)`.
- **Modify:** none.

## Files to change

- `app.py` — replace the stub at `GET /expenses/<id>/edit` with a real route
  that handles both GET (render form) and POST (validate + update + redirect).
- `database/db.py` — add `update_expense()` helper.

## Files to create

- `templates/edit_expense.html`

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs; use raw SQLite with parameterised queries (`?`).
- Reuse the exact same validation rules as the add-expense route:
  - `amount` > 0, numeric
  - `category` must be one of the 7 fixed options
  - `date` must be a valid YYYY-MM-DD string
  - `description` required, max 200 characters
- On validation failure, `flash()` each error and re-render the form preserving
  the user's input (not the original DB values).
- On success, flash `"Expense updated successfully!"` and redirect to `/profile`.
- Only the owner of the expense may edit it — look up the row by both `id`
  and `user_id` (from session); if not found, `abort(404)`.
- Use CSS variables — never hardcode hex values.
- All templates extend `base.html`.

## Definition of done

- `GET /expenses/<id>/edit` for an owned expense returns 200 and renders a form
  pre-filled with the current amount, category, date, and description.
- `GET /expenses/<id>/edit` for an expense owned by another user (or
  non-existent) returns 404.
- `POST /expenses/<id>/edit` with valid data updates the row in the database,
  flashes a success message, and redirects to `/profile`.
- `POST /expenses/<id>/edit` with invalid data (negative amount, empty
  description, etc.) re-renders the form with flashed errors and the user's
  input preserved.
- `pytest` passes (including any tests written for this feature).
