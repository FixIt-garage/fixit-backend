from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "FixIt API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fixit"
    cors_origins: list[str] = ["http://localhost:8081"]


settings = Settings()