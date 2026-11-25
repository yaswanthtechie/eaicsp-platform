import math
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.auth import verify_token
from app.core.config import settings
from app.database import get_db
from app.main import app
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.sales_history import SalesHistory
from app.models.supplier import Supplier
from app.services.reorder_service import calculate_reorder_point
from app.services.safety_stock_service import (
    calculate_demand_statistics,
    calculate_lead_time_statistics,
    calculate_safety_stock_formula,
    calculate_service_level_safety_stock,
    calculate_z_score,
    classify_abc_by_revenue,
    classify_xyz_by_cv,
    get_abc_tier_from_cumulative_share,
    get_service_level_and_z,
)
from tests.conftest import ROLE_PERMISSIONS, override_get_db

# ============================================================
# 1. FORMULA & MATHEMATICAL CALCULATIONS
# ============================================================


def test_safety_stock_formula_known_inputs():
    """Verify formula with textbook supply chain inputs: SS = z * sqrt(LT*sd_D^2 + avg_D^2*sd_LT^2)."""
    # Given:
    avg_demand = 100.0
    sd_demand = 10.0
    avg_lead_time = 4.0
    sd_lead_time = 1.0
    z = 1.6448536269514722  # 95% service level

    # Expected:
    # term1 = 4.0 * 100.0 = 400.0
    # term2 = 10000.0 * 1.0 = 10000.0
    # sqrt(10400.0) = 101.9803902718557
    # SS = 1.6448536269514722 * 101.9803902718557 = 167.742807...
    calculated = calculate_safety_stock_formula(
        avg_demand=avg_demand,
        sd_demand=sd_demand,
        avg_lead_time=avg_lead_time,
        sd_lead_time=sd_lead_time,
        z=z,
    )
    assert math.isclose(calculated, 167.7428, abs_tol=1e-3)


def test_safety_stock_formula_zero_lead_time_variance():
    """When sd_lead_time == 0, formula simplifies to classic: SS = z * sd_D * sqrt(LT)."""
    avg_demand = 50.0
    sd_demand = 5.0
    avg_lead_time = 9.0
    sd_lead_time = 0.0
    z = 2.0

    # Expected: 2.0 * 5.0 * sqrt(9.0) = 2.0 * 5.0 * 3.0 = 30.0
    calculated = calculate_safety_stock_formula(
        avg_demand=avg_demand,
        sd_demand=sd_demand,
        avg_lead_time=avg_lead_time,
        sd_lead_time=sd_lead_time,
        z=z,
    )
    assert calculated == 30.0


def test_safety_stock_formula_zero_demand_variance():
    """When sd_demand == 0, formula simplifies to: SS = z * avg_D * sd_LT."""
    avg_demand = 40.0
    sd_demand = 0.0
    avg_lead_time = 4.0
    sd_lead_time = 1.5
    z = 1.5

    # Expected: 1.5 * 40.0 * 1.5 = 90.0
    calculated = calculate_safety_stock_formula(
        avg_demand=avg_demand,
        sd_demand=sd_demand,
        avg_lead_time=avg_lead_time,
        sd_lead_time=sd_lead_time,
        z=z,
    )
    assert calculated == 90.0


def test_safety_stock_formula_zero_or_negative_inputs():
    """Zero inputs return 0.0 without errors."""
    assert (
        calculate_safety_stock_formula(
            avg_demand=0.0,
            sd_demand=0.0,
            avg_lead_time=0.0,
            sd_lead_time=0.0,
            z=1.65,
        )
        == 0.0
    )


def test_calculate_z_score():
    """Check standard normal quantiles and boundary validations."""
    assert math.isclose(calculate_z_score(0.95), 1.6449, abs_tol=1e-4)
    assert math.isclose(calculate_z_score(0.98), 2.0537, abs_tol=1e-4)
    assert math.isclose(calculate_z_score(0.90), 1.2816, abs_tol=1e-4)

    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        calculate_z_score(0.0)

    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        calculate_z_score(1.0)

    with pytest.raises(ValueError, match="strictly between 0 and 1"):
        calculate_z_score(-0.1)


# ============================================================
# 2. ABC AND XYZ CLASSIFICATION BOUNDARIES
# ============================================================


