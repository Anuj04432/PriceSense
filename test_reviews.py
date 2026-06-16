from dotenv import load_dotenv
load_dotenv()

from app.services.price_service import get_review_insights

result = get_review_insights("sony wh-1000xm5")

print("--- Summary ---")
print(result["summary"] if result else "None")

print("\n--- Top Reviews ---")
for r in result["top_reviews"]:
    print(f"\n{r['rating']}★ — {r['title']} (by {r['author']}, verified: {r['verified_purchase']})")
    print(r['snippet'])

print("\n--- Source ---")
print(result["source_domain"])