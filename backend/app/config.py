from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "",
        "changeme",
        "change-me",
        "changeme!",
        "placeholder",
        "secret",
        "your-secret-here",
        "todo",
        "tbd",
    }
)


def _looks_like_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip().lower()
    if not stripped:
        return True
    return stripped in _PLACEHOLDER_VALUES


class Settings(BaseSettings):
    """Application settings sourced from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = Field(default="development", validation_alias="APP_ENV")

    database_url: str = Field(default="sqlite+aiosqlite:///:memory:", validation_alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    secret_key: str = Field(default="changeme", validation_alias="SECRET_KEY")
    jwt_secret_key: str = Field(default="changeme", validation_alias="JWT_SECRET_KEY")
    # Distinct secret for the operator/cockpit JWT surface so a leak of the
    # tenant JWT secret can't be reused to forge cockpit tokens and vice
    # versa. Empty in dev/test → operator_auth.get_cockpit_jwt_secret falls
    # back to a deterministic placeholder.
    cockpit_jwt_secret_key: str = Field(default="", validation_alias="COCKPIT_JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=15, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")

    backend_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        validation_alias="BACKEND_CORS_ORIGINS",
    )

    receipt_signing_key_id: str = Field(default="default", validation_alias="RECEIPT_SIGNING_KEY_ID")
    receipt_signing_private_key_pem: str = Field(default="", validation_alias="RECEIPT_SIGNING_PRIVATE_KEY_PEM")
    receipt_next_signing_key_id: str = Field(default="", validation_alias="RECEIPT_NEXT_SIGNING_KEY_ID")
    receipt_next_signing_private_key_pem: str = Field(
        default="", validation_alias="RECEIPT_NEXT_SIGNING_PRIVATE_KEY_PEM"
    )

    portal_smoke_test_timeout_sec: int = Field(default=60, validation_alias="PORTAL_SMOKE_TEST_TIMEOUT_SEC")
    # Phase 4: smoke-test → Slack drift alerting
    slack_webhook_url: str = Field(default="", validation_alias="SLACK_WEBHOOK_URL")
    slack_alert_channel: str = Field(default="#portal-drift", validation_alias="SLACK_ALERT_CHANNEL")
    portal_smoke_test_alert_cooldown_sec: int = Field(
        default=900, validation_alias="PORTAL_SMOKE_TEST_ALERT_COOLDOWN_SEC"
    )
    portal_smoke_state_path: str = Field(
        default=".once/smoke_state.json",
        validation_alias="PORTAL_SMOKE_STATE_PATH",
    )
    enable_in_process_processor: bool = Field(default=False, validation_alias="ENABLE_IN_PROCESS_PROCESSOR")
    enable_tos_risky_platforms: bool = Field(default=False, validation_alias="ENABLE_TOS_RISKY_PLATFORMS")

    sentry_dsn: str = Field(default="", validation_alias="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(default=0.1, validation_alias="SENTRY_TRACES_SAMPLE_RATE")
    env: str = Field(default="development", validation_alias="ENV")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")

    # --- L3.5 billing (Stripe) ---
    # All Stripe-facing secrets are Optional[str] so the app boots cleanly when
    # billing is not yet configured. Stripe code paths fail-closed at call time
    # if the relevant key is missing. STRIPE_MOCK_MODE short-circuits the
    # actual Stripe SDK for tests + local development.
    stripe_secret_key: str | None = Field(default=None, validation_alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: str | None = Field(default=None, validation_alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: str | None = Field(default=None, validation_alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_setup_id: str | None = Field(default=None, validation_alias="STRIPE_PRICE_SETUP_ID")
    stripe_price_monthly_id: str | None = Field(default=None, validation_alias="STRIPE_PRICE_MONTHLY_ID")
    stripe_customer_portal_return_url: str = Field(
        default="http://localhost:5173/billing",
        validation_alias="STRIPE_CUSTOMER_PORTAL_RETURN_URL",
    )
    stripe_checkout_success_url: str = Field(
        default="http://localhost:5173/billing/success?session_id={CHECKOUT_SESSION_ID}",
        validation_alias="STRIPE_CHECKOUT_SUCCESS_URL",
    )
    stripe_checkout_cancel_url: str = Field(
        default="http://localhost:5173/billing/cancel",
        validation_alias="STRIPE_CHECKOUT_CANCEL_URL",
    )
    billing_grace_period_days: int = Field(default=7, validation_alias="BILLING_GRACE_PERIOD_DAYS")
    stripe_mock_mode: bool = Field(default=True, validation_alias="STRIPE_MOCK_MODE")
    # --- /L3.5 billing ---

    # --- L3.6 onboarding ---
    resend_api_key: str | None = Field(default=None, validation_alias="RESEND_API_KEY")
    email_from_address: str = Field(default="noreply@getonce.com", validation_alias="EMAIL_FROM_ADDRESS")
    email_verification_code_ttl_minutes: int = Field(default=15, validation_alias="EMAIL_VERIFICATION_CODE_TTL_MINUTES")
    email_verification_max_attempts: int = Field(default=5, validation_alias="EMAIL_VERIFICATION_MAX_ATTEMPTS")
    email_verification_max_codes_per_hour: int = Field(
        default=3, validation_alias="EMAIL_VERIFICATION_MAX_CODES_PER_HOUR"
    )
    onboarding_skip_email_verify: bool = Field(default=False, validation_alias="ONBOARDING_SKIP_EMAIL_VERIFY")
    onboarding_session_ttl_minutes: int = Field(default=30, validation_alias="ONBOARDING_SESSION_TTL_MINUTES")
    email_dispatcher: Literal["outbox", "resend"] = Field(default="outbox", validation_alias="EMAIL_DISPATCHER")
    email_outbox_dir: str = Field(default=".once/outbox", validation_alias="EMAIL_OUTBOX_DIR")
    # --- /L3.6 onboarding ---

    # --- L3.7 imports ---
    import_max_file_size_bytes: int = Field(
        default=50 * 1024 * 1024,
        validation_alias="IMPORT_MAX_FILE_SIZE_BYTES",
    )
    import_max_rows: int = Field(default=100_000, validation_alias="IMPORT_MAX_ROWS")
    import_chunk_size: int = Field(default=500, validation_alias="IMPORT_CHUNK_SIZE")
    import_storage_path: str = Field(
        default="./.once/imports/",
        validation_alias="IMPORT_STORAGE_PATH",
    )
    # --- /L3.7 imports ---

    # --- L3.8 pdf extraction ---
    pdf_extraction_enabled: bool = Field(default=True, validation_alias="PDF_EXTRACTION_ENABLED")
    pdf_max_pages: int = Field(default=50, validation_alias="PDF_MAX_PAGES")
    pdf_max_size_mb: int = Field(default=25, validation_alias="PDF_MAX_SIZE_MB")
    extractor_timeout_seconds: int = Field(default=30, validation_alias="EXTRACTOR_TIMEOUT_SECONDS")
    # --- /L3.8 pdf extraction ---

    # --- L6.1 verifier API monetization ---
    # Shared bearer that the public verifier service presents on the
    # internal key-lookup endpoint. Empty string disables the internal
    # route (useful for tests / first-run boot). Treated as secret —
    # never log or echo back in API responses.
    verifier_internal_token: str = Field(default="", validation_alias="VERIFIER_INTERNAL_TOKEN")
    # Free-tier monthly call cap stamped on any key created without an
    # explicit cap. Matches the ROADMAP "Free tier + paid >10K/mo"
    # commitment.
    verifier_free_tier_monthly_cap: int = Field(default=10_000, validation_alias="VERIFIER_FREE_TIER_MONTHLY_CAP")
    # --- /L6.1 verifier API monetization ---

    # --- L3.9 inbound email ---
    inbound_email_enabled: bool = Field(default=True, validation_alias="INBOUND_EMAIL_ENABLED")
    inbound_storage_path: str = Field(default="./.once/inbound/", validation_alias="INBOUND_STORAGE_PATH")
    inbound_max_email_size_mb: int = Field(default=30, validation_alias="INBOUND_MAX_EMAIL_SIZE_MB")
    inbound_max_attachment_size_mb: int = Field(default=25, validation_alias="INBOUND_MAX_ATTACHMENT_SIZE_MB")
    inbound_email_domain: str = Field(default="in.getonce.com", validation_alias="INBOUND_EMAIL_DOMAIN")
    postmark_webhook_secret: str | None = Field(default=None, validation_alias="POSTMARK_WEBHOOK_SECRET")
    imap_host: str | None = Field(default=None, validation_alias="IMAP_HOST")
    imap_port: int | None = Field(default=993, validation_alias="IMAP_PORT")
    imap_username: str | None = Field(default=None, validation_alias="IMAP_USERNAME")
    imap_password: str | None = Field(default=None, validation_alias="IMAP_PASSWORD")
    imap_folder: str | None = Field(default="INBOX", validation_alias="IMAP_FOLDER")
    imap_poll_interval_seconds: int = Field(default=60, validation_alias="IMAP_POLL_INTERVAL_SECONDS")
    # --- /L3.9 inbound email ---

    # --- L4 antivirus scanner ---
    # Backend selector for ``app.services.av_scanner``. ``stub_allow`` is
    # the dev/test default (no daemon required); ``clamd`` wires the real
    # ClamAV sidecar; ``eicar`` is a test backend that only flags the
    # EICAR probe string; ``stub_deny`` always refuses (exercises the
    # fail-closed paths). ``noop`` is an alias of stub_allow for explicit
    # "AV disabled" deployments.
    av_scanner_backend: Literal["clamd", "stub_allow", "stub_deny", "eicar", "noop"] = Field(
        default="stub_allow", validation_alias="AV_SCANNER_BACKEND"
    )
    av_clamd_host: str = Field(default="localhost", validation_alias="AV_CLAMD_HOST")
    av_clamd_port: int = Field(default=3310, validation_alias="AV_CLAMD_PORT")
    av_clamd_unix_socket: str | None = Field(default=None, validation_alias="AV_CLAMD_UNIX_SOCKET")
    av_clamd_timeout_sec: float = Field(default=5.0, validation_alias="AV_CLAMD_TIMEOUT_SEC")
    # Production posture: True ⇒ a downed scanner blocks uploads (we'd
    # rather lose availability than ingest an unscanned payload). Dev /
    # test default flips to False so a missing clamd sidecar doesn't
    # break local boots — the file lands on disk and a warning is logged.
    av_fail_closed_on_scanner_error: bool = Field(default=True, validation_alias="AV_FAIL_CLOSED_ON_SCANNER_ERROR")
    # --- /L4 antivirus scanner ---

    # --- DB connection pool (Postgres only; SQLite uses StaticPool) ---
    db_pool_size: int = Field(default=20, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout_sec: float = Field(default=30.0, validation_alias="DB_POOL_TIMEOUT_SEC")
    db_pool_recycle_sec: int = Field(default=1800, validation_alias="DB_POOL_RECYCLE_SEC")
    db_pool_pre_ping: bool = Field(default=True, validation_alias="DB_POOL_PRE_PING")
    db_statement_timeout_ms: int = Field(default=30_000, validation_alias="DB_STATEMENT_TIMEOUT_MS")
    # --- /DB connection pool ---

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> Any:
        if value is None or value == "":
            return ["http://localhost:5173"]
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return ["http://localhost:5173"]
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"BACKEND_CORS_ORIGINS is not valid JSON: {exc}") from exc
                if not isinstance(parsed, list):
                    raise ValueError("BACKEND_CORS_ORIGINS JSON must be a list")
                return [str(item) for item in parsed]
            return [item.strip() for item in raw.split(",") if item.strip()]
        raise ValueError("BACKEND_CORS_ORIGINS must be a list or string")

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _enforce_secrets_outside_development(self) -> Settings:
        if self.app_env == "development":
            return self

        problems: list[str] = []
        if _looks_like_placeholder(self.secret_key):
            problems.append("SECRET_KEY")
        if _looks_like_placeholder(self.jwt_secret_key):
            problems.append("JWT_SECRET_KEY")
        if _looks_like_placeholder(self.database_url):
            problems.append("DATABASE_URL")
        if _looks_like_placeholder(self.receipt_signing_private_key_pem):
            problems.append("RECEIPT_SIGNING_PRIVATE_KEY_PEM")
        if (
            _looks_like_placeholder(self.receipt_signing_key_id)
            or self.receipt_signing_key_id.strip().lower() == "default"
        ):
            problems.append("RECEIPT_SIGNING_KEY_ID")

        if problems:
            joined = ", ".join(problems)
            raise ValueError(
                f"Refusing to start in APP_ENV={self.app_env}: placeholder values "
                f"detected for: {joined}. Set real secrets before booting."
            )

        # Stripe live-mode safety: production must NOT silently run mock billing.
        if self.is_production:
            if self.stripe_mock_mode:
                raise ValueError(
                    "Refusing to start in APP_ENV=production with STRIPE_MOCK_MODE=true. "
                    "Set STRIPE_MOCK_MODE=false and provide a real STRIPE_SECRET_KEY."
                )
            if not self.stripe_secret_key or _looks_like_placeholder(self.stripe_secret_key):
                raise ValueError(
                    "Refusing to start in APP_ENV=production: STRIPE_SECRET_KEY "
                    "is missing or a placeholder. Configure live Stripe credentials."
                )
            # AV scanner must be a real backend — stub_allow/stub_deny/eicar/
            # noop all bypass real malware detection. ``clamd`` is the only
            # production-acceptable backend today (audit gap F).
            if self.av_scanner_backend in {"stub_allow", "stub_deny", "eicar", "noop"}:
                raise ValueError(
                    "Refusing to start in APP_ENV=production with "
                    f"AV_SCANNER_BACKEND={self.av_scanner_backend!r}. "
                    "Configure a real backend (e.g. 'clamd')."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (FastAPI dependency-friendly)."""

    return Settings()


settings: Settings = get_settings()