def test_abc_classification_boundaries():
    """Test ABC revenue cumulative share boundary thresholds."""
    # A <= 0.80, B <= 0.95, C > 0.95
    assert get_abc_tier_from_cumulative_share(0.0) == "A"
    assert get_abc_tier_from_cumulative_share(0.50) == "A"
    assert get_abc_tier_from_cumulative_share(0.80) == "A"
    assert get_abc_tier_from_cumulative_share(0.80001) == "B"
    assert get_abc_tier_from_cumulative_share(0.90) == "B"
    assert get_abc_tier_from_cumulative_share(0.95) == "B"
    assert get_abc_tier_from_cumulative_share(0.95001) == "C"
    assert get_abc_tier_from_cumulative_share(1.00) == "C"


def test_classify_abc_by_revenue_ranking(db_session):
    """Test revenue ranking when Product.abc_class is not pre-set.
    Top revenue SKU (e.g. 85% of total revenue) must be classified as 'A'.
    """
    sku_top = "SKU-000120"
    sku_mid = "SKU-000121"
    sku_low = "SKU-000122"
    wh_id = "WH-BLR-01"
    today = date.today()

    # Top SKU: 85,000 revenue
    db_session.add(
        Product(
            sku_id=sku_top,
            name="Top SKU",
            category="Cat",
            unit_price=100.0,
            unit_cost=50.0,
        )
    )
    db_session.add(
        SalesHistory(
            sku_id=sku_top,
            warehouse_id=wh_id,
            sale_date=today,
            quantity_sold=850,
        )
    )

    # Mid SKU: 11,000 revenue (prior cumulative = 85%, so in B tier 80%-95%)
    db_session.add(
        Product(
            sku_id=sku_mid,
            name="Mid SKU",
            category="Cat",
            unit_price=100.0,
            unit_cost=50.0,
        )
    )
    db_session.add(
        SalesHistory(
            sku_id=sku_mid,
            warehouse_id=wh_id,
            sale_date=today,
            quantity_sold=110,
        )
    )

    # Low SKU: 4,000 revenue (prior cumulative = 96%, so in C tier > 95%)
    db_session.add(
        Product(
            sku_id=sku_low,
            name="Low SKU",
            category="Cat",
            unit_price=100.0,
            unit_cost=50.0,
        )
    )
    db_session.add(
        SalesHistory(
            sku_id=sku_low,
            warehouse_id=wh_id,
            sale_date=today,
            quantity_sold=40,
        )
    )

    db_session.commit()

    assert classify_abc_by_revenue(db=db_session, sku_id=sku_top) == "A"
    assert classify_abc_by_revenue(db=db_session, sku_id=sku_mid) == "B"
    assert classify_abc_by_revenue(db=db_session, sku_id=sku_low) == "C"


def test_xyz_classification_boundaries():
    """Test XYZ demand CV (sd/mean) boundary thresholds."""
    # X <= 0.50, Y <= 1.00, Z > 1.00
    assert classify_xyz_by_cv(0.0) == "X"
    assert classify_xyz_by_cv(0.25) == "X"
    assert classify_xyz_by_cv(0.50) == "X"
    assert classify_xyz_by_cv(0.50001) == "Y"
    assert classify_xyz_by_cv(0.75) == "Y"
    assert classify_xyz_by_cv(1.00) == "Y"
    assert classify_xyz_by_cv(1.00001) == "Z"
    assert classify_xyz_by_cv(3.50) == "Z"


def test_service_level_matrix_and_z():
    """Verify combined ABC-XYZ service levels and corresponding z-scores."""
    sl_ax, z_ax = get_service_level_and_z("A", "X")
    assert sl_ax == 0.98
    assert math.isclose(z_ax, 2.0537, abs_tol=1e-3)

    sl_cz, z_cz = get_service_level_and_z("C", "Z")
    assert sl_cz == 0.90
    assert math.isclose(z_cz, 1.2816, abs_tol=1e-3)

    sl_bx, z_bx = get_service_level_and_z("B", "X")
    assert sl_bx == 0.95
    assert math.isclose(z_bx, 1.6449, abs_tol=1e-3)


