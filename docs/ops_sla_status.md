# Ops, SLA & Status Page Guide

## Overview

FlightAlertPro ships with built-in reliability tooling that does not require any external SaaS:

| Feature | Endpoint / Location |
|---|---|
| Public status page | `/status` (frontend) |
| Status API | `GET /api/status` |
| Health check | `GET /health` |
| Integration health | `GET /health/integrations` |
| System check | `GET /api/systemcheck` |
| Admin incidents | `GET/POST /api/admin/incidents` |
| Support bundle | `GET /api/support/bundle` |

---

## Metrics

### What gets recorded

All metrics are stored in the `service_metrics` Supabase table
(`id`, `ts`, `metric_name`, `value`, `labels_json`).

| Metric name | Description |
|---|---|
| `api_request_count` | Incremented per API request (grouped by endpoint) |
| `api_error_count` | Incremented for 5xx responses |
| `api_latency_ms` | Raw latency of each request |
| `notification_success_count` | Successful notification delivery |
| `notification_failure_count` | Failed notification delivery |
| `search_latency_ms` | Per-provider search latency |
| `provider_success` / `provider_failure` | Provider-level call outcome |
| `worker_last_run_ts` | Unix epoch of last alert worker run |
| `stripe_webhook_received` | Incremented on each Stripe webhook arrival |

### Retention

Metrics rows accumulate indefinitely; prune old rows periodically with:

```sql
DELETE FROM service_metrics WHERE ts < now() - INTERVAL '90 days';
```

---

## Status Page

The public status page at `/status` auto-refreshes every 30 seconds and shows:

- **Overall status** – `operational`, `degraded`, or `outage`
- **Components table** – API, Search, Alerts Worker, Notifications, Stripe Billing
- **Active incidents** – any non-resolved incidents from the `incidents` table

### How overall status is derived

| Condition | Status |
|---|---|
| Any component is `outage` | **outage** |
| Any component is `degraded` | **degraded** |
| All components `operational` or `disabled` | **operational** |

### Component health rules

| Component | Logic |
|---|---|
| **API** | Degraded if 5xx rate > 10 % in last 60 min |
| **Search** | Degraded/Outage based on uptime check failure rate (last 60 min) |
| **Alerts Worker** | Degraded if `worker_last_run_ts` is > 2 h ago |
| **Notifications** | Degraded if failure rate > 20 % in last 24 h |
| **Stripe Billing** | Disabled if Stripe not configured |

---

## Declaring Incidents

### Via API (admin token required)

```bash
# Create a new incident
curl -X POST https://your-api/api/admin/incidents \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Search degraded – Duffel API errors",
    "description": "Elevated error rates on Duffel flight search.",
    "severity": "major",
    "status": "investigating",
    "components": ["Search"]
  }'

# Update an incident
curl -X PATCH https://your-api/api/admin/incidents/{id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "identified", "description": "Root cause: Duffel rate limit. Throttling requests."}'

# Resolve an incident
curl -X POST https://your-api/api/admin/incidents/{id}/resolve \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Via Admin UI

Navigate to `/admin` → **Incident Management** section.

---

## Resolving Incidents

1. Confirm the underlying issue is fixed.
2. Update status to `monitoring` first if you want a soak period.
3. Click **Resolve** in the Admin UI, or POST to `/api/admin/incidents/{id}/resolve`.
4. The status page will immediately stop showing the incident.

---

## Interpreting Status Levels

### Degraded
- Some functionality is impaired but the system is operating.
- Users may experience slower searches or delayed notifications.
- Example: one provider down (Duffel), but airscraper fallback active.

### Outage
- A core feature is completely unavailable.
- Example: database unreachable, no searches possible.

---

## Uptime Checks

A synthetic check job runs every 5 minutes (inside the alert worker) and pings:

- `/health`
- `/api/systemcheck`
- `/api/metadata/stats`

Results are stored in `uptime_checks` (`ts`, `check_name`, `ok`, `latency_ms`, `error`).

The **Search** component health on the status page is computed from the last 60 minutes of
`api_systemcheck` uptime results.

Prune old rows:

```sql
DELETE FROM uptime_checks WHERE ts < now() - INTERVAL '7 days';
```

---

## Support Bundle

Users can export a support bundle from **Settings → Support → Export support bundle**.

The bundle contains (no secrets):

- User email, plan, locale
- Last 20 notification log entries
- Systemcheck snapshot (provider enabled flags)
- App version

Admins can also fetch it via:

```bash
curl https://your-api/api/support/bundle \
  -H "Authorization: Bearer $USER_TOKEN"
```

---

## curl Quick Reference

```bash
# Public status
curl https://your-api/api/status

# Health check
curl https://your-api/health

# Integration health
curl https://your-api/health/integrations

# System check
curl https://your-api/api/systemcheck

# List incidents (admin)
curl https://your-api/api/admin/incidents \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Create incident (admin)
curl -X POST https://your-api/api/admin/incidents \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Example","severity":"minor","status":"investigating"}'
```
