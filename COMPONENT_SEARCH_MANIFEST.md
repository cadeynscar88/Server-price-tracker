# Server Price Tracker — Canonical Component Search Manifest

This file is the human-readable recovery list for the tracker. If product data, search terms, or app state are ever lost, rebuild the tracked component list from this document.

Last architecture consolidation: 2026-08-28
Tracker schema: v2.1
Target Stage-1 budget: $2,400 all-in where practical.

## Stage 1 — actively searched / dynamically selected

### Fixed core
- CPU: AMD Ryzen 9 9950X
- Motherboard: ASUS ProArt X870E-CREATOR WIFI
- Case: Lian Li LANCOOL 217 Black
- Boot SSD: one approved 500/512GB 2.5-inch SATA TLC SSD; never consume an M.2 slot for boot.

### RAM — dynamic
- 96GB DDR5 2x48GB non-ECC — optimal/base target
- 96GB DDR5 true ECC UDIMM 2x48GB — ECC branch
- 128GB DDR5 2x64GB non-ECC — upgrade target
- 128GB DDR5 true ECC UDIMM 2x64GB — ECC upgrade branch
- 64GB DDR5 2x32GB — budget fallback
- Prefer low-profile, stability-oriented kits. Favor 128GB when <=25% premium over comparable 96GB. Favor true ECC UDIMM when <=20% premium over comparable non-ECC. ECC and non-ECC are tracked as separate branches so the collector cannot silently discard the ECC premium.

### GPU / local AI — dynamic
- NVIDIA GeForce RTX 5070 Ti 16GB — budget/value
- NVIDIA RTX PRO 4000 Blackwell 24GB — preferred 24GB class reference
- NVIDIA GeForce RTX 5090 32GB — optimal class when price is sane
- NVIDIA RTX PRO 4500 Blackwell 32GB — workstation alternative
- Two RTX 5070 Ti 16GB cards — explicit scenario only when exact physical fit, PCIe lanes, PSU cabling, UPS load, thermals and total-system economics pass
- Hard GPU price ceiling: $3,000 unless manually overridden.

### Primary NVMe — approved TLC families
4TB pool, buy two matching drives for preferred mirror:
- Lexar NM790 4TB
- WD_BLACK SN850X 4TB
- Kingston KC3000 4TB
- Crucial T500 4TB
- Samsung 990 PRO 4TB — deal-only premium

2TB pool, buy four matching drives only when economics justify it:
- Lexar NM790 2TB
- WD_BLACK SN850X 2TB
- Kingston KC3000 2TB
- Crucial T500 2TB
- Samsung 990 PRO 2TB — deal-only premium

2x4TB remains preferred. Recommend 4x2TB only when it saves at least about $200; require about $250 savings when a second GPU is actually selected. TLC required.

### Boot SSD — SATA only
- Samsung 870 EVO 500GB
- Crucial MX500 500GB
- Kingston KC600 512GB
- 500/512GB target; 250GB allowed if substantially cheaper; 1TB allowed if within roughly $10–15 of comparable 500GB.
- Do not use an M.2 boot SSD. All four motherboard M.2 positions remain available for primary data storage.

### CPU cooler — dynamic
- Noctua NH-D15 G2 — premium/reliability reference
- Thermalright Phantom Spirit 120 EVO — value reference
- Favor Noctua when premium is roughly $60 or less; otherwise Thermalright can win.
- Final selection must pass RAM-height clearance in LANCOOL 217.

### PSU — dynamic and GPU-dependent
1000W baseline:
- Corsair RM1000x ATX 3.1
- MSI MAG A1000GL PCIE5 / current ATX 3.1 revision
1200W upgrade:
- Seasonic VERTEX GX-1200 ATX 3.1
Requirements: reputable platform, fully modular, native 12V-2x6 when selected GPU requires it, correct independent cabling for every GPU. Favor 1200W when premium is <=$75 or required by selected GPU configuration.

