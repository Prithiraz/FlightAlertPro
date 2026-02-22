# FlightAlertPro — Auth Flow

## Overview

Authentication is handled entirely by **Supabase Auth** (email/password). The React frontend uses the `@supabase/supabase-js` SDK. The backend does not independently issue or verify JWTs in the current implementation — it trusts the Supabase anon key for database writes and reads.

---

## Signup Flow

**File:** `frontend/src/pages/Login.jsx`

1. User fills in email + password and clicks "Sign Up" (toggle `isSignUp = true`).
2. Frontend calls `supabase.auth.signUp({ email, password })`.
3. Supabase sends a **confirmation email** to the user.
4. On success, the UI shows: *"Account created! Check your email to confirm, then log in."*
5. After confirming, the user can log in normally.

---

## Login Flow

**File:** `frontend/src/pages/Login.jsx`

1. User enters email + password, clicks "Log In".
2. Frontend calls `supabase.auth.signInWithPassword({ email, password })`.
3. On success, Supabase sets a session (stored in `localStorage` via `persistSession: true`).
4. `navigate('/dashboard')` is called — React Router redirects to Dashboard.
5. `App.jsx` listens via `supabase.auth.onAuthStateChange()` and updates the `AuthContext` `user` state, causing the `Header` to appear and all protected routes to become accessible.

---

## Session Check / Route Guard

**Files:** `frontend/src/App.jsx`, `frontend/src/components/ProtectedRoute.jsx`, `frontend/src/pages/Dashboard.jsx`

### `App.jsx` (global session listener)
- On mount: calls `supabase.auth.getSession()` to restore session from storage; sets `user` in `AuthContext`.
- Subscribes to `supabase.auth.onAuthStateChange()` for live session changes (login/logout/token refresh).
- Exposes `{ user, loading }` via `AuthContext`.

### `ProtectedRoute.jsx` (route guard)
```jsx
// frontend/src/components/ProtectedRoute.jsx
if (loading) return <div>Loading...</div>;
if (!user) return <Navigate to="/" replace />;
return children;
```
All routes `/dashboard`, `/search`, `/alerts` are wrapped in `<ProtectedRoute>`.

### `Dashboard.jsx` (additional guard)
- On mount, calls `supabase.auth.getUser()` and navigates to `/` if no user.
- Also subscribes to `onAuthStateChange` for logout detection.

---

## Password Reset Flow

**Files:** `frontend/src/pages/Login.jsx` (trigger), `frontend/src/pages/ResetPassword.jsx` (complete)

### Step 1 — Request reset
- User clicks "Forgot password?" on the Login page.
- Frontend calls:
  ```js
  supabase.auth.resetPasswordForEmail(email, {
    redirectTo: window.location.origin + '/reset',
  });
  ```
- The `redirectTo` URL must be listed in **Supabase → Authentication → URL Configuration → Redirect URLs**.
- In Codespaces: `https://<codespace-name>-5173.preview.app.github.dev/reset`
- Locally: `http://localhost:5173/reset`

### Step 2 — Complete reset
**File:** `frontend/src/pages/ResetPassword.jsx`
- The user clicks the link in their email, which navigates to `/reset` with a Supabase token in the URL fragment.
- Supabase JS SDK detects the token via `detectSessionInUrl: true` (set in `supabase.js`) and exchanges it automatically.
- The `ResetPassword` page captures the new password and calls `supabase.auth.updateUser({ password: newPassword })`.

---

## Logout

**File:** `frontend/src/pages/Dashboard.jsx`

```js
await supabase.auth.signOut();
navigate('/');
```

The `onAuthStateChange` listener in `App.jsx` sets `user` to `null`, causing `ProtectedRoute` to redirect all protected pages back to `/`.

---

## Supabase Configuration Required

In **Supabase Dashboard → Authentication → URL Configuration**:

| Setting | Value |
|---|---|
| Site URL | `http://localhost:5173` (local) or `https://<codespace>-5173.preview.app.github.dev` (Codespaces) |
| Redirect URLs (allowed list) | `http://localhost:5173/reset` |
| | `https://<codespace>-5173.preview.app.github.dev/reset` |
| | `https://<your-production-domain>/reset` |

---

## Supabase Client Configuration

**File:** `frontend/src/lib/supabase.js`

```js
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,       // stores session in localStorage
    autoRefreshToken: true,     // refreshes JWT before expiry
    detectSessionInUrl: true,   // handles OAuth/magic-link/reset tokens in URL hash
  },
});
```

---

## Backend Auth Note

The backend (`alerts.py`, `worker.py`) currently uses `config.SUPABASE_ANON_KEY` directly. This means any caller with the anon key can read/write alerts — there is **no server-side JWT verification of the calling user**. The `user_email` field in alert requests is trusted as-is from the request body. For production, the backend should verify the Supabase JWT from the `Authorization` header to enforce ownership.
