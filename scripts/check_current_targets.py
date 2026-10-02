#!/usr/bin/env python3
"""Collect exact-model prices for current graph targets not covered by the legacy matcher."""
import json, os, re
from pathlib import Path
import check_prices as cp

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
PRODUCTS=json.loads((DATA/'products.json').read_text())
CONFIG=json.loads((DATA/'config.json').read_text())
PMAP={p['id']:p for p in PRODUCTS}
TARGETS=list(CONFIG.get('deal_search_policy',{}).get('manual_graph_ids',[]))


def n(v):
    s=str(v or '').lower().replace('&',' and ')
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9]+',' ',s)).strip()


def exact(pid,title):
    t=n(title)
    if pid=='fans-sl-inf-flex-reverse-3pack':
        return all(x in t for x in ('lian','li','sl','inf','flex','reverse','white')) and any(x in t for x in ('3 pack','3pack','triple'))
    if pid=='fans-tl-lcd-flex-reverse-3pack':
        return all(x in t for x in ('lian','li','tl','lcd','flex','reverse','white')) and any(x in t for x in ('3 pack','3pack','triple'))
    if pid=='fans-tl-flex-standard-single':
        return all(x in t for x in ('lian','li','tl','flex','white')) and 'reverse' not in t and 'lcd' not in t
    if pid=='cable-asrock-full-white-kit':
        return ('cb fkitwt' in t) or all(x in t for x in ('asrock','white','cable','full','package','kit'))
    if pid=='cable-asrock-tempguard-white':
        return ('cb 12v2x6l600w w' in t) or all(x in t for x in ('asrock','12v','2x6','600w','white'))
    if pid=='os-ssd-mp44-2tb':
        return all(x in t for x in ('team','group','mp44','2tb')) and not any(x in t for x in ('mp44l','mp44q'))
    if pid=='os-ssd-mp44-4tb':
        return all(x in t for x in ('team','group','mp44','4tb')) and not any(x in t for x in ('mp44l','mp44q'))
    if pid=='gpu-pro6000-blackwell-96gb':
        return all(x in t for x in ('rtx','pro','6000','blackwell','96gb'))
    if pid=='aon-minisforum-n5-ryzen7-255':
        return all(x in t for x in ('minisforum','n5','ryzen','7','255')) and 'air' not in t and 'pro' not in t
    if pid=='aon-minisforum-n5-air-ryzen7-255':
        return all(x in t for x in ('minisforum','n5','air','ryzen','7','255')) and 'pro' not in t
    if pid=='aon-minisforum-n5-pro-hx370':
        return all(x in t for x in ('minisforum','n5','pro')) and ('hx pro 370' in t or 'hxpro370' in t or '370' in t)
    if pid=='aon-ugreen-dxp4800-gt':
        return all(x in t for x in ('ugreen','dxp4800','gt')) and 'plus' not in t and 'pro' not in t
    if pid=='aon-ugreen-dxp4800-plus':
        return all(x in t for x in ('ugreen','dxp4800','plus')) and 'pro' not in t and 'gt' not in t
    if pid=='aon-ugreen-dxp4800-pro':
        return all(x in t for x in ('ugreen','dxp4800','pro')) and 'plus' not in t and 'gt' not in t
    if pid=='aon-terramaster-f4-425-pro-n305':
        return all(x in t for x in ('terramaster','f4','425','pro','n305'))
    if pid=='aon-terramaster-f4-425-pro-n350':
        return all(x in t for x in ('terramaster','f4','425','pro','n350'))
    if pid=='aon-asustor-as6804t':
        return ('as6804t' in t) and ('asustor' in t or 'lockerstor' in t)
    if pid=='aon-qnap-ts464':
        return ('qnap' in t) and ('ts 464' in t or 'ts464' in t)
    return False