# ============================================================
# 3. DEMAND AND LEAD TIME STATISTICS
# ============================================================


def test_demand_statistics_and_history_thresholds(db_session):
    """Test average daily demand, standard deviation, and short history flag."""
    sku_id = "SKU-000101"
    wh_id = "WH-BLR-01"
    today = date.today()

    # Empty history
    empty_stats = calculate_demand_statistics(
        db_session, sku_id, wh_id, as_of_date=today
    )
    assert empty_stats["has_sufficient_history"] is False
    assert empty_stats["avg_daily_demand"] == 0.0

    # Short history (only 3 days, minimum is 14)
    for offset in range(3):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=10,
            )
        )
    db_session.commit()

    short_stats = calculate_demand_statistics(
        db_session, sku_id, wh_id, as_of_date=today
    )
    assert short_stats["has_sufficient_history"] is False
    assert short_stats["observed_days"] == 3

    # Now add remaining days up to 20 days of sales
    for offset in range(3, 20):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=10 if offset % 2 == 0 else 20,
            )
        )
    db_session.commit()

    full_stats = calculate_demand_statistics(
        db_session, sku_id, wh_id, as_of_date=today
    )
    assert full_stats["has_sufficient_history"] is True
    assert full_stats["observed_days"] == 20
    assert full_stats["avg_daily_demand"] > 0
    assert full_stats["sd_daily_demand"] > 0
    assert full_stats["cv"] > 0


def test_lead_time_statistics_from_received_pos(db_session):
    """Test lead time statistics computed strictly from Received POs."""
    sku_id = "SKU-000102"
    wh_id = "WH-BLR-01"
    supplier_id = "SUP-00001"
    base_date = date.today() - timedelta(days=60)

    # Add 3 Received POs: lead times 5, 7, 6 days -> mean=6.0, stdev=1.0
    lead_time_days = [5, 7, 6]
    for idx, lt in enumerate(lead_time_days, start=1):
        o_date = base_date + timedelta(days=idx * 10)
        r_date = o_date + timedelta(days=lt)
        db_session.add(
            PurchaseOrder(
                po_id=f"PO-2026-00000{idx}",
                sku_id=sku_id,
                warehouse_id=wh_id,
                supplier_id=supplier_id,
                quantity=100,
                unit_cost=10.0,
                expected_cost=1000.0,
                status="received",
                order_date=o_date,
                received_date=r_date,
            )
        )

    # Add 1 draft PO (should be excluded)
    db_session.add(
        PurchaseOrder(
            po_id="PO-2026-000009",
            sku_id=sku_id,
            warehouse_id=wh_id,
            supplier_id=supplier_id,
            quantity=100,
            unit_cost=10.0,
            expected_cost=1000.0,
            status="draft",
            order_date=base_date,
            received_date=base_date + timedelta(days=20),
        )
    )
    db_session.commit()

    stats = calculate_lead_time_statistics(
        db=db_session, sku_id=sku_id, supplier_id=supplier_id
    )
    assert stats["has_sufficient_history"] is True
    assert stats["po_count"] == 3
    assert stats["avg_lead_time"] == 6.0
    assert math.isclose(stats["sd_lead_time"], 1.0, abs_tol=1e-4)
    assert stats["lead_time_source"] == "po_history_sku"


def test_lead_time_statistics_zero_variance(db_session):
    """Test lead time statistics when all received POs have identical lead time."""
    sku_id = "SKU-000103"
    wh_id = "WH-BLR-01"
    supplier_id = "SUP-00002"
    base_date = date.today() - timedelta(days=40)

    for idx in range(1, 4):
        o_date = base_date + timedelta(days=idx * 8)
        r_date = o_date + timedelta(days=4)  # exactly 4 days each
        db_session.add(
            PurchaseOrder(
                po_id=f"PO-2026-00001{idx}",
                sku_id=sku_id,
                warehouse_id=wh_id,
                supplier_id=supplier_id,
                quantity=50,
                unit_cost=15.0,
                expected_cost=750.0,
                status="received",
                order_date=o_date,
                received_date=r_date,
            )
        )
    db_session.commit()

    stats = calculate_lead_time_statistics(
        db=db_session, sku_id=sku_id, supplier_id=supplier_id
    )
    assert stats["has_sufficient_history"] is True
    assert stats["avg_lead_time"] == 4.0
    assert stats["sd_lead_time"] == 0.0


