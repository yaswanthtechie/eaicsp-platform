import streamlit as st

from dashboard.services.eta_service import predict_eta
from dashboard.services.anomaly_service import detect_anomaly


st.set_page_config(
    page_title="EAICSP ML Dashboard",
    layout="wide",
)

st.title("EAICSP ML Dashboard")
st.caption("Unified ETA Prediction and Anomaly Detection")


# ============================================================
# ETA PREDICTION
# ============================================================

st.header("ETA Prediction")

eta_col1, eta_col2 = st.columns(2)

with eta_col1:
    origin = st.text_input(
        "Origin",
        placeholder="e.g. sao paulo",
    )

    carrier = st.text_input(
        "Carrier",
        placeholder="e.g. carrier_1",
    )

with eta_col2:
    destination = st.text_input(
        "Destination",
        placeholder="e.g. rio de janeiro",
    )

    weight_kg = st.number_input(
        "Weight (kg)",
        min_value=0.0,
        value=1.0,
        step=0.1,
    )


if st.button("Predict ETA"):
    if (
        not origin.strip()
        or not destination.strip()
        or not carrier.strip()
    ):
        st.error(
            "Origin, destination, and carrier are required."
        )
    else:
        payload = {
            "origin": origin.strip(),
            "destination": destination.strip(),
            "carrier": carrier.strip(),
            "weight_kg": weight_kg,
        }

        try:
            result = predict_eta(payload)

            result_col1, result_col2, result_col3 = st.columns(3)

            with result_col1:
                st.metric(
                    "ETA (days)",
                    result["eta_days"],
                )

            with result_col2:
                st.metric(
                    "Lower Bound",
                    result["confidence_low"],
                )

            with result_col3:
                st.metric(
                    "Upper Bound",
                    result["confidence_high"],
                )

        except (ValueError, KeyError) as exc:
            st.error(
                f"ETA prediction failed: {exc}"
            )


st.divider()


# ============================================================
# ANOMALY DETECTION
# ============================================================

st.header("Anomaly Detection")

anomaly_col1, anomaly_col2 = st.columns(2)

with anomaly_col1:
    anomaly_model = st.selectbox(
        "Anomaly Model",
        options=[
            "lof",
            "iforest",
            "ocsvm",
        ],
        format_func=lambda model: {
            "lof": "Local Outlier Factor",
            "iforest": "Isolation Forest",
            "ocsvm": "One-Class SVM",
        }[model],
    )

    reading_id = st.number_input(
        "Reading ID",
        min_value=0,
        value=1,
        step=1,
    )

    temperature = st.number_input(
        "Temperature",
        value=25.0,
        step=0.1,
    )

with anomaly_col2:
    humidity = st.number_input(
        "Humidity",
        value=50.0,
        step=0.1,
    )

    stock_count = st.number_input(
        "Stock Count",
        min_value=0,
        value=100,
        step=1,
    )


if st.button("Detect Anomaly"):
    anomaly_payload = {
        "model": anomaly_model,
        "reading": {
            "reading_id": int(reading_id),
            "temperature": temperature,
            "humidity": humidity,
            "stock_count": int(stock_count),
        },
    }

    try:
        result = detect_anomaly(
            anomaly_payload
        )

        result_col1, result_col2, result_col3 = st.columns(3)

        with result_col1:
            st.metric(
                "Status",
                "ANOMALY"
                if result["is_anomaly"]
                else "NORMAL",
            )

        with result_col2:
            st.metric(
                "Anomaly Score",
                round(result["score"], 4),
            )

        with result_col3:
            st.metric(
                "Production Threshold",
                round(
                    result["production_threshold"],
                    4,
                ),
            )

        st.write(
            f"**Model:** {result['model_label']}"
        )

        st.write(
            f"**Model Version:** {result['model_version']}"
        )

        if result["reasons"]:
            st.subheader("Top Anomaly Factors")

            for reason in result["reasons"]:
                st.write(
                    f"- **{reason['feature']}** — "
                    f"{reason['contribution']:.4f}"
                )

    except Exception as exc:
        st.error(
            f"Anomaly detection failed: {exc}"
        )