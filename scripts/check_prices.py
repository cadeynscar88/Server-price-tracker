#!/usr/bin/env python3
"""Quota-safe SerpApi Google Shopping collector for the private server build.

Trusted observations require strong identity, sane price and condition/type rules.
Deferred products stay in the tracker/history but do not consume searches while
search_enabled is false. Bundle/open-box/prebuilt deal watches have dedicated rules.
"""
import json, os, re, hashlib
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; OBS=DATA/'observations'; OBS.mkdir(exist_ok=True)
PRODUCTS=json.loads((DATA/'products.json').read_text())
CONFIG=json.loads((DATA/'config.json').read_text())
QUOTA_PATH=DATA/'quota_status.json'

RETAILERS={
 'amazon':('amazon','amazon.com'),'newegg':('newegg','newegg.com'),
 'walmart':('walmart','walmart.com'),'bestbuy':('best buy','bestbuy.com'),
 'bh':('b&h','b&h photo','bhphotovideo'),'microcenter':('micro center','microcenter')
}
RETAILER_QUERY_NAMES={'amazon':'Amazon','newegg':'Newegg','walmart':'Walmart','bestbuy':'Best Buy','bh':'B&H Photo','microcenter':'Micro Center'}
CONDITION_REJECT=('refurbished','renewed','used','pre-owned','preowned','for parts','damaged','renewed premium')
ACCESSORY_REJECT=('water block','waterblock','heatsink only','fan only','empty box','backplate','replacement fan','mounting kit','bracket only','cable only')
BUNDLE_REJECT=('bundle','combo','with monitor','with display','monitor included','keyboard mouse','mouse keyboard','processor motherboard kit','motherboard kit')
SYSTEM_REJECT=('gaming pc','desktop pc','desktop computer','workstation pc','workstation computer','prebuilt','pre-built','complete system','gaming desktop','tower computer','computer tower','desktop tower')
NONRETAIL_REJECT=('bulk','oem','tray processor','tray cpu')
APPROVED_NVME=('sn850x','nm790','t500','kc3000','990 pro')
STORAGE_QUERIES={
 'nvme-4tb':['Lexar NM790 4TB NVMe','WD Black SN850X 4TB NVMe','Kingston KC3000 4TB NVMe','Crucial T500 4TB NVMe','Samsung 990 PRO 4TB NVMe'],
 'nvme-2tb':['Lexar NM790 2TB NVMe','WD Black SN850X 2TB NVMe','Kingston KC3000 2TB NVMe','Crucial T500 2TB NVMe','Samsung 990 PRO 2TB NVMe']
}
PRICE_BANDS={
 'cpu':(250,1200),'cpu-9950x3d':(300,1300),'motherboard':(200,1200),
 'ram-32gb':(40,700),'ram-64gb':(70,1100),'ram-96gb':(100,1400),'ram-96gb-ecc':(120,1800),'ram-128gb':(140,1800),'ram-128gb-ecc':(160,2200),
 'gpu-5070ti':(450,1800),'gpu-pro4000':(700,3000),'gpu-5090':(1200,6000),'gpu-pro4500':(900,6000),
 'gpu-pro5000-blackwell-48gb':(2000,9000),'gpu-a6000-48gb':(1000,8000),'gpu-pro6000-blackwell-96gb':(3000,20000),
 'nvme-4tb':(120,900),'nvme-2tb':(60,500),'boot-ssd':(20,180),'case':(70,300),
 'cooler-noctua':(60,250),'cooler-thermalright':(25,180),'psu-1000w':(80,350),'psu-1200w':(100,450),
 'ups-1000w':(100,650),'ups-1500w':(250,1600),
 'bundle-9950x-proart':(650,1600),'openbox-cpu-9950x':(250,650),'openbox-proart-x870e':(200,550),
 'openbox-gpu-5070ti':(350,1500),'prebuilt-openbox-5080':(1500,3800)
}
DETERMINISTIC_REASONS={
 'rejected condition','accessory/part result','bundle result','non-retail/bulk component result','complete-system/prebuilt result',
 'different model/variant','required exact-model terms missing','wrong/missing capacity','not approved SSD family','not internal NVMe drive','not approved SATA boot family',
 'capacity not approved','boot drive must be SATA','wrong RAM capacity/module layout','ECC result belongs in ECC branch',
 'not approved 1000W PSU','not approved 1200W PSU','open-box condition not confirmed','bundle identity not confirmed',
 'prebuilt identity not confirmed'
}
OPENBOX_IDS={'openbox-cpu-9950x','openbox-proart-x870e','openbox-gpu-5070ti','prebuilt-openbox-5080'}
BUNDLE_IDS={'bundle-9950x-proart'}
PREBUILT_IDS={'prebuilt-openbox-5080'}


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
 p=OBS/f'{pid}.json'; rows=json.loads(p.read_text()) if p.exists() else []; rows.append(row); p.write_text(json.dumps(rows,indent=2))
