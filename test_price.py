from dotenv import load_dotenv
load_dotenv()

from app.services.serpapi_service import fetch_shopping_results
from app.services.price_service import _parse_listings, _detect_category, _is_relevant_to_query, _is_junk_listing

query = "sony wh-1000xm5"

print("--- Step 1: Raw SerpAPI results ---")
raw = fetch_shopping_results(query)
print(f"Total raw results: {len(raw)}")
for item in raw[:5]:
    print(f"  - {item.get('title')} | price: {item.get('extracted_price')} | source: {item.get('source')}")

print("\n--- Step 2: After filtering ---")
category = _detect_category(query)
print(f"Detected category: {category}")

for item in raw[:10]:
    title = item.get("title", "")
    price = item.get("extracted_price")
    if not price:
        print(f"  SKIPPED (no price): {title}")
        continue
    if _is_junk_listing(title, price, query, category):
        print(f"  SKIPPED (junk): {title}")
        continue
    if not _is_relevant_to_query(title, query):
        print(f"  SKIPPED (not relevant): {title}")
        continue
    print(f"  KEPT: {title} | ₹{price}")

print("\n--- Step 3: Final parsed listings ---")
listings = _parse_listings(raw, query=query)
print(f"Final count: {len(listings)}")

print("\n--- Step 4: Store breakdown of final listings ---")
from collections import Counter
store_counts = Counter(l["store"] for l in listings)
print(store_counts)

print("\n--- All sources seen ---")
for l in listings:
    print(f"  {l['store']:10} | {l['store_name']:20} | ₹{l['price']}")