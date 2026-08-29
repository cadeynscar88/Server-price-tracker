# Server Price Tracker — Canonical Component Search Manifest

This file is the human-readable recovery list for the tracker. If product data, search terms, or app state are ever lost, rebuild the tracked component list from this document.

Last architecture consolidation: 2026-08-28
Target Stage-1 budget: $2,400 all-in where practical.

## Stage 1 — actively searched / dynamically selected

### Fixed core
- CPU: AMD Ryzen 9 9950X
- Motherboard: ASUS ProArt X870E-CREATOR WIFI
- Case: Lian Li LANCOOL 217 Black

### RAM — dynamic
- 96GB DDR5 kit, 2x48GB — optimal/base target
- 128GB DDR5 kit, 2x64GB — upgrade/dream target
- 64GB DDR5 kit, 2x32GB — budget fallback
- Search both true ECC UDIMM and non-ECC where motherboard/CPU compatibility is verified.
- Prefer low-profile, stability-oriented kits. Favor 128GB when <=25% premium over comparable 96GB. Favor ECC when <=20% premium over comparable non-ECC.

### GPU / local AI — dynamic
- NVIDIA GeForce RTX 5070 Ti 16GB — budget/value
- NVIDIA RTX PRO 4000 Blackwell 24GB — preferred 24GB class reference
- NVIDIA GeForce RTX 5090 32GB — optimal class when price is sane
- NVIDIA RTX PRO 4500 Blackwell 32GB — workstation alternative; deal-dependent
- 48GB+ NVIDIA GPU — dream/deal-only
- Two 16GB NVIDIA GPUs — allowed only when exact physical fit, PCIe lanes, PSU cabling, UPS load, thermals and total-system economics pass.
- Hard GPU price ceiling: $3,000 unless manually overridden.

### Primary NVMe — 4TB candidates, buy two matching drives for preferred mirror
- Lexar NM790 4TB
- WD_BLACK SN850X 4TB
- Kingston KC3000 4TB
- Crucial T500 4TB
- Samsung 990 PRO 4TB — deal-only premium
- TLC required for primary storage.

### Primary NVMe — 2TB candidates, buy four matching drives only when economics justify it
- Lexar NM790 2TB
- WD_BLACK SN850X 2TB
- Kingston KC3000 2TB
- Crucial T500 2TB
- Samsung 990 PRO 2TB — deal-only premium
- TLC required.
- 2x4TB remains preferred. Recommend 4x2TB only when it saves about $200 or more; require about $250 savings when a second GPU is actually selected.

### Boot SSD — SATA only
- Samsung 870 EVO 500GB
- Crucial MX500 500GB
- Kingston KC600 512GB
- 500/512GB target; 250GB allowed if substantially cheaper; 1TB allowed if within roughly $10–15 of comparable 500GB.
- Do not use an M.2 boot SSD. All four motherboard M.2 positions are reserved for possible primary data storage.

### CPU cooler — dynamic
- Noctua NH-D15 G2 — premium/reliability reference
- Thermalright Phantom Spirit 120 EVO — value reference
- Favor Noctua when premium is roughly $60 or less; otherwise Thermalright can win.
- Final selection must pass RAM-height clearance in LANCOOL 217.

### PSU — dynamic and GPU-dependent
1000W baseline candidates:
- Corsair RM1000x ATX 3.1
- MSI MAG A1000GL PCIE5 / current ATX 3.1 revision
1200W upgrade candidates:
- Seasonic VERTEX GX-1200 ATX 3.1
- Equivalent high-quality 1200W ATX 3.1 units may be approved after exact connector/fit review.
Requirements: fully modular, reputable platform, native 12V-2x6 when selected GPU requires it, correct independent cabling for every GPU. Favor 1200W when premium is <=$75 or required by selected GPU configuration.

### UPS — dynamic and measured-load-dependent
- CyberPower CP1500PFCLCD — 1500VA / 1000W pure-sine baseline reference
- Higher-output pure-sine UPS only if final measured/calculated server load requires it.
- Target baseline purchase price: about $200–250.
- UPS purpose is graceful shutdown, not prolonged server runtime.
- Must support server-visible USB or network shutdown signaling and built-in surge protection.

### Offline Stage-1 backup
- One 2TB quality SSD, selected from the approved 2TB storage pool when practical.
- Removable/offline except during deliberate backup operations.
- May be repurposed into Stage-2 vault storage if health/endurance check passes.
- Health Check must flag insufficient backup capacity before protected data outgrows the device.

## Stage 1 — required but not price searched
- LANCOOL 217 factory fans: use included 2x170mm front, 2x120mm GPU/shroud and 1x140mm rear initially. Additional case fan cost = $0 unless testing/failure justifies replacement.
- SD/microSD/USB/USB-C/Ethernet dongle: already owned; dedicated UHS-II reader optional later.
- Optical drive: user-supplied / local purchase if needed; not worth tracker complexity.
- Integrated 10GbE: provided by ASUS ProArt X870E-CREATOR WIFI; do not price a separate NIC initially.
- Integrated USB4: provided by motherboard; do not price a separate USB4 card initially.

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
- Preferred initial 2x4TB mirror: M.2_1 + M.2_3.
- Keep M.2_2 empty when practical because it shares bandwidth with PCIEX16(G5)_2.
- M.2_4 remains free in the preferred 2x4TB layout.
- 4x2TB is valid and intentionally supported; it occupies all four M.2 slots and accepts the associated second-GPU lane tradeoff.

## Deferred until after initial server startup/hardening
- Remote backup vault computer + vault SSD
- Protectli/OPNsense firewall purchase
- Wi-Fi access point
These must not block Stage-1 tracker readiness or contaminate the Stage-1 build total.

## Tracker trust rules
- Never fabricate a price.
- Only exact/strong product matches may affect totals.
- Ambiguous results are manual_review and excluded from totals.
- Reject used, refurbished, renewed, pre-owned and open-box offers unless policy is deliberately changed.
- Prefer sold-by-retailer / reputable sellers for high-value components.
- Exact GPU dimensions, slot thickness, TGP and connectors must be checked before recommendation.
- Total-system economics matter: GPU choice can change PSU, UPS, cooling and lane requirements.
