#!/usr/bin/env python3
"""SerpApi Google Shopping collector for GitHub Actions.

Only strongly matched Shopping results become verified observations. Ambiguous or
generic matches are retained as manual_review candidates and are excluded from
build totals. The browser/PWA never sees the API key.
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
REJECT_WORDS = ('refurbished','renewed','used','pre-owned','preowned','open box','open-box')


def now(): return datetime.now(timezone.utc).isoformat()

def append(pid, observation):
    path = OBS / f'{pid}.json'
    arr = json.loads(path.read_text()) if path.exists() else []
    arr.append(observation)
    path.write_text(json.dumps(arr, indent=2))

def norm(value):
    s = str(value or '').lower().replace('&',' and ')
    s = re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def has_all(text, terms): return all(norm(t) in text for t in terms)

def retailer_slug(source):
    s = norm(source)
    for slug, needles in RETAILERS.items():
        if any(norm(n) in s for n in needles): return slug
    return None

def serpapi_search(query, key):
    params={'engine':'google_shopping','q':query,'hl':'en','gl':'us','api_key':key}
    req=Request('https://serpapi.com/search.json?'+urlencode(params),headers={'User-Agent':'PrivateServerPriceTracker/1.3'})
    with urlopen(req,timeout=30) as response: payload=json.loads(response.read())
    if payload.get('error'): raise RuntimeError(payload['error'])
    return payload

def extracted_price(result):
    value=result.get('extracted_price')
    if isinstance(value,(int,float)): return float(value)
    m=re.search(r'([0-9][0-9,]*(?:\.[0-9]{1,2})?)',str(result.get('price') or ''))
    return float(m.group(1).replace(',','')) if m else None

def source_url(result,fallback=''): return result.get('product_link') or result.get('link') or fallback

def expected_retailers(product): return list((product.get('retailer_search_urls') or {}).keys())

def match_result(product, result):
    """Return (strong_match, reason). False means manual review, never verified."""
    title=norm(result.get('title'))
    pid=product.get('id','')
    if not title: return False,'missing product title'
    if any(norm(w) in title for w in REJECT_WORDS): return False,'used/refurb/open-box result rejected'

    # High-value components get explicit model guards to prevent near-model matches.
    explicit={
        'cpu': (('9950x',), ('9950x3d',)),
        'cpu-9950x3d': (('9950x3d',), ()),
        'motherboard': (('proart','x870e'), ()),
        'gpu-5070ti': (('5070','ti'), ()),
        'gpu-5080': (('5080',), ('5080 super','5080 ti')),
        'gpu-5090': (('5090',), ()),
    }
    if pid in explicit:
        required, forbidden=explicit[pid]
        if not has_all(title,required): return False,'required model terms missing'
        if any(norm(x) in title for x in forbidden): return False,'different model variant'
        return True,'explicit model match'

    # Approved NVMe pools must contain the requested capacity plus an approved model family.
    if pid in {'nvme-4tb','nvme-2tb'}:
        cap='4tb' if pid=='nvme-4tb' else '2tb'
        models=('sn850x','nm790','t500')
        if norm(cap) not in title: return False,'wrong/missing capacity'
        if not any(norm(m) in title for m in models): return False,'not an approved SSD model'
        return True,'approved SSD model and capacity'

    # Broad classes are discovery-only until an exact model is selected.
    broad_markers=('class','approved','multiple','prefer','candidate','gpu')
    model=norm(product.get('model'))
    manufacturer=norm(product.get('manufacturer'))
    if pid=='gpu-24gb' or manufacturer in {'','multiple'} and any(x in model for x in broad_markers):
        return False,'generic product class requires manual review'
    if product.get('kind')=='prebuilt' or product.get('category')=='Prebuilt Donor':
        return False,'prebuilt donor requires manual review'

    # For named products, require manufacturer plus distinctive model/spec tokens.
    if manufacturer and manufacturer!='multiple' and manufacturer not in title:
        return False,'manufacturer missing from title'
    source=norm(' '.join([str(product.get('model') or ''),*(product.get('search_terms') or [])]))
    tokens=[t for t in source.split() if len(t)>=4 and any(c.isdigit() for c in t)]
    # Keep highly generic units from being accepted by themselves.
    generic_units={'1000w','128gb','96gb','64gb','32gb','24gb','16gb','4tb','2tb','1tb','1500va','40gbps'}
    distinctive=[t for t in tokens if t not in generic_units]
    if distinctive:
        needed=1 if len(distinctive)<3 else 2
        hits=sum(t in title for t in set(distinctive))
        if hits < needed: return False,'distinctive model terms missing'
        return True,'manufacturer plus distinctive model terms'

    # No reliable unique identifier: keep as a review candidate rather than guessing.
    return False,'no unique model identifier available'

def observation(product,slug,result,price,ts,status,reason):
    return {
        'component_id':product['id'],'component':product['label'],
        'model':result.get('title') or product.get('model',''),'retailer':slug,
        'price':price,'currency':'USD',
        'source_url':source_url(result,(product.get('retailer_search_urls') or {}).get(slug,'')),
        'availability':'Shown in Google Shopping','status':status,
        'method':'serpapi_google_shopping','match_status':'strong' if status=='verified' else 'review',
        'timestamp':ts,'notes':reason,
    }

def collect_product(product,key,ts):
    query=(product.get('search_terms') or [product.get('model') or product.get('label')])[0]
    payload=serpapi_search(query,key)
    strong={}; review={}; seen=set()
    for result in payload.get('shopping_results') or []:
        slug=retailer_slug(result.get('source') or result.get('seller') or result.get('merchant'))
        if not slug: continue
        seen.add(slug)
        price=extracted_price(result)
        if price is None: continue
        ok,reason=match_result(product,result)
        bucket=strong if ok else review
        candidate=observation(product,slug,result,price,ts,'verified' if ok else 'manual_review',reason)
        if slug not in bucket or price < bucket[slug]['price']: bucket[slug]=candidate

    verified=reviews=missing=0
    for slug in expected_retailers(product):
        if slug in strong:
            append(product['id'],strong[slug]); verified+=1
        elif slug in review:
            append(product['id'],review[slug]); reviews+=1
        else:
            append(product['id'],{
                'component_id':product['id'],'component':product['label'],'model':product.get('model',''),
                'retailer':slug,'source_url':(product.get('retailer_search_urls') or {}).get(slug,''),
                'availability':'Unknown','status':'not_found','method':'serpapi_google_shopping',
                'timestamp':ts,'notes':'Retailer had no acceptable Shopping result for this item.'
            }); missing+=1
    return verified,reviews,missing

def selected_products(batch_size=24):
    if not PRODUCTS:return []
    n=len(PRODUCTS); start=(date.today().toordinal()*batch_size)%n
    return [PRODUCTS[(start+i)%n] for i in range(min(batch_size,n))]

def main():
    ts=now(); key=os.getenv('SERPAPI_API_KEY','').strip()
    batch_size=max(1,min(int(os.getenv('SERPAPI_DAILY_BATCH','24')),len(PRODUCTS) or 1))
    selected=selected_products(batch_size); verified=reviews=missing=failures=0
    if not key:
        status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'verified_retailer_offers':0,'manual_review_candidates':0,'missing_retailer_results':0,'check_failures':1,'note':'SERPAPI_API_KEY is not configured in GitHub Actions Secrets.'}
        (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2)); return
    for product in selected:
        try:
            v,r,m=collect_product(product,key,ts); verified+=v; reviews+=r; missing+=m
        except Exception as exc:
            failures+=1
            for slug in expected_retailers(product):
                append(product['id'],{'component_id':product['id'],'component':product['label'],'model':product.get('model',''),'retailer':slug,'source_url':(product.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'check_failed','method':'serpapi_google_shopping','timestamp':ts,'notes':str(exc)})
    status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':len(selected),'batch_size':batch_size,'verified_retailer_offers':verified,'manual_review_candidates':reviews,'missing_retailer_results':missing,'check_failures':failures,'note':'Only strong model matches are verified. Ambiguous offers require manual review and never affect build totals.'}
    (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2))

if __name__=='__main__': main()
