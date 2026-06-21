from datetime import datetime, timedelta
from math import isfinite

from flask import Flask, abort, render_template, request, redirect, url_for, flash, session
import os

from database.db import (
    get_db, init_db, seed_db, create_user,
    get_user_by_email, create_expense, update_expense,
)
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flashing messages


# ------------------------------------------------------------------ #
# Routes ---                                                             #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("profile"))
    if request.method == "POST":
        # Get form data
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        if not name or not email or not password or not confirm_password:
            flash("All fields are required.")
            return render_template("register.html")

        if "@" not in email or "." not in email.split("@")[1]:
            flash("Please enter a valid email address.")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters long.")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        # Check if email already exists
        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if existing:
            flash("An account with that email already exists.")
            return render_template("register.html")

        # Hash password and create user
        password_hash = generate_password_hash(password)
        try:
            user_id = create_user(name, email, password_hash)
            flash("Account created! Please sign in.")
            return redirect(url_for("login"))
        except Exception as e:
            flash("Unable to create account. Please try again.")
            return render_template("register.html")

    # GET request
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("profile"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.")
            return render_template("login.html")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash(f"Welcome back, {user['name']}!")
        return redirect(url_for("profile"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these !                 #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    if "user_id" not in session:
        return redirect(url_for("login"))
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    # --- Preset date range computation ---
    today = datetime.now()
    this_month_from = today.replace(day=1).strftime("%Y-%m-%d")
    this_month_to = today.strftime("%Y-%m-%d")
    last_3m_from = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    last_3m_to = this_month_to
    last_6m_from = (today - timedelta(days=180)).strftime("%Y-%m-%d")
    last_6m_to = this_month_to

    presets = {
        "this_month": {"from": this_month_from, "to": this_month_to},
        "last_3_months": {"from": last_3m_from, "to": last_3m_to},
        "last_6_months": {"from": last_6m_from, "to": last_6m_to},
    }

    # --- Date filter validation ---
    raw_from = request.args.get("date_from", "").strip()
    raw_to = request.args.get("date_to", "").strip()

    date_from = None
    date_to = None
    if raw_from:
        try:
            datetime.strptime(raw_from, "%Y-%m-%d")
            date_from = raw_from
        except ValueError:
            pass
    if raw_to:
        try:
            datetime.strptime(raw_to, "%Y-%m-%d")
            date_to = raw_to
        except ValueError:
            pass
    if date_from and date_to and date_from > date_to:
        flash("Start date must be before end date.")
        date_from = None
        date_to = None

    # --- Determine active preset ---
    if date_from == this_month_from and date_to == this_month_to:
        active_preset = "this_month"
    elif date_from == last_3m_from and date_to == last_3m_to:
        active_preset = "last_3_months"
    elif date_from == last_6m_from and date_to == last_6m_to:
        active_preset = "last_6_months"
    elif date_from is None and date_to is None:
        active_preset = "all_time"
    else:
        active_preset = None  # custom range

    summary = get_summary_stats(user["id"], date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(user["id"], date_from=date_from, date_to=date_to)
    categories = get_category_breakdown(user["id"], date_from=date_from, date_to=date_to)

    return render_template(
        "profile.html",
        user=user,
        summary=summary,
        transactions=transactions,
        categories=categories,
        date_from=date_from or "",
        date_to=date_to or "",
        active_preset=active_preset,
        presets=presets,
    )


@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        amount_str = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        valid_categories = [
            "Food", "Transport", "Bills", "Health",
            "Entertainment", "Shopping", "Other",
        ]

        errors = []
        amount = None

        # Amount validation
        if not amount_str:
            errors.append("Amount is required.")
        else:
            try:
                amount = float(amount_str)
                if not isfinite(amount):
                    errors.append("Amount must be a valid number.")
                elif amount <= 0:
                    errors.append("Amount must be greater than 0.")
            except ValueError:
                errors.append("Amount must be a valid number.")

        # Category validation
        if not category:
            errors.append("Category is required.")
        elif category not in valid_categories:
            errors.append("Please select a valid category.")

        # Date validation
        if not date:
            errors.append("Date is required.")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                errors.append("Date must be in YYYY-MM-DD format.")

        # Description validation
        if not description:
            errors.append("Description is required.")
        elif len(description) > 200:
            errors.append("Description must be 200 characters or fewer.")

        if errors:
            for error in errors:
                flash(error)
            return render_template("add_expense.html")

        create_expense(
            session["user_id"], amount, category, date, description,
        )
        flash("Expense added successfully!")
        return redirect(url_for("profile"))

    return render_template("add_expense.html")


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    try:
        expense = conn.execute(
            "SELECT id, user_id, amount, category, date, description "
            "FROM expenses WHERE id = ? AND user_id = ?",
            (id, session["user_id"]),
        ).fetchone()
    finally:
        conn.close()

    if expense is None:
        abort(404)

    if request.method == "POST":
        amount_str = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        valid_categories = [
            "Food", "Transport", "Bills", "Health",
            "Entertainment", "Shopping", "Other",
        ]

        errors = []
        amount = None

        if not amount_str:
            errors.append("Amount is required.")
        else:
            try:
                amount = float(amount_str)
                if not isfinite(amount):
                    errors.append("Amount must be a valid number.")
                elif amount <= 0:
                    errors.append("Amount must be greater than 0.")
            except ValueError:
                errors.append("Amount must be a valid number.")

        if not category:
            errors.append("Category is required.")
        elif category not in valid_categories:
            errors.append("Please select a valid category.")

        if not date:
            errors.append("Date is required.")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                errors.append("Date must be in YYYY-MM-DD format.")

        if not description:
            errors.append("Description is required.")
        elif len(description) > 200:
            errors.append("Description must be 200 characters or fewer.")

        if errors:
            for error in errors:
                flash(error)
            form_data = dict(expense)
            form_data["amount"] = amount_str
            form_data["category"] = category
            form_data["date"] = date
            form_data["description"] = description
            return render_template("edit_expense.html", expense=form_data)

        update_expense(
            id, session["user_id"], amount, category, date, description,
        )
        flash("Expense updated successfully!")
        return redirect(url_for("profile"))

    return render_template("edit_expense.html", expense=expense)


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
