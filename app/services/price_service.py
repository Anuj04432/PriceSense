import time
import re
from .serpapi_service import fetch_shopping_results
from .serpapi_service import fetch_shopping_results, fetch_amazon_asin, fetch_amazon_reviews

_cache = {}
CACHE_TTL_SECONDS = 30 * 60

KNOWN_STORES = {
    "amazon":   ["amazon.in", "amazon"],
    "flipkart": ["flipkart"],
    "croma":    ["croma"],
    "reliance": ["reliance digital", "reliancedigital", "reliance"],
}

# These words in a title almost certainly mean it's NOT the main product
JUNK_TITLE_KEYWORDS = [
    # Books / guides
    "book", "guide", "manual", "paperback", "kindle", "ebook",
    "comprehensive", "ultimate guide", "how to", "comparison",
    # Accessories
    "case", "cover", "tempered glass", "screen protector",
    "charger", "cable", "adapter", "pouch", "wallet", "skin",
    "holder", "stand", "mount", "sleeve", "bag", "strap",
    # Spare parts / repair
    "repair", "replacement", "spare part", "parts", "board",
    "battery replacement", "lcd", "digitizer", "flex cable",
    # Second-hand qualifiers that signal parts
    "grade a", "grade b", "fair condition", "cracked",
]

# These words in store name suggest it's a foreign/grey market seller
FOREIGN_STORE_KEYWORDS = [
    "us shipping", "usa", "united states", "uk shipping",
    "wireless source", "certified unlocked",
]

# Minimum realistic prices per category (₹)
# Anything below this is definitely not the main product
CATEGORY_MIN_PRICES = {
    "phone":      15000,
    "laptop":     20000,
    "tv":         10000,
    "headphones":  3000,   # Kept low — earbuds can be cheap
    "default":     3000,
}


def _normalize_store(source_name):
    if not source_name:
        return "other"
    name = source_name.lower()
    for store_key, aliases in KNOWN_STORES.items():
        if any(alias in name for alias in aliases):
            return store_key
    return "other"


def _detect_category(query):
    """Guess product category from the search query."""
    q = query.lower()
    if any(w in q for w in ["iphone", "samsung galaxy", "oneplus", "pixel", "phone", "mobile"]):
        return "phone"
    if any(w in q for w in ["laptop", "macbook", "thinkpad", "notebook"]):
        return "laptop"
    if any(w in q for w in ["tv", "television", "qled", "oled"]):
        return "tv"
    if any(w in q for w in ["headphone", "earphone", "earbud", "airpod", "wh-", "wf-", "xm5"]):
        return "headphones"
    return "default"


def _is_junk_listing(title, price, query, category):
    """Return True if this listing should be filtered out."""
    if not title:
        return True

    title_lower = title.lower()
    store_lower = title_lower  # also check title for store hints

    # 1. Junk keywords in title
    for keyword in JUNK_TITLE_KEYWORDS:
        if keyword in title_lower:
            return True

    # 2. Price too low for this category
    min_price = CATEGORY_MIN_PRICES.get(category, CATEGORY_MIN_PRICES["default"])
    if price and price < min_price:
        return True

    # 3. Foreign seller signals in title
    for keyword in FOREIGN_STORE_KEYWORDS:
        if keyword in title_lower:
            return True

    return False


def _is_relevant_to_query(title, query):
    """
    At least 60% of meaningful query words must appear in the title.
    Also blocks titles that contain numbers that DIFFER from the query
    (catches S25 when searching S24, iPhone 14 when searching iPhone 15, etc.)
    """
    if not title:
        return False

    title_lower = re.sub(r'[^a-z0-9\s]', ' ', title.lower())
    query_lower = re.sub(r'[^a-z0-9\s]', ' ', query.lower())

    query_words = [w for w in query_lower.split() if len(w) > 2]
    if not query_words:
        return True

    matches = sum(1 for w in query_words if w in title_lower)
    match_ratio = matches / len(query_words)

    if match_ratio < 0.6:
        return False

    # Extra check: if query has model numbers (e.g. s24, xm5, 15),
    # make sure those exact numbers appear in the title too
    query_numbers = re.findall(r'\b\d{2,5}\b', query_lower)
    for num in query_numbers:
        # Title must contain this number
        if num not in re.findall(r'\b\d{2,5}\b', title_lower):
            return False

    return True