def allowed_price(pid,p):
    bands={
        'fans-sl-inf-flex-reverse-3pack':(50,220),
        'fans-tl-lcd-flex-reverse-3pack':(80,260),
        'fans-tl-flex-standard-single':(15,80),
        'cable-asrock-full-white-kit':(40,300),
        'cable-asrock-tempguard-white':(20,100),
        'os-ssd-mp44-2tb':(100,700),
        'os-ssd-mp44-4tb':(200,900),
        'gpu-pro6000-blackwell-96gb':(4000,15000),
        'aon-minisforum-n5-ryzen7-255':(300,1200),
        'aon-minisforum-n5-air-ryzen7-255':(300,1300),
        'aon-minisforum-n5-pro-hx370':(600,2200),
        'aon-ugreen-dxp4800-gt':(300,1000),
        'aon-ugreen-dxp4800-plus':(300,1100),
        'aon-ugreen-dxp4800-pro':(400,1300),
        'aon-terramaster-f4-425-pro-n305':(300,1000),
        'aon-terramaster-f4-425-pro-n350':(300,1100),
        'aon-asustor-as6804t':(700,2200),
        'aon-qnap-ts464':(300,1100)
    }
    lo,hi=bands.get(pid,(0,float('inf')))
    return isinstance(p,(int,float)) and lo<=p<=hi


def main():
    key=os.environ.get('SERPAPI_API_KEY','').strip()
    if not key:
        print(json.dumps({'ok':True,'skipped':'SERPAPI_API_KEY missing'}))
        return
    ts=cp.now(); attempted=verified=0; results=[]
    for pid in TARGETS:
        product=PMAP.get(pid)
        if not product:
            results.append({'id':pid,'status':'missing_product'}); continue
        qstate=cp.quota_state(ts)
        if qstate.get('checks_remaining_to_plan',0)<=0 or qstate.get('checks_remaining_absolute',0)<=0:
            results.append({'id':pid,'status':'quota_stop'}); break
        query=(product.get('search_terms') or [product.get('model') or product.get('label')])[0]
        attempted+=1; cp.bump_quota(ts)
        try:
            payload=cp.serp(query,key)
        except Exception as e:
            results.append({'id':pid,'status':'error','error':str(e)}); continue
        seen={}
        for row in payload.get('shopping_results') or []:
            pr=cp.price(row); title=row.get('title') or ''
            if not exact(pid,title) or not allowed_price(pid,pr): continue
            slug=cp.retailer_slug(row.get('source') or row.get('seller') or row.get('merchant')) or n(row.get('source') or 'unknown').replace(' ','_')[:40] or 'unknown'
            cur=seen.get(slug)
            if cur is None or pr<cur[0]: seen[slug]=(pr,row)
        for slug,(pr,row) in seen.items():
            obs={
                'component_id':pid,
                'component':product.get('label'),
                'model':row.get('title') or product.get('model'),
                'condition':row.get('condition'),
                'seller':row.get('source') or row.get('seller') or row.get('merchant'),
                'delivery':row.get('delivery'),
                'retailer':slug,
                'price':pr,
                'currency':'USD',
                'source_url':cp.source_url(row,(product.get('retailer_search_urls') or {}).get(slug,'')),
                'availability':'Shown in Google Shopping; live retailer verification still required before purchase',
                'status':'verified',
                'method':'serpapi_current_targets',
                'match_status':'strong',
                'validation_version':'3.0',
                'validation_reason':'Exact current-target matcher passed',
                'query_kind':'current_exact_target',
                'timestamp':ts,
                'notes':'Graph observation only. Confirm the live retailer page before BUY/BUY NOW.'
            }
            cp.append(pid,obs); verified+=1
        results.append({'id':pid,'status':'ok','verified_retailers':sorted(seen.keys())})
    print(json.dumps({'ok':True,'checked_at':ts,'searches_attempted':attempted,'verified_rows':verified,'results':results},indent=2))


if __name__=='__main__':
    main()