def serp(q,key):
 req=Request('https://serpapi.com/search.json?'+urlencode({'engine':'google_shopping','q':q,'hl':'en','gl':'us','api_key':key}),headers={'User-Agent':'PrivateServerPriceTracker/2.7'})
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
 if any(norm(x) in t for x in ACCESSORY_REJECT): return False,'accessory/part result'
 if pid in OPENBOX_IDS:
  if any(norm(x) in t for x in CONDITION_REJECT): return False,'rejected condition'
  if 'open box' not in t: return False,'open-box condition not confirmed'
 else:
  if any(norm(x) in t for x in CONDITION_REJECT) or 'open box' in t: return False,'rejected condition'
 if pid not in BUNDLE_IDS and any(norm(x) in t for x in BUNDLE_REJECT): return False,'bundle result'
 if pid in {'cpu','cpu-9950x3d','openbox-cpu-9950x','gpu-5070ti','gpu-pro4000','gpu-5090','gpu-pro4500','gpu-pro5000-blackwell-48gb','gpu-a6000-48gb','gpu-pro6000-blackwell-96gb','openbox-gpu-5070ti'} and any(norm(x) in t for x in NONRETAIL_REJECT): return False,'non-retail/bulk component result'
 component_like=(pid.startswith('gpu-') or pid.startswith('ram-') or pid in {'cpu','cpu-9950x3d','motherboard','nvme-4tb','nvme-2tb','boot-ssd','psu-1000w','psu-1200w','openbox-cpu-9950x','openbox-proart-x870e','openbox-gpu-5070ti'})
 if pid not in PREBUILT_IDS and component_like and any(norm(x) in t for x in SYSTEM_REJECT): return False,'complete-system/prebuilt result'
 return True,'product type plausible'

