import argparse
from datetime import datetime

from pipeline import run_pipeline, run_backfill


parser = argparse.ArgumentParser()

subparsers = parser.add_subparsers(dest="command")

backfill = subparsers.add_parser("backfill")

backfill.add_argument("--from", dest="from_date", required=True)
backfill.add_argument("--to", dest="to_date", required=True)

args = parser.parse_args()


if args.command == "backfill":

    run_backfill(
        datetime.strptime(args.from_date, "%Y-%m-%d").date(),
        datetime.strptime(args.to_date, "%Y-%m-%d").date()
    )

else:

    run_pipeline()