def _is_price_realistic(price, original):
    """Filter out bad MRP data."""
    if original is None:
        return True
    if original < price:
        return False
    if price < original * 0.30:
        return False
    return True


def _parse_listings(raw_results, query=""):
    category = _detect_category(query)
    listings = []

    for item in raw_results:
        price = item.get("extracted_price")
        if not price:
            continue

        title = item.get("title", "")

        if _is_junk_listing(title, price, query, category):
            continue

        if query and not _is_relevant_to_query(title, query):
            continue

        original = item.get("extracted_old_price")
        if not _is_price_realistic(price, original):
            original = None

        # Sanitize reviews — must be integer and at least 10
        reviews = item.get("reviews")
        if reviews is not None:
            if not isinstance(reviews, int) or reviews < 10:
                reviews = None

        listings.append({
            "title":          title,
            "store":          _normalize_store(item.get("source")),
            "store_name":     item.get("source", "Unknown"),
            "price":          price,
            "original_price": original,
            "link":           item.get("product_link") or item.get("link"),
            "thumbnail":      item.get("thumbnail"),
            "rating":         item.get("rating"),
            "reviews":        reviews,
        })

    listings.sort(key=lambda x: x["price"])
    return listings


def _discount_percent(price, original):
    if original and original > price:
        return round((1 - price / original) * 100)
    return None


def get_best_deal(listings):
    """Return cheapest listing from a KNOWN Indian store (not 'other')."""
    # Prefer known stores first
    known = [l for l in listings if l["store"] != "other"]
    pool = known if known else listings

    if not pool:
        return None

    cheapest = pool[0]
    most_expensive = pool[-1]
    savings = round(most_expensive["price"] - cheapest["price"], 2)
    discount = _discount_percent(cheapest["price"], cheapest.get("original_price"))

    return {
        "title":                    cheapest["title"],
        "store":                    cheapest["store"],
        "store_name":               cheapest["store_name"],
        "price":                    cheapest["price"],
        "original_price":           cheapest.get("original_price"),
        "discount_percent":         discount,
        "link":                     cheapest["link"],
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
                "store":          store_key,
                "store_name":     item["store_name"],
                "title":          item["title"],
                "price":          item["price"],
                "original_price": item.get("original_price"),
                "discount_percent": discount,
                "link":           item["link"],
                "rating":         item.get("rating"),
                "reviews":        item.get("reviews"),
                "available":      True,
            })
        else:
            comparison.append({
                "store":      store_key,
                "store_name": store_key.capitalize(),
                "available":  False,
            })

    comparison.sort(key=lambda x: x.get("price", float("inf")))
    return comparison


def generate_recommendation(best_deal, store_comparison, other_sellers=None, main_stores_available=True):
    if not main_stores_available:
        if other_sellers:
            cheapest_other = other_sellers[0]
            return (
                f"Not currently listed on Amazon, Flipkart, Croma, or Reliance Digital. "
                f"Cheapest option found: {cheapest_other['store_name']} at "
                f"₹{cheapest_other['price']:,.0f}. Verify seller credibility before purchasing."
            )
        return "No listings found for this product right now. Try a more specific search term."

    if not best_deal:
        return "No listings found for this product in Indian stores."

    available = [s for s in store_comparison if s.get("available") and s.get("price")]
    if not available:
        return "No price data found from Amazon, Flipkart, Croma or Reliance for this product."

    rec = f"Buy from {best_deal['store_name']} at ₹{best_deal['price']:,.0f}"

    if best_deal["discount_percent"]:
        rec += f" ({best_deal['discount_percent']}% off MRP)"

    savings = best_deal["savings_vs_most_expensive"]
    if savings and savings > 100 and len(available) > 1:
        second = available[1]
        rec += (
            f". You save ₹{savings:,.0f} compared to "
            f"{second['store_name']} (₹{second['price']:,.0f})"
        )
    else:
        rec += ". Prices are similar across stores — any option is fine."

    return rec

