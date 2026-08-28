#!/usr/bin/env python3
"""No-API retailer page adapters.

Reads exact product URLs from data/products.json and extracts price/availability
from public product pages. It does not search retailers, bypass protections,
or attempt CAPTCHA/login/rate-limit evasion. If a page cannot be fetched or a
price cannot be verified, the result is check_failed/not_found.
"""
from __future__ import annotations
import json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from html import unescape
from urllib import robotparser

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
PRODUCTS=json.loads((DATA/"products.json").read_text())
RETAILERS={r["id"]:r for r in json.loads((DATA/"retailers.json").read_text())}
OBS_DIR=DATA/"observations"
OBS_DIR.mkdir(exist_ok=True)

UA="PrivateServerPriceTracker/1.1 (+price tracking; contact via repository)"
TIMEOUT=20
DELAY=2.0

def now(): return datetime.now(timezone.utc).isoformat()

def retailer_for(url):
    host=urlparse(url).netloc.lower().split(":")[0]
    for rid,r in RETAILERS.items():
        if host==r["domain"] or host.endswith("."+r["domain"]): return rid
    return None

def allowed_by_robots(url):
    p=urlparse(url)
    rp=robotparser.RobotFileParser()
    rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
    try:
        rp.read()
        return rp.can_fetch(UA,url)
    except Exception:
        # If robots.txt itself cannot be retrieved, do not treat that as a
        # reason to bypass access controls; fetch may still fail normally.
        return True

def fetch(url):
    if not allowed_by_robots(url):
        return None,"robots_disallow"
    req=Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml"})
    try:
        with urlopen(req,timeout=TIMEOUT) as r:
            code=getattr(r,"status",200)
            if code!=200: return None,f"http_{code}"
            ctype=r.headers.get("content-type","")
            if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
                return None,"not_html"
            return r.read().decode("utf-8","replace"),None
    except HTTPError as e:
        return None,f"http_{e.code}"
    except URLError as e:
        return None,f"network_error:{e.reason}"
    except Exception as e:
        return None,f"fetch_error:{type(e).__name__}"

def jsonld_blocks(html):
    out=[]
    for raw in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',html,re.I|re.S):
        raw=unescape(raw).strip()
        try:
            val=json.loads(raw)
            out.extend(val if isinstance(val,list) else [val])
        except Exception:
            continue
    return out

def find_product_nodes(node):
    if isinstance(node,dict):
        typ=node.get("@type")
        types=typ if isinstance(typ,list) else [typ]
        if any(str(t).lower()=="product" for t in types): yield node
        for v in node.values(): yield from find_product_nodes(v)
    elif isinstance(node,list):
        for v in node: yield from find_product_nodes(v)

def price_from_product(p):
    offers=p.get("offers")
    if isinstance(offers,list): offers=offers[0] if offers else {}
    if isinstance(offers,dict):
        for k in ("price","lowPrice"):
            v=offers.get(k)
            if v is not None:
                try: return float(str(v).replace(",",""))
                except ValueError: pass
    return None

def extract(html):
    # Prefer Schema.org JSON-LD because it is structured product data.
    for block in jsonld_blocks(html):
        for p in find_product_nodes(block):
            price=price_from_product(p)
            if price is not None:
                offers=p.get("offers") or {}
                if isinstance(offers,list): offers=offers[0] if offers else {}
                availability=(offers.get("availability") or "Unknown") if isinstance(offers,dict) else "Unknown"
                return {"price":price,"availability":availability,"method":"page_jsonld","product_name":p.get("name")}
    # Conservative fallback: common meta price fields only.
    patterns=[
        r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+itemprop=["\']price["\'][^>]+content=["\']([^"\']+)',
    ]
    for pat in patterns:
        m=re.search(pat,html,re.I)
        if m:
            try: return {"price":float(m.group(1).replace(",","")),"availability":"Unknown","method":"page_meta","product_name":None}
            except ValueError: pass
    return None

def run():
    results=[]
    for product in PRODUCTS:
        urls=product.get("watch_urls",[]) or []
        for url in urls:
            rid=retailer_for(url)
            if not rid:
                results.append({"component":product["id"],"url":url,"status":"check_failed","reason":"unsupported_retailer_domain","checked_at":now()})
                continue
            r=RETAILERS[rid]
            html,err=fetch(url)
            if err:
                results.append({"component":product["id"],"retailer":r["name"],"url":url,"status":"check_failed","reason":err,"checked_at":now()})
            else:
                info=extract(html)
                if not info:
                    results.append({"component":product["id"],"retailer":r["name"],"url":url,"status":"not_found","reason":"no_verifiable_price","checked_at":now()})
                else:
                    results.append({
                        "timestamp":now(),"component":product["id"],"model":product.get("model",""),
                        "retailer":r["name"],"retailer_id":rid,"price":info["price"],"currency":"USD",
                        "source_url":url,"availability":info.get("availability","Unknown"),
                        "status":"verified","method":info.get("method","page"),"notes":"Public product page; no API used."
                    })
            time.sleep(DELAY)
    # Group verified/failed observations by component.
    by={}
    for x in results: by.setdefault(x["component"],[]).append(x)
    for cid,items in by.items():
        path=OBS_DIR/f"{cid}.json"
        existing=json.loads(path.read_text()) if path.exists() and path.read_text().strip() else []
        if not isinstance(existing,list): existing=[]
        existing.extend(items)
        path.write_text(json.dumps(existing,indent=2))
    status={"checked_at":now(),"mode":"no_api_page_adapters","results":results,
            "policy":{"no_api":True,"no_captcha_bypass":True,"no_rate_limit_evasion":True,"no_guessing":True}}
    (DATA/"retailer_status.json").write_text(json.dumps(status,indent=2))
    print(json.dumps(status,indent=2))

if __name__=="__main__": run()
