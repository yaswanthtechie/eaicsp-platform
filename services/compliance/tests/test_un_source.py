from app.services.sources.un import _as_list, _clean_value, load_un


def test_as_list_handles_supported_values():
    assert _as_list(None) == []
    assert _as_list([]) == []
    assert _as_list({"name": "value"}) == [{"name": "value"}]
    assert _as_list([{"name": "value"}]) == [{"name": "value"}]
    assert _as_list("invalid") == []


def test_clean_value_handles_none_and_whitespace():
    assert _clean_value(None) == ""
    assert _clean_value("  ACME  ") == "ACME"
    assert _clean_value(123) == "123"


def test_load_un_parses_individual_and_aliases(tmp_path):
    xml_file = tmp_path / "un.xml"
    xml_file.write_text(
        """<?xml version="1.0"?>
        <CONSOLIDATED_LIST>
          <INDIVIDUALS>
            <INDIVIDUAL>
              <FIRST_NAME>John</FIRST_NAME>
              <SECOND_NAME>Smith</SECOND_NAME>
              <LISTED_ON>2024-01-10</LISTED_ON>
              <INDIVIDUAL_ALIAS>
                <ALIAS_NAME>Johnny Smith</ALIAS_NAME>
              </INDIVIDUAL_ALIAS>
            </INDIVIDUAL>
          </INDIVIDUALS>
        </CONSOLIDATED_LIST>""",
        encoding="utf-8",
    )

    entities = load_un(xml_file)

    assert len(entities) == 1
    assert entities[0].name == "John Smith"
    assert entities[0].aliases == ["Johnny Smith"]
    assert entities[0].source == "UN"
    assert entities[0].listed_date == "2024-01-10"


def test_load_un_skips_empty_names_and_invalid_records(tmp_path):
    xml_file = tmp_path / "un.xml"
    xml_file.write_text(
        """<?xml version="1.0"?>
        <CONSOLIDATED_LIST>
          <INDIVIDUALS>
            <INDIVIDUAL>invalid</INDIVIDUAL>
            <INDIVIDUAL>
              <FIRST_NAME></FIRST_NAME>
            </INDIVIDUAL>
          </INDIVIDUALS>
        </CONSOLIDATED_LIST>""",
        encoding="utf-8",
    )

    assert load_un(xml_file) == []
