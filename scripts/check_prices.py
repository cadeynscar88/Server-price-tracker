#!/usr/bin/env python3
"""Quota-safe Google Shopping collector for the current Frieren PC tracker."""
import hashlib, json, os, re
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OBS=DATA/'observations'; OBS.mkdir(exist_ok=True)
PRODUCTS=json.loads((DATA/'products.json').read_text()); CONFIG=json.loads((DATA/'config.json').read_text()); QUOTA_PATH=DATA/'quota_status.json'; VALIDATION_VERSION='2.9'
RETAILERS={'amazon':('amazon','amazon.com'),'newegg':('newegg','newegg.com'),'walmart':('walmart','walmart.com'),'bestbuy':('best buy','bestbuy.com'),'bh':('b&h','b and h','bhphotovideo'),'microcenter':('micro center','microcenter'),'ebay':('ebay','ebay.com')}
RETAILER_QUERY_NAMES={'amazon':'Amazon','newegg':'Newegg','walmart':'Walmart','bestbuy':'Best Buy','bh':'B&H Photo','microcenter':'Micro Center','ebay':'eBay'}
CONDITION_REJECT=('refurbished','renewed','for parts','damaged'); ACCESSORY_REJECT=('water block','waterblock only','heatsink only','fan only','empty box','backplate only','replacement fan','mounting kit','bracket only','cable only'); SYSTEM_REJECT=('gaming pc','desktop pc','desktop computer','workstation pc','workstation computer','prebuilt','pre-built','complete system','gaming desktop','tower computer','computer tower','desktop tower'); BUNDLE_REJECT=('bundle with','combo with','with monitor','with display','monitor included','keyboard mouse','mouse keyboard')
PRICE_BANDS={'cpu-9950x3d':(350,1100),'ram-royal-neo-64':(200,1300),'ram-royal-neo-32':(150,900),'ram-64gb-alt':(100,800),'cooler-hydroshift-ii':(150,450),'cooler-tryx-panorama-se':(140,400),'psu-lianli-rs1200':(90,350),'fans-lianli-tl120-reverse':(20,250),'fans-value-reverse':(10,180),'nvme-nm790-4tb':(180,850),'optical-uhd':(40,350),'gpu-3090':(400,2200),'gpu-5090':(1200,6500),'gpu-pro5000-blackwell-48gb':(2000,9000),'gpu-a6000-48gb':(1000,8000)}
DETERMINISTIC_REASONS={'rejected condition','accessory/part result','bundle result','complete-system/prebuilt result','different model/variant','required exact-model terms missing','wrong RAM capacity/module layout','two-DIMM kit not confirmed','wrong/missing capacity','not internal NVMe drive','reverse-blade identity not confirmed','UHD Blu-ray identity not confirmed','water-cooled 3090 not suitable for automatic air-cooled watch'}
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
 p=OBS/f'{pid}.json'; rows=[]
 if p.exists():
  try: rows=json.loads(p.read_text())
  except Exception: rows=[]
 rows.append(row); p.write_text(json.dumps(rows,indent=2)+'\n')
def serp(q,key):
 req=Request('https://serpapi.com/search.json?'+urlencode({'engine':'google_shopping','q':q,'hl':'en','gl':'us','api_key':key}),headers={'User-Agent':'FrierenPriceTracker/2.9'})
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
 p=CONFIG.get('preflight',{}); absolute=max(1,int(p.get('serpapi_monthly_limit',250))); reserve=max(0,int(p.get('serpapi_reserve',10))); planned=int(p.get('serpapi_monthly_budget',absolute-reserve)); planned=max(0,min(planned,absolute-reserve if reserve<=absolute else 0)); return absolute,reserve,planned
def quota_state(ts=None):
 dt=datetime.fromisoformat((ts or now()).replace('Z','+00:00')); month=dt.astimezone(timezone.utc).strftime('%Y-%m'); absolute,reserve,planned=quota_limits(); previous={}
 if QUOTA_PATH.exists():
  try: previous=json.loads(QUOTA_PATH.read_text())
  except Exception: previous={}
 used=int(previous.get('checks_used',0)) if previous.get('month')==month else 0; used=max(0,used)
 return {'provider':'serpapi','month':month,'monthly_limit':absolute,'reserve':reserve,'planned_budget':planned,'checks_used':used,'checks_remaining_to_plan':max(0,planned-used),'checks_remaining_absolute':max(0,absolute-used),'last_updated':previous.get('last_updated') if previous.get('month')==month else None,'source':'tracker_ledger','note':'Tracks SerpApi attempts made by this repository; provider-dashboard usage outside this repo is not included.'}
