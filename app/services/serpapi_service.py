import os
import requests

SERPAPI_URL = "https://serpapi.com/search"


def fetch_shopping_results(query):
    """
    Calls SerpAPI's Google Shopping engine for the given query,
    biased toward Indian results.

    Returns the raw 'shopping_results' list from SerpAPI.
    Raises RuntimeError with a friendly message on failure.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_KEY not found. Add it to your .env file.")

    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "in",                 # India
        "hl": "en",
        "google_domain": "google.co.in",
        "api_key": api_key,
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"SerpAPI request failed: {e}")

    data = response.json()

    if "error" in data:
        raise RuntimeError(f"SerpAPI error: {data['error']}")

    return data.get("shopping_results", [])


def fetch_amazon_asin(query, domain="amazon.in"):
    """
    Search Amazon via SerpAPI to find the ASIN of the top matching product.
    Returns None if nothing found or the request fails.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_KEY not found. Add it to your .env file.")

    params = {
        "engine": "amazon",
        "amazon_domain": domain,
        "k": query,
        "api_key": api_key,
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    data = response.json()
    results = data.get("organic_results", [])

    if not results:
        return None

    # Take the first result's ASIN
    return results[0].get("asin")


def fetch_amazon_reviews(asin, domain="amazon.in"):
    """
    Given an ASIN, fetch the product's review summary and sentiment breakdown.
    Returns None if the request fails or no review data exists.
    """
    if not asin:
        return None

    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_KEY not found. Add it to your .env file.")

    params = {
        "engine": "amazon_product",
        "amazon_domain": domain,
        "asin": asin,
        "api_key": api_key,
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    data = response.json()
    return data.get("reviews_information")