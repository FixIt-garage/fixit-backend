from pydantic import field_validator
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
    jwt_algorithm: str = "HS256"
    jwt_secret_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Uploads (FIX-32). "local" stores files on disk; an S3 backend can be added later.
    storage_backend: str = "local"
    media_root: str = "media"
    media_url: str = "/media"
    max_upload_size_mb: int = 5
    avatar_size_px: int = 512

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("JWT_SECRET_KEY must not be empty")
        return value.strip()


settings = Settings()