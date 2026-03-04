"""
reporter.py — Stock Intelligence Report Generator (.md output)

Composite Score:
  50% News Sentiment  (from full article body where available)
  30% Price Momentum  (today's % change, normalized across group)
  20% Analyst Rating  (Strong Buy=1.0 → Strong Sell=0.0)

Outputs:
  finviz_report.md   — full markdown report (human readable)
  finviz_watchlist.md — clean ranked watchlist table
"""

from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

ANALYST_MAP = {
    "strong buy":  1.00, "buy": 0.75, "hold": 0.50,
    "sell": 0.25, "strong sell": 0.00,
}


def _parse_change(s: str) -> float:
    try:
        return float(s.replace("%", "").replace("+", "").strip())
    except Exception:
        return 0.0


def _analyst_score(rating: str) -> float:
    r = (rating or "").lower().strip()
    for key, val in ANALYST_MAP.items():
        if key in r:
            return val
    return 0.5


def _normalize(val: float, mn: float, mx: float) -> float:
    if mx == mn:
        return 0.5
    return max(0.0, min(1.0, (val - mn) / (mx - mn)))


def build_watchlist(
    screener_stocks: List[Dict],
    analyzed_quotes: List[Dict],
) -> List[Dict]:
    quote_map = {q["ticker"]: q for q in analyzed_quotes}
    changes   = [
        _parse_change(s.get("change_pct", "0"))
        for s in screener_stocks if s.get("ticker") in quote_map
    ]
    min_chg = min(changes) if changes else -5.0
    max_chg = max(changes) if changes else  5.0

    watchlist = []
    for stock in screener_stocks:
        ticker = stock.get("ticker", "")
        quote  = quote_map.get(ticker, {})
        if not quote:
            continue

        sentiment_norm = (quote.get("sentiment_score", 0.0) + 1.0) / 2.0
        momentum_norm  = _normalize(_parse_change(stock.get("change_pct","0")), min_chg, max_chg)
        analyst_norm   = _analyst_score(quote.get("fundamentals",{}).get("Analyst Recom.",""))

        composite = round(
            0.50 * sentiment_norm +
            0.30 * momentum_norm  +
            0.20 * analyst_norm,
            4
        )

        scored_articles = quote.get("scored_articles", [])
        top_article     = scored_articles[0] if scored_articles else {}

        watchlist.append({
            "ticker":            ticker,
            "company":           stock.get("company", ""),
            "price":             stock.get("price", ""),
            "change_pct":        stock.get("change_pct", ""),
            "market_cap":        stock.get("market_cap", ""),
            "pe":                stock.get("pe", ""),
            "target_price":      quote.get("fundamentals",{}).get("Target Price",""),
            "analyst_rating":    quote.get("fundamentals",{}).get("Analyst Recom.",""),
            "eps_ttm":           quote.get("fundamentals",{}).get("EPS (ttm)",""),
            "roe":               quote.get("fundamentals",{}).get("ROE",""),
            "beta":              quote.get("fundamentals",{}).get("Beta",""),
            "week52_high":       quote.get("fundamentals",{}).get("52W High",""),
            "week52_low":        quote.get("fundamentals",{}).get("52W Low",""),
            "short_float":       quote.get("fundamentals",{}).get("Short Float",""),
            "sentiment_score":   quote.get("sentiment_score", 0.0),
            "sentiment_label":   quote.get("sentiment_label", ""),
            "signal_strength":   quote.get("signal_strength", 0.0),
            "full_body_count":   quote.get("full_body_count", 0),
            "articles_scored":   len(scored_articles),
            "composite_score":   composite,
            "top_headline":      top_article.get("headline", ""),
            "top_article_url":   top_article.get("url", ""),
            "top_article_score": top_article.get("compound", 0.0),
            "scored_articles":   scored_articles,
        })

    return sorted(watchlist, key=lambda x: x["composite_score"], reverse=True)


# ── Markdown helpers ──────────────────────────────────────────────────────────

def _sentiment_badge(label: str) -> str:
    """Convert sentiment label to markdown emoji badge."""
    if "Bullish 🟢"         in label: return "🟢 Bullish"
    if "Slightly Bullish"   in label: return "🟡 Slightly Bullish"
    if "Bearish 🔴"         in label: return "🔴 Bearish"
    if "Slightly Bearish"   in label: return "🟠 Slightly Bearish"
    return "⚪ Neutral"


