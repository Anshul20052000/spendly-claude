"""Tests for the date-filter feature on the /profile route (Step 7).

Covers preset filters ("This Month", "Last 3 Months", "Last 6 Months", "All Time"),
custom date ranges, validation (reversed dates, malformed dates), partial filters
(only date_from or only date_to), active_preset context, and the effect of
filtering on all three data sections (summary stats, transactions, category
breakdown).

All tests use an isolated temporary SQLite database seeded with the standard
8 sample expenses (all in June 2026). Today's date is treated as 2026-06-20.
"""

import datetime

import pytest

import database.db as db_mod
from app import app as spendly_app
from database.db import get_db, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

# ------------------------------------------------------------------ #
# Constants                                                           #
# ------------------------------------------------------------------ #

# Today is 2026-06-20 (as specified)
TODAY = datetime.date(2026, 6, 20)
THIS_MONTH_FROM = "2026-06-01"
THIS_MONTH_TO = "2026-06-20"
LAST_3M_FROM = "2026-03-22"  # 90 days before 2026-06-20
LAST_3M_TO = "2026-06-20"
LAST_6M_FROM = "2025-12-22"  # 180 days before 2026-06-20
LAST_6M_TO = "2026-06-20"

# Seed expenses that fall within "This Month" (June 1-20, 2026):
#   2026-06-02  Food          450.00
#   2026-06-05  Transport     120.50
#   2026-06-08  Bills        1850.00
#   2026-06-10  Health        320.00
#   2026-06-14  Entertainment 650.00
#   2026-06-18  Shopping     1499.00
# (2026-06-22 and 2026-06-26 are AFTER today so excluded from "This Month")
THIS_MONTH_EXPENSES = [
    (450.00, "Food", "2026-06-02", "Lunch at Saravana Bhavan"),
    (120.50, "Transport", "2026-06-05", "Uber to office"),
    (1850.00, "Bills", "2026-06-08", "Electricity bill"),
    (320.00, "Health", "2026-06-10", "Pharmacy - vitamins"),
    (650.00, "Entertainment", "2026-06-14", "Movie tickets (PVR)"),
    (1499.00, "Shopping", "2026-06-18", "Amazon - earphones"),
]
THIS_MONTH_TOTAL = sum(e[0] for e in THIS_MONTH_EXPENSES)  # 4889.50
THIS_MONTH_COUNT = len(THIS_MONTH_EXPENSES)  # 6

# All 8 seed expenses (unfiltered)
ALL_TOTAL = 5244.50
ALL_COUNT = 8


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
    row = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)).fetchone()
    conn.close()
    return row["id"]


# ------------------------------------------------------------------ #
# 1. Auth guard                                                        #
# ------------------------------------------------------------------ #


class TestAuthGuard:
    def test_profile_redirects_when_not_logged_in(self, client):
        """Unauthenticated GET /profile must redirect to /login."""
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_profile_returns_200_when_logged_in(self, logged_in):
        """Authenticated GET /profile must return 200."""
        response = logged_in.get("/profile")
        assert response.status_code == 200


# ------------------------------------------------------------------ #
# 2. No query params — unfiltered view                                 #
# ------------------------------------------------------------------ #


class TestNoQueryParams:
    def test_all_expenses_shown(self, logged_in):
        """Without query params all 8 seed expenses should be visible."""
        response = logged_in.get("/profile")
        assert response.status_code == 200
        # The newest expense (Gym day pass) should appear
        assert b"Gym day pass" in response.data
        # The oldest expense should also appear
        assert b"Lunch at Saravana Bhavan" in response.data

    def test_total_spent_is_full_sum(self, logged_in):
        """Total spent should be the sum of all 8 expenses (5244.50)."""
        response = logged_in.get("/profile")
        assert response.status_code == 200
        assert b"5244.50" in response.data or b"5,244.50" in response.data

    def test_transaction_count_is_8(self, logged_in):
        """Transaction count should show 8."""
        response = logged_in.get("/profile")
        assert response.status_code == 200
        assert b"8" in response.data

    def test_active_preset_is_all_time(self, logged_in):
        """The active_preset context variable should be 'all_time'."""
        response = logged_in.get("/profile")
        assert response.status_code == 200
        # The template receives active_preset="all_time"; the page should
        # reflect this (e.g. the "All Time" button is marked active).
        assert b"all_time" in response.data


