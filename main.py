"""
main.py — Review Mining Orchestrator

Pipeline:
  1. Spider crawls all pages → raw review dicts
  2. Analyzer scores each review with VADER sentiment
  3. Reporter aggregates stats & saves JSON report

Run:
  python main.py
"""

import asyncio
from review_miner.spider import ReviewSpider
from review_miner.analyzer import analyze_all
from review_miner.reporter import build_report, save_report, print_summary


async def collect_reviews() -> list:
    """
    Stream items from the Scrapling spider as they arrive.
    Returns a flat list of raw review dicts.
    """
    reviews = []
    spider = ReviewSpider()

    print("🕷️  Starting review scraper...")
    async for item in spider.stream():
        reviews.append(item)

    return reviews


def main():
    # ── Step 1: Scrape ───────────────────────────────────────────────
    raw_reviews = asyncio.run(collect_reviews())
    print(f"📦  Scraped {len(raw_reviews)} reviews\n")

    if not raw_reviews:
        print("❌ No reviews collected. Check spider output above.")
        return

    # ── Step 2: Analyze sentiment ────────────────────────────────────
    print("🔍  Running VADER sentiment analysis...")
    analyzed = analyze_all(raw_reviews)

    # ── Step 3: Build & save report ──────────────────────────────────
    report = build_report(analyzed)
    save_report(report, output_path="review_report.json")

    # ── Step 4: Print console summary ────────────────────────────────
    print_summary(report)


if __name__ == "__main__":
    main()