def test_lead_time_statistics_insufficient_history(db_session):
    """When fewer than 3 POs exist, static lead time source is used with sd_lead_time = 0."""
    sku_id = "SKU-000104"
    supplier_id = "SUP-00003"

    stats = calculate_lead_time_statistics(
        db=db_session, sku_id=sku_id, supplier_id=supplier_id
    )
    assert stats["has_sufficient_history"] is False
    assert stats["lead_time_source"] in (
        "static_lead_time",
        "inventory_lead_time",
        "supplier_lead_time",
        "default_config",
    )
    assert stats["sd_lead_time"] == 0.0


def test_service_level_safety_stock_sufficient_demand_short_po_history(
    db_session,
):
    """When demand history is sufficient but PO history is short, uses static lead time with sd_LT = 0."""
    sku_id = "SKU-000123"
    wh_id = "WH-BLR-01"
    today = date.today()

    db_session.add(
        Product(
            sku_id=sku_id,
            name="Short PO Item",
            category="Cat",
            unit_price=100.0,
            unit_cost=50.0,
            abc_class="A",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            product_name="Short PO Item",
            warehouse_id=wh_id,
            category="Cat",
            quantity_on_hand=50,
            lead_time_days=9,
            safety_stock=10,
            warehouse_type="local",
        )
    )
    # 20 days of sales history (sufficient)
    for offset in range(20):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=10,
            )
        )
    # 0 POs (short PO history)
    db_session.commit()

    result = calculate_service_level_safety_stock(
        db=db_session,
        sku_id=sku_id,
        warehouse_id=wh_id,
        as_of_date=today,
    )
    assert result["is_fallback"] is False
    assert result["method"] == "statistical_static_lead_time"
    assert result["inputs_used"]["sd_lead_time_days"] == 0.0
    assert result["inputs_used"]["avg_lead_time_days"] == 9.0
    assert result["inputs_used"]["lead_time_source"] == "inventory_lead_time"


# ============================================================
# 4. FULL SERVICE CALCULATION & FALLBACK
# ============================================================


def test_service_level_safety_stock_statistical(db_session):
    """Full statistical safety stock calculation when sufficient history exists."""
    sku_id = "SKU-000105"
    wh_id = "WH-BLR-01"
    supplier_id = "SUP-00004"
    today = date.today()

    db_session.add(
        Supplier(
            supplier_id=supplier_id,
            supplier_name="Alpha Supplies",
            sku_id=sku_id,
            unit_cost=60.0,
            lead_time_days=5,
        )
    )
    db_session.add(
        Product(
            sku_id=sku_id,
            name="Precision Widget",
            category="Widgets",
            unit_price=100.0,
            unit_cost=60.0,
            abc_class="A",
            supplier_id=supplier_id,
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            product_name="Precision Widget",
            warehouse_id=wh_id,
            category="Widgets",
            quantity_on_hand=50,
            lead_time_days=5,
            safety_stock=10,
            warehouse_type="local",
        )
    )

    # 20 days of sales history
    for offset in range(20):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=10 if offset % 2 == 0 else 12,
            )
        )

    # 3 received POs with lead times 4, 6, 5
    for idx, lt in enumerate([4, 6, 5], start=1):
        o_date = today - timedelta(days=40 + idx * 5)
        db_session.add(
            PurchaseOrder(
                po_id=f"PO-2026-00002{idx}",
                sku_id=sku_id,
                warehouse_id=wh_id,
                supplier_id=supplier_id,
                quantity=100,
                unit_cost=60.0,
                expected_cost=6000.0,
                status="received",
                order_date=o_date,
                received_date=o_date + timedelta(days=lt),
            )
        )
    db_session.commit()

    result = calculate_service_level_safety_stock(
        db=db_session,
        sku_id=sku_id,
        warehouse_id=wh_id,
        as_of_date=today,
    )

    assert result["method"] == "statistical"
    assert result["is_fallback"] is False
    assert result["fallback_reason"] is None
    assert result["abc_class"] == "A"
    assert result["xyz_class"] in ("X", "Y", "Z")
    assert result["safety_stock"] > 0
    assert result["current_safety_stock"] == 10
    assert result["calculated_safety_stock"] > 0
    assert result["inputs_used"]["lead_time_po_count"] == 3


