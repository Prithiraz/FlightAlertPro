# Privacy & Compliance Reference

_Last updated: March 2026_

## What We Store

| Category | Table | Fields stored |
|---|---|---|
| User profile | `user_profiles` | email, plan, currency preference, locale, timezone, notification channels, consent flags |
| Flight alerts | `price_alerts` | route, target price, channels, active/inactive status, last triggered |
| Saved searches | `saved_searches` | name, search parameters JSON |
| Alert templates | `alert_templates` | name, template JSON |
| Notification history | `notification_log` | alert ID, channel, status, sent timestamp, error message |
| Price history | `price_history` | alert ID, price, source, timestamp |
| Audit log | `audit_log` | action, user_id, hashed IP, user-agent, metadata |
| Deletion requests | `deletion_requests` | status, hashed email, hashed token, timestamps (no plaintext PII after deletion) |

We **do not** store raw payment card details (handled by Stripe).

---

## Retention Policy

| Data type | Default retention | Config variable |
|---|---|---|
| Notification logs | 90 days | `RETAIN_NOTIFICATION_LOG_DAYS` |
| Price history | 180 days | `RETAIN_PRICE_HISTORY_DAYS` |
| Audit log | 365 days | `RETAIN_AUDIT_LOG_DAYS` |

Old rows are pruned by running:

```bash
python scripts/prune_data.py
```

Use `--dry-run` to preview row counts without deleting.

---

## How Deletion Works

1. User initiates deletion via **Settings → Privacy & Data → Delete my account**.
2. Frontend sends `POST /api/privacy/delete-request` (JWT required, body: `{"confirmation":"DELETE_MY_ACCOUNT"}`).
3. Backend creates a `deletion_requests` row and returns a one-time confirmation token.
4. Frontend shows a second confirmation screen; user clicks **Confirm deletion**.
5. Frontend sends `POST /api/privacy/delete-confirm` with the token.
6. Backend:
   - Deletes or anonymises all user-owned rows (alerts, saved searches, templates, push subscriptions, price history, profile).
   - Anonymises `notification_log` rows (sets `user_id = NULL`).
   - Marks the `deletion_requests` row as `done`; clears `user_id` and retains only `email_hash` for audit purposes.
   - Writes an audit log entry (`action = privacy.delete_confirmed`).

All deletion audit records are non-PII: emails are stored as SHA-256 hashes.

---

## Responding to User Data Requests

### Export (GDPR Art. 20 / CCPA portability)

Call `GET /api/privacy/export` with the user's JWT.  
The response is a JSON object containing: profile, alerts, saved searches, notification history (last 90 days), price history (last 500 pts per alert), and billing status summary.

### Erasure (GDPR Art. 17 / CCPA right-to-delete)

Follow the deletion flow above, or run deletion manually via the Supabase dashboard for urgent cases.

### Manual admin deletion

As an admin, you can delete a user's rows directly in Supabase or via the admin dashboard.  Record the action in `audit_log` with `action = "admin.manual_delete"` for traceability.

---

## Consent Fields

The `user_profiles` table has three boolean consent columns:

| Column | Default | Meaning |
|---|---|---|
| `marketing_opt_in` | `false` | User consents to promotional/marketing emails |
| `product_updates_opt_in` | `true` | User consents to product release/feature emails |
| `transactional_only` | `false` | User wants only transactional emails (overrides the above) |

`lifecycle_emails_opt_in` controls product-lifecycle drip emails (this column already exists in the prior schema).

Lifecycle email logic in `lifecycle_emails.py` must check these flags before sending any non-transactional email.

---

## Audit Trail

All privacy-sensitive events are recorded in `audit_log`:

| Action | Trigger |
|---|---|
| `privacy.export` | User downloads their data |
| `privacy.delete_request` | User initiates deletion |
| `privacy.delete_confirmed` | Deletion completed |
| `privacy.prune_run` | Automated prune script runs |

Admin-only endpoint to query these (no PII returned):  
`GET /api/admin/privacy/events`

---

## Security Notes

- Export and deletion endpoints require a valid Supabase JWT (`Authorization: Bearer …`).
- The deletion flow uses a two-step confirmation (separate API calls) to prevent accidental or CSRF-triggered deletion.
- Confirmation tokens are single-use and stored only as SHA-256 hashes in the database.
- IP addresses in audit logs are hashed (not stored in plaintext).
