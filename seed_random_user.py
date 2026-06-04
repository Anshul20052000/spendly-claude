"""Insert a single dummy user with a random Indian name into the Spendly DB.

Idempotent on email — if the generated email already exists, regenerate and retry.
"""

import random
import sys
from datetime import datetime

from database.db import get_db
from werkzeug.security import generate_password_hash

# A diverse pool of common Indian first + last names spanning regions.
# First names cover North, South, East, West India + common unisex picks.
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Shaurya", "Atharv", "Advait", "Dhruv", "Kabir",
    "Ananya", "Diya", "Saanvi", "Aanya", "Pari", "Aadhya", "Myra", "Anika",
    "Aaradhya", "Riya", "Khushi", "Ishita", "Meera", "Priya", "Neha",
    "Rahul", "Rohan", "Karan", "Vikram", "Amit", "Suresh", "Rajesh", "Manoj",
    "Sneha", "Pooja", "Kavya", "Divya", "Lakshmi", "Sita", "Geeta", "Asha",
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Iyer", "Nair", "Menon", "Pillai",
    "Gupta", "Mishra", "Joshi", "Kapoor", "Mehta", "Shah", "Desai", "Modi",
    "Banerjee", "Mukherjee", "Chatterjee", "Bose", "Das", "Sen", "Roy",
    "Khan", "Ahmed", "Hussain", "Sheikh", "Ansari", "Siddiqui",
    "Rao", "Naidu", "Shetty", "Hegde", "Kamath", "Bhat",
    "Kaur", "Singh", "Dhillon", "Sandhu", "Gill", "Brar",
]


def generate_user():
    """Build a candidate user dict with a random Indian name and derived email."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    suffix = random.randint(10, 999)
    email = f"{first.lower()}.{last.lower()}{suffix}@gmail.com"
    return {
        "name": name,
        "email": email,
        "password_hash": generate_password_hash("password123"),
        "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
    }


def email_exists(conn, email):
    row = conn.execute(
        "SELECT 1 FROM users WHERE email = ?", (email,)
    ).fetchone()
    return row is not None


def main():
    conn = get_db()
    try:
        # Make sure the schema exists before we query it.
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            """
        )
        conn.commit()

        for attempt in range(50):
            user = generate_user()
            if not email_exists(conn, user["email"]):
                break
        else:
            print("Failed to generate a unique email after 50 attempts.", file=sys.stderr)
            sys.exit(1)

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user["name"], user["email"], user["password_hash"], user["created_at"]),
        )
        conn.commit()
        new_id = cursor.lastrowid

        print("Dummy user created successfully")
        print(f"  id:    {new_id}")
        print(f"  name:  {user['name']}")
        print(f"  email: {user['email']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
