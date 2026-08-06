import csv

from app.schemas.sanctions import SanctionedEntity


def load_ofac(csv_path) -> list[SanctionedEntity]:

    entities = []

    with open(
        csv_path,
        encoding="utf-8",
        newline=""
    ) as file:

        reader = csv.reader(file)

        for row in reader:

            if len(row) < 2:
                continue

            name = row[1].strip()

            if not name:
                continue

            entities.append(

                SanctionedEntity(

                    name=name,

                    aliases=[],

                    source="OFAC",

                    listed_date=None

                )

            )

    print(f"Loaded {len(entities)} OFAC records")

    return entities