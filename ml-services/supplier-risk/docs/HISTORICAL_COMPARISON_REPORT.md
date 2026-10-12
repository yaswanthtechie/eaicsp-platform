# Supplier Risk Score-Change Events: Hysteresis Historical Comparison Report

> **Event-count reduction measures stability, not accuracy.** Do not claim hysteresis improved accuracy merely because it reduced event counts.

> **Data provenance:** the replay dataset (`supplier_trend_headlines_25.json`) is synthetic, authored in Round 9 for trend regression testing. These numbers show how the rules behave on that data; they are not evidence from real news.

## 1. Summary

- Dates replayed: `2026-01-05` to `2026-03-23` (12 evaluation dates, 30-day rolling window)
- Suppliers: 25; articles: 300

| Run | Events | Reduction vs baseline |
| :--- | :---: | :---: |
| Baseline (nominal boundaries, no rules) | 43 | - |
| Hysteresis only (`min_evidence=0`) | 30 | 13 (30.23%) |
| Hysteresis + evidence (`min_evidence=2`) | 21 | 22 (51.16%) |

Suppressed attempts in the hysteresis + evidence run, by reason: `insufficient_evidence`: 17, `insufficient_initial_evidence`: 25

## 2. Configuration

| Parameter | Value | Rule |
| :--- | :---: | :--- |
| `enter_medium_threshold` | `62.0` | low -> medium when score >= 62.0 |
| `exit_medium_threshold` | `58.0` | medium -> low when score < 58.0 |
| `enter_high_threshold` | `74.0` | -> high when score >= 74.0 |
| `exit_high_threshold` | `70.0` | high -> medium when score < 70.0 |
| `min_evidence` | `2` | at least 2 window article(s) whose own score points toward the new tier |
| `require_min_evidence_for_initial` | `True` | first tier needs at least 2 article(s) in the window |
| `top_articles` | `3` | supporting articles carried in each event |

## 3. Per-Supplier Counts

| Supplier | Baseline | Hysteresis only | Hysteresis + evidence | Final tier | What changed |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **ArcelorMittal** | 4 | 2 | 2 | `low` | hysteresis 4 -> 2 |
| **Intel** | 4 | 2 | 2 | `low` | hysteresis 4 -> 2 |
| **Maersk** | 4 | 4 | 4 | `low` | All baseline transitions kept |
| **TSMC** | 4 | 2 | 0 | `low` | All baseline transitions suppressed |
| **Toshiba** | 4 | 2 | 2 | `high` | hysteresis 4 -> 2 |
| **Boeing** | 3 | 3 | 2 | `low` | evidence rule 3 -> 2 |
| **Evergreen Marine** | 3 | 2 | 1 | `low` | hysteresis 3 -> 2, evidence rule 2 -> 1 |
| **Glencore** | 3 | 2 | 0 | `medium` | All baseline transitions suppressed |
| **Apex Logistics** | 2 | 2 | 1 | `medium` | evidence rule 2 -> 1 |
| **DHL Supply Chain** | 2 | 2 | 2 | `low` | All baseline transitions kept |
| **Foxconn** | 2 | 2 | 1 | `low` | evidence rule 2 -> 1 |
| **Nissan** | 2 | 2 | 2 | `low` | All baseline transitions kept |
| **Tesla** | 2 | 2 | 1 | `low` | evidence rule 2 -> 1 |
| **Volvo Group** | 2 | 0 | 0 | `low` | All baseline transitions suppressed |
| **BASF** | 1 | 1 | 1 | `medium` | All baseline transitions kept |
| **Evergrande Construction Logistics** | 1 | 0 | 0 | `high` | All baseline transitions suppressed |
| **ASML** | 0 | 0 | 0 | `low` | No tier changes in any run |
| **Caterpillar** | 0 | 0 | 0 | `low` | No tier changes in any run |
| **Lockheed Martin** | 0 | 0 | 0 | `low` | No tier changes in any run |
| **Northvolt** | 0 | 0 | 0 | `high` | No tier changes in any run |
| **Rio Tinto** | 0 | 0 | 0 | `low` | No tier changes in any run |
| **Schneider Electric** | 0 | 0 | 0 | `low` | No tier changes in any run |
| **Siemens** | 0 | 0 | 0 | `low` | No tier changes in any run |
| **Silicon Power Storage** | 0 | 0 | 0 | `high` | No tier changes in any run |
| **Texas Instruments** | 0 | 0 | 0 | `low` | No tier changes in any run |

## 4. Largest Reductions: Baseline vs Accepted Transitions

### TSMC

| Date | Score | Baseline | Accepted |
| :--- | :---: | :--- | :--- |
| 2026-01-19 | 64.95 | low -> medium | no event |
| 2026-02-09 | 56.08 | medium -> low | no event |
| 2026-02-16 | 61.62 | low -> medium | no event |
| 2026-02-23 | 51.75 | medium -> low | no event |

### Glencore

| Date | Score | Baseline | Accepted |
| :--- | :---: | :--- | :--- |
| 2026-01-26 | 82.59 | medium -> high | no event |
| 2026-03-09 | 67.41 | high -> medium | no event |
| 2026-03-23 | 59.94 | medium -> low | no event |

