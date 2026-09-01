import pandas as pd
import pytest


@pytest.fixture
def sample_orders():
    """Minimal orders dataset compatible with features.py."""

    return pd.DataFrame(
        {
            "order_id": [
                "order_1",
                "order_2",
                "order_3",
            ],
            "customer_id": [
                "customer_1",
                "customer_2",
                "customer_3",
            ],
            "order_status": [
                "delivered",
                "delivered",
                "delivered",
            ],
            "order_purchase_timestamp": [
                "2018-01-01 10:00:00",
                "2018-01-02 11:00:00",
                "2018-01-03 12:00:00",
            ],
            "order_approved_at": [
                "2018-01-01 10:10:00",
                "2018-01-02 11:10:00",
                "2018-01-03 12:10:00",
            ],
            "order_delivered_carrier_date": [
                "2018-01-02 10:00:00",
                "2018-01-03 11:00:00",
                "2018-01-04 12:00:00",
            ],
            "order_delivered_customer_date": [
                "2018-01-05 10:00:00",
                "2018-01-07 11:00:00",
                "2018-01-08 12:00:00",
            ],
            "order_estimated_delivery_date": [
                "2018-01-06 10:00:00",
                "2018-01-08 11:00:00",
                "2018-01-09 12:00:00",
            ],
        }
    )


@pytest.fixture
def sample_order_items():
    """
    Minimal order-items dataset.

    order_1 deliberately contains two items so that aggregation
    of item count, weight, volume, and freight can be tested.
    """

    return pd.DataFrame(
        {
            "order_id": [
                "order_1",
                "order_1",
                "order_2",
                "order_3",
            ],
            "order_item_id": [
                1,
                2,
                1,
                1,
            ],
            "product_id": [
                "product_1",
                "product_2",
                "product_3",
                "product_4",
            ],
            "seller_id": [
                "seller_1",
                "seller_2",
                "seller_1",
                "seller_2",
            ],
            "shipping_limit_date": [
                "2018-01-02 10:00:00",
                "2018-01-02 10:00:00",
                "2018-01-03 11:00:00",
                "2018-01-04 12:00:00",
            ],
            "price": [
                10.0,
                20.0,
                30.0,
                40.0,
            ],
            "freight_value": [
                2.0,
                3.0,
                4.0,
                5.0,
            ],
        }
    )


@pytest.fixture
def sample_products():
    """Minimal products dataset compatible with features.py."""

    return pd.DataFrame(
        {
            "product_id": [
                "product_1",
                "product_2",
                "product_3",
                "product_4",
            ],
            "product_category_name": [
                "electronics",
                "books",
                "toys",
                "furniture",
            ],
            "product_weight_g": [
                500,
                300,
                700,
                1000,
            ],
            "product_length_cm": [
                10,
                12,
                15,
                20,
            ],
            "product_height_cm": [
                5,
                6,
                8,
                10,
            ],
            "product_width_cm": [
                5,
                6,
                7,
                10,
            ],
        }
    )


@pytest.fixture
def sample_customers():
    """Minimal customers dataset compatible with features.py."""

    return pd.DataFrame(
        {
            "customer_id": [
                "customer_1",
                "customer_2",
                "customer_3",
            ],
            "customer_zip_code_prefix": [
                1000,
                2000,
                3000,
            ],
            "customer_city": [
                "city_a",
                "city_b",
                "city_c",
            ],
            "customer_state": [
                "SP",
                "RJ",
                "MG",
            ],
        }
    )


@pytest.fixture
def sample_sellers():
    """Minimal sellers dataset compatible with features.py."""

    return pd.DataFrame(
        {
            "seller_id": [
                "seller_1",
                "seller_2",
            ],
            "seller_zip_code_prefix": [
                4000,
                5000,
            ],
            "seller_city": [
                "seller_city_a",
                "seller_city_b",
            ],
            "seller_state": [
                "SP",
                "RJ",
            ],
        }
    )


