# FlightAlertPro

Flight price alert platform — track routes across multiple providers and get notified when prices drop.

## Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Supabase project
- (Optional) Stripe, Duffel, RapidAPI, Gmail, Telegram accounts

### 1. Clone & configure

```bash
git clone https://github.com/Prithiraz/FlightAlertPro.git
cd FlightAlertPro
```

**Backend environment** – the backend reads its `.env` from _one directory above_ the repo root (see `config.py`):

```bash
cp .env.example ../.env
# Edit ../.env and fill in real values
```

Minimum required variables:

```
VITE_SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

### 2. Backend

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Run the background alert worker:

```bash
python worker.py
```

Run a dry-run (no notifications sent, logs what would happen):

```bash
DRY_RUN=true python worker.py
```

Worker-related environment variables:

| Variable | Default | Description |
|---|---|---|
| `DRY_RUN` | `false` | When `true`, skips sending notifications and DB writes |
| `RAPIDAPI_RATE_LIMIT` | `30` | Max RapidAPI calls per minute per worker run |
| `DUFFEL_RATE_LIMIT` | `20` | Max Duffel calls per minute per worker run |

Verify all components:

```bash
curl http://localhost:8000/api/systemcheck
```

Check provider circuit-breaker status:

```bash
curl http://localhost:8000/health/integrations
```

### 3. Frontend

```bash
cd frontend
cp .env.example .env          # already has sane defaults
# Edit VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY to match your project
npm install
npm run dev                    # development server on :5173
npm run build                  # production build → frontend/dist/
```

Frontend environment variables (`frontend/.env`):

```
VITE_SUPABASE_URL=https://YOUR_PROJECT_ID.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

### 4. Example API calls

Search flights (segments contract):
```bash
curl -X POST http://localhost:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{
    "segments": [{"from_iata":"LAX","to_iata":"JFK","departure_date":"2026-05-01"}],
    "passengers": {"adults":1},
    "cabin_class": "economy"
  }'
```

Search flights (legacy flat contract):
```bash
curl -X POST http://localhost:8000/api/search/simple \
  -H 'Content-Type: application/json' \
  -d '{"from_iata":"LAX","to_iata":"JFK","departure_date":"2026-05-01","passengers":1}'
```

Create a price alert:
```bash
curl -X POST http://localhost:8000/api/alerts/create \
  -H 'Content-Type: application/json' \
  -d '{
    "user_email":"you@example.com",
    "from_iata":"LAX",
    "to_iata":"JFK",
    "max_price":400,
    "currency":"USD",
    "notification_channels":["email"]
  }'
```

Start a Stripe checkout (plan: pro | elite | business):
```bash
curl -X POST "http://localhost:8000/api/payments/checkout?user_email=you@example.com&plan=pro&success_url=https://example.com/success&cancel_url=https://example.com/cancel"
```

Fetch price history for an alert (requires auth token):
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/alerts/<alert_id>/history?limit=50"
```

### Manual test checklist

After the worker has run at least once:

1. **Trigger worker loop once**
   ```bash
   python -c "
   from worker import AlertWorker
   import asyncio, logging; logging.basicConfig(level='INFO')
   asyncio.run(AlertWorker()._check_alerts_async())
   "
   ```

2. **Confirm notification_log written (or dedupe skip)**
   ```bash
   # Check Supabase dashboard: table notification_log
   # Or query via psql / supabase CLI
   ```

3. **Fetch price history**
   ```bash
   curl -H "Authorization: Bearer <token>" \
     "http://localhost:8000/api/alerts/<alert_id>/history"
   ```

## Admin & Operations Runbook

### Setting up admin access

Add the `ADMIN_EMAILS` environment variable with a comma-separated list of admin email addresses:

```
ADMIN_EMAILS=alice@example.com,bob@example.com
```

Verify admin access:
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/admin/me
# Returns: {"email":"alice@example.com","is_admin":true}
```

Non-admin accounts receive `403 Forbidden`.