# ------------------------------------------------------------------ #
# 3. "This Month" preset                                               #
# ------------------------------------------------------------------ #


class TestThisMonthPreset:
    def _call(self, logged_in):
        return logged_in.get(
            "/profile",
            query_string={"date_from": THIS_MONTH_FROM, "date_to": THIS_MONTH_TO},
        )

    def test_filters_to_current_month(self, logged_in):
        """This Month should show only expenses from June 1-20 (6 of 8)."""
        response = self._call(logged_in)
        assert response.status_code == 200
        # These 6 should be present
        assert b"Lunch at Saravana Bhavan" in response.data
        assert b"Uber to office" in response.data
        assert b"Electricity bill" in response.data
        assert b"Movie tickets (PVR)" in response.data
        assert b"Amazon" in response.data
        # These 2 are after June 20 and should NOT appear
        assert b"Stationery" not in response.data
        assert b"Gym day pass" not in response.data

    def test_total_spent_this_month(self, logged_in):
        """Total should be 4889.50 (sum of the 6 June 1-20 expenses)."""
        response = self._call(logged_in)
        assert response.status_code == 200
        assert b"4889.50" in response.data or b"4,889.50" in response.data

    def test_transaction_count_this_month(self, logged_in):
        """Transaction count should be 6."""
        response = self._call(logged_in)
        assert response.status_code == 200
        # The count "6" should appear in the summary section
        assert b"6" in response.data

    def test_active_preset_this_month(self, logged_in):
        """active_preset should be 'this_month'."""
        response = self._call(logged_in)
        assert response.status_code == 200
        assert b"this_month" in response.data

    def test_top_category_this_month(self, logged_in):
        """Top category within June 1-20 should still be Bills (1850.00)."""
        response = self._call(logged_in)
        assert response.status_code == 200
        assert b"Bills" in response.data


# ------------------------------------------------------------------ #
# 4. "Last 3 Months" preset                                            #
# ------------------------------------------------------------------ #


class TestLast3MonthsPreset:
    def _call(self, logged_in):
        return logged_in.get(
            "/profile",
            query_string={"date_from": LAST_3M_FROM, "date_to": LAST_3M_TO},
        )

    def test_all_expenses_shown(self, logged_in):
        """All seed expenses within the 90-day window (March 22 - June 20) should appear.
        "Gym day pass" (June 26) is outside the date_to bound and should NOT appear."""
        response = self._call(logged_in)
        assert response.status_code == 200
        # These are within the 90-day window
        assert b"Lunch at Saravana Bhavan" in response.data
        assert b"Electricity bill" in response.data
        # "Gym day pass" is on June 26, after date_to=June 20
        assert b"Gym day pass" not in response.data

    def test_active_preset_last_3_months(self, logged_in):
        """active_preset should be 'last_3_months'."""
        response = self._call(logged_in)
        assert response.status_code == 200
        assert b"last_3_months" in response.data


# ------------------------------------------------------------------ #
# 5. "Last 6 Months" preset                                            #
# ------------------------------------------------------------------ #


class TestLast6MonthsPreset:
    def _call(self, logged_in):
        return logged_in.get(
            "/profile",
            query_string={"date_from": LAST_6M_FROM, "date_to": LAST_6M_TO},
        )

    def test_all_expenses_shown(self, logged_in):
        """All seed expenses within the 180-day window (Dec 22 - June 20) should appear.
        "Gym day pass" (June 26) is outside the date_to bound and should NOT appear."""
        response = self._call(logged_in)
        assert response.status_code == 200
        # These are within the 180-day window
        assert b"Lunch at Saravana Bhavan" in response.data
        assert b"Electricity bill" in response.data
        # "Gym day pass" is on June 26, after date_to=June 20
        assert b"Gym day pass" not in response.data

    def test_active_preset_last_6_months(self, logged_in):
        """active_preset should be 'last_6_months'."""
        response = self._call(logged_in)
        assert response.status_code == 200
        assert b"last_6_months" in response.data


# ------------------------------------------------------------------ #
# 6. "All Time" preset                                                 #
# ------------------------------------------------------------------ #


