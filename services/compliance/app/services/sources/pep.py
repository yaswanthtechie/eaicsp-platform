import csv

from app.schemas.sanctions import SanctionedEntity


def load_pep(
    csv_path,
) -> list[SanctionedEntity]:

    entities: list[SanctionedEntity] = []

    with open(
        csv_path,
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            name = (row.get("name") or "").strip()

            if not name:
                continue

            entities.append(
                SanctionedEntity(
                    name=name,
                    aliases=[],
                    source="PEP",
                    listed_date=None,
                )
            )

    return entities