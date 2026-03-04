"""
analyzer.py — Full Article Sentiment Analyzer

Scores full article body text (not just headlines) using VADER.

Scoring logic per article:
  - If body text available → score full article body (richer signal)
  - If body fetch failed   → score headline only (fallback)
  - Recency weight: articles[0] = most recent → 1.5x weight

Per-stock aggregation:
  - weighted avg compound score
  - sentiment label (Bullish/Bearish/Neutral)
  - signal strength (% articles agreeing with direction)
  - best/worst article summary
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import List, Dict, Any

_analyzer = SentimentIntensityAnalyzer()

RECENCY_WEIGHTS = [1.5, 1.5, 1.5, 1.0, 1.0, 1.0, 0.8, 0.8, 0.8, 0.8]


def score_text(text: str) -> float:
    """Return VADER compound score for any text string."""
    if not text or len(text.strip()) < 5:
        return 0.0
    return round(_analyzer.polarity_scores(text)["compound"], 4)


def analyze_stock(quote_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score all articles for one stock.
    Uses full body if available, falls back to headline.
    """
    ticker   = quote_data.get("ticker", "?")
    articles = quote_data.get("articles", [])

    if not articles:
        return {
            **quote_data,
            "sentiment_score":  0.0,
            "sentiment_label":  "No Data ⚪",
            "signal_strength":  0.0,
            "scored_articles":  [],
        }

    scored = []
    for i, article in enumerate(articles):
        headline = article.get("headline", "")
        body     = article.get("body", "")

        # ── Use full body if fetched, else fallback to headline ───────────────
        if body and len(body) >= 100:
            text_used = body
            source    = "full_article"
        else:
            text_used = headline
            source    = "headline_only"

        compound = score_text(text_used)
        label = (
            "bullish"  if compound >= 0.05  else
            "bearish"  if compound <= -0.05 else
            "neutral"
        )

        scored.append({
            "headline":    headline,
            "url":         article.get("url", ""),
            "date":        article.get("date", ""),
            "source_used": source,
            "body_chars":  len(body),
            "compound":    compound,
            "label":       label,
        })

    if not scored:
        return {**quote_data, "sentiment_score": 0.0,
                "sentiment_label": "No Data ⚪", "signal_strength": 0.0,
                "scored_articles": []}

    # ── Recency-weighted average ──────────────────────────────────────────────
    weighted_sum  = 0.0
    total_weight  = 0.0
    for i, s in enumerate(scored):
        w             = RECENCY_WEIGHTS[i] if i < len(RECENCY_WEIGHTS) else 0.8
        weighted_sum += s["compound"] * w
        total_weight += w

    sentiment_score = round(weighted_sum / total_weight, 4) if total_weight else 0.0

    # ── Signal strength ───────────────────────────────────────────────────────
    dominant = (
        "bullish" if sentiment_score >= 0.05  else
        "bearish" if sentiment_score <= -0.05 else
        "neutral"
    )
    agreeing       = sum(1 for s in scored if s["label"] == dominant)
    signal_strength = round(agreeing / len(scored) * 100, 1)

    # ── Count full vs headline-only ───────────────────────────────────────────
    full_body_count = sum(1 for s in scored if s["source_used"] == "full_article")

    # ── Label ────────────────────────────────────────────────────────────────
    if sentiment_score >= 0.15:
        label = "Bullish 🟢"
    elif sentiment_score >= 0.05:
        label = "Slightly Bullish 🟡"
    elif sentiment_score <= -0.15:
        label = "Bearish 🔴"
    elif sentiment_score <= -0.05:
        label = "Slightly Bearish 🟠"
    else:
        label = "Neutral ⚪"

    print(f"     {ticker}: sentiment={sentiment_score:+.3f} | "
          f"full_body={full_body_count}/{len(scored)} | "
          f"signal={signal_strength}%")

    return {
        **quote_data,
        "sentiment_score":  sentiment_score,
        "sentiment_label":  label,
        "signal_strength":  signal_strength,
        "full_body_count":  full_body_count,
        "scored_articles":  scored,
    }


def analyze_all(quote_results: List[Dict]) -> List[Dict]:
    """Analyze sentiment for all stocks."""
    return [analyze_stock(q) for q in quote_results]
