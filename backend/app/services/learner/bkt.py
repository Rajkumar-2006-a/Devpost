"""
Bayesian Knowledge Tracing (BKT) implementation.
Updates per-concept mastery probabilities after each quiz answer.
"""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass
class BKTParams:
    prior: float = 0.30     # P(L₀) initial mastery
    transit: float = 0.10   # P(T) learning rate
    slip: float = 0.10      # P(S) slip rate
    guess: float = 0.25     # P(G) guess rate


def update_mastery(
    mastery: float,
    correct: bool,
    params: BKTParams,
) -> float:
    """
    One BKT update step.
    Returns updated P(L) after observing correct/incorrect answer.
    """
    slip = params.slip
    guess = params.guess
    transit = params.transit

    # P(obs | L) and P(obs | ~L)
    if correct:
        p_obs_given_L = 1 - slip
        p_obs_given_notL = guess
    else:
        p_obs_given_L = slip
        p_obs_given_notL = 1 - guess

    # Bayes update
    numerator = p_obs_given_L * mastery
    denominator = numerator + p_obs_given_notL * (1 - mastery)

    if denominator == 0:
        p_L_given_obs = mastery
    else:
        p_L_given_obs = numerator / denominator

    # Apply transit (learning opportunity)
    p_L_next = p_L_given_obs + (1 - p_L_given_obs) * transit

    return min(max(p_L_next, 0.001), 0.999)


def compute_uncertainty(mastery: float, n_attempts: int) -> float:
    """
    Epistemic uncertainty: high when mastery ≈ 0.5 or n_attempts is low.
    Returns a value in [0, 1] where 1 = maximally uncertain.
    """
    # Variance of Bernoulli(mastery) scaled by inverse of sample size confidence
    variance = mastery * (1 - mastery)
    confidence = 1 - math.exp(-n_attempts / 5)   # saturates after ~15 attempts
    uncertainty = variance * (1 - confidence) + variance * 0.1
    return min(uncertainty * 4, 1.0)   # scale to [0,1]


def zpd_score(mastery: float, uncertainty: float) -> float:
    """
    Zone of Proximal Development score.
    High when mastery is in the learning zone (0.35–0.75) and uncertainty is moderate.
    Used to select which concept to quiz next.
    """
    in_zpd = 1.0 - abs(mastery - 0.55) * 2   # peaks at mastery=0.55
    return max(in_zpd, 0.0) * (1 - mastery * 0.3)   # slight penalty for already-mastered
