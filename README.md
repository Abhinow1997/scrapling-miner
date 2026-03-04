# 🕷️ Finviz Stock Intelligence Miner — Scrapling Showcase

> A real-world financial data pipeline built to demonstrate **Scrapling's** web scraping capabilities across its full feature set — from browser fingerprinting to adaptive selectors to full article body extraction.

---

## 📁 Project Structure

```
scrapling/
├── finviz_main.py              ← Orchestrator — runs the full pipeline
├── finviz_miner/
│   ├── screener.py             ← Parallel screener table scraping
│   ├── quote.py                ← Parallel quote page + news link extraction
│   ├── article.py              ← Full article body fetching (Fetcher + StealthyFetcher)
│   ├── analyzer.py             ← VADER sentiment scoring (recency-weighted)
│   └── reporter.py             ← Markdown report generation
├── finviz_report.md            ← Full intelligence report (generated)
└── finviz_watchlist.md         ← Clean ranked watchlist table (generated)
```

---

## 🚀 How to Run

```powershell
# Install dependencies
pip install scrapling vaderSentiment httpx
scrapling install   # downloads browser binaries for StealthyFetcher

# Run the full pipeline
python finviz_main.py
```

---

## 🔬 Scrapling Features Used — Full Reference

### 1. `Fetcher.get(impersonate="chrome")`
**File:** `screener.py`, `quote.py`

```python
from scrapling.fetchers import Fetcher

page = Fetcher.get(
    "https://finviz.com/screener.ashx?...",
    impersonate = "chrome",   # spoof Chrome TLS fingerprint
    verify      = False,      # Windows SSL fix
    timeout     = 20,
)
```

**What it does:**
Performs an HTTP GET request while spoofing a real Chrome browser's TLS fingerprint, HTTP/2 settings, and request headers. Finviz actively checks these signals to detect bots — `impersonate="chrome"` bypasses this check by making the request indistinguishable from a real browser.

**Why not plain `requests`:**
`requests` sends a Python `urllib3` TLS fingerprint which Finviz recognizes and blocks. `impersonate="chrome"` uses `curl-cffi` under the hood to replicate Chrome's exact TLS handshake.

---

### 2. `FetcherSession(impersonate="chrome")` + `asyncio.gather()`
**File:** `screener.py`, `quote.py`

```python
from scrapling.fetchers import FetcherSession

async with FetcherSession(impersonate="chrome", retries=2) as session:
    # Fetch all pages simultaneously — not one by one
    results = await asyncio.gather(
        session.get(url_page1),
        session.get(url_page2),
        session.get(url_page3),
    )
```

**What it does:**
`FetcherSession` maintains a persistent browser session across multiple async requests. Used with `asyncio.gather()` to fetch multiple pages simultaneously.

**Benefits over multiple `Fetcher.get()` calls:**

| Feature | `Fetcher.get()` | `FetcherSession` |
|---------|----------------|-----------------|
| Speed | New connection each time | Reuses HTTP/2 connection |
| Fingerprint | New fingerprint each time | Consistent across all requests |
| Cookies | Lost between requests | Shared automatically |
| Concurrent | No | Yes — `await session.get()` |

**In this project:**
- Screener: fetches page 1 (expandable to 3+ pages) in parallel
- Quotes: fetches all 20 ticker quote pages in batches of 5 simultaneously

---

### 3. `StealthyFetcher.fetch()`
**File:** `article.py`

```python
from scrapling.fetchers import StealthyFetcher

page = StealthyFetcher.fetch(
    "https://www.marketwatch.com/story/...",
    headless           = True,
    network_idle       = True,
    disable_verify_ssl = True,
)
```

