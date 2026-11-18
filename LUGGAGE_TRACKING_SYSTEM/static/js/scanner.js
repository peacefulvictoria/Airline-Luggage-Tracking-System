/**
 * Browser-Based QR Code Camera Scanner
 * Uses html5-qrcode to read luggage QR tags via webcam/smartphone camera
 * and fetches matching luggage metadata from Flask's /api/luggage/<code > endpoint.
 */

let html5QrcodeScanner = null;

function lookupLuggageCode(code) {
    const cleanCode = code.trim().toUpperCase();
    if (!cleanCode) return;

    const codeInput = document.getElementById('tracking_code');
    const feedbackBox = document.getElementById('scan-feedback');
    const detailsBox = document.getElementById('scanned-luggage-info');

    if (codeInput) codeInput.value = cleanCode;

    if (feedbackBox) {
        feedbackBox.className = 'alert alert-info';
        feedbackBox.textContent = `Scanning code ${cleanCode}... fetching luggage record.`;
        feedbackBox.style.display = 'block';
    }

    fetch(`/api/luggage/${encodeURIComponent(cleanCode)}`)
        .then(response => response.json().then(data => ({ status: response.status, body: data })))
        .then(({ status, body }) => {
            if (status === 200 && body.found) {
                feedbackBox.className = 'alert alert-success';
                feedbackBox.textContent = `QR Verified: ${body.tracking_code} belongs to ${body.passenger_name}.`;

                if (detailsBox) {
                    detailsBox.style.display = 'block';
                    detailsBox.innerHTML = `
                        <p><strong>Tracking ID:</strong> ${body.tracking_code}</p>
                        <p><strong>Passenger:</strong> ${body.passenger_name}</p>
                        <p><strong>Destination:</strong> ${body.destination}</p>
                        <p><strong>Weight:</strong> ${body.weight} kg</p>
                        <p><strong>Current Status:</strong> <span class="badge badge-transit">${body.current_status}</span></p>
                    `;
                }
            } else {
                feedbackBox.className = 'alert alert-danger';
                feedbackBox.textContent = body.message || 'Invalid QR Code: Luggage not found.';
                if (detailsBox) detailsBox.style.display = 'none';
            }
        })
        .catch(() => {
            if (feedbackBox) {
                feedbackBox.className = 'alert alert-danger';
                feedbackBox.textContent = 'Network error while verifying QR code.';
            }
        });
}

function onScanSuccess(decodedText) {
    lookupLuggageCode(decodedText);
}

document.addEventListener('DOMContentLoaded', () => {
    const readerElement = document.getElementById('qr-reader');
    if (readerElement && typeof Html5QrcodeScanner !== 'undefined') {
        html5QrcodeScanner = new Html5QrcodeScanner(
            'qr-reader',
            { fps: 10, qrbox: { width: 240, height: 240 } },
            false
        );
        html5QrcodeScanner.render(onScanSuccess);
    }

    // Also allow manual lookup button if camera is unavailable on a desktop PC
    const manualLookupBtn = document.getElementById('manualLookupBtn');
    if (manualLookupBtn) {
        manualLookupBtn.addEventListener('click', () => {
            const codeVal = document.getElementById('tracking_code').value;
            lookupLuggageCode(codeVal);
        });
    }

    // Auto-lookup if code came via query string
    const prefilled = document.getElementById('tracking_code');
    if (prefilled && prefilled.value.trim() !== '') {
        lookupLuggageCode(prefilled.value);
    }
});