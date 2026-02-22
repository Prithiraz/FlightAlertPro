# FlightAlertPro — API Endpoints

Base URL: `http://localhost:8000` (or the Codespaces `8000` forwarded URL)

Interactive docs available at: `GET /docs` (Swagger UI) and `GET /redoc`

---

## Root / Health

### `GET /`
**Source:** `main.py:79`
```json
{ "service": "FlightAlertPro API", "version": "1.0.0", "status": "operational" }
```

### `GET /health`
**Source:** `main.py:87`
```json
{ "status": "healthy", "timestamp": "2026-02-22T13:00:00", "environment": "development" }
```

### `GET /health/integrations`
**Source:** `main.py:95`
Returns status of: `duffel`, `rapidapi`, `flightapi`, `openai`, `stripe`, `ycloud`, `gmail`, `telegram`.
```json
{
  "duffel": { "enabled": false, "status": "disabled" },
  "rapidapi": { "enabled": true, "status": "ok" },
  ...
}
```

---

## Search (`search.py` router, prefix `/api`)

### `POST /api/search`
**Source:** `search.py:262`
**Called by:** `frontend/src/pages/Dashboard.jsx` (via `apiFetch('/api/search', {method:'POST', body:...})`), `frontend/src/lib/api.js:searchFlights()`

> ⚠️ **Schema mismatch:** The frontend sends a flat payload but `search.py` expects a segments-based request (see Known Errors).

**Request body (what `search.py` actually expects):**
```json
{
  "segments": [
    {
      "from_iata": "LAX",
      "to_iata": "JFK",
      "departure_date": "2026-03-15",
      "airline_filter": null
    }
  ],
  "passengers": { "adults": 1, "children": 0, "infants": 0 },
  "cabin_class": "economy",
  "currency": "USD",
  "max_stops": null,
  "baggage_min_kg": null,
  "baggage_max_kg": null
}
```

**Response:**
```json
{
  "query": { "from": "LAX", "to": "JFK", "date": "2026-03-15", "passengers": {...} },
  "total_offers": 5,
  "offers": [
    {
      "id": "adb-AA123",
      "source": "aerodatabox",
      "airline_iata": "AA",
      "airline_name": "American Airlines",
      "from_iata": "LAX",
      "to_iata": "JFK",
      "departure_time": "2026-03-15T08:00:00",
      "arrival_time": "2026-03-15T16:30:00",
      "duration_minutes": 330,
      "stops": 0,
      "price": 299.0,
      "currency": "USD",
      "cabin_class": "economy",
      "baggage_kg": null,
      "booking_url": null
    }
  ],
  "sources_queried": ["aerodatabox", "airscraper", "duffel"],
  "search_time_ms": 850
}
```

### `GET /api/search/circuit-breaker-status`
**Source:** `search.py:345`
Returns current circuit breaker state for each provider.

---

## Alerts (`alerts.py` router, prefix `/api/alerts`)

### `POST /api/alerts/create`
**Source:** `alerts.py:26`
**Called by:** `frontend/src/lib/api.js:createAlert()`, `frontend/src/pages/Alerts.jsx`

**Request body:**
```json
{
  "user_email": "user@example.com",
  "from_iata": "LAX",
  "to_iata": "JFK",
  "max_price": 350.00,
  "currency": "USD",
  "departure_date": "2026-03-15",
  "notification_channels": ["email"],
  "phone": null
}
```
> **Note:** The frontend (`Alerts.jsx`) sends `channels` (not `notification_channels`) in the payload body but the backend model field is `notification_channels`. Check if this causes a mapping issue.

**Response (201):**
```json
{
  "success": true,
  "alert_id": "uuid-here",
  "message": "Alert created successfully for LAX → JFK"
}
```

### `GET /api/alerts/list`
**Source:** `alerts.py:65`
**Called by:** `frontend/src/lib/api.js:listAlerts()`, `frontend/src/pages/Alerts.jsx`

**Query params:** `user_email` (required), `active_only` (default `true`)

**Response:**
```json
{
  "count": 2,
  "alerts": [
    {
      "id": "uuid",
      "user_email": "user@example.com",
      "from_iata": "LAX",
      "to_iata": "JFK",
      "max_price": 350.0,
      "currency": "USD",
      "departure_date": "2026-03-15",
      "notification_channels": ["email"],
      "active": true,
      "created_at": "2026-02-01T10:00:00",
      "triggered_at": null,
      "last_triggered_price": null
    }
  ]
}
```

