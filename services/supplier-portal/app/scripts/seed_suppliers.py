
import argparse
from pathlib import Path

from app.database import SessionLocal
from app.services.supplier_seed_loader import seed_suppliers

DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "seed"
    / "suppliers.csv"
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Load the canonical supplier seed into "
            "supplier_portal.suppliers."
        ),
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help=(
            "suppliers.csv to load, e.g. the output of "
            "data-platform: python -m seed.generate --out out/"
        ),
    )
    seed_path = parser.parse_args(argv).path

    if not seed_path.is_file():
        parser.error(f"Supplier seed CSV not found: {seed_path}")

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
