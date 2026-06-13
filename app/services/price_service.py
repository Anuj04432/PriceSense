import time
from .serpapi_service import fetch_shopping_results

# Simple in-memory cache so repeated searches don't burn your SerpAPI quota.
# NOTE: resets whenever Flask's debug reloader restarts (i.e. on file save).
_cache = {}
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes

KNOWN_STORES = {
    "amazon": ["amazon"],
    "flipkart": ["flipkart"],
    "croma": ["croma"],
    "reliance": ["reliance digital", "reliancedigital", "reliance"],
}


def _normalize_store(source_name):
    """Map SerpAPI's raw 'source' string to one of our known store keys."""
    if not source_name:
        return "other"
    name = source_name.lower()
    for store_key, aliases in KNOWN_STORES.items():
        if any(alias in name for alias in aliases):
            return store_key
    return "other"


def search_products(query):
    query_key = query.strip().lower()

    cached = _cache.get(query_key)
    if cached and (time.time() - cached[0] < CACHE_TTL_SECONDS):
        return cached[1]

    raw_results = fetch_shopping_results(query)

    listings = []
    for item in raw_results:
        price = item.get("extracted_price")
        if price is None:
            continue  # skip listings with no usable numeric price

        listings.append({
            "title": item.get("title"),
            "store": _normalize_store(item.get("source")),
            "store_name": item.get("source"),
            "price": price,
            "original_price": item.get("extracted_old_price"),
            "link": item.get("product_link") or item.get("link"),
            "thumbnail": item.get("thumbnail"),
            "rating": item.get("rating"),
        })

    listings.sort(key=lambda x: x["price"])  # cheapest first

    _cache[query_key] = (time.time(), listings)
    return listings


def get_best_deal(listings):
    if not listings:
        return None

    cheapest = listings[0]
    most_expensive = listings[-1]

    return {
        "store": cheapest["store"],
        "store_name": cheapest["store_name"],
        "price": cheapest["price"],
        "title": cheapest["title"],
        "link": cheapest["link"],
        "savings": round(most_expensive["price"] - cheapest["price"], 2),
    }