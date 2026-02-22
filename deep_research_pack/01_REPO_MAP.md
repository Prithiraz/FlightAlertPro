# FlightAlertPro — Repository Map

> Only important files are listed. Data files, compiled `.pyc` files, `node_modules`, and legacy root-level `.tsx` files are omitted.

```
FlightAlertPro/                       ← repo root (also the Python package root)
│
├── main.py                           ← FastAPI app entry point; registers all routers; inline legacy routes
├── config.py                         ← Config class reading all env vars via os.getenv / dotenv
├── secrets.py                        ← SecretManager (reports which keys are present at startup)
│
├── ── Search & Flight Data ──
├── search.py                         ← /api/search router (segments-based, circuit-breaker, cache, dedup)
├── duffel_service.py                 ← Duffel API client (sync; disabled in search.py)
├── aerodatabox_service.py            ← AeroDataBox via RapidAPI
├── airscraper_service.py             ← AirScraper via RapidAPI
├── rapidapi_adapters.py              ← Thin adapters over aerodatabox_service + airscraper_service
├── merge_service.py                  ← Offer merging / deduplication utilities
├── metadata.py                       ← /api/metadata router — airport & airline lookup (OpenFlights data)
├── currency.py                       ← /api/currency router
├── currency_service.py               ← Frankfurter API wrapper (free, no key needed)
├── exchange_rates.py                 ← Exchange rate cache helper
│
├── ── Alerts ──
├── alerts.py                         ← /api/alerts router (create / list / delete / stats) — Supabase writes
├── worker.py                         ← APScheduler worker: polls active alerts every 5 min, triggers notifs
├── notifications.py                  ← Notification dispatcher (email / WhatsApp / Telegram)
├── email_service.py                  ← Gmail SMTP sender
├── telegram_service.py               ← Telegram bot sender
├── ycloud_service.py                 ← YCloud WhatsApp sender
├── ycloud_whatsapp.py                ← Alternative WABA (direct WhatsApp Business API) sender
│
├── ── Payments ──
├── payments.py                       ← PaymentsService class (Stripe checkout, webhook, subscription)
├── stripe_service.py                 ← Duplicate/alternate Stripe service (older version)
├── webhooks.py                       ← Stripe webhook handler (alternate module)
│
├── ── Auth ──
├── auth.py                           ← JWT / Supabase session validation utilities
├── gdpr.py                           ← GDPR data export / deletion helpers
│
├── ── System / Ops ──
├── systemcheck.py                    ← /api/systemcheck router (checks airports, airlines, currency, search,
│                                       stripe, alerts)
├── admin.py                          ← Admin endpoints (restricted)
├── logging_config.py                 ← Logging setup (file rotation, Sentry)
├── rate_limit.py                     ← Per-user rate limiting middleware
├── rate_limiter.py                   ← Rate limiter core logic
├── circuit_breaker.py                ← Circuit breaker shared utilities
├── cache.py                          ← Redis / in-memory cache abstraction
├── api_keys.py                       ← API key management
│
├── ── ML / Prediction ──
├── prediction_service.py             ← Price prediction orchestrator
├── price_prediction.py               ← Prediction model logic
│
├── ── DB Migrations (SQL) ──
├── 20251124210952_create_flight_search_tables.sql
├── 20251126153328_add_system_tables.sql
├── 20251201173516_20251201_fix_price_alerts.sql
├── 20251201180032_add_channels_column_to_price_alerts.sql
├── 20260208_add_last_triggered_price.sql  ← Adds last_triggered_price NUMERIC(10,2) to price_alerts
│
├── ── Static Data ──
├── airports_openflights.json         ← OpenFlights airport data (loaded by metadata.py)
├── airports_commercial.json          ← Commercial airports subset
├── airlines_openflights.json         ← OpenFlights airline data
├── airports.dat / airlines.dat       ← Raw OpenFlights .dat files
├── airport.csv / airport-codes.csv   ← Additional CSV airport datasets
│
├── ── Tests ──
├── test_worker.py                    ← Unit test for alert worker processing logic
├── test_stripe.py                    ← Unit test for Stripe service
├── smoke_test.py                     ← End-to-end smoke test (hits live endpoints)
├── cli.py                            ← CLI utility for manual operations
│
├── requirements.txt                  ← Python dependencies
├── .gitignore
├── README.md                         ← (Minimal — only "# FlightAlertPro")
├── IMPLEMENTATION_SUMMARY.md        ← PR summary for alert worker implementation
│
└── frontend/                         ← Vite React frontend
    ├── index.html                    ← Vite entry HTML
    ├── vite.config.js                ← Vite config (React plugin)
    ├── package.json                  ← npm deps (React 19, react-router-dom v7, @supabase/supabase-js)
    ├── eslint.config.js
    ├── .env.example                  ← Sample frontend env vars
    └── src/
        ├── main.jsx                  ← React entry point (mounts <App />)
        ├── App.jsx                   ← Root component: AuthContext, BrowserRouter, Routes
        ├── App.css / index.css       ← Global styles
        ├── components/
        │   ├── Header.jsx            ← Top nav bar (shown when logged in)
        │   └── ProtectedRoute.jsx    ← Auth guard: redirects to "/" if no session
        ├── pages/
        │   ├── Login.jsx             ← Login + Sign-up form (Supabase signInWithPassword / signUp)
        │   ├── ResetPassword.jsx     ← Password reset form (Supabase updateUser)
        │   ├── Dashboard.jsx         ← Main search UI + "My Alerts" placeholder
        │   ├── Search.jsx            ← Additional search page
        │   └── Alerts.jsx            ← Create / view / deactivate price alerts
        └── lib/
            ├── supabase.js           ← Supabase client (createClient with VITE_* env vars)
            └── api.js                ← API helpers (apiFetch, searchFlights, createAlert, listAlerts,
                                        deleteAlert) — base URL from VITE_API_BASE_URL or port 8000
```
