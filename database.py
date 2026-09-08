"""
database.py
-----------
Handles all direct database work for the Library Management System:
creating the SQLite file, creating tables, and inserting demo data
the very first time the app is run.

Every other file (app.py) imports get_db_connection() from here so
that there is only ONE place that knows how to connect to the database.
"""

import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

DATABASE_NAME = "library.db"


def get_db_connection():
    """Open a connection to the SQLite database.

    row_factory is set so query results behave like dictionaries
    (row["title"] instead of row[1]), which makes templates and
    route code much easier to read.
    """
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    # Enforce foreign key constraints (SQLite disables this by default).
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """Create tables if they don't exist yet, and seed demo data
    the first time the app runs on a fresh database.
    """
    db_exists_and_has_data = os.path.exists(DATABASE_NAME)

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_code TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            isbn TEXT,
            quantity INTEGER NOT NULL,
            available_quantity INTEGER NOT NULL,
            description TEXT,
            qr_code TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            return_date TEXT,
            status TEXT NOT NULL DEFAULT 'Issued',
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (book_id) REFERENCES books (id)
        )
    """)

    connection.commit()

    # Only seed demo data if the books table is completely empty.
    # This keeps re-running the app safe (it won't duplicate data).
    book_count = cursor.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    if book_count == 0:
        seed_sample_data(connection)

    connection.close()


def seed_sample_data(connection):
    """Insert demo users and books so the project can be shown
    off immediately without any manual data entry.
    """
    cursor = connection.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Demo users -----------------------------------------------------
    demo_users = [
        ("Admin User", "admin@library.com", "admin123", "admin"),
        ("Demo Student", "student@library.com", "student123", "student"),
    ]
    for name, email, password, role in demo_users:
        cursor.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role, now),
        )

    # --- Demo books -------------------------------------------------------
    demo_books = [
        ("BOOK001", "Introduction to Algorithms", "Thomas H. Cormen", "Computer Science",
         "9780262033848", 4, "A comprehensive guide to algorithms and data structures."),
        ("BOOK002", "Clean Code", "Robert C. Martin", "Computer Science",
         "9780132350884", 3, "Best practices for writing readable and maintainable code."),
        ("BOOK003", "The Pragmatic Programmer", "Andrew Hunt", "Computer Science",
         "9780201616224", 2, "Practical advice for becoming a better software developer."),
        ("BOOK004", "A Brief History of Time", "Stephen Hawking", "Science",
         "9780553380163", 3, "An exploration of cosmology and the nature of the universe."),
        ("BOOK005", "Sapiens", "Yuval Noah Harari", "History",
         "9780062316097", 5, "A brief history of humankind from ancient to modern times."),
        ("BOOK006", "The Alchemist", "Paulo Coelho", "Fiction",
         "9780061122415", 4, "A novel about following your dreams and personal legend."),
        ("BOOK007", "Atomic Habits", "James Clear", "Self-Help",
         "9780735211292", 3, "An easy and proven way to build good habits and break bad ones."),
        ("BOOK008", "Wings of Fire", "A.P.J. Abdul Kalam", "Biography",
         "9788173711466", 2, "The autobiography of India's former President and scientist."),
        ("BOOK009", "Database System Concepts", "Abraham Silberschatz", "Computer Science",
         "9780078022159", 3, "Fundamental concepts of database design and management."),
        ("BOOK010", "Computer Networks", "Andrew S. Tanenbaum", "Computer Science",
         "9780132126953", 2, "A detailed introduction to computer networking principles."),
    ]

    for book_code, title, author, category, isbn, quantity, description in demo_books:
        cursor.execute("""
            INSERT INTO books
            (book_code, title, author, category, isbn, quantity, available_quantity,
             description, qr_code, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (book_code, title, author, category, isbn, quantity, quantity,
              description, None, now))

    connection.commit()

    # Generate an actual QR code image for every seeded book.
    # Imported here (not at top) to avoid a circular import with app.py.
    from qr_utils import generate_qr_code
    books = cursor.execute("SELECT id, book_code FROM books").fetchall()
    for book in books:
        qr_filename = generate_qr_code(book["book_code"])
        cursor.execute("UPDATE books SET qr_code = ? WHERE id = ?", (qr_filename, book["id"]))

    connection.commit()
