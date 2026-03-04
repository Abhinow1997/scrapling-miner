"""
analyzer.py — Sentiment Analysis Engine

Uses VADER (Valence Aware Dictionary and sEntiment Reasoner):
  - No corpus downloads needed
  - Works great for short review-style text
  - Returns compound score: -1.0 (most negative) → +1.0 (most positive)

Sentiment bucketing:
  compound >= 0.05  → positive
  compound <= -0.05 → negative
  in between        → neutral
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from typing import List, Dict, Any

# Single shared analyzer instance (thread-safe for reads)
_analyzer = SentimentIntensityAnalyzer()


def score_review(review: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add VADER sentiment scores to a single review dict.

    Adds:
      - compound     : float, -1.0 to 1.0 (overall sentiment strength)
      - pos / neu / neg : raw VADER component scores
      - sentiment    : 'positive' | 'neutral' | 'negative' label
    """
    scores = _analyzer.polarity_scores(review["text"])

    compound = scores["compound"]

    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return {
        **review,
        "compound":   round(compound, 4),
        "pos_score":  round(scores["pos"], 4),
        "neu_score":  round(scores["neu"], 4),
        "neg_score":  round(scores["neg"], 4),
        "sentiment":  label,
    }


def analyze_all(reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Score every review in the list."""
    return [score_review(r) for r in reviews]
