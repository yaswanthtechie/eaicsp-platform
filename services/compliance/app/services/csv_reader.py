import csv
from pathlib import Path


def load_sanctions(files):

    sanction_data = {}

    total = 0

    for file_path, source, has_header, column in files:

        print(f"Loading {source}")

        path = Path(file_path)

        if not path.exists():
            raise RuntimeError(f"Missing sanctions file: {path}")

        count = 0

        with path.open(
            encoding="utf-8",
            newline=""
        ) as file:

            reader = csv.reader(file)

            if has_header:
                next(reader, None)

            for row in reader:

                if len(row) <= column:
                    continue

                name = row[column].strip()

                if not name:
                    continue

                

                if name not in sanction_data:
                    sanction_data[name] = []
                    total += 1

                if source not in sanction_data[name]:
                    sanction_data[name].append(source)

                count += 1

        print(f"{source}: {count} rows")

    if total == 0:
        raise RuntimeError(
            "No sanctions loaded. Startup aborted."
        )

    print(f"Loaded: {total}")

    return sanction_data