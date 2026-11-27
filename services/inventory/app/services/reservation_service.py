import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.inventory import Inventory
from app.models.stock_reservation import StockReservation
from app.services.cache_service import invalidate_inventory_cache
from app.services.inventory_service import check_and_record_low_stock
from app.services.valuation_service import consume_cost_layers

logger = logging.getLogger(__name__)


class ReservationNotFoundError(LookupError):
    """Raised when the target inventory record or reservation does not exist."""


class InsufficientAvailableStockError(ValueError):
    """Raised when unreserved stock cannot satisfy the requested reservation."""


class ReservationStateError(ValueError):
    """Raised when a reservation transition is invalid for its current status."""


class ReservationExpiredError(ReservationStateError):
    """Raised when attempting to confirm an expired reservation."""


def _as_utc(dt: datetime) -> datetime:
    """Normalize naive/offset datetimes to timezone-aware UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _db_utc_now(db: Session, now: datetime) -> datetime:
    """SQLite strips tzinfo on DateTime columns; match dialect expectation in SQL predicates."""
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "sqlite":
        return now.astimezone(UTC).replace(tzinfo=None)
    return now.astimezone(UTC)


def _lock_inventory(
    db: Session,
    sku_id: str,
    warehouse_id: str,
) -> Inventory:
    """Acquire row-level lock on Inventory before reading availability or updating reservations."""
    item = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .with_for_update()
        .first()
    )
    if item is None:
        raise ReservationNotFoundError(
            f"Inventory not found for {sku_id}/{warehouse_id}"
        )
    return item


def _expire_stale_reservations_for_locked_inventory(
    db: Session,
    inventory: Inventory,
    now: datetime,
) -> int:
    """
    Mark expired ACTIVE reservations as EXPIRED and release their reserved_quantity.
    Caller must already hold the row lock on `inventory`.
    """
    db_now = _db_utc_now(db, now)
    candidates = (
        db.query(StockReservation)
        .filter(
            StockReservation.sku_id == inventory.sku_id,
            StockReservation.warehouse_id == inventory.warehouse_id,
            StockReservation.status == "ACTIVE",
            StockReservation.expires_at.isnot(None),
            StockReservation.expires_at <= db_now,
        )
        .order_by(StockReservation.reservation_id.asc())
        .with_for_update()
        .all()
    )

    expired_qty = 0
    for reservation in candidates:
        if (
            reservation.expires_at is not None
            and _as_utc(reservation.expires_at) <= now
        ):
            reservation.status = "EXPIRED"
            reservation.updated_at = now
            expired_qty += int(reservation.quantity)

    if expired_qty > 0:
        inventory.reserved_quantity = max(
            0, int(inventory.reserved_quantity) - expired_qty
        )

    return expired_qty


def expire_stale_reservations_for_inventory(
    db: Session,
    inventory: Inventory,
) -> int:
    """Public wrapper to expire stale ACTIVE reservations for a locked Inventory row."""
    return _expire_stale_reservations_for_locked_inventory(
        db=db,
        inventory=inventory,
        now=datetime.now(UTC),
    )


def _lookup_reservation_inventory_key(
    db: Session,
    reservation_id: str,
) -> tuple[str, str]:
    """Read (sku_id, warehouse_id) without locking so locks always follow Inventory -> Reservation order."""
    row = (
        db.query(StockReservation.sku_id, StockReservation.warehouse_id)
        .filter(StockReservation.reservation_id == reservation_id)
        .first()
    )
    if row is None:
        raise ReservationNotFoundError(f"Reservation {reservation_id} not found")
    return str(row[0]), str(row[1])


def reserve_stock(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    quantity: int,
    ttl_seconds: int | None = None,
    commit: bool = True,
) -> StockReservation:
    """
    Create an ACTIVE stock reservation inside one transaction.

    Locks the Inventory row first, expires stale ACTIVE holds for that SKU/warehouse,
    verifies available_quantity >= quantity, increments reserved_quantity, and persists
    the StockReservation row.
    """
    if quantity <= 0:
        raise ValueError("Reservation quantity must be greater than zero")

    ttl = (
        settings.RESERVATION_EXPIRATION_SECONDS if ttl_seconds is None else ttl_seconds
    )
    if ttl <= 0:
        raise ValueError("Reservation expiration must be greater than zero")

    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=ttl)

    try:
        inventory = _lock_inventory(db=db, sku_id=sku_id, warehouse_id=warehouse_id)
        _expire_stale_reservations_for_locked_inventory(
            db=db,
            inventory=inventory,
            now=now,
        )

        available = inventory.available_quantity
        if available < quantity:
            raise InsufficientAvailableStockError(
                f"Insufficient available stock for {sku_id}/{warehouse_id}: "
                f"available={available}, requested={quantity}"
            )

        new_reserved = int(inventory.reserved_quantity) + quantity
        if new_reserved > int(inventory.quantity_on_hand):
            raise InsufficientAvailableStockError(
                f"Reserved quantity ({new_reserved}) cannot exceed "
                f"quantity_on_hand ({inventory.quantity_on_hand})"
            )

        inventory.reserved_quantity = new_reserved

        reservation = StockReservation(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            status="ACTIVE",
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        db.add(reservation)
        if commit:
            db.commit()
            db.refresh(reservation)
        else:
            db.flush()
        return reservation

    except Exception:
        db.rollback()
        raise


def release_reservation(
    db: Session,
    reservation_id: str,
) -> StockReservation:
    """
    Release an ACTIVE reservation and decrement Inventory.reserved_quantity once.

    Uses consistent lock ordering (Inventory -> StockReservation) to avoid deadlocks
    and prevent double release under concurrency.
    """
    if not reservation_id:
        raise ValueError("reservation_id is required")

    try:
        sku_id, warehouse_id = _lookup_reservation_inventory_key(
            db=db,
            reservation_id=reservation_id,
        )
        inventory = _lock_inventory(db=db, sku_id=sku_id, warehouse_id=warehouse_id)

        reservation = (
            db.query(StockReservation)
            .filter(StockReservation.reservation_id == reservation_id)
            .with_for_update()
            .first()
        )
        if reservation is None:
            raise ReservationNotFoundError(f"Reservation {reservation_id} not found")

        if reservation.status != "ACTIVE":
            raise ReservationStateError(
                f"Reservation {reservation_id} is {reservation.status} and cannot be released"
            )

        inventory.reserved_quantity = max(
            0, int(inventory.reserved_quantity) - int(reservation.quantity)
        )
        reservation.status = "RELEASED"
        reservation.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(reservation)
        return reservation

    except Exception:
        db.rollback()
        raise


def confirm_reservation(
    db: Session,
    reservation_id: str,
) -> StockReservation:
    """
    Confirm (commit) an ACTIVE, non-expired reservation.

    Locks Inventory -> StockReservation -> InventoryCostLayer in consistent order,
    decrements both quantity_on_hand and reserved_quantity, increments inventory version,
    consumes FIFO cost layers, records low-stock events if triggered, and invalidates cache.
    """
    if not reservation_id:
        raise ValueError("reservation_id is required")

    now = datetime.now(UTC)

    try:
        sku_id, warehouse_id = _lookup_reservation_inventory_key(
            db=db,
            reservation_id=reservation_id,
        )
        inventory = _lock_inventory(db=db, sku_id=sku_id, warehouse_id=warehouse_id)

        reservation = (
            db.query(StockReservation)
            .filter(StockReservation.reservation_id == reservation_id)
            .with_for_update()
            .first()
        )
        if reservation is None:
            raise ReservationNotFoundError(f"Reservation {reservation_id} not found")

        if reservation.status != "ACTIVE":
            raise ReservationStateError(
                f"Reservation {reservation_id} is {reservation.status} and cannot be confirmed"
            )

        qty = int(reservation.quantity)

        if (
            reservation.expires_at is not None
            and _as_utc(reservation.expires_at) <= now
        ):
            if int(inventory.reserved_quantity) < qty:
                raise ReservationStateError(
                    f"Reserved quantity ({inventory.reserved_quantity}) is less than "
                    f"expired reservation quantity ({qty})"
                )
            inventory.reserved_quantity = int(inventory.reserved_quantity) - qty
            reservation.status = "EXPIRED"
            reservation.updated_at = now
            db.commit()
            raise ReservationExpiredError(
                f"Reservation {reservation_id} expired at "
                f"{reservation.expires_at.isoformat()}"
            )

        if int(inventory.quantity_on_hand) < qty:
            raise InsufficientAvailableStockError(
                f"Insufficient on-hand stock to confirm {reservation_id}: "
                f"on_hand={inventory.quantity_on_hand}, requested={qty}"
            )
        if int(inventory.reserved_quantity) < qty:
            raise ReservationStateError(
                f"Reserved quantity ({inventory.reserved_quantity}) is less than "
                f"reservation quantity ({qty})"
            )

        consumed_layers = consume_cost_layers(
            db=db,
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            quantity=qty,
        )
        consumed_quantity = sum(
            layer_quantity for layer_quantity, _unit_cost in consumed_layers
        )
        uncosted_quantity = qty - consumed_quantity
        if uncosted_quantity > 0:
            logger.warning(
                "Confirming reservation %s (%s units of %s at %s) exceeded "
                "available cost layers by %s units; valuation is incomplete until "
                "stock is received against a PO.",
                reservation_id,
                qty,
                sku_id,
                warehouse_id,
                uncosted_quantity,
            )

        old_quantity = int(inventory.quantity_on_hand)
        inventory.quantity_on_hand = old_quantity - qty
        inventory.reserved_quantity = int(inventory.reserved_quantity) - qty
        inventory.version += 1

        reservation.status = "COMMITTED"
        reservation.updated_at = now

        check_and_record_low_stock(
            db=db, item=inventory, previous_quantity=old_quantity
        )

        db.commit()
        db.refresh(reservation)
        db.refresh(inventory)
        invalidate_inventory_cache(
            sku_id,
            warehouse_id,
            version=inventory.version,
        )
        return reservation

    except ReservationExpiredError:
        raise
    except Exception:
        db.rollback()
        raise