@pytest.fixture
def sample_geolocation():
    """Minimal geolocation dataset compatible with features.py."""

    return pd.DataFrame(
        {
            "geolocation_zip_code_prefix": [
                1000,
                2000,
                3000,
                4000,
                5000,
            ],
            "geolocation_lat": [
                -23.5505,
                -22.9068,
                -19.9167,
                -23.5617,
                -22.9122,
            ],
            "geolocation_lng": [
                -46.6333,
                -43.1729,
                -43.9345,
                -46.6559,
                -43.2096,
            ],
            "geolocation_city": [
                "city_a",
                "city_b",
                "city_c",
                "seller_city_a",
                "seller_city_b",
            ],
            "geolocation_state": [
                "SP",
                "RJ",
                "MG",
                "SP",
                "RJ",
            ],
        }
    )


@pytest.fixture
def sample_category_translation():
    """Minimal category translation dataset."""

    return pd.DataFrame(
        {
            "product_category_name": [
                "electronics",
                "books",
                "toys",
                "furniture",
            ],
            "product_category_name_english": [
                "electronics",
                "books",
                "toys",
                "furniture",
            ],
        }
    )


@pytest.fixture
def sample_datasets(
    sample_orders,
    sample_order_items,
    sample_customers,
    sample_sellers,
    sample_products,
    sample_geolocation,
    sample_category_translation,
):
    """Complete synthetic dataset collection for feature tests."""

    return {
        "orders": sample_orders,
        "order_items": sample_order_items,
        "customers": sample_customers,
        "sellers": sample_sellers,
        "products": sample_products,
        "geolocation": sample_geolocation,
        "category_translation": sample_category_translation,
    }


@pytest.fixture
def sample_model_data():
    """
    Reusable model-ready dataset for training, evaluation,
    prediction, and MLflow tests.

    The dataset contains only model features in X_train and
    keeps delivery_days separately as the target.

    order_purchase_timestamp and
    order_estimated_delivery_date are evaluation metadata
    and are not model features.
    """

    X_train = pd.DataFrame(
        {
            "purchase_year": [
                2018, 2018, 2018, 2018,
                2018, 2018, 2018, 2018,
            ],
            "purchase_month": [
                1, 1, 2, 2,
                3, 3, 4, 4,
            ],
            "purchase_day_of_week": [
                0, 1, 2, 3,
                4, 5, 6, 0,
            ],
            "purchase_hour": [
                8, 9, 10, 11,
                12, 13, 14, 15,
            ],
            "origin_lat": [
                -23.55,
                -22.90,
                -19.92,
                -23.56,
                -23.55,
                -22.90,
                -19.92,
                -23.56,
            ],
            "origin_lng": [
                -46.63,
                -43.18,
                -43.94,
                -46.65,
                -46.63,
                -43.18,
                -43.94,
                -46.65,
            ],
            "destination_lat": [
                -23.56,
                -22.91,
                -19.93,
                -23.57,
                -23.57,
                -22.92,
                -19.94,
                -23.58,
            ],
            "destination_lng": [
                -46.65,
                -43.20,
                -43.95,
                -46.66,
                -46.66,
                -43.21,
                -43.96,
                -46.67,
            ],
            "distance_km": [
                5.0,
                10.0,
                15.0,
                20.0,
                25.0,
                30.0,
                35.0,
                40.0,
            ],
            "item_count": [
                1,
                1,
                2,
                2,
                3,
                3,
                4,
                4,
            ],
            "total_weight_kg": [
                0.5,
                1.0,
                1.5,
                2.0,
                2.5,
                3.0,
                3.5,
                4.0,
            ],
            "total_volume_cm3": [
                100.0,
                200.0,
                300.0,
                400.0,
                500.0,
                600.0,
                700.0,
                800.0,
            ],
            "total_freight_value": [
                5.0,
                10.0,
                15.0,
                20.0,
                25.0,
                30.0,
                35.0,
                40.0,
            ],
            "product_category_name": [
                "electronics",
                "books",
                "toys",
                "furniture",
                "electronics",
                "books",
                "toys",
                "furniture",
            ],
        }
    )

    y_train = pd.Series(
        [
            5.0,
            8.0,
            11.0,
            15.0,
            20.0,
            25.0,
            30.0,
            35.0,
        ],
        name="delivery_days",
    )

    # ---------------------------------------------------------
    # Evaluation dataset
    # ---------------------------------------------------------
    X_test = X_train.iloc[
        [0, 2, 5, 7]
    ].copy()

    y_test = y_train.iloc[
        [0, 2, 5, 7]
    ].copy()

    # ---------------------------------------------------------
    # Training evaluation metadata
    # ---------------------------------------------------------
    train = X_train.copy()

    train[
        "delivery_days"
    ] = y_train.values

    train[
        "order_id"
    ] = [
        f"train_{i}"
        for i in range(len(train))
    ]

    train[
        "order_purchase_timestamp"
    ] = pd.date_range(
        "2018-01-01",
        periods=len(train),
        freq="D",
    )

    train[
        "order_estimated_delivery_date"
    ] = (
        train[
            "order_purchase_timestamp"
        ]
        + pd.Timedelta(days=10)
    )

    # ---------------------------------------------------------
    # Test evaluation metadata
    # ---------------------------------------------------------
    test = X_test.copy()

    test[
        "delivery_days"
    ] = y_test.values

    test[
        "order_id"
    ] = [
        "test_1",
        "test_2",
        "test_3",
        "test_4",
    ]

    test[
        "order_purchase_timestamp"
    ] = pd.date_range(
        "2018-05-01",
        periods=len(test),
        freq="D",
    )

    test[
        "order_estimated_delivery_date"
    ] = (
        test[
            "order_purchase_timestamp"
        ]
        + pd.Timedelta(days=10)
    )

    # ---------------------------------------------------------
    # Complete feature/evaluation dataset
    # ---------------------------------------------------------
    features = pd.concat(
        [
            train,
            test,
        ],
        ignore_index=True,
    )

    split_timestamp = test[
        "order_purchase_timestamp"
    ].min()

    return {
        "X_train": X_train,
        "y_train": y_train,
        "X_test": X_test,
        "y_test": y_test,
        "train": train,
        "test": test,
        "features": features,
        "split_timestamp": split_timestamp,
    }