### UPS — dynamic and calculated-load-dependent
- CyberPower CP1500PFCLCD — 1500VA / 1000W pure-sine baseline
- CyberPower PR1500LCD — 1500VA / 1500W higher-output fallback
- Apply 20% output headroom to estimated server peak. If the baseline 1000W UPS cannot satisfy that margin, the 1500W branch is selected.
- UPS purpose is graceful shutdown, not prolonged runtime.
- Must support server-visible shutdown signaling and built-in surge protection.

### Offline Stage-1 backup
- One approved 2TB TLC SSD, derived from the same approved 2TB pool instead of spending another SerpApi search.
- Removable/offline except during deliberate backup operations.
- May be repurposed into Stage-2 vault storage if health/endurance check passes.
- Health Check must flag insufficient backup capacity before protected data outgrows the device.

## Full-system scenarios evaluated by the tracker
- 1x RTX 5070 Ti 16GB
- 2x RTX 5070 Ti 16GB
- 1x RTX PRO 4000 Blackwell 24GB
- 1x RTX 5090 32GB
- 1x RTX PRO 4500 Blackwell 32GB

Each scenario dynamically selects RAM, cooler, storage layout, PSU and UPS before calculating its total. A component is not considered a deal if supporting hardware makes the full system a worse value.

## Stage 1 — required but not price searched
- LANCOOL 217 factory fans: use included 2x170mm front, 2x120mm GPU/shroud and 1x140mm rear initially. Additional case fan cost = $0 unless testing/failure justifies replacement.
- SD/microSD/USB/USB-C/Ethernet dongle: already owned; dedicated UHS-II reader optional later.
- Optical drive: user-supplied / local purchase if needed; not worth tracker complexity.
- Integrated 10GbE: provided by ASUS ProArt X870E-CREATOR WIFI.
- Integrated USB4: provided by motherboard.

## Security / production requirements
- Primary data encrypted at rest.
- Removable backup encrypted independently.
- Remote traffic encrypted in transit.
- Read-only operations do NOT require physical security key: browse, stream, download, search, AI analysis.
- Any operation that changes server data DOES require FIDO2/WebAuthn hardware-key authorization: upload, edit, overwrite, rename, move, delete, create/delete folders, server-stored metadata changes.
- Admin/security changes require hardware key plus stronger authentication.
- Normal write authorization must not permit deletion of protected snapshots/backups.
- Enroll two hardware security keys before production: primary + recovery.
- Keep separate break-glass encryption recovery material.

## Motherboard lane / storage sanity rule
- Preferred 2x4TB mirror: M.2_1 + M.2_3.
- Keep M.2_2 empty when practical because it shares bandwidth with PCIEX16(G5)_2.
- M.2_4 remains free in the preferred layout.
- 4x2TB is valid and intentionally supported; it occupies all four M.2 slots and accepts the associated second-GPU lane tradeoff.

## Deferred until after initial server startup/hardening
- Remote backup vault computer + vault SSD
- Protectli/OPNsense firewall purchase
- Wi-Fi access point
These must not block Stage-1 tracker readiness or contaminate Stage-1 build totals.

## Tracker trust and preflight rules
- Never fabricate a price.
- Only exact/strong product matches may affect totals.
- SerpApi observations count only when status=verified and match_status=strong.
- Ambiguous results are manual_review and excluded from totals.
- Reject used, refurbished, renewed, pre-owned, open-box and obvious accessory/system-result contamination.
- ECC RAM results must explicitly confirm ECC UDIMM/unbuffered and are kept separate from non-ECC branches.
- Derived backup pricing consumes no API search quota.
- Before any SerpApi call, scripts/validate_tracker.py must pass. It checks product IDs, dynamic-group references, storage capacity, four-M.2 architecture, SATA boot policy, FIDO2 write policy and the API run cap.
- Exact GPU dimensions, slot thickness, TGP and connectors still require final exact-SKU sanity review before purchase.
