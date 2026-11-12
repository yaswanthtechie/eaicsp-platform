"""Inventory Service management CLI (R15-B8 / #324)."""

from __future__ import annotations

import argparse
import csv
import sys
from typing import Sequence

from sqlalchemy.exc import SQLAlchemyError

from app.services.client_import_service import (
    ClientImportError,
    run_client_data_import,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Inventory Service management commands",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_cmd = subparsers.add_parser(
        "import-client-data",
        help="Import canonical Products, Warehouses, and Supplier Lead Times from client staging.",
    )
    import_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate staging records and compute counts without writing database changes.",
    )
    import_cmd.add_argument(
        "--staging-dir",
        type=str,
        default=None,
        help="Directory containing canonical staging CSV files.",
    )
    import_cmd.add_argument(
        "--source",
        choices=("auto", "csv", "db"),
        default="auto",
        help="Staging source mode (default: auto).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "import-client-data":
        try:
            summary = run_client_data_import(
                staging_dir=args.staging_dir,
                source=args.source,
                dry_run=args.dry_run,
            )
        except ClientImportError as exc:
            print(f"Client data import failed: {exc}", file=sys.stderr)
            return 1
        except SQLAlchemyError as exc:
            print(
                "Client data import failed: database error "
                f"({type(exc).__name__}). No changes were written.",
                file=sys.stderr,
            )
            return 1
        except (UnicodeDecodeError, csv.Error, OSError) as exc:
            print(
                "Client data import failed: could not read staging file "
                f"({type(exc).__name__}). Save the CSV as UTF-8 and retry.",
                file=sys.stderr,
            )
            return 1

        print(summary.format_summary())
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
