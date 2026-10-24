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
    # --- chat (M5). Langflow is reached over the Docker network; the tweak keys and the per-user switch are
    # decided by milestone M0 (see docs/WEB-APP-DESIGN.md, section 3D).
    langflow_url: str = "http://langflow:7860"
    langflow_flow: str = "language-tutor"      # endpoint name of the flow (flows/language-tutor.json)
    langflow_api_key: str = ""
    langflow_timeout: int = 100                # seconds; the page shows its "taking longer" note well before this
    langflow_tweak_keys: tuple = ("AddWord-WhP5g", "StoryGeneratorTool-RQpvc")   # node ids in flows/language-tutor.json (verified by the M0 spike); empty = no tweaks (Plan B)
    # The operator's statement that the flow's tools read the learner's own words (not the shared list). Until it
    # is "1", live chat refuses to run, because answering would mix learners' vocabulary. AI_MODE=stub is unaffected.
    langflow_per_user_tools: bool = False
    ai_gate_slots: int = 2
    ai_gate_wait: float = 5.0
    ai_tokens_per_minute: int = 8000       # Groq's free tier, app-wide; 0 switches the limiter off
    max_chat_chars: int = 2000
    # Password of the database role the Langflow tools connect with (migration 0008). Empty = that role cannot log in.
    # It goes into a URL in docker-compose.yml, so characters that would break a URL are refused.
    tools_db_password: str = ""
    # Protects learners' own model keys at rest (Fernet). Empty = the custom model feature cannot store a key, so it is off.
    model_key_secret: str = ""
    # Single-user setups only: let a learner's model address be on the host's own network (a local Ollama, say). Off by default.
    allow_private_model_urls: bool = False

    def validate(self) -> "Settings":
        if not self.database_url:
            raise ConfigError("DATABASE_URL is not set")
        secret = (self.jwt_secret or "").strip()
        if len(secret) < 32 or secret.lower() in _PLACEHOLDERS:
            raise ConfigError("JWT_SECRET must be set to a random value of at least 32 characters")
        if self.ai_mode not in ("live", "stub"):
            raise ConfigError("AI_MODE must be 'live' or 'stub'")
        if self.ai_gate_slots < 1:
            raise ConfigError("AI_GATE_SLOTS must be at least 1")
        if self.ai_tokens_per_minute < 0:
            raise ConfigError("AI_TOKENS_PER_MINUTE must be 0 (off) or more")
        if self.ai_gate_wait < 0 or self.langflow_timeout <= 0:
            raise ConfigError("AI_GATE_WAIT must be 0 or more and LANGFLOW_TIMEOUT above 0")
        bad = sorted({c for c in self.tools_db_password if c in ":@/%?#" or c.isspace() or not c.isprintable()})
        if bad:
            raise ConfigError("TOOLS_DB_PASSWORD must not contain whitespace or any of : @ / % ? # (it is part of a database URL)")
        if self.ai_mode == "live" and self.langflow_per_user_tools and not self.langflow_api_key.strip():
            raise ConfigError("LANGFLOW_API_KEY must be set when LANGFLOW_PER_USER_TOOLS=1")
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
        langflow_url=env.get("LANGFLOW_URL", "http://langflow:7860").strip(),
        langflow_flow=env.get("LANGFLOW_FLOW", "language-tutor").strip(),
        langflow_api_key=env.get("LANGFLOW_API_KEY", "").strip(),
        langflow_timeout=int(env.get("LANGFLOW_TIMEOUT", "100")),
        langflow_per_user_tools=env.get("LANGFLOW_PER_USER_TOOLS", "0") == "1",
        ai_gate_slots=int(env.get("AI_GATE_SLOTS", "2")),
        ai_gate_wait=float(env.get("AI_GATE_WAIT", "5")),
        ai_tokens_per_minute=int(env.get("AI_TOKENS_PER_MINUTE", "8000")),
        tools_db_password=env.get("TOOLS_DB_PASSWORD", ""),
        model_key_secret=env.get("MODEL_KEY_SECRET", "").strip(),
        allow_private_model_urls=env.get("ALLOW_PRIVATE_MODEL_URLS", "0") == "1",
    )
    if "LANGFLOW_TWEAK_KEYS" in env:
        s.langflow_tweak_keys = tuple(k.strip() for k in env["LANGFLOW_TWEAK_KEYS"].split(",") if k.strip())
    if origins:
        s.allowed_origins = {o.strip() for o in origins.split(",") if o.strip()}
    return s.validate()
