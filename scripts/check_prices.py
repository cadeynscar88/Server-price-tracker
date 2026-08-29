#!/usr/bin/env python3
"""SerpApi Google Shopping collector. Only strong matches become trusted prices."""
import json, os, re
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OBS=DATA/'observations'
PRODUCTS=json.loads((DATA/'products.json').read_text()); OBS.mkdir(exist_ok=True)
RETAILERS={'amazon':('amazon','amazon.com'),'newegg':('newegg','newegg.com'),'walmart':('walmart','walmart.com'),'bestbuy':('best buy','bestbuy.com'),'bh':('b&h','b&h photo','bhphotovideo'),'microcenter':('micro center','microcenter')}
REJECT=('refurbished','renewed','used','pre-owned','preowned','open box','open-box','water block','waterblock','heatsink only','fan only','empty box','laptop','desktop pc')
APPROVED_NVME=('sn850x','nm790','t500','kc3000','990 pro')

def now(): return datetime.now(timezone.utc).isoformat()
def norm(v):
 s=str(v or '').lower().replace('&',' and '); s=re.sub(r'[^a-z0-9]+',' ',s); return re.sub(r'\s+',' ',s).strip()
def has_all(t,terms): return all(norm(x) in t for x in terms)
def retailer_slug(v):
 s=norm(v)
 for slug,needles in RETAILERS.items():
  if any(norm(n) in s for n in needles): return slug
 return None
def append(pid,row):
 p=OBS/f'{pid}.json'; a=json.loads(p.read_text()) if p.exists() else []; a.append(row); p.write_text(json.dumps(a,indent=2))
def serp(q,key):
 req=Request('https://serpapi.com/search.json?'+urlencode({'engine':'google_shopping','q':q,'hl':'en','gl':'us','api_key':key}),headers={'User-Agent':'PrivateServerPriceTracker/2.0'})
 with urlopen(req,timeout=30) as r: payload=json.loads(r.read())
 if payload.get('error'): raise RuntimeError(payload['error'])
 return payload
def price(r):
 v=r.get('extracted_price')
 if isinstance(v,(int,float)): return float(v)
 m=re.search(r'([0-9][0-9,]*(?:\.[0-9]{1,2})?)',str(r.get('price') or '')); return float(m.group(1).replace(',','')) if m else None
def expected(p): return list((p.get('retailer_search_urls') or {}).keys())
def source_url(r,f=''): return r.get('product_link') or r.get('link') or f

def match_result(p,r):
 t=norm(r.get('title')); pid=p.get('id','')
 if not t: return False,'missing title'
 if any(norm(x) in t for x in REJECT): return False,'rejected condition/accessory/system result'
 exact={
  'cpu':(('9950x',),('9950x3d',)),
  'motherboard':(('proart','x870e'),()),
  'gpu-5070ti':(('5070','ti'),()),
  'gpu-pro4000':(('rtx','pro','4000','blackwell','24gb'),()),
  'gpu-5090':(('5090','32gb'),()),
  'gpu-pro4500':(('rtx','pro','4500','blackwell','32gb'),()),
  'case':(('lancool','217'),()),
  'cooler-noctua':(('nh','d15','g2'),()),
  'cooler-thermalright':(('phantom','spirit','120','evo'),()),
  'ups':(('cp1500pfclcd',),()),
 }
 if pid in exact:
  req,forbid=exact[pid]
  if not has_all(t,req): return False,'required exact-model terms missing'
  if any(norm(x) in t for x in forbid): return False,'different model variant'
  return True,'exact model match'
 if pid in {'nvme-4tb','nvme-2tb','backup-ssd'}:
  cap='4tb' if pid=='nvme-4tb' else '2tb'
  if cap not in t: return False,'wrong/missing capacity'
  if not any(norm(m) in t for m in APPROVED_NVME): return False,'not approved SSD family'
  return True,'approved TLC SSD family/capacity'
 if pid=='boot-ssd':
  if not any(x in t for x in ('870 evo','mx500','kc600')): return False,'not approved SATA boot family'
  if not any(x in t for x in ('500gb','512gb','1tb','250gb')): return False,'capacity not approved'
  return True,'approved SATA boot SSD'
 if pid.startswith('ram-'):
  cap={'ram-96gb':'96gb','ram-128gb':'128gb','ram-64gb':'64gb'}[pid]
  if cap not in t: return False,'wrong RAM capacity'
  if 'ddr5' not in t: return False,'DDR5 missing'
  return True,'capacity + DDR5 match; exact QVL/ECC status still sanity-checked before buy'
 if pid=='psu-1000w':
  if '1000w' in t and any(x in t for x in ('rm1000x','a1000gl')): return True,'approved 1000W PSU family'
  return False,'not approved 1000W PSU'
 if pid=='psu-1200w':
  if '1200w' in t and 'vertex' in t and ('gx' in t or 'gx 1200' in t): return True,'approved 1200W PSU reference'
  return False,'not approved 1200W PSU'
 return False,'no strong rule for this item'