### Admin dashboard endpoints

| Endpoint | Description |
|---|---|
| `GET /api/admin/me` | Verify admin status |
| `GET /api/admin/overview` | System health (users, alerts, searches, notifications, errors) |
| `GET /api/admin/providers` | Per-provider health (requests, failures, latency) |
| `GET /api/admin/users?sort=alerts&limit=50` | User list with usage stats |
| `GET /api/admin/user/{user_id}/details` | Detailed user view |
| `GET /api/admin/analytics?days=7` | Daily usage series |

All endpoints require a valid JWT from an email in `ADMIN_EMAILS`.

### Kill switches

Set these environment variables to instantly disable features:

| Variable | Effect |
|---|---|
| `DISABLE_SEARCH=true` | Returns `503` for all flight searches |
| `DISABLE_NOTIFICATIONS=true` | Skips all notification sends |
| `DISABLE_PROVIDER_DUFFEL=true` | Skips Duffel as a search provider |

### Interpreting provider health

The `GET /api/admin/providers` endpoint aggregates data from `provider_metrics`.

- `requests_24h` – total API calls in the last 24 h
- `failures_24h` – failed calls; alert if this exceeds ~10% of requests
- `avg_latency_ms` – average response time; > 3000 ms indicates degradation
- `last_error` – timestamp of the most recent failure

Circuit-breaker state per provider is visible at `GET /health/integrations`.

### Responding to abuse events

1. A 429 response is returned when a user exceeds plan limits or an IP exceeds `SEARCH_IP_RATE_LIMIT_PER_MINUTE` (default 30 req/min).
2. IPs that exceed **3×** the per-minute cap are temporarily blocked for `SEARCH_IP_BLOCK_MINUTES` (default 15 minutes).
3. Block events are logged as `WARNING` in the application log.
4. To permanently block an IP, add reverse-proxy/WAF rules upstream of the API.
5. To reduce the per-IP cap further, set `SEARCH_IP_RATE_LIMIT_PER_MINUTE` in `.env`.

### Per-IP anti-abuse settings

| Variable | Default | Description |
|---|---|---|
| `SEARCH_IP_RATE_LIMIT_PER_MINUTE` | `30` | Max search requests per IP per minute |
| `SEARCH_IP_BLOCK_MINUTES` | `15` | How long an abusive IP is blocked |

---

## Growth Engine

### Public marketing routes

| Route | Description |
|---|---|
| `/` | Landing page (public, shown to unauthenticated users) |
| `/pricing` | Full plan comparison page |
| `/how-it-works` | Three-step explainer |
| `/privacy` | Privacy policy |
| `/terms` | Terms of service |
| `/ref/<code>` | Referral landing page |
| `/login?signup=1` | Signup form (pre-selected) |

### Referral system

The referral system lets existing users invite friends with a unique code link (`/ref/<CODE>`).

**Flow:**
1. User visits `/ref/ABC` → code is stored in `localStorage`.
2. A `visit` event is recorded in `referral_events`.
3. User clicks "Create Free Account" → goes to `/login?signup=1`.
4. After successful signup, the frontend calls `POST /api/referral/claim` with the stored code.
5. A row is written to `user_attribution` linking the new user to the referrer.
6. When the user becomes a paying customer (Stripe webhook), a `paid` event is written.

**API endpoints:**

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/referral/my-code` | Required | Return (or create) your referral code |
| `POST` | `/api/referral/track` | None | Track a referral event (visit/signup/paid) |
| `POST` | `/api/referral/claim` | Required | Attach a referral code to your account |
| `GET` | `/api/admin/referrals` | Admin | (Future) referral summary |

**To test locally:**
```bash
# 1. Visit the referral page in your browser
open http://localhost:5173/ref/TESTCODE

# 2. Check localStorage has the code
# In browser devtools: localStorage.getItem('referral_code')  → "TESTCODE"

