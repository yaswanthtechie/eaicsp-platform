import xmltodict

from app.schemas.sanctions import SanctionedEntity


def load_un(xml_path) -> list[SanctionedEntity]:

    with open(
        xml_path,
        encoding="utf-8"
    ) as file:

        data = xmltodict.parse(file.read())

    entities = []

    individuals = (
        data.get("CONSOLIDATED_LIST", {})
            .get("INDIVIDUALS", {})
            .get("INDIVIDUAL", [])
    )

    if isinstance(individuals, dict):
        individuals = [individuals]

    for person in individuals:

        first = (person.get("FIRST_NAME") or "").strip()
        second = (person.get("SECOND_NAME") or "").strip()
        third = (person.get("THIRD_NAME") or "").strip()
        fourth = (person.get("FOURTH_NAME") or "").strip()

        name = " ".join(
            part
            for part in [first, second, third, fourth]
            if part
        ).strip()

        aliases = []

        alias_data = person.get("INDIVIDUAL_ALIAS", [])

        if isinstance(alias_data, dict):
            alias_data = [alias_data]

        for alias in alias_data:

            alias_name = (alias.get("ALIAS_NAME") or "").strip()

            if alias_name and alias_name not in aliases:
                aliases.append(alias_name)

        entities.append(

            SanctionedEntity(

                name=name,

                aliases=aliases,

                source="UN",

                listed_date=person.get("LISTED_ON")

            )

        )

   

    return entities