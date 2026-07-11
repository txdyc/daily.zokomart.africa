from pydantic_settings import BaseSettings, SettingsConfigDict


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
