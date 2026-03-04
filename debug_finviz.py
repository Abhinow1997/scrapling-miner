"""
debug_finviz.py — Inspect Finviz HTML structure
"""

import os
os.environ["CURL_CA_BUNDLE"] = ""

from scrapling.fetchers import Fetcher

URL = "https://finviz.com/screener.ashx?v=111&f=idx_sp500,sec_technology&o=-marketcap"

page = Fetcher.get(URL, impersonate="chrome", verify=False, timeout=20)

# 1. Raw HTML preview — use page.body (bytes) or page.html_content
raw = page.html_content if hasattr(page, 'html_content') else page.body.decode('utf-8', errors='ignore')
print("── RAW HTML (first 3000 chars) ──────────────────────────────")
print(raw[:3000])

print("\n── ALL <a> tags with href containing 'quote' ────────────────")
for a in page.css("a[href*='quote']")[:10]:
    print(f"  text={a.text!r:20}  href={a.attrib.get('href','')[:80]}")

print("\n── ALL <tr> count ───────────────────────────────────────────")
rows = page.css("tr")
print(f"  Total <tr> elements: {len(rows)}")

print("\n── Tables found ─────────────────────────────────────────────")
for i, t in enumerate(page.css("table")):
    tid  = t.attrib.get("id",    "no-id")
    tcls = t.attrib.get("class", "no-class")[:40]
    trows = t.css("tr")
    print(f"  table[{i:02d}]  rows={len(trows):3d}  id={tid!r}  class={tcls!r}")

print("\n── Selector child attributes ─────────────────────────────────")
# Check what methods individual elements have
sample_els = page.css("a[href*='quote']")
if sample_els:
    el = sample_els[0]
    el_attrs = [a for a in dir(el) if not a.startswith('_')]
    print("  " + ", ".join(el_attrs))
