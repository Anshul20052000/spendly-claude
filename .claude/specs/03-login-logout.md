---
# Spec: Login and Logout

## Overview
This step implements the login and logout functionality for Spendly. Currently, the `/login` route only renders a form (GET handler) and `/logout` is a stub. This step adds the POST handler to authenticate users against the database, manage sessions, and allow users to log out. This is the third step in the Spendly roadmap, enabling registered users to access their accounts.

## Depends on
Step 1: Database setup (users table exists with proper schema).
Step 2: Registration (users can create accounts with hashed passwords).

## Routes
- `POST /login` — Authenticate user credentials, start session, redirect to profile — access level: public
- `GET /logout` — Clear session, redirect to landing page — access level: logged-in

## Database changes
No new tables or columns. The users table already has `email` (UNIQUE) and `password_hash` columns needed for authentication.

## Templates
- **Create:** None
- **Modify:**
  - `templates/login.html` — Add flashed message display (success from registration, error from failed login)

## Files to change
- `app.py` — Add POST handler for `/login`, implement `/logout` to clear session
- `templates/login.html` — Add flashed message section

## Files to create
- None

## New dependencies
No new dependencies. Uses existing Flask, werkzeug, and sqlite3.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw SQLite via `database/db.py`
- Parameterised queries only — never use f-strings in SQL
- Passwords verified with werkzeug's `check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html` (login.html already does)
- Use `url_for()` for internal links — never hardcode URLs
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`
- Validate input: email and password presence; valid email format
- On successful login, store user info in Flask session (e.g., `session["user_id"]`, `session["user_name"]`)
- On logout, clear the session completely
- The `/logout` route should only be accessible to logged-in users; if accessed while not logged in, redirect to login

## Definition of done
- [ ] User can access `/login` via GET and see the form
- [ ] Submitting the form with valid credentials logs the user in and redirects to `/profile`
- [ ] Submitting the form with invalid credentials (wrong email or password) shows an appropriate error message
- [ ] Submitting the form with missing fields shows an error message
- [ ] After successful login, the session contains user information
- [ ] Accessing `/logout` clears the session and redirects to the landing page (`/`)
- [ ] Accessing `/logout` while not logged in redirects to `/login`
- [ ] All database interactions use parameterized queries
- [ ] No new Flask blueprints are used (routes stay in app.py)
- [ ] No external CSS or JS frameworks are used
- [ ] The stub message "Logout — coming in Step 3" is replaced with actual logout logic