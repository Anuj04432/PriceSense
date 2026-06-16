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

        // Fire review fetch separately — don't block the price comparison
        // from showing while we wait on the slower reviews call.
        fetchReviews(query);

    } catch (err) {
        renderError('Could not reach the server. Check your connection and try again.');
    } finally {
        searchBtn.disabled = false;
    }
}

async function fetchReviews(query) {
    // Insert a loading placeholder for the reviews section
    const reviewsContainer = document.createElement('div');
    reviewsContainer.id = 'reviews-section';
    reviewsContainer.innerHTML = `<div class="reviews-loading">Loading customer reviews...</div>`;
    resultsArea.appendChild(reviewsContainer);

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}&reviews=true`);
        const data = await response.json();

        if (!response.ok || !data.review_insights) {
            reviewsContainer.innerHTML = '';  // Silently hide — not every product has review data
            return;
        }

        renderReviews(data.review_insights, reviewsContainer);

    } catch (err) {
        reviewsContainer.innerHTML = '';  // Fail silently, price comparison already shown
    }
}

function renderReviews(insights, container) {
    const { summary, top_reviews, source_domain } = insights;
    const domainLabel = source_domain === 'amazon.in' ? 'Amazon.in' : 'Amazon.com (US reviews)';

    let html = `
        <div class="reviews-card">
            <div class="reviews-header">
                💬 <strong>Customer Sentiment</strong>
                <span class="reviews-source">Source: ${escapeHtml(domainLabel)}</span>
            </div>
            <p class="reviews-summary">${escapeHtml(summary)}</p>
    `;

    if (top_reviews && top_reviews.length > 0) {
        html += `<div class="reviews-list">`;
        for (const r of top_reviews) {
            html += `
                <div class="review-item">
                    <div class="review-item-header">
                        <span class="review-stars">${'★'.repeat(Math.round(r.rating))}</span>
                        <span class="review-title">${escapeHtml(r.title || '')}</span>
                    </div>
                    <p class="review-snippet">${escapeHtml(r.snippet)}</p>
                    <div class="review-meta">
                        — ${escapeHtml(r.author || 'Anonymous')}
                        ${r.verified_purchase ? '<span class="verified-badge">✓ Verified Purchase</span>' : ''}
                    </div>
                </div>
            `;
        }
        html += `</div>`;
    }

    html += `</div>`;
    container.innerHTML = html;
}

function renderError(message) {
    resultsArea.innerHTML = `<div class="error-box">⚠️ ${escapeHtml(message)}</div>`;
}

function renderResults(data, query) {
    const { recommendation, store_comparison, all_listings_count, main_stores_available, other_sellers } = data;

    if (!all_listings_count || all_listings_count === 0) {
        resultsArea.innerHTML = `
            <div class="no-results">
                No results found for "${escapeHtml(query)}". Try a different search term.
            </div>
        `;
        return;
    }

    let html = '';

    if (recommendation) {
        html += `
            <div class="recommendation-banner ${!main_stores_available ? 'warning' : ''}">
                ${main_stores_available ? '💡' : '⚠️'} <strong>${main_stores_available ? 'Recommendation' : 'Heads up'}:</strong> ${escapeHtml(recommendation)}
            </div>
        `;
    }

    if (main_stores_available) {
        html += `<div class="results-header">Showing prices from ${all_listings_count} listings across 4 stores</div>`;

        const availablePrices = store_comparison.filter(s => s.available && s.price).map(s => s.price);
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
    } else if (other_sellers && other_sellers.length > 0) {
        html += `<div class="results-header">Not on major stores right now — here's what we found elsewhere</div>`;

        for (const seller of other_sellers) {
            html += `
                <div class="store-card other-seller">
                    <div class="store-info">
                        <div class="store-name-row">
                            <span class="store-name">${escapeHtml(seller.store_name)}</span>
                        </div>
                        <div class="product-title">${escapeHtml(seller.title || '')}</div>
                        ${seller.link ? `<a href="${escapeHtml(seller.link)}" target="_blank" rel="noopener" class="view-link">View on Google Shopping →</a>` : ''}
                    </div>
                    <div class="price-info">
                        <span class="price">${formatPrice(seller.price)}</span>
                        ${seller.discount_percent ? `<span class="discount">${seller.discount_percent}% off</span>` : ''}
                    </div>
                </div>
            `;
        }
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