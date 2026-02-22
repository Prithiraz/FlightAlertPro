# FlightAlertPro — Config & Environment Variables

## Backend Environment Variables

All variables are read in `config.py` via `os.getenv()`. The file loads a `.env` from `Path(__file__).parent.parent / '.env'` — **one directory above the repo root** (i.e., if the repo is at `~/work/FlightAlertPro/FlightAlertPro/`, the `.env` must be at `~/work/FlightAlertPro/.env`).

### Flight Data APIs

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `RAPIDAPI_KEY` | Yes (for search) | `None` | `config.py:9`, `aerodatabox_service.py`, `airscraper_service.py`, `rapidapi_adapters.py`, `main.py:103` |
| `FLIGHTAPI_KEY` | No | `None` | `config.py:10`, `main.py:103` |
| `DUFFEL_API_KEY` | No | `None` | `config.py:11`, `duffel_service.py` |

### WhatsApp / YCloud

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `YCLOUD_API_KEY` | No | `None` | `config.py:13`, `ycloud_service.py` |
| `WABA_ACCESS_TOKEN` | No | `None` | `config.py:14`, `ycloud_whatsapp.py` |
| `WABA_BUSINESS_ID` | No | `None` | `config.py:15`, `ycloud_whatsapp.py` |
| `WABA_PHONE_NUMBER_ID` | No | `None` | `config.py:16`, `ycloud_whatsapp.py` |

### Stripe Payments

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `STRIPE_SECRET_KEY` | Yes (for payments) | `None` | `config.py:18`, `payments.py:10`, `stripe_service.py`, `systemcheck.py:135` |
| `STRIPE_PUBLISHABLE_KEY` | No | `None` | `config.py:19` (frontend uses directly via env, not config) |
| `STRIPE_WEBHOOK_KEY` | Yes (for webhooks) | `None` | `config.py:20`, `payments.py:11`, `stripe_service.py` |
| `PRO_PLAN_PRICE_ID` | Yes (for checkout) | `None` | `config.py:21`, `payments.py:12` |
| `ELITE_PLAN_PRICE_ID` | No | `None` | `config.py:22`, `payments.py:13` |
| `BUSINESS_PLAN_PRICE_ID` | No | `None` | `config.py:23`, `payments.py:14` |

### OpenAI

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `OPENAI_API_KEY` | No | `None` | `config.py:25`, `main.py:104`, `prediction_service.py` |

### Currency

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `FRANKFURTER_API_URL` | No | `https://api.frankfurter.app` | `config.py:27`, `currency_service.py` |

### Notifications

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | No | `None` | `config.py:29`, `main.py:108`, `telegram_service.py` |
| `GMAIL_USER` | No | `None` | `config.py:31`, `main.py:107`, `email_service.py` |
| `GMAIL_APP_PASSWORD` | No | `None` | `config.py:32`, `email_service.py` |

### Supabase / Database

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `VITE_SUPABASE_URL` | **Yes** | `None` | `config.py:35` as `SUPABASE_URL`, `config.py:34` as `DATABASE_URL` fallback, `alerts.py:14`, `worker.py:35`, `auth.py` |
| `VITE_SUPABASE_ANON_KEY` | **Yes** | `None` | `config.py:36` as `SUPABASE_ANON_KEY`, `alerts.py:14`, `worker.py:35` |
| `DATABASE_URL` | No | falls back to `VITE_SUPABASE_URL` | `config.py:34` |

> **Note:** The backend shares the same `VITE_SUPABASE_*` variable names used by the frontend. This means you only need to define them once (in the backend `.env`) — but be sure to set them in both the backend `.env` and the frontend `.env` file.