# 3. Sign up via /login?signup=1
# 4. Verify the user_attribution row was created in Supabase
```

**Database tables** (see `20260301_growth_engine_tables.sql`):
- `referral_codes` – one row per user, unique code
- `referral_events` – visit / signup / paid events
- `user_attribution` – which referral code converted each user

### Lifecycle emails

Lifecycle emails are sent by a daily background job. Trigger it manually:

```python
from lifecycle_emails import run_lifecycle_emails
run_lifecycle_emails()          # live send
run_lifecycle_emails(dry_run=True)  # log only, no email sent
```

**Triggers:**
| Template | When |
|---|---|
| `welcome` | Within 1 hour of signup |
| `nudge_create_alert` | >2 hours after signup, searched but no alert |
| `tips_after_alert` | First alert created, tips not yet sent |
| `reengagement` | No activity for 7+ days |

**Environment variables needed:**
```
GMAIL_USER=alerts@yourdomain.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

Users can opt out in Settings → "Email Preferences". The `lifecycle_emails_opt_in` boolean is stored in `user_profiles` (column added in migration `20260301_growth_engine_tables.sql`).

### Events / growth analytics

All funnel events are stored in `growth_events` and surfaced in the admin Analytics page.

**Tracked events:**
- `landing_view`, `pricing_view`
- `signup_start`, `signup_complete`
- `first_search`, `first_alert_created`
- `upgrade_click`, `checkout_started`, `paid_success`

**API:**
```bash
POST /api/events
{ "event_name": "upgrade_click", "props_json": { "plan": "pro" } }
```

Auth is optional – anonymous events are stored with `user_id = null`.

**Growth admin endpoint:**
```bash
GET /api/admin/growth?days=14
```
Returns per-day counts for all funnel events. Visible in the Analytics page under "Growth Funnel".

### Upgrade components

- `UpgradeBanner` – shown when the user is near their alert limit (already in use on Dashboard).
- `UpgradeModal` – triggered when the user hits a hard limit or tries a premium feature.

**Usage:**
```jsx
import UpgradeModal from '../components/UpgradeModal';

// Inside a component:
{showUpgradeModal && (
  <UpgradeModal
    reason="alert_limit"         // 'alert_limit' | 'search_limit' | 'premium_feature'
    feature="WhatsApp alerts"    // optional, used for 'premium_feature' reason
    onClose={() => setShowUpgradeModal(false)}
  />
)}
```

The modal automatically tracks an `upgrade_click` event and redirects the user to `/billing`.

### Running the full build check

```bash
# Python syntax check
python -m compileall .

# Frontend production build
cd frontend && npm run build
```

---

## PWA & Push Notifications

FlightAlertPro ships as a **Progressive Web App** (PWA).

### Install on mobile / desktop

1. Open the app in Chrome or Edge on any device.
2. Go to **Settings → Install App**.
3. Tap "Install App" when the prompt appears, or use your browser's "Add to Home Screen" option.

### Enable push notifications

1. Go to **Settings → Push Notifications**.
2. Toggle "Enable browser push notifications".
3. Allow the permission prompt.

Requires backend VAPID keys (see `.env.example`):

```
VAPID_PUBLIC_KEY=<generated>
VAPID_PRIVATE_KEY=<generated>
VITE_VAPID_PUBLIC_KEY=<same public key, for frontend>
```

Generate keys: `npx web-push generate-vapid-keys`

For detailed setup, testing, and icon generation instructions see **[docs/pwa.md](docs/pwa.md)**.

---

## Deploying to staging / production

FlightAlertPro uses **Railway** (FastAPI backend) and **Vercel** (Vite/React frontend).

### Platform choice

