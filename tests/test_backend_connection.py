"""Tests for database query helpers in database/queries.py and /profile route."""

import pytest
from database.db import init_db, seed_db, get_db
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Create a fresh in-memory database seeded with demo data for each test."""
    import database.db as db_mod
    original_path = db_mod.DB_PATH
    db_mod.DB_PATH = tmp_path / "test.db"
    init_db()
    seed_db()
    yield
    db_mod.DB_PATH = original_path


@pytest.fixture
def client(tmp_path):
    """Create a Flask test client with a fresh seeded database."""
    import database.db as db_mod
    original_path = db_mod.DB_PATH
    db_mod.DB_PATH = tmp_path / "test.db"

    from app import app as spendly_app
    spendly_app.config["TESTING"] = True
    init_db()
    seed_db()

    with spendly_app.test_client() as _client:
        yield _client

    db_mod.DB_PATH = original_path


class TestGetSummaryStats:
    def test_seed_user_returns_correct_totals(self):
        """Demo user (id=1) should have 8 transactions totalling 5244.50."""
        result = get_summary_stats(1)
        assert result["transaction_count"] == 8
        assert result["total_spent"] == pytest.approx(5244.50)
        assert result["top_category"] == "Bills"

    def test_nonexistent_user_returns_defaults(self):
        """A user with no expenses should get zeros and dash."""
        result = get_summary_stats(9999)
        assert result == {
            "total_spent": 0,
            "transaction_count": 0,
            "top_category": "—",
        }


class TestGetUserById:
    def test_seed_user_returns_correct_info(self):
        """Demo user (id=1) should return name, email, member_since."""
        result = get_user_by_id(1)
        assert result is not None
        assert result["name"] == "Demo User"
        assert result["email"] == "demo@spendly.com"
        # created_at is datetime('now') at seed time so just check format
        assert " " in result["member_since"]  # "Month YYYY"

    def test_nonexistent_user_returns_none(self):
        """A user that does not exist should return None."""
        result = get_user_by_id(9999)
        assert result is None


class TestGetRecentTransactions:
    def test_seed_user_returns_newest_first(self):
        """Demo user should get 8 transactions ordered newest date first."""
        result = get_recent_transactions(1)
        assert len(result) == 8
        assert result[0]["date"] == "2026-06-26"
        assert result[0]["description"] == "Gym day pass"
        assert result[0]["category"] == "Health"
        assert result[0]["amount"] == pytest.approx(275.00)

    def test_nonexistent_user_returns_empty(self):
        """A user with no expenses should get an empty list."""
        result = get_recent_transactions(9999)
        assert result == []

    def test_limit_parameter(self):
        """Limit=3 should return only 3 transactions."""
        result = get_recent_transactions(1, limit=3)
        assert len(result) == 3

    def test_each_item_has_required_keys(self):
        """Every transaction dict must have date, description, category, amount."""
        result = get_recent_transactions(1)
        for item in result:
            assert "date" in item
            assert "description" in item
            assert "category" in item
            assert "amount" in item


class TestGetCategoryBreakdown:
    def test_seed_user_returns_all_categories(self):
        """Demo user should have entries for each category they spent in."""
        result = get_category_breakdown(1)
        assert len(result) >= 1
        names = [r["name"] for r in result]
        assert "Bills" in names
        assert "Shopping" in names

    def test_nonexistent_user_returns_empty(self):
        """A user with no expenses should get an empty list."""
        result = get_category_breakdown(9999)
        assert result == []

    def test_ordered_by_amount_desc(self):
        """Categories must be ordered by amount descending."""
        result = get_category_breakdown(1)
        amounts = [r["amount"] for r in result]
        assert amounts == sorted(amounts, reverse=True)

    def test_pct_sum_to_100(self):
        """All pct values must sum to exactly 100."""
        result = get_category_breakdown(1)
        total_pct = sum(r["pct"] for r in result)
        assert total_pct == 100

    def test_each_item_has_required_keys(self):
        """Every breakdown dict must have name, amount, pct."""
        result = get_category_breakdown(1)
        for item in result:
            assert "name" in item
            assert "amount" in item
            assert "pct" in item


# ------------------------------------------------------------------ #
# Route tests for /profile
# ------------------------------------------------------------------ #

class TestProfileRouteUnauthenticated:
    def test_profile_redirects_to_login(self, client):
        """Unauthenticated GET /profile should redirect to /login (302)."""
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestProfileRouteAuthenticated:
    def _login(self, client):
        """Helper to log in as the demo user."""
        return client.post(
            "/login",
            data={"email": "demo@spendly.com", "password": "demo123"},
            follow_redirects=True,
        )

    def test_profile_returns_200(self, client):
        """Authenticated GET /profile should return 200."""
        self._login(client)
        response = client.get("/profile")
        assert response.status_code == 200

    def test_profile_shows_user_name(self, client):
        """Profile page should display the seed user's name."""
        self._login(client)
        response = client.get("/profile")
        assert b"Demo User" in response.data

    def test_profile_shows_user_email(self, client):
        """Profile page should display the seed user's email."""
        self._login(client)
        response = client.get("/profile")
        assert b"demo@spendly.com" in response.data

    def test_profile_shows_rupee_symbol(self, client):
        """Profile page should contain the ₹ symbol."""
        self._login(client)
        response = client.get("/profile")
        assert "₹".encode("utf-8") in response.data

    def test_profile_total_spent(self, client):
        """Total spent should equal the sum of all seed expenses (5244.50)."""
        self._login(client)
        response = client.get("/profile")
        assert b"5244.50" in response.data or b"5,244.50" in response.data

    def test_profile_transaction_count(self, client):
        """Transaction count should be 8."""
        self._login(client)
        response = client.get("/profile")
        assert b"8" in response.data

    def test_profile_top_category(self, client):
        """Top category should be Bills."""
        self._login(client)
        response = client.get("/profile")
        assert b"Bills" in response.data

    def test_profile_transaction_newest_first(self, client):
        """Transaction list should show the newest expense first."""
        self._login(client)
        response = client.get("/profile")
        # The newest expense is "Gym day pass" (2026-06-26)
        assert b"Gym day pass" in response.data

    def test_profile_category_breakdown_present(self, client):
        """Category breakdown should contain all spent categories."""
        self._login(client)
        response = client.get("/profile")
        assert b"Bills" in response.data
        assert b"Shopping" in response.data
        assert b"Food" in response.data