### Infrastructure / Ops

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `REDIS_URL` | No | `None` | `config.py:38`, `worker.py:15`, `cache.py` |
| `SENTRY_DSN` | No | `None` | `config.py:40`, `main.py:27-33` |
| `DRY_RUN` | No | `false` | `config.py:42`, `notifications.py` |
| `ENVIRONMENT` | No | `development` | `config.py:44`, `main.py:93` |
| `API_RATE_LIMIT_PER_MINUTE` | No | `100` | `config.py:46` |
| `NOTIFICATION_RATE_LIMIT_PER_HOUR` | No | `20` | `config.py:47` |
| `LOG_LEVEL` | No | `INFO` | `config.py:49`, `logging_config.py` |
| `LOG_RETENTION_DAYS` | No | `7` | `config.py:50`, `logging_config.py` |
| `SYSTEMCHECK_TEST_USER` | No | `None` | `systemcheck.py:195` — enables live DB write test in `/api/systemcheck` |

---

## Frontend Environment Variables

All frontend variables are in `frontend/.env` (copy from `frontend/.env.example`). They must be prefixed with `VITE_` to be accessible via `import.meta.env`.

| Variable | Required | Default | Where Used |
|---|---|---|---|
| `VITE_SUPABASE_URL` | **Yes** | — | `frontend/src/lib/supabase.js:3` — `createClient()` first arg |
| `VITE_SUPABASE_ANON_KEY` | **Yes** | — | `frontend/src/lib/supabase.js:4` — `createClient()` second arg |
| `VITE_API_BASE_URL` | No | auto (current host, port 8000) | `frontend/src/lib/api.js:8` — base URL for all `fetch()` calls |

> `VITE_API_BASE_URL` defaults to `window.location.origin` with port replaced by `8000`. In Codespaces, you must set this explicitly to the forwarded `8000` URL (e.g., `https://<codespace-name>-8000.preview.app.github.dev`) because cross-origin port substitution does not work the same way.

---

## Sample `.env` Templates

### Backend `.env` (place at `../` relative to `main.py`, i.e., one directory above the repo root)

```dotenv
# ── Supabase ──────────────────────────────────────────
VITE_SUPABASE_URL=https://REDACTED.supabase.co
VITE_SUPABASE_ANON_KEY=REDACTED

# ── Flight Data APIs ──────────────────────────────────
RAPIDAPI_KEY=REDACTED
# FLIGHTAPI_KEY=REDACTED
# DUFFEL_API_KEY=REDACTED

# ── Stripe ────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_test_REDACTED
STRIPE_PUBLISHABLE_KEY=pk_test_REDACTED
STRIPE_WEBHOOK_KEY=whsec_REDACTED
PRO_PLAN_PRICE_ID=price_REDACTED
# ELITE_PLAN_PRICE_ID=price_REDACTED
# BUSINESS_PLAN_PRICE_ID=price_REDACTED

# ── Email (Gmail) ─────────────────────────────────────
GMAIL_USER=alerts@example.com
GMAIL_APP_PASSWORD=REDACTED

# ── Telegram ──────────────────────────────────────────
# TELEGRAM_BOT_TOKEN=REDACTED

# ── WhatsApp (YCloud or WABA) ─────────────────────────
# YCLOUD_API_KEY=REDACTED
# WABA_ACCESS_TOKEN=REDACTED
# WABA_BUSINESS_ID=REDACTED
# WABA_PHONE_NUMBER_ID=REDACTED

# ── OpenAI ────────────────────────────────────────────
# OPENAI_API_KEY=REDACTED

# ── Optional Infrastructure ───────────────────────────
# REDIS_URL=redis://localhost:6379/0
# SENTRY_DSN=https://REDACTED@oXXXXXX.ingest.sentry.io/XXXXXXX
ENVIRONMENT=development
# DRY_RUN=false
# LOG_LEVEL=INFO
```

### Frontend `frontend/.env`

```dotenv
VITE_SUPABASE_URL=https://REDACTED.supabase.co
VITE_SUPABASE_ANON_KEY=REDACTED
VITE_API_BASE_URL=http://localhost:8000
# In Codespaces, replace localhost:8000 with your forwarded URL:
# VITE_API_BASE_URL=https://<codespace-name>-8000.preview.app.github.dev
```
