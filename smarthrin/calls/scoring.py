"""Shared scoring normalization utilities for AI screening scorecards."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Score scale boundaries
MIN_SCORE = 0.0
MAX_SCORE = 10.0
SCALE_100_THRESHOLD = 10.0


def normalize_score(val: float) -> float:
    """Normalize a score to the 0-10 scale and clamp within bounds.

    Values > 10 are assumed to be on a 0-100 scale and divided by 10.
    Negative values are clamped to 0. Values above 10 (after normalization)
    are clamped to 10.
    """
    if val < 0:
        val = 0.0
    if val > SCALE_100_THRESHOLD:
        val = val / 10.0
    # Clamp to 0-10 after normalization
    val = max(MIN_SCORE, min(val, MAX_SCORE))
    return round(val, 2)


def compute_overall_score(
    communication: float,
    knowledge: float,
    confidence: float,
    relevance: float,
    fallback_overall: float = 0.0,
) -> float:
    """Compute overall score from individual scores, or use fallback."""
    scores = [communication, knowledge, confidence, relevance]
    # Use individual scores if at least one is non-zero
    if any(s > 0 for s in scores):
        return round(sum(scores) / 4, 2)
    return fallback_overall


def compute_recommendation(overall: float) -> str:
    """Return recommendation string based on overall score."""
    if overall >= 8.0:
        return "STRONG_YES"
    elif overall >= 7.0:
        return "YES"
    elif overall >= 5.0:
        return "MAYBE"
    elif overall >= 3.0:
        return "NO"
    else:
        return "STRONG_NO"