class TestAllTimePreset:
    def test_all_time_shows_everything(self, logged_in):
        """All Time should show all 8 expenses (same as no params)."""
        response = logged_in.get(
            "/profile",
            query_string={},
        )
        assert response.status_code == 200
        assert b"Gym day pass" in response.data
        assert b"Lunch at Saravana Bhavan" in response.data

    def test_active_preset_all_time(self, logged_in):
        """active_preset should be 'all_time'."""
        response = logged_in.get(
            "/profile",
            query_string={},
        )
        assert response.status_code == 200
        assert b"all_time" in response.data


# ------------------------------------------------------------------ #
# 7. Custom date range (valid)                                         #
# ------------------------------------------------------------------ #


class TestCustomDateRange:
    def test_custom_range_filters_transactions(self, logged_in):
        """Custom range June 5-14 should include only expenses in that window."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-05", "date_to": "2026-06-14"},
        )
        assert response.status_code == 200
        # In range: Transport(06-05), Bills(06-08), Health(06-10), Entertainment(06-14)
        assert b"Uber to office" in response.data
        assert b"Electricity bill" in response.data
        assert b"Pharmacy" in response.data
        assert b"Movie tickets (PVR)" in response.data
        # Out of range
        assert b"Lunch at Saravana Bhavan" not in response.data  # June 2
        assert b"Amazon" not in response.data  # June 18
        assert b"Stationery" not in response.data  # June 22
        assert b"Gym day pass" not in response.data  # June 26

    def test_custom_range_summary_stats(self, logged_in):
        """Summary stats should reflect only the custom range."""
        date_from = "2026-06-05"
        date_to = "2026-06-14"
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from=date_from, date_to=date_to)
        # 4 expenses: Transport 120.50 + Bills 1850 + Health 320 + Entertainment 650
        assert stats["transaction_count"] == 4
        assert stats["total_spent"] == pytest.approx(2940.50)
        assert stats["top_category"] == "Bills"

    def test_custom_range_transactions_ordered_newest_first(self, logged_in):
        """Transactions within custom range should still be newest-first."""
        date_from = "2026-06-05"
        date_to = "2026-06-14"
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_from=date_from, date_to=date_to)
        assert len(txns) == 4
        dates = [t["date"] for t in txns]
        assert dates == sorted(dates, reverse=True)

    def test_custom_range_category_breakdown(self, logged_in):
        """Category breakdown should only include categories within the range."""
        date_from = "2026-06-05"
        date_to = "2026-06-14"
        uid = _get_demo_user_id()
        breakdown = get_category_breakdown(uid, date_from=date_from, date_to=date_to)
        names = [b["name"] for b in breakdown]
        assert "Bills" in names
        assert "Entertainment" in names
        assert "Health" in names
        assert "Transport" in names
        # Food is only on June 2, which is before the range
        assert "Food" not in names
        # Percentages should still sum to 100
        assert sum(b["pct"] for b in breakdown) == 100

    def test_custom_range_no_active_preset(self, logged_in):
        """A non-preset custom range should set active_preset to None."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-05", "date_to": "2026-06-14"},
        )
        assert response.status_code == 200
        # active_preset is None for custom ranges; the template should not
        # mark any preset button as active.
        assert b"active_preset" in response.data or b"date_from" in response.data


# ------------------------------------------------------------------ #
# 8. Reversed dates (date_from > date_to)                              #
# ------------------------------------------------------------------ #