def cleanup_legacy():
 changed=0
 for p in PRODUCTS:
  path=OBS/f"{p['id']}.json"
  if not path.exists(): continue
  try: rows=json.loads(path.read_text())
  except Exception: continue
  dirty=False
  for row in rows:
   if row.get('method')=='serpapi_google_shopping' and row.get('status')=='verified' and not row.get('match_status'):
    ok,reason=match_result(p,{'title':row.get('model','')}); row['match_status']='strong' if ok else 'review'; row['notes']=(row.get('notes','')+' Legacy revalidation: '+reason).strip()
    if not ok: row['status']='manual_review'
    dirty=True; changed+=1
  if dirty: path.write_text(json.dumps(rows,indent=2))
 return changed

def observation(p,slug,r,pr,ts,status,reason):
 return {'component_id':p['id'],'component':p['label'],'model':r.get('title') or p.get('model',''),'retailer':slug,'price':pr,'currency':'USD','source_url':source_url(r,(p.get('retailer_search_urls') or {}).get(slug,'')),'availability':'Shown in Google Shopping','status':status,'method':'serpapi_google_shopping','match_status':'strong' if status=='verified' else 'review','timestamp':ts,'notes':reason}
def collect(p,key,ts):
 q=(p.get('search_terms') or [p.get('model') or p.get('label')])[0]; payload=serp(q,key); strong={}; review={}
 for r in payload.get('shopping_results') or []:
  slug=retailer_slug(r.get('source') or r.get('seller') or r.get('merchant')); pr=price(r)
  if not slug or pr is None: continue
  ok,reason=match_result(p,r); bucket=strong if ok else review; row=observation(p,slug,r,pr,ts,'verified' if ok else 'manual_review',reason)
  if slug not in bucket or pr<bucket[slug]['price']: bucket[slug]=row
 v=rv=m=0
 for slug in expected(p):
  if slug in strong: append(p['id'],strong[slug]); v+=1
  elif slug in review: append(p['id'],review[slug]); rv+=1
  else: append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'not_found','method':'serpapi_google_shopping','timestamp':ts,'notes':'No acceptable Shopping result.'}); m+=1
 return v,rv,m
def selected(batch=24):
 if not PRODUCTS:return []
 n=len(PRODUCTS); start=(date.today().toordinal()*batch)%n; return [PRODUCTS[(start+i)%n] for i in range(min(batch,n))]
def main():
 ts=now(); legacy=cleanup_legacy(); key=os.getenv('SERPAPI_API_KEY','').strip(); batch=max(1,min(int(os.getenv('SERPAPI_DAILY_BATCH','24')),len(PRODUCTS) or 1)); picks=selected(batch); v=rv=m=fail=0
 if not key:
  status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'check_failures':1,'legacy_results_revalidated':legacy,'note':'SERPAPI_API_KEY missing.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2)); return
 for p in picks:
  try:
   a,b,c=collect(p,key,ts); v+=a; rv+=b; m+=c
  except Exception as e:
   fail+=1
   for slug in expected(p): append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'check_failed','method':'serpapi_google_shopping','timestamp':ts,'notes':str(e)})
 status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':len(picks),'batch_size':batch,'verified_retailer_offers':v,'manual_review_candidates':rv,'missing_retailer_results':m,'check_failures':fail,'legacy_results_revalidated':legacy,'note':'Only strong model matches affect trusted prices.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2))
if __name__=='__main__': main()