def match_result(p,r,pr=None):
 pid=p.get('id',''); t=norm(' '.join(str(x or '') for x in (r.get('title'),r.get('condition')))); pr=price(r) if pr is None else pr
 if not t:return False,'missing title'
 ok,reason=product_type_clean(pid,t)
 if not ok:return False,reason
 ok,reason=price_sane(pid,pr)
 if not ok:return False,reason
 exact={
  'cpu':(('9950x',),('9950x3d','9950x3d2')),
  'cpu-9950x3d':(('9950x3d',),('9950x3d2',)),
  'motherboard':(('asrock','x870e','taichi','white'),('proart','tuf','rog','x670e')),
  'gpu-5070ti':(('5070','ti','16gb'),('5070 ti super','5080','5090')),
  'gpu-pro4000':(('rtx','pro','4000','blackwell','24gb'),('ada',)),
  'gpu-5090':(('5090','32gb'),('5090d','5090 d')),
  'gpu-pro4500':(('rtx','pro','4500','blackwell','32gb'),('ada',)),
  'gpu-pro5000-blackwell-48gb':(('rtx','pro','5000','blackwell','48gb'),('ada',)),
  'gpu-a6000-48gb':(('rtx','a6000','48gb'),('ada','6000 blackwell')),
  'gpu-pro6000-blackwell-96gb':(('rtx','pro','6000','blackwell','96gb'),('ada',)),
  'case':(('lian','li','o11','dynamic','evo','rgb','white'),('lancool','black')),
  'cooler-noctua':(('nh','d15','g2'),()),'cooler-thermalright':(('phantom','spirit','120','evo'),()),
  'ups-1000w':(('cp1500pfclcd',),()),'ups-1500w':(('pr1500lcd',),('cp1500pfclcd',)),
  'openbox-cpu-9950x':(('9950x','open box'),('9950x3d','9950x3d2')),
  'openbox-proart-x870e':(('proart','x870e','open box'),('x670e','rog','tuf')),
  'openbox-gpu-5070ti':(('5070','ti','16gb','open box'),('5070 ti super','5080','5090'))
 }
 if pid in exact:
  req,forbid=exact[pid]
  if not has_all(t,req):return False,'required exact-model terms missing'
  if any(norm(x) in t for x in forbid):return False,'different model/variant'
  return True,'exact model/condition + sane price'
 if pid=='bundle-9950x-proart':
  if not has_all(t,('9950x','proart','x870e')) or '9950x3d' in t:return False,'bundle identity not confirmed'
  return True,'exact CPU + ProArt X870E bundle identity + sane price'
 if pid=='prebuilt-openbox-5080':
  if '5080' not in t or not any(norm(x) in t for x in SYSTEM_REJECT):return False,'prebuilt identity not confirmed'
  if '64gb' in t:return True,'open-box RTX 5080 prebuilt with 64GB + sane price'
  if '32gb' in t:return False,'prebuilt has 32GB RAM; evaluate upgrade cost manually'
  return False,'prebuilt RAM capacity unclear; manual specification review required'
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
  req={
   'ram-32gb':('32gb','16gb',False),'ram-64gb':('64gb','32gb',False),'ram-96gb':('96gb','48gb',False),
   'ram-96gb-ecc':('96gb','48gb',True),'ram-128gb':('128gb','64gb',False),'ram-128gb-ecc':('128gb','64gb',True)
  }.get(pid)
  if not req:return False,'unknown RAM rule'
  cap,module,ecc=req
  if cap not in t or module not in t or 'ddr5' not in t:return False,'wrong RAM capacity/module layout'
  if not any(x in t for x in ('2x','2 x','kit of 2','2 pack','2pack','dual kit')):return False,'two-DIMM kit not confirmed'
  is_ecc='ecc' in t
  if ecc and (not is_ecc or not any(x in t for x in ('udimm','unbuffered')) or 'rdimm' in t):return False,'true ECC UDIMM not confirmed'
  if not ecc and is_ecc:return False,'ECC result belongs in ECC branch'
  return True,'DDR5 two-DIMM capacity branch + sane price'
 if pid=='psu-1000w':return (True,'approved 1000W PSU + sane price') if '1000w' in t and any(x in t for x in ('rm1000x','a1000gl')) else (False,'not approved 1000W PSU')
 if pid=='psu-1200w':return (True,'approved 1200W PSU + sane price') if '1200w' in t and (('lian' in t and 'li' in t and ('rs1200g' in t or 'rs1200w' in t)) or ('vertex' in t and 'gx' in t)) else (False,'not approved 1200W PSU')
 return False,'no strong rule for this item'

def classification(reason):
 if reason.startswith('price $'): return 'rejected'
 if reason in DETERMINISTIC_REASONS:return 'rejected'
 return 'manual_review'

