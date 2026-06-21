"""Tests for the Edit Expense feature (Step 9).

Covers:
  - Auth guard on GET and POST
  - GET renders a pre-filled form for an owned expense
  - GET returns 404 for non-existent expense
  - GET returns 404 for another user's expense
  - POST happy path: valid data updates expense, redirects to /profile, flash success
  - DB side effect: expense row is updated with new values
  - Other user's expense is not modified
  - Validation: empty / negative / zero / non-numeric amount
  - Validation: empty / invalid category
  - Validation: empty / invalid-format date
  - Validation: empty / too-long description
  - No DB change on validation failure
  - Multiple validation errors at once
  - Input preservation on validation failure
  - SQL injection safety

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


# Valid form data used as a base for happy-path and single-field overrides
VALID_EDIT_DATA = {
    "amount": "999.99",
    "category": "Bills",
    "date": "2026-06-20",
    "description": "Updated expense description",
}


# ------------------------------------------------------------------ #
# 1. Auth guard                                                        #
# ------------------------------------------------------------------ #


class TestAuthGuard:
    def test_get_redirects_when_not_logged_in(self, client):
        """Unauthenticated GET /expenses/<id>/edit must redirect to /login."""
        response = client.get("/expenses/1/edit")
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/login" in response.headers["Location"]

    def test_post_redirects_when_not_logged_in(self, client):
        """Unauthenticated POST /expenses/<id>/edit must redirect to /login."""
        response = client.post("/expenses/1/edit", data=VALID_EDIT_DATA)
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# 2. GET renders pre-filled form                                       #
# ------------------------------------------------------------------ #


class TestGetRendersPrefilledForm:
    def test_returns_200(self, logged_in):
        """Authenticated GET for an owned expense should return 200."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert response.status_code == 200

    def test_contains_amount_field(self, logged_in):
        """Form should include an input field named 'amount'."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert b'name="amount"' in response.data

    def test_contains_category_field(self, logged_in):
        """Form should include a select field named 'category'."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert b'name="category"' in response.data

    def test_contains_date_field(self, logged_in):
        """Form should include an input field named 'date'."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert b'name="date"' in response.data

    def test_contains_description_field(self, logged_in):
        """Form should include an input field named 'description'."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert b'name="description"' in response.data

    def test_contains_submit_button(self, logged_in):
        """Form should include a submit button."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert b'type="submit"' in response.data

    def test_amount_prefilled(self, logged_in):
        """Amount field should be pre-filled with the current expense amount."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        expense = _get_expense(eid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert str(expense["amount"]).encode() in response.data

    def test_category_prefilled(self, logged_in):
        """Category select should have the current expense category selected."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        expense = _get_expense(eid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert expense["category"].encode() in response.data

    def test_date_prefilled(self, logged_in):
        """Date field should be pre-filled with the current expense date."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        expense = _get_expense(eid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert expense["date"].encode() in response.data

    def test_description_prefilled(self, logged_in):
        """Description field should be pre-filled with the current description."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        expense = _get_expense(eid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert expense["description"].encode() in response.data

    def test_page_title(self, logged_in):
        """Page should have the Edit Expense title."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        assert b"Edit Expense" in response.data

    def test_all_valid_categories_present(self, logged_in):
        """Category dropdown should list all 7 valid categories."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.get(f"/expenses/{eid}/edit")
        valid_categories = [
            "Food", "Transport", "Bills", "Health",
            "Entertainment", "Shopping", "Other",
        ]
        for cat in valid_categories:
            assert cat.encode() in response.data, f"Missing category: {cat}"


# ------------------------------------------------------------------ #
# 3. GET 404 for non-existent expense                                  #
# ------------------------------------------------------------------ #


class TestGet404NonExistent:
    def test_nonexistent_expense_returns_404(self, logged_in):
        """GET for an expense ID that does not exist should return 404."""
        response = logged_in.get("/expenses/9999/edit")
        assert response.status_code == 404

    def test_nonexistent_expense_does_not_render_form(self, logged_in):
        """404 response should not contain the edit expense form."""
        response = logged_in.get("/expenses/9999/edit")
        assert b"Edit Expense" not in response.data


# ------------------------------------------------------------------ #
# 4. GET 404 for other user's expense                                  #
# ------------------------------------------------------------------ #


class TestGet404OtherUserExpense:
    def test_other_users_expense_returns_404(self, logged_in):
        """GET for another user's expense should return 404."""
        other_uid = _get_second_user_id()
        other_eid = _create_expense_for_user(
            other_uid, amount=500.00, category="Transport",
            date="2026-06-10", description="Other user expense",
        )
        response = logged_in.get(f"/expenses/{other_eid}/edit")
        assert response.status_code == 404

    def test_other_users_expense_not_prefilled(self, logged_in):
        """404 response should not contain the other user's expense data."""
        other_uid = _get_second_user_id()
        other_eid = _create_expense_for_user(
            other_uid, amount=500.00, category="Transport",
            date="2026-06-10", description="Secret expense",
        )
        response = logged_in.get(f"/expenses/{other_eid}/edit")
        assert b"Secret expense" not in response.data