def _score_bar(score: float, width: int = 10) -> str:
    """Visual bar for composite score (0.0 - 1.0)."""
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


def build_markdown(watchlist: List[Dict]) -> str:
    """Build the full markdown report string."""
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# 📈 Finviz Stock Intelligence Report",
        f"> **Generated:** {now}  ",
        f"> **Universe:** S&P 500 Technology Sector — Page 1 (Top 20 by Market Cap)  ",
        f"> **Scoring:** 50% News Sentiment (full article) · 30% Price Momentum · 20% Analyst Rating  ",
        f"> **Source:** [finviz.com](https://finviz.com)  ",
        "",
        "---",
        "",
    ]

    # ── Summary stats ─────────────────────────────────────────────────────────
    total          = len(watchlist)
    bullish_count  = sum(1 for s in watchlist if s["sentiment_score"] >= 0.05)
    bearish_count  = sum(1 for s in watchlist if s["sentiment_score"] <= -0.05)
    neutral_count  = total - bullish_count - bearish_count
    avg_score      = sum(s["composite_score"] for s in watchlist) / total if total else 0
    avg_sentiment  = sum(s["sentiment_score"] for s in watchlist) / total if total else 0

    lines += [
        "## 📊 Market Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Stocks Analyzed | {total} |",
        f"| 🟢 Bullish | {bullish_count} ({round(bullish_count/total*100)}%) |",
        f"| ⚪ Neutral  | {neutral_count} ({round(neutral_count/total*100)}%) |",
        f"| 🔴 Bearish | {bearish_count} ({round(bearish_count/total*100)}%) |",
        f"| Avg Composite Score | {avg_score:.3f} |",
        f"| Avg Sentiment Score | {avg_sentiment:+.3f} |",
        "",
        "---",
        "",
    ]

    # ── Ranked watchlist table ────────────────────────────────────────────────
    lines += [
        "## 🏆 Ranked Watchlist",
        "",
        "| # | Ticker | Company | Price | Chg% | P/E | Sentiment | Score | Bar |",
        "|---|--------|---------|-------|------|-----|-----------|-------|-----|",
    ]

    for i, s in enumerate(watchlist, 1):
        badge = _sentiment_badge(s["sentiment_label"])
        bar   = _score_bar(s["composite_score"])
        lines.append(
            f"| {i} | **{s['ticker']}** | {s['company']} "
            f"| {s['price']} | {s['change_pct']} | {s['pe']} "
            f"| {badge} | {s['composite_score']:.3f} | `{bar}` |"
        )

    lines += ["", "---", ""]

    # ── Top 3 picks detail ────────────────────────────────────────────────────
    lines += ["## 🥇 Top 3 Picks — Detail", ""]

    for i, s in enumerate(watchlist[:3], 1):
        medal = ["🥇", "🥈", "🥉"][i-1]
        lines += [
            f"### {medal} #{i} {s['ticker']} — {s['company']}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Price** | {s['price']} |",
            f"| **Change** | {s['change_pct']} |",
            f"| **Market Cap** | {s['market_cap']} |",
            f"| **P/E** | {s['pe']} |",
            f"| **EPS (ttm)** | {s['eps_ttm'] or 'N/A'} |",
            f"| **ROE** | {s['roe'] or 'N/A'} |",
            f"| **Beta** | {s['beta'] or 'N/A'} |",
            f"| **52W High** | {s['week52_high'] or 'N/A'} |",
            f"| **52W Low** | {s['week52_low'] or 'N/A'} |",
            f"| **Short Float** | {s['short_float'] or 'N/A'} |",
            f"| **Analyst Rating** | {s['analyst_rating'] or 'N/A'} |",
            f"| **Target Price** | {s['target_price'] or 'N/A'} |",
            f"| **Sentiment** | {s['sentiment_label']} (score: {s['sentiment_score']:+.3f}) |",
            f"| **Signal Strength** | {s['signal_strength']}% of articles agree |",
            f"| **Composite Score** | **{s['composite_score']:.3f}** `{_score_bar(s['composite_score'])}` |",
            "",
        ]

        # Top headlines for this stock
        articles = s.get("scored_articles", [])
        if articles:
            lines += [f"#### 📰 News Articles ({len(articles)} scored)", ""]
            for j, a in enumerate(articles[:5], 1):
                src    = "📄 full" if a.get("source_used") == "full_article" else "📋 headline"
                score  = a.get("compound", 0.0)
                emoji  = "🟢" if score >= 0.05 else "🔴" if score <= -0.05 else "⚪"
                lines.append(
                    f"{j}. {emoji} `{score:+.3f}` [{src}] "
                    f"[{a['headline'][:80]}]({a.get('url','')})"
                )
            lines.append("")

        lines += ["---", ""]

    # ── Bottom 3 warnings ─────────────────────────────────────────────────────
    lines += ["## ⚠️ Watch Out — Bottom 3", ""]
    lines += [
        "| # | Ticker | Company | Sentiment | Score | Top Headline |",
        "|---|--------|---------|-----------|-------|--------------|",
    ]
    for i, s in enumerate(reversed(watchlist[-3:]), 1):
        headline = s.get("top_headline", "")[:60] + "..." if s.get("top_headline") else "N/A"
        lines.append(
            f"| {i} | **{s['ticker']}** | {s['company']} "
            f"| {_sentiment_badge(s['sentiment_label'])} "
            f"| {s['composite_score']:.3f} | {headline} |"
        )

    lines += ["", "---", ""]

    # ── Footer ────────────────────────────────────────────────────────────────
    lines += [
        "> ⚠️ **Disclaimer:** This report is generated automatically for educational purposes only.  ",
        "> It does not constitute financial advice. Always do your own research.  ",
        f"> *Built with [Scrapling](https://github.com/D4Vinci/Scrapling) + VADER Sentiment*",
        "",
    ]

    return "\n".join(lines)


