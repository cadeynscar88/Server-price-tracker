# Private Server Price Tracker — v1.1.3

This repository hosts the iPhone-first GitHub Pages tracker for the planned private server build.

## Architecture

- The browser/PWA is **read-only with respect to GitHub**. It does not store a GitHub PAT or retailer API secret.
- Automated public-page checks run in GitHub Actions using **No-API Price Check**.
- Blocked pages, missing structured prices, CAPTCHAs, and rate limits are treated as failures. The tracker does not invent or infer a price.
- Manual price observations can be exported separately from the browser.

## Repository layout

- `index.html` — GitHub Pages app
- `data/config.json` — budget and storage-layout settings
- `data/products.json` — resolved components, alternatives, GPU choices, and prebuilt donor candidates
- `data/retailer_url_matrix.json` — exact product watch URLs plus navigation/search URLs
- `data/observations/` — per-item price history
- `data/summary.json` — current build/storage summary
- `scripts/check_prices.py` — no-API public-page collector
- `scripts/build_summary.py` — summary generation
- `scripts/build_retailer_status.py` — retailer status data
- `.github/workflows/price-check.yml` — scheduled/manual price checks
- `icons/`, `manifest.webmanifest`, `sw.js` — PWA assets

## Current build targets

- Core/server-side target budget: **$2,400**
- Protected storage target: **4 TB usable**
- Track both **2×4 TB mirrored** and **4×2 TB RAID10-style** storage layouts
- Minimum **4 NVMe/drive positions**
- Baseline CPU: **AMD Ryzen 9 9950X**
- Baseline motherboard: **ASUS ProArt X870E-CREATOR WIFI**
- RAM target: **128 GB DDR5**, with 96 GB and 64 GB staged alternatives tracked
- GPU choices are tracked separately from the core budget
- Prebuilt systems are tracked as donor candidates and must be checked for standard motherboard/PSU/case/RAM components before purchase

## Running a price check

Open **Actions → No-API Price Check → Run workflow**. After the workflow completes, refresh the GitHub Pages tracker.

The scheduled workflow also runs once daily. Search URLs are for navigation only; only supported exact product pages are used as automated price sources.