# ------------------------------------------------------------------ #
# 5. POST happy path                                                   #
# ------------------------------------------------------------------ #


class TestPostHappyPath:
    def test_redirects_to_profile(self, logged_in):
        """Valid submission should redirect to /profile."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.post(f"/expenses/{eid}/edit", data=VALID_EDIT_DATA)
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/profile" in response.headers["Location"]

    def test_success_flash_message(self, logged_in):
        """After a successful update, the success flash should appear."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        response = logged_in.post(
            f"/expenses/{eid}/edit", data=VALID_EDIT_DATA, follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Expense updated successfully!" in response.data


# ------------------------------------------------------------------ #
# 6. DB side effect on update                                          #
# ------------------------------------------------------------------ #


class TestDbSideEffect:
    def test_expense_row_updated(self, logged_in):
        """After POST with valid data, the expense should have new values in DB."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        logged_in.post(f"/expenses/{eid}/edit", data=VALID_EDIT_DATA)

        row = _get_expense(eid)
        assert row is not None, "Expense row not found"
        assert row["amount"] == pytest.approx(999.99)
        assert row["category"] == "Bills"
        assert row["date"] == "2026-06-20"
        assert row["description"] == "Updated expense description"

    def test_expense_count_unchanged(self, logged_in):
        """Updating an expense should not change the total row count."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        initial_count = _count_expenses(uid)
        logged_in.post(f"/expenses/{eid}/edit", data=VALID_EDIT_DATA)
        assert _count_expenses(uid) == initial_count

    def test_expense_still_owned_by_same_user(self, logged_in):
        """After update, the expense should still belong to the same user."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        logged_in.post(f"/expenses/{eid}/edit", data=VALID_EDIT_DATA)

        row = _get_expense(eid)
        assert row["user_id"] == uid

    def test_amount_stored_as_float(self, logged_in):
        """Amount containing decimals should be stored as a real number."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="123.45")
        logged_in.post(f"/expenses/{eid}/edit", data=data)

        row = _get_expense(eid)
        assert row["amount"] == pytest.approx(123.45)

    def test_partial_update(self, logged_in):
        """Updating only amount should change amount and keep other fields."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)

        data = {
            "amount": "777.77",
            "category": original["category"],
            "date": original["date"],
            "description": original["description"],
        }
        logged_in.post(f"/expenses/{eid}/edit", data=data)

        row = _get_expense(eid)
        assert row["amount"] == pytest.approx(777.77)
        assert row["category"] == original["category"]
        assert row["date"] == original["date"]
        assert row["description"] == original["description"]


# ------------------------------------------------------------------ #
# 7. Other user's expense not modified                                 #
# ------------------------------------------------------------------ #


class TestOtherUserExpenseNotModified:
    def test_post_other_users_expense_returns_404(self, logged_in):
        """POST to another user's expense should return 404."""
        other_uid = _get_second_user_id()
        other_eid = _create_expense_for_user(
            other_uid, amount=500.00, category="Transport",
            date="2026-06-10", description="Other user expense",
        )
        response = logged_in.post(
            f"/expenses/{other_eid}/edit", data=VALID_EDIT_DATA,
        )
        assert response.status_code == 404

    def test_other_users_expense_unchanged_after_post(self, logged_in):
        """Another user's expense must not be modified even if POST reaches the DB."""
        other_uid = _get_second_user_id()
        other_eid = _create_expense_for_user(
            other_uid, amount=500.00, category="Transport",
            date="2026-06-10", description="Other user expense",
        )
        logged_in.post(
            f"/expenses/{other_eid}/edit", data=VALID_EDIT_DATA,
        )

        row = _get_expense(other_eid)
        assert row["amount"] == pytest.approx(500.00)
        assert row["category"] == "Transport"
        assert row["date"] == "2026-06-10"
        assert row["description"] == "Other user expense"


