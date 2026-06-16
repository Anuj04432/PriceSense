const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const resultsArea = document.getElementById('results-area');
const chips = document.querySelectorAll('.chip');

// Map our store keys to display-friendly names and colors
const STORE_META = {
    amazon:   { label: 'Amazon.in',        color: '#FF9900' },
    flipkart: { label: 'Flipkart',         color: '#2874F0' },
    croma:    { label: 'Croma',            color: '#67AE36' },
    reliance: { label: 'Reliance Digital', color: '#E32019' },
};

function formatPrice(num) {
    if (num === null || num === undefined) return '—';
    return '₹' + Math.round(num).toLocaleString('en-IN');
}

async function searchProduct(query) {
    if (!query || !query.trim()) return;

    searchBtn.disabled = true;
    resultsArea.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            Searching across Amazon, Flipkart, Croma & Reliance Digital...
        </div>
    `;

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (!response.ok) {
            renderError(data.error || 'Something went wrong. Please try again.');
            return;
        }

        renderResults(data, query);

    } catch (err) {
        renderError('Could not reach the server. Check your connection and try again.');
    } finally {
        searchBtn.disabled = false;
    }
}

function renderError(message) {
    resultsArea.innerHTML = `<div class="error-box">⚠️ ${escapeHtml(message)}</div>`;
}

function renderResults(data, query) {
    const { recommendation, store_comparison, all_listings_count } = data;

    if (!all_listings_count || all_listings_count === 0) {
        resultsArea.innerHTML = `
            <div class="no-results">
                No results found for "${escapeHtml(query)}". Try a different search term.
            </div>
        `;
        return;
    }

    let html = '';

    // Recommendation banner
    if (recommendation) {
        html += `
            <div class="recommendation-banner">
                💡 <strong>Recommendation:</strong> ${escapeHtml(recommendation)}
            </div>
        `;
    }

    html += `<div class="results-header">Showing prices from ${all_listings_count} listings across 4 stores</div>`;

    // Find the lowest price among available stores to mark "best"
    const availablePrices = store_comparison
        .filter(s => s.available && s.price)
        .map(s => s.price);
    const lowestPrice = availablePrices.length ? Math.min(...availablePrices) : null;

    for (const store of store_comparison) {
        const meta = STORE_META[store.store] || { label: store.store_name, color: '#6B7280' };
        const isBest = store.available && store.price === lowestPrice;

        if (!store.available) {
            html += `
                <div class="store-card unavailable">
                    <div class="store-info">
                        <div class="store-name-row">
                            <span class="store-name" style="color:${meta.color}">${escapeHtml(meta.label)}</span>
                        </div>
                        <div class="na-text">Not available on this store</div>
                    </div>
                </div>
            `;
            continue;
        }

        html += `
            <div class="store-card ${isBest ? 'best-price' : ''}">
                <div class="store-info">
                    <div class="store-name-row">
                        <span class="store-name" style="color:${meta.color}">${escapeHtml(meta.label)}</span>
                        ${isBest ? '<span class="best-tag">LOWEST PRICE</span>' : ''}
                    </div>
                    <div class="product-title">${escapeHtml(store.title || '')}</div>
                    ${store.rating ? `<div class="rating-row">⭐ ${store.rating} ${store.reviews ? `(${store.reviews.toLocaleString('en-IN')} reviews)` : ''}</div>` : ''}
                    ${store.link ? `<a href="${escapeHtml(store.link)}" target="_blank" rel="noopener" class="view-link">View on Google Shopping →</a>` : ''}
                </div>
                <div class="price-info">
                    <span class="price">${formatPrice(store.price)}</span>
                    ${store.original_price ? `<span class="original">${formatPrice(store.original_price)}</span>` : ''}
                    ${store.discount_percent ? `<span class="discount">${store.discount_percent}% off</span>` : ''}
                </div>
            </div>
        `;
    }

    resultsArea.innerHTML = html;
}

// Basic HTML escaping to prevent XSS when injecting API data into the page
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// Event listeners
searchBtn.addEventListener('click', () => searchProduct(searchInput.value));

searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') searchProduct(searchInput.value);
});

chips.forEach(chip => {
    chip.addEventListener('click', () => {
        const query = chip.dataset.query;
        searchInput.value = query;
        searchProduct(query);
    });
});