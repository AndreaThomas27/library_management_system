/*
 * scanner.js
 * ----------
 * Runs the browser-based QR scanner on the "Scan Book QR" page.
 *
 * Flow:
 *   1. Student clicks "Start Camera" -> browser asks for camera permission.
 *   2. html5-qrcode library reads frames from the camera and decodes any QR code.
 *   3. Once decoded, we send the text to Flask (/api/lookup_book) to find the book.
 *   4. If found, we show the book's details and an "Issue This Book" button.
 *   5. Clicking that button calls /api/issue_via_qr to actually create the transaction.
 */

let html5QrCode = null;
let currentScannedBookId = null;

const startBtn = document.getElementById("startScanBtn");
const stopBtn = document.getElementById("stopScanBtn");
const scanMessage = document.getElementById("scanMessage");
const scannedCard = document.getElementById("scannedBookCard");
const issueBtn = document.getElementById("issueScannedBookBtn");

function showMessage(text, isError) {
    scanMessage.textContent = text;
    scanMessage.style.color = isError ? "#c0392b" : "#2e8b57";
}

function stopScanning() {
    if (html5QrCode) {
        html5QrCode.stop().catch(function () { /* camera may already be stopped */ });
    }
    startBtn.style.display = "inline-block";
    stopBtn.style.display = "none";
}

async function handleScanSuccess(decodedText) {
    // Pause scanning immediately so we don't fire this repeatedly
    // for the same QR code while it's still in view.
    stopScanning();
    showMessage("QR code detected. Looking up book...", false);

    try {
        const response = await fetch("/api/lookup_book", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ qr_text: decodedText }),
        });
        const result = await response.json();

        if (!result.success) {
            showMessage(result.message || "Invalid QR code.", true);
            scannedCard.style.display = "none";
            return;
        }

        const book = result.book;
        currentScannedBookId = book.id;

        document.getElementById("scannedTitle").textContent = book.title;
        document.getElementById("scannedAuthor").textContent = "by " + book.author;
        document.getElementById("scannedCategory").textContent = "Category: " + book.category;

        const availabilityText = document.getElementById("scannedAvailability");
        if (book.available_quantity > 0) {
            availabilityText.textContent = "Available copies: " + book.available_quantity;
            issueBtn.disabled = false;
            issueBtn.textContent = "Issue This Book";
        } else {
            availabilityText.textContent = "This book is currently unavailable.";
            issueBtn.disabled = true;
            issueBtn.textContent = "Unavailable";
        }

        scannedCard.style.display = "block";
        showMessage("Book found!", false);
    } catch (error) {
        showMessage("Something went wrong while looking up the book.", true);
    }
}

startBtn.addEventListener("click", function () {
    scannedCard.style.display = "none";
    showMessage("Requesting camera access...", false);

    html5QrCode = new Html5Qrcode("qr-reader");
    html5QrCode
        .start(
            { facingMode: "environment" },
            { fps: 10, qrbox: 220 },
            handleScanSuccess
        )
        .then(function () {
            startBtn.style.display = "none";
            stopBtn.style.display = "inline-block";
            showMessage("Point your camera at a book's QR code.", false);
        })
        .catch(function () {
            showMessage("Could not access the camera. Please check permissions.", true);
        });
});

stopBtn.addEventListener("click", stopScanning);

issueBtn.addEventListener("click", async function () {
    if (!currentScannedBookId) return;

    try {
        const response = await fetch("/api/issue_via_qr", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ book_id: currentScannedBookId }),
        });
        const result = await response.json();
        showMessage(result.message, !result.success);

        if (result.success) {
            issueBtn.disabled = true;
            issueBtn.textContent = "Issued!";
        }
    } catch (error) {
        showMessage("Something went wrong while issuing the book.", true);
    }
});