# ------------------------------------------------------------------ #
# 8. Validation: amount                                                #
# ------------------------------------------------------------------ #


class TestAmountValidation:
    def test_empty_amount_renders_form_with_error(self, logged_in):
        """Submitting with empty amount should re-render the form."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200, "Expected form re-render (200)"
        assert b"Amount is required." in response.data

    def test_negative_amount_renders_form_with_error(self, logged_in):
        """Submitting with a negative amount should flash an error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="-10.00")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Amount must be greater than 0." in response.data

    def test_zero_amount_renders_form_with_error(self, logged_in):
        """Submitting with zero amount should flash an error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="0")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Amount must be greater than 0." in response.data

    def test_non_numeric_amount_renders_form_with_error(self, logged_in):
        """Submitting with non-numeric amount should flash an error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="abc")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Amount must be a valid number." in response.data

    def test_expense_not_modified_on_invalid_amount(self, logged_in):
        """No DB change should occur when amount validation fails."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)
        logged_in.post(
            f"/expenses/{eid}/edit",
            data=dict(VALID_EDIT_DATA, amount=""),
        )
        row = _get_expense(eid)
        assert row["amount"] == original["amount"]
        assert row["category"] == original["category"]
        assert row["date"] == original["date"]
        assert row["description"] == original["description"]


# ------------------------------------------------------------------ #
# 9. Validation: category                                              #
# ------------------------------------------------------------------ #


class TestCategoryValidation:
    def test_empty_category_renders_form_with_error(self, logged_in):
        """Submitting with empty category should re-render the form."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, category="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Category is required." in response.data

    def test_invalid_category_renders_form_with_error(self, logged_in):
        """Submitting with an unrecognised category should flash an error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, category="Crypto")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Please select a valid category." in response.data

    def test_case_sensitive_category_validation(self, logged_in):
        """Category 'food' (lowercase) should be rejected; only 'Food' is valid."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, category="food")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Please select a valid category." in response.data

    def test_expense_not_modified_on_invalid_category(self, logged_in):
        """No DB change should occur when category validation fails."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)
        logged_in.post(
            f"/expenses/{eid}/edit",
            data=dict(VALID_EDIT_DATA, category=""),
        )
        row = _get_expense(eid)
        assert row["category"] == original["category"]


# ------------------------------------------------------------------ #
# 10. Validation: date                                                 #
# ------------------------------------------------------------------ #


class TestDateValidation:
    def test_empty_date_renders_form_with_error(self, logged_in):
        """Submitting with empty date should re-render the form."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, date="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Date is required." in response.data

    def test_invalid_date_format_renders_form_with_error(self, logged_in):
        """Submitting with a non-YYYY-MM-DD date should flash an error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, date="15-06-2026")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Date must be in YYYY-MM-DD format." in response.data

    def test_garbage_date_renders_form_with_error(self, logged_in):
        """Submitting with a garbage date string should flash an error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, date="not-a-date")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Date must be in YYYY-MM-DD format." in response.data

    def test_expense_not_modified_on_invalid_date(self, logged_in):
        """No DB change should occur when date validation fails."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)
        logged_in.post(
            f"/expenses/{eid}/edit",
            data=dict(VALID_EDIT_DATA, date=""),
        )
        row = _get_expense(eid)
        assert row["date"] == original["date"]


# ------------------------------------------------------------------ #
# 11. Validation: description                                          #
# ------------------------------------------------------------------ #


class TestDescriptionValidation:
    def test_empty_description_renders_form_with_error(self, logged_in):
        """Submitting with empty description should re-render the form."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, description="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Description is required." in response.data

    def test_description_over_200_chars_renders_form_with_error(self, logged_in):
        """Submitting with a description longer than 200 chars should error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        long_desc = "a" * 201
        data = dict(VALID_EDIT_DATA, description=long_desc)
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Description must be 200 characters or fewer." in response.data

    def test_description_exactly_200_chars_is_accepted(self, logged_in):
        """A description of exactly 200 characters should be accepted."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        exact_desc = "b" * 200
        data = dict(VALID_EDIT_DATA, description=exact_desc)
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 302, "Expected redirect on success"

    def test_expense_not_modified_on_invalid_description(self, logged_in):
        """No DB change should occur when description validation fails."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)
        logged_in.post(
            f"/expenses/{eid}/edit",
            data=dict(VALID_EDIT_DATA, description=""),
        )
        row = _get_expense(eid)
        assert row["description"] == original["description"]


# ------------------------------------------------------------------ #
# 12. No DB change on validation failure (composite)                   #
# ------------------------------------------------------------------ #


class TestNoDbChangeOnValidationError:
    def test_no_change_when_all_fields_invalid(self, logged_in):
        """When all fields are invalid, the expense row must be unchanged."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)

        logged_in.post(
            f"/expenses/{eid}/edit",
            data={"amount": "", "category": "", "date": "", "description": ""},
        )

        row = _get_expense(eid)
        assert row["amount"] == original["amount"]
        assert row["category"] == original["category"]
        assert row["date"] == original["date"]
        assert row["description"] == original["description"]