def revalidate_existing():
 changed=reviewed=rejected=trusted=0; pmap={p['id']:p for p in PRODUCTS}
 for path in OBS.glob('*.json'):
  p=pmap.get(path.stem)
  if not p:continue
  try:rows=json.loads(path.read_text())
  except Exception:continue
  dirty=False
  for row in rows:
   if row.get('method')!='serpapi_google_shopping' or not isinstance(row.get('price'),(int,float)):continue
   synthetic={'title':row.get('model',''),'condition':row.get('condition',''),'extracted_price':row.get('price')}
   ok,reason=match_result(p,synthetic,row.get('price')); new_status='verified' if ok else classification(reason); new_match='strong' if ok else ('rejected' if new_status=='rejected' else 'review')
   trusted+=int(ok); rejected+=int(new_status=='rejected'); reviewed+=int(new_status=='manual_review')
   if row.get('status')!=new_status or row.get('match_status')!=new_match or row.get('validation_version')!='2.7' or row.get('validation_reason')!=reason:
    row['status']=new_status; row['match_status']=new_match; row['validation_version']='2.7'; row['validation_reason']=reason; dirty=True; changed+=1
  if dirty:path.write_text(json.dumps(rows,indent=2))
 return {'changed':changed,'trusted_rows':trusted,'rejected_rows':rejected,'review_rows':reviewed}

def observation(p,slug,r,pr,ts,status,reason,query_kind='generic'):
 return {'component_id':p['id'],'component':p['label'],'model':r.get('title') or p.get('model',''),'condition':r.get('condition'),'seller':r.get('source') or r.get('seller') or r.get('merchant'),'delivery':r.get('delivery'),'retailer':slug,'price':pr,'currency':'USD','source_url':source_url(r,(p.get('retailer_search_urls') or {}).get(slug,'')),'availability':'Shown in Google Shopping','status':status,'method':'serpapi_google_shopping','match_status':'strong' if status=='verified' else ('rejected' if status=='rejected' else 'review'),'validation_version':'2.7','validation_reason':reason,'query_kind':query_kind,'timestamp':ts,'notes':reason}
def search_query(p,ts=None):
 terms=STORAGE_QUERIES.get(p.get('id')) or p.get('search_terms') or [p.get('model') or p.get('label')]
 if len(terms)==1:return terms[0]
 d=datetime.fromisoformat((ts or now()).replace('Z','+00:00')).date().toordinal(); salt=int(hashlib.sha1(p['id'].encode()).hexdigest()[:8],16); return terms[(d+salt)%len(terms)]
def retailer_query(p,slug,ts=None): return f"{search_query(p,ts)} {RETAILER_QUERY_NAMES.get(slug,slug)}"
def parse_payload(p,payload,ts,query_kind='generic',only_slug=None):
 strong={}; review={}; rejected={}
 for r in payload.get('shopping_results') or []:
  slug=retailer_slug(r.get('source') or r.get('seller') or r.get('merchant')); pr=price(r)
  if not slug or pr is None or (only_slug and slug!=only_slug):continue
  ok,reason=match_result(p,r,pr); status='verified' if ok else classification(reason); bucket=strong if ok else (rejected if status=='rejected' else review); row=observation(p,slug,r,pr,ts,status,reason,query_kind)
  if slug not in bucket or pr<bucket[slug]['price']:bucket[slug]=row
 return strong,review,rejected
def collect(p,key,ts):
 payload=serp(search_query(p,ts),key); strong,review,rejected=parse_payload(p,payload,ts); v=rv=rj=m=0; unresolved=[]
 for slug in expected(p):
  if slug in strong:append(p['id'],strong[slug]); v+=1
  elif slug in review:append(p['id'],review[slug]); rv+=1; unresolved.append(slug)
  elif slug in rejected:append(p['id'],rejected[slug]); rj+=1; unresolved.append(slug)
  else:unresolved.append(slug)
 return v,rv,rj,m,unresolved
def fallback_collect(p,slug,key,ts):
 payload=serp(retailer_query(p,slug,ts),key); strong,review,rejected=parse_payload(p,payload,ts,'retailer_fallback',slug)
 if slug in strong: append(p['id'],strong[slug]); return 'verified'
 if slug in review: append(p['id'],review[slug]); return 'manual_review'
 if slug in rejected: append(p['id'],rejected[slug]); return 'rejected'
 append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'not_found','method':'serpapi_google_shopping','query_kind':'retailer_fallback','timestamp':ts,'notes':'No matching result in retailer-specific fallback.'}); return 'not_found'
