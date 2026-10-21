
from pathlib import Path

from app.database import SessionLocal
from app.services.supplier_seed_loader import seed_suppliers

DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "seed"
    / "suppliers.csv"
)


def main() -> None:
    seed_path = DEFAULT_SEED_PATH

    print(f"Loading supplier seed from: {seed_path}")

    with SessionLocal() as session:
        try:
            result = seed_suppliers(seed_path, session)
            session.commit()
            print(
                "Supplier seed completed: "
                f"inserted={result['inserted']}, "
                f"updated={result['updated']}"
            )
        except Exception:
            session.rollback()
            raise


if __name__ == "__main__":
    main()
