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

def choose_ram():
 # Initial production strategy is deliberately 32GB/2x16. Larger kits remain
 # reference/deferred products until Server Health shows sustained pressure.
 return 'ram-32gb' if cur('ram-32gb') is not None else None
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
 need=peak_w*(1+config['dynamic_groups']['ups']['rules']['output_headroom_pct']/100)
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
 threshold=config['storage_rules']['choose_4x2_only_if_savings_with_second_gpu_usd_gte'] if second_gpu else config['storage_rules']['choose_4x2_only_if_savings_usd_gte']
 return 'B' if a-b>=threshold else 'A'
def add_item(items,pid,qty=1,price_override=None):
 price=cur(pid) if price_override is None else price_override; items.append({'id':pid,'label':pmap.get(pid,{}).get('label',pid),'qty':qty,'unit_price':price,'total':price*qty if price is not None else None}); return price is not None

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
 backup=cur('nvme-2tb')
 if backup is None:missing.append('backup-ssd')
 else:items.append({'id':'backup-ssd','label':pmap['backup-ssd']['label'],'qty':1,'unit_price':backup,'total':backup})
 total=sum(x['total'] for x in items if x['total'] is not None) if not missing else None
 verdict='INCOMPLETE' if missing else ('BUY' if total<=config['target_budget'] else 'WATCH' if total<=config['target_budget']*1.08 else 'WAIT')
 return {'id':g['id'],'label':g['label'],'vram_gb':g.get('vram_gb'),'requires_second_gpu':g.get('requires_second_gpu',False),'storage_choice':storage_key,'ram_choice':ram,'cooler_choice':cooler,'psu_choice':psu,'ups_choice':ups,'estimated_peak_w':g['estimated_peak_w'],'items':items,'missing':missing,'total':round(total,2) if total is not None else None,'recommendation':verdict,'physical_fit':g.get('physical_fit','standard-check')}

def deal_watch():
 ids=config.get('deal_search_policy',{}).get('active_ids',[]); out={}
 for pid in ids:
  st=stats(pid); row={'id':pid,'label':pmap.get(pid,{}).get('label',pid),'stats':st,'status':'NO_VERIFIED_DEAL'}
  if st:
   price=st['cur']; row['status']='VERIFIED'
   if pid=='bundle-9950x-proart':
    has_ram='32gb' in str(st['curObs'].get('model','')).lower(); target=config['bundle_policy']['cpu_motherboard_ram_strong_buy_target_usd'] if has_ram else config['bundle_policy']['cpu_motherboard_buy_target_usd']; row['target']=target; row['status']='STRONG_DEAL' if price<=target else 'WATCH'
   elif pid=='openbox-cpu-9950x': row['target']=config['cpu_policy']['open_box_9950x_target_usd']; row['status']='STRONG_DEAL' if price<=row['target'] else 'WATCH'
   elif pid=='cpu-9950x3d':
    base=cur('cpu'); row['premium_vs_9950x']=round(price-base,2) if base is not None else None; row['status']='PREFER_X3D' if base is not None and price-base<=config['cpu_policy']['favor_x3d_if_premium_usd_lte'] else 'WATCH'
  out[pid]=row
 return out

def main():
 generated=datetime.now(timezone.utc).isoformat(); collector={}
 try: collector=json.loads((DATA/'collector_status.json').read_text())
 except Exception: collector={}
 last_check=collector.get('checked_at'); stg=storage_totals(); scenarios=[scenario(g,stg) for g in config['gpu_scenarios']]; complete=[s for s in scenarios if s['total'] is not None]; within=[s for s in complete if s['total']<=config['target_budget']]
 recommended=max(within,key=lambda s:(s.get('vram_gb') or 0,-s['total'])) if within else (min(complete,key=lambda s:s['total']) if complete else None)
 comps={p['id']:stats(p['id']) for p in products if p.get('price_source','search')=='search'}
 old=json.loads((DATA/'summary.json').read_text()) if (DATA/'summary.json').exists() else {}; hist=old.get('build_history',[])
 if recommended and recommended['total'] is not None and last_check:
  if not hist or hist[-1].get('timestamp')!=last_check: hist.append({'timestamp':last_check,'scenario':recommended['id'],'total':recommended['total']})
 summary={'generated':generated,'last_check':last_check,'target':config['target_budget'],'recommended_scenario':recommended['id'] if recommended else None,'build_total':recommended['total'] if recommended else None,'recommendation':recommended['recommendation'] if recommended else 'INCOMPLETE','initial_ram_strategy':'32GB 2x16; larger RAM searches paused until sustained memory-pressure evidence','components':comps,'deal_watch':deal_watch(),'storage':stg,'scenarios':scenarios,'build_history':hist[-400:],'verification_policy':'SerpApi prices count only when identity, condition/type and sanity-price rules pass with match_status=strong. Deferred products do not consume searches; manual-review rows never affect totals.'}
 (DATA/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
