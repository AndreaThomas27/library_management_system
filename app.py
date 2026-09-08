"""
app.py
------
The main Flask application for the Library Book Issue & Return
Management System.

Route groups in this file:
    1. Authentication          -> /register, /login, /logout
    2. Student pages           -> /dashboard, /books, /book/<id>, /scan,
                                   /borrow/<id>, /return/<id>, /history
    3. Admin pages             -> /admin/...
    4. Small JSON API          -> /api/lookup_book  (used by the QR scanner)

The whole app follows one simple flow:
    Browser -> HTML/CSS/JS -> Flask routes (this file) -> SQLite (database.py)
"""

import csv
import io
import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db_connection, init_db
from qr_utils import generate_qr_code

app = Flask(__name__)
app.secret_key = "college-project-secret-key-change-if-needed"

DAYS_UNTIL_DUE = 14  # a borrowed book is due back 14 days after issue


# ---------------------------------------------------------------------------
# Helpers / decorators
# ---------------------------------------------------------------------------

def login_required(view_function):
    """Blocks access to a page unless the user is logged in."""
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)
    return wrapped_view


def admin_required(view_function):
    """Blocks access to admin-only pages for normal students."""
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Unauthorized: admin access only.", "error")
            return redirect(url_for("dashboard"))
        return view_function(*args, **kwargs)
    return wrapped_view


def get_today():
    return datetime.now().strftime("%Y-%m-%d")


