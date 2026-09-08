# Library Book Issue & Return Management System

A web-based library management system built as a college technical-club
project. Students can browse books, scan QR codes to issue them, and
track their borrowing history. Admins can manage the book catalog,
monitor transactions, and download reports.

## Description

This project replaces a manual library register with a simple web
application. It demonstrates full-stack fundamentals — authentication,
a relational database, CRUD operations, QR code generation/scanning,
and basic reporting — without unnecessary frameworks or complexity.

## Features

**Student**
- Register and log in (passwords hashed, never stored in plain text)
- Browse, search, and filter available books
- View book details and issue a book
- Scan a book's QR code with the camera to issue it instantly
- View currently borrowed books, with overdue warnings
- View complete borrowing history
- Return borrowed books

**Admin**
- Dashboard with live statistics (total/available/issued/returned books,
  total students, overdue books) and a simple category chart
- Add, edit, and delete books (QR code auto-generated on add)
- View all transactions with status and search filters
- View registered students
- Download Books and Transactions reports as CSV files

## Technologies

```
HTML
CSS
JavaScript (vanilla)
Python
Flask
SQLite
QR Code (qrcode + html5-qrcode)
```

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
2. Activate it:
   - **Windows:** `venv\Scripts\activate`
   - **macOS/Linux:** `source venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
5. Open your browser at `http://127.0.0.1:5000`

The SQLite database (`library.db`) and all tables are created
automatically the first time you run the app, and demo data is
inserted automatically if the database is empty.

## Login Credentials (Demo Data)

| Role    | Email                | Password    |
|---------|-----------------------|-------------|
| Admin   | admin@library.com     | admin123    |
| Student | student@library.com   | student123  |

You can also register a new student account from the login page.

## Project Structure

```
library-management-system/
│
├── app.py               # All Flask routes (auth, student, admin, API)
├── database.py           # Table creation + demo data seeding
├── qr_utils.py            # Generates QR code images for books
├── requirements.txt
├── README.md
├── library.db             # Created automatically on first run
│
├── static/
│   ├── css/style.css        # All styling
│   ├── js/main.js            # Book search/filter (client-side)
│   ├── js/scanner.js         # QR scanner logic
│   ├── js/simple_chart.js    # Hand-written bar chart for admin dashboard
│   └── qr_codes/              # Generated QR code images
│
└── templates/
    ├── base.html, login.html, register.html, dashboard.html,
    │   books.html, book_details.html, scanner.html,
    │   borrowed_books.html, history.html, error.html
    └── admin/
        ├── dashboard.html, books.html, add_book.html, edit_book.html,
        │   transactions.html, users.html, reports.html
```

## Database

Three tables, connected with foreign keys:

- **users** — id, name, email, password (hashed), role (`student`/`admin`), created_at
- **books** — id, book_code, title, author, category, isbn, quantity,
  available_quantity, description, qr_code, created_at
- **transactions** — id, user_id, book_id, issue_date, due_date,
  return_date, status (`Issued`/`Returned`)

A user can have many transactions; a book can appear in many
transactions. Admin pages join all three tables to show readable
reports (student name + book title instead of just IDs).

## How QR Scanning Works

```
Admin adds book
      ↓
Book gets a unique book_code (e.g. BOOK011)
      ↓
Python (qrcode library) generates a QR image containing "BOOK:BOOK011"
      ↓
QR image is saved in static/qr_codes/ and its filename stored in the DB
      ↓
Student opens the Scan QR page and grants camera access
      ↓
The html5-qrcode JavaScript library reads the camera feed and decodes the QR text
      ↓
JavaScript sends the decoded text to Flask (/api/lookup_book)
      ↓
Flask extracts the book_code and looks it up in SQLite
      ↓
Book details are sent back and shown on the page
      ↓
Student clicks "Issue This Book" → /api/issue_via_qr
      ↓
A new row is inserted into transactions and available_quantity is decreased
```

## Issue / Return Workflow

**Issuing:** check the book exists → check it's available → check the
student doesn't already have it → insert a transaction row (status
`Issued`, due date = today + 14 days) → decrease `available_quantity`.

**Returning:** find the student's active transaction for that book →
set `return_date` to today and status to `Returned` → increase
`available_quantity` back by one. A transaction can only be returned
once.

**Overdue:** calculated on the fly whenever transactions are displayed
— a transaction is "Overdue" if its status is still `Issued` and
`due_date` is before today. No background scheduler is needed.

## Testing Checklist

- [ ] Register a new student, then try registering the same email again (should fail)
- [ ] Log in with wrong password (should fail with a friendly message)
- [ ] Log in as student and as admin, confirm each lands on the right dashboard
- [ ] Student cannot open any `/admin/...` URL directly
- [ ] Logged-out user is redirected to login when visiting protected pages
- [ ] Search and filter books by title, author, ISBN, category, availability
- [ ] Issue a book, then try issuing the same book again (should be blocked)
- [ ] Issue a book with 0 available copies (should be blocked)
- [ ] Return a book, then try returning it again (should be blocked)
- [ ] Let a due date pass (or edit it in SQLite) to confirm "Overdue" shows correctly
- [ ] Scan a valid QR code and issue the book from the scanner page
- [ ] Scan an invalid/foreign QR code (should show "Invalid QR code")
- [ ] Admin: add, edit, and delete a book
- [ ] Admin: try deleting a book that is currently issued (should be blocked)
- [ ] Admin: filter and search transactions
- [ ] Admin: download both CSV reports and open them

## Assumptions Made

- A book is due back 14 days after it is issued (configurable via
  `DAYS_UNTIL_DUE` in `app.py`).
- QR codes encode plain text (`BOOK:<book_code>`) rather than a
  scannable image identifier, since the book_code alone is enough to
  identify the book.
- Overdue status is a calculated/display-only value — it does not
  need its own column since it can always be derived from `due_date`
  and `return_date`.
- The QR scanner requires HTTPS or `localhost` for camera access, per
  standard browser security rules (this is a browser requirement, not
  something the app controls).

## Future Improvements

- Email notifications for due/overdue books
- Fine calculation for late returns
- Book reservation system for unavailable titles
- Moving from SQLite to a cloud-hosted database
- More advanced analytics and charts
