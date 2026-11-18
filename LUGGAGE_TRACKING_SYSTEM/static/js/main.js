/**
 * Main Frontend Interactivity Script
 * Handles live table filtering, mobile sidebar toggling, and tag printing.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Live Search Filter for Data Tables
    const searchInputs = document.querySelectorAll('[data-table-search]');
    searchInputs.forEach(input => {
        input.addEventListener('keyup', function () {
            const filter = this.value.toLowerCase().trim();
            const targetTableId = this.getAttribute('data-table-search');
            const table = document.getElementById(targetTableId);
            if (!table) return;

            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            });
        });
    });

    // 2. Mobile Sidebar Toggle
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }
});

/**
 * Triggers browser print dialog for QR luggage tags or administrative reports.
 */
function printPageSection() {
    window.print();
}