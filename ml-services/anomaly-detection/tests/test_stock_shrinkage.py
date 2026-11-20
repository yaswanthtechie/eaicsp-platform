"""
The stock shrinkage check: expected = start + received - sold, gap = expected -
actual, flags above the thresholds, and skips (never guesses) missing data.
All data here is synthetic.
"""

import pandas as pd
import pytest

from src import stock_shrinkage
from src.stock_shrinkage import check, latest_snapshot_dates, main, severity

START = "2026-11-02"
END = "2026-11-09"
P, W = "PRD-10001", "HYD-01"


def inventory(*rows):
    """rows: (snapshot_date, product, warehouse, on_hand)."""

    return pd.DataFrame(
        [(d, p, w, str(q)) for d, p, w, q in rows],
        columns=["snapshot_date", "product_code", "warehouse_code", "quantity_on_hand"],
    )


def sales(*rows):
    """rows: (sale_date, product, warehouse, quantity)."""

    return pd.DataFrame(
        [(d, p, w, str(q)) for d, p, w, q in rows],
        columns=["sale_date", "product_code", "warehouse_code", "quantity_sold"],
    )


def orders(*rows):
    """rows: (received_date, product, warehouse, quantity, status)."""

    return pd.DataFrame(
        [(d, p, w, str(q), s) for d, p, w, q, s in rows],
        columns=[
            "received_date",
            "product_code",
            "warehouse_code",
            "quantity_ordered",
            "po_status",
        ],
    )


NO_ORDERS = orders()


def pair(start_qty, end_qty, sold=0, received=0):
    """One product and warehouse; sales spread over one day and one received order."""

    po = [("2026-11-05", P, W, received, "Received")] if received else []

    return (
        inventory((START, P, W, start_qty), (END, P, W, end_qty)),
        sales(("2026-11-04", P, W, sold)),
        orders(*po),
    )


def run(inv, sold, po):
    return check(inv, sold, po, START, END)


def test_pair_that_balances_exactly_is_not_flagged():
    # 500 + 100 received - 150 sold = 450 expected; actual 450.
    result = run(*pair(500, 450, sold=150, received=100))

    assert result.checked == 1
    assert result.flags.empty
    assert result.skipped_total == 0


def test_planted_drop_is_flagged_with_its_numbers():
    # Expected 450, actual 380: 70 units (15.6%) gone without a sale.
    result = run(*pair(500, 380, sold=150, received=100))

    assert len(result.flags) == 1
    row = result.flags.iloc[0]

    assert (row.product_code, row.warehouse_code) == (P, W)
    assert row.start_on_hand == 500
    assert row.received == 100
    assert row.sold == 150
    assert row.expected == 450
    assert row.actual == 380
    assert row.gap == 70
    assert row.gap_pct == pytest.approx(0.1556, abs=1e-4)
    assert row.severity == "medium"


def test_missing_snapshot_is_skipped_and_counted():
    inv = inventory((START, P, W, 500))  # no end snapshot
    result = run(inv, sales((("2026-11-04"), P, W, 10)), NO_ORDERS)

    assert result.checked == 0
    assert result.flags.empty
    assert result.skipped["missing_end_snapshot"] == 1


def test_missing_start_snapshot_is_skipped_and_counted():
    inv = inventory((END, P, W, 500))
    result = run(inv, sales(("2026-11-04", P, W, 10)), NO_ORDERS)

    assert result.skipped["missing_start_snapshot"] == 1


@pytest.mark.parametrize(
    ("gap", "pct_of_expected", "expected_severity"),
    [
        (60, 0.30, "high"),
        (60, 0.15, "medium"),  # units are high, the share is only medium
        (30, 0.30, "medium"),  # share is high, the units are only medium
        (12, 0.06, "low"),
    ],
)
def test_severity_needs_both_units_and_share(gap, pct_of_expected, expected_severity):
    assert severity(gap, pct_of_expected) == expected_severity


def test_drop_below_either_threshold_is_not_flagged():
    # 8 units of 100 (8%): under SHRINK_MIN_UNITS.
    assert run(*pair(100, 92)).flags.empty
    # 15 units of 1000 (1.5%): under SHRINK_MIN_PCT.
    assert run(*pair(1000, 985)).flags.empty


def test_more_stock_than_expected_is_counted_not_flagged():
    result = run(*pair(500, 520))

    assert result.flags.empty
    assert result.above_expected == 1


def test_window_excludes_the_start_day_and_includes_the_end_day():
    inv = inventory((START, P, W, 100), (END, P, W, 70))
    sold = sales(
        (START, P, W, 500),  # already in the start snapshot: not counted
        ("2026-11-03", P, W, 10),
        (END, P, W, 20),  # counted
        ("2026-11-10", P, W, 500),  # after the end snapshot: not counted
    )

    assert run(inv, sold, NO_ORDERS).checked == 1
    assert run(inv, sold, NO_ORDERS).flags.empty  # 100 - 30 = 70 balances


