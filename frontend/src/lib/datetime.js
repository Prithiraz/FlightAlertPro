/**
 * Date/time formatting helpers using native Intl APIs.
 * All timestamps should be ISO 8601 UTC strings from the backend.
 */

/**
 * Format an ISO date-time string according to locale and timezone.
 * @param {string} isoString - ISO 8601 UTC timestamp
 * @param {{ locale?: string, timezone?: string }} options
 * @returns {string}
 */
export function formatDateTime(isoString, { locale = 'en-US', timezone = 'UTC' } = {}) {
  if (!isoString) return '—';
  try {
    return new Intl.DateTimeFormat(locale, {
      timeZone: timezone,
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(isoString));
  } catch {
    // Fallback: browser default locale/timezone
    return new Date(isoString).toLocaleString();
  }
}

/**
 * Format an ISO date-time string as a date only (no time).
 * @param {string} isoString - ISO 8601 UTC timestamp
 * @param {{ locale?: string, timezone?: string }} options
 * @returns {string}
 */
export function formatDate(isoString, { locale = 'en-US', timezone = 'UTC' } = {}) {
  if (!isoString) return '—';
  try {
    return new Intl.DateTimeFormat(locale, {
      timeZone: timezone,
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(isoString));
  } catch {
    return new Date(isoString).toLocaleDateString();
  }
}