### ArcelorMittal

| Date | Score | Baseline | Accepted |
| :--- | :---: | :--- | :--- |
| 2026-01-26 | 60.66 | low -> medium | no event |
| 2026-02-02 | 56.41 | medium -> low | no event |
| 2026-02-09 | 62.46 | low -> medium | low -> medium |
| 2026-03-23 | 55.48 | medium -> low | medium -> low |

## 5. Representative Event Envelopes

### Example 1: `Foxconn` (medium -> low)

```json
{
  "event_id": "4e3c09a8-9c2e-40fc-aba5-e9c0753d1194",
  "event_type": "supplierrisk.score.changed",
  "event_version": 1,
  "occurred_at": "2026-01-26T00:00:00+00:00",
  "producer": "supplier-risk-service",
  "payload": {
    "supplier": "Foxconn",
    "previous_tier": "medium",
    "new_tier": "low",
    "risk_score": 53.97,
    "supporting_articles": [
      {
        "headline": "Foxconn announces a massive expansion of its manufacturing footprint in India.",
        "date": "2026-01-19",
        "score": 0.0
      },
      {
        "headline": "Foxconn reports strong positive earnings driven by robust smartphone demand.",
        "date": "2026-01-26",
        "score": 0.0
      }
    ],
    "evidence_count": 2,
    "explanation": "Supplier 'Foxconn' moved from 'medium' to 'low': score 53.97 fell below the 'medium' exit threshold 58.00. 2 of 4 article(s) in the window point toward 'low' (minimum 2). Top drivers: \"Foxconn announces a massive expansion of its manufacturing footprint in India.\" (0.00); \"Foxconn reports strong positive earnings driven by robust smartphone demand.\" (0.00)."
  }
}
```

### Example 2: `ArcelorMittal` (low -> medium)

```json
{
  "event_id": "02efa485-f2fa-45bc-8ff2-28781e22f44d",
  "event_type": "supplierrisk.score.changed",
  "event_version": 1,
  "occurred_at": "2026-02-09T00:00:00+00:00",
  "producer": "supplier-risk-service",
  "payload": {
    "supplier": "ArcelorMittal",
    "previous_tier": "low",
    "new_tier": "medium",
    "risk_score": 62.46,
    "supporting_articles": [
      {
        "headline": "ArcelorMittal faces lawsuit from municipal authorities over industrial water contamination.",
        "date": "2026-01-26",
        "score": 63.01
      },
      {
        "headline": "ArcelorMittal steelworkers stage walkout strike demanding higher inflation compensation.",
        "date": "2026-01-19",
        "score": 62.13
      }
    ],
    "evidence_count": 2,
    "explanation": "Supplier 'ArcelorMittal' moved from 'low' to 'medium': score 62.46 reached the 'medium' entry threshold 62.00. 2 of 5 article(s) in the window point toward 'medium' (minimum 2). Top drivers: \"ArcelorMittal faces lawsuit from municipal authorities over industrial water contamination.\" (63.01); \"ArcelorMittal steelworkers stage walkout strike demanding higher inflation compensation.\" (62.13)."
  }
}
```

### Example 3: `Intel` (low -> medium)

```json
{
  "event_id": "1529b251-5624-4f32-a88e-6ecc27a4d982",
  "event_type": "supplierrisk.score.changed",
  "event_version": 1,
  "occurred_at": "2026-02-09T00:00:00+00:00",
  "producer": "supplier-risk-service",
  "payload": {
    "supplier": "Intel",
    "previous_tier": "low",
    "new_tier": "medium",
    "risk_score": 62.86,
    "supporting_articles": [
      {
        "headline": "Supply chain disruption causes delays in Intel's latest processor launch.",
        "date": "2026-02-09",
        "score": 73.03
      },
      {
        "headline": "Intel announces massive layoff affecting 15% of its global workforce.",
        "date": "2026-01-26",
        "score": 63.71
      },
      {
        "headline": "Intel faces a new lawsuit over alleged patent infringement.",
        "date": "2026-01-19",
        "score": 62.61
      }
    ],
    "evidence_count": 3,
    "explanation": "Supplier 'Intel' moved from 'low' to 'medium': score 62.86 reached the 'medium' entry threshold 62.00. 3 of 5 article(s) in the window point toward 'medium' (minimum 2). Top drivers: \"Supply chain disruption causes delays in Intel's latest processor launch.\" (73.03); \"Intel announces massive layoff affecting 15% of its global workforce.\" (63.71); \"Intel faces a new lawsuit over alleged patent infringement.\" (62.61)."
  }
}
```

## 6. Limitations

1. Hysteresis delays transitions for scores that stop between a nominal boundary and its enter threshold.
2. Suppliers with too few articles pointing toward a new tier keep their current tier until more arrive.
3. Article-level scores come from scoring each headline on its own, so a headline can count as evidence even when the aggregated score moved for a different reason.

---
*Generated by `python -m src.historical_comparison`. Every number above comes from the replay results.*
