import os


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./raizes.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-only-change-me-please-32-chars-min")
    algorithm: str = "HS256"
    token_minutes: int = int(os.getenv("TOKEN_MINUTES", "60"))


settings = Settings()
