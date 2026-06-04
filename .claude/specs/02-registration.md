---
# Spec: Registration

## Overview
This step implements the user registration functionality for Spendly. Currently, the `/register` route only renders a form (GET handler). This step adds the POST handler to process the form submission, validate input, create a new user in the database, and log them in. This is the second step in the Spendly roadmap, enabling users to create accounts and proceed to login.

## Depends on
Step 1: Database setup (users table exists with proper schema).

## Routes
- `POST /register` — Process registration form submission, create new user, redirect to login — access level: public

## Database changes
No new tables or columns. The users table was created in Step 1. This step will insert new rows into the existing users table.

## Templates
- **Create:** None
- **Modify:** 
  - `register.html` — Add conditional to show success message after redirect (optional, can rely on login page message) or keep as is and show feedback on login page.

## Files to change
- `app.py` — Add POST handler for `/register` route
- `database/db.py` — Add a helper function `create_user(name, email, password_hash)` to insert a new user (optional but encouraged to keep DB logic in db.py)
- `register.html` — Optional: add a success message display (if we redirect to login with a message) or leave unchanged and handle feedback via flash messages or redirect with query param.

## Files to create
- None (if we modify existing templates) OR
  - If we choose to create a separate success template, but that's overkill for this step.

## New dependencies
No new dependencies. Uses existing Flask and werkzeug.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw SQLite via `database/db.py`
- Parameterised queries only — never use f-strings in SQL
- Passwords hashed with werkzeug's `generate_password_hash`
- Use CSS variables — never hardcode hex values (if adding any CSS, but we aren't)
- All templates extend `base.html` (register.html already does)
- Use `url_for()` for internal links — never hardcode URLs
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`
- Validate input: name, email, password presence; email format; password length; unique email constraint
- On success, log in the user automatically by setting session (or redirect to login with a message). Since we don't have login implemented yet (step 3), we can redirect to login page with a success message.

## Definition of done
- [ ] User can access `/register` via GET and see the form
- [ ] Submitting the form with valid data creates a new user in the database
- [ ] Submitting the form with invalid data (missing fields, invalid email, duplicate email) shows appropriate error messages
- [ ] After successful registration, user is redirected to `/login` with a success message (or logged in directly if we implement session)
- [ ] Password is stored as a hash (not plaintext) in the database
- [ ] All database interactions use parameterized queries
- [ ] No new Flask blueprints are used (routes stay in app.py)
- [ ] No external CSS or JS frameworks are used