**What it does:**
Launches a modified Firefox browser (via [Camoufox](https://camoufox.com/)) with fingerprint spoofing — fake screen resolution, OS, timezone, canvas fingerprint, and cursor movement humanization. Specifically designed to bypass Cloudflare Turnstile and similar bot detection systems.

**When it's used:**
News article URLs are classified by domain when scraped from Finviz:

```python
STEALTHY_DOMAINS = ["marketwatch.com", "wsj.com", "bloomberg.com", "thestreet.com"]

# quote.py classifies each article link:
fetcher_type = "stealthy" if any(d in href for d in STEALTHY_DOMAINS) else "plain"
```

`article.py` then routes accordingly:
- `"plain"` → `Fetcher.get()` — Yahoo Finance, Reuters, Benzinga
- `"stealthy"` → `StealthyFetcher.fetch()` — MarketWatch, WSJ, Bloomberg

---

### 4. `page.css()` — CSS Selector Extraction
**File:** `screener.py`, `quote.py`, `article.py`

```python
# Confirmed from DevTools screenshot — exact class name
news_links = page.css("a.tab-link-news")       # → 100 news links per stock

# Screener table — confirmed from debug_finviz.py output
table = page.css("table.styled-table-new")[0]  # → the results table

# Article body — tried in order until one returns content
body_el = page.css("div.caas-body")            # Yahoo Finance
body_el = page.css("article")                  # generic HTML5
body_el = page.css("div.article__body")        # MarketWatch
```

**Scrapling vs BeautifulSoup:**
Scrapling's CSS engine is benchmarked at up to **1,735× faster** than BeautifulSoup on large documents. It supports the same CSS3 selector syntax plus Scrapy-style extensions like `::text` and `::attr(href)`.

---

### 5. `find_similar()` — Structural Element Discovery
**File:** `screener.py`, `quote.py`

```python
# Find the first valid ticker link on the page
ticker_el = first <a> with uppercase 1-5 char text

# Auto-discover ALL structurally identical elements
all_tickers = ticker_el.find_similar()
# → ['NVDA', 'AAPL', 'MSFT', 'AVGO', 'MU', ...] (19 tickers found)
```

**How it works internally:**
`find_similar()` compares DOM structure using:
- Tag name and depth in the DOM tree
- Parent and grandparent tag names
- Sibling element count and structure
- Attribute patterns (not values)

It does **not** rely on class names or IDs — which means if Finviz renames `class="screener-ticker"` to `class="sc-ticker-v2"` tomorrow, your scraper still works.

**Traditional approach (fragile):**
```python
# Breaks the moment Finviz renames the class
soup.find_all("td", class_="screener-ticker-col")
```

**Scrapling approach (resilient):**
```python
# Works regardless of class names — anchors on structure
ticker_el.find_similar()
```

---

### 6. `find_by_text()` + `.next` DOM Navigation
**File:** `quote.py`

```python
# Locate a metric by its visible label text
label_el = page.find_by_text("P/E", first_match=True)

# Walk to the adjacent value cell
value_el  = label_el.next
value     = value_el.get_all_text(strip=True)
# → "37.57"
```

**What it does:**
`find_by_text()` searches all elements for one whose text content matches the given string. `.next` navigates to the immediately following sibling in the DOM.

**Why this is powerful for Finviz:**
Finviz's quote page has 60+ metric label/value pairs in a dense grid. Writing a CSS selector for every single metric would be brittle and verbose. `find_by_text()` anchors on the human-readable label — which never changes — and `.next` gets the value regardless of the surrounding HTML structure.

```
"P/E"  →  find_by_text("P/E")  →  .next  →  "37.57"
"Beta" →  find_by_text("Beta") →  .next  →  "1.54"
"ROE"  →  find_by_text("ROE")  →  .next  →  "123.4%"
```

---

### 7. `.parent` DOM Tree Traversal
**File:** `quote.py`

```python
# We have an <a> news link — we want the date from the same row
row  = a.parent.parent   # <a> → <td> → <tr>
tds  = row.css("td")
date = tds[0].get_all_text(strip=True)
```

**What it does:**
`.parent` walks up one level in the DOM tree. Chained twice to go from `<a>` → `<td>` → `<tr>`, then `.css("td")` gets all cells in that row.

---

### 8. `get_all_text(strip=True)`
**File:** used throughout all files

```python
text = element.get_all_text(strip=True)
```

**What it does:**
Extracts all text content from an element and all its descendants, concatenated and optionally stripped of whitespace. More thorough than `.text` which only gets direct text nodes.

**Why `.text` wasn't enough:**
Finviz renders some values inside nested `<span>` or `<b>` tags inside `<td>`. `.text` would miss these. `get_all_text()` traverses the full subtree.

---

### 9. `.attrib` — Attribute Access
**File:** `quote.py`

```python
href   = a.attrib.get("href", "")
# → "https://finance.yahoo.com/news/nvidia-stock-climbs-..."
```

**What it does:**
Returns a dictionary of all HTML attributes on the element. `.get()` with a default prevents `KeyError` on elements that don't have the attribute.

---

## 🏗️ Full Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     finviz_main.py                              │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────┐     FetcherSession + asyncio.gather()
│    screener.py      │ ──► Fetch page 1 in parallel
│                     │     css("table.styled-table-new")
│  20 stocks          │     find_similar() → all ticker elements
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     FetcherSession batches of 5
│     quote.py        │ ──► Fetch all 20 quote pages in parallel
│                     │     css("a.tab-link-news") → 10 URLs/stock
│  fundamentals +     │     find_by_text() + .next → metrics
│  article URLs       │     .parent → date extraction
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     Sequential (polite — news sites rate-limit)
│    article.py       │ ──► Fetcher → Yahoo Finance, Reuters
│                     │     StealthyFetcher → MarketWatch, WSJ
│  full article text  │     css("div.caas-body") → article body
│  (top 10 stocks)    │     get_all_text() → clean text
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    analyzer.py      │ ──► VADER compound score per article
│                     │     Recency weighting [1.5x, 1.5x, 1.0x...]
│  sentiment scores   │     Signal strength %
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    reporter.py      │ ──► Composite score (50% sentiment +
│                     │     30% momentum + 20% analyst)
│  finviz_report.md   │     Ranked watchlist → Markdown output
│  finviz_watchlist.md│
└─────────────────────┘
```

---

## 📊 Composite Scoring Formula

```
Composite Score = 0.50 × Sentiment + 0.30 × Momentum + 0.20 × Analyst

Where:
  Sentiment = VADER weighted avg (full article body, recency-weighted)
              normalized from (-1, +1) → (0, 1)

  Momentum  = Today's % price change
              normalized relative to group (best mover = 1.0, worst = 0.0)

  Analyst   = Finviz analyst consensus
              Strong Buy=1.0 | Buy=0.75 | Hold=0.5 | Sell=0.25
```

---

## 🔄 Fetcher Selection Logic

```
Article URL
    │
    ├── yahoo.com, reuters.com, benzinga.com, fool.com
    │       └── Fetcher.get(impersonate="chrome")
    │           Fast · No JS needed · No Cloudflare
    │
    └── marketwatch.com, wsj.com, bloomberg.com, thestreet.com
            └── StealthyFetcher.fetch(headless=True)
                Camoufox browser · Spoofs fingerprint
                Bypasses Cloudflare Turnstile
```

---

## ⚠️ Disclaimer

This project is built for **educational purposes** as part of the SpringBigData course.
It is not intended for commercial use or financial advice.
Always respect website Terms of Service and rate limits when scraping.

---

*Built with [Scrapling](https://github.com/D4Vinci/Scrapling) · VADER Sentiment · Python 3.12*
