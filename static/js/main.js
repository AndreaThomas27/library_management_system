/*
 * main.js
 * -------
 * Handles simple client-side search and filtering on the Books page.
 * No server request is needed for this since all books are already
 * rendered on the page - we just hide/show the cards with JavaScript.
 */

document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("searchInput");
    const categoryFilter = document.getElementById("categoryFilter");
    const availabilityFilter = document.getElementById("availabilityFilter");
    const booksGrid = document.getElementById("booksGrid");

    // Only run this logic on the Books page (these elements won't
    // exist on other pages).
    if (!booksGrid) return;

    function applyFilters() {
        const searchTerm = searchInput.value.trim().toLowerCase();
        const selectedCategory = categoryFilter.value;
        const selectedAvailability = availabilityFilter.value;
        const bookCards = booksGrid.querySelectorAll(".book-card");
        let visibleCount = 0;

        bookCards.forEach(function (card) {
            const matchesSearch =
                card.dataset.title.includes(searchTerm) ||
                card.dataset.author.includes(searchTerm) ||
                card.dataset.isbn.includes(searchTerm);

            const matchesCategory =
                selectedCategory === "all" || card.dataset.category === selectedCategory;

            const matchesAvailability =
                selectedAvailability === "all" || card.dataset.available === selectedAvailability;

            const isVisible = matchesSearch && matchesCategory && matchesAvailability;
            card.style.display = isVisible ? "" : "none";
            if (isVisible) visibleCount++;
        });

        const noResultsMessage = document.getElementById("noResultsMessage");
        if (noResultsMessage) {
            noResultsMessage.style.display = visibleCount === 0 ? "block" : "none";
        }
    }

    searchInput.addEventListener("input", applyFilters);
    categoryFilter.addEventListener("change", applyFilters);
    availabilityFilter.addEventListener("change", applyFilters);
});
