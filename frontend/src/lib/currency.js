/**
 * Currency conversion engine using Frankfurter API (ECB rates).
 * Rates are cached per (from, to) pair with a 1-hour TTL.
 */

// 1-hour TTL matches the Frankfurter API update frequency and ensures users see
// reasonably fresh ECB rates without excessive API calls across a session.
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour
const FRANKFURTER_BASE = 'https://api.frankfurter.app';

// Cache: Map<"FROM_TO", { rate: number, fetchedAt: number }>
const rateCache = new Map();

/**
 * Fetch the exchange rate from Frankfurter API (or cache).
 * @param {string} from - ISO 4217 currency code
 * @param {string} to   - ISO 4217 currency code
 * @returns {Promise<number|null>} rate, or null on failure
 */
async function fetchRate(from, to) {
  if (from === to) return 1;

  const key = `${from}_${to}`;
  const cached = rateCache.get(key);
  if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) {
    return cached.rate;
  }

  try {
    const res = await fetch(
      `${FRANKFURTER_BASE}/latest?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
      { signal: AbortSignal.timeout(8000) }
    );
    if (!res.ok) return null;
    const data = await res.json();
    const rate = data?.rates?.[to];
    if (rate == null) return null;
    rateCache.set(key, { rate, fetchedAt: Date.now() });
    return rate;
  } catch {
    // Network failure or unsupported currency – return null for graceful fallback
    return null;
  }
}

/**
 * Convert an amount from one currency to another.
 * Returns null if conversion is unavailable (API down or unsupported pair).
 * @param {number} amount
 * @param {string} from
 * @param {string} to
 * @returns {Promise<number|null>}
 */
export async function convert(amount, from, to) {
  if (!amount || from === to) return Number(amount);
  const rate = await fetchRate(from.toUpperCase(), to.toUpperCase());
  if (rate == null) return null;
  return amount * rate;
}

/**
 * Format a currency amount using Intl.NumberFormat.
 * @param {number} amount
 * @param {string} currency - ISO 4217 code
 * @param {string} locale   - BCP 47 locale string (e.g. 'en-GB')
 * @returns {string}
 */
export function formatCurrency(amount, currency, locale = 'en-US') {
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    // Fallback for unsupported currency/locale combos
    return `${currency} ${Number(amount).toFixed(2)}`;
  }
}