def write_quota(q,ts=None):
 q=dict(q); q['last_updated']=ts or now(); q['checks_remaining_to_plan']=max(0,q['planned_budget']-q['checks_used']); q['checks_remaining_absolute']=max(0,q['monthly_limit']-q['checks_used']); QUOTA_PATH.write_text(json.dumps(q,indent=2)+'\n'); return q
def bump_quota(ts=None): q=quota_state(ts); q['checks_used']+=1; return write_quota(q,ts)
def price_sane(pid,pr):
 if pr is None:return False,'missing price'
 band=PRICE_BANDS.get(pid)
 if not band:return True,'price band not required'
 lo,hi=band
 return (False,f'price ${pr:.2f} outside sanity band ${lo}-${hi}') if pr<lo or pr>hi else (True,'price within sanity band')
def product_type_clean(pid,t):
 if any(norm(x) in t for x in ACCESSORY_REJECT): return False,'accessory/part result'
 if any(norm(x) in t for x in BUNDLE_REJECT): return False,'bundle result'
 if any(norm(x) in t for x in SYSTEM_REJECT): return False,'complete-system/prebuilt result'
 if pid not in {'gpu-3090','gpu-a6000-48gb'} and (any(norm(x) in t for x in CONDITION_REJECT) or 'used' in t or 'pre owned' in t or 'open box' in t): return False,'rejected condition'
 if pid in {'gpu-3090','gpu-a6000-48gb'} and any(norm(x) in t for x in ('for parts','damaged')): return False,'rejected condition'
 return True,'product type plausible'
def two_dimm(t): return any(x in t for x in ('2x16','2 x 16','2x32','2 x 32','kit of 2','2 pack','2pack','dual kit'))
def match_result(p,r,pr=None):
 pid=p.get('id',''); t=norm(' '.join(str(x or '') for x in (r.get('title'),r.get('condition')))); pr=price(r) if pr is None else pr
 if not t:return False,'missing title'
 ok,reason=product_type_clean(pid,t)
 if not ok:return False,reason
 ok,reason=price_sane(pid,pr)
 if not ok:return False,reason
 if pid=='cpu-9950x3d': return (True,'exact 9950X3D + sane price') if '9950x3d' in t and '9950x3d2' not in t else (False,'different model/variant')
 if pid=='ram-royal-neo-32':
  if not (('f5 6000j2836g16gx2 tr5ns' in t) or has_all(t,('trident','z5','royal','neo','32gb','6000','cl28'))): return False,'required exact-model terms missing'
  return (True,'exact Royal Neo 32GB CL28 kit + sane price') if two_dimm(t) or 'g16gx2' in t else (False,'two-DIMM kit not confirmed')
 if pid=='ram-royal-neo-64':
  if not (('f5 6000j3036g32gx2 tr5ns' in t) or has_all(t,('trident','z5','royal','neo','64gb','6000','cl30'))): return False,'required exact-model terms missing'
  return (True,'exact Royal Neo 64GB CL30 kit + sane price') if two_dimm(t) or 'g32gx2' in t else (False,'two-DIMM kit not confirmed')
 if pid=='ram-64gb-alt':
  if not has_all(t,('64gb','ddr5','6000')) or not any(x in t for x in ('2x32','2 x 32','32gb x2','32gb x 2')): return False,'wrong RAM capacity/module layout'
  return (True,'64GB 2-DIMM DDR5-6000 CL30/32 white/silver kit + sane price') if any(x in t for x in ('cl30','c30','cl32','c32')) and any(x in t for x in ('white','silver')) else (False,'required exact-model terms missing')
 if pid=='cooler-hydroshift-ii': return (True,'exact HydroShift II OLED 360 White family + sane price') if has_all(t,('lian','li','hydroshift','ii','oled','360','white')) and any(x in t for x in ('p28','curved')) else (False,'required exact-model terms missing')
 if pid=='cooler-tryx-panorama-se': return (True,'exact TRYX Panorama SE 360 White + sane price') if has_all(t,('tryx','panorama','se','360','white')) else (False,'required exact-model terms missing')
 if pid=='psu-lianli-rs1200': return (True,'exact Lian Li RS1200 White family + sane price') if has_all(t,('lian','li','1200w','white')) and any(x in t for x in ('rs1200','rs1200g','rs1200w')) else (False,'required exact-model terms missing')
 if pid=='fans-lianli-tl120-reverse': return (True,'Lian Li TL120 Reverse White + sane price') if has_all(t,('lian','li','tl','120','white','reverse')) else (False,'reverse-blade identity not confirmed')
 if pid=='fans-value-reverse': return (True,'120mm white reverse-blade fan + sane price') if '120' in t and 'white' in t and 'reverse' in t else (False,'reverse-blade identity not confirmed')
 if pid=='nvme-nm790-4tb':
  if not has_all(t,('lexar','nm790','4tb')):return False,'required exact-model terms missing'
  return (False,'not internal NVMe drive') if any(x in t for x in ('external','portable','enclosure')) else (True,'exact Lexar NM790 4TB + sane price')
 if pid=='optical-uhd': return (True,'UHD/4K Blu-ray drive + sane price') if any(x in t for x in ('blu ray','bluray','blu-ray')) and any(x in t for x in ('uhd','4k')) else (False,'UHD Blu-ray identity not confirmed')
 if pid=='gpu-3090':
  if not has_all(t,('3090','24gb')) or any(x in t for x in ('3090 ti','3090ti')):return False,'different model/variant'
  return (False,'water-cooled 3090 not suitable for automatic air-cooled watch') if any(x in t for x in ('hydro copper','waterforce wb','water cooled','watercooled','waterblock')) else (True,'RTX 3090 24GB candidate + sane price')
 if pid=='gpu-5090': return (True,'RTX 5090 32GB + sane price') if has_all(t,('5090','32gb')) and not any(x in t for x in ('5090d','5090 d')) else (False,'different model/variant')
 if pid=='gpu-pro5000-blackwell-48gb': return (True,'RTX PRO 5000 Blackwell 48GB + sane price') if has_all(t,('rtx','pro','5000','blackwell','48gb')) and 'ada' not in t else (False,'different model/variant')
 if pid=='gpu-a6000-48gb': return (True,'RTX A6000 48GB + sane price') if has_all(t,('rtx','a6000','48gb')) and not any(x in t for x in ('ada','blackwell')) else (False,'different model/variant')
 return False,'no strong rule for this item'