### `DELETE /api/alerts/{alert_id}`
**Source:** `alerts.py:88`
**Called by:** `frontend/src/lib/api.js:deleteAlert()`, `frontend/src/pages/Alerts.jsx`

**Query params:** `user_email` (required) — used to verify ownership.

**Response:**
```json
{ "success": true, "message": "Alert deactivated" }
```
> Soft delete only — sets `active = false`, does not remove the row.

### `GET /api/alerts/stats`
**Source:** `alerts.py:113`
**Called by:** Not currently called by frontend.

**Response:**
```json
{ "total_alerts": 10, "active_alerts": 7, "triggered_alerts": 3 }
```

---

## Metadata (`metadata.py` router, prefix `/api/metadata`)

### `GET /api/metadata/airports?q=<query>&commercial_only=true&grouped=true&limit=10`
**Source:** `metadata.py:133`
Airport fuzzy search. Returns grouped-by-city results.

### `GET /api/metadata/airports/{iata}`
**Source:** `metadata.py:160`
Get single airport by IATA code.

### `GET /api/metadata/airlines?q=<query>&limit=20`
**Source:** `metadata.py:170`
Airline fuzzy search.

### `GET /api/metadata/airlines/{iata}`
**Source:** `metadata.py:210`
Get single airline by IATA code.

### `GET /api/metadata/stats`
**Source:** `metadata.py:220`
Returns counts of loaded airports and airlines.

---

## Currency (`currency.py` router, prefix `/api/currency`)

### `GET /api/currency/rates?base=USD`
**Source:** `currency.py`
Returns exchange rates from Frankfurter API.

### `POST /api/currency/convert`
**Source:** `main.py:175` (inline) — also potentially in `currency.py` router.

**Query params:** `amount`, `from_currency`, `to_currency`

**Response:**
```json
{
  "from_currency": "USD",
  "to_currency": "EUR",
  "original_amount": 100.0,
  "converted_amount": 91.50
}
```

---

## System Check (`systemcheck.py` router, prefix `/api`)

### `GET /api/systemcheck`
**Source:** `systemcheck.py:14`
Runs checks on airports, airlines, currency, search providers, Stripe, and alerts DB.

**Response:**
```json
{
  "ok": true,
  "checks": {
    "airports": { "status": "pass", "message": "Found 7000 airports", "details": "..." },
    "airlines": { "status": "pass", "message": "Found 6000 airlines", "details": "..." },
    "currency":  { "status": "pass", "message": "Currency conversion works", "details": "100 USD = 91.50 EUR" },
    "search":    { "status": "fail", "message": "No search providers configured", "details": "..." },
    "stripe":    { "status": "skipped", "message": "Stripe not configured", "details": "STRIPE_SECRET_KEY not set" },
    "alerts":    { "status": "fail", "message": "...", "details": "..." }
  },
  "timestamp": "2026-02-22T13:00:00"
}
```

---

## Payments & Stripe

### `POST /api/payments/checkout`
**Source:** `main.py:211`
> ⚠️ **Broken** — calls `stripe_service.create_checkout_session(user_email, success_url, cancel_url)` with 3 args but the method signature requires 4 (`user_email`, `plan`, `success_url`, `cancel_url`).

**Query params:** `user_email`, `success_url`, `cancel_url`

### `POST /webhook/stripe`
**Source:** `main.py:223`
Receives Stripe webhook events. Handles `checkout.session.completed` and `invoice.paid`.

---

## Inline Legacy Routes in `main.py` (lower priority, may be shadowed by routers)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/search` | Flat payload version — shadowed by `search.py` router |
| `POST` | `/api/predict` | Price prediction — not called by frontend |
| `POST` | `/api/alerts` | Simple alert creation — shadowed by `alerts.py` router (`/api/alerts/create`) |
| `POST` | `/api/notifications/send` | Direct notification send — not called by frontend |

---

## Which Frontend Pages Call Which Endpoints

| Frontend Page | Endpoint(s) Called |
|---|---|
| `Login.jsx` | Supabase Auth SDK only (no backend API calls) |
| `ResetPassword.jsx` | Supabase Auth SDK only |
| `Dashboard.jsx` | `POST /api/search` |
| `Search.jsx` | `POST /api/search` (via `apiFetch`) |
| `Alerts.jsx` | `POST /api/alerts/create`, `GET /api/alerts/list`, `DELETE /api/alerts/{id}` |
| `Header.jsx` | None |
| `ProtectedRoute.jsx` | None (reads from `AuthContext` only) |