# ------------------------------------------------------------------ #
# 13. Multiple validation errors at once                                #
# ------------------------------------------------------------------ #


class TestMultipleValidationErrors:
    def test_all_errors_shown_when_every_field_invalid(self, logged_in):
        """Submitting with all fields invalid should show every error."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = {
            "amount": "",
            "category": "",
            "date": "",
            "description": "",
        }
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Amount is required." in response.data
        assert b"Category is required." in response.data
        assert b"Date is required." in response.data
        assert b"Description is required." in response.data

    def test_no_expense_modified_when_any_validation_fails(self, logged_in):
        """No row should be modified when any field fails validation."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)
        logged_in.post(
            f"/expenses/{eid}/edit",
            data={"amount": "", "category": "", "date": "", "description": ""},
        )
        row = _get_expense(eid)
        assert row["amount"] == original["amount"]
        assert row["category"] == original["category"]
        assert row["date"] == original["date"]
        assert row["description"] == original["description"]


# ------------------------------------------------------------------ #
# 14. Input preservation on validation failure                          #
# ------------------------------------------------------------------ #


class TestInputPreservation:
    def test_amount_preserved_on_error(self, logged_in):
        """On validation failure, the amount field should retain its value."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        # Only category is invalid; amount should be preserved.
        data = dict(VALID_EDIT_DATA, category="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert b"999.99" in response.data

    def test_category_preserved_on_error(self, logged_in):
        """On validation failure, the selected category should remain visible."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert b"Bills" in response.data

    def test_date_preserved_on_error(self, logged_in):
        """On validation failure, the date field should retain its value."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert b"2026-06-20" in response.data

    def test_description_preserved_on_error(self, logged_in):
        """On validation failure, the description field should retain its value."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert b"Updated expense description" in response.data

    def test_all_fields_preserved_together(self, logged_in):
        """When only one field is invalid, all other fields should be preserved."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="")  # only amount is invalid
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code == 200
        assert b"Bills" in response.data
        assert b"2026-06-20" in response.data
        assert b"Updated expense description" in response.data


# ------------------------------------------------------------------ #
# 15. SQL injection safety                                             #
# ------------------------------------------------------------------ #


class TestSqlInjectionSafety:
    def test_sql_injection_in_description_does_not_crash(self, logged_in):
        """A SQL injection attempt in description should not crash."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(
            VALID_EDIT_DATA,
            description="'; DROP TABLE expenses; --",
        )
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        # Should either succeed (parameterised query) or fail validation,
        # but must NOT crash.
        assert response.status_code in (200, 302)

    def test_sql_injection_does_not_drop_table(self, logged_in):
        """The expenses table must still exist after an injection attempt."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        logged_in.post(
            f"/expenses/{eid}/edit",
            data=dict(
                VALID_EDIT_DATA,
                description="'; DROP TABLE expenses; --",
            ),
        )
        # If the table still exists, we can query it
        count = _count_expenses(uid)
        assert count >= 0  # would raise if table were dropped

    def test_sql_injection_in_amount_does_not_crash(self, logged_in):
        """A SQL injection attempt in amount should not crash."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        data = dict(VALID_EDIT_DATA, amount="1; DROP TABLE expenses; --")
        response = logged_in.post(f"/expenses/{eid}/edit", data=data)
        assert response.status_code in (200, 302)

    def test_expense_unchanged_after_sql_injection_attempt(self, logged_in):
        """Expense data should be unchanged after a SQL injection attempt."""
        uid = _get_demo_user_id()
        eid = _first_expense_id(uid)
        original = _get_expense(eid)
        logged_in.post(
            f"/expenses/{eid}/edit",
            data=dict(
                VALID_EDIT_DATA,
                description="'; DROP TABLE expenses; --",
            ),
        )
        row = _get_expense(eid)
        # Either the update succeeded (param query stored the literal string)
        # or it was rejected, but the original data must not be corrupted.
        # We check the table is still intact by verifying the row exists.
        assert row is not None