def classification(reason):
 if reason.startswith('price $'): return 'rejected'
 return 'rejected' if reason in DETERMINISTIC_REASONS else 'manual_review'
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
   ok,reason=match_result(p,{'title':row.get('model',''),'condition':row.get('condition',''),'extracted_price':row.get('price')},row.get('price')); new_status='verified' if ok else classification(reason); new_match='strong' if ok else ('rejected' if new_status=='rejected' else 'review'); trusted+=int(ok); rejected+=int(new_status=='rejected'); reviewed+=int(new_status=='manual_review')
   if row.get('status')!=new_status or row.get('match_status')!=new_match or row.get('validation_version')!=VALIDATION_VERSION or row.get('validation_reason')!=reason: row.update(status=new_status,match_status=new_match,validation_version=VALIDATION_VERSION,validation_reason=reason); dirty=True; changed+=1
  if dirty:path.write_text(json.dumps(rows,indent=2)+'\n')
 return {'changed':changed,'trusted_rows':trusted,'rejected_rows':rejected,'review_rows':reviewed}
def observation(p,slug,r,pr,ts,status,reason,query_kind='generic'): return {'component_id':p['id'],'component':p['label'],'model':r.get('title') or p.get('model',''),'condition':r.get('condition'),'seller':r.get('source') or r.get('seller') or r.get('merchant'),'delivery':r.get('delivery'),'retailer':slug,'price':pr,'currency':'USD','source_url':source_url(r,(p.get('retailer_search_urls') or {}).get(slug,'')),'availability':'Shown in Google Shopping','status':status,'method':'serpapi_google_shopping','match_status':'strong' if status=='verified' else ('rejected' if status=='rejected' else 'review'),'validation_version':VALIDATION_VERSION,'validation_reason':reason,'query_kind':query_kind,'timestamp':ts,'notes':reason}
def search_query(p,ts=None):
 terms=p.get('search_terms') or [p.get('model') or p.get('label')]
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
 strong,review,rejected=parse_payload(p,serp(search_query(p,ts),key),ts); v=rv=rj=m=0; unresolved=[]
 for slug in expected(p):
  if slug in strong:append(p['id'],strong[slug]); v+=1
  elif slug in review:append(p['id'],review[slug]); rv+=1; unresolved.append(slug)
  elif slug in rejected:append(p['id'],rejected[slug]); rj+=1; unresolved.append(slug)
  else:unresolved.append(slug)
 return v,rv,rj,m,unresolved
