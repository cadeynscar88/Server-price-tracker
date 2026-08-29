#!/usr/bin/env python3
"""SerpApi Google Shopping collector.

Only standalone, sane-price, strong identity matches become trusted prices.
Historical SerpApi observations can be revalidated offline without making API calls.
"""
import json, os, re, hashlib
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OBS=DATA/'observations'
PRODUCTS=json.loads((DATA/'products.json').read_text()); CONFIG=json.loads((DATA/'config.json').read_text()); OBS.mkdir(exist_ok=True)
RETAILERS={'amazon':('amazon','amazon.com'),'newegg':('newegg','newegg.com'),'walmart':('walmart','walmart.com'),'bestbuy':('best buy','bestbuy.com'),'bh':('b&h','b&h photo','bhphotovideo'),'microcenter':('micro center','microcenter')}
CONDITION_REJECT=('refurbished','renewed','used','pre-owned','preowned','open box','open-box','for parts','damaged','renewed premium')
ACCESSORY_REJECT=('water block','waterblock','heatsink only','fan only','empty box','backplate','replacement fan','mounting kit','bracket only','cable only')
BUNDLE_REJECT=('bundle','combo','with monitor','with display','monitor included','keyboard mouse','mouse keyboard')
SYSTEM_REJECT=('gaming pc','desktop pc','desktop computer','workstation pc','workstation computer','prebuilt','pre-built','complete system','gaming desktop','tower computer','computer tower','desktop tower')
NONRETAIL_REJECT=('bulk','oem','tray processor','tray cpu')
APPROVED_NVME=('sn850x','nm790','t500','kc3000','990 pro')
STORAGE_QUERIES={
 'nvme-4tb':['Lexar NM790 4TB NVMe','WD Black SN850X 4TB NVMe','Kingston KC3000 4TB NVMe','Crucial T500 4TB NVMe','Samsung 990 PRO 4TB NVMe'],
 'nvme-2tb':['Lexar NM790 2TB NVMe','WD Black SN850X 2TB NVMe','Kingston KC3000 2TB NVMe','Crucial T500 2TB NVMe','Samsung 990 PRO 2TB NVMe']
}
QUOTA_PATH=DATA/'quota_status.json'
PRICE_BANDS={
 'cpu':(250,1200),'motherboard':(200,1200),
 'ram-64gb':(70,850),'ram-96gb':(100,1400),'ram-96gb-ecc':(120,1800),'ram-128gb':(140,1800),'ram-128gb-ecc':(160,2200),
 'gpu-5070ti':(450,1800),'gpu-pro4000':(700,3000),'gpu-5090':(1200,3000),'gpu-pro4500':(900,3000),
 'nvme-4tb':(120,900),'nvme-2tb':(60,500),'boot-ssd':(20,180),
 'case':(70,300),'cooler-noctua':(60,250),'cooler-thermalright':(25,180),
 'psu-1000w':(80,350),'psu-1200w':(100,450),'ups-1000w':(100,650),'ups-1500w':(250,1600)
}

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
 req=Request('https://serpapi.com/search.json?'+urlencode({'engine':'google_shopping','q':q,'hl':'en','gl':'us','api_key':key}),headers={'User-Agent':'PrivateServerPriceTracker/2.3'})
 with urlopen(req,timeout=30) as r: payload=json.loads(r.read())
 if payload.get('error'): raise RuntimeError(payload['error'])
 return payload
def price(r):
 v=r.get('extracted_price')
 if isinstance(v,(int,float)): return float(v)
 m=re.search(r'([0-9][0-9,]*(?:\.[0-9]{1,2})?)',str(r.get('price') or '')); return float(m.group(1).replace(',','')) if m else None
def expected(p): return list((p.get('retailer_search_urls') or {}).keys())
def source_url(r,f=''): return r.get('product_link') or r.get('link') or f