def compute_display_status(transaction_status, due_date, return_date):
    """A transaction is 'Overdue' if it is still Issued and the due
    date has already passed. We calculate this on the fly instead of
    running a background job, which keeps the logic simple.
    """
    if transaction_status == "Returned" or return_date:
        return "Returned"
    if due_date < get_today():
        return "Overdue"
    return "Issued"


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("register.html")

        db = get_db_connection()
        existing_user = db.execute(
            "SELECT id FROM users WHERE email = ?", (email,)
        ).fetchone()

        if existing_user:
            db.close()
            flash("An account with this email already exists.", "error")
            return render_template("register.html")

        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, generate_password_hash(password), "student",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        db.commit()
        db.close()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        db = get_db_connection()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()

        if user is None or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]

        flash(f"Welcome back, {user['name']}!", "success")
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Student: Dashboard
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db_connection()
    user_id = session["user_id"]

    available_books = db.execute(
        "SELECT COUNT(*) FROM books WHERE available_quantity > 0"
    ).fetchone()[0]

    currently_borrowed = db.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND status = 'Issued'",
        (user_id,),
    ).fetchone()[0]

    overdue_books = db.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE user_id = ? AND status = 'Issued' AND due_date < ?
    """, (user_id, get_today())).fetchone()[0]

    total_borrowed = db.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    db.close()

    stats = {
        "available_books": available_books,
        "currently_borrowed": currently_borrowed,
        "overdue_books": overdue_books,
        "total_borrowed": total_borrowed,
    }
    return render_template("dashboard.html", stats=stats)


# ---------------------------------------------------------------------------
# Student: Books, search & filter, details
# ---------------------------------------------------------------------------

@app.route("/books")
@login_required
def books():
    db = get_db_connection()
    all_books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
    categories = db.execute("SELECT DISTINCT category FROM books ORDER BY category").fetchall()
    db.close()
    return render_template("books.html", books=all_books, categories=categories)


@app.route("/book/<int:book_id>")
@login_required
def book_details(book_id):
    db = get_db_connection()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    already_borrowed = None
    if book:
        already_borrowed = db.execute("""
            SELECT id FROM transactions
            WHERE user_id = ? AND book_id = ? AND status = 'Issued'
        """, (session["user_id"], book_id)).fetchone()

    db.close()

    if book is None:
        flash("Book not found.", "error")
        return redirect(url_for("books"))

    return render_template("book_details.html", book=book, already_borrowed=already_borrowed)


# ---------------------------------------------------------------------------
# Student: Issue / Borrow a book
# ---------------------------------------------------------------------------

def issue_book_to_user(db, user_id, book):
    """Shared logic for issuing a book, used by both the normal
    'Issue Book' button and the QR-scanner issue flow.

    Returns (success: bool, message: str).
    """
    if book is None:
        return False, "Book not found."

    if book["available_quantity"] <= 0:
        return False, "This book is currently unavailable."

    already_has_it = db.execute("""
        SELECT id FROM transactions
        WHERE user_id = ? AND book_id = ? AND status = 'Issued'
    """, (user_id, book["id"])).fetchone()

    if already_has_it:
        return False, "You already have this book issued."

    issue_date = datetime.now().strftime("%Y-%m-%d")
    due_date = (datetime.now() + timedelta(days=DAYS_UNTIL_DUE)).strftime("%Y-%m-%d")

    db.execute("""
        INSERT INTO transactions (user_id, book_id, issue_date, due_date, return_date, status)
        VALUES (?, ?, ?, ?, NULL, 'Issued')
    """, (user_id, book["id"], issue_date, due_date))

    # Reduce available copies after a successful issue transaction.
    db.execute(
        "UPDATE books SET available_quantity = available_quantity - 1 WHERE id = ?",
        (book["id"],),
    )
    db.commit()

    return True, f"'{book['title']}' issued successfully. Due on {due_date}."


@app.route("/borrow/<int:book_id>", methods=["POST"])
@login_required
def borrow(book_id):
    db = get_db_connection()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    success, message = issue_book_to_user(db, session["user_id"], book)
    db.close()

    flash(message, "success" if success else "error")
    return redirect(url_for("book_details", book_id=book_id))


# ---------------------------------------------------------------------------
# Student: QR Scanner
# ---------------------------------------------------------------------------

@app.route("/scan")
@login_required
def scan():
    return render_template("scanner.html")


@app.route("/api/lookup_book", methods=["POST"])
@login_required
def api_lookup_book():
    """Called by JavaScript (scanner.js) after it decodes a QR code.

    Expects JSON: { "qr_text": "BOOK:BOOK001" }
    Returns JSON with the book info, or an error message.
    """
    data = request.get_json(silent=True) or {}
    qr_text = data.get("qr_text", "").strip()

    if not qr_text.startswith("BOOK:"):
        return jsonify({"success": False, "message": "Invalid QR code."}), 400

    book_code = qr_text.replace("BOOK:", "", 1).strip()

    db = get_db_connection()
    book = db.execute("SELECT * FROM books WHERE book_code = ?", (book_code,)).fetchone()
    db.close()

    if book is None:
        return jsonify({"success": False, "message": "Book not found."}), 404

    return jsonify({
        "success": True,
        "book": {
            "id": book["id"],
            "book_code": book["book_code"],
            "title": book["title"],
            "author": book["author"],
            "category": book["category"],
            "available_quantity": book["available_quantity"],
        }
    })


@app.route("/api/issue_via_qr", methods=["POST"])
@login_required
def api_issue_via_qr():
    """Called by the scanner page when the student clicks
    'Issue this book' after a successful scan.
    """
    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")

    db = get_db_connection()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    success, message = issue_book_to_user(db, session["user_id"], book)
    db.close()

    status_code = 200 if success else 400
    return jsonify({"success": success, "message": message}), status_code


# ---------------------------------------------------------------------------
# Student: Borrowed books & Return
# ---------------------------------------------------------------------------

@app.route("/borrowed")
@login_required
def borrowed_books():
    db = get_db_connection()
    rows = db.execute("""
        SELECT transactions.id, transactions.issue_date, transactions.due_date,
               transactions.return_date, transactions.status,
               books.id AS book_id, books.title, books.author
        FROM transactions
        JOIN books ON books.id = transactions.book_id
        WHERE transactions.user_id = ? AND transactions.status = 'Issued'
        ORDER BY transactions.due_date ASC
    """, (session["user_id"],)).fetchall()
    db.close()

    borrowed = []
    for row in rows:
        display_status = compute_display_status(row["status"], row["due_date"], row["return_date"])
        borrowed.append({**dict(row), "display_status": display_status})

    return render_template("borrowed_books.html", borrowed=borrowed)


@app.route("/return/<int:transaction_id>", methods=["POST"])
@login_required
def return_book(transaction_id):
    db = get_db_connection()
    transaction = db.execute(
        "SELECT * FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, session["user_id"]),
    ).fetchone()

    if transaction is None:
        db.close()
        flash("Transaction not found.", "error")
        return redirect(url_for("borrowed_books"))

    if transaction["status"] == "Returned":
        db.close()
        flash("This book has already been returned.", "error")
        return redirect(url_for("borrowed_books"))

    return_date = datetime.now().strftime("%Y-%m-%d")
    db.execute(
        "UPDATE transactions SET return_date = ?, status = 'Returned' WHERE id = ?",
        (return_date, transaction_id),
    )
    db.execute(
        "UPDATE books SET available_quantity = available_quantity + 1 WHERE id = ?",
        (transaction["book_id"],),
    )
    db.commit()
    db.close()

    flash("Book returned successfully.", "success")
    return redirect(url_for("borrowed_books"))


# ---------------------------------------------------------------------------
# Student: History
# ---------------------------------------------------------------------------

@app.route("/history")
@login_required
def history():
    db = get_db_connection()
    rows = db.execute("""
        SELECT transactions.issue_date, transactions.due_date,
               transactions.return_date, transactions.status,
               books.title, books.author
        FROM transactions
        JOIN books ON books.id = transactions.book_id
        WHERE transactions.user_id = ?
        ORDER BY transactions.issue_date DESC
    """, (session["user_id"],)).fetchall()
    db.close()

    past_transactions = []
    for row in rows:
        display_status = compute_display_status(row["status"], row["due_date"], row["return_date"])
        past_transactions.append({**dict(row), "display_status": display_status})

    return render_template("history.html", transactions=past_transactions)


# ---------------------------------------------------------------------------
# Admin: Dashboard
# ---------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db_connection()

    total_books = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    available_books = db.execute(
        "SELECT COALESCE(SUM(available_quantity), 0) FROM books"
    ).fetchone()[0]
    issued_books = db.execute(
        "SELECT COUNT(*) FROM transactions WHERE status = 'Issued'"
    ).fetchone()[0]
    returned_books = db.execute(
        "SELECT COUNT(*) FROM transactions WHERE status = 'Returned'"
    ).fetchone()[0]
    total_students = db.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student'"
    ).fetchone()[0]
    overdue_books = db.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE status = 'Issued' AND due_date < ?
    """, (get_today(),)).fetchone()[0]

    category_counts = db.execute("""
        SELECT category, COUNT(*) as count FROM books GROUP BY category ORDER BY count DESC
    """).fetchall()

    db.close()

    stats = {
        "total_books": total_books,
        "available_books": available_books,
        "issued_books": issued_books,
        "returned_books": returned_books,
        "total_students": total_students,
        "overdue_books": overdue_books,
    }
    return render_template("admin/dashboard.html", stats=stats, category_counts=category_counts)


