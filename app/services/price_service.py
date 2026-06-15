import time
from .serpapi_service import fetch_shopping_results

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


def _parse_listings(raw_results):
    """
    Convert raw SerpAPI results into clean listing dicts.
    Skips anything with no usable price.
    """
    listings = []
    for item in raw_results:
        price = item.get("extracted_price")
        if not price:
            continue

        listings.append({
            "title": item.get("title"),
            "store": _normalize_store(item.get("source")),
            "store_name": item.get("source", "Unknown"),
            "price": price,
            "original_price": item.get("extracted_old_price"),
            "link": item.get("product_link") or item.get("link"),
            "thumbnail": item.get("thumbnail"),
            "rating": item.get("rating"),
            "reviews": item.get("reviews"),
        })

    listings.sort(key=lambda x: x["price"])
    return listings


def _discount_percent(price, original):
    """Calculate discount percentage, returns None if not applicable."""
    if original and original > price:
        return round((1 - price / original) * 100)
    return None


def get_best_deal(listings):
    """
    Find the single cheapest listing across all stores.
    Returns None if no listings available.
    """
    if not listings:
        return None

    cheapest = listings[0]
    most_expensive = listings[-1]
    savings = round(most_expensive["price"] - cheapest["price"], 2)
    discount = _discount_percent(cheapest["price"], cheapest.get("original_price"))

    return {
        "title": cheapest["title"],
        "store": cheapest["store"],
        "store_name": cheapest["store_name"],
        "price": cheapest["price"],
        "original_price": cheapest.get("original_price"),
        "discount_percent": discount,
        "link": cheapest["link"],
        "savings_vs_most_expensive": savings,
    }


def get_store_comparison(listings):
    """
    Build a per-store comparison table.
    For each known Indian store, find the cheapest listing from that store.
    This gives a clean "Amazon vs Flipkart vs Croma vs Reliance" table.
    """
    store_best = {}

    for item in listings:
        store = item["store"]
        if store == "other":
            continue
        # Keep only the cheapest listing per store
        if store not in store_best or item["price"] < store_best[store]["price"]:
            store_best[store] = item

    # Build the final comparison list, sorted cheapest first
    comparison = []
    for store_key in ["amazon", "flipkart", "croma", "reliance"]:
        if store_key in store_best:
            item = store_best[store_key]
            discount = _discount_percent(item["price"], item.get("original_price"))
            comparison.append({
                "store": store_key,
                "store_name": item["store_name"],
                "title": item["title"],
                "price": item["price"],
                "original_price": item.get("original_price"),
                "discount_percent": discount,
                "link": item["link"],
                "rating": item.get("rating"),
                "reviews": item.get("reviews"),
            })
        else:
            # Store had no listings for this product
            comparison.append({
                "store": store_key,
                "store_name": store_key.capitalize(),
                "available": False
            })

    comparison.sort(key=lambda x: x.get("price", float("inf")))
    return comparison


def generate_recommendation(best_deal, store_comparison):
    """
    Generate a plain-English recommendation string.
    No AI needed — pure logic based on the data.
    """
    if not best_deal:
        return "No listings found for this product in Indian stores."

    available = [s for s in store_comparison if s.get("available", True) and s.get("price")]

    if not available:
        return "No price data available from major Indian stores for this product."

    best_store_name = best_deal["store_name"]
    best_price = best_deal["price"]
    savings = best_deal["savings_vs_most_expensive"]
    discount = best_deal["discount_percent"]

    # Base recommendation
    rec = f"Buy from {best_store_name} at ₹{best_price:,.0f}"

    # Add discount info if available
    if discount:
        rec += f" ({discount}% off MRP)"

    # Add savings info if meaningful (more than ₹100 difference)
    if savings and savings > 100:
        second_cheapest = available[1] if len(available) > 1 else None
        if second_cheapest:
            rec += (
                f". You save ₹{savings:,.0f} compared to "
                f"{second_cheapest['store_name']} "
                f"(₹{second_cheapest['price']:,.0f})"
            )
    else:
        rec += ". Prices are similar across stores — any option is fine."

    return rec


def search_products(query):
    """
    Main entry point. Returns structured comparison data for a query.
    Uses in-memory cache to avoid burning SerpAPI quota.
    """
    query_key = query.strip().lower()

    # Return cached result if still fresh
    cached = _cache.get(query_key)
    if cached and (time.time() - cached[0] < CACHE_TTL_SECONDS):
        return cached[1]

    # Fetch and process fresh data
    raw_results = fetch_shopping_results(query)
    listings = _parse_listings(raw_results)
    best_deal = get_best_deal(listings)
    store_comparison = get_store_comparison(listings)
    recommendation = generate_recommendation(best_deal, store_comparison)

    result = {
        "best_deal": best_deal,
        "store_comparison": store_comparison,
        "recommendation": recommendation,
        "all_listings_count": len(listings),
    }

    _cache[query_key] = (time.time(), result)
    return result