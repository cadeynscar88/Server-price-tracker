#!/usr/bin/env python3
"""Revalidate all stored SerpApi observations without contacting SerpApi."""
import json
from datetime import datetime, timezone
from pathlib import Path
import check_prices as cp

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
result=cp.revalidate_existing()
status={
  'revalidated_at':datetime.now(timezone.utc).isoformat(),
  'api_calls':0,
  'quota_consumed':0,
  **result,
  'validation_version':'2.7',
  'note':'Historical observations were reclassified locally. No SerpApi request was made.'
}
(DATA/'offline_revalidation_status.json').write_text(json.dumps(status,indent=2))
print(json.dumps(status,indent=2))
