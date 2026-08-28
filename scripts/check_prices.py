#!/usr/bin/env python3
"""SerpApi Google Shopping collector for GitHub Actions.

One search can yield offers from multiple retailers. The browser/PWA never sees the
API key; SERPAPI_API_KEY is read only from GitHub Actions Secrets.
"""
import json, os, re
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OBS = DATA / 'observations'
PRODUCTS = json.loads((DATA / 'products.json').read_text())
OBS.mkdir(exist_ok=True)

RETAILERS = {
    'amazon': ('amazon', 'amazon.com'),
    'newegg': ('newegg', 'newegg.com'),
    'walmart': ('walmart', 'walmart.com'),
    'bestbuy': ('best buy', 'bestbuy.com'),
    'bh': ('b&h', 'b&h photo', 'bhphotovideo'),
    'microcenter': ('micro center', 'microcenter'),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def append(pid, observation):
    path = OBS / f'{pid}.json'
    arr = json.loads(path.read_text()) if path.exists() else []
    arr.append(observation)
    path.write_text(json.dumps(arr, indent=2))


def retailer_slug(source):
    s = re.sub(r'\s+', ' ', str(source or '').lower()).strip()
    for slug, needles in RETAILERS.items():
        if any(n in s for n in needles):
            return slug
    return None


def serpapi_search(query, key):
    params = {
        'engine': 'google_shopping',
        'q': query,
        'hl': 'en',
        'gl': 'us',
        'api_key': key,
    }
    url = 'https://serpapi.com/search.json?' + urlencode(params)
    req = Request(url, headers={'User-Agent': 'PrivateServerPriceTracker/1.2'})
    with urlopen(req, timeout=30) as response:
        payload = json.loads(response.read())
    if payload.get('error'):
        raise RuntimeError(payload['error'])
    return payload


def extracted_price(result):
    value = result.get('extracted_price')
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(result.get('price') or '')
    m = re.search(r'([0-9][0-9,]*(?:\.[0-9]{1,2})?)', raw)
    return float(m.group(1).replace(',', '')) if m else None


def source_url(result, fallback=''):
    # Google Shopping may provide merchant/product links in different fields.
    return result.get('product_link') or result.get('link') or fallback


def expected_retailers(product):
    # Retailers already present in the tracker's link matrix are the retailers
    # we flag when a Shopping search does not return an offer.
    return list((product.get('retailer_search_urls') or {}).keys())


def collect_product(product, key, ts):
    query = (product.get('search_terms') or [product.get('model') or product.get('label')])[0]
    payload = serpapi_search(query, key)
    best = {}
    for result in payload.get('shopping_results') or []:
        slug = retailer_slug(result.get('source') or result.get('seller') or result.get('merchant'))
        if not slug:
            continue
        price = extracted_price(result)
        if price is None:
            continue
        candidate = {
            'component_id': product['id'],
            'component': product['label'],
            'model': result.get('title') or product.get('model', ''),
            'retailer': slug,
            'price': price,
            'currency': 'USD',
            'source_url': source_url(result, (product.get('retailer_search_urls') or {}).get(slug, '')),
            'availability': 'Shown in Google Shopping',
            'status': 'verified',
            'method': 'serpapi_google_shopping',
            'timestamp': ts,
            'notes': '',
        }
        if slug not in best or price < best[slug]['price']:
            best[slug] = candidate

    for slug in expected_retailers(product):
        if slug in best:
            append(product['id'], best[slug])
        else:
            append(product['id'], {
                'component_id': product['id'],
                'component': product['label'],
                'model': product.get('model', ''),
                'retailer': slug,
                'source_url': (product.get('retailer_search_urls') or {}).get(slug, ''),
                'availability': 'Unknown',
                'status': 'not_found',
                'method': 'serpapi_google_shopping',
                'timestamp': ts,
                'notes': 'Retailer was not present in the latest Google Shopping result for this item.',
            })
    return len(best), len(expected_retailers(product)) - len(best)


def selected_products(batch_size=7):
    if not PRODUCTS:
        return []
    n = len(PRODUCTS)
    # Seven/day keeps a 31-day month at 217 scheduled searches, leaving room
    # under SerpApi's 250-search free tier for manual runs.
    start = (date.today().toordinal() * batch_size) % n
    return [PRODUCTS[(start + i) % n] for i in range(min(batch_size, n))]


def main():
    ts = now()
    key = os.getenv('SERPAPI_API_KEY', '').strip()
    batch_size = max(1, min(int(os.getenv('SERPAPI_DAILY_BATCH', '7')), len(PRODUCTS) or 1))
    selected = selected_products(batch_size)
    verified = missing = failures = 0

    if not key:
        status = {
            'checked_at': ts,
            'source': 'serpapi_google_shopping',
            'searches_attempted': 0,
            'verified_retailer_offers': 0,
            'missing_retailer_results': 0,
            'check_failures': 1,
            'note': 'SERPAPI_API_KEY is not configured in GitHub Actions Secrets.'
        }
        (DATA / 'collector_status.json').write_text(json.dumps(status, indent=2))
        print(json.dumps(status, indent=2))
        return

    for product in selected:
        try:
            v, m = collect_product(product, key, ts)
            verified += v
            missing += m
        except Exception as exc:
            failures += 1
            for slug in expected_retailers(product):
                append(product['id'], {
                    'component_id': product['id'],
                    'component': product['label'],
                    'model': product.get('model', ''),
                    'retailer': slug,
                    'source_url': (product.get('retailer_search_urls') or {}).get(slug, ''),
                    'availability': 'Unknown',
                    'status': 'check_failed',
                    'method': 'serpapi_google_shopping',
                    'timestamp': ts,
                    'notes': str(exc),
                })

    status = {
        'checked_at': ts,
        'source': 'serpapi_google_shopping',
        'searches_attempted': len(selected),
        'batch_size': batch_size,
        'verified_retailer_offers': verified,
        'missing_retailer_results': missing,
        'check_failures': failures,
        'note': 'A missing retailer is flagged; its last verified price is retained and never guessed.'
    }
    (DATA / 'collector_status.json').write_text(json.dumps(status, indent=2))
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()
