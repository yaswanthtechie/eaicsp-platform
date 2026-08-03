from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Credentials belong in DATABASE_URL, never in source control.
    DATABASE_URL: str
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
