"""Read-only product and warehouse lists for the dashboard (R15 / #354)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Query, Session

from app.models.product import Product
from app.models.warehouse import Warehouse

# Same ceiling as `limit`, so one request cannot build a huge IN (...) clause.
MAX_IDS = 1000


def parse_ids(ids: str | None) -> list[str] | None:
    """Split the comma-separated `ids` filter.

    Returns None when no filter was given, and an empty list when the filter
    was given but holds no IDs (for example `?ids=`), which matches nothing.
    Raises ValueError when more than MAX_IDS IDs are given.
    """
    if ids is None:
        return None
    id_list = [value.strip() for value in ids.split(",") if value.strip()]
    if len(id_list) > MAX_IDS:
        raise ValueError(f"ids accepts at most {MAX_IDS} IDs, got {len(id_list)}")
    return id_list


def _page(
    query: Query[Any],
    key_column: Any,
    id_list: list[str] | None,
    limit: int,
    offset: int,
) -> tuple[list[Any], int]:
    if id_list is not None:
        if not id_list:
            return [], 0
        query = query.filter(key_column.in_(id_list))
    total = query.count()
    items = query.order_by(key_column).offset(offset).limit(limit).all()
    return items, total


def list_products(
    db: Session,
    *,
    ids: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Product], int]:
    return _page(db.query(Product), Product.sku_id, parse_ids(ids), limit, offset)


def list_warehouses(
    db: Session,
    *,
    ids: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Warehouse], int]:
    return _page(
        db.query(Warehouse),
        Warehouse.warehouse_id,
        parse_ids(ids),
        limit,
        offset,
    )
