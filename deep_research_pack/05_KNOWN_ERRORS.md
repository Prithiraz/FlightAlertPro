# FlightAlertPro — Known Errors

> Errors identified by static analysis of the codebase. No live server logs were available in the repository.

---

## ERROR 1 — Search request schema mismatch (frontend crashes on search)

**Severity:** 🔴 Critical — blocks all flight searches from the frontend

**Symptom:** Dashboard search form returns an HTTP 422 Unprocessable Entity from the backend.

**Root cause:**
- `frontend/src/pages/Dashboard.jsx` (line 53-67) sends a **flat JSON payload**:
  ```json
  { "from_iata": "LAX", "to_iata": "JFK", "departure_date": "2026-03-15", "passengers": 1, "cabin_class": "economy" }
  ```
- But `search.py` (line 43) defines `SearchRequest` expecting a **segments array**:
  ```json
  { "segments": [{ "from_iata": "LAX", "to_iata": "JFK", "departure_date": "2026-03-15" }], "passengers": { "adults": 1, "children": 0, "infants": 0 }, "cabin_class": "economy" }
  ```
- The legacy inline route in `main.py` (line 56) accepts the flat shape, but it is **shadowed** by `search.py`'s router, which is registered later and takes precedence.

**Likely fix:**
- Option A: Update `Dashboard.jsx` and `api.js` to send the segments-based payload.
- Option B: Re-expose the flat-payload version as a separate route (e.g., `/api/search/simple`) and point the frontend there.
- Option C: Add an alias route in `search.py` that accepts the flat shape and converts it internally.

---

## ERROR 2 — `config.SUPABASE_KEY` does not exist (systemcheck crashes)

**Severity:** 🟠 High — breaks `/api/systemcheck` alerts section

**Symptom:** `GET /api/systemcheck` returns `"alerts": { "status": "fail", "message": "Alert check failed", "details": "type object 'Config' has no attribute 'SUPABASE_KEY'" }`

**Root cause:**
- `systemcheck.py` line 197: `if config.SUPABASE_URL and config.SUPABASE_KEY:`
- `config.py` defines `SUPABASE_ANON_KEY` (line 36), **not** `SUPABASE_KEY`.

**Likely fix:**
- Change `config.SUPABASE_KEY` → `config.SUPABASE_ANON_KEY` in `systemcheck.py` line 197.
- Also update line 201: `supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)` → `create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)`.

---

## ERROR 3 — `main.py` payments checkout endpoint — wrong number of args

**Severity:** 🟠 High — breaks Stripe checkout

**Symptom:** `POST /api/payments/checkout` raises `TypeError: create_checkout_session() missing 1 required positional argument: 'success_url'` at runtime.

**Root cause:**
- `main.py` line 216: `stripe_service.create_checkout_session(user_email, success_url, cancel_url)` — 3 args.
- `payments.py` line 24: `def create_checkout_session(self, user_email, plan, success_url, cancel_url, user_id=None)` — expects 4 positional args (plan is second).

**Likely fix:**
- Update the `main.py` call to pass `plan` as the second argument:
  ```python
  session = stripe_service.create_checkout_session(user_email, "pro", success_url, cancel_url)
  ```
- Or update the endpoint to accept a `plan` query parameter.

---

## ERROR 4 — Metadata JSON files not found (airports/airlines load as empty)

**Severity:** 🟠 High — airport and airline search returns no results

**Symptom:** `GET /api/metadata/airports?q=LAX` returns `{ "count": 0, "cities": [] }`. Startup logs show no `✓ Loaded N airports` messages.

**Root cause:**
- `metadata.py` line 11: `DATA_DIR = Path(__file__).parent.parent / "data"`
- This resolves to a `data/` directory one level above the repo root, which does not exist.
- The actual JSON files (`airports_openflights.json`, `airports_commercial.json`, `airlines_openflights.json`) are in the **repo root** (same directory as `metadata.py`).

**Likely fix:**
- Change `metadata.py` line 11 to:
  ```python
  DATA_DIR = Path(__file__).parent
  ```

---

## ERROR 5 — Duffel integration disabled (no search results from Duffel)

**Severity:** 🟡 Medium — reduces search result coverage

**Symptom:** Duffel never contributes offers. Logs show: `"Duffel integration requires async wrapper - skipping"`.

**Root cause:**
- `search.py` lines 153-158: `search_duffel()` always returns `[]` with a log message because `duffel_service.search_flights()` is synchronous but is being called from an `async` FastAPI route handler. The sync call was intentionally skipped to avoid blocking.

**Likely fix:**
- Wrap `duffel_service.search_flights()` with `asyncio.get_event_loop().run_in_executor(None, ...)` to run the sync function in a thread pool:
  ```python
  import asyncio
  loop = asyncio.get_event_loop()
  results = await loop.run_in_executor(None, duffel_service.search_flights, segment.from_iata, segment.to_iata, segment.departure_date, None, 1, "economy")
  ```

---

## ERROR 6 — `Alerts.jsx` sends `channels` but backend expects `notification_channels`

**Severity:** 🟡 Medium — notification channels may not be stored correctly

**Symptom:** Alerts are created but the `notification_channels` field in Supabase may be empty or default to `["email"]` regardless of user selection.

**Root cause:**
- `frontend/src/pages/Alerts.jsx` line 66-73: the payload is built with `channels: form.channels`.
- `alerts.py` line 23: the Pydantic model field is `notification_channels: List[str]`.
- Pydantic may silently use the default `["email"]` if `channels` is passed but `notification_channels` is not.

**Likely fix:**
- Change `Alerts.jsx` to send `notification_channels` instead of `channels`:
  ```js
  notification_channels: form.channels,
  ```

---

## ERROR 7 — No `.env` file (all API integrations disabled on fresh clone)

**Severity:** 🟡 Medium — expected for development, but easy to miss

**Symptom:** All integrations show `"status": "disabled"`. Backend starts but search returns 0 results.

**Root cause:**
- No `.env` file is committed (correctly excluded by `.gitignore`).
- `config.py` loads from `../. env` (parent of the repo root). A fresh clone has no such file.

**Likely fix:**
- Create `../.env` (one directory above the repo) using the template in `02_CONFIG_AND_ENV.md`.
- Minimum required: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `RAPIDAPI_KEY`.

---

## ERROR 8 — Legacy `.tsx` files at repo root cause confusion

**Severity:** 🟢 Low — does not affect runtime

**Symptom:** Repo root contains `App.tsx`, `Alerts.tsx`, `AuthModal.tsx`, `AuthCallback.tsx`, `FlightSearchForm.tsx`, `Plans.tsx`, `SystemCheck.tsx`, `main.tsx`, `index.css`, `vite-env.d.ts` — an older TypeScript version of the frontend.

**Root cause:**
- These files appear to be an abandoned earlier version. The active frontend is in `frontend/src/`.

**Likely fix:**
- Move these files to a `legacy/` folder or delete them to reduce confusion.

---

## ERROR 9 — `Dashboard.jsx` "My Alerts" section is a placeholder

**Severity:** 🟢 Low — UI is incomplete but functional via `/alerts` route

**Symptom:** The Dashboard shows "Price alerts coming soon. Stay tuned!" instead of linking to the Alerts page.

**Root cause:** `Dashboard.jsx` lines 216-220 have a hardcoded placeholder section.

**Likely fix:**
- Add a `<Link to="/alerts">` or import and embed the `Alerts` component.
