import pandas as pd
import pytest

from src.route_insights import (
    build_route_insights,
    generate_route_findings,
    get_slowest_routes,
)


@pytest.fixture
def sample_datasets():
    orders = pd.DataFrame(
        {
            "order_id": [
                "o1",
                "o2",
                "o3",
                "o4",
            ],
            "customer_id": [
                "c1",
                "c2",
                "c3",
                "c4",
            ],
            "order_status": [
                "delivered",
                "delivered",
                "delivered",
                "delivered",
            ],
            "order_purchase_timestamp": [
                "2018-01-01",
                "2018-01-02",
                "2018-01-03",
                "2018-01-04",
            ],
            "order_delivered_customer_date": [
                "2018-01-11",
                "2018-01-14",
                "2018-01-21",
                "2018-01-22",
            ],
        }
    )

    customers = pd.DataFrame(
        {
            "customer_id": [
                "c1",
                "c2",
                "c3",
                "c4",
            ],
            "customer_city": [
                "rio de janeiro",
                "rio de janeiro",
                "curitiba",
                "curitiba",
            ],
            "customer_state": [
                "RJ",
                "RJ",
                "PR",
                "PR",
            ],
        }
    )

    sellers = pd.DataFrame(
        {
            "seller_id": [
                "s1",
                "s2",
            ],
            "seller_city": [
                "sao paulo",
                "sao paulo",
            ],
            "seller_state": [
                "SP",
                "SP",
            ],
        }
    )

    order_items = pd.DataFrame(
        {
            "order_id": [
                "o1",
                "o2",
                "o3",
                "o4",
            ],
            "seller_id": [
                "s1",
                "s1",
                "s2",
                "s2",
            ],
        }
    )

    return {
        "orders": orders,
        "customers": customers,
        "sellers": sellers,
        "order_items": order_items,
    }


def test_build_route_insights(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=1,
    )

    assert len(insights) == 2

    routes = set(insights["route"])

    assert "sao paulo -> rio de janeiro" in routes
    assert "sao paulo -> curitiba" in routes


def test_route_delivery_metrics(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=1,
    )

    rio_route = insights[
        insights["route"]
        == "sao paulo -> rio de janeiro"
    ].iloc[0]

    assert rio_route["order_count"] == 2
    assert rio_route["average_delivery_days"] == pytest.approx(
        11.0
    )


def test_route_delivery_std_is_calculated(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=1,
    )

    rio_route = insights[
        insights["route"]
        == "sao paulo -> rio de janeiro"
    ].iloc[0]

    # Delivery times are 10 and 12 days.
    assert rio_route["delivery_days_std"] == pytest.approx(
        1.41421356
    )


def test_single_order_route_std_is_zero():
    datasets = {
        "orders": pd.DataFrame(
            {
                "order_id": ["o1"],
                "customer_id": ["c1"],
                "order_status": ["delivered"],
                "order_purchase_timestamp": ["2018-01-01"],
                "order_delivered_customer_date": ["2018-01-11"],
            }
        ),
        "customers": pd.DataFrame(
            {
                "customer_id": ["c1"],
                "customer_city": ["rio de janeiro"],
                "customer_state": ["RJ"],
            }
        ),
        "sellers": pd.DataFrame(
            {
                "seller_id": ["s1"],
                "seller_city": ["sao paulo"],
                "seller_state": ["SP"],
            }
        ),
        "order_items": pd.DataFrame(
            {
                "order_id": ["o1"],
                "seller_id": ["s1"],
            }
        ),
    }

    insights = build_route_insights(
        datasets,
        min_orders=1,
    )

    assert len(insights) == 1
    assert insights.iloc[0]["delivery_days_std"] == pytest.approx(0.0)


def test_min_orders_filter(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=2,
    )

    assert len(insights) == 2
    assert all(insights["order_count"] >= 2)


def test_get_slowest_routes(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=1,
    )

    slowest = get_slowest_routes(
        insights,
        top_n=1,
    )

    assert len(slowest) == 1
    assert slowest.iloc[0]["route"] == (
        "sao paulo -> curitiba"
    )


def test_generate_route_findings(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=1,
    )

    findings = generate_route_findings(
        insights,
        top_n=2,
    )

    assert len(findings) == 2
    assert "average delivery time" in findings[0]
    assert "orders" in findings[0]


def test_route_finding_includes_network_median(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=1,
    )

    findings = generate_route_findings(
        insights,
        top_n=1,
    )

    assert "network median" in findings[0]
    assert "x the network median" in findings[0]


def test_consistently_slow_requires_low_variability():
    insights = pd.DataFrame(
        {
            "route": [
                "consistent slow",
                "erratic slow",
                "normal route",
            ],
            "order_count": [
                20,
                20,
                20,
            ],
            "average_delivery_days": [
                21.0,
                20.0,
                10.0,
            ],
            "delivery_days_std": [
                2.0,
                15.0,
                1.0,
            ],
        }
    )

    findings = generate_route_findings(
        insights,
        top_n=2,
    )

    assert any(
        "consistent slow" in finding
        and "(consistently slow)" in finding
        for finding in findings
    )

    assert any(
        "erratic slow" in finding
        and "(consistently slow)" not in finding
        for finding in findings
    )


def test_invalid_min_orders(sample_datasets):
    with pytest.raises(ValueError):
        build_route_insights(
            sample_datasets,
            min_orders=0,
        )


def test_invalid_top_n(sample_datasets):
    insights = build_route_insights(
        sample_datasets,
        min_orders=1,
    )

    with pytest.raises(ValueError):
        get_slowest_routes(
            insights,
            top_n=0,
        )