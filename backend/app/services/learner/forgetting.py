"""
Spaced repetition / forgetting curve (SM2-inspired).
Computes next review date for each concept based on recall stability.
"""
from __future__ import annotations
from datetime import datetime, timedelta
import math


def next_review_date(
    last_reviewed: datetime,
    stability: float,
    correct: bool,
    n_correct: int,
) -> tuple[datetime, float]:
    """
    SM2-inspired calculation.
    Returns (next_review_datetime, new_stability).

    stability: current memory stability (starts at 1.0 day)
    correct: whether the latest recall was correct
    n_correct: cumulative correct answers
    """
    if correct:
        # Increase stability
        if n_correct <= 1:
            interval_days = 1.0
            new_stability = 1.0
        elif n_correct == 2:
            interval_days = 3.0
            new_stability = 3.0
        else:
            new_stability = stability * 2.5
            interval_days = new_stability
    else:
        # Reset on failure
        new_stability = 1.0
        interval_days = 1.0

    next_dt = last_reviewed + timedelta(days=interval_days)
    return next_dt, new_stability


def retention_prob(last_reviewed: datetime, stability: float, now: datetime | None = None) -> float:
    """
    Ebbinghaus forgetting curve: R = e^(-t/S)
    Returns estimated retention probability [0, 1].
    """
    if now is None:
        now = datetime.utcnow()
    t = max((now - last_reviewed).total_seconds() / 86400, 0)   # days elapsed
    if stability <= 0:
        return 0.0
    return math.exp(-t / stability)


def items_due(concept_states: list[dict], now: datetime | None = None) -> list[str]:
    """
    Return concept_ids where next_review <= now (review due).
    concept_states: list of {concept_id, next_review (datetime or None), stability}
    """
    if now is None:
        now = datetime.utcnow()
    due = []
    for cs in concept_states:
        nr = cs.get("next_review")
        if nr is None or nr <= now:
            due.append(cs["concept_id"])
    return due
