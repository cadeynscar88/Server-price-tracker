#!/usr/bin/env python3
import json
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OBS=DATA/'observations'
config=json.loads((DATA/'config.json').read_text()); products=json.loads((DATA/'products.json').read_text()); pmap={p['id']:p for p in products}

def observations(pid):
 p=OBS/f'{pid}.json'; return json.loads(p.read_text()) if p.exists() else []
def trusted(o):
 if o.get('status')!='verified' or not isinstance(o.get('price'),(int,float)): return False
 if o.get('method')=='serpapi_google_shopping': return o.get('match_status')=='strong'
 return True
def verified(pid): return [o for o in observations(pid) if trusted(o)]
def stats(pid):
 v=sorted(verified(pid),key=lambda o:o.get('timestamp',''))
 if not v:return None
 latest={o.get('retailer','?'):o for o in v}; cur=min(latest.values(),key=lambda o:o['price']); prices=[o['price'] for o in v]; ss=sorted(prices)
 return {'n':len(v),'cur':cur['price'],'curObs':cur,'min':min(prices),'max':max(prices),'avg':sum(prices)/len(prices),'median':ss[len(ss)//2] if len(ss)%2 else (ss[len(ss)//2-1]+ss[len(ss)//2])/2}
def cur(pid):
 st=stats(pid); return st['cur'] if st else None

def choose_ecc(non_ecc,ecc,max_pct):
 a,b=cur(non_ecc),cur(ecc)
 if b is not None and (a is None or b<=a*(1+max_pct/100)): return ecc
 return non_ecc if a is not None else (ecc if b is not None else None)
def choose_ram():
 r=config['dynamic_groups']['ram']['rules']; p96=choose_ecc('ram-96gb','ram-96gb-ecc',r['favor_ecc_if_premium_pct_lte']); p128=choose_ecc('ram-128gb','ram-128gb-ecc',r['favor_ecc_if_premium_pct_lte'])
 if p96 and p128 and cur(p128)<=cur(p96)*(1+r['favor_128_if_premium_pct_lte']/100): return p128
 if p96:return p96
 if p128:return p128
 return 'ram-64gb' if cur('ram-64gb') is not None else None
def choose_cooler():
 n,t=cur('cooler-noctua'),cur('cooler-thermalright'); lim=config['dynamic_groups']['cooler']['rules']['favor_noctua_if_premium_usd_lte']
 if n is not None and (t is None or n-t<=lim): return 'cooler-noctua'
 return 'cooler-thermalright' if t is not None else ('cooler-noctua' if n is not None else None)
def choose_psu(min_w):
 p1,p12=cur('psu-1000w'),cur('psu-1200w'); lim=config['dynamic_groups']['psu']['rules']['favor_1200_if_premium_usd_lte']
 if min_w>1000:return 'psu-1200w' if p12 is not None else None
 if p12 is not None and p1 is not None and p12-p1<=lim:return 'psu-1200w'
 return 'psu-1000w' if p1 is not None else ('psu-1200w' if p12 is not None else None)
def choose_ups(peak_w):
 head=config['dynamic_groups']['ups']['rules']['output_headroom_pct']/100; need=peak_w*(1+head)
 for pid in ('ups-1000w','ups-1500w'):
  if cur(pid) is not None and pmap[pid].get('attrs',{}).get('output_w',0)>=need:return pid
 return None
def storage_totals():
 out={}
 for key,c in config['storage_configs'].items():
  v=cur(c['product_id']); out[key]={**c,'current_total':v*c['qty'] if v is not None else None}
 return out
def choose_storage(stg,second_gpu=False):
 a,b=stg['A']['current_total'],stg['B']['current_total']
 if a is None:return 'B' if b is not None else None
 if b is None:return 'A'
 rule=config['storage_rules']; threshold=rule['choose_4x2_only_if_savings_with_second_gpu_usd_gte'] if second_gpu else rule['choose_4x2_only_if_savings_usd_gte']
 return 'B' if a-b>=threshold else 'A'
def add_item(items,pid,qty=1,price_override=None):
 price=cur(pid) if price_override is None else price_override
 items.append({'id':pid,'label':pmap.get(pid,{}).get('label',pid),'qty':qty,'unit_price':price,'total':price*qty if price is not None else None})
 return price is not None

def scenario(g,stg):
 items=[]; missing=[]
 for pid in config['fixed_build']:
  if not add_item(items,pid):missing.append(pid)
 ram=choose_ram(); cooler=choose_cooler(); psu=choose_psu(g['psu_min_w']); ups=choose_ups(g['estimated_peak_w']); storage_key=choose_storage(stg,g.get('requires_second_gpu',False))
 for name,pid in [('ram',ram),('cooler',cooler),('psu',psu),('ups',ups)]:
  if pid is None:missing.append(name)
  elif not add_item(items,pid):missing.append(pid)
 gp=cur(g['product_id']); maxp=pmap[g['product_id']].get('attrs',{}).get('max_price',config['dynamic_groups']['gpu']['rules']['hard_price_ceiling_usd'])
 if gp is None:missing.append(g['product_id'])
 elif gp>maxp:missing.append(g['product_id']+':over-ceiling')
 else:add_item(items,g['product_id'],g['qty'])
 if storage_key is None:missing.append('storage')
 else:
  c=stg[storage_key]; items.append({'id':c['product_id'],'label':c['label'],'qty':c['qty'],'unit_price':cur(c['product_id']),'total':c['current_total']})
 # Offline backup derives from the currently trusted single-drive 2TB pool price.
 backup=cur('nvme-2tb')
 if backup is None:missing.append('backup-ssd')
 else:items.append({'id':'backup-ssd','label':pmap['backup-ssd']['label'],'qty':1,'unit_price':backup,'total':backup})
 total=sum(x['total'] for x in items if x['total'] is not None) if not missing else None
 verdict='INCOMPLETE' if missing else ('BUY' if total<=config['target_budget'] else 'WATCH' if total<=config['target_budget']*1.08 else 'WAIT')
 return {'id':g['id'],'label':g['label'],'vram_gb':g.get('vram_gb'),'requires_second_gpu':g.get('requires_second_gpu',False),'storage_choice':storage_key,'ram_choice':ram,'cooler_choice':cooler,'psu_choice':psu,'ups_choice':ups,'estimated_peak_w':g['estimated_peak_w'],'items':items,'missing':missing,'total':round(total,2) if total is not None else None,'recommendation':verdict,'physical_fit':g.get('physical_fit','standard-check')}

def main():
 stg=storage_totals(); scenarios=[scenario(g,stg) for g in config['gpu_scenarios']]
 complete=[s for s in scenarios if s['total'] is not None]
 within=[s for s in complete if s['total']<=config['target_budget']]
 if within: recommended=max(within,key=lambda s:(s.get('vram_gb') or 0,-s['total']))
 elif complete: recommended=min(complete,key=lambda s:s['total'])
 else: recommended=None
 comps={p['id']:stats(p['id']) for p in products if p.get('price_source','search')=='search'}
 old=json.loads((DATA/'summary.json').read_text()) if (DATA/'summary.json').exists() else {}; hist=old.get('build_history',[])
 if recommended and recommended['total'] is not None:hist.append({'timestamp':datetime.now(timezone.utc).isoformat(),'scenario':recommended['id'],'total':recommended['total']})
 summary={'generated':datetime.now(timezone.utc).isoformat(),'last_check':datetime.now(timezone.utc).isoformat(),'target':config['target_budget'],'recommended_scenario':recommended['id'] if recommended else None,'build_total':recommended['total'] if recommended else None,'recommendation':recommended['recommendation'] if recommended else 'INCOMPLETE','components':comps,'storage':stg,'scenarios':scenarios,'build_history':hist[-400:],'verification_policy':'Manual verified observations are trusted. SerpApi observations count only with match_status=strong. Dynamic scenarios enforce storage, RAM, PSU, UPS and GPU ceiling rules.'}
 (DATA/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
