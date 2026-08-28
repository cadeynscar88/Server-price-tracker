# Private Server Price Tracker (PST) — v1.0.0

iPhone-first PWA that tracks component prices for the planned private server
against a **$2,400 target**, records real price history, and answers
**BUY / WATCH / WAIT** at a glance.

Everything runs in the browser. Data lives as JSON in this repo. No backend
server — a Netlify Function is used only as a CORS proxy for retailers
without APIs. **No price is ever fabricated**: failed checks are recorded as
`check_failed`.

## Architecture

```
iPhone PWA (index.html, GitHub Pages)
 ├─ reads/writes data/*.json  ──►  GitHub REST API (fine-grained PAT)
 ├─ Best Buy Products API     ──►  direct from the browser
 ├─ Netlify Function proxy    ──►  JSON-LD price extraction (B&H, Crucial, …)
 └─ Manual entry              ──►  offline pending queue → synced to repo
Laptop = same URL, read-only viewer.
```

## Setup

1. **Create the repo** — push these files to a GitHub repo, e.g.
   `private-server-price-tracker`.
2. **Enable Pages** — Settings → Pages → Deploy from branch → `main` / root.
   Open `https://<you>.github.io/private-server-price-tracker/` on the iPhone
   and **Add to Home Screen**.
3. **Token** — GitHub → Settings → Developer settings → Fine-grained tokens.
   Repository access: *only this repo*. Permissions: **Contents – Read and
   write**. Paste it in the app's Setup tab (stored on-device only).
4. **Best Buy key** (optional but recommended) — free key from
   developer.bestbuy.com. Paste in Setup. Then fill `bestbuy_sku` for any
   product in `data/products.json`.
5. **Proxy** (optional) — deploy this same repo to Netlify (it will pick up
   `netlify.toml` and the function automatically). Paste
   `https://<site>.netlify.app/.netlify/functions/proxy` in Setup. Then add
   `watch_urls` entries to products, e.g.
   `{"retailer":"crucial","url":"https://www.crucial.com/…"}`.

## Daily use

- **RUN PRICE CHECK NOW** — queries every configured adapter, records one
  observation per product×retailer, commits to the repo, updates the summary.
- **Check-on-open** — enable in Setup: if data is older than 48 h when you
  open the app, a check runs automatically (this replaces cron on iOS, which
  cannot run background PWAs).
- **Add price manually** — first-class path for Newegg / Micro Center /
  in-store prices. Works offline; entries queue on-device and sync later.
- **Export** — full JSON or observations CSV from the Data tab.

## Data files

| File | Purpose |
|---|---|
| `data/config.json` | Target budget, storage configs A/B, staleness window |
| `data/products.json` | Tracked components; add `bestbuy_sku` / `watch_urls`; motherboard `attrs.m2_slots < 4` without `expansion_ok` renders **DO NOT USE** |
| `data/observations/<id>.json` | Append-only price history per component |
| `data/summary.json` | Computed snapshot + build-total history (app-written) |
| `data/retailers.json`, `data/manufacturers.json` | Rating references, editable |

Observation schema (spec §12) plus `status`
(`verified | unavailable | not_found | check_failed`) and `method`
(`bestbuy | proxy | manual`).

## Storage rule (hard requirements)

4 TB usable, SSD/NVMe only, four NVMe positions on the board. The app always
prices both **A: 2×4 TB (mirror)** and **B: 4×2 TB (RAID10)** and tags the
cheaper one BEST.

## Future migration

The app only knows how to read/write a set of JSON shapes. Moving the backend
onto the private server later = serving the same shapes from an API and
changing the data base URL. Nothing else changes.

## Versioning

MAJOR.MINOR.PATCH per project convention. Changelog lives in the HTML comment
block at the top of `index.html`.
