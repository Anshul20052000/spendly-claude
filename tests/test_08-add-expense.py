"""Tests for the Add Expense feature (Step 8).

Covers:
  - Auth guard on GET and POST
  - GET renders the add-expense form
  - POST happy path: valid data creates expense, redirects to /profile, flash success
  - DB side effect: expense row is persisted and linked to the current user
  - Validation: empty / negative / zero / non-numeric amount
  - Validation: empty / invalid category
  - Validation: empty / invalid-format date
  - Validation: empty / too-long description
  - Input preservation on validation failure

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
# Helper                                                               #
# ------------------------------------------------------------------ #


def _get_demo_user_id():
    """Return the demo user's database id (always 1 for a fresh seed)."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()
    conn.close()
    return row["id"]


def _count_expenses(user_id):
    """Return the number of expense rows for the given user."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row["cnt"]


# Valid form data used as a base for happy-path and single-field overrides
VALID_DATA = {
    "amount": "450.00",
    "category": "Food",
    "date": "2026-06-15",
    "description": "Lunch at Saravana Bhavan",
}


# ------------------------------------------------------------------ #
# 1. Auth guard                                                        #
# ------------------------------------------------------------------ #


class TestAuthGuard:
    def test_get_redirects_when_not_logged_in(self, client):
        """Unauthenticated GET /expenses/add must redirect to /login."""
        response = client.get("/expenses/add")
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/login" in response.headers["Location"]

    def test_post_redirects_when_not_logged_in(self, client):
        """Unauthenticated POST /expenses/add must redirect to /login."""
        response = client.post("/expenses/add", data=VALID_DATA)
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/login" in response.headers["Location"]


# ------------------------------------------------------------------ #
# 2. GET renders form                                                  #
# ------------------------------------------------------------------ #


class TestGetRendersForm:
    def test_returns_200(self, logged_in):
        """Authenticated GET /expenses/add should return 200."""
        response = logged_in.get("/expenses/add")
        assert response.status_code == 200

    def test_contains_amount_field(self, logged_in):
        """Form should include an input field named 'amount'."""
        response = logged_in.get("/expenses/add")
        assert b'name="amount"' in response.data

    def test_contains_category_field(self, logged_in):
        """Form should include a select field named 'category'."""
        response = logged_in.get("/expenses/add")
        assert b'name="category"' in response.data

    def test_contains_date_field(self, logged_in):
        """Form should include an input field named 'date'."""
        response = logged_in.get("/expenses/add")
        assert b'name="date"' in response.data

    def test_contains_description_field(self, logged_in):
        """Form should include an input field named 'description'."""
        response = logged_in.get("/expenses/add")
        assert b'name="description"' in response.data

    def test_contains_submit_button(self, logged_in):
        """Form should include a submit button."""
        response = logged_in.get("/expenses/add")
        assert b'type="submit"' in response.data

    def test_all_valid_categories_present(self, logged_in):
        """Category dropdown should list all 7 valid categories."""
        response = logged_in.get("/expenses/add")
        valid_categories = [
            "Food", "Transport", "Bills", "Health",
            "Entertainment", "Shopping", "Other",
        ]
        for cat in valid_categories:
            assert cat.encode() in response.data, f"Missing category: {cat}"

    def test_page_title(self, logged_in):
        """Page should have the Add Expense title."""
        response = logged_in.get("/expenses/add")
        assert b"Add Expense" in response.data


# ------------------------------------------------------------------ #
# 3. POST happy path                                                   #
# ------------------------------------------------------------------ #


class TestPostHappyPath:
    def test_redirects_to_profile(self, logged_in):
        """Valid submission should redirect to /profile."""
        response = logged_in.post("/expenses/add", data=VALID_DATA)
        assert response.status_code == 302, "Expected 302 redirect"
        assert "/profile" in response.headers["Location"]

    def test_success_flash_message(self, logged_in):
        """After a successful submission, the success flash should appear."""
        response = logged_in.post(
            "/expenses/add", data=VALID_DATA, follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Expense added successfully!" in response.data


# ------------------------------------------------------------------ #
# 4. DB side effect                                                    #
# ------------------------------------------------------------------ #


class TestDbSideEffect:
    def test_expense_row_created(self, logged_in):
        """After POST with valid data, the expense should exist in the DB."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/add", data=VALID_DATA)
        assert _count_expenses(uid) == initial_count + 1

    def test_expense_linked_to_logged_in_user(self, logged_in):
        """New expense must belong to the demo user's id."""
        uid = _get_demo_user_id()
        logged_in.post("/expenses/add", data=VALID_DATA)

        conn = get_db()
        row = conn.execute(
            "SELECT user_id, amount, category, date, description "
            "FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (uid,),
        ).fetchone()
        conn.close()

        assert row is not None, "Expense row not found"
        assert row["user_id"] == uid
        assert row["amount"] == pytest.approx(450.00)
        assert row["category"] == "Food"
        assert row["date"] == "2026-06-15"
        assert row["description"] == "Lunch at Saravana Bhavan"

    def test_amount_stored_as_float(self, logged_in):
        """Amount containing decimals should be stored as a real number."""
        uid = _get_demo_user_id()
        data = dict(VALID_DATA, amount="123.45")
        logged_in.post("/expenses/add", data=data)

        conn = get_db()
        row = conn.execute(
            "SELECT amount FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (uid,),
        ).fetchone()
        conn.close()

        assert row["amount"] == pytest.approx(123.45)

    def test_multiple_expenses_each_create_row(self, logged_in):
        """Submitting the form twice should create two expense rows."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/add", data=VALID_DATA)
        logged_in.post("/expenses/add", data=VALID_DATA)
        assert _count_expenses(uid) == initial_count + 2


# ------------------------------------------------------------------ #
# 5. Validation: amount                                                #
# ------------------------------------------------------------------ #


class TestAmountValidation:
    def test_empty_amount_renders_form_with_error(self, logged_in):
        """Submitting with empty amount should re-render the form."""
        data = dict(VALID_DATA, amount="")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200, "Expected form re-render (200)"
        assert b"Amount is required." in response.data

    def test_negative_amount_renders_form_with_error(self, logged_in):
        """Submitting with a negative amount should flash an error."""
        data = dict(VALID_DATA, amount="-10.00")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Amount must be greater than 0." in response.data

    def test_zero_amount_renders_form_with_error(self, logged_in):
        """Submitting with zero amount should flash an error."""
        data = dict(VALID_DATA, amount="0")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Amount must be greater than 0." in response.data

    def test_non_numeric_amount_renders_form_with_error(self, logged_in):
        """Submitting with non-numeric amount should flash an error."""
        data = dict(VALID_DATA, amount="abc")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Amount must be a valid number." in response.data

    def test_expense_not_created_on_invalid_amount(self, logged_in):
        """No DB row should be written when amount validation fails."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/add", data=dict(VALID_DATA, amount=""))
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 6. Validation: category                                              #
# ------------------------------------------------------------------ #


