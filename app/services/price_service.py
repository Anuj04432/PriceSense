import time
import re
from .serpapi_service import fetch_shopping_results

_cache = {}
CACHE_TTL_SECONDS = 30 * 60

KNOWN_STORES = {
    "amazon": ["amazon"],
    "flipkart": ["flipkart"],
    "croma": ["croma"],
    "reliance": ["reliance digital", "reliancedigital", "reliance"],
}

# Titles containing these words are almost certainly not electronics
JUNK_TITLE_KEYWORDS = [
    "book", "guide", "manual", "paperback", "kindle", "ebook",
    "comparison", "comprehensive", "ultimate guide", "how to",
    "case", "cover", "tempered glass", "screen protector",
    "charger", "cable", "adapter", "pouch", "wallet",
]


def _normalize_store(source_name):
    if not source_name:
        return "other"
    name = source_name.lower()
    for store_key, aliases in KNOWN_STORES.items():
        if any(alias in name for alias in aliases):
            return store_key
    return "other"


def _is_junk_listing(title, price):
    """
    Returns True if this listing is clearly not the product we want.
    Filters out books, accessories, and suspiciously low prices.
    """
    if not title:
        return True

    title_lower = title.lower()

    # Filter out books, guides, accessories by title keywords
    for keyword in JUNK_TITLE_KEYWORDS:
        if keyword in title_lower:
            return True

    # Filter out suspiciously low prices (phones/laptops won't be under ₹3000)
    if price and price < 3000:
        return True

    return False


def _is_price_realistic(price, original_price):
    """
    Returns True only if the original_price makes sense relative to price.
    Filters out bad data like original_price=12 when price=113999.
    """
    if original_price is None:
        return True  # No MRP listed is fine — just skip discount calc

    # If original is LESS than current price, it's bad data
    if original_price < price:
        return False

    # If original is more than 70% off, it's likely bad data
    # (real discounts rarely exceed 60-65% even during sales)
    if price < original_price * 0.30:
        return False

    return True


def _parse_listings(raw_results):
    listings = []
    for item in raw_results:
        price = item.get("extracted_price")
        if not price:
            continue

        title = item.get("title", "")

        # Skip junk listings (books, accessories, impossibly cheap items)
        if _is_junk_listing(title, price):
            continue

        original = item.get("extracted_old_price")

        # Sanitize bad original_price data
        if not _is_price_realistic(price, original):
            original = None  # Drop the bad MRP, keep the listing

        listings.append({
            "title": title,
            "store": _normalize_store(item.get("source")),
            "store_name": item.get("source", "Unknown"),
            "price": price,
            "original_price": original,
            "link": item.get("product_link") or item.get("link"),
            "thumbnail": item.get("thumbnail"),
            "rating": item.get("rating"),
            "reviews": item.get("reviews"),
        })

    listings.sort(key=lambda x: x["price"])
    return listings


def _discount_percent(price, original):
    if original and original > price:
        return round((1 - price / original) * 100)
    return None


def get_best_deal(listings):
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
    store_best = {}

    for item in listings:
        store = item["store"]
        if store == "other":
            continue
        if store not in store_best or item["price"] < store_best[store]["price"]:
            store_best[store] = item

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
                "available": True,
            })
        else:
            comparison.append({
                "store": store_key,
                "store_name": store_key.capitalize(),
                "available": False,
            })

    comparison.sort(key=lambda x: x.get("price", float("inf")))
    return comparison


def generate_recommendation(best_deal, store_comparison):
    if not best_deal:
        return "No listings found for this product in Indian stores."

    available = [s for s in store_comparison if s.get("available") and s.get("price")]

    if not available:
        return "No price data available from major Indian stores for this product."

    best_store_name = best_deal["store_name"]
    best_price = best_deal["price"]
    savings = best_deal["savings_vs_most_expensive"]
    discount = best_deal["discount_percent"]

    rec = f"Buy from {best_store_name} at ₹{best_price:,.0f}"

    if discount:
        rec += f" ({discount}% off MRP)"

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
    query_key = query.strip().lower()

    cached = _cache.get(query_key)
    if cached and (time.time() - cached[0] < CACHE_TTL_SECONDS):
        return cached[1]

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