#!/usr/bin/env python3
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OBS=DATA/'observations'
config=json.loads((DATA/'config.json').read_text()); products=json.loads((DATA/'products.json').read_text())
def observations(pid):
 p=OBS/f'{pid}.json'; return json.loads(p.read_text()) if p.exists() else []
def verified(pid): return [o for o in observations(pid) if o.get('status')=='verified' and isinstance(o.get('price'),(int,float))]
def stats(pid):
 v=sorted(verified(pid),key=lambda o:o.get('timestamp',''))
 if not v:return None
 latest={o.get('retailer','?'):o for o in v}; cur=min(latest.values(),key=lambda o:o['price']); prices=[o['price'] for o in v]; ss=sorted(prices)
 return {'n':len(v),'cur':cur['price'],'curObs':cur,'min':min(prices),'max':max(prices),'avg':sum(prices)/len(prices),'median':ss[len(ss)//2] if len(ss)%2 else (ss[len(ss)//2-1]+ss[len(ss)//2])/2,'prev':v[-2]['price'] if len(v)>1 else None}
def main():
 stg={}
 for k,c in config['storage_configs'].items():
  st=stats(c['product_id']); stg[k]={**c,'current_total':st['cur']*c['qty'] if st else None,'hist_low_total':st['min']*c['qty'] if st else None,'hist_avg_total':st['avg']*c['qty'] if st else None}
 available=[(k,v) for k,v in stg.items() if v['current_total'] is not None]; best=min(available,key=lambda kv:kv[1]['current_total'])[0] if available else None
 total=0; missing=0; comps={}; hist_low=hist_avg=0
 for p in products:
  if not p.get('in_build'): continue
  st=stats(p['id']); comps[p['id']]={'label':p['label'],'current':st['cur'],'low':st['min'],'high':st['max'],'avg':st['avg'],'median':st['median'],'n':st['n']} if st else None
  if st: total+=st['cur']*p.get('qty',1); hist_low+=st['min']*p.get('qty',1); hist_avg+=st['avg']*p.get('qty',1)
  else: missing+=1
 if best: total+=stg[best]['current_total']; hist_low+=stg[best]['hist_low_total']; hist_avg+=stg[best]['hist_avg_total']
 else: missing+=1
 target=config['target_budget']; verdict='NONE' if missing else ('BUY' if total<=target else 'WATCH' if total<=target*1.08 else 'WAIT')
 old=json.loads((DATA/'summary.json').read_text()) if (DATA/'summary.json').exists() else {}; hist=old.get('build_history',[])
 if missing==0: hist.append({'timestamp':datetime.now(timezone.utc).isoformat(),'total':round(total,2)})
 summary={'generated':datetime.now(timezone.utc).isoformat(),'last_check':datetime.now(timezone.utc).isoformat(),'build_total':round(total,2) if missing==0 else None,'missing_components':missing,'recommendation':verdict,'target':target,'components':comps,'storage':stg,'best_storage':best,'build_history':hist[-400:]}
 (DATA/'summary.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
