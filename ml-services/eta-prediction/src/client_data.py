
"""Adapter for the R15 client shipment-history format."""

import logging
from pathlib import Path

import pandas as pd


logger = logging.getLogger(__name__)


REQUIRED_COLUMNS = [
    "shipment_id",
    "po_number",
    "origin_city",
    "destination_warehouse_code",
    "carrier_name",
    "dispatch_date",
    "planned_delivery_date",
    "actual_delivery_date",
]

OPTIONAL_COLUMNS = [
    "weight_kg",
    "volume_m3",
]

DATE_COLUMNS = [
    "dispatch_date",
    "planned_delivery_date",
    "actual_delivery_date",
]


def adapt_client_shipments(
    shipments: pd.DataFrame,
) -> pd.DataFrame:
    """
    Validate and normalize client shipment-history data.

    Optional weight and volume columns are added when absent.
    Duplicate shipment IDs are counted, logged, and resolved
    by keeping the latest dated occurrence.
    """

    if not isinstance(shipments, pd.DataFrame):
        raise TypeError("shipments must be a pandas DataFrame.")

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in shipments.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required shipment columns: {missing_columns}"
        )

    shipments = shipments.copy()

    # Keep the expected schema while preserving optional fields.
    for column in OPTIONAL_COLUMNS:
        if column not in shipments.columns:
            shipments[column] = pd.NA

    expected_columns = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
    shipments = shipments[expected_columns]

    # Validate shipment identifiers.
    if shipments["shipment_id"].isna().any():
        raise ValueError("shipment_id contains missing values.")

    shipments["shipment_id"] = (
        shipments["shipment_id"].astype(str).str.strip()
    )

    if shipments["shipment_id"].eq("").any():
        raise ValueError("shipment_id contains empty values.")

    # Normalize text fields without changing their meaning.
    text_columns = [
        "po_number",
        "origin_city",
        "destination_warehouse_code",
        "carrier_name",
    ]

    for column in text_columns:
        shipments[column] = (
            shipments[column]
            .astype("string")
            .str.strip()
        )

    # Strictly accept YYYY-MM-DD dates.
    # Invalid or missing dates become NaT; rows are retained.
    for column in DATE_COLUMNS:
        shipments[column] = pd.to_datetime(
            shipments[column],
            format="%Y-%m-%d",
            errors="coerce",
        )

    # Sort by shipment dates before resolving duplicate shipment IDs.
    # NaT values come first, allowing valid dated records to win.
    shipments = shipments.sort_values(
        ["dispatch_date", "actual_delivery_date"],
        kind="stable",
        na_position="first",
    )

    # Keep the latest dated record for each shipment ID.
    duplicate_mask = shipments["shipment_id"].duplicated(keep="last")
    duplicate_count = int(duplicate_mask.sum())

    if duplicate_count:
        logger.warning(
            "Dropping %d duplicate shipment_id rows (kept latest).",
            duplicate_count,
        )
        shipments = shipments.loc[~duplicate_mask].copy()

    shipments.attrs["duplicate_shipment_count"] = duplicate_count

    return shipments.reset_index(drop=True)


def load_client_shipments(
    file_path: str | Path,
) -> pd.DataFrame:
    """Load a client shipment-history CSV through the adapter."""

    file_path = Path(file_path)

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Client shipment file not found: {file_path}"
        )

    raw_shipments = pd.read_csv(file_path)

    return adapt_client_shipments(raw_shipments)
