"""
quote.py — Finviz Quote Page Scraper (parallel fetch via FetcherSession)

Scrapling features used:
  ✅ FetcherSession(impersonate="chrome") — shared session, parallel async requests
  ✅ asyncio.gather()                     — all quote pages fetched simultaneously
  ✅ css("a.tab-link-news")               — confirmed selector (DevTools verified)
  ✅ find_by_text() + .next               — locate fundamental metric values
  ✅ get_all_text()                       — full text extraction
  ✅ .attrib                              — href access
  ✅ .parent DOM navigation               — walk a → td → tr to get date
"""

import os
import asyncio
os.environ["CURL_CA_BUNDLE"] = ""

from scrapling.fetchers import FetcherSession

QUOTE_BASE = "https://finviz.com/quote.ashx?t={ticker}&ty=c&p=d&b=1"

FUNDAMENTAL_KEYS = [
    "P/E", "EPS (ttm)", "EPS next Y", "ROE", "ROI",
    "Short Float", "Analyst Recom.", "Target Price",
    "52W High", "52W Low", "Beta",
]

STEALTHY_DOMAINS = [
    "marketwatch.com", "wsj.com", "bloomberg.com",
    "ft.com", "thestreet.com", "investorsbusinessdaily.com",
]

# Max concurrent requests — be polite to Finviz
BATCH_SIZE = 5


def _safe_text(el) -> str:
    if el is None:
        return ""
    try:
        t = el.get_all_text(strip=True) if hasattr(el, 'get_all_text') else (el.text or "")
        return (t or "").strip()
    except Exception:
        return ""


def _find_metric(page, label: str) -> str:
    """find_by_text() + .next DOM navigation to extract metric value."""
    try:
        label_el = page.find_by_text(label, first_match=True)
        if label_el:
            val_el = label_el.next
            if val_el:
                return _safe_text(val_el)
    except Exception:
        pass
    return ""


async def _fetch_one_quote(session: FetcherSession, ticker: str) -> dict:
    """Async fetch + parse one quote page."""
    url = QUOTE_BASE.format(ticker=ticker)

    try:
        # ✅ FetcherSession async get — reuses browser session
        page = await session.get(url, timeout=20)
    except Exception as e:
        print(f"  ⚠️  {ticker}: fetch failed — {e}")
        return {"ticker": ticker, "fundamentals": {}, "articles": []}

    # ── Fundamentals ──────────────────────────────────────────────────────────
    fundamentals = {}
    for key in FUNDAMENTAL_KEYS:
        val = _find_metric(page, key)
        if val:
            fundamentals[key] = val

    # ── Article links via confirmed a.tab-link-news selector ──────────────────
    articles = []
    seen_urls = set()

    news_links = page.css("a.tab-link-news")

    for a in news_links:
        headline = (a.text or "").strip()
        href     = a.attrib.get("href", "").strip()

        # Skip relative URLs (no domain) — curl can't fetch them
        if not headline or not href or href in seen_urls or len(headline) < 10:
            continue
        if not href.startswith("http"):
            continue

        seen_urls.add(href)

        # Classify domain for article.py to choose right fetcher
        fetcher_type = "stealthy" if any(d in href for d in STEALTHY_DOMAINS) else "plain"

        # Date from parent row
        date = ""
        try:
            row  = a.parent.parent
            tds  = row.css("td")
            if tds:
                date = _safe_text(tds[0])
        except Exception:
            pass

        articles.append({
            "headline": headline,
            "url":      href,
            "date":     date,
            "fetcher":  fetcher_type,
        })

        if len(articles) >= 10:
            break

    print(f"  ✅ {ticker:<6} {len(fundamentals)} metrics | "
          f"{len(articles)} article links | "
          f"plain={sum(1 for a in articles if a['fetcher']=='plain')} "
          f"stealthy={sum(1 for a in articles if a['fetcher']=='stealthy')}")

    return {"ticker": ticker, "fundamentals": fundamentals, "articles": articles}


async def _fetch_quotes_parallel(tickers: list[str]) -> list[dict]:
    """
    Fetch all quote pages in parallel batches using FetcherSession.

    Batching (BATCH_SIZE=5) prevents hammering Finviz with 60 simultaneous
    requests — still much faster than sequential, but polite.
    """
    all_results = []

    async with FetcherSession(
        impersonate = "chrome",
        retries     = 2,
    ) as session:
        # Process in batches of BATCH_SIZE
        for i in range(0, len(tickers), BATCH_SIZE):
            batch = tickers[i:i + BATCH_SIZE]
            print(f"\n  🚀 Batch {i//BATCH_SIZE + 1}: "
                  f"fetching {batch} in parallel...")

            # ✅ asyncio.gather() — all tickers in batch fetched simultaneously
            batch_results = await asyncio.gather(*[
                _fetch_one_quote(session, ticker)
                for ticker in batch
            ])

            all_results.extend(batch_results)

            # Small delay between batches — polite to Finviz
            if i + BATCH_SIZE < len(tickers):
                await asyncio.sleep(2.0)

    return all_results


def scrape_quotes(tickers: list[str], delay: float = 2.0) -> list[dict]:
    """
    Public entry point — parallel quote page fetching.
    `delay` param kept for API compatibility but batching handles pacing.
    """
    print(f"  🌐 Fetching {len(tickers)} quote pages "
          f"in parallel batches of {BATCH_SIZE}...")
    return asyncio.run(_fetch_quotes_parallel(tickers))
