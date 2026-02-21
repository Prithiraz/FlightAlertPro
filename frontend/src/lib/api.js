const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

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
  return request('POST', '/api/search', params);
}

export function createAlert(params) {
  return request('POST', '/api/alerts/create', params);
}

export function listAlerts(userEmail) {
  return request('GET', `/api/alerts/list?user_email=${encodeURIComponent(userEmail)}`);
}

export function deleteAlert(alertId, userEmail) {
  return request('DELETE', `/api/alerts/${alertId}?user_email=${encodeURIComponent(userEmail)}`);
}
