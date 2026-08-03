from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Main PostgreSQL database
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/inventory"
    )

    # PostgreSQL database used for pytest
    TEST_DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/inventory_test"
    )

    class Config:
        env_file = ".env"


settings = Settings()