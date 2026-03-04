"""
debug_quote.py — Inspect NVDA quote page news link structure
"""
import os
os.environ["CURL_CA_BUNDLE"] = ""

from scrapling.fetchers import Fetcher

page = Fetcher.get(
    "https://finviz.com/quote.ashx?t=NVDA&ty=c&p=d&b=1",
    impersonate="chrome", verify=False, timeout=20
)

print("── a.tab-link-news elements ─────────────────────────────────")
links = page.css("a.tab-link-news")
print(f"  Total found: {len(links)}\n")

for i, a in enumerate(links[:12]):
    print(f"  [{i:02d}] text : {(a.text or '').strip()[:70]}")
    print(f"       href : {a.attrib.get('href','')[:120]}")
    print()
