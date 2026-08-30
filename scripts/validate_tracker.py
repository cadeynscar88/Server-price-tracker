#!/usr/bin/env python3
"""Fail fast before consuming SerpApi quota when tracker configuration is inconsistent."""
import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
config=json.loads((DATA/'config.json').read_text()); products=json.loads((DATA/'products.json').read_text())
errors=[]; warnings=[]; ids=[p.get('id') for p in products]; pmap={p['id']:p for p in products if p.get('id')}
if len(ids)!=len(set(ids)): errors.append('Duplicate product IDs exist.')
for p in products:
 if not p.get('id') or not p.get('label'): errors.append(f'Product missing id/label: {p}')
 if p.get('price_source','search')=='search':
  if not p.get('search_terms'): errors.append(f"{p.get('id')}: searchable product has no search_terms")
  if not p.get('retailer_search_urls'): errors.append(f"{p.get('id')}: searchable product has no retailer_search_urls")
for pid in config.get('fixed_build',[]):
 if pid not in pmap: errors.append(f'fixed_build references missing product {pid}')
for name,g in config.get('dynamic_groups',{}).items():
 if not g.get('candidates'): errors.append(f'dynamic group {name} has no candidates')
 for pid in g.get('candidates',[]):
  if pid not in pmap: errors.append(f'dynamic group {name} references missing product {pid}')
for key,c in config.get('storage_configs',{}).items():
 if c.get('product_id') not in pmap: errors.append(f'storage {key} references missing product')
 if c.get('usable_tb',0)<config.get('storage_requirement_tb',0): errors.append(f'storage {key} does not meet usable capacity requirement')
for g in config.get('gpu_scenarios',[]):
 if g.get('product_id') not in pmap: errors.append(f"GPU scenario {g.get('id')} references missing product")
 if g.get('psu_min_w',0)>1200: warnings.append(f"GPU scenario {g.get('id')} exceeds current PSU pool")
for d in config.get('derived_items',[]):
 if d.get('id') not in pmap or d.get('source_product_id') not in pmap: errors.append(f"Derived item mapping invalid: {d}")
# RAM/search strategy guards.
ram_rules=config.get('dynamic_groups',{}).get('ram',{}).get('rules',{})
if ram_rules.get('initial')!='ram-32gb' or 'ram-32gb' not in pmap: errors.append('Initial RAM strategy must point to tracked ram-32gb.')
for pid in ram_rules.get('deferred_search_ids',[]):
 if pid not in pmap: errors.append(f'Deferred RAM search references missing product {pid}')
 elif pmap[pid].get('search_enabled',True): errors.append(f'Deferred RAM product {pid} must have search_enabled=false')
for pid in config.get('deal_search_policy',{}).get('active_ids',[]):
 if pid not in pmap: errors.append(f'Deal search references missing product {pid}')
 elif not pmap[pid].get('search_enabled',True): errors.append(f'Active deal search {pid} is disabled')
# Hard architectural guards.
if pmap.get('motherboard',{}).get('attrs',{}).get('m2_slots')!=4: errors.append('Motherboard must expose four M.2 slots.')
if pmap.get('boot-ssd',{}).get('price_source')!='search' or 'SATA' not in pmap.get('boot-ssd',{}).get('label',''): errors.append('Boot SSD must remain a separately tracked SATA device.')
if 'M.2_2' not in config.get('storage_rules',{}).get('m2_assignment_4x2',[]): errors.append('4x2TB layout must account for M.2_2 lane-sharing tradeoff.')
if config.get('security_policy',{}).get('write_requires_fido2') is not True: errors.append('Production security rule requires FIDO2 for server-data writes.')
if config.get('security_policy',{}).get('read_stream_download_requires_fido2') is not False: errors.append('Read/stream/download must remain keyless after normal authentication.')
searchable=[p for p in products if p.get('price_source','search')=='search' and p.get('search_enabled',True)]
pre=config.get('preflight',{}); max_run=int(pre.get('max_serpapi_searches_per_run',24)); fallback=int(pre.get('retailer_fallback_searches_per_run',1)); monthly=int(pre.get('serpapi_monthly_limit',250)); reserve=int(pre.get('serpapi_reserve',10)); planned=int(pre.get('serpapi_monthly_budget',monthly-reserve)); base_cap=max_run-fallback
if max_run>24: errors.append('Configured SerpApi run cap exceeds 24-search quota strategy.')
if fallback<0 or fallback>3: errors.append('Retailer fallback search budget must be between 0 and 3.')
if monthly<=0: errors.append('SerpApi monthly limit must be positive.')
if reserve<0 or reserve>=monthly: errors.append('SerpApi reserve must be non-negative and smaller than monthly limit.')
if planned<0 or planned>monthly-reserve: errors.append('SerpApi planned monthly budget must fit inside monthly limit minus reserve.')
if max_run>planned: errors.append('Per-run SerpApi cap cannot exceed planned monthly budget.')
if len(searchable)>base_cap: warnings.append(f'{len(searchable)} active searchable products exceed base-search cap {base_cap}; rotation will be used.')
quota_path=DATA/'quota_status.json'
if quota_path.exists():
 try:
  q=json.loads(quota_path.read_text()); used=int(q.get('checks_used',0))
  if used<0: errors.append('Quota ledger checks_used cannot be negative.')
  if int(q.get('monthly_limit',monthly))!=monthly or int(q.get('planned_budget',planned))!=planned or int(q.get('reserve',reserve))!=reserve: warnings.append('Quota ledger limits differ from config; collector will normalize them on its next run.')
  if used>monthly: warnings.append('Repo-tracked SerpApi usage is above the configured absolute monthly limit.')
 except Exception as e: errors.append(f'quota_status.json is invalid: {e}')
print(json.dumps({'ok':not errors,'errors':errors,'warnings':warnings,'active_searchable_products':len(searchable),'base_search_cap':base_cap,'run_cap':max_run,'monthly_limit':monthly,'planned_budget':planned,'reserve':reserve},indent=2))
sys.exit(1 if errors else 0)
