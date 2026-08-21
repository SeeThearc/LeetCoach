"""Application configuration using pydantic-settings.

This module defines all environment variables the application needs.
pydantic-settings reads from .env files and environment variables,
validates types at startup, and provides a single source of truth
for configuration across the entire application.

Why pydantic-settings instead of python-dotenv alone?
- Type validation: catches misconfigured values at startup, not at runtime
- Default values: provides sensible defaults for development
- Immutability: settings are frozen after creation (no accidental mutation)
- Auto-documentation: the Settings class IS the documentation
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables or a .env file.
    The .env file is read automatically from the project root.

    Attributes:
        app_name: Display name of the application.
        debug: Enable debug mode (verbose logging, auto-reload).
        environment: Current environment (development/staging/production).
        database_url: Async SQLAlchemy database connection string.
        google_api_key: API key for Google Gemini LLM.
        gemini_model: Which Gemini model to use.
        leetcode_api_base_url: Base URL for the LeetCode problem API.
        allowed_origins: CORS allowed origins for the Chrome Extension.
    """

    # --- Application ---
    app_name: str = "AI LeetCode Coach"
    debug: bool = False
    environment: str = "development"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./ai_tutor.db"

    # --- AI (Google Gemini) ---
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # --- LeetCode API ---
    leetcode_api_base_url: str = "https://leetcode-api-pied.vercel.app"

    # --- CORS ---
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars that aren't defined here
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    Uses @lru_cache so the .env file is only read and parsed once.
    Subsequent calls return the same Settings instance.

    Returns:
        The application Settings singleton.
    """
    return Settings()