def fallback_collect(p,slug,key,ts):
 strong,review,rejected=parse_payload(p,serp(retailer_query(p,slug,ts),key),ts,'retailer_fallback',slug)
 if slug in strong:append(p['id'],strong[slug]); return 'verified'
 if slug in review:append(p['id'],review[slug]); return 'manual_review'
 if slug in rejected:append(p['id'],rejected[slug]); return 'rejected'
 append(p['id'],{'component_id':p['id'],'component':p['label'],'model':p.get('model',''),'retailer':slug,'source_url':(p.get('retailer_search_urls') or {}).get(slug,''),'availability':'Unknown','status':'not_found','method':'serpapi_google_shopping','query_kind':'retailer_fallback','timestamp':ts,'notes':'No matching result in retailer-specific fallback.'}); return 'not_found'
def searchable_products(): return [p for p in PRODUCTS if p.get('price_source','search')=='search' and p.get('search_enabled',True) and p.get('search_terms') and p.get('retailer_search_urls')]
def selected(batch,limit=None):
 items=searchable_products()
 if not items:return []
 n=len(items); count=min(batch,n) if limit is None else min(batch,n,max(0,int(limit))); start=(date.today().toordinal()*max(1,batch))%n; return [items[(start+i)%n] for i in range(count)]
def fallback_candidates(picks,unresolved):
 priority={'cpu-9950x3d':0,'ram-royal-neo-64':1,'ram-royal-neo-32':2,'cooler-hydroshift-ii':3,'psu-lianli-rs1200':4,'nvme-nm790-4tb':5,'gpu-3090':6,'gpu-a6000-48gb':7,'gpu-pro5000-blackwell-48gb':8,'gpu-5090':9}; out=[]
 for p in picks:
  for slug in unresolved.get(p['id'],[]): out.append((priority.get(p['id'],20),p['id'],slug,p))
 out.sort(key=lambda x:(x[0],x[1],x[2])); return out
def main():
 ts=now(); revalidated=revalidate_existing(); key=os.getenv('SERPAPI_API_KEY','').strip(); pre=CONFIG.get('preflight',{}); max_batch=int(pre.get('max_serpapi_searches_per_run',24)); fallback_budget=max(0,min(3,int(pre.get('retailer_fallback_searches_per_run',1)))); base_cap=max(1,max_batch-fallback_budget); requested=max(1,min(int(os.getenv('SERPAPI_DAILY_BATCH',str(max_batch))),max_batch)); quota=quota_state(ts); base_budget=min(base_cap,requested,quota['checks_remaining_to_plan']); picks=selected(base_budget,base_budget); v=rv=rj=m=fail=attempted=fallbacks=0; unresolved={}
 if not key:
  status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'searchable_products':len(searchable_products()),'check_failures':0,'existing_results_revalidated':revalidated,'quota':quota,'note':'SERPAPI_API_KEY missing; offline revalidation completed and no quota was consumed.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)+'\n'); print(json.dumps(status,indent=2)); return
 if not picks:
  status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':0,'batch_size':requested,'searchable_products':len(searchable_products()),'check_failures':0,'existing_results_revalidated':revalidated,'quota':quota,'note':'Monthly tracker budget exhausted; no SerpApi request was made.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)+'\n'); print(json.dumps(status,indent=2)); return
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
 quota=quota_state(ts); status={'checked_at':ts,'source':'serpapi_google_shopping','searches_attempted':attempted,'base_searches':attempted-fallbacks,'retailer_fallback_searches':fallbacks,'max_searches_per_run':max_batch,'searchable_products':len(searchable_products()),'verified_retailer_offers':v,'manual_review_candidates':rv,'auto_rejected_results':rj,'missing_retailer_results':m,'check_failures':fail,'existing_results_revalidated':revalidated,'quota':quota,'note':'Current Frieren build targets searched with product-specific strong-match rules. Manual-review/rejected rows never count as trusted prices.'}; (DATA/'collector_status.json').write_text(json.dumps(status,indent=2)+'\n'); print(json.dumps(status,indent=2))
if __name__=='__main__': main()