def test_service_level_safety_stock_short_history_fallback(db_session):
    """Falls back to current safety stock when history is below minimum."""
    sku_id = "SKU-000106"
    wh_id = "WH-BLR-01"
    today = date.today()

    db_session.add(
        Product(
            sku_id=sku_id,
            name="Low History Item",
            category="Items",
            unit_price=50.0,
            unit_cost=30.0,
            abc_class="C",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            product_name="Low History Item",
            warehouse_id=wh_id,
            category="Items",
            quantity_on_hand=30,
            lead_time_days=4,
            safety_stock=18,
            warehouse_type="local",
        )
    )
    # Only 2 days of sales history (insufficient)
    for offset in range(2):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=5,
            )
        )
    db_session.commit()

    result = calculate_service_level_safety_stock(
        db=db_session,
        sku_id=sku_id,
        warehouse_id=wh_id,
        as_of_date=today,
    )

    assert result["method"] == "fallback"
    assert result["is_fallback"] is True
    assert "Insufficient demand history" in str(result["fallback_reason"])
    assert result["safety_stock"] == 18
    assert result["current_safety_stock"] == 18
    assert result["xyz_class"] == "N/A"
    assert result["abc_xyz_class"] == "N/A"
    assert result["service_level"] == 0.0
    assert result["z_score"] == 0.0


# ============================================================
# 5. REORDER POINT INTEGRATION BEHIND CONFIG FLAG
# ============================================================


def test_reorder_logic_behind_config_flag(db_session, monkeypatch):
    """When flag is off, existing formula is used; when on, dynamic safety stock is used."""
    sku_id = "SKU-000107"
    wh_id = "WH-BLR-01"
    today = date.today()

    db_session.add(
        Product(
            sku_id=sku_id,
            name="Switch Widget",
            category="Switches",
            unit_price=100.0,
            unit_cost=50.0,
            abc_class="A",
        )
    )
    inv = Inventory(
        sku_id=sku_id,
        product_name="Switch Widget",
        warehouse_id=wh_id,
        category="Switches",
        quantity_on_hand=40,
        lead_time_days=4,
        safety_stock=20,
        warehouse_type="local",
    )
    db_session.add(inv)

    # 20 days of sales history (sufficient)
    for offset in range(20):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=15 if offset % 2 == 0 else 5,
            )
        )
    db_session.commit()

    # Case A: Flag OFF -> uses calculate_tier_safety_stock
    # Tier A multiplier is 1.5 -> base safety stock 20 * 1.5 = 30
    monkeypatch.setattr(settings, "USE_DYNAMIC_SAFETY_STOCK", False)
    calc_off = calculate_reorder_point(db=db_session, inventory=inv)
    assert calc_off["adjusted_safety_stock"] == 30

    # Case B: Flag ON with sufficient demand history -> uses statistical formula
    monkeypatch.setattr(settings, "USE_DYNAMIC_SAFETY_STOCK", True)
    calc_on = calculate_reorder_point(db=db_session, inventory=inv)
    assert calc_on["adjusted_safety_stock"] != calc_off["adjusted_safety_stock"]
    assert calc_on["adjusted_safety_stock"] == 18
    assert calc_on["reorder_point"] == 58

    # Case C: Flag ON with insufficient history -> falls back to current calculation preserving ABC tier multiplier
    sku_fallback = "SKU-000124"
    inv_fallback = Inventory(
        sku_id=sku_fallback,
        product_name="Fallback Widget",
        warehouse_id=wh_id,
        category="Switches",
        quantity_on_hand=40,
        lead_time_days=4,
        safety_stock=20,
        warehouse_type="local",
    )
    db_session.add(
        Product(
            sku_id=sku_fallback,
            name="Fallback Widget",
            category="Switches",
            unit_price=100.0,
            unit_cost=50.0,
            abc_class="A",
        )
    )
    db_session.add(inv_fallback)
    # Only 3 days of sales history (insufficient)
    for offset in range(3):
        db_session.add(
            SalesHistory(
                sku_id=sku_fallback,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=10,
            )
        )
    db_session.commit()

    calc_fallback = calculate_reorder_point(db=db_session, inventory=inv_fallback)
    # Fallback must preserve the A-tier multiplier: 20 * 1.5 = 30
    assert calc_fallback["adjusted_safety_stock"] == 30


