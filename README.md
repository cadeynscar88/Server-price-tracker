# Private Server Price Tracker

This repository hosts the iPhone-first GitHub Pages tracker for the Frieren gaming-PC/private-server hybrid build.

## Architecture

- The browser/PWA is **read-only with respect to GitHub**. It never stores a GitHub PAT or the SerpApi key.
- Automated price discovery uses **SerpApi Google Shopping** from GitHub Actions.
- `SERPAPI_API_KEY` exists only as a GitHub Actions Secret.
- One Google Shopping search can return offers from multiple retailers for the same item.
- The scheduled collector currently runs **twice per week, Tuesdays and Fridays**, rotating tracked products within the configured quota budget.
- Separate ChatGPT deal-watch automation may run more frequently; that is independent of the GitHub SerpApi schedule.
- If a retailer is absent from the latest automated result, the prior verified price is retained and freshness is downgraded rather than guessed.

## Freshness colors

- **Green** — verified retailer price is 7 days old or newer and the latest applicable check returned the retailer.
- **Yellow** — last verified price is more than 7 days old.
- **Red** — latest check did not return the retailer, or the API check failed.
- **Gray** — retailer/item combination has not produced a verified observation yet.

## Screenshot correction workflow

If an automated price is missing or stale:

1. Open the tracker on iPhone.
2. Tap the retailer under the item.
3. Take a screenshot clearly showing retailer, exact item/model and price.
4. Send the screenshot in the ChatGPT project conversation.
5. After validation, add it to `data/observations/<item>.json` as a verified `manual_screenshot` observation.

This preserves the security model: the PWA itself has no credential capable of writing to GitHub.

## Repository layout

- `index.html` — GitHub Pages app and retailer/freshness display
- `data/config.json` — current build state, thresholds and architecture
- `data/products.json` — tracked components and alternatives
- `data/reference_prices.json` — purchased/manual/planning fallback references
- `data/historical_baselines.json` — explicitly historical pricing context
- `data/manual_price_crossover.json` — manually reviewed observations
- `data/observations/` — per-item current/API/manual history
- `data/summary.json` — current displayed build summary
- `data/retailer_status.json` — aggregate retailer freshness/health
- `scripts/check_prices.py` — SerpApi collector
- `scripts/build_summary.py` — summary generation
- `scripts/build_retailer_status.py` — freshness/missing-result flags
- `scripts/validate_tracker.py` — preflight consistency checks
- `.github/workflows/price-check.yml` / related workflow files — scheduled/manual checks

## Current build state — Sep 4 2026

Confirmed or ordered:

- AMD Ryzen 9 9950X3D
- ASRock X870E Taichi White
- MSI GeForce RTX 5070 Ti Frieren Edition 16GB (**Frieren is only the GPU nickname; the PC is not Frieren-themed**)
- Lian Li O11 Dynamic EVO RGB White
- Lexar NM790 4TB TLC Gen4 NVMe
- ASRock Phantom Gaming PG-1600G 1600W, ordered/backordered

Overall aesthetic: **white / black / champagne-gold**. Frieren's factory anime artwork is being covered by a custom marble backplate and should not drive the build design.

## Current RAM target

Primary exact kit:

**G.Skill Trident Z5 Royal Neo Silver 96GB (2x48GB) DDR5-6000 CL28**  
MPN: `F5-6000J2836F48GX2-TR5NS`

- AMD EXPO
- CL28-36-36-96
- 1.35V
- 2-DIMM arrangement preferred

Sep 4 current observations:
- Amazon screenshot: **$1,959.99**
- Newegg screenshot / web revalidation: **$2,099.99**

Tracker thresholds:
- <= $1,600: investigate
- $1,400–$1,500: strong BUY territory
- <= $1,300: exceptional / BUY NOW territory after live verification

Historical exact-SKU context is stored in `data/historical_baselines.json`, including the Pangoly tracked low, average and 2026 price changes.

64GB is now fallback only; 32GB is no longer a priority.

## Frieren return-window / RTX 4090 target

Until the original receipt date is verified, the tracker uses **Sep 28 2026 as the safe internal Frieren decision date**.

Default: keep the RTX 5070 Ti unless a compelling, healthy, protected and waterblock-compatible RTX 4090 appears.

Thresholds:
- <= $1,950: exceptional / BUY NOW after verification
- $1,950–$2,100: BUY territory
- $2,100–$2,200: conditional for unusually strong examples
- > $2,200: keep Frieren / WAIT

Current and historical RTX 4090 market references are stored in `data/historical_baselines.json` and `data/observations/gpu-4090.json`.

## Cooling / fans

Preferred CPU AIO: **Lian Li HydroShift II OLED Curved 360 P28 White**.
- Below $270: strong
- <= $250: exceptional

Fans: six white 120mm reverse-blade intake fans, preferably Lian Li UNI FAN TL Reverse White if price is sensible.

## Storage

- Existing Lexar NM790 4TB = persistent server data.
- Continue tracking an exact second NM790 4TB for the future mirror.
- Separate ~1TB OS/apps NVMe is recommended; prefer a strong Black Friday storage deal.
- Windows 11 Pro bare-metal first remains the current OS direction.

## PSU

Current PSU target is resolved:

**ASRock Phantom Gaming PG-1600G 1600W** — ordered from Newegg for **$199.99**, currently backordered.

Key specs: ATX 3.1, PCIe 5.1, fully modular, dual native 12V-2x6, 10-year warranty.

The old Lian Li RS1200 target is retired from active search.

## Future Heavy AI GPU

Heavy is intentionally **not committed yet** and is expected roughly 1–2 years out. The tracker continues to watch:

- RTX PRO 5000 Blackwell 48GB ECC
- used RTX A6000 48GB ECC
- RTX 5090 32GB
- exceptional RTX PRO 6000 Blackwell 96GB deals

The current gaming/Light GPU should not be overbuilt solely for AI because the future Heavy GPU will handle the serious high-VRAM role.

## Tracker trust rules

- Never fabricate a price.
- Search snippets and price trackers are leads, not live proof.
- User screenshots can be treated as verified manual observations when retailer, exact item and price are visible.
- Historical pricing is explicitly labeled and cannot masquerade as current live availability.
- A BUY/BUY NOW recommendation requires exact SKU/model, live price, seller, condition, warranty/returns, shipping/local availability and compatibility to be checked.
- Exact GPU waterblock compatibility is PCB-specific and must be verified before purchase.

## Enabling the API

Create a repository Actions secret named exactly:

`SERPAPI_API_KEY`

Then open **Actions → SerpApi Price Check → Run workflow** for an immediate manual check. Do not put the API key in `index.html`, a JSON file, browser storage, an issue, or a commit.
