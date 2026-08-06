import xmltodict

from app.schemas.sanctions import SanctionedEntity


def get_value(data: dict, key: str):

    if not isinstance(data, dict):
        return None


    for item_key, value in data.items():

        clean_key = item_key.split(":")[-1]

        if clean_key == key:
            return value


    return None



def find_entities(data):

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
    xml_path
) -> list[SanctionedEntity]:


    print("Loading EU sanctions list...")


    try:

        with open(
            xml_path,
            encoding="utf-8-sig"
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
            f"Failed loading EU sanctions XML: {error}"
        )



    entities = []


    sanctions = find_entities(
        data
    )


    print(
        f"EU XML entities found: {len(sanctions)}"
    )



    for entity in sanctions:


        if not isinstance(entity, dict):

            continue



        aliases = []

        primary_name = ""


        name_alias = get_value(
            entity,
            "nameAlias"
        )



        if name_alias:


            if isinstance(
                name_alias,
                dict
            ):

                name_alias = [
                    name_alias
                ]



            for alias in name_alias:


                if not isinstance(
                    alias,
                    dict
                ):

                    continue



                whole_name = (

                    alias.get("@wholeName")

                    or

                    alias.get("wholeName")

                )



                if whole_name:


                    if not primary_name:

                        primary_name = whole_name.strip()



                    elif whole_name not in aliases:

                        aliases.append(
                            whole_name.strip()
                        )



        if not primary_name:


            name = get_value(
                entity,
                "name"
            )


            if isinstance(
                name,
                str
            ):

                primary_name = name.strip()



        # Ignore invalid records

        if not primary_name:

            continue



        listed_date = (

            entity.get("@designationDate")

            or

            entity.get("designationDate")

        )



        entities.append(

            SanctionedEntity(

                name=primary_name,

                aliases=aliases,

                source="EU",

                listed_date=listed_date

            )

        )



    print(
        f"Loaded {len(entities)} EU records"
    )


    return entities