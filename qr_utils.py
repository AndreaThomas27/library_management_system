"""
qr_utils.py
-----------
One job only: turn a book_code (like "BOOK001") into a QR code
image saved inside static/qr_codes/, and return the filename so
it can be stored in the books table.

Keeping this in its own tiny module means app.py and database.py
can both use it without duplicating code.
"""

import qrcode
import os

QR_FOLDER = os.path.join("static", "qr_codes")


def generate_qr_code(book_code):
    """Create a QR code image that encodes the book's unique code.

    The QR content is simply "BOOK:<book_code>" so the scanner page
    can tell at a glance that the scanned code belongs to this system
    (and not some random QR code from the internet).
    """
    os.makedirs(QR_FOLDER, exist_ok=True)

    qr_content = f"BOOK:{book_code}"
    qr_image = qrcode.make(qr_content)

    filename = f"{book_code}.png"
    filepath = os.path.join(QR_FOLDER, filename)
    qr_image.save(filepath)

    return filename
