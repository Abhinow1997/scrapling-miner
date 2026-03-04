"""
reporter.py — Stats Aggregator & Report Generator

Builds a structured JSON report from analyzed reviews:
  - Overall sentiment distribution
  - Average polarity score
  - Per-category (tag) breakdown  ← the e-commerce insight layer
  - Top 3 most positive reviews
  - Top 3 most negative reviews
  - Most reviewed categories (volume signal)
"""

import json
from collections import defaultdict
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime


def build_report(analyzed: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate analyzed reviews into a structured insight report.
    """
    total = len(analyzed)
    if total == 0:
        return {"error": "No reviews to analyze"}

    # ── Overall sentiment counts ─────────────────────────────────────
    sentiment_counts: Dict[str, int] = defaultdict(int)
    for r in analyzed:
        sentiment_counts[r["sentiment"]] += 1

    # ── Per-category sentiment breakdown ─────────────────────────────
    # Each review can have multiple tags → expand into all categories
    category_data: Dict[str, Dict] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0,
                 "total": 0, "compound_sum": 0.0}
    )
    for r in analyzed:
        for tag in r["tags"]:
            category_data[tag]["total"] += 1
            category_data[tag][r["sentiment"]] += 1
            category_data[tag]["compound_sum"] += r["compound"]

    # Compute avg compound per category and sort by volume
    category_summary = {}
    for tag, data in sorted(
        category_data.items(), key=lambda x: x[1]["total"], reverse=True
    ):
        avg_compound = data["compound_sum"] / data["total"] if data["total"] else 0
        dominant = max(
            ["positive", "neutral", "negative"],
            key=lambda s: data[s]
        )
        category_summary[tag] = {
            "total_reviews": data["total"],
            "positive": data["positive"],
            "neutral":  data["neutral"],
            "negative": data["negative"],
            "avg_compound": round(avg_compound, 4),
            "dominant_sentiment": dominant,
        }

    # ── Extreme reviews ───────────────────────────────────────────────
    sorted_by_compound = sorted(analyzed, key=lambda x: x["compound"])

    def format_review(r: Dict) -> Dict:
        return {
            "text":      r["text"][:120] + ("..." if len(r["text"]) > 120 else ""),
            "author":    r["author"],
            "tags":      r["tags"],
            "compound":  r["compound"],
            "sentiment": r["sentiment"],
        }

    most_negative = [format_review(r) for r in sorted_by_compound[:3]]
    most_positive = [format_review(r) for r in reversed(sorted_by_compound[-3:])]

    # ── Assemble final report ─────────────────────────────────────────
    avg_compound = sum(r["compound"] for r in analyzed) / total

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_reviews_scraped": total,
            "source": "quotes.toscrape.com",
        },
        "overall": {
            "sentiment_distribution": {
                k: {
                    "count": sentiment_counts[k],
                    "pct":   round(sentiment_counts[k] / total * 100, 1),
                }
                for k in ["positive", "neutral", "negative"]
            },
            "avg_compound_score": round(avg_compound, 4),
            "verdict": (
                "Mostly Positive 😊" if avg_compound >= 0.05 else
                "Mostly Negative 😞" if avg_compound <= -0.05 else
                "Mixed / Neutral 😐"
            ),
        },
        "by_category": category_summary,
        "spotlight": {
            "most_positive_reviews": most_positive,
            "most_negative_reviews": most_negative,
        },
    }


def save_report(report: Dict[str, Any], output_path: str = "review_report.json") -> None:
    """Save report to JSON file."""
    path = Path(output_path)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✅ Report saved → {path.resolve()}")


def print_summary(report: Dict[str, Any]) -> None:
    """Print a human-readable console summary."""
    meta    = report.get("metadata", {})
    overall = report.get("overall", {})
    dist    = overall.get("sentiment_distribution", {})
    cats    = report.get("by_category", {})

    print("\n" + "═" * 55)
    print("  🛒  E-COMMERCE REVIEW SENTIMENT REPORT")
    print("═" * 55)
    print(f"  Source     : {meta.get('source')}")
    print(f"  Generated  : {meta.get('generated_at')}")
    print(f"  Reviews    : {meta.get('total_reviews_scraped')}")
    print("─" * 55)
    print(f"  Verdict    : {overall.get('verdict')}")
    print(f"  Avg Score  : {overall.get('avg_compound_score')}")
    print("─" * 55)
    print("  SENTIMENT BREAKDOWN")
    for label in ["positive", "neutral", "negative"]:
        d = dist.get(label, {})
        bar_len = int(d.get("pct", 0) / 2)
        bar = "█" * bar_len
        print(f"  {label:10} {bar:<25} {d.get('pct', 0):5.1f}%  ({d.get('count', 0)} reviews)")
    print("─" * 55)
    print("  TOP 5 CATEGORIES BY VOLUME")
    for i, (tag, data) in enumerate(list(cats.items())[:5], 1):
        print(
            f"  {i}. {tag:<20} "
            f"{data['total_reviews']:>3} reviews  |  "
            f"avg score: {data['avg_compound']:+.3f}  |  "
            f"dominant: {data['dominant_sentiment']}"
        )
    print("═" * 55)
