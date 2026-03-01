# PWA & Push Notifications Guide

FlightAlertPro ships as a Progressive Web App (PWA) that can be installed on any modern device and optionally receive browser push notifications when price alerts trigger.

---

## Running Locally

```bash
cd frontend
npm install
npm run dev        # starts Vite dev server at http://localhost:5173
```

The service worker (`public/sw.js`) **only activates over HTTPS or `localhost`**. The Vite dev server on `localhost` is sufficient for testing.

---

## Generating Icons

The `public/icons/` directory ships with two pre-generated icons (192 px and 512 px).

To regenerate or replace them with custom artwork:

1. Create a 512×512 source image (PNG or SVG).
2. Use any of the following tools:
   - **squoosh** (browser): https://squoosh.app
   - **sharp** (Node.js): `npx sharp-cli input.png -o icon-512.png resize 512 512`
   - **ImageMagick**: `convert input.png -resize 192x192 icon-192.png`
3. Place the output files in `frontend/public/icons/`.

---

## Testing PWA Install Prompt

The "Install App" button in **Settings** appears when the browser fires `beforeinstallprompt`.

Browser requirements:
- Chrome / Edge: served over **HTTPS** (or `localhost`).
- Firefox / Safari: use their own "Add to Home Screen" mechanism; no prompt event.

In **GitHub Codespaces** the preview URL is automatically HTTPS — use the Codespace URL for full PWA testing.

---

## Testing Push Notifications in Development

Push notifications require:

1. **HTTPS** (or `localhost` for Chrome).
2. **VAPID keys** configured in both backend and frontend.
3. **pywebpush** installed in the backend (`pip install pywebpush`).

### Step 1 — Generate VAPID keys

```bash
npx web-push generate-vapid-keys
```

Copy the output into your `.env` (see `.env.example`):

```
VAPID_PUBLIC_KEY=<your public key>
VAPID_PRIVATE_KEY=<your private key>
VAPID_CONTACT_EMAIL=you@example.com
VITE_VAPID_PUBLIC_KEY=<same public key>
```

> The `VITE_VAPID_PUBLIC_KEY` value is bundled into the frontend and used by the browser when subscribing.

### Step 2 — Install pywebpush

```bash
pip install pywebpush
```

### Step 3 — Enable push in Settings

1. Open the app in Chrome (over localhost or HTTPS).
2. Go to **Settings → Push Notifications**.
3. Toggle **"Enable browser push notifications"**.
4. Allow the permission prompt.

### Step 4 — Trigger a test alert

In development you can call the helper directly from the Python shell:

```python
from push_notifications import send_push_notification
send_push_notification("user@example.com", "Test", "Hello from FlightAlertPro!", url="/alerts")
```

Or trigger the worker manually:

```bash
python -c "from worker import AlertWorker; AlertWorker().check_alerts()"
```

---

## Database Migration

Run the migration to create the `push_subscriptions` table:

```sql
-- Copy contents of 20260301_push_subscriptions.sql into the Supabase SQL editor
```

---

## Offline Support

- The service worker caches the **app shell** (HTML entry point) so the app loads on repeat visits even without a network connection.
- **Last search results** are saved to `localStorage` (`fap_last_search_results`) and displayed automatically when the app detects `navigator.onLine === false`.
- `/api/metadata/*` responses (airports, airlines) are cached with a **stale-while-revalidate** strategy.

---

## Environment Variables Reference

| Variable | Where | Description |
|---|---|---|
| `VAPID_PUBLIC_KEY` | backend `.env` | VAPID public key for Web Push |
| `VAPID_PRIVATE_KEY` | backend `.env` | VAPID private key for Web Push |
| `VAPID_CONTACT_EMAIL` | backend `.env` | Contact email in VAPID claims |
| `VITE_VAPID_PUBLIC_KEY` | `frontend/.env` | Same public key exposed to browser |
