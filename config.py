import os
import logging
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

_logger = logging.getLogger(__name__)

# Mapping of env-var name -> human-readable feature that depends on it.
# If the var is absent, the feature is gracefully disabled (not a crash).
_FEATURE_ENV_VARS: dict[str, str] = {
    "VITE_SUPABASE_URL": "Database (Supabase)",
    "VITE_SUPABASE_ANON_KEY": "Database (Supabase)",
    "SUPABASE_SERVICE_KEY": "Database admin / worker",
    "STRIPE_SECRET_KEY": "Payments (Stripe)",
    "OPENAI_API_KEY": "AI search / insights",
    "DUFFEL_ACCESS_TOKEN": "Flight data (Duffel)",
    "AMADEUS_CLIENT_ID": "Flight data (Amadeus)",
    "AMADEUS_CLIENT_SECRET": "Flight data (Amadeus)",
    "RAPIDAPI_KEY": "Flight data (RapidAPI)",
    "GMAIL_USER": "Email notifications",
    "GMAIL_APP_PASSWORD": "Email notifications",
}


def validate_env_vars() -> list[str]:
    """Check every critical env var and emit a CRITICAL log for each missing one.

    Returns the list of missing variable names so callers can act on it if needed.
    The server is intentionally *not* crashed – each service disables itself when
    its key is absent.
    """
    missing: list[str] = []
    for var, feature in _FEATURE_ENV_VARS.items():
        if not os.getenv(var):
            missing.append(var)
            _logger.critical(
                "CRITICAL: %s is missing! The '%s' feature will be disabled.",
                var,
                feature,
            )
    if not missing:
        _logger.info("Environment variable validation passed – all critical keys present.")
    return missing


class Config:
    CHECKWX_API_KEY = os.getenv('CHECKWX_API_KEY')
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY')
    RAPIDAPI_HOST = os.getenv('RAPIDAPI_HOST', 'sky-scrapper.p.rapidapi.com')
    FLIGHTAPI_KEY = os.getenv('FLIGHTAPI_KEY')
    # DUFFEL_ACCESS_TOKEN is the dashboard token name; DUFFEL_API_KEY is the internal alias.
    # Accept either so that both .env conventions work.
    DUFFEL_ACCESS_TOKEN = os.getenv('DUFFEL_ACCESS_TOKEN') or os.getenv('DUFFEL_API_KEY')
    DUFFEL_API_KEY = os.getenv('DUFFEL_API_KEY') or os.getenv('DUFFEL_ACCESS_TOKEN')
    AMADEUS_CLIENT_ID = os.getenv('AMADEUS_CLIENT_ID')
    AMADEUS_CLIENT_SECRET = os.getenv('AMADEUS_CLIENT_SECRET')
    FLIGHT_API_KEY = os.getenv('FLIGHT_API_KEY')

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
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

    REDIS_URL = os.getenv('REDIS_URL')

    SENTRY_DSN = os.getenv('SENTRY_DSN')

    DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    API_RATE_LIMIT_PER_MINUTE = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '100'))
    NOTIFICATION_RATE_LIMIT_PER_HOUR = int(os.getenv('NOTIFICATION_RATE_LIMIT_PER_HOUR', '20'))

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '7'))

    ALERT_CHECK_INTERVAL_HOURS = int(os.getenv('ALERT_CHECK_INTERVAL_HOURS', '6'))

    CRON_SECRET = os.getenv('CRON_SECRET')

    # Comma-separated list of allowed CORS origins.
    # In production set this to your Vercel URL(s), e.g.:
    #   ALLOWED_ORIGINS=https://flightalertpro.vercel.app,https://www.flightalertpro.com
    # Leave empty (or unset) in development to allow all origins.
    _raw_origins = os.getenv('ALLOWED_ORIGINS', '')
    ALLOWED_ORIGINS: list[str] = (
        [o.strip() for o in _raw_origins.split(',') if o.strip()]
        if _raw_origins.strip()
        else []
    )

config = Config()
