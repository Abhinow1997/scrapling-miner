"""
finviz_main.py — Finviz Stock Intelligence Miner

Pipeline:
  1. Screener  → page 1 only → 20 stocks
  2. Quotes    → all 20 ticker pages in PARALLEL batches of 5
  3. Articles  → top 10 stocks only, sequential (news sites ban parallel)
  4. Analyze   → VADER on full article bodies (recency-weighted)
  5. Report    → Composite score → ranked watchlist → JSON outputs

Why parallel for screener + quotes but sequential for articles:
  - Finviz is a single domain — parallel is fine, session handles it cleanly
  - News sites (Yahoo, MarketWatch) → parallel = instant rate limit / ban

Run:
  python finviz_main.py
"""

from finviz_miner.screener import scrape_screener
from finviz_miner.quote    import scrape_quotes
from finviz_miner.article  import fetch_all_articles
from finviz_miner.analyzer import analyze_all
from finviz_miner.reporter import build_watchlist, save_reports, print_summary

# How many stocks to fetch full articles for (slow — keep at 10)
ARTICLE_FETCH_LIMIT = 10


def main():
    print("=" * 72)
    print("  📈  Finviz Stock Intelligence Miner — Scrapling")
    print("  3 pages | parallel fetch | full article sentiment")
    print("=" * 72)

    # ── Step 1: Screener (3 pages, parallel) ─────────────────────────────────
    print("\n📋 STEP 1: Scraping Finviz screener page 1 (top 20 stocks)...")
    stocks = scrape_screener()

    if not stocks:
        print("❌ No stocks found.")
        return

    print(f"\n   {len(stocks)} stocks found. Top 10:")
    print(f"   {'#':<3} {'Ticker':<7} {'Company':<28} {'MktCap':>10}  {'P/E':>6}  {'Chg%':>7}")
    print(f"   {'─'*3} {'─'*7} {'─'*28} {'─'*10}  {'─'*6}  {'─'*7}")
    for i, s in enumerate(stocks[:10], 1):
        print(f"   {i:<3} {s['ticker']:<7} {s['company'][:27]:<28} "
              f"{s['market_cap']:>10}  {s['pe']:>6}  {s['change_pct']:>7}")

    # ── Step 2: Quote pages (all stocks, parallel batches) ────────────────────
    all_tickers = [s["ticker"] for s in stocks]
    print(f"\n📰 STEP 2: Fetching quote pages for all {len(all_tickers)} stocks (parallel batches of 5)...")
    quote_results = scrape_quotes(all_tickers)

    # ── Step 3: Full articles (top 10 only, sequential) ───────────────────────
    top_quotes = quote_results[:ARTICLE_FETCH_LIMIT]
    print(f"\n🌐 STEP 3: Fetching full article bodies for top "
          f"{ARTICLE_FETCH_LIMIT} stocks (sequential — polite)...")
    print(f"   Fetcher        → Yahoo Finance, Reuters")
    print(f"   StealthyFetcher → MarketWatch, WSJ (Cloudflare)\n")

    enriched_top = fetch_all_articles(top_quotes, max_per_stock=10, delay=1.5)

    # Remaining stocks keep their quote data (no articles — just headline scoring)
    remaining = quote_results[ARTICLE_FETCH_LIMIT:]
    all_analyzed_input = enriched_top + remaining

    # ── Step 4: Sentiment analysis ────────────────────────────────────────────
    print(f"\n🔍 STEP 4: VADER sentiment analysis...")
    analyzed = analyze_all(all_analyzed_input)

    # ── Step 5: Build ranked watchlist ────────────────────────────────────────
    print(f"\n📊 STEP 5: Building ranked watchlist ({len(stocks)} stocks)...")
    watchlist = build_watchlist(stocks, analyzed)
    save_reports(watchlist)
    print_summary(watchlist)


if __name__ == "__main__":
    main()
