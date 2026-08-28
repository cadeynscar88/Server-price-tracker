#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OBS = DATA / 'observations'
PRODUCTS = json.loads((DATA / 'products.json').read_text())
NOW = datetime.now(timezone.utc)
STALE_AFTER = timedelta(days=7)

RETAILER_NAMES = {
    'amazon': 'Amazon',
    'newegg': 'Newegg',
    'walmart': 'Walmart',
    'bestbuy': 'Best Buy',
    'bh': 'B&H Photo',
    'microcenter': 'Micro Center',
}


def parse_ts(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def all_observations():
    rows = []
    for product in PRODUCTS:
        path = OBS / f"{product['id']}.json"
        if not path.exists():
            continue
        try:
            arr = json.loads(path.read_text())
        except Exception:
            continue
        for row in arr:
            if isinstance(row, dict):
                row = dict(row)
                row['_product_id'] = product['id']
                rows.append(row)
    return rows


rows = all_observations()
retailers = []
for slug, name in RETAILER_NAMES.items():
    rrows = [r for r in rows if r.get('retailer') == slug]
    verified = [r for r in rrows if r.get('status') == 'verified' and isinstance(r.get('price'), (int, float)) and parse_ts(r.get('timestamp'))]
    latest_verified = max(verified, key=lambda r: parse_ts(r.get('timestamp'))) if verified else None
    latest_any = max(rrows, key=lambda r: parse_ts(r.get('timestamp')) or datetime.min.replace(tzinfo=timezone.utc)) if rrows else None
    age_days = None
    if latest_verified:
        age_days = max(0, (NOW - parse_ts(latest_verified['timestamp'])).total_seconds() / 86400)

    latest_status = (latest_any or {}).get('status')
    missing_flag = latest_status in {'not_found', 'check_failed'}
    if latest_verified is None:
        state = 'red' if missing_flag else 'gray'
        label = 'no verified price'
    elif age_days is not None and age_days > 7:
        state = 'yellow'
        label = f'price is {int(age_days)} days old'
    elif missing_flag:
        # Keep the price fresh/usable but visibly flag that the latest search did not return this retailer.
        state = 'red'
        label = 'missing from latest search'
    else:
        state = 'green'
        label = 'fresh within 7 days'

    retailers.append({
        'id': slug,
        'name': name,
        'state': state,
        'status': label,
        'last_verified_at': latest_verified.get('timestamp') if latest_verified else None,
        'last_verified_price': latest_verified.get('price') if latest_verified else None,
        'latest_check_status': latest_status,
    })

summary = {
    'generated_at': NOW.isoformat(),
    'retailers': retailers,
    'freshness_policy': {
        'green': 'verified price is 7 days old or newer and latest check returned the retailer',
        'yellow': 'last verified price is more than 7 days old',
        'red': 'retailer missing from latest search, check failed, or no verified price after a failed/missing result',
        'gray': 'not checked/configured yet'
    },
    'note': 'Missing results never erase the last verified price and no price is inferred.'
}
(DATA / 'retailer_status.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
