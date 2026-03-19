from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Avery Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./avery.db"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days (30 * 24 * 60 minutes)

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8000"
    ]

    # AI Provider API Keys
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"

    # Agent max tokens for Claude API responses (default: 8000)
    # Increase for complex tasks, decrease for faster/cheaper responses
    AGENT_MAX_TOKENS: int = 8000

    # Repository Storage
    REPOS_BASE_PATH: str = "/tmp/avery-repos"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # Session Secret for OAuth (use same as SECRET_KEY if not specified)
    SESSION_SECRET_KEY: str = ""

    # Frontend URL
    FRONTEND_URL: str = "http://localhost:5173"

    # Backend URL (for webhooks from GitHub Actions)
    BACKEND_URL: str = "http://localhost:8000"

    # Authentication Methods (enable/disable)
    AUTH_PASSWORD_ENABLED: bool = True
    AUTH_MAGIC_LINK_ENABLED: bool = False
    AUTH_GOOGLE_ENABLED: bool = False

    # SMTP Settings for Magic Link
    SMTP_HOST: str = "smtp.office365.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Avery"
    SMTP_USE_TLS: bool = True
    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Plugin System (for extending Avery with custom plugins)
    AVERY_EDITION: str = "ce"
    AVERY_PLUGIN_CLASS: str = ""  # Dotted path to plugin class

    # CI/CD Integration
    AVERY_API_TOKEN: str = ""  # Token for GitHub Actions webhook authentication

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
