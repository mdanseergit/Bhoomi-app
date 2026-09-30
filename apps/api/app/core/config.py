"""
Central application configuration.

All configuration is sourced from environment variables (see .env.example
at the repository root). Nothing here should ever contain a hardcoded
secret, API key, or credential.

Production posture
------------------
Defaults here are deliberately *fail-closed for production*: secrets have no
usable default, DEBUG defaults to off, and docs endpoints are disabled when
``APP_ENV=production``. Anything genuinely optional defaults to ``None`` and
the application reports the capability as "not configured" rather than
inventing a value.
"""
from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- App -----------------------------------------------------------
    APP_ENV: str = Field(default="development")
    APP_NAME: str = Field(default="BHOOMI Agriculture Intelligence Platform")
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = Field(default=False)

    # --- Security --------------------------------------------------------
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    CORS_ORIGINS: str = Field(default="http://localhost:3000")

    # --- Database --------------------------------------------------------
    DATABASE_URL: str = Field(default="")

    # --- Redis / Jobs ------------------------------------------------------
    REDIS_URL: str = Field(default="")

    # --- AI Providers --------------------------------------------------------
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    # Ordered model chain. Every entry is tried in turn; the first healthy
    # response wins, otherwise the deterministic rule engine is used.
    # NOTE: these defaults are overridable purely through the environment.
    AI_PRIMARY_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    AI_FALLBACK_MODEL: str = "meta/llama-3.2-11b-vision-instruct"
    AI_MODEL_CHAIN: str = ""  # optional explicit override, comma separated

    AI_PROVIDER_ORDER: str = "nvidia,deterministic"
    AI_REQUEST_TIMEOUT_SECONDS: int = 12
    AI_MAX_ATTEMPTS: int = 2
    AI_MAX_TOKENS_OUT: int = 700
    AI_DAILY_USER_QUOTA: int = 200
    AI_MIN_RESPONSE_CHARS: int = 40

    EMBEDDING_PROVIDER: str = "deterministic"  # nvidia | openai | deterministic
    EMBEDDING_DIM: int = 384

    # --- Weather -----------------------------------------------------------
    IMD_API_BASE_URL: Optional[str] = None
    IMD_API_KEY: Optional[str] = None
    WEATHER_CACHE_TTL_SECONDS: int = 1800  # 30 min
    WEATHER_FALLBACK_PROVIDER: str = "nasa_power"  # none | nasa_power

    # --- Satellite -----------------------------------------------------------
    # No simulated/synthetic satellite source ships in production. An
    # unconfigured provider means "no observation available".
    SATELLITE_PROVIDER: str = "none"  # none | sentinel_hub | planetary_computer
    SATELLITE_API_KEY: Optional[str] = None
    SATELLITE_API_BASE_URL: Optional[str] = None

    # --- Crop Doctor ---------------------------------------------------------
    # The bundled classifier is a development heuristic. Production refuses
    # image diagnosis unless a validated model provider is configured here.
    DISEASE_MODEL_PROVIDER: str = "none"  # none | <validated provider name>

    # --- Storage -------------------------------------------------------------
    STORAGE_BACKEND: str = "local"  # local | s3
    STORAGE_BUCKET: str = "bhoomi-uploads"
    STORAGE_LOCAL_PATH: str = "./var/uploads"
    MAX_UPLOAD_SIZE_MB: int = 8

    # --- Observability ---------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # --- Rate limiting -----------------------------------------------------------
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120
    RATE_LIMIT_AI_PER_MINUTE: int = 10
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_DISEASE_PER_MINUTE: int = 6

    # --- Registration -----------------------------------------------------------
    # Roles a brand-new self-registered account may hold. Administrative roles
    # are provisioned out-of-band and can never be claimed at signup.
    REGISTRATION_ALLOWED_ROLES: str = "farmer,agronomist"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def ai_provider_order_list(self) -> List[str]:
        return [o.strip() for o in self.AI_PROVIDER_ORDER.split(",") if o.strip()]

    @property
    def registration_allowed_role_list(self) -> List[str]:
        return [r.strip().lower() for r in self.REGISTRATION_ALLOWED_ROLES.split(",") if r.strip()]

    @property
    def ai_model_chain(self) -> List[str]:
        """Model ids to try in order, de-duplicated, blanks removed."""
        raw = self.AI_MODEL_CHAIN.strip()
        if not raw:
            raw = ",".join([self.AI_PRIMARY_MODEL, self.AI_FALLBACK_MODEL])
        seen: List[str] = []
        for m in (x.strip() for x in raw.split(",")):
            if m and m not in seen:
                seen.append(m)
        return seen

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in ("production", "prod")

    @property
    def sqlalchemy_database_url(self) -> str:
        """DATABASE_URL with an explicit driver.

        The project depends on psycopg 3 (psycopg[binary]), not psycopg2, but
        SQLAlchemy falls back to psycopg2 when a postgresql:// URL carries no
        driver marker. That raises ModuleNotFoundError on the first engine
        creation, which is at import time, so the app dies before serving a
        request. Pinning "+psycopg" makes any provider-supplied URL work
        without the deployer having to know this.
        """
        url = self.DATABASE_URL.strip()
        if not url:
            return url
        # Already carries an explicit driver, e.g. postgresql+psycopg://.
        if url.startswith("postgresql+") or url.startswith("postgres+"):
            return url
        for scheme in ("postgresql://", "postgres://"):
            if url.startswith(scheme):
                return "postgresql+psycopg://" + url[len(scheme):]
        return url

    def validate_for_startup(self) -> List[str]:
        """Returns a list of fatal configuration problems. Empty means safe."""
        problems: List[str] = []
        if not self.JWT_SECRET_KEY:
            problems.append("JWT_SECRET_KEY is required.")
        elif self.is_production and len(self.JWT_SECRET_KEY) < 32:
            problems.append("JWT_SECRET_KEY must be at least 32 characters in production.")
        if not self.DATABASE_URL:
            problems.append("DATABASE_URL is required.")
        if not self.REDIS_URL:
            problems.append("REDIS_URL is required.")
        if self.is_production:
            if self.DEBUG:
                problems.append("DEBUG must be false in production.")
            if self.APP_ENV.lower() == "production" and "localhost" in self.CORS_ORIGINS:
                problems.append("CORS_ORIGINS must not contain localhost in production.")
            satellite = (self.SATELLITE_PROVIDER or "none").strip().lower()
            if satellite in ("seeded_dev", "dev_seed", "simulated", "mock", "fake"):
                problems.append(
                    f"SATELLITE_PROVIDER={self.SATELLITE_PROVIDER!r} is a simulated source and is "
                    "not permitted in production. Use a real provider or 'none'."
                )
            disease = (self.DISEASE_MODEL_PROVIDER or "none").strip().lower()
            if disease not in ("", "none"):
                # Resolve the name the same way DiseaseService does and ask the
                # backend whether it is validated. A name that is not
                # registered resolves to the heuristic, so a typo or a
                # fabricated provider name cannot pass this check.
                from app.integrations.disease.heuristic_provider import HeuristicDiseaseModelProvider
                from app.services.disease_service import _PROVIDERS

                provider = _PROVIDERS.get(disease, HeuristicDiseaseModelProvider)()
                if not provider.is_validated:
                    problems.append(
                        f"DISEASE_MODEL_PROVIDER={self.DISEASE_MODEL_PROVIDER!r} resolves to "
                        f"{provider.name!r}, which is not a validated model and is not permitted in "
                        "production. Configure a validated model or 'none'."
                    )
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

