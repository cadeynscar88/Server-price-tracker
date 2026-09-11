# Private Server Price Tracker

This repository hosts the iPhone-first GitHub Pages price tracker for the user's Frieren gaming-PC/private-server build.

## Current tracker state — Sep 11 2026

The repository is aligned to the current hardware plan rather than the older RAM/4090/1TB-SSD search.

### Purchased / fixed

- AMD Ryzen 9 9950X3D — purchased at $619.99; retained on price-protection watch only.
- ASRock X870E Taichi White — purchased.
- MSI GeForce RTX 5070 Ti Frieren Edition 16GB — purchased and retained as gaming/Mid-AI GPU.
- G.Skill Trident Z5 Royal Neo Silver 96GB (2x48GB) DDR5-6000 CL28 — purchased/final; routine RAM shopping is closed and RAM customization is deferred.
- Lian Li O11 Dynamic EVO RGB White — purchased.
- Lexar NM790 4TB TLC Gen4 NVMe — purchased for persistent server data.
- ASRock Phantom Gaming PG-1600G 1600W — ordered at $199.99.

`Frieren` refers only to the MSI GPU. The overall build is white / black / champagne-gold, not Frieren-themed.

## Active completion targets

### CPU cooling / fans

Stage 1:
- Lian Li HydroShift II OLED Curved 360TL White (`HS2OLDC36TW`).
- The AIO includes 3x white TL FLEX Standard fans for top-radiator exhaust.
- 3x white Lian Li SL-INF FLEX Reverse fans for bottom intake.

Stage 2:
- 3x white Lian Li TL LCD FLEX Reverse fans for side intake.
- 1x white Lian Li TL FLEX Standard fan for rear exhaust.

### OS/application SSD

- Separate 2TB high-quality TLC Gen4 NVMe is the baseline.
- 4TB is an opportunistic value upgrade when the premium over a directly comparable 2TB model is about $200-$225 or less, especially when $/TB improves materially.
- The existing Lexar NM790 4TB remains persistent server-data storage.
- Do **not** assume a second physical ingestion/staging SSD, a second NM790 mirror drive, or repartitioning of the existing NM790 at this stage.
- Implementation requires logical separation between untrusted `INGESTION/STAGING` and encrypted authoritative `SERVER_DATA`.

### ASRock white factory cabling

Track:
- `CB-FKITWT` — ASRock White Cable Full Package Kit. Normal U.S. retail availability is actionable even without a discount.
- `CB-12V2X6L600W/W` — ASRock white 600W 12V-2x6 TempGuard cable.

Exact PG-1600G compatibility and supported NTC/TempGuard over-temperature functionality must be preserved. Generic modular PSU cables are not substitutes unless exact PSU-side pinout compatibility is independently verified.

### Future Heavy GPU

Exact Heavy GPU is intentionally open for the later 2027/2028 horizon. The tracker keeps reference graphs for:
- RTX PRO 5000 Blackwell 48GB ECC
- used RTX A6000 48GB ECC
- RTX 5090 32GB
- RTX PRO 6000 Blackwell 96GB as an exceptional-value wildcard

## Deal logic

A sale label does not make an item a deal. BUY / BUY NOW / CONSIDER decisions are based on verified market value and build fit.

During Prime Big Deal Days, early-November promotions, Black Friday Week, Cyber Monday and similar sale windows, compare the advertised price against recent verified baselines. Fake markdowns, inflated reference prices and ordinary prices wearing sale labels remain WAIT/PASS.

## Price-history graphs

The Parts page links each product to `history.html?id=<product-id>`.

Graphs plot verified observations from `data/observations/<product-id>.json`. Current exact-model manual-web observations can seed a graph immediately; subsequent scheduled SerpApi checks add new points.

The older HydroShift P28 graph was reset when the active cooler changed to the 360TL model so unrelated variants do not share one trend line.

## Collection architecture

- GitHub Pages UI is read-only with respect to GitHub.
- `SERPAPI_API_KEY` exists only as a GitHub Actions Secret.
- `.github/workflows/price-check-v2.yml` runs twice weekly, Tuesdays and Fridays, and can also be launched manually from GitHub Actions.
- `scripts/check_prices.py` continues collecting the legacy-supported exact targets such as the 9950X3D, HydroShift family and primary Heavy-GPU candidates.
- `scripts/check_current_targets.py` collects the newer exact graph targets: current Lian Li fan banks, ASRock white cabling, current MP44 OS-SSD comparison and RTX PRO 6000 wildcard.
- `scripts/build_summary.py` rebuilds current summary data after collection.

The separate ChatGPT Frieren Build Deal Tracker is independent of the twice-weekly GitHub collector and performs the broader live deal search.

## Freshness / trust rules

- Never fabricate a price.
- Search snippets, shopping feeds and price trackers are leads, not sufficient proof for a purchase recommendation.
- BUY/BUY NOW requires live exact-model verification, seller, condition, stock/orderability, shipping, warranty/returns or buyer protection and compatibility.
- GitHub graph observations may come from verified manual-web research or the repository's SerpApi collectors.
- A graph point is price-history evidence, not an instruction to purchase without rechecking the live listing.
- If a retailer disappears from a later scan, retain prior verified history rather than guessing a replacement price.

## Main files

- `index.html` — GitHub Pages app
- `history.html` — per-product price-history graph
- `data/config.json` — current build state and tracker policy
- `data/products.json` — current product list
- `data/observations/` — per-product price history
- `data/summary.json` — displayed build summary
- `scripts/check_prices.py` — primary SerpApi collector
- `scripts/check_current_targets.py` — exact current-target graph collector
- `.github/workflows/price-check-v2.yml` — scheduled/manual collector workflow

## Manual refresh

Open **Actions → SerpApi Price Check v2 → Run workflow** for an immediate GitHub-side price refresh. Do not place API keys in repository files, browser storage, issues or commits.
