
import csv

from app.schemas.sanctions import SanctionedEntity


def load_ofac(
    csv_path,
) -> list[SanctionedEntity]:
   
    entities: list[SanctionedEntity] = []

    with open(
        csv_path,
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.reader(file)

        for row in reader:

            # Ignore malformed/empty rows.
            if len(row) < 2:
                continue

            # OFAC name is stored in column 2.
            name = row[1].strip()

            # Skip an actual header row only.
            if name.upper() in {
                "NAME",
                "ENTITY NAME",
                "SDN NAME",
            }:
                continue

            if not name:
                continue

            entities.append(
                SanctionedEntity(
                    name=name,
                    aliases=[],
                    source="OFAC",
                    listed_date=None,
                )
            )

    return entities