def test_only_received_orders_add_stock():
    inv = inventory((START, P, W, 100), (END, P, W, 100))
    sold = sales(("2026-11-04", P, W, 0))
    po = orders(
        ("2026-11-05", P, W, 50, "Open"),
        ("2026-11-05", P, W, 70, "Cancelled"),
        ("2026-10-20", P, W, 90, "Received"),  # before the window
    )

    result = run(inv, sold, po)

    assert result.checked == 1
    assert result.flags.empty  # nothing received in the window: 100 = 100


def test_invalid_sales_row_skips_that_pair_only():
    inv = inventory(
        (START, P, W, 500),
        (END, P, W, 100),
        (START, "PRD-10002", W, 50),
        (END, "PRD-10002", W, 50),
    )
    sold = sales(("not-a-date", P, W, 10), ("2026-11-04", "PRD-10002", W, 0))

    result = run(inv, sold, NO_ORDERS)

    assert result.skipped["bad_sales_row"] == 1  # P/W would otherwise be a 400-unit gap
    assert result.checked == 1


def test_negative_sales_quantity_skips_the_pair():
    inv = inventory((START, P, W, 500), (END, P, W, 450))
    sold = sales(("2026-11-04", P, W, -5))

    assert run(inv, sold, NO_ORDERS).skipped["bad_sales_row"] == 1


def test_received_order_without_a_valid_date_skips_the_pair():
    inv = inventory((START, P, W, 100), (END, P, W, 40))
    po = orders(("", P, W, 80, "Received"))

    result = run(inv, sales(("2026-11-04", P, W, 0)), po)

    assert result.skipped["bad_po_row"] == 1
    assert result.flags.empty


def test_no_sales_rows_in_the_window_is_skipped_not_assumed_zero():
    inv = inventory((START, P, W, 500), (END, P, W, 100))

    result = run(inv, sales(("2026-10-01", P, W, 5)), NO_ORDERS)

    assert result.skipped["no_sales_in_window"] == 1
    assert result.flags.empty


def test_invalid_or_duplicate_on_hand_is_skipped():
    bad = inventory((START, P, W, "x"), (END, P, W, 10))
    dup = inventory((START, P, W, 500), (START, P, W, 480), (END, P, W, 10))
    sold = sales(("2026-11-04", P, W, 1))

    assert run(bad, sold, NO_ORDERS).skipped["invalid_on_hand"] == 1
    assert run(dup, sold, NO_ORDERS).skipped["duplicate_snapshot"] == 1


def test_rows_without_a_code_are_counted_not_guessed():
    inv, sold, po = pair(500, 450)
    sold = pd.concat([sold, sales(("2026-11-04", "", W, 40))], ignore_index=True)

    result = run(inv, sold, po)

    assert result.unattributable_rows == 1


def test_start_must_be_before_end():
    with pytest.raises(ValueError, match="before"):
        check(*pair(1, 1), END, START)


def test_missing_column_is_an_error():
    with pytest.raises(ValueError, match="quantity_on_hand"):
        check(pd.DataFrame({"snapshot_date": []}), sales(), NO_ORDERS, START, END)


def test_latest_snapshot_dates_takes_the_two_most_recent():
    inv = inventory(("2026-10-26", P, W, 1), (START, P, W, 1), (END, P, W, 1))

    assert latest_snapshot_dates(inv) == (pd.Timestamp(START), pd.Timestamp(END))


def test_one_snapshot_date_is_an_error():
    with pytest.raises(ValueError, match="two snapshot dates"):
        latest_snapshot_dates(inventory((END, P, W, 1)))


def _write(tmp_path, inv, sold, po):
    paths = {}

    for name, frame in (("inventory", inv), ("sales", sold), ("po", po)):
        paths[name] = tmp_path / f"{name}.csv"
        frame.to_csv(paths[name], index=False)

    return [
        "--inventory", str(paths["inventory"]),
        "--sales", str(paths["sales"]),
        "--purchase-orders", str(paths["po"]),
        "--out", str(tmp_path / "flags.csv"),
    ]  # fmt: skip


def test_main_writes_the_flags_and_logs_to_mlflow(tmp_path, monkeypatch, capsys):
    logged = {}
    monkeypatch.setattr(
        stock_shrinkage,
        "safe_log_run",
        lambda name, **kwargs: logged.update(name=name, **kwargs),
    )

    code = main(_write(tmp_path, *pair(500, 380, sold=150, received=100)))

    assert code == 0
    assert pd.read_csv(tmp_path / "flags.csv").loc[0, "gap"] == 70
    assert "flagged: 1 (high 0, medium 1, low 0)" in capsys.readouterr().out
    assert logged["name"] == "stock-shrinkage"
    assert logged["severities"] == {"high": 0, "medium": 1, "low": 0}
    assert logged["metrics"]["pairs_checked"] == 1
    assert logged["metrics"]["units_unexplained"] == 70
    assert logged["params"]["shrink_min_units"] == 10
    assert logged["data_start"] == START
    assert logged["data_end"] == END
    assert "flags.csv" in logged["texts"]
    assert logged["tags"] == {"run_kind": "shrinkage"}


def test_main_with_one_snapshot_date_exits_2(tmp_path, capsys):
    inv = inventory((END, P, W, 5))
    code = main(_write(tmp_path, inv, sales(), NO_ORDERS))

    assert code == 2
    assert "two snapshot dates" in capsys.readouterr().err