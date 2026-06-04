"""One-off seeder: insert <count> randomised expenses for <user_id>
spread randomly across the past <months> months.

Invoked from the /seed-expenses slash command. Uses get_db() from
database.db so the DB filename is never hardcoded, and runs every
insert in a single transaction — any failure rolls back the lot.
"""

import random
import sys
from datetime import date, timedelta

from database.db import get_db

# Category weights — Food most common; Health & Entertainment least.
# (category, weight, amount_min, amount_max, [descriptions])
CATEGORY_POOL = [
    (
        "Food", 30, 50, 800,
        [
            "Lunch at Saravana Bhavan", "Zomato — biryani", "Swiggy — paneer tikka",
            "Chai and samosa", "Dinner at Barbeque Nation", "Domino's pizza",
            "Street food — pani puri", "Filter coffee at Indian Coffee House",
            "Groceries from BigBasket", "Vegetables from local market",
            "McDonald's combo", "Masala dosa breakfast",
        ],
    ),
    (
        "Transport", 20, 20, 500,
        [
            "Uber to office", "Ola Auto ride", "Metro card recharge",
            "Petrol top-up", "Bus ticket", "Rapido bike taxi",
            "IRCTC train booking", "Parking fee at mall",
        ],
    ),
    (
        "Bills", 15, 200, 3000,
        [
            "Electricity bill", "Airtel postpaid", "Jio Fiber broadband",
            "Water bill", "Gas cylinder refill", "DTH recharge",
            "Society maintenance", "Netflix subscription",
        ],
    ),
    (
        "Shopping", 15, 200, 5000,
        [
            "Amazon — earphones", "Flipkart — t-shirt", "Myntra — kurta",
            "Decathlon — running shoes", "Reliance Digital — charger",
            "DMart — household items", "Lenskart — sunglasses",
            "Nykaa — skincare",
        ],
    ),
    (
        "Other", 10, 50, 1000,
        [
            "Stationery", "Birthday gift for cousin", "Temple donation",
            "Haircut at salon", "Dry cleaning", "Newspaper subscription",
        ],
    ),
    (
        "Health", 5, 100, 2000,
        [
            "Pharmacy — vitamins", "Gym day pass", "Apollo clinic consultation",
            "Dental checkup", "Yoga class fee", "Medical lab test",
        ],
    ),
    (
        "Entertainment", 5, 100, 1500,
        [
            "Movie tickets (PVR)", "BookMyShow — concert", "Spotify Premium",
            "Bowling at Smaaash", "Arcade games", "Hotstar subscription",
        ],
    ),
]


def random_date_within(months_back: int) -> str:
    """Pick a random date between today and ~months_back months ago (ISO yyyy-mm-dd)."""
    today = date.today()
    days_back = random.randint(0, months_back * 30)
    return (today - timedelta(days=days_back)).isoformat()


def build_expense(user_id: int, months: int) -> tuple:
    """Generate one (user_id, amount, category, date, description) tuple."""
    weights = [c[1] for c in CATEGORY_POOL]
    chosen = random.choices(CATEGORY_POOL, weights=weights, k=1)[0]
    category, _, amt_min, amt_max, descriptions = chosen
    amount = round(random.uniform(amt_min, amt_max), 2)
    return (user_id, amount, category, random_date_within(months), random.choice(descriptions))


def main(user_id: int, count: int, months: int) -> None:
    rows = [build_expense(user_id, months) for _ in range(count)]

    conn = get_db()
    try:
        conn.execute("BEGIN")
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Re-open read-only-ish to summarise the latest insert.
    conn = get_db()
    try:
        inserted = conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, count),
        ).fetchall()
        dates = [r["date"] for r in inserted]
        print(f"Inserted {len(inserted)} expenses for user_id={user_id}.")
        print(f"Date range: {min(dates)} → {max(dates)}")
        print("Sample of 5:")
        for r in inserted[:5]:
            print(f"  id={r['id']:>4}  ₹{r['amount']:>8.2f}  {r['category']:<14}  {r['date']}  {r['description']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
