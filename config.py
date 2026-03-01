import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory in development; no-op when file is absent (staging/prod).
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

class Config:
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
    FLIGHTAPI_KEY = os.getenv('FLIGHTAPI_KEY')
    DUFFEL_API_KEY = os.getenv('DUFFEL_API_KEY')

    YCLOUD_API_KEY = os.getenv('YCLOUD_API_KEY')
    WABA_ACCESS_TOKEN = os.getenv('WABA_ACCESS_TOKEN')
    WABA_BUSINESS_ID = os.getenv('WABA_BUSINESS_ID')
    WABA_PHONE_NUMBER_ID = os.getenv('WABA_PHONE_NUMBER_ID')

    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_KEY = os.getenv('STRIPE_WEBHOOK_KEY')
    PRO_PLAN_PRICE_ID = os.getenv('PRO_PLAN_PRICE_ID')
    ELITE_PLAN_PRICE_ID = os.getenv('ELITE_PLAN_PRICE_ID')
    BUSINESS_PLAN_PRICE_ID = os.getenv('BUSINESS_PLAN_PRICE_ID')

    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    FRANKFURTER_API_URL = os.getenv('FRANKFURTER_API_URL', 'https://api.frankfurter.app')

    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

    GMAIL_USER = os.getenv('GMAIL_USER')
    GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')

    DATABASE_URL = os.getenv('DATABASE_URL', os.getenv('VITE_SUPABASE_URL'))
    SUPABASE_URL = os.getenv('VITE_SUPABASE_URL')
    SUPABASE_ANON_KEY = os.getenv('VITE_SUPABASE_ANON_KEY')
    SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET')

    # Comma-separated list of allowed CORS origins.
    # FRONTEND_ORIGINS (preferred) or ALLOWED_ORIGINS (legacy alias).
    # Must be explicit (not "*") when allow_credentials=True.
    ALLOWED_ORIGINS = [
        o.strip()
        for o in os.getenv(
            'FRONTEND_ORIGINS',
            os.getenv('ALLOWED_ORIGINS', 'http://localhost:5173,http://localhost:3000')
        ).split(',')
        if o.strip()
    ]

    MAX_ALERTS_PER_USER = int(os.getenv('MAX_ALERTS_PER_USER', '10'))

    REDIS_URL = os.getenv('REDIS_URL')

    SENTRY_DSN = os.getenv('SENTRY_DSN')

    DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    # Admin allowlist – comma-separated email addresses
    ADMIN_EMAILS = [
        e.strip()
        for e in os.getenv('ADMIN_EMAILS', '').split(',')
        if e.strip()
    ]

    # Cache and provider tuning
    CACHE_TTL_SECONDS = int(os.getenv('CACHE_TTL_SECONDS', '900'))
    PROVIDER_TIMEOUT_SECONDS = int(os.getenv('PROVIDER_TIMEOUT_SECONDS', '10'))

    # Kill switches
    DISABLE_SEARCH = os.getenv('DISABLE_SEARCH', 'false').lower() == 'true'
    DISABLE_NOTIFICATIONS = os.getenv('DISABLE_NOTIFICATIONS', 'false').lower() == 'true'
    DISABLE_BILLING = os.getenv('DISABLE_BILLING', 'false').lower() == 'true'
    DISABLE_PROVIDER_DUFFEL = os.getenv('DISABLE_PROVIDER_DUFFEL', 'false').lower() == 'true'

    # Per-IP search rate limiting (in-memory)
    SEARCH_IP_RATE_LIMIT_PER_MINUTE = int(os.getenv('SEARCH_IP_RATE_LIMIT_PER_MINUTE', '30'))
    SEARCH_IP_BLOCK_MINUTES = int(os.getenv('SEARCH_IP_BLOCK_MINUTES', '15'))

    API_RATE_LIMIT_PER_MINUTE = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '100'))
    NOTIFICATION_RATE_LIMIT_PER_HOUR = int(os.getenv('NOTIFICATION_RATE_LIMIT_PER_HOUR', '20'))
    # Per-provider per-minute call caps enforced by the worker's token bucket
    RAPIDAPI_RATE_LIMIT = int(os.getenv('RAPIDAPI_RATE_LIMIT', '30'))
    DUFFEL_RATE_LIMIT = int(os.getenv('DUFFEL_RATE_LIMIT', '20'))

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '7'))

    # VAPID keys for Web Push notifications (optional; push is disabled if absent)
    VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')
    VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
    VAPID_CONTACT_EMAIL = os.getenv('VAPID_CONTACT_EMAIL', '')

    @classmethod
    def validate(cls) -> None:
        """Fail fast with a readable error if required env vars are missing.

        In staging/production all Supabase and JWT vars must be present.
        In development only a warning is emitted so local startup is frictionless.
        """
        required_always = {
            'VITE_SUPABASE_URL': cls.SUPABASE_URL,
            'VITE_SUPABASE_ANON_KEY': cls.SUPABASE_ANON_KEY,
        }
        required_non_dev = {
            'SUPABASE_JWT_SECRET': cls.SUPABASE_JWT_SECRET,
        }

        missing = [k for k, v in required_always.items() if not v]

        if cls.ENVIRONMENT != 'development':
            missing += [k for k, v in required_non_dev.items() if not v]

        if missing:
            msg = (
                f"[config] Missing required environment variables: {', '.join(missing)}. "
                "Set them in your platform environment or in ../.env (development only)."
            )
            if cls.ENVIRONMENT == 'development':
                import logging as _log
                _log.getLogger(__name__).warning(msg)
            else:
                print(msg, file=sys.stderr)
                sys.exit(1)

        # Security checks: warn about dangerous misconfigurations.
        import logging as _log
        _sec = _log.getLogger(__name__)

        # SUPABASE_SERVICE_ROLE_KEY must never appear in frontend (VITE_) env vars.
        service_role_in_frontend = os.getenv('VITE_SUPABASE_SERVICE_ROLE_KEY')
        if service_role_in_frontend:
            _sec.error(
                "[security] VITE_SUPABASE_SERVICE_ROLE_KEY is set — this exposes a "
                "privileged service key to the browser. Remove it immediately."
            )

        # Wildcard CORS with credentials is insecure.
        if '*' in cls.ALLOWED_ORIGINS:
            _sec.warning(
                "[security] ALLOWED_ORIGINS contains '*' while allow_credentials=True. "
                "This is insecure. Specify explicit origins instead."
            )

config = Config()