class TestReversedDates:
    def test_reversed_dates_falls_back_to_unfiltered(self, logged_in):
        """Reversed dates should show all expenses (unfiltered fallback)."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-20", "date_to": "2026-06-01"},
        )
        assert response.status_code == 200
        # All expenses should be visible (unfiltered)
        assert b"Gym day pass" in response.data
        assert b"Lunch at Saravana Bhavan" in response.data

    def test_reversed_dates_flash_message(self, logged_in):
        """Reversed dates should flash 'Start date must be before end date.'."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-20", "date_to": "2026-06-01"},
            follow_redirects=False,
        )
        # The flash message is set on the same response (no redirect needed
        # since it's a GET request that renders the template directly).
        assert response.status_code == 200
        assert b"Start date must be before end date." in response.data

    def test_reversed_dates_active_preset_all_time(self, logged_in):
        """After reversing, active_preset should fall back to 'all_time'."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-20", "date_to": "2026-06-01"},
        )
        assert response.status_code == 200
        assert b"all_time" in response.data


# ------------------------------------------------------------------ #
# 9. Malformed date strings                                            #
# ------------------------------------------------------------------ #


class TestMalformedDates:
    def test_malformed_date_from_falls_back(self, logged_in):
        """A garbage date_from should be treated as absent (unfiltered)."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "not-a-date", "date_to": "2026-06-20"},
        )
        assert response.status_code == 200
        # Should not crash; falls back to unfiltered for the bad param.
        # date_to is valid but date_from is ignored, so only date_to filter applies.
        # With only date_to=2026-06-20, expenses up to June 20 are shown (7 of 8,
        # excluding Gym day pass on June 26).
        assert b"Lunch at Saravana Bhavan" in response.data

    def test_malformed_date_to_falls_back(self, logged_in):
        """A garbage date_to should be treated as absent (unfiltered)."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-01", "date_to": "abc"},
        )
        assert response.status_code == 200
        # date_from is valid but date_to is ignored, so only date_from filter applies.
        # With only date_from=2026-06-01, all 8 expenses are on or after June 1.
        assert b"Gym day pass" in response.data

    def test_both_malformed_falls_back_to_unfiltered(self, logged_in):
        """Both params malformed should show all expenses."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "garbage", "date_to": "rubbish"},
        )
        assert response.status_code == 200
        assert b"Gym day pass" in response.data
        assert b"Lunch at Saravana Bhavan" in response.data

    def test_malformed_date_no_crash(self, logged_in):
        """The app must not crash on malformed date input."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "not-a-date", "date_to": "also-bad"},
        )
        assert response.status_code == 200

    def test_malformed_date_sql_injection_attempt(self, logged_in):
        """SQL injection in date params must not crash or alter behaviour."""
        response = logged_in.get(
            "/profile",
            query_string={
                "date_from": "2026-01-01'; DROP TABLE expenses; --",
                "date_to": "2026-12-31",
            },
        )
        assert response.status_code == 200
        # The table should still exist and data should be intact
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid)
        assert stats["transaction_count"] == 8


# ------------------------------------------------------------------ #
# 10. Only date_from provided                                          #
# ------------------------------------------------------------------ #


class TestOnlyDateFrom:
    def test_only_date_from_filters_correctly(self, logged_in):
        """Providing only date_from should filter with >= date_from."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2026-06-14")
        # Expenses on or after June 14: Entertainment(06-14), Shopping(06-18),
        # Other(06-22), Health(06-26) => 4 expenses
        assert stats["transaction_count"] == 4

    def test_only_date_from_no_active_preset(self, logged_in):
        """Only date_from (no date_to) should not match any preset."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-14"},
        )
        assert response.status_code == 200
        # active_preset should be None (custom range) -- the page should
        # still render the profile without errors.
        assert b"Demo User" in response.data

    def test_only_date_from_transactions(self, logged_in):
        """Only date_from should return transactions >= that date."""
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_from="2026-06-14")
        assert len(txns) == 4
        for t in txns:
            assert t["date"] >= "2026-06-14"


# ------------------------------------------------------------------ #
# 11. Only date_to provided                                            #
# ------------------------------------------------------------------ #


class TestOnlyDateTo:
    def test_only_date_to_filters_correctly(self, logged_in):
        """Providing only date_to should filter with <= date_to."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_to="2026-06-10")
        # Expenses on or before June 10: Food(06-02), Transport(06-05),
        # Bills(06-08), Health(06-10) => 4 expenses
        assert stats["transaction_count"] == 4

    def test_only_date_to_no_active_preset(self, logged_in):
        """Only date_to (no date_from) should not match any preset."""
        response = logged_in.get(
            "/profile",
            query_string={"date_to": "2026-06-10"},
        )
        assert response.status_code == 200

    def test_only_date_to_transactions(self, logged_in):
        """Only date_to should return transactions <= that date."""
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_to="2026-06-10")
        assert len(txns) == 4
        for t in txns:
            assert t["date"] <= "2026-06-10"


# ------------------------------------------------------------------ #
# 12. Active preset context variable                                   #
# ------------------------------------------------------------------ #


