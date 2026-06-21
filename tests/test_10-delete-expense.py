"""Tests for the Delete Expense feature (Step 10).

Covers:
  - POST happy path: owned expense is deleted, redirects to /profile, flash success
  - DB side effect: expense row is removed from the database
  - Auth guard on POST (unauthenticated requests redirect to /login)
  - GET returns 405 Method Not Allowed
  - Non-existent expense returns 404
  - Other user's expense returns 404 (ownership guard)
  - Other user's expense is not deleted
  - Expense count decreases by exactly 1 after deletion
  - Deleting one expense does not affect other expenses
  - SQL injection safety in the expense ID parameter
  - Flash message content on success

All tests use an isolated temporary SQLite database seeded with the standard
demo user (demo@spendly.com / demo123).
"""

import pytest

import database.db as db_mod
from app import app as spendly_app
from database.db import get_db, init_db, seed_db

# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Redirect the DB to a temp file and re-init/seed for every test."""
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_db)
    init_db()
    seed_db()
    yield


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a Flask app configured for testing with an isolated DB."""
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_db)

    spendly_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        }
    )
    init_db()
    seed_db()
    return spendly_app


@pytest.fixture
def client(app):
    """Return a Flask test client."""
    return app.test_client()


@pytest.fixture
def logged_in(client):
    """Return a test client that is already logged in as the demo user."""
    client.post(
        "/login",
        data={"email": "demo@spendly.com", "password": "demo123"},
        follow_redirects=True,
    )
    return client


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #


def _get_demo_user_id():
    """Return the demo user's database id (always 1 for a fresh seed)."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    conn.close()
    return row["id"]


def _get_second_user_id():
    """Create and return a second user's id for ownership tests."""
    from werkzeug.security import generate_password_hash
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Other User", "other@test.com", generate_password_hash("otherpass")),
    )
    conn.commit()
    uid = cursor.lastrowid
    conn.close()
    return uid


def _get_expense(expense_id):
    """Return the expense row with the given id, or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, user_id, amount, category, date, description "
        "FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    return row


def _count_expenses(user_id):
    """Return the number of expense rows for the given user."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]


def _first_expense_id(user_id):
    """Return the id of the first expense belonging to user_id."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM expenses WHERE user_id = ? ORDER BY id ASC LIMIT 1",
        (user_id,),
    ).fetchone()
    conn.close()
    return row["id"]


def _create_expense_for_user(user_id, amount=100.00, category="Food",
                              date="2026-06-15", description="Test expense"):
    """Create an expense for a specific user and return its id."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    eid = cursor.lastrowid
    conn.close()
    return eid


def _all_expense_ids(user_id):
    """Return a list of all expense ids for the given user, ordered by id."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id FROM expenses WHERE user_id = ? ORDER BY id ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [r["id"] for r in rows]


# ------------------------------------------------------------------ #
# 1. POST happy path                                                   #
# ------------------------------------------------------------------ #


class TestPostHappyPath:
    def test_redirects_to_profile(self, logged_in):
        """Deleting an owned expense should redirect to /profile."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.post(f"/expenses/{eid}/delete")
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/profile" in response.headers["Location"]

    def test_success_flash_message(self, logged_in):
        """After deletion, the success flash should appear on the profile page."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.post(
            f"/expenses/{eid}/delete", follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Expense deleted successfully!" in response.data


# ------------------------------------------------------------------ #
# 2. DB side effect: expense row is removed                            #
# ------------------------------------------------------------------ #


class TestDbSideEffect:
    def test_expense_row_deleted(self, logged_in):
        """After POST, the expense should no longer exist in the database."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        logged_in.post(f"/expenses/{eid}/delete")
        row = _get_expense(eid)
        assert row is None, "Expense row should have been deleted"

    def test_expense_count_decreases_by_one(self, logged_in):
        """Deleting an expense should reduce the user's expense count by exactly 1."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        initial_count = _count_expenses(uid)
        logged_in.post(f"/expenses/{eid}/delete")
        assert _count_expenses(uid) == initial_count - 1

    def test_other_expenses_not_affected(self, logged_in):
        """Deleting one expense should not remove any other expenses."""
        uid = _get_demo_user_id()
        all_ids_before = _all_expense_ids(uid)
        assert len(all_ids_before) > 1, "Need at least 2 expenses for this test"

        eid_to_delete = all_ids_before[0]
        logged_in.post(f"/expenses/{eid_to_delete}/delete")

        remaining_ids = _all_expense_ids(uid)
        expected_ids = all_ids_before[1:]
        assert remaining_ids == expected_ids

    def test_specific_expense_targeted(self, logged_in):
        """Only the specified expense should be deleted, not others."""
        uid = _get_demo_user_id()
        all_ids = _all_expense_ids(uid)
        assert len(all_ids) >= 2, "Need at least 2 expenses"

        # Delete the second expense
        target_id = all_ids[1]
        logged_in.post(f"/expenses/{target_id}/delete")

        # First expense should still exist
        assert _get_expense(all_ids[0]) is not None
        # Target should be gone
        assert _get_expense(target_id) is None


# ------------------------------------------------------------------ #
# 3. Auth guard                                                         #
# ------------------------------------------------------------------ #


class TestAuthGuard:
    def test_post_redirects_when_not_logged_in(self, client):
        """Unauthenticated POST /expenses/<id>/delete must redirect to /login."""
        response = client.post("/expenses/1/delete")
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/login" in response.headers["Location"]

    def test_post_does_not_delete_when_not_logged_in(self, app, client):
        """An unauthenticated POST must not delete any expense."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        client.post("/expenses/1/delete")
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 4. GET returns 405 Method Not Allowed                                #
# ------------------------------------------------------------------ #


