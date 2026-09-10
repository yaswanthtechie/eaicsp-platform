from dataclasses import dataclass, field


@dataclass
class SanctionedEntity:

    name: str

    aliases: list[str] = field(
        default_factory=list
    )

    source: str = ""

    listed_date: str | None = None

    sources: list[str] = field(
        default_factory=list
    )

    confidence: int = 100