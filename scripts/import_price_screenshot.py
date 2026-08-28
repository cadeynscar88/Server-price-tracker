#!/usr/bin/env python3
"""Import a manually submitted retailer screenshot from an owner-created GitHub issue.

The issue is prefilled by the PWA. This script only downloads GitHub-hosted image
attachments, OCRs them locally on the GitHub runner, and records a price only when
there is one unambiguous plausible price. Ambiguous screenshots are left for review.
"""
import json, os, re, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OBS = DATA / 'observations'
PRODUCTS = {p['id']: p for p in json.loads((DATA / 'products.json').read_text())}
RESULT = ROOT / 'manual_result.json'


def finish(**kwargs):
    RESULT.write_text(json.dumps(kwargs, indent=2))
    print(json.dumps(kwargs, indent=2))


def field(body, name):
    m = re.search(rf'(?mi)^\s*{re.escape(name)}\s*:\s*(.+?)\s*$', body or '')
    return m.group(1).strip() if m else ''


def attachment_url(body):
    urls = re.findall(r'https://[^\s)]+', body or '')
    allowed = (
        'https://github.com/user-attachments/assets/',
        'https://user-images.githubusercontent.com/',
        'https://private-user-images.githubusercontent.com/',
    )
    for url in urls:
        url = url.rstrip('>.,]')
        if url.startswith(allowed):
            return url
    return ''


def download_image(url):
    token = os.getenv('GITHUB_TOKEN', '').strip()
    headers = {'User-Agent': 'PrivateServerPriceTracker/1.2'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as response:
        ctype = response.headers.get('content-type', '')
        raw = response.read(12 * 1024 * 1024 + 1)
    if len(raw) > 12 * 1024 * 1024:
        raise ValueError('Screenshot is larger than 12 MB.')
    if ctype and not ctype.lower().startswith('image/'):
        raise ValueError(f'Attachment is not an image ({ctype}).')
    suffix = '.png' if 'png' in ctype.lower() else '.jpg'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw); tmp.close()
    return tmp.name


def ocr(path):
    proc = subprocess.run(['tesseract', path, 'stdout', '--psm', '6'], text=True, capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or 'Tesseract OCR failed.')
    return proc.stdout


def candidates(text):
    excluded = ('/mo', 'month', 'monthly', 'save ', 'savings', ' off', 'discount', 'warranty', 'protection', 'trade-in', 'trade in')
    values = []
    for line in text.splitlines():
        low = line.lower()
        if any(x in low for x in excluded):
            continue
        # Prefer explicit currency-looking amounts to avoid model numbers/specs.
        for m in re.finditer(r'\$\s*([0-9]{1,5}(?:,[0-9]{3})*(?:[\.,][0-9]{2})?)', line):
            raw = m.group(1).replace(',', '')
            try:
                val = round(float(raw), 2)
            except Exception:
                continue
            if 10 <= val <= 15000:
                values.append(val)
    return sorted(set(values))


def append_observation(pid, row):
    path = OBS / f'{pid}.json'
    arr = json.loads(path.read_text()) if path.exists() else []
    arr.append(row)
    path.write_text(json.dumps(arr, indent=2))


def main():
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path:
        return finish(ok=False, message='No GitHub event payload was provided.')
    event = json.loads(Path(event_path).read_text())
    issue = event.get('issue') or {}
    body = issue.get('body') or ''
    pid = field(body, 'product_id')
    retailer = field(body, 'retailer').lower()
    source_url = field(body, 'source_url')
    if pid not in PRODUCTS:
        return finish(ok=False, message=f'Unknown product_id: {pid or "(missing)"}')
    allowed_retailers = set((PRODUCTS[pid].get('retailer_search_urls') or {}).keys())
    if retailer not in allowed_retailers:
        return finish(ok=False, message=f'Unknown retailer for {pid}: {retailer or "(missing)"}')
    image_url = attachment_url(body)
    if not image_url:
        return finish(ok=False, message='No GitHub-hosted screenshot attachment was found. Attach the screenshot to the issue and edit/resubmit it.')
    try:
        path = download_image(image_url)
        text = ocr(path)
        vals = candidates(text)
    except Exception as exc:
        return finish(ok=False, message=f'Could not read screenshot: {exc}')
    if len(vals) != 1:
        shown = ', '.join(f'${v:,.2f}' for v in vals) if vals else 'none'
        return finish(ok=False, message=f'Screenshot was not unambiguous. Price candidates: {shown}. Crop the screenshot tightly around the current price and re-attach it.')

    price = vals[0]
    product = PRODUCTS[pid]
    ts = datetime.now(timezone.utc).isoformat()
    append_observation(pid, {
        'component_id': pid,
        'component': product['label'],
        'model': product.get('model', ''),
        'retailer': retailer,
        'price': price,
        'currency': 'USD',
        'source_url': source_url,
        'screenshot_url': image_url,
        'availability': 'Human screenshot verification',
        'status': 'verified',
        'method': 'owner_screenshot_ocr',
        'timestamp': ts,
        'notes': f'Price verified from screenshot submitted in GitHub issue #{issue.get("number")}.',
    })
    finish(ok=True, price=price, product_id=pid, retailer=retailer, message=f'Recorded ${price:,.2f} for {product["label"]} at {retailer}.')


if __name__ == '__main__':
    main()
