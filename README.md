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