| Layer | Platform | Why |
|---|---|---|
| Backend | [Railway](https://railway.app) | Native Python / FastAPI support, built-in env management, easy rollback |
| Frontend | [Vercel](https://vercel.com) | Zero-config Vite builds, preview URLs per branch, free tier |

### One-time setup

#### Backend (Railway)

1. Create a Railway project and a **backend** service pointing at this repo root.
2. Set the start command:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
3. Add all required env vars in **Railway → Variables** (see `docs/ops.md` for the full list).
4. Generate a **Railway token** (`railway login --browserless`) and add it as the
   `RAILWAY_TOKEN` GitHub secret.

#### Frontend (Vercel)

1. Import the repo into Vercel, set **Root Directory** to `frontend`.
2. Vercel auto-detects Vite; no extra build config needed.
3. Set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL` in Vercel → Settings → Environment Variables for each environment.
4. Generate a Vercel token and add `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` as GitHub secrets.

#### GitHub Environments

Create two environments in **GitHub → Settings → Environments**:
- `staging` – no required reviewers (auto-deploy on `main`)
- `production` – add required reviewers; deploy triggers on `v*` tag or manual dispatch

### Triggering deployments

| Target | How |
|---|---|
| Staging (auto) | Push or merge to `main` — the `deploy-staging` workflow runs automatically |
| Production (tag) | `git tag v1.2.3 && git push origin v1.2.3` |
| Production (manual) | GitHub UI → Actions → **Deploy – Production** → Run workflow |

### Required secrets & variables

#### GitHub Secrets (all environments)

| Secret | Description |
|---|---|
| `RAILWAY_TOKEN` | Railway API token for CLI deploys |
| `VERCEL_TOKEN` | Vercel personal access token |
| `VERCEL_ORG_ID` | Found in Vercel project settings |
| `VERCEL_PROJECT_ID` | Found in Vercel project settings |

#### GitHub Variables

| Variable | Environment | Value |
|---|---|---|
| `STAGING_BACKEND_URL` | staging | `https://your-staging.up.railway.app` |
| `PROD_BACKEND_URL` | production | `https://your-prod.up.railway.app` |
| `VITE_SUPABASE_URL` | all | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | all | Supabase anon key |
| `VITE_API_BASE_URL` | staging/prod | Backend Railway URL |

### Post-deploy smoke tests

The `smoke-test-staging` / `smoke-test-prod` job runs `scripts/smoke_test.sh` which checks:
- `GET /health` → HTTP 200
- `GET /health/integrations` → HTTP 200
- `GET /api/metadata/stats` → HTTP 200
- `GET /api/systemcheck` → HTTP 200

Run manually:
```bash
SMOKE_BASE_URL=https://your-backend.up.railway.app bash scripts/smoke_test.sh
```

### Further reading

- `docs/release-checklist.md` — step-by-step deploy + rollback guide
- `docs/ops.md` — backups, key rotation, incident response

## Performance Tuning

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CACHE_TTL_SECONDS` | `900` | How long (seconds) search results are cached (5–15 min recommended) |
| `PROVIDER_TIMEOUT_SECONDS` | `10` | Per-provider HTTP timeout; provider is skipped on timeout |
| `REDIS_URL` | *(unset)* | Optional Redis URL. If set, uses Redis for caching; otherwise in-memory LRU |

### Cache behaviour

- Search results for identical request payloads are cached for `CACHE_TTL_SECONDS`.
- Concurrent identical requests are deduplicated: only one upstream call is made.
- Response includes `cache_hit` (bool) and `cached_at` (ISO timestamp) fields.
- Partial results are returned when a provider fails; check `provider_status` in the response.

### Metrics endpoint

`GET /api/metrics` returns JSON with:
- `search_total`, `search_cache_hits`, `cache_hit_ratio`
- `provider_calls`, `provider_errors`, `provider_latency` (avg + p95 ms per provider)
- `circuit_breakers` state per provider

### Performance smoke test

Verify cache is working after deployment:

```bash
# Start the backend locally first, then:
./scripts/perf_smoke.sh http://localhost:8000
```

The script runs the same search twice and asserts `cache_hit=true` on the second call.

---

## Security

### How to store secrets

All secrets must be stored as **server-side environment variables only**.  Never commit real values to the repository.

| Rule | Detail |
|---|---|
| Backend secrets | Set in Railway/Render/etc. Environment Variables. Never in `frontend/.env`. |
| `SUPABASE_SERVICE_ROLE_KEY` | **Must never appear in any `VITE_*` variable.** The app validates this at startup and logs an error if found. |
| `STRIPE_SECRET_KEY` | Backend only. `STRIPE_PUBLISHABLE_KEY` is safe to expose to the frontend. |
| JWT secret (`SUPABASE_JWT_SECRET`) | Backend only. Never expose to the browser. |

### How to rotate keys

1. **Supabase JWT secret** – rotate in Supabase Dashboard → Project Settings → API → JWT Secret. Update `SUPABASE_JWT_SECRET` in Railway and redeploy. Existing sessions will be invalidated.
2. **Stripe keys** – generate new restricted keys in Stripe Dashboard, update env vars, redeploy.
3. **Webhook secret** (`STRIPE_WEBHOOK_KEY`) – regenerate in Stripe → Webhooks, update env var, redeploy. The old secret becomes invalid immediately.

### Webhook secret handling

The Stripe webhook endpoint (`POST /webhook/stripe`) verifies the `Stripe-Signature` header against `STRIPE_WEBHOOK_KEY` before processing any event.  Requests with missing or invalid signatures return `400`.

Webhook idempotency is enforced: duplicate event IDs are ignored (stored in cache with a 24 h TTL).

### CORS

`allow_credentials=True` requires explicit origins — wildcard `*` is rejected.  Configure `FRONTEND_ORIGINS` with your exact frontend URL(s):

```
FRONTEND_ORIGINS=https://app.yourdomain.com
```

The startup config validator logs an error if `*` is found in `ALLOWED_ORIGINS`.

### Kill switches

| Variable | Effect |
|---|---|
| `DISABLE_SEARCH=true` | Returns `503` for all flight searches |
| `DISABLE_NOTIFICATIONS=true` | Skips all notification sends |
| `DISABLE_BILLING=true` | Returns `503` for checkout and portal requests |
| `DISABLE_PROVIDER_DUFFEL=true` | Skips Duffel as a search provider |

### Audit log

All sensitive actions (alert create/delete, plan upgrade/downgrade/cancel) are written to the `audit_log` table.  Admin users can query it via:

```bash
GET /api/admin/audit?action=alert.create&limit=100
GET /api/admin/audit?user_id=<uuid>&date_from=2026-01-01T00:00:00
```

IP addresses are one-way hashed (SHA-256, truncated to 16 hex chars) before storage for GDPR compliance.

### Security smoke tests

```bash
# Run all security checks against a local or remote server:
SMOKE_BASE_URL=http://localhost:8000 bash scripts/security_smoke.sh

# With auth tokens for full coverage:
SMOKE_BASE_URL=http://localhost:8000 \
  USER_TOKEN=<regular-user-jwt> \
  ADMIN_TOKEN=<admin-jwt> \
  bash scripts/security_smoke.sh
```

The script verifies:
- Unauthenticated calls to auth-protected endpoints return `401`
- Admin-only endpoints return `401`/`403` for non-admin callers
- Per-IP rate limiting triggers a `429` on `/api/search` after 35 rapid requests
- Required security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`) are present

### Known limitations and next improvements

- **Audit log** is best-effort: a failed Supabase write is logged but does not fail the request.
- **Rate limiting** uses in-memory state — blocked IPs are not shared across multiple workers/processes. For multi-process deployments, configure `REDIS_URL` so the shared Redis cache is used.
- **GDPR deletion** – the audit log stores hashed IPs but retains email addresses; add a retention policy (e.g. delete rows older than 90 days) in Supabase.
- **2FA / MFA** – authentication delegates entirely to Supabase; enable MFA in the Supabase project settings.
- **WAF / DDoS protection** – add Cloudflare or similar in front of the API for volumetric attack protection.