class TestGetMethodNotAllowed:
    def test_get_returns_405(self, logged_in):
        """GET /expenses/<id>/delete should return 405 Method Not Allowed."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/delete")
        assert response.status_code == 405

    def test_get_does_not_delete_expense(self, logged_in):
        """GET request must not delete the expense."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        initial_count = _count_expenses(uid)
        logged_in.get(f"/expenses/{eid}/delete")
        assert _get_expense(eid) is not None
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 5. Non-existent expense returns 404                                  #
# ------------------------------------------------------------------ #


class TestNonExistentExpense:
    def test_nonexistent_expense_returns_404(self, logged_in):
        """POST for a non-existent expense ID should return 404."""
        response = logged_in.post("/expenses/9999/delete")
        assert response.status_code == 404

    def test_no_expense_deleted_for_nonexistent_id(self, logged_in):
        """A 404 for a non-existent id must not delete any existing expense."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/9999/delete")
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 6. Other user's expense returns 404 (ownership guard)                #
# ------------------------------------------------------------------ #


class TestOwnershipGuard:
    def test_other_users_expense_returns_404(self, logged_in):
        """POST for another user's expense should return 404."""
        other_uid = _get_second_user_id()
        other_eid = _create_expense_for_user(
            other_uid, amount=500.00, category="Transport",
            date="2026-06-10", description="Other user expense",
        )
        response = logged_in.post(f"/expenses/{other_eid}/delete")
        assert response.status_code == 404

    def test_other_users_expense_not_deleted(self, logged_in):
        """Another user's expense must not be deleted."""
        other_uid = _get_second_user_id()
        other_eid = _create_expense_for_user(
            other_uid, amount=500.00, category="Transport",
            date="2026-06-10", description="Other user expense",
        )
        logged_in.post(f"/expenses/{other_eid}/delete")

        row = _get_expense(other_eid)
        assert row is not None, "Other user's expense should not be deleted"
        assert row["amount"] == pytest.approx(500.00)
        assert row["category"] == "Transport"
        assert row["description"] == "Other user expense"

    def test_demo_user_expenses_intact_after_other_user_delete_attempt(self, logged_in):
        """Demo user expenses must be intact after attempting to delete another user's expense."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        initial_ids = _all_expense_ids(uid)

        other_uid = _get_second_user_id()
        other_eid = _create_expense_for_user(
            other_uid, amount=500.00, category="Transport",
            date="2026-06-10", description="Other user expense",
        )
        logged_in.post(f"/expenses/{other_eid}/delete")

        assert _count_expenses(uid) == initial_count
        assert _all_expense_ids(uid) == initial_ids


# ------------------------------------------------------------------ #
# 7. Flash message content                                             #
# ------------------------------------------------------------------ #


class TestFlashMessage:
    def test_flash_contains_exact_text(self, logged_in):
        """The flash message should be exactly 'Expense deleted successfully!'."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.post(
            f"/expenses/{eid}/delete", follow_redirects=True,
        )
        assert b"Expense deleted successfully!" in response.data

    def test_no_flash_on_get_request(self, logged_in):
        """GET request (405) should not produce a success flash."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(
            f"/expenses/{eid}/delete", follow_redirects=True,
        )
        # GET returns 405, so no flash should be set
        assert b"Expense deleted successfully!" not in response.data


# ------------------------------------------------------------------ #
# 8. SQL injection safety                                              #
# ------------------------------------------------------------------ #


class TestSqlInjectionSafety:
    def test_sql_injection_in_id_does_not_crash(self, logged_in):
        """A SQL injection attempt in the id parameter should not crash."""
        response = logged_in.post("/expenses/1%20OR%201=1/delete")
        # Should return 404 (no such id) or 405/400, but must NOT crash
        assert response.status_code in (404, 405, 400, 302)

    def test_sql_injection_does_not_drop_table(self, logged_in):
        """The expenses table must still exist after an injection attempt."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/1;DROP TABLE expenses;/delete")
        # Table should still be queryable
        count = _count_expenses(uid)
        assert count >= 0

    def test_sql_injection_does_not_delete_all_expenses(self, logged_in):
        """A SQL injection must not delete expenses beyond the target."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        # Attempt injection that might try to delete all rows
        logged_in.post("/expenses/1%20OR%201=1/delete")
        # Count should not have decreased (or at most by 1 if id 1 matched)
        current_count = _count_expenses(uid)
        assert current_count >= initial_count - 1

    def test_expenses_table_intact_after_injection(self, logged_in):
        """All original expenses should still exist after a SQL injection attempt."""
        uid = _get_demo_user_id()
        ids_before = _all_expense_ids(uid)
        logged_in.post("/expenses/1%20OR%201%3D1/delete")
        ids_after = _all_expense_ids(uid)
        # At most one expense (id=1) could have been legitimately deleted
        assert len(ids_after) >= len(ids_before) - 1


# ------------------------------------------------------------------ #
# 9. Multiple deletions                                                #
# ------------------------------------------------------------------ #


class TestMultipleDeletions:
    def test_delete_two_expenses_sequentially(self, logged_in):
        """Deleting two different expenses should remove both."""
        uid = _get_demo_user_id()
        ids = _all_expense_ids(uid)
        assert len(ids) >= 2, "Need at least 2 expenses"

        logged_in.post(f"/expenses/{ids[0]}/delete")
        logged_in.post(f"/expenses/{ids[1]}/delete")

        assert _get_expense(ids[0]) is None
        assert _get_expense(ids[1]) is None
        assert _count_expenses(uid) == len(ids) - 2

    def test_delete_same_expense_twice_returns_404_second_time(self, logged_in):
        """Deleting an already-deleted expense should return 404."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)

        response1 = logged_in.post(f"/expenses/{eid}/delete")
        assert response1.status_code == 302, "First delete should succeed"

        response2 = logged_in.post(f"/expenses/{eid}/delete")
        assert response2.status_code == 404, "Second delete should return 404"


# ------------------------------------------------------------------ #
# 10. Delete all expenses one by one                                   #
# ------------------------------------------------------------------ #


class TestDeleteAllExpenses:
    def test_delete_all_expenses_results_in_zero_count(self, logged_in):
        """Deleting all expenses should result in zero count."""
        uid = _get_demo_user_id()
        ids = _all_expense_ids(uid)

        for eid in ids:
            response = logged_in.post(f"/expenses/{eid}/delete")
            assert response.status_code == 302, f"Failed to delete expense {eid}"

        assert _count_expenses(uid) == 0

    def test_profile_still_loads_after_deleting_all_expenses(self, logged_in):
        """Profile page should still render after all expenses are deleted."""
        uid = _get_demo_user_id()
        ids = _all_expense_ids(uid)

        for eid in ids:
            logged_in.post(f"/expenses/{eid}/delete")

        response = logged_in.get("/profile")
        assert response.status_code == 200