# ---------------------------------------------------------------------------
# Admin: Book management
# ---------------------------------------------------------------------------

@app.route("/admin/books")
@admin_required
def admin_books():
    db = get_db_connection()
    all_books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
    db.close()
    return render_template("admin/books.html", books=all_books)


@app.route("/admin/books/add", methods=["GET", "POST"])
@admin_required
def admin_add_book():
    if request.method == "POST":
        book_code = request.form.get("book_code", "").strip()
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        isbn = request.form.get("isbn", "").strip()
        quantity = request.form.get("quantity", "").strip()
        description = request.form.get("description", "").strip()

        if not all([book_code, title, author, category, quantity]):
            flash("Please fill in all required fields.", "error")
            return render_template("admin/add_book.html")

        if not quantity.isdigit() or int(quantity) <= 0:
            flash("Quantity must be a positive number.", "error")
            return render_template("admin/add_book.html")

        quantity = int(quantity)

        db = get_db_connection()
        existing = db.execute(
            "SELECT id FROM books WHERE book_code = ?", (book_code,)
        ).fetchone()
        if existing:
            db.close()
            flash("A book with this book code already exists.", "error")
            return render_template("admin/add_book.html")

        # Generate the book's unique QR code before saving.
        qr_filename = generate_qr_code(book_code)

        db.execute("""
            INSERT INTO books
            (book_code, title, author, category, isbn, quantity, available_quantity,
             description, qr_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (book_code, title, author, category, isbn, quantity, quantity,
              description, qr_filename, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        db.commit()
        db.close()

        flash(f"Book '{title}' added successfully with QR code generated.", "success")
        return redirect(url_for("admin_books"))

    return render_template("admin/add_book.html")


@app.route("/admin/books/edit/<int:book_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_book(book_id):
    db = get_db_connection()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if book is None:
        db.close()
        flash("Book not found.", "error")
        return redirect(url_for("admin_books"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        isbn = request.form.get("isbn", "").strip()
        new_quantity = request.form.get("quantity", "").strip()
        description = request.form.get("description", "").strip()

        if not all([title, author, category, new_quantity]):
            db.close()
            flash("Please fill in all required fields.", "error")
            return redirect(url_for("admin_edit_book", book_id=book_id))

        if not new_quantity.isdigit():
            db.close()
            flash("Quantity must be a valid number.", "error")
            return redirect(url_for("admin_edit_book", book_id=book_id))

        new_quantity = int(new_quantity)
        currently_issued = book["quantity"] - book["available_quantity"]

        # Never let the total quantity drop below the number of
        # copies that are currently out with students.
        if new_quantity < currently_issued:
            db.close()
            flash(
                f"Cannot set quantity below {currently_issued} "
                f"(that many copies are currently issued).", "error"
            )
            return redirect(url_for("admin_edit_book", book_id=book_id))

        new_available = new_quantity - currently_issued

        db.execute("""
            UPDATE books
            SET title = ?, author = ?, category = ?, isbn = ?,
                quantity = ?, available_quantity = ?, description = ?
            WHERE id = ?
        """, (title, author, category, isbn, new_quantity, new_available, description, book_id))
        db.commit()
        db.close()

        flash("Book updated successfully.", "success")
        return redirect(url_for("admin_books"))

    db.close()
    return render_template("admin/edit_book.html", book=book)


@app.route("/admin/books/delete/<int:book_id>", methods=["POST"])
@admin_required
def admin_delete_book(book_id):
    db = get_db_connection()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if book is None:
        db.close()
        flash("Book not found.", "error")
        return redirect(url_for("admin_books"))

    currently_issued = book["quantity"] - book["available_quantity"]
    if currently_issued > 0:
        db.close()
        flash("Cannot delete this book because it is currently issued.", "error")
        return redirect(url_for("admin_books"))

    # Clean up the QR code image file along with the database row.
    if book["qr_code"]:
        qr_path = os.path.join("static", "qr_codes", book["qr_code"])
        if os.path.exists(qr_path):
            os.remove(qr_path)

    db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    db.commit()
    db.close()

    flash("Book deleted successfully.", "success")
    return redirect(url_for("admin_books"))


# ---------------------------------------------------------------------------
# Admin: Transactions
# ---------------------------------------------------------------------------

@app.route("/admin/transactions")
@admin_required
def admin_transactions():
    status_filter = request.args.get("status", "All")
    search_query = request.args.get("q", "").strip()

    query = """
        SELECT transactions.id, transactions.issue_date, transactions.due_date,
               transactions.return_date, transactions.status,
               users.name AS student_name, books.title AS book_title
        FROM transactions
        JOIN users ON users.id = transactions.user_id
        JOIN books ON books.id = transactions.book_id
        WHERE 1 = 1
    """
    params = []

    if search_query:
        query += " AND (users.name LIKE ? OR books.title LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY transactions.issue_date DESC"

    db = get_db_connection()
    rows = db.execute(query, params).fetchall()
    db.close()

    all_transactions = []
    for row in rows:
        display_status = compute_display_status(row["status"], row["due_date"], row["return_date"])
        all_transactions.append({**dict(row), "display_status": display_status})

    # Status filtering happens after computing display_status because
    # "Overdue" isn't a value actually stored in the database column.
    if status_filter != "All":
        all_transactions = [t for t in all_transactions if t["display_status"] == status_filter]

    return render_template(
        "admin/transactions.html",
        transactions=all_transactions,
        status_filter=status_filter,
        search_query=search_query,
    )


# ---------------------------------------------------------------------------
# Admin: Users
# ---------------------------------------------------------------------------

@app.route("/admin/users")
@admin_required
def admin_users():
    db = get_db_connection()
    students = db.execute(
        "SELECT id, name, email, created_at FROM users WHERE role = 'student' ORDER BY created_at DESC"
    ).fetchall()
    db.close()
    return render_template("admin/users.html", students=students)


# ---------------------------------------------------------------------------
# Admin: Reports
# ---------------------------------------------------------------------------

@app.route("/admin/reports")
@admin_required
def admin_reports():
    return render_template("admin/reports.html")


@app.route("/admin/reports/books.csv")
@admin_required
def download_books_report():
    db = get_db_connection()
    all_books = db.execute("SELECT * FROM books ORDER BY title").fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Book Code", "Title", "Author", "Category", "ISBN", "Quantity", "Available Quantity"])
    for book in all_books:
        writer.writerow([
            book["book_code"], book["title"], book["author"], book["category"],
            book["isbn"], book["quantity"], book["available_quantity"],
        ])

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(
        csv_bytes, mimetype="text/csv", as_attachment=True,
        download_name="books_report.csv",
    )


@app.route("/admin/reports/transactions.csv")
@admin_required
def download_transactions_report():
    db = get_db_connection()
    rows = db.execute("""
        SELECT users.name AS student_name, books.title AS book_title,
               transactions.issue_date, transactions.due_date,
               transactions.return_date, transactions.status
        FROM transactions
        JOIN users ON users.id = transactions.user_id
        JOIN books ON books.id = transactions.book_id
        ORDER BY transactions.issue_date DESC
    """).fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student", "Book", "Issue Date", "Due Date", "Return Date", "Status"])
    for row in rows:
        display_status = compute_display_status(row["status"], row["due_date"], row["return_date"])
        writer.writerow([
            row["student_name"], row["book_title"], row["issue_date"],
            row["due_date"], row["return_date"] or "-", display_status,
        ])

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    return send_file(
        csv_bytes, mimetype="text/csv", as_attachment=True,
        download_name="transactions_report.csv",
    )


# ---------------------------------------------------------------------------
# Error handlers (avoid exposing raw Python errors to users)
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):
    return render_template("error.html", message="Page not found."), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html", message="Something went wrong. Please try again."), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
