from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models.inventory import Inventory
from app.models.inventory_cost_layer import InventoryCostLayer


CATEGORY_BASE_COST = {
    "Electronics": 50.00,
    "Accessories": 15.00,
    "Office Equipment": 80.00,
    "Furniture": 120.00,
    "Networking": 100.00,
    "Storage": 60.00,
    "Office Supplies": 10.00,
    "Lighting": 30.00,
    "Electrical": 25.00,
    "Appliances": 150.00,
    "Uncategorized": 50.00,
}


def split_quantity(quantity):
    """
    Split current inventory quantity into up to 3 cost layers.
    """

    if quantity <= 0:
        return []

    if quantity == 1:
        return [1]

    if quantity == 2:
        return [1, 1]

    first = quantity // 3
    second = quantity // 3
    third = quantity - first - second

    return [
        first,
        second,
        third,
    ]


def seed_cost_layers():

    db = SessionLocal()

    try:

        print("Deleting old inventory cost layers...")

        db.query(InventoryCostLayer).delete()

        db.commit()

        inventories = (
            db.query(Inventory)
            .order_by(
                Inventory.sku_id,
                Inventory.warehouse_id,
            )
            .all()
        )

        if not inventories:
            print("No inventory records found.")
            return

        layers = []

        now = datetime.utcnow()

        for inventory in inventories:

            quantity = inventory.quantity_on_hand

            if quantity <= 0:
                continue

            category = (
                inventory.category
                or "Uncategorized"
            )

            base_cost = CATEGORY_BASE_COST.get(
                category,
                50.00,
            )

            quantities = split_quantity(
                quantity
            )

            costs = [
                round(base_cost * 0.90, 2),
                round(base_cost, 2),
                round(base_cost * 1.10, 2),
            ]

            for index, layer_quantity in enumerate(
                quantities
            ):

                layers.append(
                    InventoryCostLayer(
                        sku_id=inventory.sku_id,
                        warehouse_id=inventory.warehouse_id,
                        category=category,
                        quantity_received=layer_quantity,
                        quantity_remaining=layer_quantity,
                        unit_cost=costs[index],
                        received_at=(
                            now
                            - timedelta(
                                days=(10 - index * 5)
                            )
                        ),
                    )
                )

        print(
            f"Creating {len(layers)} cost layers..."
        )

        db.add_all(layers)

        db.commit()

        total_layers = (
            db.query(
                InventoryCostLayer
            ).count()
        )

        unique_skus = (
            db.query(
                InventoryCostLayer.sku_id
            )
            .distinct()
            .count()
        )

        unique_warehouses = (
            db.query(
                InventoryCostLayer.warehouse_id
            )
            .distinct()
            .count()
        )

        print()
        print("=" * 45)
        print("   INVENTORY COST LAYER SEED COMPLETE")
        print("=" * 45)
        print(
            f"Inventory records : {len(inventories)}"
        )
        print(
            f"Cost layers       : {total_layers}"
        )
        print(
            f"Unique SKUs       : {unique_skus}"
        )
        print(
            f"Warehouses        : {unique_warehouses}"
        )
        print("=" * 45)

    except Exception as exc:

        db.rollback()

        print(
            f"ERROR: {exc}"
        )

        raise

    finally:

        db.close()


if __name__ == "__main__":
    seed_cost_layers()