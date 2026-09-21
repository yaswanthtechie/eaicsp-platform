import xmltodict

from app.schemas.sanctions import SanctionedEntity



def get_value(
    data: dict,
    key: str,
):
    """
    Get a value from a dictionary while ignoring
    XML namespace prefixes.
    """

    if not isinstance(data, dict):
        return None

    for item_key, value in data.items():

        clean_key = item_key.split(":")[-1]

        if clean_key == key:
            return value

    return None


def find_entities(data):
    """
    Recursively find all sanctionEntity objects
    from the EU sanctions XML structure.
    """

    entities = []

    if isinstance(data, dict):

        for key, value in data.items():

            clean_key = key.split(":")[-1]

            if clean_key == "sanctionEntity":

                if isinstance(value, list):
                    entities.extend(value)

                else:
                    entities.append(value)

            elif isinstance(value, (dict, list)):

                entities.extend(
                    find_entities(value)
                )

    elif isinstance(data, list):

        for item in data:

            entities.extend(
                find_entities(item)
            )

    return entities


def load_eu(
    xml_path,
) -> list[SanctionedEntity]:
    """
    Load EU sanctions entities from the XML file.

    The XML file is read as raw bytes so that the XML
    parser can detect and correctly handle the encoding
    declared inside the document.
    """

    print(
        "Loading EU sanctions list..."
    )

    try:

        # Read raw bytes instead of forcing UTF-8.
        # This allows the XML parser to detect the
        # encoding declared in the XML document.
        with open(
            xml_path,
            "rb",
        ) as file:

            xml_content = file.read()

        if not xml_content.strip():

            raise RuntimeError(
                "EU XML file is empty"
            )

        data = xmltodict.parse(
            xml_content
        )

        

    except Exception as error:

        raise RuntimeError(
            "Failed loading EU sanctions XML: "
            f"{error}"
        )

    entities: list[SanctionedEntity] = []

    sanctions = find_entities(
        data
    )

    print(
        "EU XML entities found: "
        f"{len(sanctions)}"
    )

    for entity in sanctions:

        if not isinstance(
            entity,
            dict,
        ):
            continue

        aliases: list[str] = []
        primary_name = ""

        # -------------------------------------------------
        # Read nameAlias entries
        # -------------------------------------------------

        name_alias = get_value(
            entity,
            "nameAlias",
        )

        if name_alias:

            if isinstance(
                name_alias,
                dict,
            ):

                name_alias = [
                    name_alias
                ]

            for alias in name_alias:

                if not isinstance(
                    alias,
                    dict,
                ):
                    continue

                whole_name = (
                    alias.get(
                        "@wholeName"
                    )
                    or alias.get(
                        "wholeName"
                    )
                )

                if not isinstance(
                    whole_name,
                    str,
                ):
                    continue

                whole_name = (
                    whole_name.strip()
                )

                if not whole_name:
                    continue

                # First name becomes the primary name.
                if not primary_name:

                    primary_name = (
                        whole_name
                    )

                # Remaining unique names become aliases.
                elif whole_name not in aliases:

                    aliases.append(
                        whole_name
                    )

        # -------------------------------------------------
        # Fallback to <name> if no nameAlias exists
        # -------------------------------------------------

        if not primary_name:

            name = get_value(
                entity,
                "name",
            )

            if isinstance(
                name,
                str,
            ):

                primary_name = (
                    name.strip()
                )

        # Skip records without a usable name.
        if not primary_name:
            continue

        # -------------------------------------------------
        # Listed/designation date
        # -------------------------------------------------

        listed_date = (
            entity.get(
                "@designationDate"
            )
            or entity.get(
                "designationDate"
            )
        )

        if isinstance(
            listed_date,
            str,
        ):

            listed_date = (
                listed_date.strip()
            )

        # -------------------------------------------------
        # Create standard SanctionedEntity
        # -------------------------------------------------

        entities.append(
            SanctionedEntity(
                name=primary_name,
                aliases=aliases,
                source="EU",
                listed_date=listed_date,
            )
        )

    print(
        f"Loaded {len(entities)} EU records"
    )

    return entities