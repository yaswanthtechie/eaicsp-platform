from pydantic import BaseModel, Field


class SanctionedEntity(BaseModel):

    name: str

    aliases: list[str] = Field(default_factory=list)

    source: str

    listed_date: str | None = None