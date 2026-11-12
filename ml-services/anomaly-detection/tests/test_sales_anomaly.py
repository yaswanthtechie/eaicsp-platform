import logging

import numpy as np
import pandas as pd
import pytest

from src.sales_anomaly import (
    MIN_SERIES_DAYS,
    classify,
    detect,
    score_series,
)


def frame(values, product="SKU-000001", warehouse="WH-BLR-01", start="2026-01-05"):

    dates = pd.date_range(start, periods=len(values), freq="D")

    return pd.DataFrame(
        {
            "sale_date": dates,
            "sku_id": product,
            "warehouse": warehouse,
            "quantity_sold": values,
        }
    )


def flat(n=120, level=50.0):
    return np.full(n, level)


def test_flat_series_has_no_anomalies():

    scores, skipped = detect(frame(flat()))

    assert skipped == []
    assert scores["score"].notna().sum() > 0
    assert not scores["is_anomaly"].any()


def test_weekly_pattern_without_noise_has_no_anomalies():

    values = np.tile([40, 42, 45, 50, 60, 80, 30], 18)[:120].astype(float)

    scores, _ = detect(frame(values))

    assert not scores["is_anomaly"].any()


def test_injected_spike_is_found_as_a_high_spike():

    values = flat()
    values[100] = 250.0

    scores, _ = detect(frame(values))
    hit = scores[scores["is_anomaly"]]

    assert len(hit) == 1
    row = hit.iloc[0]
    assert row["date"] == pd.Timestamp("2026-01-05") + pd.Timedelta(days=100)
    assert row["direction"] == "spike"
    assert row["severity"] == "high"


def test_injected_drop_to_zero_is_found_as_a_high_drop():

    values = flat()
    values[100] = 0.0

    scores, _ = detect(frame(values))
    hit = scores[scores["is_anomaly"]]

    assert len(hit) == 1
    assert hit.iloc[0]["direction"] == "drop"
    assert hit.iloc[0]["severity"] == "high"


def test_normal_noise_size_bump_is_not_flagged():

    values = flat()
    values[100] = 80.0  # +60% on 50: inside day-to-day noise for real sales

    scores, _ = detect(frame(values))

    assert not scores["is_anomaly"].any()


@pytest.mark.parametrize(
    "quantity,expected,z,direction,severity",
    [
        (50, 50, 0.0, "", ""),
        (60, 50, 4.8, "", ""),
        (100, 50, 4.9, "spike", "low"),
        (120, 50, 7.0, "spike", "medium"),
        (200, 50, 10.0, "spike", "high"),
        (11, 50, -2.0, "", ""),
        (10, 50, -2.0, "drop", "low"),
        (5, 50, -2.3, "drop", "medium"),
        (2, 50, -2.5, "drop", "high"),
        (0, 10, -1.8, "", ""),  # expected under 15: too small to call a drop
        (99, 50, float("nan"), "", ""),
    ],
)
def test_classify_rule(quantity, expected, z, direction, severity):

    d, s = classify([quantity], [expected], [z])

    assert (d[0], s[0]) == (direction, severity)


def test_series_that_stops_selling_is_flagged_as_a_drop():

    selling = frame(flat(120), warehouse="WH-BLR-01")
    stopped = frame(flat(100), warehouse="WH-DEL-01")  # no rows after day 100

    scores, _ = detect(pd.concat([selling, stopped]))
    hit = scores[(scores["warehouse"] == "WH-DEL-01") & scores["is_anomaly"]]

    assert len(hit) > 0
    assert set(hit["direction"]) == {"drop"}


def test_scores_use_no_future_data():

    rng = np.random.default_rng(7)
    values = rng.poisson(50, 200).astype(float)

    _, _, z_before = score_series(values)

    changed = values.copy()
    changed[100:] = changed[100:] * 5 + 1000

    _, _, z_after = score_series(changed)

    assert np.allclose(z_before[:100], z_after[:100], equal_nan=True)
    assert not np.allclose(z_before[100:], z_after[100:], equal_nan=True)


def test_first_four_weeks_are_not_scored():

    values = flat()
    values[10] = 999.0

    scores, _ = detect(frame(values))
    early = scores.head(28)

    assert early["score"].isna().all()
    assert not early["is_anomaly"].any()


def test_short_series_is_skipped_with_a_log_line(caplog):

    with caplog.at_level(logging.WARNING):
        scores, skipped = detect(frame(flat(MIN_SERIES_DAYS - 1)))

    assert len(scores) == 0
    assert skipped == [("SKU-000001", "WH-BLR-01", MIN_SERIES_DAYS - 1)]
    assert "Skipping SKU-000001 / WH-BLR-01" in caplog.text


def test_series_with_exactly_eight_weeks_is_processed():

    scores, skipped = detect(frame(flat(MIN_SERIES_DAYS)))

    assert skipped == []
    assert len(scores) == MIN_SERIES_DAYS


def test_products_and_warehouses_are_scored_independently():

    spiked = flat()
    spiked[100] = 300.0

    df = pd.concat(
        [
            frame(spiked, warehouse="WH-BLR-01"),
            frame(flat(), warehouse="WH-DEL-01"),
        ]
    )

    scores, _ = detect(df)
    hit = scores[scores["is_anomaly"]]

    assert set(hit["warehouse"]) == {"WH-BLR-01"}


def test_rows_for_the_same_day_are_summed():

    df = frame(flat(120, 25.0))
    df = pd.concat([df, df], ignore_index=True)

    scores, _ = detect(df)

    assert (scores["quantity"] == 50.0).all()
    assert not scores["is_anomaly"].any()


def test_missing_day_counts_as_zero_by_default():

    df = frame(flat()).drop(index=100)

    scores, _ = detect(df)
    hit = scores[scores["is_anomaly"]]

    assert len(hit) == 1
    assert hit.iloc[0]["direction"] == "drop"

    scores_off, _ = detect(df, fill_missing_as_zero=False)

    assert not scores_off["is_anomaly"].any()


def test_product_code_column_is_accepted():

    df = frame(flat()).rename(columns={"sku_id": "product_code"})

    scores, _ = detect(df)

    assert len(scores) == 120


def test_missing_column_raises():

    with pytest.raises(ValueError):
        detect(frame(flat()).drop(columns=["warehouse"]))


def test_all_series_skipped_gives_an_empty_filterable_result():

    scores, skipped = detect(frame(flat(10)))

    assert len(skipped) == 1
    assert len(scores[scores["is_anomaly"].astype(bool)]) == 0
    assert "severity" in scores.columns