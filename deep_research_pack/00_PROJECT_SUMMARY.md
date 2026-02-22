# FlightAlertPro — Project Summary

## What the App Does

FlightAlertPro is a full-stack flight price monitoring and alerting service.

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python 3.13), Uvicorn |
| Frontend | Vite + React 19 (JSX), React Router v7 |
| Auth | Supabase (email/password, session token) |
| Database | Supabase (PostgreSQL via supabase-py) |
| Payments | Stripe Subscriptions (Pro / Elite / Business plans) |
| Notifications | Email (Gmail SMTP), WhatsApp (YCloud / WABA), Telegram Bot |
| Flight Data | Duffel API, AeroDataBox (RapidAPI), AirScraper (RapidAPI) |
| Background Jobs | APScheduler blocking scheduler (worker.py, every 5 min) |
| Caching | Redis (optional) or in-process Python dict |
| Error Tracking | Sentry SDK (optional) |

### Core User Flow
1. User signs up / logs in via Supabase auth on the React frontend.
2. User searches flights (origin IATA → destination IATA + date) via POST `/api/search`.
3. Backend fans-out to AeroDataBox + AirScraper + Duffel (disabled, see Known Errors), deduplicates, sorts by price, returns results.
4. User creates a price alert: `POST /api/alerts/create` — stored in Supabase `price_alerts` table.
5. Background worker (`worker.py`) polls every 5 minutes, runs search for each active alert, compares lowest price to `max_price`, and sends a notification if price drops below threshold (with deduplication via `last_triggered_price` field).
6. Stripe handles subscription billing; webhook `/webhook/stripe` updates subscription state.

---

## Current Status

### ✅ What Works
- FastAPI backend starts and all routers load (`metadata`, `search`, `currency`, `alerts`, `systemcheck`).
- React frontend builds and runs; login/signup/logout flow works via Supabase auth.
- `ProtectedRoute` component redirects unauthenticated users to `/`.
- Dashboard flight search form POSTs to `/api/search` and displays results.
- `/api/alerts/create`, `/api/alerts/list`, `/api/alerts/{id}` (DELETE) are implemented and write to Supabase.
- Background worker (`worker.py`) processes alerts, compares prices, sends notifications.
- Alert deduplication with `last_triggered_price` (migration: `20260208_add_last_triggered_price.sql`).
- Stripe checkout session creation and webhook verification are implemented.
- Offline airport/airline metadata loaded from OpenFlights JSON at startup.
- Circuit-breaker pattern on all three search providers.
- Currency conversion via Frankfurter API (no API key needed).
- System-check endpoint at `GET /api/systemcheck`.

### ❌ What Is Broken / Incomplete
- **Duffel integration disabled** in `search.py` — the async wrapper is missing; `search_duffel()` always returns `[]` with a log message.
- **`config.SUPABASE_KEY` does not exist** — `systemcheck.py` line 197 references `config.SUPABASE_KEY` but `config.py` only defines `config.SUPABASE_ANON_KEY`. This causes the alerts check in `/api/systemcheck` to always fail with an `AttributeError`.
- **Dashboard "My Alerts" section is a placeholder** — `Dashboard.jsx` shows "Price alerts coming soon." The dedicated Alerts page (`/alerts`) is functional, but the dashboard doesn't link to or embed it.
- **`search.py` POST `/api/search` uses a different request shape** (segments-based `SearchRequest`) than `main.py` POST `/api/search` (flat `SearchRequest`). Both routers mount at `/api/search`, causing a conflict — the router registered last wins. The `search_router` is included after direct inline routes, so `search.py`'s version takes effect at runtime, breaking the simple flat-field calls coming from `Dashboard.jsx`.
- **Frontend `Dashboard.jsx` sends a flat payload** (`from_iata`, `to_iata`, `departure_date`) but `search.py` expects `{ "segments": [{ "from_iata": ..., "to_iata": ..., "departure_date": ... }], "passengers": {...} }`.
- **`metadata.py` looks for data in a `../data/` directory** that does not exist at the repo root — the JSON files (`airports_openflights.json`, etc.) are in the repo root, not a `data/` sub-folder. Metadata loads silently as empty arrays, so airport/airline search endpoints return no results.
- **`main.py` `/api/payments/checkout`** calls `stripe_service.create_checkout_session(user_email, success_url, cancel_url)` with 3 positional args, but `PaymentsService.create_checkout_session` now requires 4 positional args (`user_email`, `plan`, `success_url`, `cancel_url`). This raises a `TypeError` at runtime.
- **No `.env` file is present** — both backend and frontend require environment variables that are not set in Codespaces by default.
- **Stripe plan IDs are not configured** — `PRO_PLAN_PRICE_ID`, `ELITE_PLAN_PRICE_ID`, `BUSINESS_PLAN_PRICE_ID` are `None` by default.
- **No frontend page for Plans / Payments** — `plans.tsx` (root-level legacy file) is not wired into the Vite React frontend.
- **Legacy `.tsx` files at repo root** (`App.tsx`, `Alerts.tsx`, `AuthModal.tsx`, `AuthCallback.tsx`, `FlightSearchForm.tsx`, `Plans.tsx`, `SystemCheck.tsx`, `main.tsx`) appear to be an older, abandoned TypeScript version; the active frontend is in `frontend/src/`.

---

## Exact Run Commands

### Backend (FastAPI)
```bash
# From repo root
cd /path/to/FlightAlertPro   # the folder containing main.py

# (First time) install dependencies
pip install -r requirements.txt

# Create .env in the PARENT of this folder (one level up) OR set vars in shell
# The config.py loads from Path(__file__).parent.parent / '.env'
# So if repo is at ~/FlightAlertPro/FlightAlertPro/, put .env at ~/FlightAlertPro/.env

# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Background Worker
```bash
# From repo root (same directory as worker.py)
python3 worker.py
```

### Frontend (Vite + React)
```bash
cd frontend

# (First time) install dependencies
npm install

# Create frontend/.env with VITE_* variables (see 02_CONFIG_AND_ENV.md)

# Start dev server
npm run dev
# Vite starts on port 5173 by default
```

---

## Codespaces Forwarded URLs

| Port | URL pattern | Serves |
|---|---|---|
| `5173` | `https://<codespace-name>-5173.preview.app.github.dev` | Vite React frontend — login, dashboard, search, alerts pages |
| `8000` | `https://<codespace-name>-8000.preview.app.github.dev` | FastAPI backend — all `/api/*` routes, `/health`, `/webhook/stripe`, OpenAPI docs at `/docs` |

> **Important for Supabase auth redirect URLs:** In Supabase Dashboard → Authentication → URL Configuration, add both Codespaces URLs as allowed redirect URLs. The password reset `redirectTo` is set to `window.location.origin + '/reset'`, so the Codespaces `5173` URL must be listed.
