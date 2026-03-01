import os
from pathlib import Path
from dotenv import load_dotenv

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
    # Must be explicit (not "*") when allow_credentials=True.
    ALLOWED_ORIGINS = [
        o.strip()
        for o in os.getenv(
            'ALLOWED_ORIGINS',
            'http://localhost:5173,http://localhost:3000'
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

    # Kill switches
    DISABLE_SEARCH = os.getenv('DISABLE_SEARCH', 'false').lower() == 'true'
    DISABLE_NOTIFICATIONS = os.getenv('DISABLE_NOTIFICATIONS', 'false').lower() == 'true'
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

config = Config()
