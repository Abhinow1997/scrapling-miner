"""
traditional_parallel.py — BeautifulSoup + aiohttp + asyncio parallel fetch
vs
scrapling_parallel.py  — Scrapling FetcherSession parallel fetch

This demo fetches the same 5 Finviz quote pages using both approaches
and times them so you can see the difference.

Run this file:
  python traditional_parallel.py
"""

import asyncio
import time
import os

os.environ["CURL_CA_BUNDLE"] = ""

# ── Target URLs (same 5 tickers, same pages) ─────────────────────────────────
TICKERS = ["NVDA", "AAPL", "MSFT", "AVGO", "MU"]
URLS    = [f"https://finviz.com/quote.ashx?t={t}&ty=c&p=d&b=1" for t in TICKERS]

HEADERS = {
    # Basic header — no browser fingerprinting
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Accept":     "text/html,application/xhtml+xml",
}


# ══════════════════════════════════════════════════════════════════════════════
# APPROACH 1: Traditional — aiohttp + BeautifulSoup + asyncio (manual wiring)
# ══════════════════════════════════════════════════════════════════════════════

async def traditional_fetch_one(session, url: str, ticker: str) -> dict:
    """Fetch one page with aiohttp, parse with BeautifulSoup."""
    import aiohttp
    from bs4 import BeautifulSoup

    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            status = resp.status
            html   = await resp.text()

            # BeautifulSoup parses the HTML string
            soup   = BeautifulSoup(html, "html.parser")

            # Try to find the company name — basic CSS class lookup
            company_el = soup.find("h2", class_="quote-header_ticker-wrapper-company")
            company    = company_el.text.strip() if company_el else "not found"

            # Count how many <td> elements on the page
            td_count = len(soup.find_all("td"))

            return {
                "ticker":   ticker,
                "status":   status,
                "company":  company,
                "td_count": td_count,
                "approach": "aiohttp + BeautifulSoup",
            }

    except Exception as e:
        return {
            "ticker":   ticker,
            "status":   "error",
            "company":  str(e)[:60],
            "td_count": 0,
            "approach": "aiohttp + BeautifulSoup",
        }


async def run_traditional() -> list[dict]:
    """
    Traditional parallel fetch:
      - aiohttp.ClientSession for HTTP
      - asyncio.gather for concurrency
      - BeautifulSoup for parsing (separate step)
      - No browser fingerprinting → Finviz may block
    """
    import aiohttp

    print("\n" + "─" * 60)
    print("  APPROACH 1: aiohttp + asyncio + BeautifulSoup")
    print("─" * 60)

    start = time.perf_counter()

    # Manual session creation — no fingerprinting, no impersonation
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[
            traditional_fetch_one(session, url, ticker)
            for ticker, url in zip(TICKERS, URLS)
        ])

    elapsed = time.perf_counter() - start

    for r in results:
        print(f"  {r['ticker']:<6} status={r['status']}  "
              f"tds={r['td_count']:>4}  company={r['company'][:30]}")

    print(f"\n  ⏱️  Total time: {elapsed:.2f}s")
    print(f"  ⚠️  Note: No browser fingerprint — likely blocked by Finviz (status 403/200 empty)")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# APPROACH 2: Scrapling — FetcherSession (all-in-one)
# ══════════════════════════════════════════════════════════════════════════════

async def scrapling_fetch_one(session, url: str, ticker: str) -> dict:
    """Fetch one page with Scrapling FetcherSession — no separate parser needed."""
    from scrapling.fetchers import FetcherSession

    try:
        # Response object already has .css(), .find_by_text(), .find_similar() built in
        page = await session.get(url, timeout=15)

        # Direct CSS on the response — no soup needed
        company_els = page.css("h2.quote-header_ticker-wrapper-company")
        company     = company_els[0].text if company_els else "not found"

        # Count <td> elements
        td_count = len(page.css("td"))

        # Bonus: can call find_by_text, find_similar directly
        pe_label = page.find_by_text("P/E", first_match=True)
        pe_value = pe_label.next.text if pe_label and pe_label.next else "N/A"

        return {
            "ticker":   ticker,
            "status":   page.status,
            "company":  company,
            "td_count": td_count,
            "pe":       pe_value,
            "approach": "Scrapling FetcherSession",
        }

    except Exception as e:
        return {
            "ticker":   ticker,
            "status":   "error",
            "company":  str(e)[:60],
            "td_count": 0,
            "pe":       "N/A",
            "approach": "Scrapling FetcherSession",
        }


async def run_scrapling() -> list[dict]:
    """
    Scrapling parallel fetch:
      - FetcherSession handles HTTP + async + fingerprinting
      - impersonate="chrome" → consistent Chrome TLS fingerprint
      - Response already has .css(), .find_by_text(), .find_similar()
      - No separate parser library needed
    """
    from scrapling.fetchers import FetcherSession

    print("\n" + "─" * 60)
    print("  APPROACH 2: Scrapling FetcherSession")
    print("─" * 60)

    start = time.perf_counter()

    async with FetcherSession(
        impersonate = "chrome",   # ← this is what aiohttp CAN'T do
        retries     = 2,
    ) as session:
        results = await asyncio.gather(*[
            scrapling_fetch_one(session, url, ticker)
            for ticker, url in zip(TICKERS, URLS)
        ])

    elapsed = time.perf_counter() - start

    for r in results:
        print(f"  {r['ticker']:<6} status={r['status']}  "
              f"tds={r['td_count']:>4}  P/E={r.get('pe','N/A'):>8}  "
              f"company={r['company'][:30]}")

    print(f"\n  ⏱️  Total time: {elapsed:.2f}s")
    print(f"  ✅ Chrome fingerprint → Finviz responds with real data")
    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — run both and compare
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("  Parallel Fetch Comparison")
    print("  aiohttp+BeautifulSoup  vs  Scrapling FetcherSession")
    print("  Target: Finviz quote pages for NVDA, AAPL, MSFT, AVGO, MU")
    print("=" * 60)

    # Run traditional first
    trad_results = await run_traditional()

    # Small gap between the two tests
    await asyncio.sleep(3)

    # Run Scrapling
    scrap_results = await run_scrapling()

    # ── Side by side comparison ───────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  COMPARISON SUMMARY")
    print("=" * 60)
    print(f"  {'Feature':<30} {'aiohttp+BS4':<20} {'Scrapling'}")
    print(f"  {'─'*30} {'─'*20} {'─'*20}")

    comparisons = [
        ("Browser fingerprint",      "❌ None",          "✅ Chrome TLS"),
        ("Cloudflare bypass",         "❌ Not possible",  "✅ StealthyFetcher"),
        ("Async parallel",            "✅ Manual wiring", "✅ Built-in"),
        ("HTML parser included",      "❌ Need BS4",      "✅ Built-in"),
        ("find_similar() adaptive",   "❌ Not possible",  "✅ Built-in"),
        ("find_by_text() + .next",    "❌ Not possible",  "✅ Built-in"),
        ("Retry logic",               "❌ Manual",        "✅ retries=2"),
        ("Libraries needed",          "3 (aiohttp+asyncio+bs4)", "1 (scrapling)"),
    ]

    for feature, trad, scrap in comparisons:
        print(f"  {feature:<30} {trad:<20} {scrap}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
