#!/usr/bin/env python3
"""Fetch interest-rate series from FRED (Federal Reserve) -> data/rates.json.
Uses the FRED JSON API. Requires a free API key (FRED_API_KEY secret):
  Get one in ~30s at https://fredaccount.stlouisfed.org/apikeys
Per-site config lives in pipeline/fred_series.json so each site shows the rates it cares about.
"""
import urllib.request, json, os, sys

API_KEY = os.environ.get("FRED_API_KEY", "").strip()
CONFIG = os.environ.get("FRED_CONFIG", "pipeline/fred_series.json")
DEST = sys.argv[1] if len(sys.argv) > 1 else "data/rates.json"
URL = ("https://api.stlouisfed.org/fred/series/observations"
       "?series_id={id}&api_key={key}&file_type=json&sort_order=desc&limit=12")

if not API_KEY:
    print("FRED_API_KEY not set — skipping (free key: https://fredaccount.stlouisfed.org/apikeys)")
    sys.exit(0)   # exit clean so the scheduled workflow stays green until the key is added

def latest_two(series_id):
    url = URL.format(id=series_id, key=API_KEY)
    data = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "rates-data/1.0"}), timeout=30).read())
    obs = [o for o in data.get("observations", []) if o.get("value") not in (".", "", None)]
    if not obs:
        return None
    vals = [(o["date"], float(o["value"])) for o in obs]  # already desc (newest first)
    latest = vals[0]
    prior = vals[1] if len(vals) > 1 else None
    return latest, prior

with open(CONFIG, encoding="utf-8") as fh:
    cfg = json.load(fh)

out = []
for s in cfg["series"]:
    try:
        res = latest_two(s["id"])
        if not res:
            print(f"  {s['id']}: no data", file=sys.stderr); continue
        (ld, lv), prior = res
        change = round(lv - prior[1], 2) if prior else 0.0
        out.append({"label": s["label"], "value": round(lv, 2), "unit": s.get("unit", "%"),
                    "as_of": ld, "change": change})
        print(f"  {s['label']}: {lv}% (as of {ld}, {'+' if change>=0 else ''}{change})")
    except Exception as e:
        print(f"  ERROR {s['id']}: {e}", file=sys.stderr)

if not out:
    print("No rates fetched — leaving existing data/rates.json untouched"); sys.exit(0)

result = {"title": cfg.get("title", "Current Rates"),
          "source": "Federal Reserve Economic Data (FRED), St. Louis Fed",
          "updated": out[0]["as_of"], "rates": out}
os.makedirs(os.path.dirname(DEST), exist_ok=True)
with open(DEST, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)
print(f"\nWrote {len(out)} rates to {DEST}")
