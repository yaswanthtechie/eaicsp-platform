
from sqlalchemy.orm import Session

from app.models.inventory import Inventory


def get_inventory(
    db: Session,
    sku_id: str,
    warehouse_id: str,
):
    return (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .first()
    )


def get_parent_warehouse(
    db: Session,
    sku_id: str,
    warehouse_id: str,
):
    current = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )

    if current is None:
        return None

    if not current.parent_warehouse_id:
        return None

    return get_inventory(
        db,
        sku_id,
        current.parent_warehouse_id,
    )


def transfer_stock(
    db: Session,
    sku_id: str,
    source_warehouse_id: str,
    destination_warehouse_id: str,
    quantity: int,
):
    if quantity <= 0:
        raise ValueError(
            "Transfer quantity must be greater than zero"
        )

    source = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == source_warehouse_id,
        )
        .with_for_update()
        .first()
    )

    destination = (
        db.query(Inventory)
        .filter(
            Inventory.sku_id == sku_id,
            Inventory.warehouse_id == destination_warehouse_id,
        )
        .with_for_update()
        .first()
    )

    if source is None:
        raise ValueError(
            f"Source inventory not found: "
            f"{sku_id}/{source_warehouse_id}"
        )

    if destination is None:
        raise ValueError(
            f"Destination inventory not found: "
            f"{sku_id}/{destination_warehouse_id}"
        )

    if source.quantity_on_hand < quantity:
        raise ValueError(
            f"Insufficient stock in source warehouse: "
            f"{source_warehouse_id}"
        )

    source.quantity_on_hand -= quantity
    destination.quantity_on_hand += quantity


def create_supplier_po(
    sku_id: str,
    warehouse_id: str,
    quantity: int,
):
    if quantity <= 0:
        return None

    return {
        "sku_id": sku_id,
        "warehouse_id": warehouse_id,
        "quantity": quantity,
        "status": "supplier_required",
    }


def fulfill_shortage(
    db: Session,
    sku_id: str,
    warehouse_id: str,
    required_quantity: int,
):
    if required_quantity <= 0:
        raise ValueError(
            "Required quantity must be greater than zero"
        )

    local = get_inventory(
        db,
        sku_id,
        warehouse_id,
    )

    if local is None:
        raise ValueError(
            f"Inventory not found: "
            f"{sku_id}/{warehouse_id}"
        )

    if local.quantity_on_hand >= required_quantity:
        return {
            "status": "sufficient_stock",
            "sku_id": sku_id,
            "warehouse_id": warehouse_id,
            "required_quantity": required_quantity,
            "transferred_quantity": 0,
            "supplier_quantity": 0,
            "transfers": [],
            "supplier_po": None,
        }

    shortage = (
        required_quantity
        - local.quantity_on_hand
    )

    transfers = []

    current_warehouse_id = warehouse_id

    while shortage > 0:

        parent = get_parent_warehouse(
            db,
            sku_id,
            current_warehouse_id,
        )

        if parent is None:
            break

        available_stock = max(
            parent.quantity_on_hand,
            0,
        )

        transfer_quantity = min(
            shortage,
            available_stock,
        )

        if transfer_quantity > 0:
            transfer_stock(
                db=db,
                sku_id=sku_id,
                source_warehouse_id=parent.warehouse_id,
                destination_warehouse_id=warehouse_id,
                quantity=transfer_quantity,
            )

            transfers.append(
                {
                    "from_warehouse": parent.warehouse_id,
                    "to_warehouse": warehouse_id,
                    "quantity": transfer_quantity,
                }
            )

            shortage -= transfer_quantity

        current_warehouse_id = parent.warehouse_id

    supplier_quantity = shortage

    supplier_po = create_supplier_po(
        sku_id,
        warehouse_id,
        supplier_quantity,
    )

    transferred_quantity = sum(
        transfer["quantity"]
        for transfer in transfers
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    if supplier_quantity > 0:
        status = "supplier_required"
    else:
        status = "fulfilled_from_network"

    return {
        "status": status,
        "sku_id": sku_id,
        "warehouse_id": warehouse_id,
        "required_quantity": required_quantity,
        "transferred_quantity": transferred_quantity,
        "supplier_quantity": supplier_quantity,
        "transfers": transfers,
        "supplier_po": supplier_po,
    }
