# Business Tier — Enterprise & Team Features

This document describes the enterprise/business tier features of FlightAlertPro, including team workspaces, roles, API keys, and usage metering.

---

## Workspaces

Every user automatically gets a **personal workspace** on first login. Users on the **Business** or **Elite** plan can create additional workspaces for team collaboration.

### Workspace object

| Field | Type | Description |
|---|---|---|
| `id` | uuid | Unique workspace identifier |
| `name` | string | Display name |
| `owner_user_id` | string | Supabase `auth.uid()` of the owner |
| `plan` | string | Plan associated with the workspace (`free`, `pro`, `elite`, `business`) |
| `stripe_customer_id` | string | Stripe customer ID (for billing hooks) |
| `created_at` | timestamptz | Creation timestamp |

---

## Roles & Permissions

Each workspace membership has one of four roles:

| Role | Description | Permissions |
|---|---|---|
| `owner` | Workspace creator | Full control: manage workspace, billing, members, API keys |
| `admin` | Trusted team lead | Manage members, create/revoke API keys, view usage |
| `member` | Team contributor | Create and edit own alerts and saved searches |
| `viewer` | Read-only access | View alerts, searches, and usage — no writes |

### Permission matrix

| Action | Owner | Admin | Member | Viewer |
|---|---|---|---|---|
| View workspace members | ✓ | ✓ | ✓ | ✓ |
| Invite members | ✓ | ✓ | — | — |
| Change member roles | ✓ | ✓* | — | — |
| Remove members | ✓ | ✓ | — | — |
| Create/manage alerts | ✓ | ✓ | ✓ (own) | — |
| Create API keys | ✓ | ✓ | — | — |
| Revoke API keys | ✓ | ✓ | — | — |
| View usage | ✓ | ✓ | ✓ | ✓ |
| Manage billing | ✓ | — | — | — |

\* Admins cannot assign the `owner` role; only the owner can do that.

---

## API Endpoints

### Workspaces

```
GET  /api/workspaces                      — list workspaces for current user
POST /api/workspaces                      — create workspace (Business/Elite only)
```

### Members

```
GET    /api/workspaces/{id}/members              — list members
POST   /api/workspaces/{id}/invite               — invite by email (returns invite token)
POST   /api/workspaces/invites/accept            — accept invite using token
PATCH  /api/workspaces/{id}/members/{member_id}  — update role
DELETE /api/workspaces/{id}/members/{member_id}  — remove member
```

### API Keys (Business/Elite only)

```
POST   /api/workspaces/{id}/api-keys            — create key (plaintext returned once)
GET    /api/workspaces/{id}/api-keys            — list active keys (masked)
DELETE /api/workspaces/{id}/api-keys/{key_id}   — revoke key
```

### Usage

```
GET /api/workspaces/{id}/usage?range=7d    — workspace usage (7d / 30d / 90d)
GET /api/admin/usage?days=7               — admin-only usage summary across all workspaces
```

---

## API Key Usage

1. **Create** a key via `POST /api/workspaces/{id}/api-keys` (Business plan required). The plaintext key is returned **once** — store it securely.
2. **Use** the key by passing the `X-API-Key` header in requests:

```bash
curl -X POST https://api.yourapp.com/api/search \
  -H "X-API-Key: sk_live_YOURKEY" \
  -H "Content-Type: application/json" \
  -d '{"segments": [{"from_iata": "LHR", "to_iata": "JFK", "departure_date": "2026-06-01"}], "passengers": {"adults": 1}}'
```

3. **Revoke** a key via `DELETE /api/workspaces/{id}/api-keys/{key_id}`.

Key format: `sk_live_<random-url-safe-32-bytes>`  
Only the **first 12 characters** are stored in plaintext (as `key_prefix`) for display purposes.

---

## Usage Metering

Usage events are recorded in the `usage_events` table with the following `type` values:

| Event type | When recorded |
|---|---|
| `search` | Each `/api/search` call |
| `alert_check` | Each worker alert check cycle |
| `notification` | Each notification sent |

Usage is aggregated per workspace. Use `GET /api/workspaces/{id}/usage?range=30d` to retrieve counts.

### Stripe Metered Billing (optional)

Set `ENABLE_METERED_BILLING=true` in your environment to enable Stripe usage-based billing hooks.  
Each workspace can have a `stripe_customer_id` for linking to Stripe.

> **Note:** Full Stripe metered billing integration is not included in this milestone. The flag and `stripe_customer_id` field are placeholders for the next billing phase.

---

## curl Examples

### Create a workspace (Business plan)

```bash
curl -X POST https://api.yourapp.com/api/workspaces \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Travel Team"}'
```

### Invite a user

```bash
curl -X POST https://api.yourapp.com/api/workspaces/$WORKSPACE_ID/invite \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "role": "member"}'
```

### List members

```bash
curl https://api.yourapp.com/api/workspaces/$WORKSPACE_ID/members \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Create an API key

```bash
curl -X POST https://api.yourapp.com/api/workspaces/$WORKSPACE_ID/api-keys \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "CI Pipeline"}'
# Response includes "api_key" — save it securely, it won't be shown again.
```

### Search flights using X-API-Key

```bash
curl -X POST https://api.yourapp.com/api/search \
  -H "X-API-Key: sk_live_YOURKEY" \
  -H "Content-Type: application/json" \
  -d '{
    "segments": [{"from_iata": "LHR", "to_iata": "JFK", "departure_date": "2026-06-01"}],
    "passengers": {"adults": 1},
    "cabin_class": "economy"
  }'
```

### Get workspace usage

```bash
curl "https://api.yourapp.com/api/workspaces/$WORKSPACE_ID/usage?range=30d" \
  -H "Authorization: Bearer $JWT_TOKEN"
```

---

## Upgrade Path

| Plan | Workspace limit | API keys | Metered billing |
|---|---|---|---|
| Free | 1 (personal) | — | — |
| Pro | 1 (personal) | — | — |
| Elite | Multiple | ✓ | Optional |
| Business | Multiple | ✓ | Optional |

To upgrade, visit `/billing` in the app or call `POST /api/billing/checkout?plan=business`.
