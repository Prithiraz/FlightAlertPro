# i18n, Currency Conversion & Timezone Guide

## Overview

FlightAlertPro supports internationalization (i18n), multi-currency price display, and timezone-aware date formatting. This document covers implementation details, TTL cache behaviour, and a manual test checklist.

---

## Currency Conversion

### How it works

Currency conversion is performed entirely in the frontend using the [Frankfurter API](https://www.frankfurter.app/) (European Central Bank rates).

- **Library**: `frontend/src/lib/currency.js`
- **Function**: `convert(amount, from, to)` – returns a `Promise<number|null>`
- **Formatting**: `formatCurrency(amount, currency, locale)` – uses native `Intl.NumberFormat`

### Frankfurter API endpoint used

```
GET https://api.frankfurter.app/latest?from=<FROM>&to=<TO>
```

The response returns the exact ECB rate for the requested pair.  Conversions are **exact** (not estimated or random) — they use the official ECB reference rates published by Frankfurter.

### TTL Cache

Rates are cached client-side (in a `Map`) per `FROM_TO` pair with a **1-hour TTL**:

| Detail | Value |
|--------|-------|
| Cache store | `Map` in module scope (per browser session) |
| Cache key | `"FROM_TO"` (e.g. `"USD_GBP"`) |
| TTL | 3,600,000 ms (1 hour) |
| Stale behaviour | New fetch attempted; on failure returns `null` |

### Graceful fallback

If the Frankfurter API is unreachable (network error, timeout, unsupported currency):
- `convert()` returns `null`
- The UI falls back to displaying the original currency amount unchanged
- No error is thrown to the user; conversion is silently skipped

### Supported currencies

Any currency pair supported by Frankfurter/ECB is supported. Common ones include:
`USD, EUR, GBP, CAD, AUD, INR, JPY, SGD, AED, CHF, NZD, ZAR`

---

## Timezone Handling

### How it works

All backend timestamps are stored as **ISO 8601 UTC** strings (e.g. `2026-03-01T18:00:00Z`).

The frontend converts timestamps to the user's selected timezone using native `Intl.DateTimeFormat`.

- **Library**: `frontend/src/lib/datetime.js`
- **Functions**:
  - `formatDateTime(isoString, { locale, timezone })` – returns date + time string
  - `formatDate(isoString, { locale, timezone })` – returns date-only string

Both functions accept any valid [IANA timezone identifier](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g. `Europe/London`, `America/New_York`, `Asia/Kolkata`).

### User timezone preference

Users select their timezone in **Settings → Display Preferences**. The setting is stored in `user_profiles.timezone` and loaded by `PreferencesContext`.

---

## Locale & i18n

### Translation system

A lightweight translation system lives in `frontend/src/i18n/`:

- `en.json` – English key/value strings
- `index.js` – exports `t(key, vars?)` function

```js
import { t } from '../i18n';
t('settings.title')                     // → "Settings"
t('dashboard.flightsFound', { n: 5 })  // → "5 flights found"
```

If a key is missing, `t()` returns the key itself as a fallback.

### Adding a new language

1. Create `frontend/src/i18n/<locale>.json` with the same keys as `en.json`
2. In `index.js`, import the locale file and select based on the active locale string

### Locale-aware number formatting

`formatCurrency()` in `currency.js` uses `Intl.NumberFormat` with the user's locale:

```js
formatCurrency(1234.5, 'GBP', 'en-GB')  // → "£1,234.50"
formatCurrency(1234.5, 'EUR', 'de-DE')  // → "1.234,50 €"
```

---

## User Profile Preferences

Stored in the `user_profiles` database table:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `home_currency` | TEXT | `USD` | User's preferred currency for price display |
| `locale` | TEXT | `en-US` | BCP 47 locale string |
| `timezone` | TEXT | `UTC` | IANA timezone identifier |
| `preferred_date_format` | TEXT | `NULL` | Optional custom date format hint |

### API endpoints

- `GET /api/profile` – returns current preferences
- `POST /api/profile` – updates preferences (any subset of fields)

---

## Manual Test Checklist

### Locale / Timezone

- [ ] Go to **Settings → Display Preferences**
- [ ] Change Timezone to `Europe/London` and save
- [ ] Navigate to **Alerts** – verify `Created:` timestamps show UK time
- [ ] Navigate to **Notifications** – verify timestamps reflect London time
- [ ] Change Timezone to `America/New_York` – verify timestamps shift by expected offset
- [ ] Change Locale to `en-GB` – verify currency amounts format as `£1,234.00`
- [ ] Change Locale to `de-DE` – verify amounts format with European separators

### Home Currency

- [ ] Change Home Currency to `GBP` and save
- [ ] Run a flight search – verify results show prices in GBP
- [ ] Verify original currency is shown in parentheses when different
- [ ] Navigate to **Alerts** – verify max price displays in GBP with correct formatting
- [ ] Create a new alert – verify Currency dropdown defaults to `GBP`

### Frankfurter Offline / Fallback

- [ ] In browser DevTools → Network, block `api.frankfurter.app`
- [ ] Run a flight search – verify prices still display (in original currency, no crash)
- [ ] Re-enable network – verify prices update to converted values on next search

### Build validation

```bash
cd frontend && npm run build
python -m compileall .
```