def test_reorder_flag_off_preserves_volume_tier_ignoring_stored_abc_class(
    db_session, monkeypatch
):
    """
    Item A verification: When flag is OFF, reorder logic strictly uses classify_skus volume tier
    and ignores any stored Product.abc_class, preserving develop behavior.
    """
    sku_id = "SKU-000130"
    wh_id = "WH-BLR-01"
    today = date.today()

    # Product stored with abc_class="C"
    db_session.add(
        Product(
            sku_id=sku_id,
            name="Volume Leader Item",
            category="Switches",
            unit_price=10.0,
            unit_cost=5.0,
            abc_class="C",
        )
    )
    inv = Inventory(
        sku_id=sku_id,
        product_name="Volume Leader Item",
        warehouse_id=wh_id,
        category="Switches",
        quantity_on_hand=50,
        lead_time_days=4,
        safety_stock=20,
        warehouse_type="local",
    )
    db_session.add(inv)

    # 30 days of high sales volume -> volume tier A in classify_skus
    for offset in range(30):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=100,
            )
        )
    db_session.commit()

    monkeypatch.setattr(settings, "USE_DYNAMIC_SAFETY_STOCK", False)
    calc = calculate_reorder_point(db=db_session, inventory=inv)

    # With flag OFF, volume tier A is used (1.5x multiplier), giving 20 * 1.5 = 30
    assert calc["abc_tier"] == "A"
    assert calc["adjusted_safety_stock"] == 30
    assert calc["reorder_point"] == int(calc["rolling_avg_demand"] * 4 + 30)