def quota_limits():
 p=CONFIG.get('preflight',{}); absolute=max(1,int(p.get('serpapi_monthly_limit',250))); reserve=max(0,int(p.get('serpapi_reserve',10)))
 planned=int(p.get('serpapi_monthly_budget',absolute-reserve)); planned=max(0,min(planned,absolute-reserve if reserve<=absolute else 0)); return absolute,reserve,planned
def quota_state(ts=None):
 dt=datetime.fromisoformat((ts or now()).replace('Z','+00:00')); month=dt.astimezone(timezone.utc).strftime('%Y-%m'); absolute,reserve,planned=quota_limits(); previous={}
 if QUOTA_PATH.exists():
  try: previous=json.loads(QUOTA_PATH.read_text())
  except Exception: previous={}
 used=int(previous.get('checks_used',0)) if previous.get('month')==month else 0; used=max(0,used)
 return {'provider':'serpapi','month':month,'monthly_limit':absolute,'reserve':reserve,'planned_budget':planned,'checks_used':used,'checks_remaining_to_plan':max(0,planned-used),'checks_remaining_absolute':max(0,absolute-used),'last_updated':previous.get('last_updated') if previous.get('month')==month else None,'source':'tracker_ledger','note':'Tracks SerpApi search attempts made by this repository; provider-dashboard usage outside this repo is not included.'}
def write_quota(q,ts=None):
 q=dict(q); q['last_updated']=ts or now(); q['checks_remaining_to_plan']=max(0,q['planned_budget']-q['checks_used']); q['checks_remaining_absolute']=max(0,q['monthly_limit']-q['checks_used']); QUOTA_PATH.write_text(json.dumps(q,indent=2)); return q
def bump_quota(ts=None): q=quota_state(ts); q['checks_used']+=1; return write_quota(q,ts)

def price_sane(pid,pr):
 if pr is None:return False,'missing price'
 band=PRICE_BANDS.get(pid)
 if not band:return True,'price band not required'
 lo,hi=band
 if pr<lo or pr>hi:return False,f'price ${pr:.2f} outside sanity band ${lo}-${hi}'
 return True,'price within sanity band'
def product_type_clean(pid,t):
 if any(norm(x) in t for x in CONDITION_REJECT):return False,'rejected condition'
 if any(norm(x) in t for x in ACCESSORY_REJECT):return False,'accessory/part result'
 if any(norm(x) in t for x in BUNDLE_REJECT):return False,'bundle result'
 if pid in {'cpu','gpu-5070ti','gpu-pro4000','gpu-5090','gpu-pro4500'} and any(norm(x) in t for x in NONRETAIL_REJECT):return False,'non-retail/bulk component result'
 if pid.startswith('gpu-') or pid.startswith('ram-') or pid in {'cpu','motherboard','nvme-4tb','nvme-2tb','boot-ssd','psu-1000w','psu-1200w'}:
  if any(norm(x) in t for x in SYSTEM_REJECT):return False,'complete-system/prebuilt result'
 return True,'standalone product type plausible'

