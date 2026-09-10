from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    PLATFORM_AUTH_URL: str = "http://localhost:8005"

    model_config = SettingsConfigDict(
        env_file=".env"
    )


settings = Settings()