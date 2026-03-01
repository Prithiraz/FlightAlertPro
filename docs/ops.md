# Operations Runbook

## Backup strategy

FlightAlertPro stores all persistent data in **Supabase** (PostgreSQL).

### Supabase automatic backups

| Supabase plan | Retention | How to restore |
|---|---|---|
| Free | 7 days (daily) | Dashboard → Settings → Backups → Restore |
| Pro | 7 days (daily) | Dashboard → Settings → Backups → Restore |
| Team/Enterprise | Up to 30 days (PITR) | Contact Supabase support or use PITR |

Enable **Point-in-Time Recovery** (PITR) on paid plans for production workloads.

### Manual database export

```bash
# Full schema + data dump (requires psql client)
pg_dump "$DATABASE_URL" -Fc -f "backup_$(date +%Y%m%d_%H%M%S).dump"

# Restore from dump
pg_restore -d "$DATABASE_URL" backup_20260301_120000.dump
```

Store dumps in a private S3/R2 bucket; never commit them to the repo.

---

## Rotating secrets / API keys

1. **Generate** the new key in the provider dashboard (Stripe, Supabase, etc.)
2. **Add** the new value to the platform environment (Railway / Vercel) for staging first
3. **Deploy** to staging and verify integrations via `/health/integrations`
4. **Promote** to production (rotate production env var then redeploy)
5. **Revoke** the old key in the provider dashboard only after the new deploy is stable

### Key locations

| Secret | Platform | Rotation frequency |
|---|---|---|
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_KEY` | Stripe dashboard | On breach or every 12 months |
| `VITE_SUPABASE_ANON_KEY` | Supabase Settings → API | On breach; anon key is low-risk |
| `SUPABASE_JWT_SECRET` | Supabase Settings → API | On breach only – logs out all users |
| `RAILWAY_TOKEN` | Railway dashboard | On team member offboarding |
| `VERCEL_TOKEN` | Vercel dashboard | On team member offboarding |

---

## Incident response basics

### Service is down (`/health` returns 5xx or times out)

1. Check Railway logs: `railway logs --tail` (or Dashboard → Logs)
2. Check if the last deployment succeeded (Railway → Deployments tab)
3. If the bad deploy is identified, **rollback** (see `docs/release-checklist.md`)
4. Check Supabase status at https://status.supabase.com
5. If all else fails, redeploy the last known-good git tag

### High error rate in Sentry

1. Open Sentry project → Issues, filter by environment and last 1 h
2. Identify the most frequent error
3. If it is a database error: check Supabase metrics, consider increasing connection pool
4. If it is a provider error (Duffel/RapidAPI): circuit breaker state at `/health/integrations`
5. Apply a hotfix, tag, and deploy to production following the release checklist

### Worker stopped sending alerts

1. Confirm the worker process is running in Railway (separate service / cron)
2. Check worker logs for exceptions
3. Run a one-shot test via the public worker module entry point:
   ```bash
   python worker.py --once   # if the worker supports a --once flag
   # or trigger via the admin API if available
   ```
4. Verify Supabase connectivity: `GET /api/systemcheck`

---

## Testing Stripe webhooks locally

Use the Stripe CLI to forward events to your local server:

```bash
# Install Stripe CLI: https://stripe.com/docs/stripe-cli
stripe listen --forward-to http://localhost:8000/api/webhooks/stripe

# In a separate terminal, trigger a test event
stripe trigger checkout.session.completed
```

The `STRIPE_WEBHOOK_KEY` in your local `.env` must match the signing secret shown by
`stripe listen` (begins with `whsec_`).

---

## Testing webhooks in staging/production

1. Go to Stripe Dashboard → Developers → Webhooks → your endpoint
2. Click **Send test webhook** and choose an event type
3. Verify the response is `200 OK` and check application logs

---

## Monitoring checklist (weekly)

- [ ] Check `/health/integrations` – all expected providers show `"status": "ok"`
- [ ] Check Sentry for new high-severity issues
- [ ] Review Railway metrics (CPU/memory) for anomalies
- [ ] Review Supabase metrics (DB connections, row counts)
- [ ] Verify Stripe webhook delivery rate is 100%
- [ ] Run `bash scripts/smoke_test.sh` against production URL

---

## Environment variable reference (staging / production)

Set these in the Railway service environment and Vercel project settings.

### Backend (Railway)

```
ENVIRONMENT=staging                          # or production
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>
SUPABASE_JWT_SECRET=<jwt-secret>
STRIPE_SECRET_KEY=sk_live_…
STRIPE_PUBLISHABLE_KEY=pk_live_…
STRIPE_WEBHOOK_KEY=whsec_…
PRO_PLAN_PRICE_ID=price_…
ELITE_PLAN_PRICE_ID=price_…
BUSINESS_PLAN_PRICE_ID=price_…
FRONTEND_ORIGINS=https://your-app.vercel.app,https://yourdomain.com
SENTRY_DSN=https://…@sentry.io/…
LOG_LEVEL=INFO
```

### Frontend (Vercel)

```
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>
VITE_API_BASE_URL=https://your-railway-backend.up.railway.app
VITE_SENTRY_DSN=https://…@sentry.io/…   # optional
```