def searchable_products(): return [p for p in PRODUCTS if p.get('price_source','search')=='search' and p.get('search_enabled',True) and p.get('search_terms') and p.get('retailer_search_urls')]
def selected(batch,limit=None):
 items=searchable_products()
 if not items:return []
 n=len(items); count=min(batch,n) if limit is None else min(batch,n,max(0,int(limit))); start=(date.today().toordinal()*max(1,batch))%n; return [items[(start+i)%n] for i in range(count)]
def fallback_candidates(picks,unresolved):
 priority={'cpu':0,'cpu-9950x3d':1,'bundle-9950x-proart':2,'openbox-cpu-9950x':3,'motherboard':4,'openbox-proart-x870e':5,'case':6,'boot-ssd':7,'nvme-4tb':8,'nvme-2tb':9}
 out=[]
 for p in picks:
  for slug in unresolved.get(p['id'],[]): out.append((priority.get(p['id'],20),p['id'],slug,p))
 out.sort(key=lambda x:(x[0],x[1],x[2])); return out

def main():
 ts=now(); revalidated=revalidate_existing(); key=os.getenv('SERPAPI_API_KEY','').strip(); pre=CONFIG.get('preflight',{}); max_batch=int(pre.get('max_serpapi_searches_per_run',24)); fallback_budget=max(0,min(3,int(pre.get('retailer_fallback_searches_per_run',1)))); base_cap=max(1,max_batch-fallback_budget); requested=max(1,min(int(os.getenv('SERPAPI_DAILY_BATCH',str(max_batch))),max_batch)); quota=quota_state(ts); base_budget=min(base_cap,requested,quota['checks_remaining_to_plan']); picks=selected(base_budget,base_budget); v=rv=rj=m=fail=attempted=fallbacks=0; unresolved={}
 if not key:
  status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'searchable_products':len(searchable_products()),'check_failures':0,'existing_results_revalidated':revalidated,'quota':quota,'note':'SERPAPI_API_KEY missing; offline revalidation completed and no quota was consumed.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2)); return
 if not picks:
  status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'batch_size':requested,'searchable_products':len(searchable_products()),'check_failures':0,'existing_results_revalidated':revalidated,'quota':quota,'note':'Monthly tracker budget exhausted; no SerpApi request was made.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2)); return
 for p in picks:
  quota=bump_quota(ts); attempted+=1
  try:a,b,c,d,u=collect(p,key,ts); v+=a; rv+=b; rj+=c; m+=d; unresolved[p['id']]=u
  except Exception as e:
   fail+=1
   for slug in expected(p):append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'check_failed','method':'serpapi_google_shopping','timestamp':ts,'notes':str(e)})
 for _,_,slug,p in fallback_candidates(picks,unresolved):
  if fallbacks>=fallback_budget or attempted>=max_batch or quota_state(ts)['checks_remaining_to_plan']<=0:break
  quota=bump_quota(ts); attempted+=1; fallbacks+=1
  try:
   status=fallback_collect(p,slug,key,ts); v+=int(status=='verified'); rv+=int(status=='manual_review'); rj+=int(status=='rejected'); m+=int(status=='not_found')
  except Exception as e: fail+=1; append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'check_failed','method':'serpapi_google_shopping','query_kind':'retailer_fallback','timestamp':ts,'notes':str(e)})
 quota=quota_state(ts); status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':attempted,'base_searches':attempted-fallbacks,'retailer_fallback_searches':fallbacks,'max_searches_per_run':max_batch,'searchable_products':len(searchable_products()),'verified_retailer_offers':v,'manual_review_candidates':rv,'auto_rejected_results':rj,'missing_retailer_results':m,'check_failures':fail,'existing_results_revalidated':revalidated,'quota':quota,'note':'Focused active products are searched; deferred RAM upgrades consume no searches. Bundle/open-box/prebuilt results use dedicated identity/condition rules. One retailer fallback is reserved inside the same hard run cap.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)); print(json.dumps(status,indent=2))

if __name__=='__main__': main()
