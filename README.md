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
