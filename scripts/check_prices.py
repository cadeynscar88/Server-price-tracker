#!/usr/bin/env python3
"""Verified price collector for GitHub Actions.
Secrets are supplied through environment variables, never committed or sent to the PWA.
"""
import json, os, re, statistics
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; OBS=DATA/'observations'
PRODUCTS=json.loads((DATA/'products.json').read_text())
OBS.mkdir(exist_ok=True)
UA='PrivateServerPriceTracker/1.0 (+GitHub Actions)'

def now(): return datetime.now(timezone.utc).isoformat()
def fetch(url, headers=None, timeout=25):
    h={'User-Agent':UA,'Accept':'text/html,application/xhtml+xml,application/json'}; h.update(headers or {})
    req=Request(url,headers=h)
    with urlopen(req,timeout=timeout) as r: return r.status,r.headers.get('content-type',''),r.read()

def jsonld(html):
    text=html.decode('utf-8','ignore')
    blocks=re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',text,re.I|re.S)
    for block in blocks:
        try: data=json.loads(block.strip())
        except Exception: continue
        items=data if isinstance(data,list) else data.get('@graph',[data]) if isinstance(data,dict) else []
        for item in items:
            if not isinstance(item,dict) or 'Product' not in str(item.get('@type','')): continue
            offers=item.get('offers')
            if isinstance(offers,list): offers=offers[0] if offers else None
            if not isinstance(offers,dict): continue
            raw=offers.get('price',offers.get('lowPrice'))
            try: price=float(raw)
            except Exception: continue
            avail=str(offers.get('availability','')).split('/')[-1] or 'Unknown'
            status='unavailable' if avail.lower() in {'outofstock','discontinued'} else 'verified'
            return price,offers.get('priceCurrency','USD'),avail,item.get('name',''),status
    return None

def append(pid,o):
    path=OBS/f'{pid}.json'; arr=json.loads(path.read_text()) if path.exists() else []
    arr.append(o); path.write_text(json.dumps(arr,indent=2))

def bestbuy(p):
    key=os.getenv('BESTBUY_API_KEY','').strip()
    if not key or not p.get('bestbuy_sku'): return None
    url=f"https://api.bestbuy.com/v1/products(sku={p['bestbuy_sku']})?apiKey={key}&format=json&show=sku,name,salePrice,regularPrice,onlineAvailability,url"
    try:
        _,_,raw=fetch(url,{'Accept':'application/json'}); j=json.loads(raw); prod=(j.get('products') or [None])[0]
        if not prod: return dict(component_id=p['id'],component=p['label'],retailer='bestbuy',status='not_found',method='bestbuy',notes='SKU not found')
        price=prod.get('salePrice') if prod.get('salePrice') is not None else prod.get('regularPrice')
        avail='In Stock' if prod.get('onlineAvailability') else 'Out of Stock'
        return dict(component_id=p['id'],component=p['label'],model=prod.get('name') or p.get('model',''),retailer='bestbuy',price=price,currency='USD',source_url=prod.get('url',''),availability=avail,status='verified' if price is not None and prod.get('onlineAvailability') else 'unavailable',method='bestbuy')
    except Exception as e: return dict(component_id=p['id'],component=p['label'],retailer='bestbuy',status='check_failed',method='bestbuy',notes=str(e))

def watch(p,w):
    url=w.get('url',''); host=urlparse(url).hostname or ''
    allowed=set(x.strip() for x in os.getenv('ALLOWED_WATCH_HOSTS','').split(',') if x.strip())
    if allowed and host not in allowed: return dict(component_id=p['id'],component=p['label'],retailer=w.get('retailer',''),source_url=url,status='check_failed',method='watch',notes='Host not allowlisted')
    try:
        _,_,raw=fetch(url); found=jsonld(raw)
        if not found: return dict(component_id=p['id'],component=p['label'],retailer=w.get('retailer',''),source_url=url,status='check_failed',method='watch',notes='No structured JSON-LD offer found')
        price,currency,avail,name,status=found
        return dict(component_id=p['id'],component=p['label'],model=name or p.get('model',''),retailer=w.get('retailer',''),price=price,currency=currency,source_url=url,availability=avail,status=status,method='watch')
    except Exception as e: return dict(component_id=p['id'],component=p['label'],retailer=w.get('retailer',''),source_url=url,status='check_failed',method='watch',notes=str(e))

def main():
    ts=now(); count=0; failures=0
    for p in PRODUCTS:
        jobs=[]
        if p.get('bestbuy_sku'): jobs.append(bestbuy(p))
        for w in p.get('watch_urls',[]): jobs.append(watch(p,w))
        for o in jobs:
            o['timestamp']=ts; o.setdefault('model',p.get('model','')); o.setdefault('currency','USD'); o.setdefault('availability','Unknown'); o.setdefault('notes','')
            append(p['id'],o); count+=1; failures += o.get('status')=='check_failed'
    status={'checked_at':ts,'observations_added':count,'check_failures':failures}
    (DATA/'collector_status.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status,indent=2))
if __name__=='__main__': main()
