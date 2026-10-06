# Learner Model

## Overview

The learner model tracks per-concept mastery for each student using two complementary techniques:
1. **Bayesian Knowledge Tracing (BKT)** — estimates current mastery probability
2. **SM2 Spaced Repetition** — schedules future reviews based on recall performance

## Bayesian Knowledge Tracing

BKT models each concept as a latent binary variable: *known* or *unknown*.

### Parameters (per student per concept)

| Parameter | Symbol | Default | Meaning |
|---|---|---|---|
| Initial mastery | P(L₀) | 0.30 | Probability of knowing the concept before any practice |
| Learning rate | P(T) | 0.10 | Probability of transitioning from unknown to known after each attempt |
| Slip rate | P(S) | 0.10 | Probability of answering incorrectly despite knowing |
| Guess rate | P(G) | 0.25 | Probability of answering correctly without knowing |

### Update Equations

After observing a correct answer:
```
P(L | correct) = P(L)(1-S) / [P(L)(1-S) + (1-P(L))G]
P(L_next) = P(L | correct) + (1 - P(L | correct)) × P(T)
```

After observing an incorrect answer:
```
P(L | wrong) = P(L)S / [P(L)S + (1-P(L))(1-G)]
P(L_next) = P(L | wrong) + (1 - P(L | wrong)) × P(T)
```

### Epistemic Uncertainty

Uncertainty is computed as `mastery × (1 - mastery) × (1 - confidence)`, where confidence saturates as the number of attempts increases. High uncertainty signals the model is unsure about its estimate.

### Zone of Proximal Development (ZPD)

Items for adaptive assessment are selected using a ZPD score:
```
ZPD = max(1 - |mastery - 0.55| × 2, 0)
```
This peaks at mastery ≈ 0.55 — the ideal challenge zone where learning is most efficient.

## Spaced Repetition (SM2-inspired)

After each successful recall, the next review date is extended:
- After 1 correct: next review in 1 day (stability=1)
- After 2 correct: next review in 3 days (stability=3)
- After N+1 correct: stability × 2.5 days

Failed recalls reset stability to 1 day (next review tomorrow).

### Retention Probability

Between sessions, the Ebbinghaus forgetting curve predicts how much has been retained:
```
R = e^(-t / S)
```
where `t` = days since last review, `S` = stability factor.

## Cold Start (Onboarding)

New students go through:
1. **Profile creation**: name, exam date, goals, prior knowledge self-assessment.
2. **Diagnostic quiz**: a short assessment to calibrate initial mastery estimates.
3. **Initial mastery prior**: set from self-assessment (high/medium/low) mapped to P(L₀) = {0.6, 0.3, 0.1}.

## Persistence

Every quiz answer and relevant chat interaction updates the learner model in real-time:
- `concept_mastery` table stores BKT state + spaced-rep schedule per concept per student.
- `interaction_history` logs every interaction for audit and future analytics.

## Limitations

- BKT assumes concept independence; correlated concepts require more sophisticated models (like DKVMN).
- Slip/guess rates use fixed defaults; per-student estimation requires EM with sufficient data (~50+ observations).
- The forgetting curve model doesn't account for context-dependent recall.
