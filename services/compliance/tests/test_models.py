from app.models.regulatory_rule import RegulatoryRule
from app.models.sanction import SanctionedEntity


def test_regulatory_rule_table_definition():
    assert RegulatoryRule.__tablename__ == "regulatory_rules"

    columns = RegulatoryRule.__table__.columns

    assert columns["id"].primary_key is True
    assert columns["rule_code"].unique is True
    assert columns["rule_code"].nullable is False
    assert columns["country"].nullable is False
    assert columns["rule_name"].nullable is False
    assert columns["description"].nullable is False
    assert columns["enabled"].default.arg is True


def test_sanctioned_entity_defaults():
    entity = SanctionedEntity(name="ACME CORPORATION")

    assert entity.name == "ACME CORPORATION"
    assert entity.aliases == []
    assert entity.source == ""
    assert entity.listed_date is None
    assert entity.sources == []
    assert entity.confidence == 100


def test_sanctioned_entity_custom_values():
    entity = SanctionedEntity(
        name="ACME CORPORATION",
        aliases=["ACME", "ACME CORP"],
        source="OFAC",
        listed_date="2026-01-15",
        sources=["OFAC", "EU"],
        confidence=85,
    )

    assert entity.aliases == ["ACME", "ACME CORP"]
    assert entity.source == "OFAC"
    assert entity.listed_date == "2026-01-15"
    assert entity.sources == ["OFAC", "EU"]
    assert entity.confidence == 85


def test_sanctioned_entity_lists_are_independent():
    first = SanctionedEntity(name="FIRST")
    second = SanctionedEntity(name="SECOND")

    first.aliases.append("FIRST ALIAS")
    first.sources.append("OFAC")

    assert second.aliases == []
    assert second.sources == []
