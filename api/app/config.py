"""Settings come from environment variables only. Missing or weak secrets stop the app at startup."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

_PLACEHOLDERS = {"change-me", "changeme", "secret", "your-secret-here", "replace-me"}


class ConfigError(RuntimeError):
    pass


@dataclass
class Settings:
    database_url: str
    jwt_secret: str
    jwt_hours: int = 8
    cookie_secure: bool = False
    bcrypt_rounds: int = 12
    allowed_origins: set[str] = field(default_factory=lambda: {
        "http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5173", "http://127.0.0.1:5173"})
    ai_mode: str = "live"          # live | stub
    max_prompt_words: int = 150
    upload_max_bytes: int = 1_000_000
    upload_max_rows: int = 5000
    run_migrations: bool = True
    privacy_contact: str | None = None    # shown on the privacy page: who to ask about your data

    def validate(self) -> "Settings":
        if not self.database_url:
            raise ConfigError("DATABASE_URL is not set")
        secret = (self.jwt_secret or "").strip()
        if len(secret) < 32 or secret.lower() in _PLACEHOLDERS:
            raise ConfigError("JWT_SECRET must be set to a random value of at least 32 characters")
        if self.ai_mode not in ("live", "stub"):
            raise ConfigError("AI_MODE must be 'live' or 'stub'")
        return self


def load_settings(env=None) -> Settings:
    env = os.environ if env is None else env
    origins = env.get("ALLOWED_ORIGINS")
    s = Settings(
        database_url=env.get("DATABASE_URL", ""),
        jwt_secret=env.get("JWT_SECRET", ""),
        jwt_hours=int(env.get("JWT_HOURS", "8")),
        cookie_secure=env.get("COOKIE_SECURE", "0") == "1",
        bcrypt_rounds=int(env.get("BCRYPT_ROUNDS", "12")),
        ai_mode=env.get("AI_MODE", "live"),
        max_prompt_words=int(env.get("MAX_PROMPT_WORDS", "150")),
        privacy_contact=(env.get("PRIVACY_CONTACT") or "").strip() or None,
    )
    if origins:
        s.allowed_origins = {o.strip() for o in origins.split(",") if o.strip()}
    return s.validate()