def save_reports(watchlist: List[Dict], out_dir: str = ".") -> None:
    """Save full report and clean watchlist as .md files."""
    out = Path(out_dir)

    # ── Full report .md ───────────────────────────────────────────────────────
    report_md   = build_markdown(watchlist)
    report_path = out / "finviz_report.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"\n✅ Full report  → {report_path.resolve()}")

    # ── Clean watchlist .md (table only) ─────────────────────────────────────
    now   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# 📊 Finviz Watchlist — {now}",
        "",
        "| # | Ticker | Company | Price | Chg% | P/E | Market Cap | Sentiment | Score |",
        "|---|--------|---------|-------|------|-----|------------|-----------|-------|",
    ]
    for i, s in enumerate(watchlist, 1):
        lines.append(
            f"| {i} | **{s['ticker']}** | {s['company']} "
            f"| {s['price']} | {s['change_pct']} | {s['pe']} "
            f"| {s['market_cap']} | {_sentiment_badge(s['sentiment_label'])} "
            f"| {s['composite_score']:.3f} |"
        )

    watch_path = out / "finviz_watchlist.md"
    watch_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Watchlist    → {watch_path.resolve()}  ({len(watchlist)} stocks)")


def print_summary(watchlist: List[Dict]) -> None:
    """Console summary."""
    print("\n" + "═" * 76)
    print("  📊  FINVIZ STOCK INTELLIGENCE WATCHLIST")
    print("═" * 76)
    print(f"  {'#':<3} {'Ticker':<7} {'Company':<22} {'Price':>7} "
          f"{'Chg%':>7} {'Sentiment':<22} {'Arts':>5} {'Score':>6}")
    print(f"  {'─'*3} {'─'*7} {'─'*22} {'─'*7} {'─'*7} {'─'*22} {'─'*5} {'─'*6}")

    for i, s in enumerate(watchlist, 1):
        arts = f"{s['full_body_count']}/{s['articles_scored']}" if s['articles_scored'] else "—"
        print(
            f"  {i:<3} {s['ticker']:<7} {s['company'][:21]:<22} "
            f"{s['price']:>7} {s['change_pct']:>7} "
            f"{s['sentiment_label'][:21]:<22} {arts:>5} "
            f"{s['composite_score']:>6.3f}"
        )

    print("─" * 76)
    if watchlist:
        top = watchlist[0]
        print(f"\n  🏆 TOP PICK: {top['ticker']} — {top['company']}")
        print(f"     {top['sentiment_label']} | score {top['sentiment_score']:+.3f} "
              f"| signal {top['signal_strength']}% | composite {top['composite_score']:.3f}")
        if top.get("top_headline"):
            print(f"     \"{top['top_headline'][:72]}\"")
    print("═" * 76)
