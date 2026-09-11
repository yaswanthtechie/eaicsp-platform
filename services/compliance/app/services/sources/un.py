
import xmltodict

from app.schemas.sanctions import SanctionedEntity


def _as_list(value):
 
    if not value:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, dict):
        return [value]

    return []


def _clean_value(value) -> str:
    """
    Safely convert an XML value into a stripped string.
    """
    if value is None:
        return ""

    return str(value).strip()


def load_un(
    xml_path,
) -> list[SanctionedEntity]:
    """
    Load individual sanctions entities from the UN XML list.
    """

    with open(
        xml_path,
        encoding="utf-8",
    ) as file:

        data = xmltodict.parse(
            file.read()
        )

    entities: list[SanctionedEntity] = []

    consolidated_list = data.get(
        "CONSOLIDATED_LIST",
        {},
    )

    if not isinstance(
        consolidated_list,
        dict,
    ):
        return entities

    individuals_section = consolidated_list.get(
        "INDIVIDUALS",
        {},
    )

    if not isinstance(
        individuals_section,
        dict,
    ):
        return entities

    individuals = _as_list(
        individuals_section.get(
            "INDIVIDUAL",
            [],
        )
    )

    for person in individuals:

        if not isinstance(
            person,
            dict,
        ):
            continue



        name_parts = []

        for field in (
            "FIRST_NAME",
            "SECOND_NAME",
            "THIRD_NAME",
            "FOURTH_NAME",
        ):

            value = _clean_value(
                person.get(field)
            )

            if value:
                name_parts.append(
                    value
                )

        name = " ".join(
            name_parts
        ).strip()

        if not name:
            continue


        aliases: list[str] = []

        alias_data = _as_list(
            person.get(
                "INDIVIDUAL_ALIAS",
                [],
            )
        )

        for alias in alias_data:

            if not isinstance(
                alias,
                dict,
            ):
                continue

            alias_name = _clean_value(
                alias.get(
                    "ALIAS_NAME"
                )
            )

            if (
                alias_name
                and alias_name != name
                and alias_name not in aliases
            ):
                aliases.append(
                    alias_name
                )


        listed_date = _clean_value(
            person.get(
                "LISTED_ON"
            )
        )


        entities.append(
            SanctionedEntity(
                name=name,
                aliases=sorted(
                    aliases
                ),
                source="UN",
                listed_date=(
                    listed_date
                    or None
                ),
            )
        )

    return entities

