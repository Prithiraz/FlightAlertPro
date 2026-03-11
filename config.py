import os
import logging
from pathlib import Path
from dotenv import load_dotenv

def _load_dotenv() -> str:
    """Try repo root, then parent directory, then cwd for .env. Returns the path that was loaded."""
    candidates = [
        Path(__file__).parent / '.env',
        Path(__file__).parent.parent / '.env',
        Path.cwd() / '.env',
    ]
    for candidate in candidates:
        if candidate.is_file():
            load_dotenv(candidate)
            return str(candidate)
    # No .env file found; fall back to environment variables already set
    return "(none found)"

_loaded_env_path = _load_dotenv()
logging.getLogger(__name__).debug("config: loaded .env from %s", _loaded_env_path)

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

    FRONTEND_ORIGINS = os.getenv('FRONTEND_ORIGINS')

    REDIS_URL = os.getenv('REDIS_URL')

    SENTRY_DSN = os.getenv('SENTRY_DSN')

    DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    API_RATE_LIMIT_PER_MINUTE = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '100'))
    NOTIFICATION_RATE_LIMIT_PER_HOUR = int(os.getenv('NOTIFICATION_RATE_LIMIT_PER_HOUR', '20'))

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '7'))

config = Config()
