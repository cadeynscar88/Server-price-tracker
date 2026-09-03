#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; OBS=DATA/'observations'
config=json.loads((DATA/'config.json').read_text())
products=json.loads((DATA/'products.json').read_text())

def observations(pid):
    p=OBS/f'{pid}.json'
    try: return json.loads(p.read_text()) if p.exists() else []
    except Exception: return []

def trusted(o):
    if o.get('status')!='verified' or not isinstance(o.get('price'),(int,float)): return False
    if o.get('method')=='serpapi_google_shopping': return o.get('match_status')=='strong'
    return True

def stats(pid):
    v=sorted([o for o in observations(pid) if trusted(o)], key=lambda o:o.get('timestamp',''))
    if not v: return None
    latest={o.get('retailer','?'):o for o in v}
    cur=min(latest.values(),key=lambda o:o['price'])
    prices=[o['price'] for o in v]; ss=sorted(prices)
    median=ss[len(ss)//2] if len(ss)%2 else (ss[len(ss)//2-1]+ss[len(ss)//2])/2
    return {'n':len(v),'cur':cur['price'],'curObs':cur,'min':min(prices),'max':max(prices),'avg':sum(prices)/len(prices),'median':median}

def main():
    collector={}
    try: collector=json.loads((DATA/'collector_status.json').read_text())
    except Exception: pass
    manual={}
    try: manual=json.loads((DATA/'manual_price_crossover.json').read_text())
    except Exception: manual={'observations':[]}
    component_stats={p['id']:stats(p['id']) for p in products if p.get('price_source','search')=='search'}
    purchased=config.get('purchased_components',{})
    purchase_total=round(sum(float(v.get('purchase_price_usd',0) or 0)+float(v.get('protection_plan_usd',0) or 0) for v in purchased.values()),2)
    summary={
      'generated':datetime.now(timezone.utc).isoformat(),
      'last_check':collector.get('checked_at'),
      'tracker_version':config.get('version'),
      'target_budget':config.get('target_budget'),
      'build_state_updated':config.get('build_state_updated'),
      'confirmed_build':config.get('current_build_plan',{}),
      'purchased_components':purchased,
      'returned_components':config.get('returned_components',{}),
      'confirmed_hardware_subtotal_ex_tax_usd':config.get('confirmed_hardware_subtotal_ex_tax_usd',purchase_total),
      'remaining_budget_to_target_usd':round(config.get('target_budget',0)-config.get('confirmed_hardware_subtotal_ex_tax_usd',purchase_total),2),
      'ram_strategy':config.get('dynamic_groups',{}).get('ram',{}),
      'cooler_strategy':config.get('dynamic_groups',{}).get('cooler',{}),
      'psu_strategy':config.get('dynamic_groups',{}).get('psu',{}),
      'future_gpu_watch':config.get('future_gpu_watch',{}),
      'storage_rules':config.get('storage_rules',{}),
      'component_price_stats':component_stats,
      'manual_price_crossover':manual.get('observations',[]),
      'verification_policy':'Manual crossover rows are historical/reference observations unless verified_live=true. Automated prices count only when tracker verification rules pass.'
    }
    (DATA/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
