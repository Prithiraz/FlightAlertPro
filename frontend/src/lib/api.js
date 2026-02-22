// Default to the same host but on port 8000 (Codespaces-friendly fallback)
const _defaultBase = (() => {
  const url = new URL(window.location.href);
  url.port = '8000';
  return url.origin;
})();

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || _defaultBase;

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
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
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
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
  // Always map legacy channels -> notification_channels when channels is provided
  const payload = { ...params };
  if (payload.channels !== undefined) {
    payload.notification_channels = payload.channels;
    delete payload.channels;
  }
  return request('POST', '/api/alerts/create', payload);
}

export function listAlerts(userEmail) {
  return request('GET', `/api/alerts/list?user_email=${encodeURIComponent(userEmail)}`);
}

export function deleteAlert(alertId, userEmail) {
  return request('DELETE', `/api/alerts/${alertId}?user_email=${encodeURIComponent(userEmail)}`);
}