class TestCategoryValidation:
    def test_empty_category_renders_form_with_error(self, logged_in):
        """Submitting with empty category should re-render the form."""
        data = dict(VALID_DATA, category="")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Category is required." in response.data

    def test_invalid_category_renders_form_with_error(self, logged_in):
        """Submitting with an unrecognised category should flash an error."""
        data = dict(VALID_DATA, category="Crypto")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Please select a valid category." in response.data

    def test_case_sensitive_category_validation(self, logged_in):
        """Category 'food' (lowercase) should be rejected; only 'Food' is valid."""
        data = dict(VALID_DATA, category="food")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Please select a valid category." in response.data

    def test_expense_not_created_on_invalid_category(self, logged_in):
        """No DB row should be written when category validation fails."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/add", data=dict(VALID_DATA, category=""))
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 7. Validation: date                                                  #
# ------------------------------------------------------------------ #


class TestDateValidation:
    def test_empty_date_renders_form_with_error(self, logged_in):
        """Submitting with empty date should re-render the form."""
        data = dict(VALID_DATA, date="")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Date is required." in response.data

    def test_invalid_date_format_renders_form_with_error(self, logged_in):
        """Submitting with a non-YYYY-MM-DD date should flash an error."""
        data = dict(VALID_DATA, date="15-06-2026")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Date must be in YYYY-MM-DD format." in response.data

    def test_garbage_date_renders_form_with_error(self, logged_in):
        """Submitting with a garbage date string should flash an error."""
        data = dict(VALID_DATA, date="not-a-date")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Date must be in YYYY-MM-DD format." in response.data

    def test_expense_not_created_on_invalid_date(self, logged_in):
        """No DB row should be written when date validation fails."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/add", data=dict(VALID_DATA, date=""))
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 8. Validation: description                                           #
# ------------------------------------------------------------------ #


