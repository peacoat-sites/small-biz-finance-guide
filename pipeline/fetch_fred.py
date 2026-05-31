#!/usr/bin/env python3
"""Fetch interest-rate series from FRED (Federal Reserve) -> data/rates.json.
Keyless: uses the public fredgraph.csv download endpoint.
Per-site config lives in pipeline/fred_series.json so each site shows the rates it cares about.
Runs in GitHub Actions (unrestricted network).
"""
import urllib.request, json, os, sys, io, csv

CONFIG = os.environ.get("FRED_CONFIG", "pipeline/fred_series.json")
DEST = sys.argv[1] if len(sys.argv) > 1 else "data/rates.json"
CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"

def latest_two(series_id):
    url = CSV_URL.format(id=series_id)
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "rates-data/1.0"}), timeout=40).read().decode("utf-8")
    rows = list(csv.reader(io.StringIO(raw)))
    # rows[0] is header (DATE/observation_date, <id>); collect valid numeric rows
    vals = []
    for r in rows[1:]:
        if len(r) < 2:
            continue
        date, v = r[0].strip(), r[1].strip()
        if v in (".", "", "NA"):
            continue
        try:
            vals.append((date, float(v)))
        except ValueError:
            continue
    if not vals:
        return None
    latest = vals[-1]
    prior = vals[-2] if len(vals) > 1 else None
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
        out.append({
            "label": s["label"],
            "value": round(lv, 2),
            "unit": s.get("unit", "%"),
            "as_of": ld,
            "change": change,
        })
        print(f"  {s['label']}: {lv}% (as of {ld}, {'+' if change>=0 else ''}{change})")
    except Exception as e:
        print(f"  ERROR {s['id']}: {e}", file=sys.stderr)

result = {
    "title": cfg.get("title", "Current Rates"),
    "source": "Federal Reserve Economic Data (FRED), St. Louis Fed",
    "updated": out[0]["as_of"] if out else None,
    "rates": out,
}
os.makedirs(os.path.dirname(DEST), exist_ok=True)
with open(DEST, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)
print(f"\nWrote {len(out)} rates to {DEST}")