def match_result(p,r,pr=None):
 t=norm(r.get('title')); pid=p.get('id',''); pr=price(r) if pr is None else pr
 if not t:return False,'missing title'
 ok,reason=product_type_clean(pid,t)
 if not ok:return False,reason
 ok,reason=price_sane(pid,pr)
 if not ok:return False,reason
 exact={
  'cpu':(('9950x',),('9950x3d',)),
  'motherboard':(('proart','x870e'),('x670e',)),
  'gpu-5070ti':(('5070','ti','16gb'),('5070 ti super','5080','5090')),
  'gpu-pro4000':(('rtx','pro','4000','blackwell','24gb'),('ada',)),
  'gpu-5090':(('5090','32gb'),('5090d','5090 d')),
  'gpu-pro4500':(('rtx','pro','4500','blackwell','32gb'),('ada',)),
  'case':(('lancool','217'),('walnut','wood','white','inf')),
  'cooler-noctua':(('nh','d15','g2'),()),
  'cooler-thermalright':(('phantom','spirit','120','evo'),()),
  'ups-1000w':(('cp1500pfclcd',),()),
  'ups-1500w':(('pr1500lcd',),('cp1500pfclcd',)),
 }
 if pid in exact:
  req,forbid=exact[pid]
  if not has_all(t,req):return False,'required exact-model terms missing'
  if any(norm(x) in t for x in forbid):return False,'different model/variant'
  return True,'exact standalone model + sane price'
 if pid in {'nvme-4tb','nvme-2tb'}:
  cap='4tb' if pid=='nvme-4tb' else '2tb'
  if cap not in t:return False,'wrong/missing capacity'
  if not any(norm(m) in t for m in APPROVED_NVME):return False,'not approved SSD family'
  if any(x in t for x in ('external ssd','portable ssd','enclosure')):return False,'not internal NVMe drive'
  return True,'approved internal TLC SSD family/capacity + sane price'
 if pid=='boot-ssd':
  if not any(x in t for x in ('870 evo','mx500','kc600')):return False,'not approved SATA boot family'
  if not any(x in t for x in ('500gb','512gb','1tb','250gb')):return False,'capacity not approved'
  if 'nvme' in t or 'm 2' in t or 'm2' in t:return False,'boot drive must be SATA'
  return True,'approved SATA boot SSD + sane price'
 if pid.startswith('ram-'):
  req={'ram-96gb':('96gb','48gb',False),'ram-96gb-ecc':('96gb','48gb',True),'ram-128gb':('128gb','64gb',False),'ram-128gb-ecc':('128gb','64gb',True),'ram-64gb':('64gb','32gb',False)}.get(pid)
  if not req:return False,'unknown RAM rule'
  cap,module,ecc=req
  if cap not in t or module not in t or 'ddr5' not in t:return False,'wrong RAM capacity/module layout'
  if not any(x in t for x in ('2x','2 x','kit of 2','2 pack','2pack','dual kit')):return False,'two-DIMM kit not confirmed'
  is_ecc='ecc' in t
  if ecc and (not is_ecc or not any(x in t for x in ('udimm','unbuffered')) or 'rdimm' in t):return False,'true ECC UDIMM not confirmed'
  if not ecc and is_ecc:return False,'ECC result belongs in ECC branch'
  return True,'DDR5 two-DIMM capacity branch + sane price'
 if pid=='psu-1000w':return (True,'approved 1000W PSU + sane price') if '1000w' in t and any(x in t for x in ('rm1000x','a1000gl')) else (False,'not approved 1000W PSU')
 if pid=='psu-1200w':return (True,'approved 1200W PSU + sane price') if '1200w' in t and 'vertex' in t and 'gx' in t else (False,'not approved 1200W PSU')
 return False,'no strong rule for this item'

def revalidate_existing():
 changed=0; reviewed=0; trusted=0; pmap={p['id']:p for p in PRODUCTS}
 for path in OBS.glob('*.json'):
  p=pmap.get(path.stem)
  if not p:continue
  try:rows=json.loads(path.read_text())
  except Exception:continue
  dirty=False
  for row in rows:
   if row.get('method')!='serpapi_google_shopping' or not isinstance(row.get('price'),(int,float)):continue
   ok,reason=match_result(p,{'title':row.get('model',''),'extracted_price':row.get('price')},row.get('price')); new_status='verified' if ok else 'manual_review'; new_match='strong' if ok else 'review'; trusted+=int(ok); reviewed+=int(not ok)
   if row.get('status')!=new_status or row.get('match_status')!=new_match or row.get('validation_version')!='2.3' or row.get('validation_reason')!=reason:
    row['status']=new_status; row['match_status']=new_match; row['validation_version']='2.3'; row['validation_reason']=reason; dirty=True; changed+=1
  if dirty:path.write_text(json.dumps(rows,indent=2))
 return {'changed':changed,'trusted_rows':trusted,'review_rows':reviewed}

