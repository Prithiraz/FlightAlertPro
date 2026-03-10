import os
from pathlib import Path
from dotenv import load_dotenv

# Try to load .env from (1) repo root, (2) parent directory, (3) cwd – first match wins.
_candidate_paths = [
    Path(__file__).parent / '.env',
    Path(__file__).parent.parent / '.env',
    Path.cwd() / '.env',
]

_loaded_env_path = None
for _p in _candidate_paths:
    if _p.exists():
        load_dotenv(_p)
        _loaded_env_path = _p
        break

# print() is intentional here: config.py is imported before logging is configured,
# so logger calls would be silently dropped.
print(f"[config] .env loaded from: {_loaded_env_path}" if _loaded_env_path else "[config] No .env file found; using environment variables")

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

    REDIS_URL = os.getenv('REDIS_URL')

    SENTRY_DSN = os.getenv('SENTRY_DSN')

    DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    API_RATE_LIMIT_PER_MINUTE = int(os.getenv('API_RATE_LIMIT_PER_MINUTE', '100'))
    NOTIFICATION_RATE_LIMIT_PER_HOUR = int(os.getenv('NOTIFICATION_RATE_LIMIT_PER_HOUR', '20'))

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', '7'))

config = Config()
