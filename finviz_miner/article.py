"""
article.py — Full Article Body Fetcher

This is where Scrapling's fetcher tiers are properly showcased:

  Fetcher        → Yahoo Finance, Reuters, Benzinga (no Cloudflare)
  StealthyFetcher→ MarketWatch, WSJ, TheStreet (Cloudflare protected)

For each article URL we:
  1. Choose the right fetcher based on domain
  2. Fetch the full page
  3. Extract article body text using common content selectors
  4. Return clean text for VADER analysis

Article body selectors tried (in order):
  - <article>               — semantic HTML5 article tag
  - div.caas-body           — Yahoo Finance
  - div.article__body       — MarketWatch
  - div.article-body        — Reuters, Benzinga
  - div.body-copy           — GuruFocus
  - div[class*="article"]   — generic fallback
  - all <p> tags            — last resort

Scrapling features showcased:
  ✅ Fetcher         — fast plain HTTP for unprotected news sites
  ✅ StealthyFetcher — Camoufox-based stealth for Cloudflare sites
  ✅ css()           — multi-selector article body extraction
  ✅ get_all_text()  — clean text extraction stripping all HTML
  ✅ find_by_text()  — locate article content anchored on known text
"""

import os
import time
os.environ["CURL_CA_BUNDLE"] = ""

from scrapling.fetchers import Fetcher, StealthyFetcher

# URL patterns that never fully load — skip before attempting fetch
SKIP_URL_PATTERNS = [
    "livecoverage", "live-blog", "live-updates",
    "live-markets", "liveblog", "/live/",
]

# Ordered list of CSS selectors to try for article body
ARTICLE_BODY_SELECTORS = [
    "article",
    "div.caas-body",           # Yahoo Finance
    "div.article__body",       # MarketWatch
    "div.article-body",        # Reuters, Benzinga
    "div.body-copy",           # GuruFocus
    "div.article-content",     # generic
    "div[class*='article-body']",
    "div[class*='story-body']",
    "div.content-body",
    "main",                    # broad fallback
]

MIN_ARTICLE_LENGTH = 150   # chars — anything shorter is likely a nav/ad element
MAX_ARTICLE_CHARS  = 3000  # cap text sent to VADER (saves processing time)


def _extract_body(page) -> str:
    """
    Try multiple selectors to extract article body text.
    Returns the longest clean text found.
    """
    candidates = []

    for selector in ARTICLE_BODY_SELECTORS:
        try:
            els = page.css(selector)
            if not els:
                continue
            # Take the longest text match (avoids nav snippets)
            for el in els:
                text = el.get_all_text(strip=True) if hasattr(el, 'get_all_text') \
                       else (el.text or "")
                text = (text or "").strip()
                if len(text) >= MIN_ARTICLE_LENGTH:
                    candidates.append(text)
        except Exception:
            continue

    if candidates:
        # Return the longest candidate (most likely the full article)
        return sorted(candidates, key=len, reverse=True)[0][:MAX_ARTICLE_CHARS]

    # Last resort: concatenate all <p> tags
    try:
        paras = page.css("p")
        text  = " ".join(
            (p.get_all_text(strip=True) or p.text or "")
            for p in paras
        ).strip()
        if len(text) >= MIN_ARTICLE_LENGTH:
            return text[:MAX_ARTICLE_CHARS]
    except Exception:
        pass

    return ""


def fetch_article(article: dict, delay: float = 1.5) -> dict:
    """
    Fetch a single article and extract its body text.

    Chooses fetcher based on domain classification from quote.py:
      "plain"   → Fetcher (fast, for Yahoo Finance etc.)
      "stealthy" → StealthyFetcher (for Cloudflare-protected sites)

    Returns article dict enriched with 'body' field.
    """
    url        = article.get("url", "")
    fetcher_type = article.get("fetcher", "plain")
    headline   = article.get("headline", "")[:60]

    if not url:
        return {**article, "body": "", "fetch_status": "no_url"}

    # Skip live-blog / live-coverage URLs — they never finish loading
    if any(pat in url.lower() for pat in SKIP_URL_PATTERNS):
        print(f"       ⏭️  [{fetcher_type:7s}] Skipping live URL: {headline}...")
        return {**article, "body": "", "fetch_status": "skipped_live"}

    print(f"       📰 [{fetcher_type:7s}] {headline}...")

    try:
        if fetcher_type == "stealthy":
            # ✅ StealthyFetcher — Camoufox-based, bypasses Cloudflare
            # timeout is in ms for Playwright — 30000ms = 30 seconds
            page = StealthyFetcher.fetch(
                url,
                headless          = True,
                network_idle      = True,
                disable_verify_ssl = True,
                timeout           = 30000,
            )
        else:
            # ✅ Fetcher — fast plain HTTP for unprotected sites
            page = Fetcher.get(
                url,
                impersonate = "chrome",
                verify      = False,
                timeout     = 15,
            )

        body = _extract_body(page)

        if body:
            print(f"               ✅ {len(body)} chars extracted")
        else:
            print(f"               ⚠️  No body text found")

        time.sleep(delay)
        return {**article, "body": body, "fetch_status": "ok"}

    except Exception as e:
        print(f"               ❌ Failed: {str(e)[:60]}")
        # Fall back to headline only for sentiment
        return {**article, "body": "", "fetch_status": f"error: {str(e)[:40]}"}


def fetch_articles_for_stock(
    ticker:   str,
    articles: list[dict],
    max_articles: int = 10,
    delay:    float   = 1.5,
) -> list[dict]:
    """
    Fetch full article bodies for one stock's news links.
    Caps at max_articles to be polite to news sites.
    """
    print(f"\n  🗞️  Fetching articles for {ticker} "
          f"({min(len(articles), max_articles)} articles)...")

    fetched = []
    for article in articles[:max_articles]:
        result = fetch_article(article, delay=delay)
        fetched.append(result)

    successful = sum(1 for a in fetched if a.get("body"))
    print(f"  ✅ {ticker}: {successful}/{len(fetched)} articles fetched successfully")
    return fetched


def fetch_all_articles(
    quote_results: list[dict],
    max_per_stock: int   = 10,
    delay:         float = 1.5,
) -> list[dict]:
    """
    Fetch articles for all stocks.
    Returns enriched quote_results with 'articles' containing full body text.
    """
    enriched = []
    for quote in quote_results:
        ticker   = quote.get("ticker", "?")
        articles = quote.get("articles", [])

        fetched_articles = fetch_articles_for_stock(
            ticker, articles,
            max_articles = max_per_stock,
            delay        = delay,
        )

        enriched.append({
            **quote,
            "articles": fetched_articles,
        })

    return enriched