def observation(p,slug,r,pr,ts,status,reason):
 return {'component_id':p['id'],'component':p['label'],'model':r.get('title') or p.get('model',''),'retailer':slug,'price':pr,'currency':'USD','source_url':source_url(r,(p.get('retailer_search_urls') or {}).get(slug,'')),'availability':'Shown in Google Shopping','status':status,'method':'serpapi_google_shopping','match_status':'strong' if status=='verified' else 'review','validation_version':'2.3','validation_reason':reason,'timestamp':ts,'notes':reason}
def search_query(p,ts=None):
 terms=STORAGE_QUERIES.get(p.get('id')) or p.get('search_terms') or [p.get('model') or p.get('label')]
 if len(terms)==1:return terms[0]
 d=datetime.fromisoformat((ts or now()).replace('Z','+00:00')).date().toordinal(); salt=int(hashlib.sha1(p['id'].encode()).hexdigest()[:8],16); return terms[(d+salt)%len(terms)]
def collect(p,key,ts):
 q=search_query(p,ts); payload=serp(q,key); strong={}; review={}
 for r in payload.get('shopping_results') or []:
  slug=retailer_slug(r.get('source') or r.get('seller') or r.get('merchant')); pr=price(r)
  if not slug or pr is None:continue
  ok,reason=match_result(p,r,pr); bucket=strong if ok else review; row=observation(p,slug,r,pr,ts,'verified' if ok else 'manual_review',reason)
  if slug not in bucket or pr<bucket[slug]['price']:bucket[slug]=row
 v=rv=m=0
 for slug in expected(p):
  if slug in strong:append(p['id'],strong[slug]); v+=1
  elif slug in review:append(p['id'],review[slug]); rv+=1
  else:append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'not_found','method':'serpapi_google_shopping','timestamp':ts,'notes':'No acceptable Shopping result.'}); m+=1
 return v,rv,m
def searchable_products():return [p for p in PRODUCTS if p.get('price_source','search')=='search' and p.get('search_terms') and p.get('retailer_search_urls')]
def selected(batch,limit=None):
 items=searchable_products()
 if not items:return []
 n=len(items); count=min(batch,n) if limit is None else min(batch,n,max(0,int(limit))); start=(date.today().toordinal()*batch)%n; return [items[(start+i)%n] for i in range(count)]
def main():
 ts=now(); revalidated=revalidate_existing(); key=os.getenv('SERPAPI_API_KEY','').strip(); max_batch=int(CONFIG.get('preflight',{}).get('max_serpapi_searches_per_run',24)); batch=max(1,min(int(os.getenv('SERPAPI_DAILY_BATCH',str(max_batch))),max_batch)); quota=quota_state(ts); picks=selected(batch,quota['checks_remaining_to_plan']); v=rv=m=fail=attempted=0
 if not key:
  status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'check_failures':0,'existing_results_revalidated':revalidated,'quota':quota,'note':'SERPAPI_API_KEY missing; offline revalidation completed and no quota was consumed.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2)); return
 if not picks:
  status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'batch_size':batch,'searchable_products':len(searchable_products()),'check_failures':0,'existing_results_revalidated':revalidated,'quota':quota,'note':'Monthly tracker budget exhausted; no SerpApi request was made.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2)); return
 for p in picks:
  quota=bump_quota(ts); attempted+=1
  try:a,b,c=collect(p,key,ts); v+=a; rv+=b; m+=c
  except Exception as e:
   fail+=1
   for slug in expected(p):append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'check_failed','method':'serpapi_google_shopping','timestamp':ts,'notes':str(e)})
 status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':attempted,'batch_size':batch,'searchable_products':len(searchable_products()),'verified_retailer_offers':v,'manual_review_candidates':rv,'missing_retailer_results':m,'check_failures':fail,'existing_results_revalidated':revalidated,'quota':quota,'note':'Only standalone strong identity matches inside sanity bands affect trusted prices. Quota increments once per SerpApi search attempt.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2))
if __name__=='__main__':main()