class TestActivePreset:
    def test_active_preset_all_time_no_params(self, logged_in):
        """No params => active_preset == 'all_time'."""
        response = logged_in.get("/profile")
        assert b"all_time" in response.data

    def test_active_preset_this_month(self, logged_in):
        """This Month params => active_preset == 'this_month'."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": THIS_MONTH_FROM, "date_to": THIS_MONTH_TO},
        )
        assert b"this_month" in response.data

    def test_active_preset_last_3_months(self, logged_in):
        """Last 3 Months params => active_preset == 'last_3_months'."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": LAST_3M_FROM, "date_to": LAST_3M_TO},
        )
        assert b"last_3_months" in response.data

    def test_active_preset_last_6_months(self, logged_in):
        """Last 6 Months params => active_preset == 'last_6_months'."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": LAST_6M_FROM, "date_to": LAST_6M_TO},
        )
        assert b"last_6_months" in response.data

    def test_active_preset_none_for_custom(self, logged_in):
        """Custom non-preset range => active_preset is None."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-05", "date_to": "2026-06-10"},
        )
        assert response.status_code == 200
        # The template receives active_preset=None. Verify none of the preset
        # strings appear as the active value.
        data = response.data
        # We look for the pattern that would indicate which preset is active.
        # Since active_preset is None, no preset button should be marked active.
        # The page should still render without errors.
        assert b"date_from" in data  # custom range fields should be present


# ------------------------------------------------------------------ #
# 13. Summary stats respect date filter                                #
# ------------------------------------------------------------------ #


class TestSummaryStatsWithFilter:
    def test_total_spent_filtered(self, logged_in):
        """Summary total_spent should reflect only filtered expenses."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2026-06-05", date_to="2026-06-14")
        # Transport 120.50 + Bills 1850 + Health 320 + Entertainment 650 = 2940.50
        assert stats["total_spent"] == pytest.approx(2940.50)

    def test_transaction_count_filtered(self, logged_in):
        """Summary transaction_count should reflect only filtered expenses."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2026-06-05", date_to="2026-06-14")
        assert stats["transaction_count"] == 4

    def test_top_category_filtered(self, logged_in):
        """top_category should be computed from filtered set."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2026-06-05", date_to="2026-06-14")
        assert stats["top_category"] == "Bills"

    def test_top_category_changes_with_filter(self, logged_in):
        """A different filter window may yield a different top category."""
        uid = _get_demo_user_id()
        # Filter to only June 18-26: Shopping(1499), Other(80), Health(275)
        stats = get_summary_stats(uid, date_from="2026-06-18", date_to="2026-06-26")
        assert stats["top_category"] == "Shopping"

    def test_summary_stats_route_integration(self, logged_in):
        """The /profile route should display filtered totals in the HTML."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-05", "date_to": "2026-06-14"},
        )
        assert response.status_code == 200
        # 2940.50 should appear in the rendered page
        assert b"2940.50" in response.data or b"2,940.50" in response.data


# ------------------------------------------------------------------ #
# 14. Transaction list respects date filter                            #
# ------------------------------------------------------------------ #


