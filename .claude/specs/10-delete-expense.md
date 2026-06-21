# Spec: Delete Expense

## Overview

Delete Expense allows a logged-in user to remove an expense record they previously
added. A confirmation dialog prevents accidental deletion, and the route enforces
ownership so users can only delete their own expenses. This completes the
CRUD cycle (Create, Read, Update, Delete) for expenses in Spendly.

## Depends on

- **08-add-expense** — expenses exist to delete
- **09-edit-expense** — establishes the owner-check pattern and DB helper convention

## Routes

- `POST /expenses/<int:id>/delete` — delete the expense and redirect to `/profile` — logged-in only

Note: POST (not GET) is used for destructive operations to prevent accidental
deletion from link prefetching or crawlers.

## Database changes

No new tables or columns. A new helper `delete_expense(id, user_id)` will be
added to `database/db.py` to execute the `DELETE` statement with a parameterised
query.

## Templates

- **Modify:** `templates/profile.html` — add a Delete button next to the Edit
  link in each transaction row, with a JavaScript confirmation dialog before
  submitting the delete form.

## Files to change

- `app.py` — replace the stub at `GET /expenses/<id>/delete` with a POST route
  that verifies ownership, deletes the row, flashes a success message, and
  redirects to `/profile`.
- `database/db.py` — add `delete_expense()` helper.
- `templates/profile.html` — add Delete button with JS confirmation in the
  Actions column.
- `static/css/profile.css` — add `.profile-action-delete` button styles.

## Files to create

No new files.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs; use raw SQLite with parameterised queries (`?`).
- Use POST method only — never use GET for destructive operations.
- Only the owner of the expense may delete it — look up the row by both `id`
  and `user_id` (from session); if not found, `abort(404)`.
- On success, flash `"Expense deleted successfully!"` and redirect to `/profile`.
- Use a JavaScript `confirm()` dialog before submitting the delete form — no
  separate confirmation page needed.
- Use CSS variables — never hardcode hex values.
- All templates extend `base.html`.

## Definition of done

- `POST /expenses/<id>/delete` for an owned expense removes the row from the
  database, flashes a success message, and redirects to `/profile`.
- `POST /expenses/<id>/delete` for a non-existent expense returns 404.
- `POST /expenses/<id>/delete` for another user's expense returns 404 and
  does not modify the row.
- `GET /expenses/<id>/delete` returns 405 Method Not Allowed.
- Clicking the Delete button shows a browser confirmation dialog; cancelling
  it does not submit the form.
- `pytest` passes (including any tests written for this feature).