def search_products(query, include_reviews=False):
    query_key = query.strip().lower() + ("_reviews" if include_reviews else "")

    cached = _cache.get(query_key)
    if cached and (time.time() - cached[0] < CACHE_TTL_SECONDS):
        return cached[1]

    raw_results = fetch_shopping_results(query)
    listings = _parse_listings(raw_results, query=query)
    best_deal = get_best_deal(listings)
    store_comparison = get_store_comparison(listings)

    # Check if ANY of the 4 main stores actually had a listing
    main_stores_available = any(s.get("available") for s in store_comparison)

    other_sellers = []
    if not main_stores_available:
        other_sellers = get_other_sellers(listings)

    recommendation = generate_recommendation(best_deal, store_comparison, other_sellers, main_stores_available)

    result = {
        "best_deal":             best_deal,
        "store_comparison":      store_comparison,
        "main_stores_available": main_stores_available,
        "other_sellers":         other_sellers,
        "recommendation":        recommendation,
        "all_listings_count":    len(listings),
    }

    if include_reviews:
        result["review_insights"] = get_review_insights(query)

    _cache[query_key] = (time.time(), result)
    return result


def get_review_insights(query):
    """
    Fetch a review summary + a couple of top verified reviews for a product.
    Tries amazon.in first; falls back to amazon.com since review-summary
    coverage is inconsistent across domains.

    Returns a dict like:
    {
        "summary": "Customers praise the headphones' sound quality...",
        "top_reviews": [
            {"title": "...", "rating": 5.0, "author": "...", "verified_purchase": True, "snippet": "..."},
            ...
        ],
        "source_domain": "amazon.com"
    }
    or None if no review data could be found.
    """
    for domain in ["amazon.in", "amazon.com"]:
        asin = fetch_amazon_asin(query, domain=domain)
        if not asin:
            continue

        reviews_info = fetch_amazon_reviews(asin, domain=domain)
        if not reviews_info:
            continue

        summary_block = reviews_info.get("summary", {})
        summary_text = summary_block.get("text")

        if not summary_text:
            continue

        # Pull the top 3 verified-purchase reviews, prioritizing 4-5 star
        # ones first so the snippet feels representative, not cherry-picked
        # toward complaints.
        authors_reviews = reviews_info.get("authors_reviews", [])
        verified = [r for r in authors_reviews if r.get("verified_purchase")]
        verified.sort(key=lambda r: r.get("rating", 0), reverse=True)

        top_reviews = []
        for r in verified[:3]:
            text = r.get("text", "")
            # Trim long review text to a readable snippet
            snippet = text[:220] + "..." if len(text) > 220 else text

            top_reviews.append({
                "title": r.get("title"),
                "rating": r.get("rating"),
                "author": r.get("author"),
                "verified_purchase": r.get("verified_purchase", False),
                "snippet": snippet,
            })

        return {
            "summary": summary_text,
            "top_reviews": top_reviews,
            "source_domain": domain,
        }

    return None


def get_other_sellers(listings, limit=5):
    """
    Return the cheapest listings from sellers OUTSIDE the 4 known stores.
    Used as a fallback display when none of Amazon/Flipkart/Croma/Reliance
    appear in the results for this product.
    """
    others = [l for l in listings if l["store"] == "other"]
    others.sort(key=lambda x: x["price"])

    return [
        {
            "store_name":      o["store_name"],
            "title":           o["title"],
            "price":           o["price"],
            "original_price":  o.get("original_price"),
            "discount_percent": _discount_percent(o["price"], o.get("original_price")),
            "link":            o["link"],
            "rating":          o.get("rating"),
        }
        for o in others[:limit]
    ]