@pytest.fixture
def trained_model_path(
    tmp_path,
    monkeypatch,
    sample_model_data,
):
    """
    Train a temporary ETA pipeline for prediction tests.

    Both the production model and prediction-interval
    calibration are stored in pytest's temporary directory.

    This prevents prediction tests from depending on the
    real production model or calibration artifacts.
    """

    from src import model_loader
    from src import train
    from src.train import train_model

    # ---------------------------------------------------------
    # 1. Get reusable model training data
    # ---------------------------------------------------------
    X_train = sample_model_data[
        "X_train"
    ]

    y_train = sample_model_data[
        "y_train"
    ]

    # ---------------------------------------------------------
    # 2. Temporary production model path
    # ---------------------------------------------------------
    model_path = (
        tmp_path
        / "eta_pipeline.joblib"
    )

    # ---------------------------------------------------------
    # 3. Temporary calibration path
    # ---------------------------------------------------------
    calibration_path = (
        tmp_path
        / "eta_prediction_interval.joblib"
    )

    # ---------------------------------------------------------
    # 4. Redirect training module paths
    # ---------------------------------------------------------
    monkeypatch.setattr(
        train,
        "MODEL_PATH",
        model_path,
    )

    monkeypatch.setattr(
        train,
        "CALIBRATION_MODEL_PATH",
        calibration_path,
    )

    # ---------------------------------------------------------
    # 5. Redirect model-loader paths
    # ---------------------------------------------------------
    monkeypatch.setattr(
        model_loader,
        "MODEL_PATH",
        model_path,
    )

    monkeypatch.setattr(
        model_loader,
        "CALIBRATION_MODEL_PATH",
        calibration_path,
    )

    # ---------------------------------------------------------
    # 6. Clear lazy-loaded caches
    # ---------------------------------------------------------
    model_loader._model = None
    model_loader._prediction_interval = None

    # ---------------------------------------------------------
    # 7. Train temporary model
    # ---------------------------------------------------------
    train_model(
        X_train,
        y_train,
    )

    # ---------------------------------------------------------
    # 8. Verify both artifacts exist
    # ---------------------------------------------------------
    assert model_path.exists()

    assert calibration_path.exists()

    # ---------------------------------------------------------
    # 9. Return production model path
    # ---------------------------------------------------------
    yield model_path

    # ---------------------------------------------------------
    # 10. Clean loader state
    # ---------------------------------------------------------
    model_loader._model = None
    model_loader._prediction_interval = None