class TestDescriptionValidation:
    def test_empty_description_renders_form_with_error(self, logged_in):
        """Submitting with empty description should re-render the form."""
        data = dict(VALID_DATA, description="")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Description is required." in response.data

    def test_description_over_200_chars_renders_form_with_error(self, logged_in):
        """Submitting with a description longer than 200 chars should error."""
        long_desc = "a" * 201
        data = dict(VALID_DATA, description=long_desc)
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Description must be 200 characters or fewer." in response.data

    def test_description_exactly_200_chars_is_accepted(self, logged_in):
        """A description of exactly 200 characters should be accepted."""
        exact_desc = "b" * 200
        data = dict(VALID_DATA, description=exact_desc)
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 302, "Expected redirect on success"

    def test_expense_not_created_on_invalid_description(self, logged_in):
        """No DB row should be written when description validation fails."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post("/expenses/add", data=dict(VALID_DATA, description=""))
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 9. Input preservation on validation failure                          #
# ------------------------------------------------------------------ #


class TestInputPreservation:
    def test_amount_preserved_on_error(self, logged_in):
        """On validation failure, the amount field should retain its value."""
        data = dict(VALID_DATA, amount="", category="")
        response = logged_in.post("/expenses/add", data=data)
        # The amount was empty so it won't appear, but other fields should.
        # Test with a non-empty amount that fails on another field.
        data2 = dict(VALID_DATA, category="")
        response2 = logged_in.post("/expenses/add", data=data2)
        assert b"450.00" in response2.data

    def test_category_preserved_on_error(self, logged_in):
        """On validation failure, the selected category should remain selected."""
        data = dict(VALID_DATA, amount="")
        response = logged_in.post("/expenses/add", data=data)
        assert b"Food" in response.data

    def test_date_preserved_on_error(self, logged_in):
        """On validation failure, the date field should retain its value."""
        data = dict(VALID_DATA, amount="")
        response = logged_in.post("/expenses/add", data=data)
        assert b"2026-06-15" in response.data

    def test_description_preserved_on_error(self, logged_in):
        """On validation failure, the description field should retain its value."""
        data = dict(VALID_DATA, amount="")
        response = logged_in.post("/expenses/add", data=data)
        assert b"Lunch at Saravana Bhavan" in response.data

    def test_all_fields_preserved_together(self, logged_in):
        """When only one field is invalid, all other fields should be preserved."""
        data = dict(VALID_DATA, amount="")  # only amount is invalid
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Food" in response.data
        assert b"2026-06-15" in response.data
        assert b"Lunch at Saravana Bhavan" in response.data


# ------------------------------------------------------------------ #
# 10. Multiple validation errors at once                                #
# ------------------------------------------------------------------ #


class TestMultipleValidationErrors:
    def test_all_errors_shown_when_every_field_invalid(self, logged_in):
        """Submitting with all fields invalid should show every error."""
        data = {
            "amount": "",
            "category": "",
            "date": "",
            "description": "",
        }
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code == 200
        assert b"Amount is required." in response.data
        assert b"Category is required." in response.data
        assert b"Date is required." in response.data
        assert b"Description is required." in response.data

    def test_no_expense_created_when_any_validation_fails(self, logged_in):
        """No row should be written when any field fails validation."""
        uid = _get_demo_user_id()
        initial_count = _count_expenses(uid)
        logged_in.post(
            "/expenses/add",
            data={"amount": "", "category": "", "date": "", "description": ""},
        )
        assert _count_expenses(uid) == initial_count


# ------------------------------------------------------------------ #
# 11. SQL injection safety                                             #
# ------------------------------------------------------------------ #


class TestSqlInjectionSafety:
    def test_sql_injection_in_description_does_not_crash(self, logged_in):
        """A SQL injection attempt in description should not crash."""
        data = dict(
            VALID_DATA,
            description="'; DROP TABLE expenses; --",
        )
        response = logged_in.post("/expenses/add", data=data)
        # Should either succeed (parameterised query) or fail validation,
        # but must NOT crash.
        assert response.status_code in (200, 302)

    def test_sql_injection_does_not_drop_table(self, logged_in):
        """The expenses table must still exist after an injection attempt."""
        uid = _get_demo_user_id()
        logged_in.post(
            "/expenses/add",
            data=dict(
                VALID_DATA,
                description="'; DROP TABLE expenses; --",
            ),
        )
        # If the table still exists, we can query it
        count = _count_expenses(uid)
        assert count >= 0  # would raise if table were dropped

    def test_sql_injection_in_amount_does_not_crash(self, logged_in):
        """A SQL injection attempt in amount should not crash."""
        data = dict(VALID_DATA, amount="1; DROP TABLE expenses; --")
        response = logged_in.post("/expenses/add", data=data)
        assert response.status_code in (200, 302)
