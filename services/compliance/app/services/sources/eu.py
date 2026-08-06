import xmltodict

from app.schemas.sanctions import SanctionedEntity



def get_value(data, key):

    for item_key, value in data.items():

        clean_key = item_key.split(":")[-1]

        if clean_key == key:

            return value

    return None



def find_entities(data):

    found = []


    if isinstance(data, dict):

        for key, value in data.items():

            clean_key = key.split(":")[-1]


            if clean_key == "sanctionEntity":

                if isinstance(value, list):

                    found.extend(value)

                else:

                    found.append(value)


            elif isinstance(value, (dict,list)):

                found.extend(
                    find_entities(value)
                )


    elif isinstance(data,list):

        for item in data:

            found.extend(
                find_entities(item)
            )


    return found



def load_eu(xml_path) -> list[SanctionedEntity]:


    with open(
        xml_path,
        encoding="utf-8"
    ) as file:

        data = xmltodict.parse(
            file.read()
        )


    entities = []


    sanctions = find_entities(data)


    print(
        f"EU XML entities found: {len(sanctions)}"
    )


    for entity in sanctions:


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


                if not isinstance(alias,dict):

                    continue


                whole_name = (

                    alias.get("@wholeName")

                    or

                    alias.get("wholeName")

                )


                if whole_name:


                    if not primary_name:

                        primary_name = whole_name


                    elif whole_name not in aliases:

                        aliases.append(
                            whole_name
                        )



        if not primary_name:

            name = get_value(
                entity,
                "name"
            )

            if isinstance(name,str):

                primary_name = name



        if not primary_name:

            continue



        entities.append(

            SanctionedEntity(

                name=primary_name,

                aliases=aliases,

                source="EU",

                listed_date=(

                    entity.get("@designationDate")

                    or

                    entity.get("designationDate")

                )

            )

        )


    print(
        f"Loaded {len(entities)} EU records"
    )


    return entities