# Release Checklist

Use this checklist every time you deploy to **staging** or **production**.

---

## Pre-deploy

- [ ] All CI checks green on the branch/tag you intend to deploy
- [ ] CHANGELOG or PR description reviewed by at least one other person
- [ ] Supabase migrations reviewed and tested locally (see [Migrations](#database-migrations))
- [ ] New environment variables documented and added to the platform dashboard
- [ ] Stripe webhook URL updated if the backend URL changed
- [ ] Alerts worker (`worker.py`) restart plan confirmed (if applicable)

---

## Database migrations

FlightAlertPro uses raw SQL migrations applied directly via the Supabase dashboard or CLI.

### Apply order

Migrations must be applied in filename-date order:

```
20251124210952_create_flight_search_tables.sql
20251126153328_add_system_tables.sql
20251201173516_20251201_fix_price_alerts.sql
20251201180032_add_channels_column_to_price_alerts.sql
20260208_add_last_triggered_price.sql
20260301_add_price_history.sql
20260301_admin_usage_events.sql
20260301_growth_engine_tables.sql
20260301_onboarding_saved_searches_templates.sql
```

### Via Supabase dashboard

1. Open your project → **SQL Editor**
2. Paste and run each file in date order
3. Confirm row counts / schema in **Table Editor**

### Via Supabase CLI

```bash
# One-off: apply a specific migration
supabase db push --db-url "$DATABASE_URL" < 20260301_add_price_history.sql
```

### Rollback a migration

Supabase does not auto-rollback. Write an inverse SQL statement and apply it manually:
```sql
-- Example: undo adding a column
ALTER TABLE price_alerts DROP COLUMN IF EXISTS last_triggered_price;
```

---

## Deploy steps

### Staging (automatic on push to `main`)

1. Push or merge to `main`
2. The `deploy-staging` GitHub Actions workflow triggers automatically
3. Wait for the `smoke-test-staging` job to pass
4. Verify in Supabase dashboard that data looks correct

### Production (manual)

1. Tag a release:
   ```bash
   git tag v1.2.3 && git push origin v1.2.3
   ```
   or use **Actions → Deploy – Production → Run workflow** in GitHub UI
2. A reviewer must **approve** the `production` environment in GitHub
3. After deploy, wait for the `smoke-test-prod` job to pass
4. Verify `/health` and `/health/integrations` on the production URL

---

## Post-deploy verification

- [ ] `GET /health` returns `{"status": "healthy"}`
- [ ] `GET /health/integrations` shows all expected integrations enabled
- [ ] `GET /api/systemcheck` returns `"ok": true`
- [ ] Stripe webhook deliveries are successful (check Stripe dashboard → Developers → Webhooks)
- [ ] Alerts worker is running (check Railway logs or the platform console)
- [ ] At least one test alert fires end-to-end (smoke account)

---

## Rollback procedure

### Backend rollback (Railway)

1. Open Railway dashboard → your service
2. Go to **Deployments** tab
3. Click **Rollback** on the previous successful deployment
4. Alternatively re-deploy the previous git tag via the CLI:
   ```bash
   git checkout v1.2.2
   railway up --service backend --environment production
   ```

### Frontend rollback (Vercel)

1. Open Vercel dashboard → your project → **Deployments**
2. Find the previous production deployment and click **Promote to Production**

### Database rollback

Apply the inverse SQL migration manually (see [above](#rollback-a-migration)).

---

## Key environment variables per environment

| Variable | dev | staging | prod |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `staging` | `production` |
| `FRONTEND_ORIGINS` | `http://localhost:5173` | staging Vercel URL | production domain |
| `VITE_SUPABASE_URL` | your-dev-project | your-staging-project | your-prod-project |
| `STRIPE_SECRET_KEY` | `sk_test_…` | `sk_test_…` | `sk_live_…` |
| `STRIPE_WEBHOOK_KEY` | test key | test key | live key |
| `SENTRY_DSN` | optional | recommended | required |
