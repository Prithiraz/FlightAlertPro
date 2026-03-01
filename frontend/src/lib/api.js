import { supabase } from './supabase.js';

// Default to the same host but on port 8000 (Codespaces-friendly fallback)
const _defaultBase = (() => {
  const url = new URL(window.location.href);
  url.port = '8000';
  return url.origin;
})();

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || _defaultBase;

/** Retrieve the Supabase access token for the current session (best-effort). */
async function getAuthHeaders() {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      return { Authorization: `Bearer ${session.access_token}` };
    }
  } catch (_) {
    // supabase may not be initialised (e.g. SSR / tests)
  }
  return {};
}

export async function apiFetch(path, options = {}) {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function request(method, path, body) {
  const authHeaders = await getAuthHeaders();
  const options = {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders },
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function searchFlights(params) {
  // If already segments-based, POST as-is; otherwise convert flat params to segments contract
  if (params.segments) {
    return request('POST', '/api/search', params);
  }
  const segmentsBody = {
    segments: [{
      from_iata: params.from_iata,
      to_iata: params.to_iata,
      departure_date: params.departure_date,
    }],
    passengers: { adults: params.passengers || 1 },
    cabin_class: params.cabin_class || 'economy',
    currency: params.currency || 'USD',
  };
  if (params.return_date) {
    segmentsBody.segments.push({
      from_iata: params.to_iata,
      to_iata: params.from_iata,
      departure_date: params.return_date,
    });
  }
  return request('POST', '/api/search', segmentsBody);
}

export function createAlert(params) {
  // Strip user_email – backend derives identity from the JWT
  const { user_email: _ignored, ...rest } = params;
  // Always map legacy channels -> notification_channels when channels is provided
  const payload = { ...rest };
  if (payload.channels !== undefined) {
    payload.notification_channels = payload.channels;
    delete payload.channels;
  }
  return request('POST', '/api/alerts/create', payload);
}

/** List the authenticated user's alerts (no user_email param needed). */
export function listAlerts() {
  return request('GET', '/api/alerts/list');
}

/** Deactivate an alert by ID (backend enforces ownership via JWT). */
export function deleteAlert(alertId) {
  return request('DELETE', `/api/alerts/${alertId}`);
}

export function searchAirports(query, { grouped = true, commercial_only = true, limit = 10 } = {}) {
  const params = new URLSearchParams({
    q: query,
    grouped: String(grouped),
    commercial_only: String(commercial_only),
    limit: String(limit),
  });
  return apiFetch(`/api/metadata/airports?${params}`);
}

export function searchAirlines(query, { limit = 20 } = {}) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return apiFetch(`/api/metadata/airlines?${params}`);
}

export function getCurrencyRates(base = 'USD') {
  return apiFetch(`/api/currency/rates?base=${encodeURIComponent(base)}`);
}

/** Fetch the current user's profile, plan, and usage. */
export function getMe() {
  return request('GET', '/api/me');
}

/** Fetch the current user's billing status and subscription info. */
export function getBillingStatus() {
  return request('GET', '/api/billing/status');
}

/**
 * Create a Stripe Checkout session for the given plan.
 * @param {'pro'|'elite'|'business'} plan
 */
export function createBillingCheckout(plan) {
  return request('POST', `/api/billing/checkout?plan=${encodeURIComponent(plan)}`);
}

/** Fetch a Stripe Billing Portal URL for the current user. */
export function getBillingPortal() {
  return request('GET', '/api/billing/portal');
}

/** Fetch the last N notifications for the current user. */
export function getNotificationHistory(limit = 20) {
  return request('GET', `/api/notifications/history?limit=${limit}`);
}

