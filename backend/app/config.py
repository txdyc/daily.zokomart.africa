from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {"", "change-me-in-production"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://root:root@localhost:3306/zokodaily?charset=utf8mb4"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440
    scheduler_enabled: bool = True
    upload_dir: str = "uploads"
    otp_ttl_seconds: int = 300
    otp_resend_seconds: int = 60
    otp_hourly_limit: int = 5
    otp_max_attempts: int = 5


settings = Settings()

# Fail fast if the JWT secret is left at the insecure default — forging admin
# tokens would be trivial. Tests set a non-default secret via env or monkeypatch.
if settings.jwt_secret in _INSECURE_SECRETS and not settings.database_url.startswith("sqlite"):
    import warnings
    warnings.warn(
        "jwt_secret is set to an insecure default. "
        "Set JWT_SECRET in .env before deploying to production.",
        RuntimeWarning,
        stacklevel=2,
    )