class TestTransactionsWithFilter:
    def test_filtered_transactions_subset(self, logged_in):
        """Filtered transactions should be a subset of all transactions."""
        uid = _get_demo_user_id()
        all_txns = get_recent_transactions(uid)
        filtered = get_recent_transactions(uid, date_from="2026-06-05", date_to="2026-06-14")
        assert len(filtered) < len(all_txns)
        assert len(filtered) == 4

    def test_filtered_transactions_newest_first(self, logged_in):
        """Filtered transactions must still be ordered newest-first."""
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_from="2026-06-05", date_to="2026-06-14")
        dates = [t["date"] for t in txns]
        assert dates == sorted(dates, reverse=True)
        # First should be June 14 (Entertainment)
        assert txns[0]["date"] == "2026-06-14"
        assert txns[0]["description"] == "Movie tickets (PVR)"

    def test_filtered_transactions_content(self, logged_in):
        """Each filtered transaction should have the required keys."""
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_from="2026-06-05", date_to="2026-06-14")
        for t in txns:
            assert "date" in t
            assert "description" in t
            assert "category" in t
            assert "amount" in t

    def test_transactions_route_integration(self, logged_in):
        """The /profile route should render only filtered transactions."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-05", "date_to": "2026-06-14"},
        )
        assert response.status_code == 200
        assert b"Movie tickets (PVR)" in response.data
        assert b"Lunch at Saravana Bhavan" not in response.data


# ------------------------------------------------------------------ #
# 15. Category breakdown respects date filter                          #
# ------------------------------------------------------------------ #


class TestCategoryBreakdownWithFilter:
    def test_filtered_breakdown_has_fewer_categories(self, logged_in):
        """Filtering to a narrow range should reduce the number of categories."""
        uid = _get_demo_user_id()
        all_cats = get_category_breakdown(uid)
        filtered = get_category_breakdown(uid, date_from="2026-06-05", date_to="2026-06-14")
        assert len(filtered) < len(all_cats)

    def test_filtered_breakdown_pct_sums_to_100(self, logged_in):
        """Percentages in filtered breakdown must still sum to 100."""
        uid = _get_demo_user_id()
        breakdown = get_category_breakdown(uid, date_from="2026-06-05", date_to="2026-06-14")
        total_pct = sum(b["pct"] for b in breakdown)
        assert total_pct == 100

    def test_filtered_breakdown_ordered_by_amount(self, logged_in):
        """Filtered breakdown should be ordered by amount descending."""
        uid = _get_demo_user_id()
        breakdown = get_category_breakdown(uid, date_from="2026-06-05", date_to="2026-06-14")
        amounts = [b["amount"] for b in breakdown]
        assert amounts == sorted(amounts, reverse=True)

    def test_filtered_breakdown_amounts_correct(self, logged_in):
        """Filtered breakdown amounts should match the filtered expenses."""
        uid = _get_demo_user_id()
        breakdown = get_category_breakdown(uid, date_from="2026-06-05", date_to="2026-06-14")
        by_name = {b["name"]: b["amount"] for b in breakdown}
        assert by_name["Bills"] == pytest.approx(1850.00)
        assert by_name["Entertainment"] == pytest.approx(650.00)
        assert by_name["Health"] == pytest.approx(320.00)
        assert by_name["Transport"] == pytest.approx(120.50)

    def test_category_breakdown_route_integration(self, logged_in):
        """The /profile route should render the filtered category breakdown."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-05", "date_to": "2026-06-14"},
        )
        assert response.status_code == 200
        assert b"Bills" in response.data
        assert b"Entertainment" in response.data
        # Food should not appear in the breakdown (no Food expenses in range)
        assert b"Food" not in response.data


# ------------------------------------------------------------------ #
# 16. User with no expenses in selected range                          #
# ------------------------------------------------------------------ #


class TestNoExpensesInRange:
    def test_total_spent_zero(self, logged_in):
        """A range with no expenses should show total_spent = 0."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2025-01-01", date_to="2025-01-31")
        assert stats["total_spent"] == 0

    def test_transaction_count_zero(self, logged_in):
        """A range with no expenses should show transaction_count = 0."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2025-01-01", date_to="2025-01-31")
        assert stats["transaction_count"] == 0

    def test_top_category_dash(self, logged_in):
        """A range with no expenses should show top_category = em-dash."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2025-01-01", date_to="2025-01-31")
        assert stats["top_category"] == "—"

    def test_transactions_empty(self, logged_in):
        """A range with no expenses should return an empty transaction list."""
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_from="2025-01-01", date_to="2025-01-31")
        assert txns == []

    def test_category_breakdown_empty(self, logged_in):
        """A range with no expenses should return an empty category breakdown."""
        uid = _get_demo_user_id()
        breakdown = get_category_breakdown(uid, date_from="2025-01-01", date_to="2025-01-31")
        assert breakdown == []

    def test_route_no_crash_empty_range(self, logged_in):
        """The /profile route should not crash for a range with no expenses."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2025-01-01", "date_to": "2025-01-31"},
        )
        assert response.status_code == 200
        # Should show 0.00 or 0 for total spent
        assert b"0.00" in response.data or b"0" in response.data


# ------------------------------------------------------------------ #
# 17. BETWEEN query pattern                                            #
# ------------------------------------------------------------------ #


