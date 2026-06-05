---
# Spec: Profile

## Overview
This step implements the user profile page for Spendly. Currently, `/profile` is a stub returning a plain string. This step replaces it with a proper template that displays the logged-in user's information (name, email, member since date) and provides navigation to expense-related actions. This is the fourth step in the Spendly roadmap, giving authenticated users a personalized dashboard.

## Depends on
Step 1: Database setup (users table exists).
Step 2: Registration (users can create accounts).
Step 3: Login and Logout (session management with `session["user_id"]` and `session["user_name"]`).

## Routes
- `GET /profile` — Display the logged-in user's profile — access level: logged-in (redirects to `/login` if not authenticated)

## Database changes
No new tables or columns. The existing `users` table has all needed fields: `id`, `name`, `email`, `created_at`.

## Templates
- **Create:** `templates/profile.html` — new template extending `base.html`
- **Modify:** `templates/base.html` — update nav bar to show user name and "Logout" when logged in (optional but recommended for good UX)

## Files to change
- `app.py` — Replace the stub `/profile` route with a proper handler that fetches the user from the session and renders the profile template
- `database/db.py` — Optionally add a `get_user_by_id(user_id)` helper for fetching user details (recommended to keep DB logic out of routes)
- `templates/base.html` — Update nav bar to conditionally show logged-in state (user name + Logout) vs logged-out state (Sign in + Get started)

## Files to create
- `templates/profile.html` — Profile page template

## New dependencies
No new dependencies. Uses existing Flask, werkzeug, and sqlite3.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw SQLite via `database/db.py`
- Parameterised queries only — never use f-strings in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for internal links — never hardcode URLs
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`
- Check authentication: if `"user_id"` not in session, redirect to `/login`
- Display user's name, email, and formatted `created_at` date (e.g., "Member since June 2026")
- Add navigation links/cards to: View Expenses, Add Expense (future steps)

## Definition of done
- [ ] Accessing `/profile` while logged in shows a page with the user's name, email, and member-since date
- [ ] Accessing `/profile` while NOT logged in redirects to `/login`
- [ ] The page uses the `base.html` layout
- [ ] Navigation bar in `base.html` shows the user's name and "Logout" when logged in; shows "Sign in" and "Get started" when logged out
- [ ] All database interactions use parameterized queries
- [ ] No new Flask blueprints are used (routes stay in app.py)
- [ ] No external CSS or JS frameworks are used
- [ ] The stub message "Profile page — coming in Step 4" is replaced with the actual profile template