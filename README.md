# Private Server Price Tracker

This repository hosts the iPhone-first GitHub Pages tracker for the planned private server build.

## Architecture

- The browser/PWA is **read-only with respect to GitHub**. It never stores a GitHub PAT or the SerpApi key.
- Automated price discovery uses **SerpApi Google Shopping** from GitHub Actions.
- `SERPAPI_API_KEY` exists only as a GitHub Actions Secret.
- One Google Shopping search can return offers from multiple retailers for the same item.
- The scheduled collector rotates **7 tracked products per day**, which is 217 searches in a 31-day month and leaves some room under a 250-search monthly allowance for manual runs.
- If a retailer is absent from the latest Google Shopping result, it is explicitly flagged. The previous verified price is retained; no price is guessed or erased.

## Freshness colors

- **Green** — verified retailer price is 7 days old or newer and the latest applicable check returned the retailer.
- **Yellow** — the last verified price is more than 7 days old.
- **Red** — the latest check did not return the retailer, or the API check failed.
- **Gray** — that retailer/item combination has not produced a verified observation yet.

Each tracked item displays tappable retailer links. The app prefers the latest retailer/product URL returned by Google Shopping, then an exact tracked product URL when available, then the retailer search URL.

## Screenshot correction workflow

If an automated price is missing or stale:

1. Open the tracker on the iPhone.
2. Tap the retailer under the item.
3. Take a screenshot that clearly shows the retailer, matching item/model and price.
4. Send that screenshot in the ChatGPT conversation for this project.
5. The screenshot can be reviewed and added to `data/observations/<item>.json` as a `verified` observation with method `manual_screenshot`.

Manual screenshot observations are treated as real verified observations by the same build/history calculations. This preserves the security model: the PWA itself still has no credential capable of writing to GitHub.

## Repository layout

- `index.html` — GitHub Pages app and retailer/freshness display
- `data/config.json` — budget and storage-layout settings
- `data/products.json` — components, alternatives, GPU choices and prebuilt donors
- `data/retailer_url_matrix.json` — exact and retailer navigation URLs
- `data/observations/` — per-item price history, including API and manual screenshot observations
- `data/summary.json` — current build/storage summary
- `data/retailer_status.json` — aggregate retailer freshness/health
- `scripts/check_prices.py` — SerpApi Google Shopping collector
- `scripts/build_summary.py` — summary generation
- `scripts/build_retailer_status.py` — seven-day freshness and missing-result flags
- `.github/workflows/price-check.yml` — scheduled/manual SerpApi checks
- `icons/`, `manifest.webmanifest`, `sw.js` — PWA assets

## Current build targets

- Core/server-side target budget: **$2,400**
- Protected storage target: **4 TB usable**
- Track both **2×4 TB mirrored** and **4×2 TB RAID10-style** layouts
- Minimum **4 NVMe/drive positions**
- Baseline CPU: **AMD Ryzen 9 9950X**
- Baseline motherboard: **ASUS ProArt X870E-CREATOR WIFI**
- RAM target: **128 GB DDR5**, with 96 GB and 64 GB alternatives
- GPU choices are tracked separately from the core budget
- Prebuilt systems are tracked as donor candidates

## Enabling the API

Create a repository Actions secret named exactly:

`SERPAPI_API_KEY`

Then open **Actions → SerpApi Price Check → Run workflow**. The workflow also runs once daily. Do not put the API key in `index.html`, a JSON file, browser storage, an issue, or a commit.
