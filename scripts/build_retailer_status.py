#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
statuses=json.loads((DATA/"retailer_status.json").read_text()) if (DATA/"retailer_status.json").exists() else {}
summary={
 "generated_at":datetime.now(timezone.utc).isoformat(),
 "retailers":statuses.get("retailers",[]),
 "freshness_policy":{
   "green":"successful verified price within 24 hours",
   "yellow":"last successful price older than 24 hours",
   "red":"check_failed / blocked / rate_limited",
   "gray":"manual-only or not configured"
 },
 "note":"A retailer failure never changes a product price and never creates an inferred price."
}
(DATA/"retailer_status.json").write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
