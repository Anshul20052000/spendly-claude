"""Pure query helpers for the Spendly profile page.

Each function opens its own connection via get_db(), executes
parameterised SQL, and returns plain dicts/lists — no Flask imports.
"""

from database.db import get_db


def get_user_by_id(user_id):
    """Return a dict with name, email, member_since for the given user_id.

    Returns None if the user does not exist.
    member_since is formatted as 'Month YYYY' (e.g. 'January 2026').
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        # Parse 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD' and format as 'Month YYYY'
        date_str = row["created_at"][:10]
        year, month, _ = date_str.split("-")
        MONTH_NAMES = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        member_since = f"{MONTH_NAMES[int(month) - 1]} {year}"
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "member_since": member_since,
        }
    finally:
        conn.close()


def get_summary_stats(user_id):
    """Return a dict with total_spent, transaction_count, top_category.

    If the user has no expenses, returns:
        {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS transaction_count, "
            "       COALESCE(SUM(amount), 0) AS total_spent, "
            "       (SELECT category FROM expenses "
            "        WHERE user_id = ? "
            "        GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1) AS top_category "
            "FROM expenses WHERE user_id = ?",
            (user_id, user_id),
        ).fetchone()

        if row["transaction_count"] == 0:
            return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}

        return {
            "total_spent": row["total_spent"],
            "transaction_count": row["transaction_count"],
            "top_category": row["top_category"],
        }
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=10):
    """Return a list of dicts for the user's most recent expenses.

    Each dict has: date, description, category, amount.
    Ordered newest-first. Returns empty list if no expenses.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount "
            "FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [
            {
                "date": row["date"],
                "description": row["description"],
                "category": row["category"],
                "amount": row["amount"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_category_breakdown(user_id):
    """Return a list of dicts with name, amount, pct for each category.

    Ordered by amount descending. pct values are integers summing to 100.
    Returns empty list if no expenses.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total "
            "FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()

        if not rows:
            return []

        totals = [(row["category"], row["total"]) for row in rows]
        grand_total = sum(t for _, t in totals)

        # Compute rounded percentages
        breakdown = []
        running_pct = 0
        for i, (name, amount) in enumerate(totals):
            if i == len(totals) - 1:
                # Last category absorbs rounding remainder so sum = 100
                pct = 100 - running_pct
            else:
                pct = round((amount / grand_total) * 100)
                running_pct += pct
            breakdown.append({
                "name": name,
                "amount": amount,
                "pct": pct,
            })

        return breakdown
    finally:
        conn.close()
