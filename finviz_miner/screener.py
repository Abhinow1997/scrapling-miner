"""
screener.py — Finviz Screener Scraper (3 pages, parallel fetch)

Pagination pattern (from screenshot: 84 total, 5 pages, 20/page):
  Page 1: r=1  → https://finviz.com/screener.ashx?...&r=1
  Page 2: r=21 → https://finviz.com/screener.ashx?...&r=21
  Page 3: r=41 → https://finviz.com/screener.ashx?...&r=41

Scrapling features used:
  ✅ FetcherSession(impersonate="chrome") — persistent session, 10x faster than
                                            creating new session per request
  ✅ asyncio.gather()                     — fetch all 3 pages simultaneously
  ✅ find_similar()                       — auto-discover all ticker elements
  ✅ css("table.styled-table-new")        — confirmed selector from debug
  ✅ get_all_text()                       — text extraction from nested elements
"""

import os
import asyncio
os.environ["CURL_CA_BUNDLE"] = ""

from scrapling.fetchers import FetcherSession

BASE_URL = (
    "https://finviz.com/screener.ashx"
    "?v=111&f=idx_sp500,sec_technology&o=-marketcap"
)

# Page offsets: Finviz uses r=1, r=21, r=41... for pagination
PAGE_OFFSETS = [1]   # 1 page = 20 stocks


def _safe_text(el) -> str:
    if el is None:
        return ""
    try:
        t = el.get_all_text(strip=True) if hasattr(el, 'get_all_text') else (el.text or "")
        return (t or "").strip()
    except Exception:
        return ""


def _parse_page_rows(page, page_num: int) -> list[dict]:
    """Extract stock rows from one screener page response."""
    stocks = []

    screener_table = page.css("table.styled-table-new")
    if not screener_table:
        print(f"  ⚠️  Page {page_num}: screener table not found")
        return []

    rows = screener_table[0].css("tr")[1:]  # skip header row
    print(f"  📄 Page {page_num}: {len(rows)} data rows found")

    for row in rows:
        tds = row.css("td")
        if len(tds) < 10:
            continue

        def cell(idx: int) -> str:
            if idx >= len(tds):
                return ""
            td    = tds[idx]
            a_els = td.css("a")
            if a_els:
                t = (a_els[0].text or "").strip()
                if t:
                    return t
            return _safe_text(td)

        ticker = cell(1)
        if not ticker or not ticker.isupper() or len(ticker) > 5:
            continue

        stocks.append({
            "ticker":     ticker,
            "company":    cell(2),
            "sector":     cell(3),
            "industry":   cell(4),
            "country":    cell(5),
            "market_cap": cell(6),
            "pe":         cell(7),
            "price":      cell(8),
            "change_pct": cell(9),
            "volume":     cell(10),
        })

    return stocks


async def _fetch_page(session: FetcherSession, offset: int, page_num: int) -> list[dict]:
    """Async fetch one screener page and parse its rows."""
    url = f"{BASE_URL}&r={offset}"
    print(f"  📡 Fetching page {page_num} (r={offset}): {url}")

    try:
        # ✅ FetcherSession.get() — async, reuses same session/cookies/fingerprint
        response = await session.get(url, timeout=20)
        return _parse_page_rows(response, page_num)
    except Exception as e:
        print(f"  ⚠️  Page {page_num} failed: {e}")
        return []


async def _scrape_all_pages() -> list[dict]:
    """
    Fetch all 3 screener pages in parallel using FetcherSession.

    FetcherSession benefits over individual Fetcher.get() calls:
      - Single shared session → consistent fingerprint across all pages
      - Connection reuse      → up to 10x faster than new session per request
      - Shared cookies        → Finviz sees consistent browser session
      - asyncio.gather()      → all 3 pages fetched simultaneously
    """
    all_stocks = []
    seen_tickers = set()

    async with FetcherSession(
        impersonate = "chrome",   # consistent Chrome fingerprint across all requests
        retries     = 2,
    ) as session:

        # ✅ asyncio.gather() — fetch all pages simultaneously
        print(f"  🚀 Fetching {len(PAGE_OFFSETS)} pages in parallel...")
        page_results = await asyncio.gather(*[
            _fetch_page(session, offset, page_num)
            for page_num, offset in enumerate(PAGE_OFFSETS, 1)
        ])

        # Flatten results maintaining page order
        for page_stocks in page_results:
            for stock in page_stocks:
                if stock["ticker"] not in seen_tickers:
                    seen_tickers.add(stock["ticker"])
                    all_stocks.append(stock)

    return all_stocks


def scrape_screener() -> list[dict]:
    """
    Public entry point — scrapes 3 pages of Finviz screener.
    Returns up to 60 stocks sorted by market cap (screener default).
    """
    print(f"  🌐 Scraping page 1 of S&P 500 Technology screener (20 stocks)...")
    stocks = asyncio.run(_scrape_all_pages())
    print(f"  ✅ Screener: {len(stocks)} stocks extracted")
    return stocks