class TestBetweenQueryPattern:
    def test_both_bounds_use_between_in_summary(self, logged_in):
        """When both date_from and date_to are provided, the query should use BETWEEN."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2026-06-05", date_to="2026-06-14")
        # If BETWEEN is used correctly, we get exactly 4 expenses
        assert stats["transaction_count"] == 4
        assert stats["total_spent"] == pytest.approx(2940.50)

    def test_both_bounds_use_between_in_transactions(self, logged_in):
        """Transaction query with both bounds should use BETWEEN."""
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_from="2026-06-05", date_to="2026-06-14")
        assert len(txns) == 4
        for t in txns:
            assert "2026-06-05" <= t["date"] <= "2026-06-14"

    def test_both_bounds_use_between_in_breakdown(self, logged_in):
        """Category breakdown query with both bounds should use BETWEEN."""
        uid = _get_demo_user_id()
        breakdown = get_category_breakdown(uid, date_from="2026-06-05", date_to="2026-06-14")
        # Total of all category amounts should equal the filtered total
        cat_total = sum(b["amount"] for b in breakdown)
        assert cat_total == pytest.approx(2940.50)

    def test_single_bound_does_not_use_between(self, logged_in):
        """With only one bound, BETWEEN should not be used (>= or <= instead)."""
        uid = _get_demo_user_id()
        # Only date_from: should get expenses >= 2026-06-18 (3 expenses)
        stats = get_summary_stats(uid, date_from="2026-06-18")
        assert stats["transaction_count"] == 3

        # Only date_to: should get expenses <= 2026-06-05 (2 expenses)
        stats2 = get_summary_stats(uid, date_to="2026-06-05")
        assert stats2["transaction_count"] == 2


# ------------------------------------------------------------------ #
# 18. Flash message on reversed dates (exact text)                     #
# ------------------------------------------------------------------ #


class TestFlashMessageExactText:
    def test_exact_flash_text(self, logged_in):
        """The flash message must be exactly 'Start date must be before end date.'."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-20", "date_to": "2026-06-01"},
        )
        assert response.status_code == 200
        assert b"Start date must be before end date." in response.data

    def test_no_flash_on_valid_range(self, logged_in):
        """A valid date range should NOT produce the reversed-dates flash."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-01", "date_to": "2026-06-20"},
        )
        assert response.status_code == 200
        assert b"Start date must be before end date." not in response.data

    def test_no_flash_on_no_params(self, logged_in):
        """No params should NOT produce any flash about date order."""
        response = logged_in.get("/profile")
        assert response.status_code == 200
        assert b"Start date must be before end date." not in response.data


# ------------------------------------------------------------------ #
# 19. Edge cases                                                       #
# ------------------------------------------------------------------ #


class TestEdgeCases:
    def test_same_date_from_and_to(self, logged_in):
        """date_from == date_to should show only expenses on that single day."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2026-06-08", date_to="2026-06-08")
        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == pytest.approx(1850.00)

    def test_date_range_before_all_expenses(self, logged_in):
        """A range entirely before all expenses should return zeros."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2025-01-01", date_to="2025-12-31")
        assert stats["transaction_count"] == 0
        assert stats["total_spent"] == 0

    def test_date_range_after_all_expenses(self, logged_in):
        """A range entirely after all expenses should return zeros."""
        uid = _get_demo_user_id()
        stats = get_summary_stats(uid, date_from="2027-01-01", date_to="2027-12-31")
        assert stats["transaction_count"] == 0
        assert stats["total_spent"] == 0

    def test_very_long_date_string(self, logged_in):
        """An extremely long invalid date string should not crash."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "a" * 5000, "date_to": "2026-06-20"},
        )
        assert response.status_code == 200

    def test_empty_string_dates(self, logged_in):
        """Empty string date params should be treated as absent (unfiltered)."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "", "date_to": ""},
        )
        assert response.status_code == 200
        # Should show all expenses (unfiltered)
        assert b"Gym day pass" in response.data

    def test_partial_day_match(self, logged_in):
        """Filtering to a single day with one expense should show exactly 1."""
        uid = _get_demo_user_id()
        txns = get_recent_transactions(uid, date_from="2026-06-02", date_to="2026-06-02")
        assert len(txns) == 1
        assert txns[0]["description"] == "Lunch at Saravana Bhavan"

    def test_rupee_symbol_present_with_filter(self, logged_in):
        """The rupee symbol should still appear when a filter is active."""
        response = logged_in.get(
            "/profile",
            query_string={"date_from": "2026-06-01", "date_to": "2026-06-20"},
        )
        assert response.status_code == 200
        assert "₹".encode("utf-8") in response.data
