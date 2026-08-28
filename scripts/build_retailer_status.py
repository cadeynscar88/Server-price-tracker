#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OBS=DATA/'observations'
PRODUCTS=json.loads((DATA/'products.json').read_text()); NOW=datetime.now(timezone.utc); STALE_AFTER=timedelta(days=7)
RETAILER_NAMES={'amazon':'Amazon','newegg':'Newegg','walmart':'Walmart','bestbuy':'Best Buy','bh':'B&H Photo','microcenter':'Micro Center'}

def parse_ts(value):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except Exception:return None

def trusted(r):
    if r.get('status')!='verified' or not isinstance(r.get('price'),(int,float)):return False
    if r.get('method')=='serpapi_google_shopping':return r.get('match_status')=='strong'
    return True

def all_observations():
    rows=[]
    for product in PRODUCTS:
        path=OBS/f"{product['id']}.json"
        if not path.exists():continue
        try:arr=json.loads(path.read_text())
        except Exception:continue
        for row in arr:
            if isinstance(row,dict):
                row=dict(row); row['_product_id']=product['id']; rows.append(row)
    return rows

rows=all_observations(); retailers=[]
for slug,name in RETAILER_NAMES.items():
    rrows=[r for r in rows if r.get('retailer')==slug]
    verified=[r for r in rrows if trusted(r) and parse_ts(r.get('timestamp'))]
    latest_verified=max(verified,key=lambda r:parse_ts(r.get('timestamp'))) if verified else None
    latest_any=max(rrows,key=lambda r:parse_ts(r.get('timestamp')) or datetime.min.replace(tzinfo=timezone.utc)) if rrows else None
    age_days=max(0,(NOW-parse_ts(latest_verified['timestamp'])).total_seconds()/86400) if latest_verified else None
    latest_status=(latest_any or {}).get('status')
    if latest_status=='manual_review':
        state='yellow'; label='latest result needs model review'
    elif latest_verified is None:
        state='red' if latest_status in {'not_found','check_failed'} else 'gray'; label='no trusted verified price'
    elif age_days is not None and age_days>7:
        state='yellow'; label=f'price is {int(age_days)} days old'
    elif latest_status in {'not_found','check_failed'}:
        state='red'; label='missing from latest search'
    else:
        state='green'; label='fresh trusted price'
    retailers.append({'id':slug,'name':name,'state':state,'status':label,'last_verified_at':latest_verified.get('timestamp') if latest_verified else None,'last_verified_price':latest_verified.get('price') if latest_verified else None,'latest_check_status':latest_status})

summary={'generated_at':NOW.isoformat(),'retailers':retailers,'freshness_policy':{'green':'trusted verified price is 7 days old or newer','yellow':'trusted price is stale or latest result needs manual model review','red':'retailer missing from latest search/check failed with no acceptable current result','gray':'not checked/configured yet'},'note':'Ambiguous SerpApi offers never count toward totals. Missing/review results never erase a previously trusted price.'}
(DATA/'retailer_status.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))