def test_reorder_and_endpoint_agree_on_revenue_abc_when_flag_on(
    client, db_session, monkeypatch
):
    """
    Item B verification: When flag is ON, both reorder (with or without context)
    and the API endpoint use revenue ABC ranking (e.g. high price low volume SKU is A).
    """
    from app.services.reorder_service import build_reorder_context

    sku_high_rev = "SKU-000131"
    sku_low_rev = "SKU-000132"
    wh_id = "WH-BLR-01"
    today = date.today()

    # High unit price item (no explicit abc_class)
    db_session.add(
        Product(
            sku_id=sku_high_rev,
            name="Expensive Low Volume Item",
            category="Enterprise",
            unit_price=10000.0,
            unit_cost=5000.0,
            abc_class=None,
        )
    )
    inv_high = Inventory(
        sku_id=sku_high_rev,
        product_name="Expensive Low Volume Item",
        warehouse_id=wh_id,
        category="Enterprise",
        quantity_on_hand=20,
        lead_time_days=3,
        safety_stock=10,
        warehouse_type="local",
    )
    db_session.add(inv_high)

    # Cheap high volume item
    db_session.add(
        Product(
            sku_id=sku_low_rev,
            name="Cheap High Volume Item",
            category="Accessories",
            unit_price=1.0,
            unit_cost=0.5,
            abc_class=None,
        )
    )
    inv_low = Inventory(
        sku_id=sku_low_rev,
        product_name="Cheap High Volume Item",
        warehouse_id=wh_id,
        category="Accessories",
        quantity_on_hand=500,
        lead_time_days=2,
        safety_stock=20,
        warehouse_type="local",
    )
    db_session.add(inv_low)

    # High rev SKU has 2 units/day for 20 days -> revenue = 20 * 2 * 10000 = 400,000 (> 99% total revenue)
    for offset in range(20):
        db_session.add(
            SalesHistory(
                sku_id=sku_high_rev,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=2,
            )
        )
        # Low rev SKU has 50 units/day for 20 days -> revenue = 20 * 50 * 1 = 1,000
        db_session.add(
            SalesHistory(
                sku_id=sku_low_rev,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=50,
            )
        )
    db_session.commit()

    monkeypatch.setattr(settings, "USE_DYNAMIC_SAFETY_STOCK", True)

    # 1. API endpoint
    res = client.get(
        f"/api/v1/inventory/{sku_high_rev}/{wh_id}/safety-stock",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res.status_code == 200
    api_data = res.json()
    assert api_data["abc_class"] == "A"

    # 2. Reorder calculation with context
    context = build_reorder_context(db=db_session)
    assert context["revenue_classifications"].get(sku_high_rev) == "A"
    calc_ctx = calculate_reorder_point(
        db=db_session, inventory=inv_high, context=context
    )
    assert calc_ctx["adjusted_safety_stock"] == api_data["safety_stock"]

    # 3. Reorder calculation without context
    calc_no_ctx = calculate_reorder_point(db=db_session, inventory=inv_high)
    assert calc_no_ctx["adjusted_safety_stock"] == api_data["safety_stock"]


# ============================================================
# 6. API ENDPOINT AND PERMISSIONS
# ============================================================


def test_safety_stock_api_endpoint(client, db_session):
    """Test GET /{sku_id}/{warehouse_id}/safety-stock returns 200 with full schema."""
    sku_id = "SKU-000108"
    wh_id = "WH-BLR-01"

    db_session.add(
        Product(
            sku_id=sku_id,
            name="API Test SKU",
            category="Electronics",
            unit_price=200.0,
            unit_cost=120.0,
            abc_class="B",
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            product_name="API Test SKU",
            warehouse_id=wh_id,
            category="Electronics",
            quantity_on_hand=100,
            lead_time_days=6,
            safety_stock=25,
            warehouse_type="local",
        )
    )
    db_session.commit()

    # Primary route
    res = client.get(
        f"/api/v1/inventory/{sku_id}/{wh_id}/safety-stock",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sku_id"] == sku_id
    assert data["warehouse_id"] == wh_id
    assert data["abc_class"] == "B"
    assert data["xyz_class"] == "N/A"
    assert data["abc_xyz_class"] == "N/A"
    assert data["service_level"] == 0.0
    assert data["z_score"] == 0.0
    assert data["method"] == "fallback"
    assert data["is_fallback"] is True
    assert "inputs_used" in data
    assert data["current_safety_stock"] == 25
    # Tier B multiplier is 1.2: 25 * 1.2 = 30
    assert data["safety_stock"] == 30
    assert data["calculated_safety_stock"] == 30.0

    # Alias route: /safety-stock/{sku_id}/{warehouse_id}
    res_alias = client.get(
        f"/api/v1/inventory/safety-stock/{sku_id}/{wh_id}",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res_alias.status_code == 200
    assert res_alias.json() == data


def test_safety_stock_api_endpoint_statistical_with_sufficient_history(
    client, db_session
):
    """Test API endpoint with sufficient demand and PO history returns method='statistical' and exact number."""
    sku_id = "SKU-000133"
    wh_id = "WH-BLR-01"
    sup_id = "SUP-00101"
    today = date.today()

    db_session.add(
        Product(
            sku_id=sku_id,
            name="Statistical API SKU",
            category="Electronics",
            unit_price=200.0,
            unit_cost=100.0,
            abc_class="A",
            supplier_id=sup_id,
        )
    )
    db_session.add(
        Inventory(
            sku_id=sku_id,
            product_name="Statistical API SKU",
            warehouse_id=wh_id,
            category="Electronics",
            quantity_on_hand=100,
            lead_time_days=4,
            safety_stock=20,
            warehouse_type="local",
        )
    )
    # 20 days of sales history (mean = 10, sd = 5.12989, CV = 0.513 -> class AY, SL = 0.96)
    for offset in range(20):
        db_session.add(
            SalesHistory(
                sku_id=sku_id,
                warehouse_id=wh_id,
                sale_date=today - timedelta(days=offset),
                quantity_sold=15 if offset % 2 == 0 else 5,
            )
        )
    # 3 received POs with fixed 4 days lead time (mean LT = 4, sd LT = 0)
    for po_idx in range(3):
        db_session.add(
            PurchaseOrder(
                po_id=f"PO-2026-00013{po_idx}",
                sku_id=sku_id,
                warehouse_id=wh_id,
                supplier_id=sup_id,
                quantity=100,
                unit_cost=100.0,
                expected_cost=10000.0,
                order_date=today - timedelta(days=20 + po_idx * 5),
                received_date=today - timedelta(days=16 + po_idx * 5),
                status="Received",
            )
        )
    db_session.commit()

    res = client.get(
        f"/api/v1/inventory/{sku_id}/{wh_id}/safety-stock",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["method"] == "statistical"
    assert data["is_fallback"] is False
    assert data["fallback_reason"] is None
    assert data["abc_class"] == "A"
    assert data["xyz_class"] == "Y"
    assert data["abc_xyz_class"] == "AY"
    assert data["service_level"] == 0.96
    # Exact safety stock formula value: ceil(1.7507 * sqrt(4 * 5.1299^2 + 0)) = 18
    assert data["safety_stock"] == 18
    assert data["current_safety_stock"] == 20


def test_safety_stock_api_404_not_found(client):
    """Calling safety stock on non-existent inventory returns 404."""
    res = client.get(
        "/api/v1/inventory/SKU-999999/WH-BLR-01/safety-stock",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Inventory not found"


def test_safety_stock_api_weeks_validation(client, db_session):
    """Weeks parameter bounds validation: < 2 and > 104 return 422 Unprocessable Entity."""
    sku_id = "SKU-000108"
    wh_id = "WH-BLR-01"

    # 1. Exceeding max weeks (104)
    res_large = client.get(
        f"/api/v1/inventory/{sku_id}/{wh_id}/safety-stock?weeks=999999999999",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res_large.status_code == 422

    # 2. Below minimum weeks (2)
    res_small = client.get(
        f"/api/v1/inventory/{sku_id}/{wh_id}/safety-stock?weeks=1",
        headers={"Authorization": "Bearer warehouse-token"},
    )
    assert res_small.status_code == 422


def test_safety_stock_api_permissions(db_session):
    """Verify unauthorized roles get 403, missing token gets 401, procurement/warehouse gets 200."""
    sku_id = "SKU-000109"
    wh_id = "WH-BLR-01"

    db_session.add(
        Inventory(
            sku_id=sku_id,
            product_name="Auth Test Item",
            warehouse_id=wh_id,
            category="Testing",
            quantity_on_hand=10,
            lead_time_days=3,
            safety_stock=5,
            warehouse_type="local",
        )
    )
    db_session.commit()

    app.dependency_overrides[get_db] = override_get_db

    try:
        # 1. Missing token -> 401
        with TestClient(app) as anonymous_client:
            res_no_auth = anonymous_client.get(
                f"/api/v1/inventory/{sku_id}/{wh_id}/safety-stock"
            )
            assert res_no_auth.status_code == 401

        # 2. Supplier token (lacks inventory:read) -> 403
        async def _supplier_override():
            return {
                "valid": True,
                "role": "supplier",
                "user_id": 99,
                "permissions": ROLE_PERMISSIONS["supplier"],
            }

        app.dependency_overrides[verify_token] = _supplier_override
        with TestClient(app) as supplier_client:
            res_supplier = supplier_client.get(
                f"/api/v1/inventory/{sku_id}/{wh_id}/safety-stock",
                headers={"Authorization": "Bearer supplier-token"},
            )
            assert res_supplier.status_code == 403

        # 3. Procurement manager token (has inventory:read) -> 200
        async def _procurement_override():
            return {
                "valid": True,
                "role": "procurement_manager",
                "user_id": 10,
                "permissions": ROLE_PERMISSIONS["procurement_manager"],
            }

        app.dependency_overrides[verify_token] = _procurement_override
        with TestClient(app) as pm_client:
            res_pm = pm_client.get(
                f"/api/v1/inventory/{sku_id}/{wh_id}/safety-stock",
                headers={"Authorization": "Bearer pm-token"},
            )
            assert res_pm.status_code == 200
            assert res_pm.json()["sku_id"] == sku_id
    finally:
        app.dependency_overrides.clear()
